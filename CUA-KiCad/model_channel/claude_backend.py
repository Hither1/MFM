"""Drive one KiCad turn through the Claude Code CLI -- `CodexTurn`'s contract on `claude -p`.

Copied from the Minecraft harness (`MCU/mcu_worldmodel/claude_backend.py`), itself
written after the design of PRO-LONG's Claude Code agent. A copy rather than an import:
an arm must not move when the other benchmark retunes its backend. The measurements
quoted below were made there, on claude 2.1.233-2.1.257.

What this copy changes for the KiCad arm:

  * The KiCad `run` contract: `run(prompt, images, *, expect_artifact=True, timeout=None)`
    returning `{"artifact", "actions_json", "message", "ok", "error", "overflow"}`, with an
    `artifact_name` (the design turn writes none).
  * `audit()` returns the codex audit's keys (`analyzer_turns`, `requests`, `input_tokens`,
    ...) so every consumer of an arm's audit reads either CLI, plus `cli`,
    `resolved_model`, `cost_usd` and `quota_hits`.
  * A per-episode CLAUDE_CONFIG_DIR (`<workspace>.claudehome`), the twin of
    `<workspace>.codexhome`: no episode shares a session store or auto-memory with another.
  * Reads are bounded by `claude_sandbox.sh`, the twin of `codex_sandbox.sh`: only the
    workspace and this episode's config dir are mounted, and the one route out is the
    allowlisting proxy to Anthropic. Claude Code's own sandbox bounds writes and the network
    but not reads, and on KiCad the reference netlists sit on the same filesystem. Under the
    wrapper the native sandbox is off (bwrap does not nest there); unwrapped it is on, with
    this episode's config dir denied to the model.

Differences from CodexTurn worth naming (measured on the Minecraft harness):

  * Frames travel as base64 image blocks on a stream-json stdin message, TEXT FIRST: an image
    block placed before the text block was stored and silently never shown to the model.
  * Sessions are created under our own uuid (`--session-id`) and resumed with `--resume`.
  * Auto-compaction and auto-memory are forced off: an overflow is a cold start onto the
    filesystem memory, as on codex.
  * The tool surface is an allowlist (`--tools`): Bash/Read/Write/Edit, the capability set of
    codex's exec_command/view_image/apply_patch. The init event echoes it and a mismatch
    raises. The direct arm runs with no tools at all.
  * The image tool is `Read`, not `view_image`; harness-written text is renamed on its way
    to this channel.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger("model_channel.claude")

ALLOWED_TOOLS: tuple[str, ...] = ("Bash", "Read", "Write", "Edit")

_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})

#: Environment names that look like credentials are not handed to the CLI. The one
#: credential this channel signs with is kept.
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSW|CREDENTIAL", re.I)
ENV_KEEP = frozenset({"CLAUDE_CODE_OAUTH_TOKEN"})

#: Stderr wording the CLI prints when its native sandbox degrades to running commands bare.
_SANDBOX_DEGRADED = re.compile(r"Sandbox disabled|WITHOUT sandboxing|Sandbox is required but failed")

#: Subscription quota exhaustion ("You've reached your usage limit ... resets ...").
_QUOTA_RE = re.compile(r"usage limit|out of (?:extra )?usage", re.I)

#: The CLI has no working credential. Every later turn fails the same way, so the run stops
#: instead of spending the remaining steps and tasks as no-ops (the "Not logged in" smokes).
_AUTH_RE = re.compile(r"Not logged in|Please run /login|OAuth (?:access )?token (?:has )?expired|"
                      r"authentication_error|Invalid (?:API key|bearer token)|"
                      r"OAuth (?:access )?token has been revoked", re.I)

#: Exit status of a run stopped for lost authentication (EX_TEMPFAIL).
AUTH_EXIT_STATUS = 75

_IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif"}

IMAGE_TOOL = "Read"
_VIEW_IMAGE_RE = re.compile(r"\bview_image\b")

WRAPPER_NAME = "claude_sandbox.sh"


def rename_image_tool(text: str) -> str:
    """Codex's `view_image` -> this channel's `Read`, wherever the harness names it."""
    return _VIEW_IMAGE_RE.sub(IMAGE_TOOL, text)


def effort_for(effort: str) -> str:
    """Clamp a codex effort onto the CLI's --effort vocabulary ("minimal"/"none" -> low)."""
    return effort if effort in _EFFORTS else "low"


def is_overflow(text: str) -> bool:
    """The codex classifier's wording: a full context window, not any other error."""
    lmsg = (text or "").lower()
    return ("too long" in lmsg
            or ("context" in lmsg and ("length" in lmsg or "limit" in lmsg or "window" in lmsg))
            or ("maximum" in lmsg and "tokens" in lmsg))


class SandboxViolation(RuntimeError):
    """A turn reached a capability the arm is defined not to have. Raised, not recorded:
    the result sits in the resumed conversation and the workspace."""


def default_claude_bin() -> str:
    """$CLAUDE_BIN, else `claude` on PATH, else the npm-prefix install."""
    for cand in (os.environ.get("CLAUDE_BIN"), shutil.which("claude"),
                 os.path.expanduser("~/.local/share/claude-code-npm/bin/claude")):
        if cand and os.access(cand, os.X_OK):
            return cand
    raise RuntimeError("no runnable claude binary: set CLAUDE_BIN, or install "
                       "@anthropic-ai/claude-code")


def scrubbed_env() -> dict[str, str]:
    """The runner's environment minus the CLI's own session namespace and any credential
    the CLI does not sign with. This runner is routinely launched from inside a claude
    session (CLAUDECODE, CLAUDE_CONFIG_DIR, CLAUDE_CODE_SESSION_ID, ...); any of those
    leaking into the child would tag it as a nested session of the launching account."""
    drop_exact = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CLAUDE_PID", "CLAUDE_EFFORT",
                  "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"}
    env = {k: v for k, v in os.environ.items()
           if k in ENV_KEEP or not (k in drop_exact or k.startswith("CLAUDE_CODE_"))}
    return {k: v for k, v in env.items() if k in ENV_KEEP or not SECRET_NAME.search(k)}


def run_claude(args: Sequence[str], *, cwd: Path | str, stdin_payload: str,
               env: dict[str, str] | None, timeout: float) -> subprocess.CompletedProcess:
    """`subprocess.run` that kills the whole process group on timeout (the child may be the
    sandbox wrapper, and killing only it would orphan the process talking to the model)."""
    proc = subprocess.Popen(list(args), cwd=cwd, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
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


class ClaudeTurn:
    """One resumable Claude Code conversation driving a workspace that outlives it, behind
    `CodexTurn`'s surface: `run`, `write_system_prompt`, `audit`, `calls`, `session_id`,
    `_discard_session`, `split_briefing`, `extract_plan`.

    A score obtained here is "model via the Claude Code harness", as a codex arm's is "model
    via codex": the CLI's own scaffold and tool idioms ride along. Compare within one CLI.
    """

    cli = "claude"

    def __init__(self, workspace: Path, *, model: str, artifact_name: str = "actions.json",
                 reasoning_effort: str = "low", base_url: str | None = None,
                 claude_bin: str | None = None, config_dir: Path | None = None,
                 timeout: int = int(os.environ.get("CLAUDE_TIMEOUT", 1800)),
                 transcript_dir: Path | None = None, tools: Sequence[str] | None = None,
                 session_max_turns: int | None = None,
                 native_sandbox: bool | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.model = model
        self.artifact_name = artifact_name
        if reasoning_effort not in _EFFORTS:
            logger.info("[claude] effort %r is not in the CLI's vocabulary; sending 'low'",
                        reasoning_effort)
        self.reasoning_effort = effort_for(reasoning_effort)
        # An Anthropic-compatible endpoint; reaches the CLI as ANTHROPIC_BASE_URL.
        self.base_url = base_url
        self.claude_bin = claude_bin or default_claude_bin()
        self.wrapped = Path(self.claude_bin).name == WRAPPER_NAME
        # Per episode, beside the workspace, never the account's own ~/.claude.
        self.config_dir = (Path(config_dir) if config_dir
                           else self.workspace.with_name(self.workspace.name + ".claudehome")).resolve()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config_dir, 0o700)
        self.timeout = timeout
        self.tools = list(ALLOWED_TOOLS) if tools is None else list(tools)
        self.expected_tools = frozenset(self.tools)
        if native_sandbox is None:
            env = os.environ.get("CLAUDE_NATIVE_SANDBOX")
            native_sandbox = (env != "0") if env is not None else (bool(self.tools) and not self.wrapped)
        self.native_sandbox = native_sandbox
        self.autocompact = os.environ.get("CLAUDE_AUTOCOMPACT", "").strip()
        self.api_key_helper = os.environ.get("CLAUDE_API_KEY_HELPER", "").strip()
        self.deny_read = [str(self.config_dir)] + [
            p for p in os.environ.get("CLAUDE_SANDBOX_DENY_READ", "").split(os.pathsep) if p]
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        if self.transcript_dir:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)
        if not self.wrapped:
            self._seed_auth()

        self.session_id: str | None = None
        self.session_ids: list[str] = []
        self.resolved_model: str | None = None
        self.calls = 0
        self.max_calls = int(os.environ.get("CLAUDE_MAX_CALLS", "0") or 0)
        self.ceiling_hits = 0
        self.images_attached = 0
        self.session_attachment_bytes = 0
        self.peak_attachment_bytes = 0
        self.view_image_calls = 0
        self.tool_errors = 0
        self.overflow_resets = 0
        self.timeout_resets = 0
        self.empty_resets = 0
        self.session_resets = 0
        self.session_max_turns = (int(session_max_turns) if session_max_turns is not None
                                  else int(os.environ.get("CLAUDE_SESSION_MAX_TURNS", "0")))
        self.session_turns = 0
        self.age_resets = 0
        self.compactions = 0
        self.quota_hits = 0
        self.quota_wait_s = 0.0
        self.results = 0
        self.agent_messages = 0
        self.usage_totals = {"input_tokens": 0, "output_tokens": 0,
                             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.cost_usd_total = 0.0
        self.api_turns_total = 0
        self.tool_calls_total = 0

    # -- auth / session lifecycle ------------------------------------------------------

    def _seed_auth(self) -> None:
        """Unwrapped only (the wrapper binds the credential itself). A long-lived
        `claude setup-token` token in CLAUDE_CODE_OAUTH_TOKEN needs no file. Otherwise the
        eval account's .credentials.json is linked in -- linked, never copied: the CLI
        refreshes the file in place, and a copy forks the refresh chain."""
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return
        target = self.config_dir / ".credentials.json"
        if target.exists() or target.is_symlink():
            return
        auth = Path(os.environ.get("CLAUDE_EVAL_AUTH")
                    or os.path.expanduser("~/.claude-eval/.credentials.json"))
        if auth.exists():
            target.symlink_to(auth.resolve())

    def _discard_session(self, why: str, counter: str) -> None:
        logger.warning("[claude] turn %d: discarding session %s (%s); the next call "
                       "cold-starts", self.calls, self.session_id, why)
        self.session_id = None
        self.session_turns = 0
        self.session_attachment_bytes = 0
        self.session_resets += 1
        setattr(self, counter, getattr(self, counter) + 1)

    def write_system_prompt(self, text: str) -> None:
        """CLAUDE.md is to claude what AGENTS.md is to codex: the project file discovered
        from the cwd and injected every turn (requires `--setting-sources project`).
        Written once, with the image tool renamed."""
        claude_md = self.workspace / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(rename_image_tool(text), encoding="utf-8")

    # -- argv / stdin ------------------------------------------------------------------

    def _settings(self) -> str:
        settings: dict[str, Any] = {
            "autoCompactEnabled": bool(self.autocompact),
            "autoMemoryEnabled": False,
            "permissions": {"deny": [f"Read({p.rstrip('/')}/**)" for p in self.deny_read]},
        }
        if self.api_key_helper:
            settings["apiKeyHelper"] = self.api_key_helper
        if self.native_sandbox:
            settings["sandbox"] = {
                "enabled": True, "failIfUnavailable": True, "autoAllowBashIfSandboxed": True,
                "network": {"allowedDomains": [], "allowUnixSockets": [],
                            "allowLocalBinding": False},
                "filesystem": {"denyRead": list(self.deny_read),
                               "allowWrite": [str(self.workspace)]},
            }
        return json.dumps(settings)

    def _args(self) -> list[str]:
        args = [self.claude_bin, "-p", "--model", self.model,
                "--effort", self.reasoning_effort,
                "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--setting-sources", "project", "--strict-mcp-config",
                "--disable-slash-commands", "--settings", self._settings(),
                "--tools", ",".join(self.tools),
                "--permission-mode", "bypassPermissions"]
        if self.autocompact:
            args += ["--autocompact", self.autocompact]
        if self.session_id:
            args += ["--resume", self.session_id]
        else:
            self.session_id = str(uuid.uuid4())
            self.session_turns = 0
            args += ["--session-id", self.session_id]
        return args

    @staticmethod
    def _build_stdin(prompt: str, images: Sequence[Path]) -> str:
        """One stream-json user message: the text block first, then the image blocks.
        Do not reorder (an image-first message was stored and never shown to the model)."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in images:
            media = _IMAGE_MEDIA.get(path.suffix.lower())
            if media is None:
                raise ValueError(f"unsupported attachment type: {path}")
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": media,
                "data": base64.b64encode(path.read_bytes()).decode()}})
        return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"

    @staticmethod
    def _result(artifact: str | None, message: str, *, ok: bool, error: str | None,
                overflow: bool) -> dict[str, Any]:
        return {"artifact": artifact, "actions_json": artifact, "message": message,
                "ok": ok, "error": error, "overflow": overflow}

    # -- the turn ----------------------------------------------------------------------

    def run(self, prompt: str, images: Sequence[Path] = (), *, expect_artifact: bool = True,
            timeout: float | None = None) -> dict[str, Any]:
        """Execute one turn. `expect_artifact=False` is a turn whose output is filesystem
        writes and a closing message (the design turn): "ok" then means the message."""
        waited = 0.0
        while True:
            result = self._run_once(prompt, images, expect_artifact=expect_artifact,
                                    timeout=timeout)
            error = result.get("error") or ""
            if error and _AUTH_RE.search(error):
                self._auth_lost(error)
            if not (error and _QUOTA_RE.search(error)):
                return result
            # A usage limit resets on a clock; the step is not the model's to lose. Wait
            # and send the same turn again, up to CLAUDE_QUOTA_WAIT_MAX seconds per turn.
            pause = float(os.environ.get("CLAUDE_QUOTA_WAIT", "600"))
            budget = float(os.environ.get("CLAUDE_QUOTA_WAIT_MAX", str(24 * 3600)))
            if waited + pause > budget:
                logger.error("[claude] usage limit still in force after %.0fs; giving the "
                             "turn up", waited)
                return result
            logger.warning("[claude] usage limit (%s); waiting %.0fs and re-sending turn %d",
                           error[:120], pause, self.calls)
            self.calls -= 1
            time.sleep(pause)
            waited += pause
            self.quota_wait_s += pause

    def _auth_lost(self, error: str) -> None:
        """Stop the whole run. Raising would only fail this task and start the next, which
        fails the same way; and a carry arm would record those failures as outcomes. The
        unfinished task writes no row, so `run_eval.py` re-runs it on resume."""
        logger.critical("[claude] turn %d: no working credential (%s). Stopping the run "
                        "(exit %d); renew CLAUDE_CODE_OAUTH_TOKEN and re-run the same "
                        "command to resume.", self.calls, error[:200], AUTH_EXIT_STATUS)
        if os.environ.get("CLAUDE_AUTH_FATAL", "1") == "0":
            raise RuntimeError(f"claude: not authenticated: {error[:200]}")
        logging.shutdown()
        os._exit(AUTH_EXIT_STATUS)

    def _run_once(self, prompt: str, images: Sequence[Path], *, expect_artifact: bool,
                  timeout: float | None) -> dict[str, Any]:
        if self.max_calls and self.calls >= self.max_calls:
            self.ceiling_hits += 1
            return self._result(None, "", ok=False, error=f"call ceiling {self.max_calls} reached",
                                overflow=False)
        self.calls += 1
        ceiling = self.timeout if timeout is None else timeout
        if self.session_id and self.session_max_turns and self.session_turns >= self.session_max_turns:
            self._discard_session(f"reached {self.session_turns} turns, cap "
                                  f"{self.session_max_turns}", "age_resets")
        for stale in {self.artifact_name, "actions.json", "last_message.txt"}:
            (self.workspace / stale).unlink(missing_ok=True)

        env = scrubbed_env()
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        env["DISABLE_AUTOUPDATER"] = "1"
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        env["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"] = "1"
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        env["CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING"] = "1"
        if self.base_url:
            env["ANTHROPIC_BASE_URL"] = self.base_url
        env["MFM_IMAGE_TOOL"] = IMAGE_TOOL
        prompt = rename_image_tool(prompt)

        images = [Path(p) for p in images]
        relative = [p for p in images if not p.is_absolute()]
        if relative:
            raise ValueError(f"attachments must be absolute paths: {relative}")
        missing = [p for p in images if not p.exists()]
        if missing:
            logger.error("[claude] turn %d: %d attachment(s) do not exist and will not be "
                         "sent: %s", self.calls, len(missing), missing)
        images = [p for p in images if p.exists()]
        resuming = self.session_id is not None
        args = self._args()
        if self.session_id not in self.session_ids:
            self.session_ids.append(self.session_id)
        stdin_payload = self._build_stdin(prompt, images)
        self.images_attached += len(images)
        self.session_attachment_bytes += sum(p.stat().st_size for p in images) * 4 // 3
        self.peak_attachment_bytes = max(self.peak_attachment_bytes, self.session_attachment_bytes)
        logger.info("[claude] turn %d model=%s resume=%s images=%d", self.calls, self.model,
                    "yes" if resuming else "no", len(images))
        try:
            proc = run_claude(args, cwd=self.workspace, stdin_payload=stdin_payload, env=env,
                              timeout=ceiling)
        except subprocess.TimeoutExpired as expired:
            partial = expired.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            if self.transcript_dir:
                stem = f"turn_{self.calls:04d}.timeout"
                (self.transcript_dir / f"{stem}.events.jsonl").write_text(partial, encoding="utf-8")
                (self.transcript_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
            logger.error("[claude] turn %d timed out after %ss", self.calls, ceiling)
            self._discard_session(f"timed out after {ceiling}s", "timeout_resets")
            return self._result(None, "", ok=False, error="timeout", overflow=False)

        parsed = self._parse_events(proc.stdout)
        if self.transcript_dir:
            stem = self.transcript_dir / f"turn_{self.calls:04d}"
            stem.with_suffix(".events.jsonl").write_text(proc.stdout, encoding="utf-8")
            stem.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
            if proc.stderr:
                stem.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")

        degraded = self.native_sandbox and proc.stderr and _SANDBOX_DEGRADED.search(proc.stderr)
        if degraded:
            raise SandboxViolation(
                f"claude turn {self.calls}: the CLI dropped its native sandbox "
                f"({degraded.group(0)!r}); this turn's commands ran unconfined. Install "
                f"socat/bwrap, or run under {WRAPPER_NAME}.")
        if parsed["violations"]:
            raise SandboxViolation(
                f"claude turn {self.calls} used capabilities this arm must not have: "
                f"{parsed['violations']} (requested {sorted(self.expected_tools) or 'no tools'}); "
                f"transcript under {self.transcript_dir}")

        if parsed["saw_result"]:
            self.session_turns += 1
            self.results += 1
        elif not resuming:
            self.session_id = None

        error = parsed["error"]
        if not parsed["saw_result"] and not error and proc.returncode:
            error = f"claude exited rc={proc.returncode}: {(proc.stderr or '').strip()[-300:]}"
        overflowed = bool(error) and is_overflow(error)
        if error and _QUOTA_RE.search(error):
            self.quota_hits += 1
            logger.error("[claude] turn %d hit the account usage limit: %s", self.calls,
                         error[:200])
        if overflowed and self.session_id:
            self._discard_session("overflowed the context window", "overflow_resets")

        artifact_path = self.workspace / self.artifact_name
        artifact = artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else None
        message = parsed["message"]
        if error:
            logger.warning("[claude] turn %d reported: %s", self.calls, error[:200])
        if artifact is None and expect_artifact:
            logger.warning("[claude] turn %d wrote no %s (rc=%s)", self.calls,
                           self.artifact_name, proc.returncode)
        if artifact is None and not message and self.session_id:
            self._discard_session("produced no output at all", "empty_resets")
        return self._result(artifact, message,
                            ok=(artifact is not None) if expect_artifact else bool(message),
                            error=error, overflow=overflowed)

    # -- events ------------------------------------------------------------------------

    def _parse_events(self, events: str) -> dict[str, Any]:
        """Fold one invocation's stream-json events: `system/init` (session, model, tools
        in force), `system/compact_boundary`, `assistant` (text / tool_use), `user`
        (tool_result), and the closing `result` (usage, cost, num_turns, final text)."""
        message = ""
        error: str | None = None
        saw_result = False
        violations: dict[str, Any] = {}
        for line in (events or "").splitlines():
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
                        logger.warning("[claude] session drift: asked %s, got %s",
                                       self.session_id, event["session_id"])
                        self.session_id = event["session_id"]
                    self.resolved_model = event.get("model") or self.resolved_model
                    tools = set(event.get("tools") or [])
                    if tools != self.expected_tools:
                        violations["tool_surface"] = sorted(tools ^ self.expected_tools)
                    for surface in ("mcp_servers", "skills", "slash_commands", "plugins"):
                        if event.get(surface):
                            violations[surface] = event[surface]
                elif sub == "compact_boundary":
                    self.compactions += 1
                    if not self.autocompact:
                        logger.error("[claude] turn %d shows a compaction event; the "
                                     "conversation is not the one this arm runs", self.calls)
            elif kind == "assistant":
                for block in (event.get("message") or {}).get("content") or []:
                    btype = block.get("type")
                    if btype == "text":
                        message += block.get("text") or ""
                        self.agent_messages += 1
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
            elif kind == "result":
                saw_result = True
                usage = event.get("usage") or {}
                for key in self.usage_totals:
                    self.usage_totals[key] += int(usage.get(key) or 0)
                served = usage.get("server_tool_use") or {}
                if any(int(served.get(k) or 0) for k in ("web_search_requests", "web_fetch_requests")):
                    violations["server_tool_use"] = served
                cost = event.get("total_cost_usd")
                if isinstance(cost, (int, float)):
                    self.cost_usd_total += cost
                self.api_turns_total += int(event.get("num_turns") or 0)
                if event.get("is_error"):
                    error = str(event.get("result") or event.get("subtype") or "error")
                else:
                    message = str(event.get("result") or message)
        return {"message": message.strip(), "error": error, "saw_result": saw_result,
                "violations": violations}

    # -- audit -------------------------------------------------------------------------

    def audit(self) -> dict[str, Any]:
        """The codex audit's keys, read off this CLI's event stream, plus what only this
        CLI reports. Token counts follow codex's convention: `input_tokens` is every input
        token (fresh + cache reads + cache writes), `cached_input_tokens` the cache reads."""
        u = self.usage_totals
        return {
            "cli": "claude",
            "analyzer_turns": self.calls,
            "images_attached": self.images_attached,
            "view_image_calls": self.view_image_calls,
            "image_attach_failures": 0,
            "vision_audit_source": "events",
            "overflow_resets": self.overflow_resets,
            "session_resets": self.session_resets,
            "timeout_resets": self.timeout_resets,
            "timeouts_salvaged": 0,
            "empty_resets": self.empty_resets,
            "age_resets": self.age_resets,
            "session_max_turns": self.session_max_turns,
            "sessions": len(self.session_ids),
            "peak_attachment_bytes": self.peak_attachment_bytes,
            "auto_compact_token_limit": int(self.autocompact) if self.autocompact else None,
            "compactions": self.compactions,
            "compactions_from_rollout": 0,
            "turns": self.results,
            "requests": self.api_turns_total,
            "tool_calls": self.tool_calls_total,
            "agent_messages": self.agent_messages,
            "input_tokens": (u["input_tokens"] + u["cache_read_input_tokens"]
                             + u["cache_creation_input_tokens"]),
            "cached_input_tokens": u["cache_read_input_tokens"],
            "cache_creation_input_tokens": u["cache_creation_input_tokens"],
            "output_tokens": u["output_tokens"],
            "threads": len(self.session_ids),
            "web_searches": 0,
            "mcp_tool_calls": 0,
            "subthreads": 0,
            "tool_errors": self.tool_errors,
            "quota_hits": self.quota_hits,
            "quota_wait_s": round(self.quota_wait_s),
            "call_ceiling_hits": self.ceiling_hits,
            "resolved_model": self.resolved_model,
            "cost_usd": round(self.cost_usd_total, 4),
            "sandbox": WRAPPER_NAME if self.wrapped else ("native" if self.native_sandbox else "none"),
        }

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        """(briefing, plan), split exactly as CodexTurn does."""
        text = (message or "").strip()
        match = re.search(r"\[PLAN\]\s*(.+)", text, re.DOTALL)
        if match:
            return text[: match.start()].strip(), match.group(1).strip()
        return "", text[-400:]

    @staticmethod
    def extract_plan(message: str) -> str:
        return ClaudeTurn.split_briefing(message)[1]
