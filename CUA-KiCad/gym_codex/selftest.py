"""Offline checks for gym_codex: the direct arm is unchanged by the actions split, and
the two memory arms drive the turn protocol correctly against a fake `codex`.

    <cua-lite>/.venv/bin/python gym_codex/selftest.py

No model, no container. The fake codex is a python script that plays a per-call
script of (actions.json contents, closing message) from a file, so the memory arms'
whole path -- workspace, log sections, artifact, parse, feedback, induction cadence,
frame identity -- runs through the real CodexTurn.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gym_codex import actions as A                     # noqa: E402
from gym_codex import codex_gui_agent as D             # noqa: E402
from gym_codex import memory_agents as M               # noqa: E402
from gym_codex import backend_errors as E                # noqa: E402
from gym_codex import prompts_prolong, prompts_worldmodel  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


# The direct arm's rendered system prompt before the split, per env id. A change here
# is a change to the running campaign's arm and must be deliberate.
PROMPT_SHA = {
    "cua.bench.local.kicad": "982b6d3bb33bba4ed99a5b70407538d554a6f4c2f76b71b3d7e28fd3a8cd60c8",
    "lite.osworld": "d542f3e20d9ab71672f233c21d1da41026965f82fd7f1feb0681f7f57e49af1a",
    "": "67908f947a2e4e4ffe585795342262f3ce822ada878f1970d7e75167c6a85c87",
}


def test_direct_unchanged() -> None:
    print("\ndirect arm unchanged by the split")
    for env, sha in PROMPT_SHA.items():
        rendered = D.SYSTEM_PROMPT.replace("{desktop_notes}", D.DESKTOP_NOTES.get(env, ""))
        check(f"system prompt byte-identical ({env or 'no env'})",
              hashlib.sha256(rendered.encode()).hexdigest() == sha)

    seq = [0]

    def tc(name, args):
        seq[0] += 1
        return {"id": f"call_{seq[0]:04d}", "type": "function",
                "function": {"name": name, "arguments": args}}

    pb = A.parse_batch(A.last_json_block('think\n```json\n{"actions": [{"action": "click", '
                                         '"coordinate": [1200, -5], "button": "left"}, '
                                         '{"action": "nope"}, {"action": "click"}]}\n```'), tc)
    check("coordinates clamped to [0,1000]",
          pb.calls[0]["function"]["arguments"]["actions"][0]["coordinate"] == [1000, 0])
    check("unknown action and click-without-coordinate dropped with feedback",
          len(pb.calls[0]["function"]["arguments"]["actions"]) == 1
          and "unknown action" in (pb.feedback or "") and "click without coordinate" in pb.feedback)
    check("log line describes the executed batch", pb.log_line == "click(1000,0)")
    pb = A.parse_batch({"actions": []}, tc)
    check("empty actions is terminate(success)", pb.done and pb.log_line.startswith("terminate(success"))
    pb = A.parse_batch({"terminate": {"status": "failure", "reason": "x"}}, tc)
    check("terminate failure carries its reason",
          pb.calls[0]["function"]["arguments"] == {"status": "failure", "reason": "x"})
    pb = A.parse_batch(None, tc)
    check("no JSON is a no-op with the direct arm's feedback",
          not pb.calls and pb.feedback == A.NO_JSON_FEEDBACK)
    pb = A.parse_batch({"foo": 1}, tc)
    check("JSON without actions is a no-op", not pb.calls and "no \"actions\"" in pb.feedback)
    pb = A.parse_batch({"actions": [{"action": "wait", "duration": 1}] * 9}, tc)
    check("batches capped at MAX_BATCH",
          len(pb.calls[0]["function"]["arguments"]["actions"]) == A.MAX_BATCH)

    ag = D.CodexGuiAgent.__new__(D.CodexGuiAgent)
    ag.action_log, ag._pending_feedback, ag._call_seq = [], None, 0
    calls, done = ag._parse("no json here")
    check("CodexGuiAgent._parse routes through parse_batch",
          not calls and ag._pending_feedback == A.NO_JSON_FEEDBACK
          and ag.action_log == ["(unparseable reply; no action executed)"])


# -- a fake codex -------------------------------------------------------------------

FAKE_CODEX = r'''#!/usr/bin/env python3
"""Plays FAKE_CODEX_SCRIPT (a JSONL of {"artifact": ..., "message": ..., "error": ...})
one line per call, in cwd; records every invocation to FAKE_CODEX_CALLS."""
import json, os, sys
argv = sys.argv[1:]
prompt = sys.stdin.read()
out = argv[argv.index("-o") + 1]
images = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
resume = "resume" in argv
script = os.environ["FAKE_CODEX_SCRIPT"]
lines = open(script).read().splitlines()
idx_path = script + ".idx"
import fcntl
with open(idx_path, "a+") as lf:          # the parallel induction pass runs 5 at once
    fcntl.flock(lf, fcntl.LOCK_EX)
    lf.seek(0)
    raw = lf.read().strip()
    i = int(raw) if raw else 0
    lf.seek(0)
    lf.truncate()
    lf.write(str(i + 1))
    lf.flush()
step = json.loads(lines[min(i, len(lines) - 1)]) if lines else {}
with open(os.environ["FAKE_CODEX_CALLS"], "a") as f:
    f.write(json.dumps({"i": i, "cwd": os.getcwd(), "images": images, "resume": resume,
                        "prompt": prompt, "artifact_written": step.get("artifact") is not None}) + "\n")
print(json.dumps({"type": "thread.started", "thread_id": "0f0f0f0f-0000-4000-8000-%012d" % (i // 1000)}))
if step.get("error"):
    print(json.dumps({"type": "error", "message": step["error"]}))
    sys.exit(1)
for rel, text in (step.get("files") or {}).items():
    os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
    open(rel, "w").write(text)
if step.get("artifact") is not None:
    open("actions.json", "w").write(step["artifact"] if isinstance(step["artifact"], str)
                                    else json.dumps(step["artifact"]))
open(out, "w").write(step.get("message", ""))
print(json.dumps({"type": "turn.completed"}))
'''


class Fake:
    def __init__(self, tmp: Path, script: list[dict]) -> None:
        self.bin = tmp / "codex"
        self.bin.write_text(FAKE_CODEX)
        self.bin.chmod(0o755)
        self.script = tmp / "script.jsonl"
        self.script.write_text("\n".join(json.dumps(s) for s in script) + "\n")
        self.calls_path = tmp / "calls.jsonl"
        self.calls_path.write_text("")
        os.environ["CODEX_BIN"] = str(self.bin)
        os.environ["FAKE_CODEX_SCRIPT"] = str(self.script)
        os.environ["FAKE_CODEX_CALLS"] = str(self.calls_path)
        os.environ["CODEX_HOME"] = str(tmp / "codexhome")

    def calls(self) -> list[dict]:
        return [json.loads(l) for l in self.calls_path.read_text().splitlines()]


def _png(n: int) -> bytes:
    return b"\x89PNG-fake-" + bytes([n])


def _drive(agent, task: str, screens: list[bytes], max_steps: int = 10,
           env_errors: dict[int, str] | None = None) -> list[tuple]:
    """A miniature run_eval loop: predict, then feed env feedback, until done."""
    out = []
    for step_idx, png in enumerate(screens):
        reply, calls, done = agent.predict(task, png, step_idx, max_steps)
        out.append((reply, calls, done))
        if env_errors and step_idx in env_errors:
            agent.add_feedback(f"env error: {env_errors[step_idx]}")
        if done:
            break
    return out


def test_prolong() -> None:
    print("\nprolong arm on a fake codex")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        act = {"actions": [{"action": "click", "coordinate": [500, 500]}]}
        fake = Fake(tmp, [
            {"artifact": act, "message": "briefing one\n[PLAN]\nclick the canvas"},
            {"artifact": {"actions": [{"action": "bogus"}]}, "message": "[PLAN]\np2"},
            {"artifact": "not json{", "message": "oops"},              # 3 attempts...
            {"artifact": "not json{", "message": "oops"},
            {"artifact": "not json{", "message": "oops"},
            {"artifact": {"terminate": {"status": "success"}}, "message": "[PLAN]\ndone"},
        ])
        agent = M.ProlongGuiAgent(workspace=tmp / "t1" / "workspace", model="m", effort="low",
                                  max_steps=10, transcript_dir=tmp / "t1" / "codex",
                                  analyzer_retries=3)
        res = _drive(agent, "Add a resistor R1", [_png(1), _png(2), _png(2), _png(3)],
                     env_errors={0: "boom"})
        calls = fake.calls()
        check("turn 1 executed the click",
              res[0][1][0]["function"]["arguments"]["actions"] == [{"action": "click", "coordinate": [500, 500]}])
        check("turn 2's invalid action became a no-op with feedback",
              res[1][1] == [] and "unknown action" in (agent._pending_feedback or "")
              or "unknown action" in (tmp / "t1" / "workspace" / "logs.txt").read_text())
        check("turn 3 spent three attempts on unparseable artifacts, then no-op",
              len(calls) == 6 and res[2][1] == [] and agent.parse_failures == 1)
        check("turn 4 terminated", res[3][2] and res[3][1][0]["function"]["name"] == "terminate")
        log = (tmp / "t1" / "workspace" / "logs.txt").read_text()
        check("initial section carries the task", "[TASK] Add a resistor R1" in log)
        check("one section per turn (plus the header)", log.count("\nTurn ") == 5, str(log.count("\nTurn ")))
        check("env feedback reached turn 2's section", "[FEEDBACK] env error: boom" in log)
        check("parser feedback reached turn 3's section",
              re.search(r"Turn 3 \| Step 3/10\n\n\[FEEDBACK\] .*unknown action", log) is not None)
        check("plan and actions appended to the turn's own section",
              "[SCREEN] frames/step_0001.png\n[PLAN]\nbriefing one\nclick the canvas\n\n"
              "[ACTIONS] click(500,500)" in log)
        check("screens saved and named", "[SCREEN] frames/step_0001.png" in log
              and (tmp / "t1" / "workspace" / "frames" / "step_0004.png").read_bytes() == _png(3))
        check("the current screenshot is attached to every call, as an absolute path",
              all(len(c["images"]) == 1 and c["images"][0].startswith("/") for c in calls))
        check("the thread is resumed across turns", calls[1]["resume"] and calls[5]["resume"])
        check("the retry nudge is added on attempt 2+", M.RETRY_NUDGE in calls[3]["prompt"]
              and M.RETRY_NUDGE not in calls[2]["prompt"])
        check("AGENTS.md carries the action reference",
              A.ACTION_REFERENCE in (tmp / "t1" / "workspace" / "AGENTS.md").read_text())
        check("the failed turn's note attributes it to the model",
              "produced no usable ./actions.json" in log)
        aud = agent.audit()
        check("audit reports the arm and turns", aud["arm"] == "prolong" and aud["turns"] == 4
              and aud["no_op_turns"] == 1)
        p = prompts_prolong.build_turn_prompt(False, turns=190, step=191, max_steps=200)
        check("budget note appears in the last quarter", "10 steps remain" in p)
        check("and not before", "remain" not in prompts_prolong.build_turn_prompt(False, 5, 6, 200))


def test_worldmodel() -> None:
    print("\nworldmodel arm on a fake codex")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        act = {"actions": [{"action": "key", "keys": ["a"]}]}
        ops = json.dumps({"hypotheses": [
            {"id": "h1", "statement": "'a' opens the symbol chooser", "confidence": 0.95,
             "status": "confirmed", "kind": "domain", "evidence": ["T1: saw it", "T2: saw it"]}],
            "testing": "h1"})
        script = [
            {"artifact": act, "message": "[PLAN]\np1", "files": {"hypotheses_ops.json": ops}},
            {"artifact": act, "message": "[PLAN]\np2"},
            # induction pass before turn 3 (induction_every=2): 5 docs + ops
            {"message": "rewrote spatial", "files": {"world_model/spatial.md": "# Spatial\nMARKER_SPATIAL"}},
            {"message": "rewrote semantic", "files": {"world_model/semantic.md": "# Semantic\nx"}},
            {"message": "rewrote dynamics", "files": {"world_model/dynamics.md": "# Dynamics\nx"}},
            {"message": "nothing"},                                  # causal left silent
            {"message": "rewrote procedural", "files": {"world_model/procedural.md": "# P\n## Goal check\nx"}},
            {"message": "settled beliefs"},
            {"artifact": act, "message": "[PLAN]\np3"},
            {"artifact": {"terminate": {"status": "success"}}, "message": "[PLAN]\ndone"},
        ]
        fake = Fake(tmp, script)
        agent = M.WorldModelGuiAgent(workspace=tmp / "t2" / "workspace", model="m", effort="low",
                                     max_steps=10, transcript_dir=tmp / "t2" / "codex",
                                     induction_every=2)
        res = _drive(agent, "Wire R1 to C1", [_png(1), _png(1), _png(2), _png(3)])
        calls = fake.calls()
        ws = tmp / "t2" / "workspace"
        check("four act turns plus one six-call induction pass", len(calls) == 10, str(len(calls)))
        check("every call is a fresh conversation", not any(c["resume"] for c in calls))
        check("induction calls carry no screenshot", all(not c["images"] for c in calls[2:8]))
        check("induction is ordered spatial..procedural then ops",
              all(f"world_model/{d}.md" in calls[2 + i]["prompt"]
                  for i, d in enumerate(prompts_worldmodel.INDUCTION_DOC_ORDER))
              and "settle the" in calls[7]["prompt"])
        check("the silent causal call is counted", agent.induction_calls_silent == 1
              and agent.induction_turns == 1 and agent.induction_silent == 0)
        check("the recompiled model reaches the next act prompt", "MARKER_SPATIAL" in calls[8]["prompt"])
        check("turn 2 saw the seen-before fact for its identical screen",
              "pixel-identical to the one at T1" in calls[1]["prompt"])
        check("turn 3 (a new screen) did not", "pixel-identical" not in calls[8]["prompt"])
        n = agent.graph.nodes["h1"]
        check("the discipline reverted a self-confirmed node (T1, T2 share a screen)",
              n.status == "active" and n.confidence <= 0.8 and "unverified" in n.statement,
              f"{n.status} {n.confidence}")
        check("the T<n> unit reaches the harness notices",
              "two distinct turns" in agent.discipline.summary())
        log = ws.joinpath("logs.txt").read_text()
        check("the induction section is in the log and the open turn re-headed after it",
              "[INDUCTION] 4 document(s) rewritten; nothing landed for: causal" in log
              and "Turn 3 | Step 3/10 (continued after induction)" in log)
        check("[TASK] reaches the first act prompt", "[TASK] Wire R1 to C1" in calls[0]["prompt"])
        check("the graph is persisted", (ws / "hypotheses" / "graph.json").exists()
              and (ws / "hypotheses" / "h1.md").exists())
        check("the world model docs are the KiCad set",
              "netlist" in (ws / "world_model" / "causal.md").read_text())
        check("terminate parsed", res[-1][2])
        aud = agent.audit()
        check("audit carries induction and discipline counters",
              aud["induction_turns"] == 1 and aud["discipline"]["confirm_reverted"] == 1
              and aud["hypotheses"]["n"] == 1)


def test_worldmodel_v2() -> None:
    print("\nworldmodel v2 levers: session reuse, parallel induction, verify, campaign scope")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        camp = tmp / "campaign_world_model"
        act = {"actions": [{"action": "key", "keys": ["a"]}]}
        term = {"terminate": {"status": "success"}}
        docs = lambda tag: [                                  # 5 parallel doc calls
            {"message": "s", "files": {"world_model/spatial.md": f"# Spatial\nMARKER_{tag}_SPATIAL"}},
            {"message": "s", "files": {"world_model/semantic.md": "# Semantic\nx"}},
            {"message": "s", "files": {"world_model/dynamics.md": "# Dynamics\nx"}},
            {"message": "s", "files": {"world_model/causal.md": "# Causal\nx"}},
            {"message": "s", "files": {"world_model/procedural.md":
                                       f"# P\n## Recipes\nMARKER_{tag}_RECIPE\n\n## Goal check\nPOSTMORTEM_{tag}"}},
        ]
        script = [
            {"artifact": act, "message": "[PLAN]\np1"},
            {"artifact": act, "message": "[PLAN]\np2"},
            *docs("MID"),                                     # pass 1 before T3
            {"message": "settled"},                           # ops call
            {"artifact": term, "message": "[PLAN]\ndone?"},   # T3: held for verification
            {"artifact": {"actions": [{"action": "key", "keys": ["ctrl+s"]}]},
             "message": "unsaved; saving"},                    # the verification call
            {"artifact": term, "message": "[PLAN]\ndone"},    # T4: passes through
            *docs("FINAL"),                                   # final pass, no ops call
        ]
        fake = Fake(tmp, script)
        mk = lambda name: M.WorldModelGuiAgent(
            workspace=tmp / name / "workspace", model="m", effort="low", max_steps=10,
            transcript_dir=tmp / name / "codex", induction_every=2, session_turns=3,
            parallel_induction=True, campaign_dir=camp, final_induction=True,
            final_induction_min_turns=1, verify_before_terminate=True, task_id=name)
        agent = mk("tA")
        res = _drive(agent, "Wire R1 to C1", [_png(1), _png(2), _png(3), _png(3)])
        agent.finish(1.0, None)
        calls = fake.calls()
        ind = [c for c in calls if "Rewrite `world_model/" in c["prompt"]]   # doc calls
        check("2 acts + (5 docs + ops) + act + verify + act + 5 final docs = 16 calls",
              len(calls) == 16, str(len(calls)))
        check("the thread is resumed on the second act turn", calls[1]["resume"])
        check("no induction document call resumes a thread", not any(c["resume"] for c in ind))
        check("the act turn after the pass cold-starts", not calls[8]["resume"])
        check("the verification call is on the held turn's thread and says so",
              calls[9]["resume"] and "Verification call" in calls[9]["prompt"])
        check("the held terminate became the verification call's batch",
              res[2][1][0]["function"]["name"] == "computer" and not res[2][2]
              and (agent.verify_outcome or "").startswith("continued"))
        check("the second terminate passes through", res[3][2])
        check("mid-episode docs reached the act prompt after the pass",
              "MARKER_MID_SPATIAL" in calls[8]["prompt"])
        final = [c for c in ind if "The episode has ENDED" in c["prompt"]]
        check("the final pass is 5 document calls, no ops call, numbered of 5",
              len(final) == 5 and all("of 5 in this pass" in c["prompt"] for c in final)
              and agent.final_induction_ran)
        check("campaign-scope citations name this task",
              all("`task tA T<n>`" in c["prompt"] for c in ind))
        check("each document call has its own transcript dir",
              (tmp / "tA" / "codex" / "induction_spatial" / "turn_0002.events.jsonl").exists()
              or (tmp / "tA" / "codex" / "induction_spatial").is_dir())
        log = (tmp / "tA" / "workspace" / "logs.txt").read_text()
        check("both passes are in the log, the final one marked",
              log.count("[INDUCTION]") >= 2 and "after the episode ended" in log)
        check("the documents were published with a manifest and a history snapshot",
              "MARKER_FINAL_RECIPE" in (camp / "world_model" / "procedural.md").read_text()
              and json.loads((camp / "manifest.json").read_text())[0]["reward"] == 1.0
              and (camp / "history" / "00_tA" / "spatial.md").exists())
        aud = agent.audit()
        check("audit records the levers", aud["wm_scope"] == "campaign" and aud["wm_prior_tasks"] == 0
              and aud["wm_session_turns"] == 3 and aud["wm_parallel_induction"]
              and aud["induction_codex"] and aud["induction_codex"]["spatial"]["analyzer_turns"] == 2)

        # -- the next task inherits the documents, minus the post-mortem ----------
        (tmp / "second").mkdir(exist_ok=True)
        fake2 = Fake(tmp / "second", [
            {"artifact": term, "message": "[PLAN]\ntrivial"},
            {"artifact": term, "message": "checked"},
            *[{"message": "silent"}] * 5,
        ])
        agent2 = mk("tB")
        res2 = _drive(agent2, "Set R1 to 10k", [_png(5), _png(6)])
        agent2.finish(0.0, None)
        calls2 = fake2.calls()
        proc = (tmp / "tB" / "workspace" / "world_model" / "procedural.md").read_text()
        check("tB starts from tA's recipes with the post-mortem dropped",
              "MARKER_FINAL_RECIPE" in proc and "POSTMORTEM_FINAL" not in proc
              and "not yet evaluated" in proc)
        check("tB's first act prompt is the carried-over variant",
              "carry over from 1 earlier task(s)" in calls2[0]["prompt"])
        agents_md = (tmp / "tB" / "workspace" / "AGENTS.md").read_text()
        check("tB's system prompt carries the campaign and resumed-thread notes",
              "outlives the task" in agents_md and "1 earlier task(s)" in agents_md
              and "Conversations are short-lived" in agents_md)
        check("a verification that terminates ends the episode on the same turn",
              res2[0][2] and agent2.verify_outcome == "terminated" and len(res2) == 1)
        check("a silent final pass still publishes, and the manifest is in order",
              [m["task_id"] for m in json.loads((camp / "manifest.json").read_text())] == ["tA", "tB"]
              and agent2.audit()["wm_prior_tasks"] == 1 and agent2.induction_silent == 1)


def test_worldmodel_v1_defaults_unchanged() -> None:
    print("\nworldmodel v1 rendering unchanged by the v2 slots")
    sp = prompts_worldmodel.build_system_prompt(200)
    check("no scope note, fresh-call note, no stray blank lines",
          "outlives" not in sp and "Each call is a fresh conversation" in sp
          and "\n\n\n" not in sp)
    ip = prompts_worldmodel.build_induction_doc_prompt(doc="spatial", turns=25, step=26,
                                                       max_steps=200, per_doc_chars=1500)
    check("episode-scope induction prompt has neither scope nor ended notes",
          "Scope" not in ip and "ENDED" not in ip and "call 1 of 6" in ip and "\n\n\n" not in ip)


def test_backend_errors() -> None:
    print("\nbackend error classification (a declined call is not a failed method)")
    REFUSAL = ("This content was flagged for possible biological risk. If this seems "
               "wrong, try rephrasing your request.")
    check("a refusal is recognised", E.is_filter_refusal(REFUSAL))
    check("an ordinary failure is not", not E.is_filter_refusal("timeout"))
    check("a missing reason is not", not E.is_filter_refusal(None))
    SANDBOX = "codex_sandbox: egress proxy socket never appeared"
    check("a sandbox failure is bucketed as the sandbox's",
          E.default_reason_key(SANDBOX) == "sandbox")
    check("a sandbox failure is transient infrastructure, not the task's",
          E.is_transient_infra(SANDBOX) and not E.is_filter_refusal(SANDBOX))
    check("capacity is transient infrastructure too",
          E.is_transient_infra("Selected model is at capacity. Please try a different model."))
    check("a refusal is not transient infrastructure", not E.is_transient_infra(REFUSAL))
    check("an overflow is the arm's own", E.default_reason_key("context overflow: x") == "context overflow"
          and not E.is_transient_infra("context overflow: x"))
    check("a bare parse failure is 'other'", E.default_reason_key("no usable actions.json") == "other")

    def drive(errors: "list[str | None]", retries: int = 3) -> tuple[int, bool]:
        """Replay the arms' loop shape over a scripted sequence of failures."""
        attempt, budget, refusals = 0, retries, 0
        while attempt < budget:
            attempt += 1
            err = errors[attempt - 1] if attempt - 1 < len(errors) else None
            if err is None:
                return attempt, True                      # answered
            if E.is_filter_refusal(err) and refusals < E.FILTER_RETRIES:
                refusals += 1
                budget += 1
        return attempt, False

    n, ok = drive([REFUSAL] * 5 + [None])
    check("five refusals then an answer still lands", ok and n == 6, f"{n} {ok}")
    n, ok = drive(["timeout", "timeout", "timeout", "timeout"])
    check("real failures still stop at the normal budget", not ok and n == 3, str(n))
    n, ok = drive([REFUSAL, "timeout", "timeout", "timeout"])
    check("a refusal does not spend the budget for real failures",
          not ok and n == 4, str(n))
    n, ok = drive([REFUSAL] * 50)
    check("refusal retries are bounded, not unbounded",
          not ok and n == 3 + E.FILTER_RETRIES, str(n))


def test_infra_failure_raises() -> None:
    print("\ninfrastructure failures reach the driver")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cap = "Selected model is at capacity. Please try a different model."
        Fake(tmp, [{"error": cap}] * 12)
        M.backend_errors.CAPACITY_RETRIES, saved = 1, M.backend_errors.CAPACITY_RETRIES
        try:
            import time as _t
            _sleep, _t.sleep = _t.sleep, lambda s: None
            M.time.sleep = lambda s: None
            agent = M.ProlongGuiAgent(workspace=tmp / "t3" / "workspace", model="m", effort="low",
                                      max_steps=10, analyzer_retries=2)
            raised = None
            try:
                agent.predict("t", _png(1), 0, 10)
            except RuntimeError as exc:
                raised = str(exc)
            check("a capacity error after the arm's retries raises", raised is not None
                  and "at capacity" in raised, str(raised))
            check("the turn stays open for the driver's retry", agent._open is not None)
            log = (tmp / "t3" / "workspace" / "logs.txt").read_text()
            check("one section written, not two", log.count("Turn 1 |") == 1)
        finally:
            M.backend_errors.CAPACITY_RETRIES = saved
            M.time.sleep = _sleep


def main() -> int:
    test_direct_unchanged()
    test_prolong()
    test_worldmodel()
    test_worldmodel_v2()
    test_worldmodel_v1_defaults_unchanged()
    test_backend_errors()
    test_infra_failure_raises()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
