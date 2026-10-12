"""One resumable Codex conversation driving a workspace that outlives it.

The Codex channel of the KiCad mfm arm. (The Minecraft harness has its own channel,
`MCU/mcu_worldmodel/codex_backend.py`.) The constructor has a few policy knobs; the KiCad
arm runs with their defaults:

  derive_codex_home   derive a per-episode `<workspace>.codexhome` when no home is given;
                      False leaves the home to the caller.
  window_headroom,    the `_metadata_args` sent for a locally served model: by default
  compact_scope       codex is told the window is 8x the real one, and the compaction
                      scope is pinned (codex 0.148).
  poisoned_after      drop a session after N consecutive failed turns.
  salvage_timeouts    accept an artifact written before a stall.
  overflow_policy     the phrases that classify an error as a context overflow.
  quota_gate          stop calling after a run of usage-limit refusals (off by default).

The contract: a persistent workspace, AGENTS.md carrying the system prompt, a turn prompt
pointing at logs.txt, one JSON artifact as the only output that matters, and
`codex exec resume` for continuity with a cold start on overflow. The result dict
carries the artifact under both `artifact` and `actions_json`.

The inline notes record measurements taken while the channel was built, some of them on
MCU-AgentBeats and on a question-answering benchmark run in shards; treat them as
provenance.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def resolve_codex_bin(bin_str: str) -> str:
    """A codex binary named by a relative path is resolved against the launch CWD,
    once, at construction. Every call runs with cwd == the workspace (CodexTurn) or a
    scratch dir (CodexClient), so a relative `CODEX_BIN=model_channel/codex_sandbox.sh`
    stops existing the moment it is used -- measured as FileNotFoundError on the first
    turn. A bare command name carries no directory and is left to PATH."""
    if "/" in bin_str:
        return str(Path(bin_str).resolve())
    return bin_str


def ensure_system_skills_marker(home: Path) -> Path:
    """Tell codex its system skills are already installed (as nothing), so none are.

    Two conventions exist for the same intent and both must be left standing. This
    package seeds a DIRECTORY `skills/.system` holding the marker file, the way the
    codex_sandbox wrapper does. The MCU launcher (`MCU/scripts/codex-home.sh`)
    instead seeds a plain FILE at that path: codex 0.153 installs its bundled
    skills there at every start, and a file makes that install fail harmlessly.

    `mkdir(exist_ok=True)` raises FileExistsError when the path is a file, and an
    arm that calls this on every episode start did so: on one run the adapter swallowed that
    exception, returned a noop, and retried `start` on the next step -- 5,910 identical
    failures, the player never leaving spawn, a node held for 25 minutes with nothing in
    the log calling it an error. A file already there is the launcher's marker, and it
    serves.
    """
    marker = Path(home) / "skills" / ".system"
    if marker.exists() and not marker.is_dir():
        return marker
    marker.mkdir(parents=True, exist_ok=True)
    (marker / ".codex-system-skills.marker").touch()
    return marker


def prepare_codex_home(home: Path, *, hosted: bool) -> Path:
    """Create and seed a per-episode (or throwaway) CODEX_HOME the way
    `codex_sandbox.sh` does, so the bare-binary path gets the same state isolation as
    the wrapped one.

    Without this, codex falls back to `~/.codex`: the personal AGENTS.md lands in every
    prompt (+3,866 tokens measured on a one-word prompt), the account's skills and
    plugins land in the tool surface, and every run's sessions -- another episode's
    included -- share one `sessions/` dir that
    `workspace-write` does nothing to keep the agent's shell out of, since it bounds
    writes and not reads.

    The seed is the wrapper's: an empty `skills/.system` with its marker, which tells
    codex the system skills are already installed (as nothing), so none are injected.
    Hosted calls also need credentials; auth.json is symlinked read-through from the
    master home ($CODEX_EVAL_HOME, else ~/.codex) rather than copied, so no token is
    written into the run tree.
    """
    ensure_system_skills_marker(home)
    if hosted and not (home / "auth.json").exists():
        masters = [Path(os.environ["CODEX_EVAL_HOME"])] if os.environ.get("CODEX_EVAL_HOME") \
            else [Path.home() / ".codex-eval", Path.home() / ".codex"]
        for master in masters:
            src = master / "auth.json"
            if src.exists():
                try:
                    (home / "auth.json").symlink_to(src)
                except OSError as e:
                    logger.warning("[codex] could not link auth into %s: %s", home, e)
                break
        else:
            logger.warning(
                "[codex] no auth.json under %s; a hosted call from %s will not "
                "authenticate", " or ".join(map(str, masters)), home,
            )
    return home

_SESSION_RE = re.compile(r'"(?:thread_id|session_id)"\s*:\s*"([0-9a-fA-F-]{36})"')
# Compaction announces itself in a type-ish field, never in prose, so this cannot be
# tripped by a model that happens to write the word. See `_metadata_args` for why a
# single hit matters.
_COMPACTION_RE = re.compile(r'"(?:type|kind|action_trigger)"\s*:\s*"[^"]*compact', re.I)

# What codex should believe about a locally served model. Codex has no catalog entry
# for it -- every turn logs `Model metadata for <name> not found. Defaulting to
# fallback metadata` -- so without this its context accounting is a guess. Not applied
# to hosted models, where codex's own metadata is right and ours would be a guess
# overriding a fact.
DEFAULT_CONTEXT_WINDOW = int(os.environ.get("CODEX_MODEL_CONTEXT_WINDOW", 131072))

# How far above the real window codex is told the window is. Only has to be enough that
# codex never reaches its own compaction trigger; the server enforces the real limit.
_CODEX_WINDOW_HEADROOM = int(os.environ.get("CODEX_WINDOW_HEADROOM", 8))

# What happens when a resumed conversation fills up. Codex ships auto-compaction, so
# there are two outcomes and this arm only ever described one of them: overflow and
# cold-start, with logs.txt as the memory of record. Left unset the choice belongs to
# `_metadata_args`' far-above-the-window default (local) or codex's own default (hosted),
# and the arm behaves exactly as before. Set above the real window it is that same policy
# made explicit on both paths; set below it, the thread survives summarised -- a
# different memory story that has to be labelled as one. The audit reports the value in
# force and `compactions` says which branch actually ran.
AUTO_COMPACT_TOKEN_LIMIT = os.environ.get("CODEX_AUTO_COMPACT_TOKEN_LIMIT", "").strip()

# The account behind the credential has no usage left. Codex reports it as an ordinary
# turn error carrying the reset time ("You've hit your usage limit ... try again at
# Sep 7th, 2026 10:25 AM"), so nothing else here can tell it apart from a transient
# failure. Measured on MCU-AgentBeats, where the arms run on a subscription credential
# and retry in a fixed loop: one run spent 1,551 of its 2,394 calls on this refusal, each
# an instant failure. With the gate (`quota_gate`; the Minecraft channel has the same
# rule), after QUOTA_STREAK_STOP refusals in a row the calls stop -- no spawn, no call
# counted against the ceiling -- and every QUOTA_RETRY_AFTER-th blocked call still goes
# out as a probe, which is what picks up a rolling window reopening mid-run.
_QUOTA_RE = re.compile(r"hit your usage limit|usage limit reached|purchase more credits", re.I)
QUOTA_STREAK_STOP = 5
QUOTA_RETRY_AFTER = 40

# Consecutive failed turns on one session before it is treated as unusable. 2, not 1: one
# failure is a hiccup worth retrying in place, and the arm gets 3 attempts, so the
# third one cold-starts and the turn still produces a plan.
_POISONED_AFTER = 2


def effort_for(base_url: str | None, effort: str) -> str:
    """The reasoning effort to send, which on a local server is the thinking switch.

    vLLM synthesises `enable_thinking = (effort != "none")` from a Responses request's
    `reasoning.effort` and merges it as `defaults | request`, so the request wins and a
    server-side `--default-chat-template-kwargs` pin is overridden by every codex turn.
    Codex sends no `chat_template_kwargs` of its own, so effort is the only lever it has.

    **The invariant this function exists to hold: the codex arms and the direct arm must
    agree about thinking.** They are configured from opposite ends -- the server's
    template kwargs govern the direct arm, this value governs the codex arms -- so
    nothing but care keeps them together, and a comparison whose channel control differs
    in thinking cannot separate the agent axis from the channel axis.

    Hosted models keep the caller's effort: there the field means what codex means by
    it, and nothing downstream reinterprets it as a template switch.
    """
    if not base_url:
        return effort
    return os.environ.get("CODEX_LOCAL_EFFORT", effort)


def _metadata_args(context_window: int, headroom: int | None = None,
                   scope: bool = True) -> list[str]:
    """Codex config for a model codex has never heard of.

    `model_auto_compact_token_limit` is the load-bearing one. The binary carries
    auto-compaction and its fallback prompts, and telling codex the real context window
    is exactly what would let it start compacting a long resumed conversation as it
    fills. That would quietly replace the log as the memory: PRO-LONG's stance, which
    our overflow handler mirrors, is that codex has no compaction and an overflowed
    session must cold-start, which is what keeps logs.txt the memory of record. Set the
    trigger above the window so the server's own context limit -- and the cold start
    that follows it -- always arrives first.

    The direction of that comparison is inferred, not documented, so it is not trusted
    on its own: `CodexTurn` counts compaction events in the transcripts and reports them
    in the audit, and a nonzero count means this argument is wrong and the arm needs
    re-describing rather than quietly re-running.

    **That tripwire did not fire, and the guard still failed.** codex-cli
    0.148.0 -- installed two hours before a run started, against code measured
    on 0.147.0 -- compacts *before* sampling, and does it against
    `model_context_window` rather than the auto-compact limit. On that run the
    conversation reached that window at turn 763 and every turn after it died the same
    way: stderr `Failed to run pre-sampling compact`, then a 400 from the compaction
    request itself. 386 of 1150 turns and 64 questions were lost to it, and `compactions`
    stayed 0 throughout -- the tripwire counts compactions that *happened*, and these
    never got far enough to be one.

    So the window codex is told about is now deliberately far above the real one, which
    is the same intent as before applied one level up: with nothing for codex to compact
    against, the server's own context limit arrives first and `is_overflow` turns it into
    the cold start that keeps logs.txt the memory of record. `..._scope` is pinned rather
    than inherited because 0.148 added it (`total` | `body_after_prefix`) and a default
    that moves under us is what caused this.
    """
    # `headroom=1, scope=False` is the two-flag form: the real window, no scope pin.
    codex_window = context_window * (_CODEX_WINDOW_HEADROOM if headroom is None else headroom)
    args = [
        "-c", f"model_context_window={codex_window}",
        # CODEX_AUTO_COMPACT_TOKEN_LIMIT makes the overflow policy an experiment
        # variable; unset, the far-above-the-window default keeps compaction unreachable.
        "-c", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT or codex_window * 8}",
    ]
    if scope:
        args += ["-c", 'model_auto_compact_token_limit_scope="total"']
    return args


# What the model is allowed to hold in its hands, fixed here rather than left to codex's
# defaults. Measured on codex-cli 0.147.0, through the production sandbox
# wrapper, hosted account: without these the tool list carried `web__run` -- and the model
# used it to fetch a Wikipedia article -- plus ~250 account-level `mcp__codex_apps__*`
# connectors (github, gmail, slack, google_drive, hugging_face, ...) and the sub-agent
# tools (`spawn_agent`, ...). All three run server-side or in the codex process itself,
# so no local sandbox, ours or upstream's container, is on their path; only config is.
#
#   web_search          default "cached": OpenAI's web index.
#   features.apps       account connectors; the docs say their "traffic [is] not
#                       controlled by sandboxed-command network proxy".
#   agents.enabled      the sub-agent tools. `--disable multi_agent` does NOT remove
#                       them (measured); this key does. Off so a turn is one thread and
#                       the request/token accounting means what it says.
#   plugins/remote      the plugin catalog and its `request_plugin_install` tool.
#   image_generation    server-side image tool; noise here.
#
# Injected by `CodexTurn._args` and `CodexClient` (both codex code paths, both the first
# turn and `codex exec resume`), not by the wrapper -- the wrapper passes args through
# verbatim and could not add these without knowing where the resume SESSION_ID positional
# sits. `request_stats` turns any web_search / mcp_tool_call / sub-thread that shows up
# anyway into a hard SandboxViolation.
SAFE_CODEX_FLAGS: tuple[str, ...] = (
    "-c", 'web_search="disabled"',
    "-c", "features.apps=false",
    "-c", "apps._default.enabled=false",
    "-c", "agents.enabled=false",
    "-c", "features.remote_plugin=false",
    "-c", "features.plugins=false",
    "-c", "features.image_generation=false",
    # goals are local scratch state, not an exfiltration path, but disabling them makes
    # the nested tool list exactly EXPECTED_NESTED_TOOLS, so a check can assert equality
    # rather than a subset and a new default tool cannot slip in unnoticed.
    "-c", "features.goals=false",
)

# The nested-tool names a turn is allowed to see once SAFE_CODEX_FLAGS are in force;
# anything extra is a configuration that reached the model and must not be run.
EXPECTED_NESTED_TOOLS: frozenset[str] = frozenset({
    "apply_patch", "exec_command", "update_plan", "view_image", "write_stdin",
})


class SandboxViolation(RuntimeError):
    """A turn reached a capability the arm is defined not to have.

    Raised, not recorded: a web search or a connector call means the configuration in
    force is not the one the results claim, and every later turn of the episode is
    contaminated (the result may sit in the resumed conversation or in a file the model
    wrote). The evaluators do not catch this, so the run stops here, loudly.
    """


# A tool result is what makes codex send the model another request, so these are what
# turn one call into several. Named rather than inferred, so an unfamiliar item type is
# undercounted visibly instead of inflating the count silently.
_TOOL_ITEM_TYPES = frozenset({
    "command_execution", "view_image", "file_change", "patch_apply",
    "mcp_tool_call", "web_search", "todo_list",
})


def request_stats(events: str) -> dict[str, Any]:
    """What one arm's calls actually cost, read off the saved event stream.

    "One call per step" is the wrong unit for a codex arm. A single turn runs an agentic
    loop: the model answers, calls a tool, and is asked again with the result appended,
    re-paying the whole prompt each time. Comparing per-call cost against the direct arm
    without this counts a codex turn as one request and understates it by however many
    tools the model reached for.

    requests = one per tool result plus the one that closes each turn. Token totals come
    from codex's own `turn.completed` usage, so they are its accounting, not our estimate
    -- but that usage is CUMULATIVE over the thread, so summing it naively is quadratic.
    Usage is returned per thread, to be maxed and only then summed (`merge_stats`); a
    session dropped after an overflow starts a new thread and its own counter, which is
    exactly the boundary the totals should respect.
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


# The wordings a full context window has actually been observed to arrive as. Kept as
# data, because the first version of this predicate was
# written from what the error *ought* to say: it matched OpenAI's "maximum context length
# is N tokens" and missed vLLM's "exceeds the max_model_len", which shares not one word
# with it. The cost was silent. On one n=1042 run 132 overflows
# were reported by the server and `overflow_resets` recorded 0, so the one-turn cold start
# this function exists to trigger never ran; recovery fell to the generic two-failures
# rule, one turn later each time, and the questions lost in that extra turn came in blocks
# of a dozen -- 44 of the run's 47 unanswered questions.
_OVERFLOW_PHRASES = (
    "max_model_len",                 # vLLM: "engine prompt length N exceeds the max_model_len M"
    "reduce prompt",                 # vLLM, same message
    "too long",
    "context_length_exceeded",
)

# What `is_overflow` matches beyond the shared clauses: free phrases, and word pairs that
# must both appear.
OVERFLOW_POLICY: dict[str, tuple] = {
    "phrases": _OVERFLOW_PHRASES, "pairs": (("prompt length", "exceeds"),)}


def is_overflow(name: str, text: str, policy: dict[str, tuple] | None = None) -> bool:
    """Does this Codex error mean the model's context window is full?

    Codex has no native compaction, so an overflowed session stays overflowed: every
    later turn on the same session id fails the same way. The only recovery is a cold
    start, which is cheap here because `logs.txt` -- not the conversation -- is the
    memory.

    Matching is deliberately broad. A false positive costs one cold start, which this
    arm is built to absorb; a false negative costs a block of failed turns, which it is not.
    """
    policy = policy or OVERFLOW_POLICY
    lname, lmsg = name.lower(), text.lower()
    return (
        "overflow" in lname
        or any(p in lmsg for p in policy["phrases"])
        or ("context" in lmsg and ("length" in lmsg or "limit" in lmsg or "window" in lmsg))
        or ("maximum" in lmsg and "tokens" in lmsg)
        or any(all(w in lmsg for w in pair) for pair in policy["pairs"])
    )


# Codex 0.147 runs the model's tools inside a `exec` code-mode cell, and the `--json`
# event stream reports only *shell* commands (`command_execution`). A nested
# `tools.view_image(...)` -- which is how the model looks at a frame -- never appears
# there at all. Measured on a sandbox calibration run: 0 events mentioning view_image, while
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
_ROLLOUT_VIEW_IMAGE = re.compile(r"view_image")
# codex 0.148 records the model's tool calls as response_item payloads of type
# "function_call" with a "name" field; 0.147 wrapped them in "custom_tool_call" lines.
# Matching the name alone would overcount: the system prompt itself says "view_image"
# and rides every rollout as message text.
_ROLLOUT_FN_VIEW_IMAGE = re.compile(r'"name"\s*:\s*"view_image"')
_ROLLOUT_ATTACH_FAIL = re.compile(r"could not read the local image", re.I)
# The MFM arm's retrieval tool, counted so a run can say whether the agent used the
# episode store at all, separately from whether the score moved.
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


# The rollout's own record of a compaction having happened. `_COMPACTION_RE` scans the
# per-turn event stream, which -- exactly as with view_image -- does not carry the event:
# one run's three shards compacted 8-25 times each while every stream-derived
# count stayed 0. The rollout is the ground truth, so the tripwire reads it.
_ROLLOUT_COMPACTED = re.compile(r'"type"\s*:\s*"compacted"')


def scan_rollout(path: Path) -> dict[str, int]:
    """Count what the transcripts cannot show: nested vision calls and failed attachments."""
    full = scan_rollout_full(path)
    return {k: full[k] for k in ("view_image_calls", "image_attach_failures", "compactions")}


def scan_rollout_full(path: Path) -> dict[str, int]:
    """`scan_rollout` plus the calls of the episode tool, in the same single pass."""
    out = {"view_image_calls": 0, "image_attach_failures": 0, "compactions": 0,
           "episodes_tool_calls": 0}
    # Streamed, never read whole. A rollout embeds every image the turn sent as base64,
    # so it grows with the episode: a 350-question shard left 3.0 GB of them
    # and a 345-question one 5.7 GB, with single files near 1 GB. `read_text()` plus
    # `splitlines()` holds the file twice over -- as one string and as a list of its
    # lines -- which is what killed one shard of that run with OUT_OF_MEMORY at
    # 7.5G/8G, after it had answered all 350 questions but before it could write
    # result.json. Line-by-line, the peak is one line.
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if '"custom_tool_call"' in line:
                out["view_image_calls"] += len(_ROLLOUT_VIEW_IMAGE.findall(line))
            elif '"function_call"' in line and _ROLLOUT_FN_VIEW_IMAGE.search(line):
                out["view_image_calls"] += 1
            if _ROLLOUT_ATTACH_FAIL.search(line):
                out["image_attach_failures"] += 1
            # One `"type":"compacted"` record per event. The paired `ContextCompaction`
            # item is deliberately NOT counted: both describe the same compaction, and
            # counting both doubles the figure the tripwire is read by.
            if _ROLLOUT_COMPACTED.search(line):
                out["compactions"] += 1
            if is_tool_call_line(line):
                out["episodes_tool_calls"] += len(_ROLLOUT_EPISODES_TOOL.findall(line))
    return out


def find_rollout(codex_home: Path | None, workspace: Path, session_id: str | None) -> Path | None:
    """The rollout file for this session, under whichever home the wrapper gave codex.

    `codex_sandbox.sh` derives `<workspace>.codexhome` when nothing is set, so that is
    the default guess; an explicit `codex_home` or $CODEX_HOME wins.
    """
    if not session_id:
        return None
    candidates = [c for c in (
        codex_home,
        Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else None,
        # What `codex_sandbox.sh` gives codex regardless of what the runner asked for.
        Path(os.environ["CODEX_EPISODE_HOME"]) if os.environ.get("CODEX_EPISODE_HOME") else None,
        Path(str(workspace).rstrip("/") + ".codexhome"),
        # codex 0.148 writes rollouts under its own "runtime home" regardless of the
        # CODEX_HOME it was handed (measured: one run's eleven sessions
        # landed in ~/.codex/runtime-home/sessions while the per-episode home got only
        # auth.json and skills/). These shared homes are safe last resorts because the
        # lookup matches the exact session id.
        Path.home() / ".codex" / "runtime-home",
        Path.home() / ".codex",
    ) if c]
    seen: list[Path] = []
    for home in candidates:
        if home in seen:
            continue
        seen.append(home)
        matches = sorted((home / "sessions").rglob(f"*{session_id}.jsonl"))
        if matches:
            return matches[-1]
    return None


def run_codex(
    args: Sequence[str], *, cwd: Path | str, prompt: str, env: dict[str, str] | None,
    timeout: float,
) -> subprocess.CompletedProcess:
    """`subprocess.run(capture_output=True, text=True)` that kills the whole process
    group on timeout.

    `subprocess.run` kills only its direct child. Here that child is a launcher -- the
    `codex` on PATH is a bash wrapper that execs node, which spawns the native codex
    binary; `codex_sandbox.sh` is bash around bwrap -- so on a timeout the process that
    is actually talking to the model survives as an orphan and keeps issuing requests
    (measured in MCU-AgentBeats: still going eight minutes after its caller
    gave up). Codex is started in its own session and the group is killed, so a timeout
    ends the requests as well as the wait. Raises `subprocess.TimeoutExpired` carrying
    the partial stdout/stderr, like `subprocess.run` does.
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
        try:
            # Bounded, because SIGKILL does not reach a process blocked in the kernel:
            # when a storage server dropped out every codex turn in flight
            # left a live `bwrap` with an unreaped child, and this drain -- written
            # without a timeout -- waited on a pipe that namespace never closed. Three
            # 12-hour shard jobs sat there until they were cancelled by hand, past a
            # 30-minute turn timeout that had already fired.
            stdout, stderr = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            logger.error(
                "[codex] the killed process group did not exit within 60s (a process "
                "blocked in the kernel ignores SIGKILL -- a stalled filesystem does "
                "this); abandoning its pipes and failing the turn")
            for pipe in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass
            stdout = stderr = ""
        raise subprocess.TimeoutExpired(list(args), timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(list(args), proc.returncode, stdout, stderr)


class LocalServerGate:
    """The server gate: a locally served model that can move between nodes.

    Shared by `CodexTurn` (the agent arms) and `codex_client.CodexClient` (the direct
    arm), so that every channel pointed at a preemptible server treats an outage as a
    pause rather than a run of defaults. Requires a `base_url` attribute.
    """

    # -- a local server that can move -----------------------------------------------
    #
    # `CODEX_BASE_URL_FILE` names a file whose one line is the current server address
    # (for example `runs/<name>/server.addr`, written by the serve job once /v1/models answers
    # and removed on its way out). Set only for a locally served channel on a preemptible
    # partition, where the server can be killed and come back minutes later on another
    # node. Without this, that outage reached the arms as a run of transport failures:
    # each question spent its whole retry budget against a dead address and defaulted,
    # so a fifteen-minute preemption cost a shard several questions it never asked --
    # and every question after it, because the address the process held was stale.
    # With it, an outage is a pause: the turn waits for a healthy address, adopts it,
    # and runs once more without spending the caller's budget.

    def _address_file(self) -> Path | None:
        f = os.environ.get("CODEX_BASE_URL_FILE", "").strip()
        return Path(f) if (f and self.base_url) else None

    @staticmethod
    def _server_answers(url: str) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/models", timeout=10) as r:
                return r.status == 200
        except Exception:
            return False

    def _adopt_published_address(self) -> bool:
        """Take the address the file names, if it differs. True when it changed."""
        f = self._address_file()
        if f is None or not f.exists():
            return False
        try:
            url = f.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if url and url != self.base_url:
            logger.warning("[codex] server address changed: %s -> %s", self.base_url, url)
            self.base_url = url
            return True
        return False

    def _await_server(self) -> bool:
        """Block until the address file names a server that answers. False on giving up."""
        f = self._address_file()
        if f is None:
            return False
        ceiling = float(os.environ.get("CODEX_SERVER_WAIT", 4 * 3600))
        waited, step = 0.0, 15.0
        while waited < ceiling:
            if f.exists():
                self._adopt_published_address()
                if self._server_answers(self.base_url):
                    if waited:
                        logger.warning("[codex] server back at %s after %.0fs",
                                       self.base_url, waited)
                    return True
            if waited == 0:
                logger.warning("[codex] server at %s is not answering; waiting for %s "
                               "(up to %.0fs)", self.base_url, f, ceiling)
            time.sleep(step)
            waited += step
            step = min(step * 1.5, 120)
        logger.error("[codex] no server after %.0fs; failing the turn", ceiling)
        return False


    def _sandbox_allow_env(self, env: dict) -> None:
        """Re-allow the current server host in the sandbox's egress allowlist.

        The allowlist is read per invocation from `CODEX_SANDBOX_ALLOW`, so a server that
        moved to another node must be re-allowed here as well as re-addressed --
        otherwise the call would resolve the new address and the proxy would refuse to
        connect to it. A no-op when no address file is configured.
        """
        if self._address_file() is None or not self.base_url:
            return
        from urllib.parse import urlparse
        u = urlparse(self.base_url)
        if u.hostname:
            env["CODEX_SANDBOX_ALLOW"] = f"{u.hostname}:{u.port or (443 if u.scheme == 'https' else 80)}"


class CodexTurn(LocalServerGate):
    """One resumable Codex conversation, driving a workspace that outlives it."""

    def __init__(
        self,
        workspace: Path,
        *,
        model: str,
        artifact_name: str = "actions.json",
        # The closing message's file. A second CodexTurn in the same workspace names
        # its own (the KiCad design call: `.design.msg`), so neither overwrites the
        # other's `-o` file.
        message_name: str = "last_message.txt",
        reasoning_effort: str = "low",
        base_url: str | None = None,
        codex_bin: str | None = None,
        codex_home: Path | None = None,
        # The same ceiling the client provider reads, from the same place, so a run that
        # bounds one arm's stalls bounds the other's identically.
        timeout: int = int(os.environ.get("CODEX_TIMEOUT", 1800)),
        transcript_dir: Path | None = None,
        context_window: int | None = None,
        session_max_turns: int | None = None,
        session_max_bytes: int | None = None,
        # Backend policy (module docstring); the KiCad arm runs with these defaults.
        derive_codex_home: bool = True,
        window_headroom: int | None = None,
        compact_scope: bool = True,
        poisoned_after: int | None = _POISONED_AFTER,
        salvage_timeouts: bool = True,
        overflow_policy: dict[str, tuple] | None = None,
        quota_gate: bool = False,
    ) -> None:
        # Absolute, always. Codex runs with cwd == this directory, so every path derived
        # from it -- `-o last_message.txt`, the `-i` frames -- is handed to codex relative
        # to *its* cwd, and a relative `--workspace` made both resolve to nothing: measured
        # as `Failed to write last message file "runs/.../last_message.txt"`
        # (so no [PLAN] ever reached the log) and `Codex could not read the local image at
        # runs/.../frames/q0000_0.png` on every turn. Inside the sandbox nothing
        # but the absolute path exists, which is what made it visible.
        self.workspace = Path(workspace).resolve()
        self.model = model
        self.artifact_name = artifact_name
        self.message_name = message_name
        self.reasoning_effort = reasoning_effort
        self.base_url = base_url
        self.context_window = context_window or DEFAULT_CONTEXT_WINDOW
        self.codex_bin = resolve_codex_bin(codex_bin or os.environ.get("CODEX_BIN", "codex"))
        # The home is never left to codex's `~/.codex` default: an explicit argument
        # wins, an explicit $CODEX_HOME is respected (and recorded by the arm block),
        # and otherwise the per-episode sibling the sandbox wrapper would derive --
        # `<workspace>.codexhome` -- is derived here too and seeded the same way, so
        # the bare-binary path and the wrapped path put state in the same place and
        # neither ever mixes with a personal home. Only the derived home is seeded;
        # a home the caller named is theirs.
        self.window_headroom = window_headroom
        self.compact_scope = compact_scope
        self.poisoned_after = poisoned_after
        self.salvage_timeouts = salvage_timeouts
        self.overflow_policy = overflow_policy or OVERFLOW_POLICY
        if codex_home:
            self.codex_home = Path(codex_home)
        elif not derive_codex_home:
            # The caller owns the home ($CODEX_HOME reaching codex through the
            # inherited environment); nothing is derived here.
            self.codex_home = None
        elif os.environ.get("CODEX_HOME"):
            self.codex_home = Path(os.environ["CODEX_HOME"])
        else:
            # Auth is seeded only on the truly bare path. Under the sandbox wrapper the
            # wrapper bind-mounts the master's auth.json onto this same home itself --
            # and bwrap cannot create a mount point over the dangling symlink the seed
            # would leave (measured: "Can't create file at .../auth.json"), so seeding
            # here would break the very path that already had auth handled.
            wrapped = Path(self.codex_bin).name == "codex_sandbox.sh"
            self.codex_home = prepare_codex_home(
                Path(str(self.workspace) + ".codexhome"),
                hosted=base_url is None and not wrapped)
            logger.info("[codex] derived per-episode CODEX_HOME %s", self.codex_home)
        self.timeout = timeout
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        if self.transcript_dir:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.session_id: str | None = None
        # Every session this conversation has run under, in order. Under a session age
        # cap an episode leaves many sessions behind, and the vision audit has to scan
        # all of their rollouts rather than the last one's.
        self.session_ids: list[str] = []
        self._rollout_by_session: dict[str, Path] = {}
        self.calls = 0
        # Audited in the comparison: an arm's score is only interpretable next to how
        # much of the observation it actually received.
        self.images_attached = 0
        # Bytes of attachment carried by the *current* session. On a resumed thread codex
        # re-sends every prior image with each call; past roughly 5.5 MB on the wire the
        # first call of every turn stalls near the timeout and the arm effectively stops
        # (measured in MCU-AgentBeats). Tracked because the token counters
        # read far-from-full at the point that happens.
        self.session_attachment_bytes = 0
        self.peak_attachment_bytes = 0
        # Read off the rollout at audit time, not from the event stream, which does not
        # carry them. See scan_rollout.
        self.view_image_calls = 0
        self.image_attach_failures = 0
        self.overflow_resets = 0
        # Upstream discards the session on ANY unclean ending -- timeout, empty output,
        # overflow -- never resuming into a suspect thread: a resumed retry re-pays the
        # whole transcript into the same stall.
        self.timeout_resets = 0
        # A stalled stream is not a failed turn when the artifact is already on disk:
        # the workspace file is the contract, and the stale-clear at the top of run()
        # guarantees one present after this attempt was written by it. One task
        # lost three completed answers to this over 45 minutes and scored a default.
        self.timeouts_salvaged = 0
        # The usage-limit gate (module docstring at `_QUOTA_RE`); off in the KiCad
        # policy, whose extend loop hands infrastructure failures to the driver.
        self.quota_gate = quota_gate
        self.quota_refusals = 0
        self.quota_streak = 0
        self.quota_message = ""
        self.quota_skipped = 0
        self.empty_resets = 0
        # A backend that slows with session depth instead of erroring never trips the
        # overflow cold start. The cap synthesises the missing signal client-side: the
        # same cold start, triggered by session age. 0 disables it. An arm whose thread
        # policy is part of its definition passes the argument (the KiCad mfm arm: 6,
        # `mfm_agent.DEFAULT_SESSION_TURNS`); otherwise the environment decides,
        # defaulting to off (one thread, cold start on overflow only).
        self.session_max_turns = (
            int(os.environ.get("CODEX_SESSION_MAX_TURNS", "0"))
            if session_max_turns is None else int(session_max_turns))
        self.session_turns = 0
        self.age_resets = 0
        # The same synthesised cold start, triggered by the frames the resumed thread
        # carries instead of by its age. Codex re-sends every earlier attachment on each
        # call, so a resumed session's payload grows ~0.48 MB an act turn and past ~5.5 MB
        # on the wire every turn stalls near the timeout (MCU run-arm.sh). A
        # turn cap of 1 sidestepped that by giving up the conversation entirely; this
        # keeps one thread until the NEXT turn's frame would carry it past the budget,
        # then hands off to a fresh one -- VISTA's `thread_bytes_budget`, with the
        # filesystem as the checkpoint. 0 disables (CODEX_SESSION_MAX_BYTES, default 0).
        self.session_max_bytes = (
            int(os.environ.get("CODEX_SESSION_MAX_BYTES", "0") or 0)
            if session_max_bytes is None else int(session_max_bytes))
        self.bytes_resets = 0
        # A session can be left unusable by something that is not an overflow -- codex
        # 0.148's failed pre-sampling compaction is the case this exists for: every turn
        # on the poisoned session returned the same 400, `is_overflow` did not match it,
        # and the analyzer retried into the same session until it ran out of attempts and
        # answered from a default. Retries are cheap; retrying into a dead conversation is
        # not, so a session that fails twice running is dropped the same way an overflowed
        # one is. logs.txt is the memory either way.
        self.session_resets = 0
        self._failed_turns_on_session = 0
        self.stats: list[dict[str, Any]] = []
        # Must stay 0. A nonzero count means codex compacted the conversation, so the
        # arm is no longer "the filesystem as memory + a cold start on overflow" and
        # cannot be averaged with the runs that were.
        self.compactions = 0
        self.rollout_compactions: int | None = None   # set once a rollout is scanned
        # Runaway ceiling, outside the scored protocol (env CODEX_MAX_CALLS; 0 = off,
        # and the KiCad launcher does not set it). It exists for the degenerate case (a
        # retry storm's worst case is analyzer_retries x steps). A run that hits it logs
        # an error and is not a reportable result.
        self.max_calls = int(os.environ.get("CODEX_MAX_CALLS", "0") or 0)
        self.ceiling_hits = 0
        # Per-rollout scan results, refreshed only when a file's mtime moves: an episode
        # under a session age cap leaves hundreds of rollouts and the audit is written
        # periodically, so rescanning all of them each time would read gigabytes.
        self._rollout_counts: dict[Path, dict[str, int]] = {}
        self._rollout_mtimes: dict[Path, int] = {}
        self._last_rollouts: list[Path] = []
        self.episodes_tool_calls = 0
        self._transcript_counts: dict[Path, int] = {}
        self._transcript_mtimes: dict[Path, int] = {}

    def _result(self, artifact: str | None, message: str, *, ok: bool,
                error: str | None, overflow: bool) -> dict[str, Any]:
        """The turn's result. `actions_json` duplicates `artifact` (the field's name
        in the Minecraft channel)."""
        return {"artifact": artifact, "actions_json": artifact, "message": message,
                "ok": ok, "error": error, "overflow": overflow}

    def _quota_blocked(self) -> bool:
        """Has the account's usage limit refused enough turns in a row that spawning
        another codex is pure cost? See `_QUOTA_RE`."""
        if not self.quota_gate or self.quota_streak < QUOTA_STREAK_STOP:
            return False
        self.quota_skipped += 1
        return bool(self.quota_skipped % QUOTA_RETRY_AFTER)

    def _note_quota(self, errors: list[str]) -> None:
        quota = next((e for e in errors if _QUOTA_RE.search(e)), None)
        if quota:
            self.quota_refusals += 1
            self.quota_streak += 1
            self.quota_message = quota.strip()[:200]
            if self.quota_streak == 1:
                logger.error("[codex] the account has no usage left: %s", self.quota_message)
            elif self.quota_gate and self.quota_streak == QUOTA_STREAK_STOP:
                logger.error("[codex] %d usage-limit refusals in a row; model calls stop, "
                             "one probe every %d", self.quota_streak, QUOTA_RETRY_AFTER)
        elif self.quota_streak:
            logger.info("[codex] usage limit cleared after %d refusal(s)", self.quota_streak)
            self.quota_streak = 0

    def _discard_session(self, why: str, counter: str) -> None:
        """Drop the thread rather than retry into it -- the single place a session ends.

        Every unclean ending (timeout, empty output, overflow, poisoned, age cap) routes
        through here, so the counters always add up and no path can forget half the
        bookkeeping. Everything the next turn needs is in logs.txt and the workspace;
        only the conversation is lost.
        """
        logger.warning(
            "[codex] turn %d: discarding session %s (%s); the next call cold-starts",
            self.calls, self.session_id, why,
        )
        self.session_id = None
        self.session_turns = 0
        self._failed_turns_on_session = 0
        # The next call cold-starts, so the thread stops carrying its old attachments.
        self.session_attachment_bytes = 0
        setattr(self, counter, getattr(self, counter) + 1)

    def write_system_prompt(self, text: str) -> None:
        """Upstream puts the system prompt in AGENTS.md, which Codex discovers from the
        working directory. Written once; rewriting it mid-episode would change the
        agent's instructions underneath it."""
        agents_md = self.workspace / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(text, encoding="utf-8")

    def _args(self, images: Sequence[Path] = (), prompt_on_stdin: bool = True) -> list[str]:
        args = [
            self.codex_bin, "exec",
            "--json", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
        ]
        # Before -m, not after the last flag: -i/--image is variadic, so anything
        # positional that follows it is read as one more image path. On the resume path
        # that positional is the session id, and losing it would silently turn every turn
        # into a cold start. A non-variadic flag terminates the list.
        for image in images:
            args += ["-i", str(image)]
        args += [
            "-m", self.model,
            "-c", f'model_reasoning_effort="{effort_for(self.base_url, self.reasoning_effort)}"',
            "-o", str(self.workspace / self.message_name),
        ]
        # Opt-in output cap via env, so existing arms are byte-identical without it.
        max_out = os.environ.get("CODEX_MAX_OUTPUT_TOKENS", "").strip()
        if max_out:
            args += ["-c", f"model_max_output_tokens={int(max_out)}"]
        if self.base_url:
            args += [
                "-c", "model_provider=local",
                "-c", 'model_providers.local.name="local"',
                "-c", f'model_providers.local.base_url="{self.base_url}"',
                "-c", 'model_providers.local.wire_api="responses"',
                "-c", 'model_providers.local.env_key="LOCAL_API_KEY"',
            ] + _metadata_args(self.context_window, self.window_headroom, self.compact_scope)
        # workspace-write, not danger-full-access: writes stay in the workspace and the
        # agent's own commands get no network, so it cannot reach the corpus, the dataset
        # or the grader behind the runner's back. Set through -c rather than -s because
        # `codex exec resume` rejects -s while accepting the same config override, and
        # bypassing the sandbox on resume would leave every turn after the first
        # unconfined.
        args += ["-c", 'sandbox_mode="workspace-write"']
        # Hosted models keep codex's own context metadata, but the overflow policy is a
        # separate knob and belongs to the experiment rather than to a default. The
        # local path gets the same value through `_metadata_args`.
        if AUTO_COMPACT_TOKEN_LIMIT and not self.base_url:
            args += ["-c", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}"]
        args += list(SAFE_CODEX_FLAGS)
        if self.session_id:
            # Documented order: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]
            args = args[:2] + ["resume"] + args[2:] + [self.session_id]
        if prompt_on_stdin:
            args.append("-")
        return args

    def run(self, prompt: str, images: Sequence[Path] = (), *,
            expect_artifact: bool = True,
            timeout: float | None = None) -> dict[str, Any]:
        """One turn, behind the server gate; `_run_turn` is the turn itself."""
        if self._address_file() is not None:
            self._adopt_published_address()
        result = self._run_turn(prompt, images, expect_artifact=expect_artifact,
                                timeout=timeout)
        if result["ok"] or self._address_file() is None:
            return result
        if self._server_answers(self.base_url):
            return result           # the server is fine, so the failure is the model's
        if not self._await_server():
            return result
        logger.warning("[codex] re-running the turn against the recovered server")
        return self._run_turn(prompt, images, expect_artifact=expect_artifact,
                              timeout=timeout)

    def _run_turn(self, prompt: str, images: Sequence[Path] = (), *,
                  expect_artifact: bool = True,
                  timeout: float | None = None) -> dict[str, Any]:
        """Execute one turn. Returns {"artifact", "message", "ok", "error", "overflow"}.

        `images` are attached to this turn's prompt unconditionally -- on the resume path
        too, which `codex exec resume -i` supports. Where the observation is pixels
        (a frame or a screenshot), attaching them is what keeps the analyzer as informed as the direct
        arm it is compared against: a run where looking was optional made 8 analyzer
        turns and 0 `view_image` calls.

        `expect_artifact=False` is for a turn whose whole output is filesystem writes and
        a closing message (the KiCad design call): "ok" then means the message, and a
        missing artifact is not a failure and does not poison the session.

        `timeout` overrides this turn's ceiling. Not every turn is the same size: the
        KiCad design call works out a whole circuit and gets 1800 s
        (`mfm_agent.DEFAULT_DESIGN_TIMEOUT`) against an act turn's 900 s.
        """
        if self.max_calls and self.calls >= self.max_calls:
            self.ceiling_hits += 1
            if self.ceiling_hits == 1:
                logger.error("[codex] call ceiling %d reached (CODEX_MAX_CALLS); refusing "
                             "further model calls -- the episode continues on the agents' "
                             "failure paths", self.max_calls)
            return self._result(None, "", ok=False,
                                error=f"call ceiling {self.max_calls} reached", overflow=False)
        if self._quota_blocked():
            return dict(self._result(None, "", ok=False,
                                     error=f"account usage limit: {self.quota_message}",
                                     overflow=False), skipped=True)
        self.calls += 1
        ceiling = self.timeout if timeout is None else timeout
        if (
            self.session_id
            and self.session_max_turns
            and self.session_turns >= self.session_max_turns
        ):
            self._discard_session(
                f"reached {self.session_turns} turns, cap {self.session_max_turns}",
                "age_resets",
            )
        for stale in (self.artifact_name, self.message_name):
            (self.workspace / stale).unlink(missing_ok=True)

        env = os.environ.copy()
        if self.codex_home:
            env["CODEX_HOME"] = str(self.codex_home)
        env.setdefault("LOCAL_API_KEY", "EMPTY")
        self._sandbox_allow_env(env)

        # Absolute, and present. Codex resolves `-i` against ITS cwd -- the workspace --
        # so a relative path that exists for the runner does not exist for codex, and the
        # only trace is a line in the conversation the event stream never shows. That cost
        # one calibration run every one of its 20 attachments. Raise rather than filter:
        # an arm that quietly stops attaching is a different arm.
        images = [Path(p) for p in images]
        relative = [p for p in images if not p.is_absolute()]
        if relative:
            raise ValueError(
                f"attachments must be absolute paths; codex resolves -i against its own "
                f"cwd ({self.workspace}), not the runner's: {relative}"
            )
        missing = [p for p in images if not p.exists()]
        if missing:
            logger.error("[codex] turn %d: %d attachment(s) do not exist and will not be "
                         "sent: %s", self.calls + 1, len(missing), missing)
        images = [p for p in images if p.exists()]
        # 4/3 for base64, which is how the payload travels and where the wall was measured.
        incoming = sum(p.stat().st_size for p in images) * 4 // 3
        if (
            self.session_id
            and self.session_max_bytes
            and self.session_attachment_bytes + incoming > self.session_max_bytes
        ):
            self._discard_session(
                f"its frames would reach "
                f"{(self.session_attachment_bytes + incoming) / 1e6:.2f} MB on the wire, "
                f"budget {self.session_max_bytes / 1e6:.2f} MB",
                "bytes_resets",
            )
        args = self._args(images)
        self.images_attached += len(images)
        self.session_attachment_bytes += incoming
        self.peak_attachment_bytes = max(
            self.peak_attachment_bytes, self.session_attachment_bytes)
        logger.info(
            "[codex] turn %d model=%s resume=%s images=%d",
            self.calls, self.model, "yes" if self.session_id else "no", len(images),
        )
        try:
            proc = run_codex(
                args, cwd=self.workspace, prompt=prompt, env=env, timeout=ceiling,
            )
        except subprocess.TimeoutExpired as expired:
            # Keep what the turn had already emitted. A stall's last event is what
            # distinguishes hanging in a tool from hanging on the wire, and without it
            # the only evidence a timeout leaves is its duration.
            partial = expired.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            partial_err = expired.stderr or ""
            if isinstance(partial_err, bytes):
                partial_err = partial_err.decode(errors="replace")
            if self.transcript_dir:
                # Composed, not `with_suffix`: that replaces `.timeout` rather than
                # extending it, and the partial would land under the name a completed
                # turn uses.
                stem = f"turn_{self.calls:04d}.timeout"
                (self.transcript_dir / f"{stem}.events.jsonl").write_text(partial, encoding="utf-8")
                (self.transcript_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
                # The stall's stderr is the half we most need and used to drop: the
                # sandbox proxy logs every CONNECT it allows and every error it hits
                # there, so whether a disconnect came from our egress path or from the
                # server is answerable only from this file -- and only on the turns that
                # actually stalled.
                if partial_err:
                    (self.transcript_dir / f"{stem}.stderr.txt").write_text(
                        partial_err, encoding="utf-8")
            logger.error(
                "[codex] turn %d timed out after %ds; %d events kept",
                self.calls, ceiling, len(partial.splitlines()),
            )
            if self.session_id:
                # A resumed retry replays the same payload into the same stall; the
                # retry only means anything as a cold start.
                self._discard_session(f"timed out after {ceiling}s", "timeout_resets")
            if expect_artifact and self.salvage_timeouts:
                artifact_path = self.workspace / self.artifact_name
                if artifact_path.exists():
                    # Torn writes degrade safely: the caller validates the JSON and
                    # retries on garbage, which is the pre-salvage behaviour.
                    self.timeouts_salvaged += 1
                    logger.warning(
                        "[codex] turn %d: %s was written before the stall; salvaging "
                        "the artifact (the closing message is lost -- see the "
                        ".timeout transcript)", self.calls, self.artifact_name,
                    )
                    return self._result(artifact_path.read_text(encoding="utf-8"), "",
                                        ok=True, error="timeout (artifact salvaged)",
                                        overflow=False)
            return self._result(None, "", ok=False, error="timeout", overflow=False)

        stats = request_stats(proc.stdout)
        self.stats.append(stats)
        if self.transcript_dir:
            stem = self.transcript_dir / f"turn_{self.calls:04d}"
            stem.with_suffix(".events.jsonl").write_text(proc.stdout, encoding="utf-8")
            stem.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
            if proc.stderr:
                stem.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")

        violated = {k: stats[k] for k in ("web_searches", "mcp_tool_calls", "subthreads") if stats[k]}
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
                self.session_ids.append(match.group(1))
                logger.info("[codex] session %s", self.session_id)
        if self.session_id:
            self.session_turns += 1

        errors: list[str] = []
        overflowed = False
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            # No view_image counting here: codex 0.147 runs the model's tools inside an
            # `exec` cell and this stream reports only shell commands, so the count was
            # structurally 0 -- on an episode where the conversation shows 20 calls
            # returning 60 images. `audit()` reads the rollout instead.
            if _COMPACTION_RE.search(line):
                self.compactions += 1
                logger.error(
                    "[codex] turn %d shows a compaction event; the conversation is no "
                    "longer the one this arm claims to run: %s", self.calls, line[:200],
                )
            if event.get("type") in ("error", "turn.failed"):
                raw = event.get("message") or event.get("error") or ""
                if isinstance(raw, dict):
                    name, text = raw.get("name", "CodexError"), raw.get("message", str(raw))
                else:
                    name, text = "CodexError", str(raw)
                errors.append(text)
                overflowed = overflowed or is_overflow(name, text, self.overflow_policy)

        if overflowed and self.session_id:
            self._discard_session("overflowed the context window", "overflow_resets")

        artifact_path = self.workspace / self.artifact_name
        artifact = artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else None
        message_path = self.workspace / self.message_name
        message = message_path.read_text(encoding="utf-8").strip() if message_path.exists() else ""

        self._note_quota(errors)
        discarded_now = False
        if artifact is None and not message and self.session_id:
            # No artifact AND no message means the call produced nothing at all; the
            # nudged same-session retry is for a model that answered badly, not for a
            # call that never answered.
            self._discard_session("produced no output at all", "empty_resets")
            discarded_now = True
        if expect_artifact and artifact is None:
            logger.warning(
                "[codex] turn %d wrote no %s (rc=%s); %s",
                self.calls, self.artifact_name, proc.returncode,
                errors[-1] if errors else proc.stderr.strip()[:200],
            )
            # The failure that just discarded the session belongs to that session; the
            # next one starts at zero, not at one (which made it poisoned after a
            # single failure instead of `poisoned_after`).
            if not discarded_now:
                self._failed_turns_on_session += 1
            if (self.poisoned_after and self.session_id
                    and self._failed_turns_on_session >= self.poisoned_after):
                self._discard_session(
                    f"{self._failed_turns_on_session} turns in a row failed "
                    f"(last error: {(errors[-1] if errors else proc.stderr.strip())[:200]})",
                    "session_resets",
                )
        elif (artifact is not None) if expect_artifact else bool(message):
            self._failed_turns_on_session = 0
        error = errors[-1] if errors else None
        if error is None and proc.returncode != 0 and not (artifact or message):
            # The event stream only carries errors codex itself raised. When the sandbox
            # script fails before codex starts (its egress proxy never came up, say), the
            # failure is on stderr and nowhere else -- and reported as `error: None` it
            # looked to the harness like a model that answered badly, which it retried
            # on the generic short backoff and defaulted within thirty seconds.
            tail = [l for l in proc.stderr.strip().splitlines() if l.strip()]
            error = tail[-1][:300] if tail else f"exit status {proc.returncode}"
        return self._result(
            artifact, message,
            ok=artifact is not None if expect_artifact else bool(message),
            error=error, overflow=overflowed)

    def audit(self) -> dict[str, Any]:
        """The numbers a score is only interpretable next to.

        `view_image_calls` and `image_attach_failures` come from the rollout, because the
        event stream does not carry either: codex 0.147 runs the model's tools inside an
        `exec` cell and reports only shell commands. An arm whose attachments failed is
        vision-on-demand, not forced-vision, whatever its `images_attached` says.
        """
        # Every session this conversation has run under, not just the current one. Under
        # a session age cap (or after resets) an episode leaves many rollouts, and a scan
        # of the last would report a fraction of the episode as if it were the whole.
        seen = self.session_ids or ([self.session_id] if self.session_id else [])
        # A rollout's path never changes once found, so it is looked up once per
        # session and remembered. Under a 1-turn session cap every call is a session,
        # and looking all of them up again on every audit walked the sessions tree
        # N times for the N-th audit (a 2,000-call episode: millions of stats).
        for sid in seen:
            if sid not in self._rollout_by_session:
                path = find_rollout(self.codex_home, self.workspace, sid)
                if path is not None:
                    self._rollout_by_session[sid] = path
        rollouts = [self._rollout_by_session[sid] for sid in seen
                    if sid in self._rollout_by_session]
        self._last_rollouts = rollouts
        if rollouts:
            self.view_image_calls = 0
            self.image_attach_failures = 0
            rollout_compactions = 0
            episodes_tool_calls = 0
            for rollout in rollouts:
                try:
                    mtime = rollout.stat().st_mtime_ns
                except OSError:
                    continue
                if self._rollout_mtimes.get(rollout) != mtime:
                    self._rollout_counts[rollout] = scan_rollout_full(rollout)
                    self._rollout_mtimes[rollout] = mtime
                counts = self._rollout_counts[rollout]
                self.view_image_calls += counts["view_image_calls"]
                self.image_attach_failures += counts["image_attach_failures"]
                rollout_compactions += counts["compactions"]
                episodes_tool_calls += counts.get("episodes_tool_calls", 0)
            # The turn transcripts this backend writes itself are a second, independent
            # source: they survive a node-local codex home the rollouts do not outlive,
            # and they carry the shapes a future CLI may record instead. Whichever saw
            # more is the count, so a format this scanner has not met can only
            # under-report through one channel, never through both silently.
            self.episodes_tool_calls = max(episodes_tool_calls,
                                           self._transcript_episodes_tool_calls())
            # The stream can only under-report, never over-report, so the tripwire takes
            # whichever source saw more. Reported separately as well, because "the
            # stream saw none and the rollout saw 25" is the fact that explains why
            # earlier runs reported `compactions: 0`.
            self.rollout_compactions = rollout_compactions
            if rollout_compactions > self.compactions:
                logger.error(
                    "[codex] the rollout records %d compaction(s) the event stream never "
                    "reported; the conversation is not the one this arm claims to run",
                    rollout_compactions,
                )
                self.compactions = rollout_compactions
            if self.image_attach_failures:
                logger.error(
                    "[codex] %d attachment(s) never reached the model (\"could not read "
                    "the local image\" across %d rollout(s)). This episode ran "
                    "vision-on-demand, not the forced-vision arm it reports.",
                    self.image_attach_failures, len(rollouts),
                )
        elif self.images_attached:
            logger.warning("[codex] no rollout found for session(s) %s; the vision audit "
                           "is unverified for this episode", seen)
        return {
            "analyzer_turns": self.calls,
            "images_attached": self.images_attached,
            "view_image_calls": self.view_image_calls,
            # Must be 0. Nonzero means `-i` did not land and the model saw a frame only if
            # it went and fetched one itself.
            "image_attach_failures": self.image_attach_failures,
            "vision_audit_source": [str(r) for r in rollouts] or None,
            "overflow_resets": self.overflow_resets,
            "session_resets": self.session_resets,
            "timeout_resets": self.timeout_resets,
            "timeouts_salvaged": self.timeouts_salvaged,
            "empty_resets": self.empty_resets,
            "age_resets": self.age_resets,
            "session_max_turns": self.session_max_turns,
            # Only when the byte budget is on (CODEX_SESSION_MAX_BYTES), so the audit of
            # a run without it has no such keys.
            **({"session_max_bytes": self.session_max_bytes,
                "bytes_resets": self.bytes_resets} if self.session_max_bytes else {}),
            "sessions": len(seen),
            "peak_attachment_bytes": self.peak_attachment_bytes,
            # The overflow policy in force: None means the far-above-the-window default
            # (never compact; cold-start on the server's own limit).
            "auto_compact_token_limit": AUTO_COMPACT_TOKEN_LIMIT or None,
            # Expected 0. Nonzero means codex compacted the conversation, which is a
            # different memory architecture than the one being measured.
            "compactions": self.compactions,
            # Which source saw them. A rollout count above the stream count is the norm,
            # not an anomaly: the stream does not carry the event at all.
            "compactions_from_rollout": self.rollout_compactions,
            **merge_stats(self.stats),
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

    @staticmethod
    def extract_plan(message: str) -> str:
        """Pull the [PLAN] block the prompt asks for; fall back to the last lines."""
        return CodexTurn.split_briefing(message)[1]

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        """(briefing, plan): the text before the [PLAN] marker and the block after it,
        as upstream splits its `hint`/`plan` pair. Without a marker the whole message is
        the plan's stand-in (last 400 chars) and there is no briefing. A prompt
        convention rather than a backend concern; it lives here because both agents
        call it through the backend class."""
        text = (message or "").strip()
        match = re.search(r"\[PLAN\]\s*(.+)", text, re.DOTALL)
        if match:
            return text[: match.start()].strip(), match.group(1).strip()
        return "", text[-400:]
