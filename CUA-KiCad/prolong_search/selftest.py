"""Offline assertions for the PRO-LONG port. No model, no GPU, no network.

    python -m prolong_search.selftest

Mirrors `MineExplorer:prolong_mc/selftest.py` in purpose: the parts of this arm that can
be wrong *silently* are the ones checked here. An ablation that does not bind, a cap that
does not truncate, or a prompt that has drifted away from the baseline it is supposed to
be matched against all produce a number that looks fine and means something else.

The prompt-drift checks read the baseline modules with `ast` rather than importing them,
so this stays runnable on a login node: importing an evaluator pulls in torch.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from prolong_search import codex_backend                                # noqa: E402
from prolong_search import prompts_bcp                                  # noqa: E402
from prolong_search.codex_backend import (  # noqa: E402
    EXPECTED_NESTED_TOOLS, SAFE_CODEX_FLAGS, CodexTurn, effort_for, is_overflow,
    merge_stats, request_stats,
)
from prolong_search.log import SEPARATOR, EpisodeLog, prepare_workspace  # noqa: E402
from prolong_search.plans import parse_search_plan                       # noqa: E402

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  --  {detail}" if detail else ""))
        _failures.append(name)


# ---------------------------------------------------------------------------
# Overflow recognition
# ---------------------------------------------------------------------------

# Every wording a full context window has actually been seen to arrive as, kept verbatim.
# These are transcript quotes, not paraphrases: the predicate they guard was originally
# written against what the error ought to say, matched OpenAI's phrasing, and missed
# vLLM's -- which shares no word with it. 132 overflows went uncounted before anyone
# noticed, because a missed overflow does not raise, it just answers the question wrong.
OBSERVED_OVERFLOW = [
    # vLLM 0.26, chat + responses paths (2026-08-20)
    "The engine prompt length 131098 exceeds the max_model_len 131072. Please reduce prompt.",
    # OpenAI-compatible servers and hosted codex
    "This model's maximum context length is 131072 tokens. However, you requested 140000 tokens.",
    "context_length_exceeded",
    "Input is too long for requested model.",
]

# Failures that are *not* overflow. A false positive here costs one cold start, which is
# cheap; but calling a transport blip an overflow would hide a dead server behind a
# recovery that looks like normal operation.
OBSERVED_NOT_OVERFLOW = [
    "stream disconnected before completion: Transport error: network error: error decoding response body",
    "stream disconnected before completion: error sending request for url (http://192.168.2.20:8013/v1/responses)",
    'Unterminated string starting at: line 1 column 9 (char 8)',
    "",
]


def test_overflow_recognition() -> None:
    print("\noverflow recognition")
    for msg in OBSERVED_OVERFLOW:
        check(f"recognised: {msg[:48]}", is_overflow("CodexError", msg))
    for msg in OBSERVED_NOT_OVERFLOW:
        check(f"not overflow: {(msg or '<empty>')[:44]}", not is_overflow("CodexError", msg))
    check("the name channel still works", is_overflow("ContextOverflowError", "whatever"))


# ---------------------------------------------------------------------------
# The thinking invariant
# ---------------------------------------------------------------------------

def test_thinking_invariant() -> None:
    print("\nthinking invariant")
    # Hosted models keep the caller's effort; a local server's effort is the thinking
    # switch and must be changeable from the environment, not from an edit.
    check("hosted effort passes through", effort_for(None, "xhigh") == "xhigh")
    check("local effort defaults to the caller's",
          effort_for("http://localhost:8000/v1", "low") == "low")
    os.environ["CODEX_LOCAL_EFFORT"] = "none"
    try:
        check("CODEX_LOCAL_EFFORT overrides the local channel",
              effort_for("http://localhost:8000/v1", "low") == "none")
        check("CODEX_LOCAL_EFFORT does not touch the hosted channel",
              effort_for(None, "low") == "low")
    finally:
        del os.environ["CODEX_LOCAL_EFFORT"]


def test_overflow_classifier() -> None:
    print("\noverflow classifier")
    check("context-length error", is_overflow("BadRequest", "maximum context length exceeded"))
    check("prompt too long", is_overflow("BadRequest", "This prompt is too long"))
    check("named overflow", is_overflow("ContextOverflowError", "whatever"))
    check("an ordinary error is not an overflow",
          not is_overflow("RateLimit", "429 slow down"))


def test_merge_stats() -> None:
    print("\ncodex usage accounting")
    # Every turn of a resumed thread reports the whole thread's usage so far, so summing
    # them is quadratic. Max within a thread, then sum across threads.
    parts = [
        {"turns": 1, "requests": 2, "tool_calls": 1, "agent_messages": 1,
         "usage_by_thread": {"A": {"input_tokens": 40_000, "cached_input_tokens": 0,
                                   "output_tokens": 500}}},
        {"turns": 1, "requests": 1, "tool_calls": 0, "agent_messages": 1,
         "usage_by_thread": {"A": {"input_tokens": 88_000, "cached_input_tokens": 0,
                                   "output_tokens": 900}}},
        {"turns": 1, "requests": 1, "tool_calls": 0, "agent_messages": 1,
         "usage_by_thread": {"B": {"input_tokens": 12_000, "cached_input_tokens": 0,
                                   "output_tokens": 100}}},
    ]
    total = merge_stats(parts)
    check("counts add", total["turns"] == 3 and total["requests"] == 4)
    check("usage is per-thread max, then summed",
          total["input_tokens"] == 100_000, f"got {total['input_tokens']}")
    check("threads counted", total["threads"] == 2)


# ---------------------------------------------------------------------------
# Artifact parsing
# ---------------------------------------------------------------------------

def test_search_plan() -> None:
    print("\nsearch-plan parsing")
    plan = parse_search_plan('{"actions": [{"search": "a"}, {"search": "b"}, {"search": "c"}]}',
                             action_cap=2, step_budget=10)
    check("action cap truncates", plan.queries == ["a", "b"], str(plan.queries))

    plan = parse_search_plan('{"actions": [{"search": "a"}, {"search": "b"}]}',
                             action_cap=5, step_budget=1)
    check("remaining budget truncates", plan.queries == ["a"], str(plan.queries))

    plan = parse_search_plan('{"answer": {"exact_answer": "Paris", "confidence": 90}}')
    check("answer parses", plan.answer is not None and plan.answer["exact_answer"] == "Paris")

    plan = parse_search_plan(
        '{"actions": [{"search": "a"}], "answer": {"exact_answer": "Paris"}}')
    check("answer wins over searches",
          plan.answer is not None and not plan.queries)

    check("malformed JSON yields nothing", not parse_search_plan("not json"))
    check("empty actions yields nothing", not parse_search_plan('{"actions": []}'))
    check("a fenced block still parses",
          parse_search_plan('```json\n{"actions": [{"search": "a"}]}\n```').queries == ["a"])
    check("a bare string entry parses",
          parse_search_plan('{"actions": ["a"]}').queries == ["a"])


# ---------------------------------------------------------------------------
# The ablations, which must bind rather than ask
# ---------------------------------------------------------------------------

def _seed_log(record: Path, n: int) -> EpisodeLog:
    log = EpisodeLog(record, attachment_markers=("DOC",), attachment_dirs=("docs",))
    log.write_initial("Search 0 | QUESTION", ["Question: who?"])
    for i in range(1, n + 1):
        rel = log.save_attachment(f"docs/t{i:02d}_1_doc{i}.txt", f"body of doc {i}")
        log.write_section(f"Search {i} | query", [f"[SEARCH] q{i}", f"[DOC] {rel}"])
    return log


def test_windowed_copy() -> None:
    print("\nlog window")
    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / "record"
        log = _seed_log(record, 5)
        dest = Path(tmp) / "view.txt"

        full = log.windowed_copy(dest, None).read_text()
        check("window=None keeps every section", full.count(SEPARATOR) == 6,
              f"{full.count(SEPARATOR)} sections")

        latest = log.windowed_copy(dest, 0).read_text()
        check("window=0 keeps the initial section plus the latest",
              latest.count(SEPARATOR) == 2 and "Search 5" in latest and "Search 4" not in latest)

        last2 = log.windowed_copy(dest, 2).read_text()
        check("window=N keeps the initial section plus the last N",
              last2.count(SEPARATOR) == 3 and "Search 5" in last2 and "Search 4" in last2
              and "Search 3" not in last2, last2[:200])


def test_publish_binds() -> None:
    print("\nablation enforcement")
    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / "ws_record"
        visible = Path(tmp) / "ws"
        visible.mkdir()
        log = _seed_log(record, 4)
        (visible / "AGENTS.md").write_text("system prompt")
        (visible / "notes.md").write_text("what the agent worked out")

        info = log.publish(visible, window=1, stateless=False)
        view = (visible / "logs.txt").read_text()
        check("the visible log is the truncated one",
              "Search 4" in view and "Search 2" not in view)
        check("the full log is not in the visible directory",
              not (visible / "logs.txt.full").exists()
              and (record / "logs.txt").read_text().count("Search") > view.count("Search"))
        check("only the attachments the view still names are linked",
              sorted(p.name for p in (visible / "docs").glob("*")) == ["t04_1_doc4.txt"],
              str(sorted(p.name for p in (visible / "docs").glob("*"))))
        check("publish reports what it did", info["published"] and info["attachments_visible"] == 1)
        check("a non-stateless window leaves the agent's own files alone",
              (visible / "notes.md").exists())

        log.publish(visible, window=None, stateless=True)
        check("stateless removes what the agent wrote", not (visible / "notes.md").exists())
        check("stateless keeps the harness files",
              (visible / "logs.txt").exists() and (visible / "AGENTS.md").exists())
        check("stateless diverts the plan out of the carried log",
              True)  # covered by test_stateless_plan below


def test_stateless_plan() -> None:
    print("\nstateless plans")
    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / "record"
        log = EpisodeLog(record, attachment_markers=("DOC",), attachment_dirs=("docs",),
                         stateless=True)
        log.write_initial("Search 0 | QUESTION", ["Question: who?"])
        log.set_plan("try the rare surname first")
        log.write_section("Search 1 | query", ["[SEARCH] q1"])
        text = (record / "logs.txt").read_text()
        check("the plan is not carried in the log", "[PLAN]" not in text)
        check("the plan is kept for our records",
              "try the rare surname first" in (record / "plans.txt").read_text())

        log2 = EpisodeLog(Path(tmp) / "record2", attachment_markers=("DOC",),
                          attachment_dirs=("docs",), stateless=False)
        log2.write_initial("Search 0 | QUESTION", ["Question: who?"])
        log2.set_plan("try the rare surname first")
        log2.write_section("Search 1 | query", ["[SEARCH] q1"])
        check("the unablated arm keeps the plan in the log",
              "[PLAN]" in (Path(tmp) / "record2" / "logs.txt").read_text())


def test_append_lines() -> None:
    print("\nappend-to-open-section")
    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / "record"
        log = EpisodeLog(record, attachment_markers=("FRAME",), attachment_dirs=("frames",))
        log.write_initial("Question 0 | perception", ["[QUESTION] first"])
        log.append_lines(["[ANSWER] C"], plan="noted", title="Question 0")
        log.write_section("Question 1 | perception", ["[QUESTION] second"])
        log.append_lines(["[ANSWER] A"], title="Question 1")
        text = (record / "logs.txt").read_text()
        check("one section per question", text.count(SEPARATOR) == 2,
              f"{text.count(SEPARATOR)} sections")
        check("the answer lands in its own question's section",
              text.index("[ANSWER] C") < text.index("[QUESTION] second"))


def test_prepare_workspace() -> None:
    print("\nstale-workspace handling")
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "q0000"
        ws.mkdir()
        (ws / "logs.txt").write_text("a crashed attempt")
        visible, record = prepare_workspace(ws, ablated=False)
        check("the crashed workspace is moved aside, not deleted",
              (Path(tmp) / "q0000.crashed" / "logs.txt").exists())
        check("a fresh workspace is created", visible.exists() and not (visible / "logs.txt").exists())
        check("unablated record == visible", record == visible)

        visible2, record2 = prepare_workspace(Path(tmp) / "q0001", ablated=True)
        check("ablated record is a sibling of the visible dir",
              record2.name == "q0001_record" and visible2.name == "q0001")


# ---------------------------------------------------------------------------
# The sandbox contract: tool surface, its accounting, and the tripwire
# ---------------------------------------------------------------------------

def test_safe_flags_on_every_codex_call() -> None:
    print("\nsandbox: the safety flags reach codex on both paths")
    # The flags that strip web_search, the account connectors and the sub-agent tools
    # (measured on codex-cli 0.147.0). A run whose args lack any of these was configured
    # to let the model reach a capability the arm is defined not to have.
    joined = " ".join(SAFE_CODEX_FLAGS)
    for needle in ('web_search="disabled"', "features.apps=false", "agents.enabled=false",
                   "features.remote_plugin=false", "features.plugins=false",
                   "features.image_generation=false", "features.goals=false"):
        check(f"SAFE_CODEX_FLAGS carries {needle}", needle in joined)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        turn = CodexTurn(Path(tmp) / "ws", model="gpt-5.6-sol")
        first = " ".join(turn._args())
        check("first-turn args carry every safety flag",
              all(f in turn._args() for f in SAFE_CODEX_FLAGS), first[:200])
        check("first-turn args pin workspace-write", 'sandbox_mode="workspace-write"' in first)
        turn.session_id = "0" * 36           # force the resume path
        resumed = turn._args()
        check("resume args carry every safety flag too",
              all(f in resumed for f in SAFE_CODEX_FLAGS))
        # The resume positional (session id) must come last, after the -c options, or
        # codex reads a safety flag's value as the id. This is the ordering the flags
        # would break if appended naively.
        check("resume keeps the session id after the options, not swallowed by one",
              resumed[-2] == "0" * 36 and resumed[-1] == "-")


def test_request_stats_flags_violations() -> None:
    print("\nsandbox: forbidden tool use is counted, not hidden")
    import json as _json
    stream = "\n".join(_json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": "T1"},
        {"type": "item.completed", "item": {"type": "web_search", "query": "x"}},
        {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "codex_apps"}},
        {"type": "thread.started", "thread_id": "T2"},       # a spawned sub-agent
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10}},
    ])
    st = request_stats(stream)
    check("a web search is counted", st["web_searches"] == 1, str(st))
    check("an account-connector call is counted", st["mcp_tool_calls"] == 1)
    check("a second thread is counted as a sub-agent", st["subthreads"] == 1)
    # web_search and mcp_tool_call are also in _TOOL_ITEM_TYPES, so they count as
    # tool_calls too: 3 = web_search + mcp_tool_call + command_execution.
    check("tool calls still counted alongside the violation flags", st["tool_calls"] == 3,
          str(st["tool_calls"]))
    # This is exactly the dict CodexTurn.run turns into a SandboxViolation.
    violated = {k: st[k] for k in ("web_searches", "mcp_tool_calls", "subthreads") if st[k]}
    check("the tripwire would fire on this stream", bool(violated))
    clean = request_stats(_json.dumps({"type": "turn.completed", "usage": {}}))
    check("a clean stream trips nothing",
          not any(clean[k] for k in ("web_searches", "mcp_tool_calls", "subthreads")))


def test_expected_tool_surface_is_the_whitelist() -> None:
    print("\nsandbox: the expected tool whitelist is what the flags produce")
    # Kept in sync with what `sandbox_selftest.py --with-model` asserts against a live
    # ALL_TOOLS. Measured 2026-08-17 with SAFE_CODEX_FLAGS in force.
    check("whitelist is exactly the five local tools",
          EXPECTED_NESTED_TOOLS == frozenset(
              {"apply_patch", "exec_command", "update_plan", "view_image", "write_stdin"}))


def test_codex_home_isolation() -> None:
    print("\nCODEX_HOME isolation (the bare-binary path)")
    # CODEX_BIN too, and not for tidiness: whether auth is seeded depends on which
    # binary will run (the wrapper bind-mounts it instead), so a bare-binary assertion
    # made inside a job that exported the wrapper is testing the wrapped path and
    # failing. That is exactly how this test failed the first time any of it ran under
    # sbatch. The wrapped behaviour is asserted below by passing codex_bin explicitly.
    saved_env = {k: os.environ.pop(k, None)
                 for k in ("CODEX_HOME", "CODEX_EVAL_HOME", "CODEX_BIN")}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = CodexTurn(Path(tmp) / "ws", model="qwen3.8-27b",
                              base_url="http://localhost:8000/v1")
            check("no config -> the per-episode sibling is derived",
                  local.codex_home == (Path(tmp) / "ws.codexhome").resolve()
                  or local.codex_home == Path(tmp) / "ws.codexhome",
                  str(local.codex_home))
            check("the derived home is seeded with the system-skills marker",
                  (local.codex_home / "skills" / ".system"
                   / ".codex-system-skills.marker").exists())
            check("a local-server home gets no auth link",
                  not (local.codex_home / "auth.json").exists())

            master = Path(tmp) / "master"
            master.mkdir()
            (master / "auth.json").write_text("{}")
            os.environ["CODEX_EVAL_HOME"] = str(master)
            hosted = CodexTurn(Path(tmp) / "ws2", model="gpt-5.6-sol")
            check("a hosted home links auth from the master, without copying",
                  (hosted.codex_home / "auth.json").is_symlink()
                  and (hosted.codex_home / "auth.json").resolve() == (master / "auth.json").resolve())
            del os.environ["CODEX_EVAL_HOME"]

            explicit = Path(tmp) / "explicit_home"
            named = CodexTurn(Path(tmp) / "ws3", model="gpt-5.6-sol",
                              codex_home=explicit)
            check("an explicit argument wins and is not seeded",
                  named.codex_home == explicit and not explicit.exists())

            os.environ["CODEX_EVAL_HOME"] = str(master)
            wrapped = CodexTurn(Path(tmp) / "ws5", model="gpt-5.6-sol",
                                codex_bin=str(Path(tmp) / "codex_sandbox.sh"))
            check("under the wrapper the home is derived but auth is left to the "
                  "wrapper's bind (bwrap cannot mount over a dangling symlink)",
                  (wrapped.codex_home / "skills" / ".system"
                   / ".codex-system-skills.marker").exists()
                  and not (wrapped.codex_home / "auth.json").exists())
            del os.environ["CODEX_EVAL_HOME"]

            os.environ["CODEX_HOME"] = str(Path(tmp) / "env_home")
            env_turn = CodexTurn(Path(tmp) / "ws4", model="gpt-5.6-sol")
            check("an explicit $CODEX_HOME wins and is not seeded",
                  env_turn.codex_home == Path(tmp) / "env_home"
                  and not (Path(tmp) / "env_home").exists())
            del os.environ["CODEX_HOME"]

            rel = CodexTurn(Path(tmp) / "ws6", model="gpt-5.6-sol",
                            codex_bin="prolong_search/codex_sandbox.sh")
            check("a relative codex_bin is resolved at construction (calls run from "
                  "the workspace, where it would not exist)",
                  Path(rel.codex_bin).is_absolute(), rel.codex_bin)
            check("a bare command name is left to PATH",
                  CodexTurn(Path(tmp) / "ws7", model="gpt-5.6-sol",
                            codex_bin="codex").codex_bin == "codex")
    finally:
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_session_lifecycle() -> None:
    print("\nsession lifecycle (one discard choke point)")
    with tempfile.TemporaryDirectory() as tmp:
        turn = CodexTurn(Path(tmp) / "ws", model="gpt-5.6-sol")
        check("age cap disabled by default (this arm's documented behavior)",
              turn.session_max_turns == 0)
        check("the age cap is settable per arm, over the environment",
              CodexTurn(Path(tmp) / "ws1", model="gpt-5.6-sol",
                        session_max_turns=1).session_max_turns == 1)
        turn.session_id = "0" * 36
        turn.session_turns = 7
        turn._failed_turns_on_session = 1
        turn.session_attachment_bytes = 123_456
        turn.peak_attachment_bytes = 123_456
        turn._discard_session("test", "timeout_resets")
        check("discard clears the session id", turn.session_id is None)
        check("discard zeroes the turn count", turn.session_turns == 0)
        check("discard zeroes the failed-turn count", turn._failed_turns_on_session == 0)
        check("discard zeroes the live attachment bytes but keeps the peak",
              turn.session_attachment_bytes == 0 and turn.peak_attachment_bytes == 123_456)
        check("discard bumps exactly the named counter",
              turn.timeout_resets == 1 and turn.empty_resets == 0
              and turn.overflow_resets == 0 and turn.age_resets == 0
              and turn.session_resets == 0)

        os.environ["CODEX_SESSION_MAX_TURNS"] = "3"
        try:
            capped = CodexTurn(Path(tmp) / "b", model="gpt-5.6-sol")
            check("CODEX_SESSION_MAX_TURNS is read", capped.session_max_turns == 3)
        finally:
            del os.environ["CODEX_SESSION_MAX_TURNS"]

        audit = turn.audit()
        for key in ("timeout_resets", "empty_resets", "age_resets", "session_max_turns",
                    "peak_attachment_bytes", "auto_compact_token_limit", "sessions"):
            check(f"audit reports {key}", key in audit)
        check("no policy env means no policy override reported",
              audit["auto_compact_token_limit"] in (None, codex_backend.AUTO_COMPACT_TOKEN_LIMIT or None))


def test_resume() -> None:
    print("\nresume (the checkpoint says what was answered, the workspace holds why)")
    from prolong_search import resume as R

    with tempfile.TemporaryDirectory() as tmp:
        ck = Path(tmp) / "c.jsonl"
        rows = [{"index": i, "key_question": 100 + i, "task": "perception",
                 "pred": 1, "gt": 1, "correct": True} for i in range(3)]
        ck.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        recs = R.load_checkpoint_records(ck)
        check("a clean checkpoint loads whole", len(recs) == 3)

        ck.write_text("\n".join(json.dumps(r) for r in rows) + '\n{"index": 3, "key_qu')
        recs = R.load_checkpoint_records(ck)
        check("a torn final line is dropped, not fatal", len(recs) == 3)

        ck.write_text('{"index": 0, "key_q\n' + json.dumps(rows[0]) + "\n")
        try:
            R.load_checkpoint_records(ck)
            check("a torn line that is not last is refused", False)
        except SystemExit:
            check("a torn line that is not last is refused", True)

        samples = [{"key_question": 100 + i, "task_str": "perception"} for i in range(5)]
        R.verify_prefix(rows, samples)
        check("a matching prefix verifies", True)
        try:
            R.verify_prefix(rows, [{"key_question": 999, "task_str": "perception"}] * 5)
            check("a different sample sequence is refused", False)
        except SystemExit:
            check("a different sample sequence is refused", True)
        try:
            R.verify_prefix(rows, samples[:2])
            check("a limit below the checkpoint is refused", False)
        except SystemExit:
            check("a limit below the checkpoint is refused", True)

        results, per_task = R.preload(rows)
        check("preload restores the results and the per-task tallies",
              len(results) == 3 and per_task["perception"] == [True, True, True])

        out = Path(tmp) / "r.json"
        out.write_text("{}")
        R.archive_prior_result(out, 3)
        check("the earlier result is archived, not overwritten",
              (Path(tmp) / "r.json.n3").exists() and not out.exists())

        fresh = Path(tmp) / "fresh.jsonl"
        fresh.write_text(json.dumps(rows[0]) + "\n")
        try:
            R.guard_stale_checkpoint(fresh, resume=False)
            check("a stale checkpoint blocks a fresh run", False)
        except SystemExit:
            check("a stale checkpoint blocks a fresh run", True)
        R.guard_stale_checkpoint(fresh, resume=True)
        check("and does not block a resume", True)

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        (ws / "logs.txt").write_text("SECTION 0\n")
        (ws / "frames").mkdir()
        _, record = prepare_workspace(ws, ablated=False, resume=True)
        check("resume keeps the workspace where it is",
              (record / "logs.txt").read_text() == "SECTION 0\n"
              and not (ws.parent / "ws.crashed").exists())
        prepare_workspace(ws, ablated=False, resume=False)
        check("without resume the same workspace is moved aside",
              (ws.parent / "ws.crashed").exists() and not (ws / "logs.txt").exists())
        try:
            prepare_workspace(Path(tmp) / "nothing", ablated=False, resume=True)
            check("resume onto an empty directory is refused", False)
        except SystemExit:
            check("resume onto an empty directory is refused", True)


def test_timeout_salvage() -> None:
    print("\ntimeout salvage (the artifact is the contract, not the stream)")
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        stub = Path(tmp) / "stub_codex.sh"
        stub.write_text("#!/bin/bash\ncat >/dev/null\n"
                        "echo 'sandbox-proxy: ALLOW chatgpt.com:443' >&2\n"
                        "printf '{\"answer\": \"B\", \"note\": \"\"}' > answer.json\n"
                        "sleep 30\n")
        stub.chmod(0o755)
        transcripts = Path(tmp) / "turns"
        turn = CodexTurn(ws, model="m", artifact_name="answer.json",
                         codex_bin=str(stub), timeout=2,
                         codex_home=Path(tmp) / "home", transcript_dir=transcripts)
        out = turn.run("p")
        check("a timed-out turn whose artifact is on disk is salvaged",
              out["ok"] and out["artifact"] is not None
              and "salvaged" in (out["error"] or ""))
        check("the salvage is counted for the audit", turn.timeouts_salvaged == 1)
        err = transcripts / "turn_0001.timeout.stderr.txt"
        check("a stall keeps its stderr, where the egress log lives",
              err.exists() and "sandbox-proxy: ALLOW" in err.read_text())

        stub.write_text("#!/bin/bash\ncat >/dev/null\nsleep 30\n")
        out2 = turn.run("p")
        check("a timed-out turn with no artifact still fails",
              not out2["ok"] and out2["error"] == "timeout"
              and turn.timeouts_salvaged == 1)

        stub.write_text("#!/bin/bash\ncat >/dev/null\n"
                        "printf 'x' > induction_scratch.txt\nsleep 30\n")
        turn2 = CodexTurn(ws, model="m", artifact_name="answer.json",
                          codex_bin=str(stub), timeout=2,
                          codex_home=Path(tmp) / "home")
        out3 = turn2.run("p", expect_artifact=False)
        check("an induction timeout is not salvaged (its contract is the message)",
              not out3["ok"] and turn2.timeouts_salvaged == 0)


def test_per_call_timeout() -> None:
    print("\nper-call timeout override (turns are not all the same size)")
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"; ws.mkdir()
        stub = Path(tmp) / "slow.sh"
        stub.write_text("#!/bin/bash\ncat >/dev/null\nsleep 30\n")
        stub.chmod(0o755)
        turn = CodexTurn(ws, model="m", artifact_name="answer.json",
                         codex_bin=str(stub), timeout=2, codex_home=Path(tmp) / "h")
        import time as _t
        t0 = _t.monotonic(); turn.run("p"); short = _t.monotonic() - t0
        t0 = _t.monotonic(); turn.run("p", timeout=5); longer = _t.monotonic() - t0
        check("the override lengthens this call's ceiling only",
              3 < longer < 9 and short < 4 and turn.timeout == 2,
              f"short={short:.1f}s long={longer:.1f}s")


def test_auto_compact_policy() -> None:
    print("\noverflow policy (CODEX_AUTO_COMPACT_TOKEN_LIMIT)")
    saved = codex_backend.AUTO_COMPACT_TOKEN_LIMIT
    try:
        codex_backend.AUTO_COMPACT_TOKEN_LIMIT = ""
        default_args = " ".join(codex_backend._metadata_args(131072))
        check("unset: the far-above-the-window default holds",
              f"model_auto_compact_token_limit={131072 * 8 * 8}" in default_args,
              default_args)
        check("unset: the scope pin survives",
              'model_auto_compact_token_limit_scope="total"' in default_args)

        codex_backend.AUTO_COMPACT_TOKEN_LIMIT = "50000"
        set_args = " ".join(codex_backend._metadata_args(131072))
        check("set: the local path carries the explicit limit",
              "model_auto_compact_token_limit=50000" in set_args, set_args)

        with tempfile.TemporaryDirectory() as tmp:
            hosted = CodexTurn(Path(tmp) / "h", model="gpt-5.6-sol")
            hosted_args = " ".join(hosted._args())
            check("set: the hosted path carries the explicit limit too",
                  "model_auto_compact_token_limit=50000" in hosted_args)
            local = CodexTurn(Path(tmp) / "l", model="qwen3.8-27b",
                              base_url="http://localhost:8000/v1")
            local_args = " ".join(local._args())
            check("set: the local path carries it exactly once (via metadata args)",
                  local_args.count("model_auto_compact_token_limit=50000") == 1,
                  local_args)
    finally:
        codex_backend.AUTO_COMPACT_TOKEN_LIMIT = saved

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CODEX_MAX_OUTPUT_TOKENS"] = "1024"
        try:
            capped = " ".join(CodexTurn(Path(tmp) / "c", model="gpt-5.6-sol")._args())
            check("CODEX_MAX_OUTPUT_TOKENS rides the request when set",
                  "model_max_output_tokens=1024" in capped)
        finally:
            del os.environ["CODEX_MAX_OUTPUT_TOKENS"]
        uncapped = " ".join(CodexTurn(Path(tmp) / "u", model="gpt-5.6-sol")._args())
        check("no output cap without the env", "model_max_output_tokens" not in uncapped)


def test_prepare_workspace_is_absolute() -> None:
    print("\nsandbox: workspaces resolve to absolute paths")
    import os as _os, tempfile as _tf
    cwd = _os.getcwd()
    with _tf.TemporaryDirectory() as tmp:
        _os.chdir(tmp)
        try:
            visible, record = prepare_workspace(Path("rel_ws"), ablated=False)
            check("a relative workspace is made absolute",
                  visible.is_absolute() and record.is_absolute(), str(visible))
        finally:
            _os.chdir(cwd)


# ---------------------------------------------------------------------------
# Prompt drift: the arms must differ in mechanism, not in task framing
# ---------------------------------------------------------------------------

def _module_string_const(path: Path, name: str) -> str | None:
    """Read a top-level `NAME = "..."` or `NAME = textwrap.dedent("...")` without importing."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
                and value.func.attr == "dedent" and value.args:
            value = value.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return textwrap.dedent(value.value)
    return None


def test_task_framing_matches_baseline() -> None:
    print("\ntask framing (confound guard)")
    bcp_baseline = _module_string_const(_REPO / "eval_direct_browsecomp_plus.py", "SYSTEM_PROMPT")
    check("baseline BCP prompt found", bcp_baseline is not None)
    if bcp_baseline:
        check("BCP task framing is verbatim from the direct arm",
              prompts_bcp.TASK_FRAMING.strip() in bcp_baseline,
              "prompts_bcp.TASK_FRAMING has drifted from eval_direct_browsecomp_plus")


def test_prompt_rendering() -> None:
    print("\nprompt rendering")
    full = prompts_bcp.build_system_prompt("who?", action_cap=3, step_cap=8,
                                           log_window=None, stateless=False)
    check("full log described", "full search history" in full)
    check("cross-turn hint present with history", "Cross-turn parsing" in full)
    check("the question is interpolated", "who?" in full)

    windowed = prompts_bcp.build_system_prompt("who?", action_cap=3, step_cap=8,
                                               log_window=0, stateless=False)
    check("window=0 described", "only the most recent search" in windowed)
    check("no cross-turn hint without history", "Cross-turn parsing" not in windowed)

    # The instructions must agree with what `EpisodeLog.publish` actually enforces. These
    # two checks exist because the first version of this port told the agent its
    # workspace persisted while deleting it every turn.
    stateless = prompts_bcp.build_system_prompt("who?", action_cap=3, step_cap=8,
                                                log_window=None, stateless=True)
    check("stateless workspace wording applied", "does NOT persist across calls" in stateless)
    check("stateless drops the prior-analyses claim", "prior analyses" not in stateless)
    check("the persistent arm still claims a persistent workspace",
          "persists across calls" in full and "does NOT persist" not in full)

    final = prompts_bcp.build_turn_prompt(is_first=False, log_window=None, used=8,
                                          step_cap=8, out_of_budget=True)
    check("the out-of-budget turn asks for an answer only",
          "No further searches will be executed" in final)


def test_server_gate() -> None:
    """A moved or briefly dead local server must be a pause, not a run of defaults.

    The failure modes: a turn that fails against a dead address is returned to the
    caller (who then burns the question's budget); a server that comes back on another
    node is not adopted; the sandbox allowlist keeps the old host; or the gate engages on
    a hosted channel where no address file exists.
    """
    print("\nserver gate (a preempted local server is a pause, not a default)")
    import tempfile as _tempfile

    root = Path(_tempfile.mkdtemp())
    addr = root / "server.addr"
    addr.write_text("http://node1:8010/v1\n")
    calls: list[str] = []
    alive = {"http://node1:8010/v1": False, "http://node2:8010/v1": True}

    class _T(CodexTurn):
        def __init__(self):
            self.base_url = "http://node1:8010/v1"

        def _run_turn(self, prompt, images=(), *, expect_artifact=True, timeout=None):
            calls.append(self.base_url)
            ok = alive.get(self.base_url, False)
            return {"artifact": "x" if ok else None, "message": "", "ok": ok,
                    "error": None if ok else "connection refused", "overflow": False}

    real_answers, real_sleep = CodexTurn._server_answers, codex_backend.time.sleep
    CodexTurn._server_answers = staticmethod(lambda url: alive.get(url, False))
    codex_backend.time.sleep = lambda s: addr.write_text("http://node2:8010/v1\n")   # the server moves
    os.environ["CODEX_BASE_URL_FILE"] = str(addr)
    try:
        t = _T()
        r = t.run("p")
        check("the failed turn is re-run instead of returned", r["ok"] and len(calls) == 2,
              str(calls))
        check("the new address is adopted", t.base_url == "http://node2:8010/v1", t.base_url)
        check("the first attempt went to the old address", calls[0] == "http://node1:8010/v1")

        # A failure while the server is healthy is the model's, and is returned as-is.
        calls.clear()
        alive["http://node2:8010/v1"] = True
        t2 = _T(); t2.base_url = "http://node2:8010/v1"
        t2._run_turn = lambda *a, **k: {"artifact": None, "message": "", "ok": False,
                                        "error": "bad json", "overflow": False}
        check("a model failure on a live server is not retried by the gate",
              not t2.run("p")["ok"])

        os.environ.pop("CODEX_BASE_URL_FILE")
        calls.clear()
        t3 = _T(); t3.base_url = None
        check("no address file, no gate", t3._address_file() is None)
    finally:
        os.environ.pop("CODEX_BASE_URL_FILE", None)
        CodexTurn._server_answers = real_answers
        codex_backend.time.sleep = real_sleep


def test_client_server_gate() -> None:
    """The direct arm's client sits behind the same gate as the agent turns.

    qwen38_1042 (2026-09-02): the server died, the agent arms paused, and the direct arm
    -- whose client had no gate -- burned each question's retries against the dead
    address and recorded 69 index-0 defaults in a row.
    """
    print("\nclient server gate (the direct arm pauses on a dead server too)")
    import tempfile as _tempfile
    from prolong_search.codex_client import CodexClient

    root = Path(_tempfile.mkdtemp())
    addr = root / "server.addr"
    addr.write_text("http://node1:8010/v1\n")
    calls: list[str] = []
    alive = {"http://node1:8010/v1": False, "http://node2:8010/v1": True}

    class _C(CodexClient):
        def __init__(self):
            self.base_url = "http://node1:8010/v1"

        def _generate_once(self, messages, images=None):
            calls.append(self.base_url)
            if not alive.get(self.base_url, False):
                raise RuntimeError("stream disconnected before completion")
            return "ANSWER: A"

    real_answers, real_sleep = CodexClient._server_answers, codex_backend.time.sleep
    CodexClient._server_answers = staticmethod(lambda url: alive.get(url, False))
    codex_backend.time.sleep = lambda s: addr.write_text("http://node2:8010/v1\n")
    os.environ["CODEX_BASE_URL_FILE"] = str(addr)
    try:
        c = _C()
        out = c.generate_text([{"role": "user", "content": "p"}])
        check("the failed call is re-run against the recovered server",
              out == "ANSWER: A" and calls == ["http://node1:8010/v1", "http://node2:8010/v1"],
              str(calls))
        check("the client adopted the new address", c.base_url == "http://node2:8010/v1")

        calls.clear()
        c2 = _C(); c2.base_url = "http://node2:8010/v1"
        def _model_failure(messages, images=None):
            calls.append(c2.base_url); raise RuntimeError("no message")
        c2._generate_once = _model_failure
        raised = False
        try:
            c2.generate_text([{"role": "user", "content": "p"}])
        except RuntimeError:
            raised = True
        check("a model failure on a live server is raised once, not retried by the gate",
              raised and len(calls) == 1, str(calls))

        env = {}
        c._sandbox_allow_env(env)
        check("the sandbox allowlist follows the adopted address",
              env.get("CODEX_SANDBOX_ALLOW") == "node2:8010", str(env))

        os.environ.pop("CODEX_BASE_URL_FILE")
        c3 = _C(); c3.base_url = None
        check("no address file, no gate", c3._address_file() is None)
    finally:
        os.environ.pop("CODEX_BASE_URL_FILE", None)
        CodexClient._server_answers = real_answers
        codex_backend.time.sleep = real_sleep


def test_rollout_scan_streams() -> None:
    """The audit must not hold a rollout in memory; rollouts reach a gigabyte.

    A rollout embeds every image the turn sent, so its size grows with the episode:
    prolong1042_v1 left 1.6-5.7 GB per shard, single files near 1 GB. Reading one whole
    (`read_text().splitlines()` holds it twice) is what killed shard C with
    OUT_OF_MEMORY *after* it had answered all 350 questions -- the most expensive
    possible moment to run out of memory. Counting is asserted alongside, because a
    scan that streams but miscounts would pass a memory test happily.
    """
    print("\nthe rollout scan streams")
    import tempfile as _tempfile
    from prolong_search import codex_backend as _cb

    view = ('{"type":"custom_tool_call","name":"view_image",'
            '"arguments":"{\\"path\\":\\"a.png\\"}"}')
    with _tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "rollout.jsonl"
        f.write_text("\n".join([view, '{"type":"message"}'] * 3) + "\n", encoding="utf-8")
        expected = _cb.scan_rollout(f)

        # Prove it is streamed rather than slurped: with read_text unavailable the scan
        # must still produce the same counts.
        real = Path.read_text
        Path.read_text = lambda self, *a, **k: (_ for _ in ()).throw(
            AssertionError("scan_rollout read the whole rollout into memory"))
        try:
            streamed = _cb.scan_rollout(f)
        finally:
            Path.read_text = real
        check("the scan does not slurp the file", streamed == expected, str(streamed))
        check("view_image calls are counted", streamed["view_image_calls"] == 3,
              str(streamed))
        check("a missing rollout is not an error",
              _cb.scan_rollout(Path(tmp) / "nope.jsonl")
              == {"view_image_calls": 0, "image_attach_failures": 0, "compactions": 0})

        # The tripwire's real source. The per-turn event stream does not carry the
        # event, so a rollout-blind count reads 0 on a run that compacted 25 times --
        # which is how prolong1042_v1 and every campaign before it published
        # `compactions: 0`. Each compaction writes ONE `"type":"compacted"` record and
        # one paired `ContextCompaction` item; counting both would double the figure.
        comp = Path(tmp) / "compacted.jsonl"
        comp.write_text(
            '{"type":"compacted","payload":{"window_number":1}}\n'
            '{"type":"event_msg","payload":{"item":{"type":"ContextCompaction"}}}\n'
            '{"type":"message"}\n', encoding="utf-8")
        got = _cb.scan_rollout(comp)
        check("a compaction in the rollout is counted", got["compactions"] == 1, str(got))
        check("the paired ContextCompaction item is not double-counted",
              got["compactions"] == 1, str(got))


def main() -> int:
    print("prolong_search selftest")
    test_overflow_recognition()
    test_thinking_invariant()
    test_overflow_classifier()
    test_merge_stats()
    test_search_plan()
    test_windowed_copy()
    test_publish_binds()
    test_stateless_plan()
    test_append_lines()
    test_prepare_workspace()
    test_codex_home_isolation()
    test_session_lifecycle()
    test_resume()
    test_timeout_salvage()
    test_per_call_timeout()
    test_auto_compact_policy()
    test_prepare_workspace_is_absolute()
    test_safe_flags_on_every_codex_call()
    test_request_stats_flags_violations()
    test_expected_tool_surface_is_the_whitelist()
    test_task_framing_matches_baseline()
    test_prompt_rendering()
    test_server_gate()
    test_client_server_gate()
    test_rollout_scan_streams()
    print()
    if _failures:
        print(f"{len(_failures)} FAILED: " + ", ".join(_failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
