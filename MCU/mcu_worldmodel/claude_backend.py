"""Drive one turn through the Claude Code CLI.

The Claude-side sibling of `codex_backend.CodexTurn`, holding the same contract --
a persistent workspace, a project file carrying the system prompt (CLAUDE.md here,
AGENTS.md there), a turn prompt pointing at logs.txt, `actions.json` as the only
output that matters, and CLI-native session resume for conversation continuity --
behind the same public surface, so the agent swaps one for the other on a
`--cli` flag and nothing downstream can tell except the arm label.

Modeled on upstream PRO-LONG's `claude_code_agent.py`/`claude_events.py` rather than
forked from them: that implementation is a Docker container pool around
`docker exec claude -p` with ARC-specific prompt assembly, and none of it survives
here -- `claude_sandbox.sh` (bwrap) stands where Docker stood, exactly as
`codex_sandbox.sh` does for the codex arms.

Differences from CodexTurn worth naming, each measured on claude 2.1.233
 unless said otherwise:

  * Frames travel as base64 image blocks on a stream-json stdin message, not as
    `-i` flags. BLOCK ORDER IS LOAD-BEARING: text first, then images. An image
    block *before* the text block was silently dropped -- stored intact in the
    session transcript, invisible to the model ("I don't see an attached image"),
    no error anywhere -- while text-first landed on the first try. This is the
    same silent attach-loss failure codex's vision audit exists to catch, so
    `_build_stdin` fixes the order by construction and the audit records bytes.
  * The event stream shows the model's tool calls directly (codex 0.147 hides
    nested calls from `--json`), so every audit here reads the events of the turn
    that produced them; there is no rollout scan and no home search.
  * Sessions are created under our own uuid (`--session-id`) and resumed with
    `--resume`. A discarded session gets a fresh uuid: a used id cannot be
    re-created, and the transcript it leaves under
    `$CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<uuid>.jsonl` is the episode's record.
  * Auto-compaction is claude's default and is forced OFF (settings
    `autoCompactEnabled:false`) unless CLAUDE_AUTOCOMPACT names a token window.
    Same story CODEX_AUTO_COMPACT_TOKEN_LIMIT pins for codex: overflow means a
    cold start onto the filesystem memory, and a `compact_boundary` event in a
    non-compact arm is an arm redefinition, counted and shouted.
  * Auto-memory is forced off (env + settings). It files notes under the config
    dir keyed by cwd, so it would survive a session discard and quietly become a
    second memory mechanism inside an experiment that is about memory mechanisms.
  * The tool surface is an allowlist (`--tools`), which codex cannot do; the init
    event echoes the tool set in force and a mismatch raises before the turn is
    trusted. Bash/Read/Write/Edit/TodoWrite is the same capability set as codex's
    EXPECTED_NESTED_TOOLS (exec_command/view_image/apply_patch/update_plan).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from mcu_worldmodel.codex_backend import ENV_KEEP, scrub_env

# The one credential this channel signs with: a `claude setup-token` token, exported by
# scripts/claude-home.sh when MCU_CLAUDE_OAUTH_TOKEN is set. Every other secret-named
# variable is still dropped (scrub_env).
CLAUDE_ENV_KEEP: frozenset[str] = ENV_KEEP | {"CLAUDE_CODE_OAUTH_TOKEN"}

# The same capability set the codex arms hold (EXPECTED_NESTED_TOOLS over there):
# run a command, look at a file/frame, write and patch files, keep a plan list.
# WebSearch/WebFetch/Task/Skill/NotebookEdit exist in the CLI and are simply not
# on this list; the init event check below is what keeps a future default from
# slipping in unnoticed.
# TodoWrite (codex's update_plan analog) is not grantable here: 2.1.233 silently
# drops it from a --tools allowlist in this mode, and a
# plan-list renderer changes nothing about the workspace contract anyway.
ALLOWED_TOOLS: tuple[str, ...] = ("Bash", "Read", "Write", "Edit")

# Files a turn produces, cleared before each turn so a stale one from the previous
# turn is never mistaken for this turn's output. The codex twin's list.
TURN_ARTEFACTS: tuple[str, ...] = ("actions.json", "last_message.txt")

# What the CLI reports back in the init event when the allowlist is in force.
# Compared as a set: an extra tool is a capability this arm must not have, a
# missing one means the arm no longer matches the codex surface it is compared to.
EXPECTED_TOOLS: frozenset[str] = frozenset(ALLOWED_TOOLS)

# Overflow policy, the CODEX_AUTO_COMPACT_TOKEN_LIMIT sibling. Empty (default):
# autoCompactEnabled=false, a full conversation overflows and cold-starts, logs.txt
# stays the memory of record. A token count (100000..1000000): compaction fires at
# that window and the thread survives summarised -- a different memory story that
# has to be labelled as one (run-arm.sh --compact).
AUTOCOMPACT_TOKENS = os.environ.get("CLAUDE_AUTOCOMPACT", "").strip()

_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})

# The codex arms' `sandbox_mode="workspace-write"` twin: Claude Code's native
# sandbox (bubblewrap under the hood, like codex's) runs every Bash command with
# writes bounded and -- because the domain allowlist below is empty -- no network
# at all, so the agent's own commands cannot reach the Minecraft server or
# anything else even when the outer claude_sandbox.sh is not in force. The CLI
# process itself still reaches the model API: the sandbox wraps tool commands,
# not the harness. Measured, on haiku, both ways: curl NET_DOWN with
# echo and Write working, bare and under the outer sandbox alike (inside the
# outer bwrap no bwrap binary exists for srt to nest, and the egress proxy is
# what bounds the shell there -- the observable contract is the same).
# CLAUDE_NATIVE_SANDBOX=0 turns the setting off for debugging.
NATIVE_SANDBOX = os.environ.get("CLAUDE_NATIVE_SANDBOX", "1") != "0"

# Credential isolation for a hosted-provider arm (OpenRouter): a script
# that prints the API key, run by the CLI itself (settings `apiKeyHelper`), so the key
# exists only inside the CLI's HTTP client -- the twin of codex's auth.command
# (codex_backend.provider_auth_args). Measured on 2.1.257: `env | grep -i key` inside
# the model's Bash shows nothing, the init event reports apiKeySource=apiKeyHelper.
API_KEY_HELPER = os.environ.get("CLAUDE_API_KEY_HELPER", "").strip()

# Paths the model must not read, os.pathsep-separated: the secrets directory the key
# helper reads and the arm's own config dir (which holds the helper and, on a
# subscription arm, .credentials.json). Enforced twice, because two tools read files:
# the native sandbox denies the model's Bash (bwrap: `cat` sees "No such file"), and
# `permissions.deny` Read(...) rules cover the CLI's own Read tool, which the sandbox
# does not wrap. Measured on 2.1.257 -- both paths unreadable, workspace
# writable, a write outside it "Read-only file system".
SANDBOX_DENY_READ = [p for p in os.environ.get("CLAUDE_SANDBOX_DENY_READ", "").split(os.pathsep) if p]

# The CLI announces sandbox degradation only on stderr -- the init event carries
# no sandbox field (checked on 2.1.251) -- so wording is the only live signal.
# 2.1.251 prints "Sandbox disabled: ... socat not installed ... Commands will run
# WITHOUT sandboxing" and then runs every command bare: the no-net shell this arm
# is defined by silently becomes full-net, which is how
# one run ran unsandboxed with nothing failing. Wording
# drift would disarm this classifier; it is what catches a degradation in the
# middle of a run.
_SANDBOX_DEGRADED = re.compile(
    r"Sandbox disabled|WITHOUT sandboxing|Sandbox is required but failed")


def effort_for(effort: str) -> str:
    """Clamp the caller's reasoning effort onto the CLI's --effort vocabulary.

    codex accepts "minimal" and (on a local server) "none"; claude 2.1.233 takes
    low|medium|high|xhigh|max and rejects anything else at argv parse time, which
    would fail every turn of the arm. "none" has no claude meaning at all -- it is
    the vLLM thinking switch, and no claude arm is served by vLLM -- so both map
    to "low" and the mapping is logged once by the constructor.
    """
    return effort if effort in _EFFORTS else "low"


class SandboxViolation(RuntimeError):
    """A turn reached a capability the arm is defined not to have.

    Raised, not recorded, for the same reason as the codex twin: the result sits
    in the resumed conversation and the workspace, so the episode after it is
    contaminated whatever the score says.
    """


def is_overflow(name: str, text: str) -> bool:
    """Does this error mean the model's context window is full?

    The codex classifier verbatim: Anthropic's wording ("prompt is too long:
    218094 tokens > 200000 maximum", "input length and max_tokens exceed context
    limit") already lands on the "too long" and "context ... limit" arms, and
    keeping the classifiers identical keeps the two arms' cold-start triggers
    identical.
    """
    lname, lmsg = name.lower(), text.lower()
    return (
        "overflow" in lname
        or "too long" in lmsg
        or ("context" in lmsg and ("length" in lmsg or "limit" in lmsg or "window" in lmsg))
        or ("maximum" in lmsg and "tokens" in lmsg)
    )


# Subscription quota exhaustion ("You've reached your usage limit ... resets
# 3:00pm (UTC)"). Not an overflow -- the session is fine, the account is out of
# budget -- and not slept through here: the runner owns pacing, and a purple agent
# that sleeps inside a turn burns the green agent's step timeout into noops.
# Counted so a run that starved on quota is not read as a run that planned badly.
_QUOTA_RE = re.compile(r"usage limit|out of (?:extra )?usage", re.I)

_IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif"}


# The image tool has a different name on this channel: codex's `view_image` is Claude
# Code's `Read` on an image path (the Read tool returns the PNG as an image block --
# measured 2.1.257). The contract, the skills, the references, the turn prompt and the
# [RECALL] block all name the codex tool, so every harness-written text is renamed at
# the moment it reaches this channel; nothing else in the wording changes. The
# episodes tool prints the name at run time and reads it from MFM_IMAGE_TOOL (set in
# the CLI's environment below), since it runs inside the model's own shell.
IMAGE_TOOL = "Read"
_VIEW_IMAGE_RE = re.compile(r"\bview_image\b")


def rename_image_tool(text: str) -> str:
    """Codex's `view_image` -> this channel's `Read`, wherever the harness names it."""
    return _VIEW_IMAGE_RE.sub(IMAGE_TOOL, text)


def default_claude_bin() -> str:
    """$CLAUDE_BIN, else `claude` on PATH, else the npm-prefix install.

    An nvm shim can be a dead symlink (bin/claude -> bin/claude.exe, mode 644),
    which `shutil.which` correctly skips; the last candidate is an npm-prefix
    install. Resolved at construction
    so a missing binary fails the run at t=0, not minutes in.
    """
    for cand in (os.environ.get("CLAUDE_BIN"), shutil.which("claude"),
                 os.path.expanduser("~/.local/share/claude-code-npm/bin/claude")):
        if cand and os.access(cand, os.X_OK):
            return cand
    raise RuntimeError(
        "no runnable claude binary: set CLAUDE_BIN, or install @anthropic-ai/claude-code"
    )


def run_claude(
    args: Sequence[str], *, cwd: Path | str, stdin_payload: str,
    env: dict[str, str] | None, timeout: float,
) -> subprocess.CompletedProcess:
    """`subprocess.run(capture_output=True, text=True)` that kills the whole
    process group on timeout.

    Same shape and reason as `codex_backend.run_codex`: the direct child may be a
    wrapper (claude_sandbox.sh is bash around bwrap; the npm bin is a node
    launcher), and killing only it leaves the process actually talking to the
    model looping as an orphan. Started in its own session; the group dies.
    """
    proc = subprocess.Popen(
        list(args), cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(stdin_payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(list(args), timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(list(args), proc.returncode, stdout, stderr)


def scrubbed_env() -> dict[str, str]:
    """The runner's environment minus the CLI's own session namespace.

    This runner is routinely launched from inside a claude session itself (the
    development shell carries CLAUDECODE, CLAUDE_CONFIG_DIR, CLAUDE_CODE_SESSION_ID,
    a messaging socket, an effort override, ...), and any of those leaking into the
    child would tag it as a nested child session of the developer's account, point
    it at the developer's config dir, or pin its effort/compaction behaviour.

    Scrubbed by name, not by the whole CLAUDE_ prefix: this harness's OWN control
    variables share the prefix (CLAUDE_BIN, CLAUDE_TIMEOUT, CLAUDE_SANDBOX_*,
    CLAUDE_EVAL_HOME, CLAUDE_NODE_DIR, ...) and must flow through -- the first
    version stripped them all and claude_sandbox.sh quietly fell back to its
    defaults, which is exactly the wrong-config-in-force failure the init check
    exists to catch. What goes: CLAUDECODE, CLAUDE_CONFIG_DIR (the backend re-sets
    it), the CLI's runtime identity/behaviour knobs, and every CLAUDE_CODE_* key
    except the auth token a token-authenticated arm signs with.
    """
    drop_exact = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CLAUDE_PID", "CLAUDE_EFFORT",
                  "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"}
    keep = {"CLAUDE_CODE_OAUTH_TOKEN"}
    return {k: v for k, v in os.environ.items()
            if k in keep
            or not (k in drop_exact or k.startswith("CLAUDE_CODE_"))}


class ClaudeTurn:
    """`CodexTurn` for the Claude Code CLI: same constructor shape (the home
    parameter is the CLAUDE_CONFIG_DIR), same `run` contract, same lifecycle
    counters, same audit surface.

    **Interpretive caveat.** A score obtained here is "model via the Claude Code
    harness", as a codex arm's is "model via codex" -- ~27k tokens of the CLI's
    own scaffold, adaptive thinking, and Edit/Write tool idioms ride along, and
    none of them exist on the other channel. Every knob that CAN be matched is
    matched; the differences no knob removes are the ones above, and a cross-CLI
    comparison should state them.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        model: str,
        reasoning_effort: str = "low",
        base_url: str | None = None,
        claude_bin: str | None = None,
        config_dir: Path | None = None,
        # The same ceiling discipline as CodexTurn, read from the claude-side env
        # so one arm's knobs can never silently retune the other's.
        timeout: int = int(os.environ.get("CLAUDE_TIMEOUT", 1800)),
        transcript_dir: Path | None = None,
        # None = the arms' shared Bash/Edit/Read/Write surface. An explicit empty
        # sequence is the direct arm: no tools at all, the reply is the whole output
        # channel. Anything else would be a third tool surface and needs a fairness
        # entry before it needs code.
        tools: Sequence[str] | None = None,
        # None = the environment decides (CLAUDE_SESSION_MAX_TURNS, default 0: never
        # drop the session). The purple agent passes its value explicitly.
        session_max_turns: int | None = None,
    ) -> None:
        # Absolute, always: claude runs with cwd == the workspace, CLAUDE.md is
        # discovered from it, and actions.json is read back relative to it.
        self.workspace = Path(workspace).resolve()
        self.model = model
        if reasoning_effort not in _EFFORTS:
            logger.info(f"[claude] effort {reasoning_effort!r} is not in the CLI's "
                        f"vocabulary; sending 'low'")
        self.reasoning_effort = effort_for(reasoning_effort)
        # An Anthropic-compatible endpoint (a proxy, a gateway). Reaches the CLI
        # as ANTHROPIC_BASE_URL; credentials for it are the caller's problem
        # (ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN), exactly as codex's
        # local-server arm owns LOCAL_API_KEY.
        self.base_url = base_url
        self.claude_bin = claude_bin or default_claude_bin()
        self.config_dir = Path(config_dir).resolve() if config_dir else None
        self.timeout = timeout
        self.tools = list(ALLOWED_TOOLS) if tools is None else list(tools)
        # What the init-event tripwire holds the CLI to: the surface THIS arm
        # requested, not the module default -- measured on the first direct smoke,
        # where `--tools ""` correctly granted zero tools and the module-level
        # expectation then failed every turn for having exactly what it asked for.
        self.expected_tools = frozenset(self.tools)
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        if self.transcript_dir:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: str | None = None
        self.resolved_model: str | None = None
        self.calls = 0
        # Runaway ceiling, outside the scored protocol; same semantics and default
        # story as CODEX_MAX_CALLS (run-arm.sh exports both from one value).
        self.max_calls = int(os.environ.get("CLAUDE_MAX_CALLS", "0") or 0)
        self.ceiling_hits = 0
        self.images_attached = 0
        # Bytes of attachment carried by the current session, on the wire (4/3 for
        # base64). Claude's prompt cache makes a resumed thread's old frames cheap
        # rather than free; the counter is kept comparable with the codex arms,
        # where 5 MB of carried attachment was a measured 10x stall.
        self.session_attachment_bytes = 0
        self.peak_attachment_bytes = 0
        # Read off the live event stream (visible here, unlike codex 0.147):
        # Read-tool calls on image files are this arm's view_image analog.
        self.view_image_calls = 0
        # 0 by construction: attachments are base64 payloads we build from bytes we
        # already read, and the text-first block order that measurably lands them is
        # asserted in _build_stdin. Kept as a key so the two arms' audits line up.
        self.image_attach_failures = 0
        self.tool_errors = 0
        self.turns_with_tool_error = 0
        self.overflow_resets = 0
        self.timeout_resets = 0
        self.empty_resets = 0
        self.session_max_turns = (int(session_max_turns) if session_max_turns is not None
                                  else int(os.environ.get("CLAUDE_SESSION_MAX_TURNS", "0")))
        self.session_turns = 0
        self.age_resets = 0
        # Must stay 0 in a cold-start arm (see AUTOCOMPACT_TOKENS).
        self.compactions = 0
        self.quota_hits = 0
        # The CLI's own accounting, summed across calls. Unlike codex's cumulative
        # per-thread usage, a resumed `claude -p` invocation reports only its own
        # spend (history returns as cache reads), so plain sums are the truth.
        self.usage_totals = {"input_tokens": 0, "output_tokens": 0,
                             "cache_read_input_tokens": 0,
                             "cache_creation_input_tokens": 0}
        self.cost_usd_total = 0.0
        self.api_turns_total = 0
        self.tool_calls_total = 0

    # -- session lifecycle -------------------------------------------------

    def _discard_session(self, why: str, counter: str) -> None:
        """Drop the thread rather than retry into it -- the stance every unclean
        ending gets, inherited from upstream via the codex twin. Everything the
        next turn needs is in logs.txt and the workspace."""
        logger.warning(
            f"[claude] turn {self.calls}: discarding session {self.session_id} "
            f"({why}); the next call cold-starts"
        )
        self.session_id = None
        self.session_turns = 0
        self.session_attachment_bytes = 0
        setattr(self, counter, getattr(self, counter) + 1)

    def write_system_prompt(self, text: str) -> None:
        """CLAUDE.md is to claude what AGENTS.md is to codex: the project file the
        CLI discovers from its cwd and injects every turn. Written once; requires
        `--setting-sources project` (measured: with sources empty the file is
        stored but never read, and the model does not know its own instructions).

        Sharing codex's AGENTS.md instead does not work: claude 2.1.233 ignores a
        workspace AGENTS.md under both `--setting-sources ""` and `project`
        (measured; the AGENTS.md strings in the CLI bundle belong to
        `claude import`, which converts other agents' config INTO CLAUDE.md).
        Upstream PRO-LONG draws the same line: its codex agent writes AGENTS.md
        and its claude agent writes CLAUDE.md, one system prompt behind two
        filenames (claude_code_agent.py:236).
        """
        claude_md = self.workspace / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(rename_image_tool(text), encoding="utf-8")

    # -- argv / stdin ------------------------------------------------------

    def _settings(self) -> str:
        settings: dict[str, Any] = {
            # The overflow policy (see AUTOCOMPACT_TOKENS). CLI --settings outranks
            # the project source, so a workspace settings file cannot flip it back.
            "autoCompactEnabled": bool(AUTOCOMPACT_TOKENS),
            # A second memory mechanism has no place in a memory experiment.
            "autoMemoryEnabled": False,
        }
        if API_KEY_HELPER:
            settings["apiKeyHelper"] = API_KEY_HELPER
        if SANDBOX_DENY_READ:
            settings["permissions"] = {
                "deny": [f"Read({p.rstrip('/')}/**)" for p in SANDBOX_DENY_READ]}
        if NATIVE_SANDBOX:
            settings["sandbox"] = {
                "enabled": True,
                # No sandbox, no shell: a missing bwrap/socat must fail the turn
                # (and trip the stderr classifier), never run commands bare.
                "failIfUnavailable": True,
                "autoAllowBashIfSandboxed": True,
                # Empty allowlist: the agent's commands get no network, exactly
                # codex's workspace-write posture. The runner steps the world;
                # the agent only ever writes actions.json.
                "network": {"allowedDomains": [], "allowUnixSockets": [],
                            "allowLocalBinding": False},
            }
            if SANDBOX_DENY_READ:
                settings["sandbox"]["filesystem"] = {
                    "denyRead": list(SANDBOX_DENY_READ),
                    "allowWrite": [str(self.workspace)],
                }
        return json.dumps(settings)

    def _args(self) -> list[str]:
        args = [
            self.claude_bin, "-p",
            "--model", self.model,
            "--effort", self.reasoning_effort,
            # stream-json on both sides: input so frames ride as content blocks
            # (text first -- see _build_stdin), output so the turn's tool calls,
            # usage and result are events we parse rather than prose we guess at.
            # --verbose is load-bearing: print mode rejects stream-json without it.
            "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose",
            # `project` and nothing else: workspace CLAUDE.md is the system prompt
            # channel and must load; user/local settings belong to whatever
            # account the host happens to have and must not. The workspace is
            # agent-writable, so the project source is closed off elsewhere:
            # --strict-mcp-config kills a planted .mcp.json, --disable-slash-commands
            # kills planted skills, and the --settings flag above outranks a
            # planted settings.json on the keys this arm pins.
            "--setting-sources", "project",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--settings", self._settings(),
            "--tools", ",".join(self.tools),
            # Inside claude_sandbox.sh (bwrap binds exactly the workspace and an
            # episode home rw, one proxied route out) this is the codex arms'
            # workspace-write posture; unsandboxed it is the operator's choice to
            # have made, same as upstream's danger-full-access.
            "--permission-mode", "bypassPermissions",
        ]
        if AUTOCOMPACT_TOKENS:
            args += ["--autocompact", AUTOCOMPACT_TOKENS]
        if self.session_id:
            args += ["--resume", self.session_id]
        else:
            # Our uuid, not the CLI's: the transcript path under
            # projects/<cwd-slug>/<uuid>.jsonl is then known before the call runs.
            self.session_id = str(uuid.uuid4())
            self.session_turns = 0
            args += ["--session-id", self.session_id]
        return args

    def _build_stdin(self, prompt: str, images: Sequence[Path]) -> str:
        """One stream-json user message: text block first, then image blocks.

        The order is the whole function. Image-before-text was measured (2.1.233)
        to store the block and silently never show it to the model --
        the exact failure the codex arms' vision audit hunts -- while text-first
        landed. Do not reorder.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in images:
            media = _IMAGE_MEDIA.get(path.suffix.lower())
            if media is None:
                raise ValueError(f"unsupported attachment type: {path}")
            import base64
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": media,
                "data": base64.b64encode(path.read_bytes()).decode(),
            }})
        assert content[0]["type"] == "text", "text block must lead; see docstring"
        return json.dumps({"type": "user",
                           "message": {"role": "user", "content": content}}) + "\n"

    # -- the turn ----------------------------------------------------------

    def run(self, prompt: str, images: Sequence[Path] = (), *,
            expect_actions: bool = True) -> dict[str, Any]:
        """Execute one turn. Returns {"actions_json", "message", "ok", "error",
        "overflow"} -- the CodexTurn contract, unchanged.

        `expect_actions=False` for a turn that by design produces no
        `actions.json`; without it every such turn logs a
        missing-plan warning, which is not a defect and hides the ones that are.
        """
        if self.max_calls and self.calls >= self.max_calls:
            self.ceiling_hits += 1
            if self.ceiling_hits == 1:
                logger.error(f"[claude] call ceiling {self.max_calls} reached "
                             f"(CLAUDE_MAX_CALLS); refusing further model calls -- "
                             f"the episode continues on the agents' failure paths")
            return {"actions_json": None, "message": "", "ok": False,
                    "error": f"call ceiling {self.max_calls} reached",
                    "overflow": False}
        self.calls += 1
        if (
            self.session_id
            and self.session_max_turns
            and self.session_turns >= self.session_max_turns
        ):
            self._discard_session(
                f"reached {self.session_turns} turns, cap {self.session_max_turns}",
                "age_resets",
            )
        for stale in TURN_ARTEFACTS:
            (self.workspace / stale).unlink(missing_ok=True)

        env, dropped = scrub_env(scrubbed_env(), keep=CLAUDE_ENV_KEEP)
        if dropped and not getattr(self, "_env_scrub_logged", False):
            self._env_scrub_logged = True
            logger.info(f"[claude] env: not passed to claude: {', '.join(dropped)}")
        if self.config_dir:
            env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        env["DISABLE_AUTOUPDATER"] = "1"
        # statsig + sentry + fetch-of-the-day; probe shows analytics_disabled:true.
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        # Belt to the settings key's braces: both spellings of "no auto-memory".
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        env["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"] = "1"
        # A background shell outliving its turn would keep mutating the workspace
        # while the runner reads it; codex has no such tool and this arm gets none.
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        env["CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING"] = "1"
        if self.base_url:
            env["ANTHROPIC_BASE_URL"] = self.base_url
        # The episodes tool names the image tool in its output; see rename_image_tool.
        env["MFM_IMAGE_TOOL"] = IMAGE_TOOL
        prompt = rename_image_tool(prompt)

        images = [Path(p) for p in images]
        relative = [p for p in images if not p.is_absolute()]
        if relative:
            # Same guard, different reason than codex (-i resolves against codex's
            # cwd): we read the bytes ourselves, and a relative path is whatever
            # the runner's cwd happens to be, which is exactly the ambiguity the
            # absolute-only rule exists to kill.
            raise ValueError(f"attachments must be absolute paths: {relative}")
        missing = [p for p in images if not p.exists()]
        if missing:
            logger.error(
                f"[claude] turn {self.calls}: {len(missing)} attachment(s) do not "
                f"exist and will not be sent: {missing}"
            )
        images = [p for p in images if p.exists()]
        resuming = self.session_id is not None
        args = self._args()
        stdin_payload = self._build_stdin(prompt, images)
        self.images_attached += len(images)
        self.session_attachment_bytes += sum(p.stat().st_size for p in images) * 4 // 3
        self.peak_attachment_bytes = max(
            self.peak_attachment_bytes, self.session_attachment_bytes)
        logger.info(
            f"[claude] turn {self.calls} model={self.model} "
            f"resume={'yes' if resuming else 'no'} images={len(images)}"
        )
        try:
            proc = run_claude(
                args, cwd=self.workspace, stdin_payload=stdin_payload, env=env,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as expired:
            partial = expired.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            if self.transcript_dir:
                stem = f"turn_{self.calls:04d}.timeout"
                (self.transcript_dir / f"{stem}.events.jsonl").write_text(partial, encoding="utf-8")
                (self.transcript_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
            logger.error(
                f"[claude] turn {self.calls} timed out after {self.timeout}s; "
                f"{len(partial.splitlines())} events kept"
            )
            # Unconditional, like this package's codex twin: every timeout ends
            # whatever thread there was, cold starts included, and is counted.
            self._discard_session(f"timed out after {self.timeout}s", "timeout_resets")
            return {"actions_json": None, "message": "", "ok": False, "error": "timeout"}

        parsed = self._parse_events(proc.stdout)
        if self.transcript_dir:
            stem = self.transcript_dir / f"turn_{self.calls:04d}"
            stem.with_suffix(".events.jsonl").write_text(proc.stdout, encoding="utf-8")
            stem.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
            if proc.stderr:
                stem.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")

        degraded = NATIVE_SANDBOX and proc.stderr and _SANDBOX_DEGRADED.search(proc.stderr)
        if degraded:
            raise SandboxViolation(
                f"claude turn {self.calls}: the CLI dropped its native sandbox "
                f"({degraded.group(0)!r} on stderr), so this turn's commands ran "
                f"with an open network -- not the no-net shell the arm is defined "
                f"by. 2.1.251 degrades like this when socat is missing from PATH; "
                f"install it, or pair CLAUDE_NATIVE_SANDBOX=0 with the outer "
                f"claude_sandbox.sh. Stderr kept under {self.transcript_dir}."
            )

        if parsed["violations"]:
            raise SandboxViolation(
                f"claude turn {self.calls} used capabilities this arm must not "
                f"have: {parsed['violations']}. The surface in force is not the "
                f"one this arm requested ({sorted(self.expected_tools) or 'no tools'}); "
                f"see the transcript under {self.transcript_dir}."
            )

        if parsed["saw_result"]:
            self.session_turns += 1
        elif not resuming:
            # The cold start never produced a closing result, so the session it
            # minted an id for may not exist at all; forget the uuid rather than
            # resume into the void. Not a discard -- there was nothing to discard
            # -- which keeps empty_resets meaning what the codex twin means by it.
            self.session_id = None

        error = parsed["error"]
        overflowed = bool(error) and is_overflow("", error)
        if error and _QUOTA_RE.search(error):
            self.quota_hits += 1
            logger.error(f"[claude] turn {self.calls} hit the account usage limit; "
                         f"the turn is lost and the arm idles until it resets: "
                         f"{error[:200]}")
        if overflowed and self.session_id:
            self._discard_session("overflowed the context window", "overflow_resets")

        actions_path = self.workspace / "actions.json"
        actions_json = actions_path.read_text(encoding="utf-8") if actions_path.exists() else None
        message = parsed["message"]

        # Two independent facts, reported on separate lines -- a tool error inside
        # the turn is not why a plan is missing, and a turn run with expect_actions=False writes no
        # plan by design (the codex twin's lesson, kept).
        if error:
            logger.warning(f"[claude] turn {self.calls} reported: {error[:200]}")
        if actions_json is None and expect_actions:
            logger.warning(
                f"[claude] turn {self.calls} wrote no actions.json (rc={proc.returncode})"
                f"{'' if error else '; ' + proc.stderr.strip()[:200]}"
            )
        # Nothing at all -- no plan and no prose -- means the call never really
        # answered; a broken --resume is exactly this shape and a resumed retry
        # reproduces it forever. Cold-start instead, those turns included.
        if actions_json is None and not message and self.session_id:
            self._discard_session("produced no output at all", "empty_resets")
        return {
            "actions_json": actions_json,
            "message": message,
            "ok": actions_json is not None if expect_actions else bool(message),
            "error": error,
            "overflow": overflowed,
        }

    # -- event parsing -----------------------------------------------------

    def _parse_events(self, events: str) -> dict[str, Any]:
        """Fold one invocation's stream-json events into the turn's facts.

        Event shapes (2.1.233): `system/init` (session_id, resolved model, tools
        in force, mcp_servers), `system/compact_boundary`, `assistant` (text /
        tool_use / thinking blocks), `user` (tool_result blocks, is_error), and
        the closing `result` (usage, total_cost_usd, num_turns, is_error, the
        final text under "result").
        """
        message = ""
        error: str | None = None
        saw_result = False
        violations: dict[str, Any] = {}
        turn_tool_errors = 0
        for line in events.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "system":
                sub = event.get("subtype")
                if sub == "init":
                    if event.get("session_id") and event["session_id"] != self.session_id:
                        # The CLI answered under a different session than the one
                        # asked for; trusting ours would resume into the void.
                        logger.warning(f"[claude] session drift: asked "
                                       f"{self.session_id}, got {event['session_id']}")
                        self.session_id = event["session_id"]
                    self.resolved_model = event.get("model") or self.resolved_model
                    tools: set[str] = set(event.get("tools") or [])
                    if tools != self.expected_tools:
                        violations["tool_surface"] = sorted(
                            tools.symmetric_difference(self.expected_tools))
                    # The whole account-side surface must be flat: an MCP server,
                    # a skill, a slash command or a plugin in force means some
                    # config layer leaked past the isolation (a dirty home, a
                    # workspace plant, a CLI default resurrected by an upgrade)
                    # and the arm is not the one its results would claim.
                    for surface in ("mcp_servers", "skills", "slash_commands",
                                    "plugins"):
                        found = event.get(surface) or []
                        if surface == "plugins":
                            # The CLI's own built-in plugins (2.1.284 lists
                            # `agents-md@builtin`) are the CLI, not a config layer.
                            found = [pl for pl in found
                                     if not (isinstance(pl, dict) and pl.get("path") == "builtin")]
                        if found:
                            violations[surface] = found
                elif sub == "compact_boundary":
                    self.compactions += 1
                    if not AUTOCOMPACT_TOKENS:
                        logger.error(
                            f"[claude] turn {self.calls} shows a compaction event; "
                            f"the conversation is no longer the one this arm "
                            f"claims to run"
                        )
            elif kind == "assistant":
                for block in (event.get("message") or {}).get("content") or []:
                    btype = block.get("type")
                    if btype == "text":
                        message += block.get("text") or ""
                    elif btype == "tool_use":
                        name = block.get("name") or "unknown"
                        self.tool_calls_total += 1
                        if name not in self.expected_tools:
                            violations.setdefault("tool_calls", []).append(name)
                        if name == "Read":
                            path = str((block.get("input") or {}).get("file_path", ""))
                            if Path(path).suffix.lower() in _IMAGE_MEDIA:
                                self.view_image_calls += 1
            elif kind == "user":
                for block in (event.get("message") or {}).get("content") or []:
                    if block.get("type") == "tool_result" and block.get("is_error"):
                        self.tool_errors += 1
                        turn_tool_errors += 1
            elif kind == "result":
                saw_result = True
                usage = event.get("usage") or {}
                for key in self.usage_totals:
                    self.usage_totals[key] += int(usage.get(key) or 0)
                served = (usage.get("server_tool_use") or {})
                if any(int(served.get(k) or 0)
                       for k in ("web_search_requests", "web_fetch_requests")):
                    violations["server_tool_use"] = served
                cost = event.get("total_cost_usd")
                if isinstance(cost, (int, float)):
                    self.cost_usd_total += cost
                self.api_turns_total += int(event.get("num_turns") or 0)
                if event.get("is_error"):
                    error = str(event.get("result") or event.get("subtype") or "error")
                else:
                    # The final text is authoritative here; assistant blocks can
                    # include mid-loop narration the result already supersedes.
                    message = str(event.get("result") or message)
        if turn_tool_errors:
            self.turns_with_tool_error += 1
        return {"message": message.strip(), "error": error,
                "saw_result": saw_result, "violations": violations}

    # -- audit -------------------------------------------------------------

    def vision_audit(self) -> dict[str, Any]:
        """The codex audit's shape, from the event stream instead of rollouts.

        `image_attach_failures` stays 0 by construction (see _build_stdin); the
        counters that matter here are the lifecycle ones and the CLI's own
        accounting, which codex never exposes.
        """
        return {
            "frames_attached": self.images_attached,
            "call_ceiling_hits": self.ceiling_hits,
            "view_image_calls": self.view_image_calls,
            "image_attach_failures": self.image_attach_failures,
            "vision_audit_source": (
                str(self.config_dir / "projects") if self.config_dir else "events"),
            "tool_errors": self.tool_errors,
            "turns_with_tool_error": self.turns_with_tool_error,
            "attachment_bytes_peak": self.peak_attachment_bytes,
            "auto_compact_tokens": AUTOCOMPACT_TOKENS or "disabled",
            "api_key_helper": bool(API_KEY_HELPER),
            "sandbox_deny_read": list(SANDBOX_DENY_READ),
            "compactions": self.compactions,
            "overflow_resets": self.overflow_resets,
            "age_resets": self.age_resets,
            "timeout_resets": self.timeout_resets,
            "empty_resets": self.empty_resets,
            "quota_hits": self.quota_hits,
            "resolved_model": self.resolved_model,
            "api_turns_total": self.api_turns_total,
            "tool_calls_total": self.tool_calls_total,
            "cost_usd_total": round(self.cost_usd_total, 4),
            **{f"{k}_total": v for k, v in self.usage_totals.items()},
        }

    @staticmethod
    def extract_plan(message: str) -> str:
        """Pull the [PLAN] block the prompt asks for; fall back to the last lines."""
        return ClaudeTurn.split_briefing(message)[1]

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        """(briefing, plan), split exactly as CodexTurn does so the two arms'
        transcripts read the same."""
        text = (message or "").strip()
        match = re.search(r"\[PLAN\]\s*(.+)", text, re.DOTALL)
        if match:
            return text[: match.start()].strip(), match.group(1).strip()
        return "", text[-400:]
