"""Drive one turn through the Codex CLI.

One turn is one `codex exec` (or `codex exec resume`) in the workspace: the prompt and
the current frame go in, `actions.json` and the last message come out. The inline notes
record measurements taken while the channel was built; treat them as provenance.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loguru import logger

_SESSION_RE = re.compile(r'"(?:thread_id|session_id)"\s*:\s*"([0-9a-fA-F-]{36})"')
# Compaction announces itself in a type-ish field, never in prose, so this cannot be
# tripped by a model that happens to write the word. See `_metadata_args` for why a
# single hit matters.
_COMPACTION_RE = re.compile(r'"(?:type|kind|action_trigger)"\s*:\s*"[^"]*compact', re.I)

# The account behind the credential has no usage left. Codex reports it as an ordinary
# turn error carrying the reset time ("You've hit your usage limit ... try again at
# Sep 7th, 2026 10:25 AM"), so nothing else in this backend can tell it apart from a
# transient failure: four arms each spent every turn spawning a codex,
# waiting ~10 s for the same refusal and retrying, and would have run their whole
# 12,000-step episode that way. A cap that resets days from now cannot clear inside an
# episode, so after a short streak the calls stop; one probe every RETRY_AFTER refusals
# still catches the shorter rolling window resetting mid-run.
_QUOTA_RE = re.compile(r"hit your usage limit|usage limit reached|purchase more credits", re.I)
QUOTA_STREAK_STOP = 5
QUOTA_RETRY_AFTER = 40

# What codex should believe about a locally served model. Codex has no catalog entry
# for it -- every turn logs `Model metadata for <name> not found. Defaulting to
# fallback metadata` -- so without this its context accounting is a guess.
#
# Two things this is NOT. It does not silence that warning: the warning is emitted by
# the catalog lookup on the model *name*, and it still appears verbatim with
# `-c model_context_window=131072` set (measured against a no-config baseline and
# against `-m gpt-5.6-sol`, which is in the catalog and warns not at all). Silencing it
# needs `model_catalog_json`, whose schema is an undocumented nested struct that would
# break every run on a codex upgrade -- not worth buying a quieter log with. And it is
# not applied to hosted models, where codex's own metadata is right and ours would be
# a guess overriding a fact.
DEFAULT_CONTEXT_WINDOW = int(os.environ.get("CODEX_MODEL_CONTEXT_WINDOW", 131072))

# What happens when a resumed conversation fills up. Codex ships auto-compaction, so
# there are two outcomes and only one of them was ever described: compact the thread and
# carry on, or overflow and cold-start onto the filesystem memory. Left unset the choice
# belongs to whatever codex defaults to, which is neither measured nor guaranteed equal
# across arms -- and under `CODEX_SESSION_MAX_TURNS=1` it never came up at all, because
# no conversation lived long enough to fill.
#
# Set it explicitly on both arms of any comparison. A limit above the real window can
# never be reached, so compaction never fires and every full session cold-starts; a
# limit below it fires first and the thread survives, summarised. `vision_audit` reports
# the value alongside the `compactions` and `overflow_resets` counts, so which branch an
# episode actually took is in the record rather than inferred.
AUTO_COMPACT_TOKEN_LIMIT = os.environ.get("CODEX_AUTO_COMPACT_TOKEN_LIMIT", "").strip()


def effort_for(base_url: str | None, effort: str) -> str:
    """The reasoning effort to send, which on a local server is the thinking switch.

    `--default-chat-template-kwargs '{"enable_thinking": false}'` does not reach the
    codex arms. vLLM synthesises `enable_thinking = (effort != "none")` from a Responses
    request's `reasoning.effort` and merges it as `defaults | request`
    (`responses/protocol.py:329-330`, `renderers/params.py:99-115`), so the request wins
    and the server's pin is overridden by every codex turn.

    Measured, not inferred. Codex puts `reasoning: {"effort": ..., "summary": "auto"}` on
    the wire verbatim and sends no `chat_template_kwargs` of its own, so effort is the
    only lever it has. Rendering Qwen3.8's pinned template shows what each value buys:
    with thinking enabled the generation prompt ends with a bare `<think>` and the system
    message gains "Reasoning effort is set to <effort>"; with `none` it ends with an
    already-closed `<think></think>` and no effort instruction -- byte-identical to what
    the server pin produces for the direct-vLLM arm, which is the alignment dz asked for.

    This also names what the finished Qwen3.8 runs were really doing: thinking was ON for
    all of them. The absence of `<think>` in their output is because the tag sits in the
    prompt, and the "free-form deliberation before the JSON" was the thinking channel
    without a label.

    Hosted models keep the caller's effort: there the field means what codex means by it,
    and nothing downstream reinterprets it as a template switch.

    **The invariant this function exists to hold: the codex arms and the direct-vLLM arm
    must agree about thinking.** They are configured from opposite ends -- the server's
    `--default-chat-template-kwargs` governs the direct arm, this value governs the codex
    arms -- so nothing but care keeps them together, and a matrix whose channel control
    differs in thinking cannot separate the agent axis from the channel axis.

    So a local server gets the caller's effort through, and thinking is on for both by
    default. Turning it off is one variable changed on two sides: `CODEX_LOCAL_EFFORT=none`
    here and the chat-template arguments of the server. Setting one without the other is
    the bug this note is about.

    Both settings are worth having because the choice has a measured cost. With thinking
    off the default arm looped on `echo ok` 85 times inside one call and burned the client
    timeout -- 6 of 13 calls returned nothing on the 0313 diagnostic -- where the same arm
    with thinking on never exceeded 3 tool calls across 46, and PRO-LONG was unaffected
    either way. That measurement changed thinking and the sampling recipe together, so it
    does not yet say which is responsible; separating them needs both switches reachable
    from a run's environment rather than from an edit.
    """
    if not base_url:
        return effort
    return os.environ.get("CODEX_LOCAL_EFFORT", effort)


def provider_auth_args() -> list[str]:
    """How codex authenticates against the --base-url provider.

    Default: the LOCAL_API_KEY environment variable (`env_key`), "EMPTY" for a local
    server. A hosted provider's key must NOT travel that way: the model's exec cells
    inherit codex's environment (see scrub_env), so an `env_key` credential is readable
    by the model. CODEX_LOCAL_AUTH_COMMAND, a JSON list, names a command codex runs to
    obtain the key instead (OpenRouter's documented `auth.command` form) -- e.g.
    ["sed", "-n", "s/^OPENROUTER_API_KEY=//p", "/abs/path/openrouter.env"] reads a 600
    file, and the key exists only inside codex's HTTP client. Measured: the
    turn ran, and `${OPENROUTER_API_KEY:+set}` printed nothing inside an exec cell.
    """
    raw = os.environ.get("CODEX_LOCAL_AUTH_COMMAND", "").strip()
    if not raw:
        return ["-c", 'model_providers.local.env_key="LOCAL_API_KEY"']
    cmd = json.loads(raw)
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise ValueError("CODEX_LOCAL_AUTH_COMMAND must be a JSON list of strings")
    return [
        "-c", f"model_providers.local.auth.command={json.dumps(cmd[0])}",
        "-c", f"model_providers.local.auth.args={json.dumps(cmd[1:])}",
    ]


def _metadata_args(context_window: int) -> list[str]:
    """Codex config for a model codex has never heard of.

    `model_auto_compact_token_limit` is the load-bearing one. The vendored binary
    carries auto-compaction and its fallback prompts, and telling codex the real
    context window is exactly what would let it start compacting a long resumed
    conversation as it fills. That would quietly replace the log as the memory:
    PRO-LONG's stance, which our overflow handler mirrors, is that codex has no
    compaction and an overflowed session must cold-start, which is what keeps logs.txt
    the memory of record. Set the trigger above the window so the server's own context
    limit -- and the cold start that follows it -- always arrives first.

    The direction of that comparison is inferred, not documented, so it is not trusted
    on its own: `CodexTurn` counts compaction events in the transcripts and reports
    them in the vision audit, and a nonzero count means this argument is wrong and the
    arm needs re-describing rather than quietly re-running.
    """
    return [
        "-c", f"model_context_window={context_window}",
        "-c", f"model_auto_compact_token_limit="
              f"{AUTO_COMPACT_TOKEN_LIMIT or context_window * 8}",
    ]


# What the model is allowed to hold in its hands, fixed here rather than left to codex's
# defaults. Measured on codex-cli 0.147.0 on a sibling port,
# same subscription account: without these the tool list carried `web__run` -- and the
# model used it to fetch a Wikipedia article -- plus ~250 account-level
# `mcp__codex_apps__*` connectors (github, gmail, slack, google_drive, hugging_face, ...)
# and the sub-agent tools (`spawn_agent`, ...). All of them run server-side or in the
# codex process itself, so no local sandbox is on their path; only config is.
#
# This matters more here than the filesystem does: a connector that can fetch a repo --
# or a web search against a public benchmark -- is a way to a task's answers that never
# touches the local filesystem.
#
#   web_search          default "cached": OpenAI's web index.
#   features.apps       account connectors; the docs say their "traffic [is] not
#                       controlled by sandboxed-command network proxy".
#   agents.enabled      the sub-agent tools. `--disable multi_agent` does NOT remove
#                       them (measured); this key does. Off so one analyzer turn is one
#                       thread and `request_stats` means what it says.
#   plugins/remote      the plugin catalog and its `request_plugin_install` tool.
#   image/goals         server-side image generation and goal state; off so the nested
#                       tool list is exactly EXPECTED_NESTED_TOOLS and a new default
#                       cannot slip in unnoticed.
# Files a turn produces, cleared before each turn so a stale one from the previous turn
# is never mistaken for this turn's output.
TURN_ARTEFACTS: tuple[str, ...] = ("actions.json", "last_message.txt")

SAFE_CODEX_FLAGS: tuple[str, ...] = (
    "-c", 'web_search="disabled"',
    "-c", "features.apps=false",
    "-c", "apps._default.enabled=false",
    "-c", "agents.enabled=false",
    "-c", "features.remote_plugin=false",
    "-c", "features.plugins=false",
    "-c", "features.image_generation=false",
    "-c", "features.goals=false",
    # No shell snapshot. codex 0.153 otherwise writes `$CODEX_HOME/shell_snapshots/
    # <thread>.sh` at thread start -- `declare -x` of every variable in its environment --
    # and deletes it only on a clean exit, so an arm stopped mid-turn leaves the file
    # (21 of 54 homes). With HOME at the arm's own home there is no profile
    # for the snapshot to capture, so nothing the model's commands see changes.
    "-c", "features.shell_snapshot=false",
)

# Variables that never reach codex. The model's exec cells inherit codex's whole
# environment (measured on codex 0.153: `${GITHUB_PERSONAL_ACCESS_TOKEN:+set}`
# printed `set` inside a turn, and `shell_environment_policy.exclude` changed nothing), so
# any credential exported by the launching shell was readable by the model and could have
# been written into the workspace, which is carried across lives and staged. Dropped by
# name: anything that looks like a secret, except what codex itself is configured to read
# (LOCAL_API_KEY on the --base-url path) and its own CODEX_* settings. The names dropped
# are logged once per CodexTurn so a run's log shows what its shell carried.
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.IGNORECASE)
ENV_KEEP: frozenset[str] = frozenset({"LOCAL_API_KEY"})


def scrub_env(env: dict[str, str],
              keep: frozenset[str] = ENV_KEEP) -> tuple[dict[str, str], list[str]]:
    """The environment the CLI gets, and the names removed from it. `keep` names the
    secrets the CLI itself reads."""
    dropped = sorted(
        k for k in env
        if SECRET_NAME.search(k) and k not in keep and not k.startswith("CODEX_")
    )
    return {k: v for k, v in env.items() if k not in set(dropped)}, dropped

EXPECTED_NESTED_TOOLS: frozenset[str] = frozenset({
    "apply_patch", "exec_command", "update_plan", "view_image", "write_stdin",
})


class SandboxViolation(RuntimeError):
    """A turn reached a capability the arm is defined not to have.

    Raised, not recorded: a web search or a connector call means the configuration in
    force is not the one the results claim, and the episode that follows it is
    contaminated -- the result sits in the resumed conversation and in whatever the
    agent wrote into its workspace.
    """


# A tool result is what makes codex send the model another request, so these are what
# turn one call into several. Named rather than inferred, so an unfamiliar item type is
# undercounted visibly instead of inflating the count silently.
_TOOL_ITEM_TYPES = frozenset({
    "command_execution", "view_image", "file_change", "patch_apply",
    "mcp_tool_call", "web_search", "todo_list",
})


def request_stats(events: str) -> dict[str, int]:
    """What one arm's calls actually cost, read off the saved event stream.

    "One call per step" is the wrong unit for the codex arms. A single turn runs an
    agentic loop: the model answers, calls a tool, and is asked again with the result
    appended -- one measured turn was three requests (two bash calls plus the
    closing message) re-paying a ~46k-token prompt each time. Comparing
    per-call cost across arms without this counts a codex turn as one request and
    understates it by however many tools the model reached for.

    The alternative -- stripping codex's tools so a step is one request -- would redefine
    the arm mid-study, so this measures the harness that is actually being run.

    requests = one per tool result plus the one that closes each turn. Token totals come
    from codex's own `turn.completed` usage, so they are its accounting, not our estimate
    -- but that usage is CUMULATIVE over the thread: across one episode it reads
    40k, 88k, 147k, 243k for turns 1-4 of the same resumed conversation. Adding those up
    is quadratic, and it is not a subtle error: summed naively, one 57-turn run claimed
    659M input tokens. So usage is returned per thread, to be maxed and only then summed
    (`merge_stats`); a session dropped after an overflow starts a new thread and its own
    counter, which is exactly the boundary the totals should respect.
    """
    out: dict[str, Any] = dict(turns=0, requests=0, tool_calls=0, agent_messages=0,
                               usage_by_thread={},
                               # Must all stay 0; see SAFE_CODEX_FLAGS.
                               web_searches=0, mcp_tool_calls=0, subthreads=0)
    thread = ""
    for line in events.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "thread.started":
            new_thread = event.get("thread_id") or ""
            if thread and new_thread and new_thread != thread:
                # A second thread inside one `codex exec` is a spawned sub-agent.
                out["subthreads"] += 1
            thread = new_thread
        elif kind == "item.completed":
            item_type = (event.get("item") or {}).get("type")
            if item_type in _TOOL_ITEM_TYPES:
                out["tool_calls"] += 1
            elif item_type == "agent_message":
                out["agent_messages"] += 1
            if item_type == "web_search":
                out["web_searches"] += 1
            elif item_type == "mcp_tool_call":
                out["mcp_tool_calls"] += 1
        elif kind == "turn.completed":
            out["turns"] += 1
            usage = event.get("usage") or {}
            seen = out["usage_by_thread"].setdefault(
                thread, dict(input_tokens=0, cached_input_tokens=0, output_tokens=0))
            for key in seen:
                seen[key] = max(seen[key], int(usage.get(key) or 0))
    out["requests"] = out["tool_calls"] + out["turns"]
    return out


def merge_stats(parts: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Total up per-call stats without double-counting codex's cumulative usage.

    Counts add; token usage is the per-thread maximum, summed across threads, because
    every turn of a resumed thread reports the whole thread's usage so far.
    """
    total = dict(turns=0, requests=0, tool_calls=0, agent_messages=0,
                 input_tokens=0, cached_input_tokens=0, output_tokens=0, threads=0,
                 web_searches=0, mcp_tool_calls=0, subthreads=0)
    per_thread: dict[str, dict[str, int]] = {}
    for part in parts:
        for key in ("turns", "requests", "tool_calls", "agent_messages",
                    "web_searches", "mcp_tool_calls", "subthreads"):
            total[key] += int(part.get(key) or 0)
        for thread, usage in (part.get("usage_by_thread") or {}).items():
            seen = per_thread.setdefault(
                thread, dict(input_tokens=0, cached_input_tokens=0, output_tokens=0))
            for key in seen:
                seen[key] = max(seen[key], int(usage.get(key) or 0))
    for usage in per_thread.values():
        for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
            total[key] += usage[key]
    total["threads"] = len(per_thread)
    return total


def is_overflow(name: str, text: str) -> bool:
    """Does this Codex error mean the model's context window is full?

    Mirrors upstream's classifier (`codex_agent.py:207-212`). Codex has no native
    compaction, so an overflowed session stays overflowed: every later turn on the
    same session id fails the same way. The only recovery is a cold start, which is
    cheap here because `logs.txt` -- not the conversation -- is the memory.
    """
    lname, lmsg = name.lower(), text.lower()
    return (
        "overflow" in lname
        or "too long" in lmsg
        or ("context" in lmsg and ("length" in lmsg or "limit" in lmsg or "window" in lmsg))
        or ("maximum" in lmsg and "tokens" in lmsg)
    )


# Codex 0.147 runs the model's tools inside a `exec` code-mode cell, and the `--json`
# event stream reports only *shell* commands (`command_execution`). A nested
# `tools.view_image(...)` -- which is how the model looks at a frame -- never appears
# there at all. Measured on a sibling codex port's calibration run: 0 events mentioning
# view_image, while
# the conversation shows 20 calls returning 60 images.
#
# So the vision audit reads the rollout instead. That is the conversation as codex stored
# it, it is per-episode now that each episode has its own CODEX_HOME, and it is the only
# place two things are recorded:
#
#   view_image calls        what the model chose to look at
#   "could not read the     an `-i` attachment that did not land. This is the failure the
#    local image"           audit exists to catch: the run still scores, the counter still
#                           says images_attached=N, and the arm has silently become
#                           vision-on-demand instead of the forced-vision arm it claims.
#   tool errors             a tool call the model got an error back from and recovered
#                           inside its own turn. These never reach the event stream: the
#                           tool returns the failure to the model, it retries, writes
#                           actions.json, and the harness sees a clean turn. Measured on
#                           an arm whose turns wrote several files: 75% of its turns
#                           against 3% of PRO-LONG turns, ~9s each -- two operations
#                           landing on one path reject the whole patch. A per-arm tax of
#                           exactly the kind a comparison otherwise charges to the method.
_ROLLOUT_VIEW_IMAGE = re.compile(r"view_image")
_ROLLOUT_ATTACH_FAIL = re.compile(r"could not read the local image", re.I)
# Broken out by kind, because the aggregate is actively misleading: on one run the two
# `apply_patch verification failed` variants were 4 and 132 occurrences and have nothing
# to do with each other, and counting them together turned a 4-event induction bug into a
# claimed "67% of act turns". Whatever is added here, keep it separated.
#
#   patch_stale_target   the model sends an *update* for a file the harness unlinked at
#                        the start of the turn -- `actions.json` in 132 of 133 cases. It
#                        retries as a create and succeeds, so nothing is lost but ~9 s.
#   patch_dup_target     two operations on one path in one patch; codex rejects the whole
#                        patch. All four on one run were induction turns rewriting
#                        world_model/spatial.md.
#   attach_miss          the model asked to view an image that is not there.
#
# Match the error strings, never the human-readable phrase: `multiple operations target`
# now appears in the induction prompt itself, warning against the thing it names --
# counting it there scored the fix that added the warning as a regression.
_ROLLOUT_TOOL_ERROR = re.compile(r"Script error:")
_ROLLOUT_PATCH_STALE = re.compile(r"apply_patch verification failed: Failed to read")
_ROLLOUT_PATCH_DUP = re.compile(r"apply_patch verification failed: invalid patch: "
                                r"multiple operations target")
_ROLLOUT_ATTACH_MISS = re.compile(r"unable to locate image at")
# The MFM arm's query tool, run from inside a turn: how often the model went to the
# episodes instead of grepping the log. 0 in every other arm.
_ROLLOUT_EPISODES_TOOL = re.compile(r"tools/episodes\.py")

# A call to the MFM query tool, in every shape the CLIs record one in. The path alone is
# not enough: the tool is DESCRIBED in AGENTS.md, which the rollout embeds verbatim as
# the system prompt, so a bare path match counts the instructions rather than a call.
# Requiring a tool-call record on the same line is what separates them, and the shapes
# differ by CLI and by mode: codex 0.149 records shell work as `command_execution` or
# `function_call`, 0.153 runs it inside a code-mode `exec` cell recorded as
# `custom_tool_call`. Counting only the first two read 0 against a KiCad run whose
# 1,410 exec cells were the only place a call could appear, and against an MCU run whose
# saved transcripts show 18 real calls.
_TOOL_CALL_MARKERS = ('"command_execution"', '"function_call"', '"custom_tool_call"',
                      '"local_shell_call"')


def is_tool_call_line(line: str) -> bool:
    return any(m in line for m in _TOOL_CALL_MARKERS)


def count_episodes_tool(path, pattern) -> int:
    """Episode-tool calls in one JSONL file (a rollout or a saved turn transcript)."""
    n = 0
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return 0
    with fh:
        for line in fh:
            if is_tool_call_line(line):
                n += len(pattern.findall(line))
    return n


def scan_rollout(path: Path) -> dict[str, int]:
    """Count what the transcripts cannot show: nested vision calls, failed attachments,
    and tool errors the model absorbed inside its turn."""
    out = {"view_image_calls": 0, "image_attach_failures": 0, "tool_errors": 0,
           "patch_stale_target": 0, "patch_dup_target": 0, "attach_miss": 0,
           "turns_with_tool_error": 0, "episodes_tool_calls": 0}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        # Two shapes, depending on how codex ran the tool: nested inside a code-mode
        # `exec` cell it is a `custom_tool_call` mentioning view_image (the sibling
        # port's runs); called directly it is a `function_call` named view_image (every
        # run here -- the first version counted only the former and
        # read 0 against rollouts that held the call).
        if '"custom_tool_call"' in line:
            out["view_image_calls"] += len(_ROLLOUT_VIEW_IMAGE.findall(line))
        elif '"function_call"' in line and re.search(r'"name":\s*"view_image"', line):
            out["view_image_calls"] += 1
        if _ROLLOUT_ATTACH_FAIL.search(line):
            out["image_attach_failures"] += 1
        out["tool_errors"] += len(_ROLLOUT_TOOL_ERROR.findall(line))
        out["patch_stale_target"] += len(_ROLLOUT_PATCH_STALE.findall(line))
        out["patch_dup_target"] += len(_ROLLOUT_PATCH_DUP.findall(line))
        out["attach_miss"] += len(_ROLLOUT_ATTACH_MISS.findall(line))
        if is_tool_call_line(line):
            out["episodes_tool_calls"] += len(_ROLLOUT_EPISODES_TOOL.findall(line))
    # One rollout is one turn under one turn per session (`SESSION_TURNS` 1, the direct arm), so this is the rate that matters:
    # a turn that lost an attempt, however many times the text is echoed inside it.
    out["turns_with_tool_error"] = 1 if out["tool_errors"] else 0
    return out


def find_rollout(codex_home: Path | None, workspace: Path, session_id: str | None) -> Path | None:
    """The rollout file for this session, under whichever home the wrapper gave codex.

    Codex writes `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<session_id>.jsonl`.
    Which home that was depends on the wrapper in front of codex, and none of them is
    visible from here, so every candidate is searched in order of specificity:

      1. `codex_home` given to CodexTurn, then $CODEX_HOME -- what the runner asked for;
      2. $CODEX_EPISODE_HOME, then `<workspace>.codexhome` -- what `codex_sandbox.sh`
         gives codex, regardless of what the runner asked for (it --clearenvs);
      3. `~/.codex/runtime-home`, then `~/.codex` -- what a `codex` wrapper that
         overrides CODEX_HOME can force, and codex's own default.
    """
    if not session_id:
        return None
    workspace = Path(workspace)
    home = Path(os.environ.get("HOME", "~")).expanduser()
    candidates: list[Path] = []
    for cand in (
        codex_home,
        os.environ.get("CODEX_HOME"),
        os.environ.get("CODEX_EPISODE_HOME"),
        workspace.with_name(workspace.name + ".codexhome"),
        home / ".codex" / "runtime-home",
        home / ".codex",
    ):
        if cand:
            cand = Path(cand)
            if cand not in candidates:
                candidates.append(cand)
    for cand in candidates:
        sessions = cand / "sessions"
        if not sessions.is_dir():
            continue
        hits = sorted(sessions.glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
        if hits:
            return hits[-1]
    return None


def run_codex(
    args: Sequence[str], *, cwd: Path | str, prompt: str, env: dict[str, str] | None,
    timeout: float,
) -> subprocess.CompletedProcess:
    """`subprocess.run(capture_output=True, text=True)` that kills the whole process
    group on timeout.

    `subprocess.run` kills only its direct child. Here that child is a launcher -- the
    `codex` on PATH is a bash wrapper that execs node, which spawns the native codex
    binary; `codex_sandbox.sh` is bash around bwrap -- so on a timeout the process
    that is actually talking to the model survives as an orphan and keeps looping.
    Measured: a default×codex call timed out at 420 s and its native codex
    was still issuing requests eight minutes later. Codex is started in its own
    session and the group is killed, so a timeout ends the requests as well as the
    wait. Raises `subprocess.TimeoutExpired` carrying the partial stdout/stderr, like
    `subprocess.run` does.
    """
    proc = subprocess.Popen(
        list(args), cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(list(args), timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(list(args), proc.returncode, stdout, stderr)


class CodexTurn:
    def __init__(
        self,
        workspace: Path,
        *,
        model: str,
        reasoning_effort: str = "low",
        base_url: str | None = None,
        codex_bin: str | None = None,
        codex_home: Path | None = None,
        # See CodexProvider: the same ceiling, read from the same place, so a run that
        # bounds one arm's stalls bounds the other's identically.
        timeout: int = int(os.environ.get("CODEX_TIMEOUT", 1800)),
        transcript_dir: Path | None = None,
        context_window: int | None = None,
        # "workspace-write" is the arms' shared posture. "read-only" is the direct
        # arm's closest approach to a toolless turn: codex exec cannot shed its exec
        # cell, so the filesystem is made unwritable instead and the residual asymmetry
        # is audited via tool/write counters rather than assumed away.
        sandbox_mode: str = "workspace-write",
        # None = the environment decides (CODEX_SESSION_MAX_TURNS, default 0: never
        # drop the session). The purple agent passes its value explicitly.
        session_max_turns: int | None = None,
    ) -> None:
        # Absolute, always. Codex runs with cwd == this directory, so every path derived
        # from it -- `-o last_message.txt`, the `-i` frames -- is handed to codex relative
        # to *its* cwd. A sibling port measured a relative workspace losing
        # every attached frame and every last_message.txt, silently.
        self.workspace = Path(workspace).resolve()
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.base_url = base_url
        self.context_window = context_window or DEFAULT_CONTEXT_WINDOW
        self.codex_bin = codex_bin or os.environ.get("CODEX_BIN", "codex")
        self._env_scrub_logged = False
        self.codex_home = Path(codex_home) if codex_home else None
        self.timeout = timeout
        self.sandbox_mode = sandbox_mode
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        if self.transcript_dir:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.session_id: str | None = None
        self.calls = 0
        # Runaway ceiling, outside the scored protocol (env CODEX_MAX_CALLS, set by
        # run-arm.sh; 0 = off). A healthy 12,000-step run uses ~2,200 calls at the
        # baseline's cadence and ~130 at the worldmodel's; the ceiling exists for the
        # degenerate case -- a retry storm's worst case is analyzer_retries x steps =
        # 60,000 calls. A run that hits it is reported by the nonzero counter and is
        # not a reportable result.
        self.max_calls = int(os.environ.get("CODEX_MAX_CALLS", "0") or 0)
        self.ceiling_hits = 0
        # Turns the account's usage limit refused, the current streak of them, and the
        # refusal text (it carries the reset time). See `_QUOTA_RE`.
        self.quota_refusals = 0
        self.quota_streak = 0
        self.quota_message = ""
        self.quota_skipped = 0
        # Audited in the comparison: an arm's score is only interpretable next to how
        # much vision it actually received.
        self.images_attached = 0
        # Bytes of attachment carried by the *current* session. On a resumed thread codex
        # re-sends every prior frame with each call, so this grows ~0.4 MB a turn; past
        # roughly 5.5 MB on the wire the first call of every turn stalls at ~600s and the
        # arm effectively stops. Tracked because every other counter here is
        # token-triggered and reads 27% used at the point that happens -- nothing in this
        # report moved while three arms ground to a halt.
        self.session_attachment_bytes = 0
        self.peak_attachment_bytes = 0
        # Read off the rollout at audit time, not from the event stream, which does not
        # carry them. See scan_rollout.
        self.view_image_calls = 0
        self.image_attach_failures = 0
        # Per-rollout scan results, keyed by path, refreshed only when a file's mtime
        # moves. Under one turn per session (`SESSION_TURNS` 1, the direct arm) an episode leaves hundreds of rollouts and
        # `report()` is written periodically, so rescanning all of them every time would
        # cost ~90 MB of reading per report by the end.
        self._rollout_counts: dict[Path, dict[str, int]] = {}
        self._rollout_mtimes: dict[Path, int] = {}
        self._transcript_counts: dict[Path, int] = {}
        self._transcript_mtimes: dict[Path, int] = {}
        # Fixed once the first rollout is located, so the audit can never wander into
        # another arm's home partway through an episode.
        self._sessions_root: Path | None = None
        self._rollouts_scanned = 0
        self._tool_error_counts = {
            "tool_errors": 0, "patch_stale_target": 0, "patch_dup_target": 0,
            "attach_miss": 0, "turns_with_tool_error": 0, "episodes_tool_calls": 0}
        self.overflow_resets = 0
        # Three recovery counters this backend once lacked and the PRO-LONG baseline's
        # channel had. Their absence was a single point of failure: this backend
        # dropped a session only on context overflow, so any *other* unclean ending left
        # `session_id` set and every later turn resumed into the same broken thread.
        # Measured on the 200-step ender_dragon smoke: `codex exec resume` failed
        # host-wide with a corrupt thread store, the PRO-LONG baseline discarded and
        # cold-started twice in 9 turns and kept planning, and this arm spent 27 of its 55
        # turns re-resuming the same dead session -- one successful plan in the whole run,
        # then a permanent 3-retries-and-noop loop. An agent that cannot recover its model
        # channel is not measuring its memory mechanism.
        self.timeout_resets = 0
        self.empty_resets = 0
        # Synthesises the signal the hosted backend never sends: latency grows with session
        # depth until every call times out, and there is no server error to listen for. 0
        # disables (the vLLM path, whose flat latency never needed it).
        self.session_max_turns = (
            int(os.environ.get("CODEX_SESSION_MAX_TURNS", "0"))
            if session_max_turns is None else int(session_max_turns))
        self.session_turns = 0
        self.age_resets = 0
        # Must stay 0. A nonzero count means codex compacted the conversation, so the
        # arm is no longer "the filesystem as memory + a cold start on overflow" and
        # cannot be averaged with the runs that were.
        self.compactions = 0

    def _discard_session(self, why: str, counter: str) -> None:
        """Drop the thread rather than retry into it -- PRO-LONG's stance for every
        unclean ending. Everything the next turn needs is on the filesystem: logs.txt, the
        episode store, the agent's own files. Only the conversation is lost, and a
        conversation that cannot be resumed is worth nothing anyway."""
        logger.warning(
            f"[codex] turn {self.calls}: discarding session {self.session_id} "
            f"({why}); the next call cold-starts"
        )
        self.session_id = None
        self.session_turns = 0
        # The next call cold-starts, so the thread stops carrying its old frames.
        self.session_attachment_bytes = 0
        setattr(self, counter, getattr(self, counter) + 1)

    def write_system_prompt(self, text: str) -> None:
        """Upstream puts the system prompt in AGENTS.md, which Codex discovers from
        the working directory. Written once; rewriting it mid-episode would change
        the agent's instructions underneath it."""
        agents_md = self.workspace / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(text, encoding="utf-8")

    def _args(
        self, images: Sequence[Path] = (), prompt_on_stdin: bool = True
    ) -> list[str]:
        args = [
            self.codex_bin, "exec",
            "--json", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
        ]
        # Before -m, not after the last flag: -i/--image is variadic, so anything
        # positional that follows it is read as one more image path. On the resume
        # path that positional is the session id, and losing it would silently turn
        # every turn into a cold start. A non-variadic flag terminates the list.
        for image in images:
            args += ["-i", str(image)]
        args += [
            "-m", self.model,
            "-c", f'model_reasoning_effort="{effort_for(self.base_url, self.reasoning_effort)}"',
            "-o", str(self.workspace / "last_message.txt"),
        ]
        if self.base_url:
            args += [
                "-c", "model_provider=local",
                "-c", 'model_providers.local.name="local"',
                "-c", f'model_providers.local.base_url="{self.base_url}"',
                "-c", 'model_providers.local.wire_api="responses"',
            ] + provider_auth_args() + _metadata_args(self.context_window)
        # workspace-write, not upstream's danger-full-access: writes stay in the
        # workspace and the agent's own commands get no network, so it cannot reach
        # the Minecraft sandbox and drive the world behind the runner's back.
        #
        # Set through -c rather than -s because `codex exec resume` rejects -s
        # ("unexpected argument '-s' found") while accepting the same config
        # override. Upstream hits this too and works around it by bypassing the
        # sandbox entirely on resume; that would leave every turn after the first
        # unconfined, so the config form is used on both paths instead.
        args += ["-c", f'sandbox_mode="{self.sandbox_mode}"']
        # Hosted models keep codex's own context metadata -- it knows the real window and
        # ours would be a guess overriding a fact -- but the overflow policy is a separate
        # knob and belongs to the experiment, not to a default.
        if AUTO_COMPACT_TOKEN_LIMIT and not self.base_url:
            args += ["-c", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}"]
        args += list(SAFE_CODEX_FLAGS)
        if self.session_id:
            # Documented order: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]
            args = args[:2] + ["resume"] + args[2:] + [self.session_id]
        if prompt_on_stdin:
            args.append("-")
        return args

    def _quota_blocked(self) -> bool:
        """Has the account's usage limit refused enough turns in a row that spawning
        another codex is pure cost?

        The limit that stopped four arms resets days later, so nothing an
        episode does can clear it; every QUOTA_RETRY_AFTER-th blocked call is still let
        through as a probe, which is what picks up a shorter rolling window reopening
        mid-run.
        """
        if self.quota_streak < QUOTA_STREAK_STOP:
            return False
        self.quota_skipped += 1
        return bool(self.quota_skipped % QUOTA_RETRY_AFTER)

    def run(self, prompt: str, images: Sequence[Path] = (), *,
            expect_actions: bool = True) -> dict[str, Any]:
        """Execute one turn. Returns {"actions_json", "message", "ok", "error"}.

        `images` are attached to this turn's prompt unconditionally -- on the resume
        path too, which `codex exec resume -i` supports. Upstream's log carries the
        full observation as text; here the observation is pixels, so attaching the
        current frame is what keeps the analyzer as informed as upstream's is, and as
        informed as the baseline agent it is compared against.

        `expect_actions=False` for a turn that by design produces no `actions.json`.
        Without it every such turn logs a missing-plan warning, which is not a defect
        and hides the ones that are.
        """
        if self.max_calls and self.calls >= self.max_calls:
            self.ceiling_hits += 1
            if self.ceiling_hits == 1:
                logger.error(f"[codex] call ceiling {self.max_calls} reached "
                             f"(CODEX_MAX_CALLS); refusing further model calls -- "
                             f"the episode continues on the agents' failure paths")
            return {"actions_json": None, "message": "", "ok": False,
                    "error": f"call ceiling {self.max_calls} reached",
                    "overflow": False}
        if self._quota_blocked():
            return {"actions_json": None, "message": "", "ok": False,
                    "error": f"account usage limit: {self.quota_message}",
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

        env, dropped = scrub_env(os.environ.copy())
        if dropped and not self._env_scrub_logged:
            self._env_scrub_logged = True
            logger.info(f"[codex] env: not passed to codex: {', '.join(dropped)}")
        if self.codex_home:
            env["CODEX_HOME"] = str(self.codex_home)
        env.setdefault("LOCAL_API_KEY", "EMPTY")
        # Codex is a tokio binary and sizes its worker pool to the host's cores: 255
        # here, so every in-flight turn held ~270 threads and 16 arms used ~4,500 of the
        # user's 21,626-pid cgroup on codex alone (a launch died at java start once the
        # budget was gone). Eight workers is plenty for a process that waits on one HTTP
        # stream; measured 22 threads with this set. Resource-only: nothing the model
        # sees or does changes, so the arms stay comparable across the switch.
        env.setdefault("TOKIO_WORKER_THREADS", "8")

        # Absolute, and present. Codex resolves `-i` against ITS cwd -- the workspace --
        # so a relative path that exists for the runner does not exist for codex, and the
        # only trace is a line in the conversation that the event stream never shows. The
        # sibling port lost all 20 attachments of a run that way. Raise rather
        # than filter: an arm that quietly stops attaching frames is a different arm, and
        # this one is compared against a baseline that gets 20 frames every step.
        images = [Path(p) for p in images]
        relative = [p for p in images if not p.is_absolute()]
        if relative:
            raise ValueError(
                f"attachments must be absolute paths; codex resolves -i against its own "
                f"cwd ({self.workspace}), not the runner's: {relative}"
            )
        missing = [p for p in images if not p.exists()]
        if missing:
            logger.error(
                f"[codex] turn {self.calls + 1}: {len(missing)} attachment(s) do not "
                f"exist and will not be sent: {missing}"
            )
        images = [p for p in images if p.exists()]
        args = self._args(images)
        self.images_attached += len(images)
        # 4/3 for base64, which is how the payload travels and where the wall was measured.
        self.session_attachment_bytes += sum(p.stat().st_size for p in images) * 4 // 3
        self.peak_attachment_bytes = max(
            self.peak_attachment_bytes, self.session_attachment_bytes)
        logger.info(
            f"[codex] turn {self.calls} model={self.model} "
            f"resume={'yes' if self.session_id else 'no'} images={len(images)}"
        )
        try:
            proc = run_codex(
                args, cwd=self.workspace, prompt=prompt, env=env, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as expired:
            # Keep what the turn had already emitted. Written after `run` returned, the
            # transcript was missing for exactly the turns worth reading -- a stall's
            # last event is what distinguishes hanging in a tool from hanging on the
            # wire, and without it the only evidence a timeout leaves is its duration.
            partial = expired.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            if self.transcript_dir:
                # Composed, not `with_suffix`: that replaces `.timeout` rather than
                # extending it, and the partial would land under the name a completed
                # turn uses.
                stem = f"turn_{self.calls:04d}.timeout"
                (self.transcript_dir / f"{stem}.events.jsonl").write_text(partial, encoding="utf-8")
                (self.transcript_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
            logger.error(
                f"[codex] turn {self.calls} timed out after {self.timeout}s; "
                f"{len(partial.splitlines())} events kept"
            )
            self._discard_session(f"timed out after {self.timeout}s", "timeout_resets")
            return {"actions_json": None, "message": "", "ok": False, "error": "timeout"}

        stats = request_stats(proc.stdout)
        violated = {k: stats[k] for k in ("web_searches", "mcp_tool_calls", "subthreads") if stats[k]}
        if self.transcript_dir:
            stem = self.transcript_dir / f"turn_{self.calls:04d}"
            stem.with_suffix(".events.jsonl").write_text(proc.stdout, encoding="utf-8")
            stem.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
            if proc.stderr:
                stem.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")

        if violated:
            raise SandboxViolation(
                f"codex turn {self.calls} used capabilities this arm must not have: "
                f"{violated}. The tool surface in force is not the one SAFE_CODEX_FLAGS "
                f"describes; see the transcript under {self.transcript_dir}."
            )

        # Keep the thread id so the next turn resumes rather than restarting cold.
        if self.session_id is None:
            match = _SESSION_RE.search(proc.stdout)
            if match:
                self.session_id = match.group(1)
                logger.info(f"[codex] session {self.session_id}")
        self.session_turns += 1

        errors = []
        overflowed = False
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            # No view_image counting here. "Every observed value is 0" was not a
            # measurement, it was the counter: codex 0.147 runs the model's tools inside
            # an `exec` cell and this stream reports only shell commands, so a nested
            # `tools.view_image(...)` never appears. `vision_audit()` reads the rollout.
            # Finding #30 -- "the analyzer opened none across 8 turns" -- rests on this
            # counter and has to be re-checked against those runs' rollouts before it is
            # quoted again.
            if _COMPACTION_RE.search(line):
                self.compactions += 1
                logger.error(
                    f"[codex] turn {self.calls} shows a compaction event; the "
                    f"conversation is no longer the one this arm claims to run: {line[:200]}"
                )
            if event.get("type") in ("error", "turn.failed"):
                raw = event.get("message") or event.get("error") or ""
                if isinstance(raw, dict):
                    name, text = raw.get("name", "CodexError"), raw.get("message", str(raw))
                else:
                    name, text = "CodexError", str(raw)
                errors.append(text)
                overflowed = overflowed or is_overflow(name, text)

        if overflowed and self.session_id:
            # Drop the thread rather than retry into it. Everything the next turn
            # needs is in logs.txt and the workspace; only the conversation is lost.
            self._discard_session("overflowed the context window", "overflow_resets")

        actions_path = self.workspace / "actions.json"
        actions_json = actions_path.read_text(encoding="utf-8") if actions_path.exists() else None
        message_path = self.workspace / "last_message.txt"
        message = message_path.read_text(encoding="utf-8").strip() if message_path.exists() else ""

        # Two independent facts, reported on separate lines. A tool error inside the turn
        # is not why a plan is missing, and a turn run with expect_actions=False writes no plan by design;
        # gluing them into one warning cost two misdiagnoses in a single session, both of
        # them reading a self-healing apply_patch rejection as a lost action.
        quota = next((e for e in errors if _QUOTA_RE.search(e)), None)
        if quota:
            self.quota_refusals += 1
            self.quota_streak += 1
            self.quota_message = quota.strip()[:200]
            if self.quota_streak == 1:
                logger.error(f"[codex] the account has no usage left: {self.quota_message}")
            elif self.quota_streak == QUOTA_STREAK_STOP:
                logger.error(
                    f"[codex] {QUOTA_STREAK_STOP} turns in a row refused for usage; "
                    f"stopping model calls (one probe every {QUOTA_RETRY_AFTER} turns) -- "
                    f"the episode continues on the agents' failure paths and its result "
                    f"is not a measurement")
        elif actions_json is not None or message:
            self.quota_streak = 0
        if errors:
            logger.warning(f"[codex] turn {self.calls} reported: {errors[-1][:200]}")
        if actions_json is None and expect_actions:
            logger.warning(
                f"[codex] turn {self.calls} wrote no actions.json (rc={proc.returncode})"
                f"{'' if errors else '; ' + proc.stderr.strip()[:200]}"
            )
        # Nothing at all -- no plan and no message -- means the turn never reached the
        # model. A broken `resume` is exactly this shape, and retrying into the same
        # session reproduces it forever; the agent's own retry loop then just multiplies
        # the cost. Cold-start instead, which is the one thing that can succeed. Checked
        # for a turn without a plan too, where a missing plan is normal but silence is not.
        if actions_json is None and not message and self.session_id:
            self._discard_session("produced no output at all", "empty_resets")
        return {
            "actions_json": actions_json,
            "message": message,
            "ok": actions_json is not None if expect_actions else bool(message),
            "error": errors[-1] if errors else None,
            "overflow": overflowed,
        }

    def _transcript_episodes_tool_calls(self) -> int:
        """Episode-tool calls counted from this backend's own saved turn events."""
        if not self.transcript_dir or not self.transcript_dir.exists():
            return 0
        total = 0
        for path in sorted(self.transcript_dir.glob("turn_*.events.jsonl")):
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if self._transcript_mtimes.get(path) != mtime:
                self._transcript_counts[path] = count_episodes_tool(
                    path, _ROLLOUT_EPISODES_TOOL)
                self._transcript_mtimes[path] = mtime
            total += self._transcript_counts[path]
        return total

    def vision_audit(self) -> dict[str, Any]:
        """What the model actually saw, read from the rollout rather than the events.

        `image_attach_failures` must be 0. Nonzero means `-i` did not land, so the
        episode ran vision-on-demand while reporting itself as the forced-vision arm.
        """
        rollout = find_rollout(self.codex_home, self.workspace, self.session_id)
        if rollout is not None and self._sessions_root is None:
            # .../sessions/YYYY/MM/DD/rollout-*.jsonl
            self._sessions_root = rollout.parents[3]
        # Every rollout this arm has written, not just the current session's. A session
        # used to be the whole episode, so one file was the whole audit; under
        # one turn per session (`SESSION_TURNS` 1, the direct arm) it is one turn out of hundreds, and this read
        # `view_image_calls=0` against rollouts holding 96 of them while
        # `image_attach_failures` -- the check that the arm really ran forced vision --
        # covered a single turn. Broken by the session-length default in 6ed146a.
        found = (sorted(self._sessions_root.glob("*/*/*/rollout-*.jsonl"))
                 if self._sessions_root else ([rollout] if rollout else []))
        for path in found:
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if self._rollout_mtimes.get(path) != mtime:
                self._rollout_counts[path] = scan_rollout(path)
                self._rollout_mtimes[path] = mtime
        if found:
            counts = {k: sum(c.get(k, 0) for c in self._rollout_counts.values())
                      for k in ("view_image_calls", "image_attach_failures",
                                "tool_errors", "patch_stale_target", "patch_dup_target",
                                "attach_miss", "turns_with_tool_error",
                                "episodes_tool_calls")}
            self.view_image_calls = counts["view_image_calls"]
            self.image_attach_failures = counts["image_attach_failures"]
            # See the shared backend: the turn transcripts are a second source, and they
            # outlive a node-local codex home. Whichever saw more wins.
            counts["episodes_tool_calls"] = max(
                counts.get("episodes_tool_calls", 0),
                self._transcript_episodes_tool_calls())
            self._tool_error_counts = counts
            self._rollouts_scanned = len(found)
            if self.image_attach_failures:
                logger.error(
                    f"[codex] {self.image_attach_failures} attachment(s) never reached "
                    f"the model (\"could not read the local image\" in {rollout}); this "
                    f"episode ran vision-on-demand, not forced vision"
                )
        elif self.images_attached:
            logger.warning(
                f"[codex] no rollout found for session {self.session_id}; the vision "
                f"audit is unverified for this episode"
            )
        return {
            "frames_attached": self.images_attached,
            # Must be 0 in any reportable run: nonzero means the CODEX_MAX_CALLS
            # runaway ceiling fired and the tail of the episode ran without a model.
            "call_ceiling_hits": self.ceiling_hits,
            # Turns the account's usage limit refused. Must be 0 in any reportable run:
            # nonzero means part of the episode ran with no model behind it.
            "quota_refusals": self.quota_refusals,
            "quota_skipped_calls": self.quota_skipped,
            "view_image_calls": self.view_image_calls,
            "image_attach_failures": self.image_attach_failures,
            "vision_audit_source": str(self._sessions_root or rollout) if
                                   (self._sessions_root or rollout) else None,
            "rollouts_scanned": self._rollouts_scanned,
            # Tool calls the model got an error back from and recovered inside its turn.
            # Invisible to the event stream and therefore to every other counter here.
            # `turns_with_tool_error / rollouts_scanned` is the rate to compare between
            # arms: on one run it was 75% for the world model against 3% for PRO-LONG, ~9 s
            # a turn, which a comparison would otherwise charge to the method.
            "tool_errors": self._tool_error_counts["tool_errors"],
            "patch_stale_target": self._tool_error_counts["patch_stale_target"],
            "patch_dup_target": self._tool_error_counts["patch_dup_target"],
            "attach_miss": self._tool_error_counts["attach_miss"],
            "turns_with_tool_error": self._tool_error_counts["turns_with_tool_error"],
            # The MFM arm's query tool (tools/episodes.py) run inside a turn; 0 elsewhere.
            "episodes_tool_calls": self._tool_error_counts.get("episodes_tool_calls", 0),
            # Why each conversation ended. Under a turn cap these are all zero and the
            # arm's memory is the filesystem by construction; once sessions are allowed
            # to grow, `overflow_resets` against `compactions` is the whole difference
            # between an arm that cold-starts when it fills and one that summarises and
            # carries on.
            # Byte-side, unlike everything below it. The stall crossed at
            # 5.15-6.15 MB with the token budget reading 27% used; if this number
            # approaches 5 MB the arm is about to slow by 10x with no other symptom.
            "attachment_bytes_peak": self.peak_attachment_bytes,
            "auto_compact_token_limit": AUTO_COMPACT_TOKEN_LIMIT or "codex default",
            "compactions": self.compactions,
            "overflow_resets": self.overflow_resets,
            "age_resets": self.age_resets,
            "timeout_resets": self.timeout_resets,
            "empty_resets": self.empty_resets,
        }

    @staticmethod
    def extract_plan(message: str) -> str:
        """Pull the [PLAN] block the prompt asks for; fall back to the last lines."""
        return CodexTurn.split_briefing(message)[1]

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        """(briefing, plan): the text before the [PLAN] marker and the block after it,
        as upstream splits its `hint`/`plan` pair (`codex_agent.py:677-681`). Without a
        marker the whole message is the plan's stand-in (last 400 chars) and there is
        no briefing."""
        text = (message or "").strip()
        match = re.search(r"\[PLAN\]\s*(.+)", text, re.DOTALL)
        if match:
            return text[: match.start()].strip(), match.group(1).strip()
        return "", text[-400:]
