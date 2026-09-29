"""Offline assertions for the world-model arm. No model, no GPU, no network.

    python -m worldmodel_search.selftest

Mirrors `prolong_search.selftest` in purpose: the parts of this arm that can be wrong
*silently* are checked here. A discipline rule that never fires, a view cap that does
not bind, an ops file that is read twice, or a prompt that has drifted from the
baseline all produce a number that looks fine and means something else.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from worldmodel_search.discipline import (                               # noqa: E402
    ACTIVE_CEILING, REVERTED_CONFIDENCE, SINGLE_SOURCE_CEILING, TEST_BUDGET_QUESTIONS,
    UNCITED_CEILING, UNVERIFIED_MARK, Discipline,
)
from worldmodel_search.hypotheses import (                               # noqa: E402
    MAX_OBSERVATION_IN_PROMPT, MAX_STRATEGY_IN_PROMPT, CycleError, HypothesisGraph,
)
from worldmodel_search.memory import WorldModelWorkspace                 # noqa: E402
from worldmodel_search.ops import apply_ops, read_ops                    # noqa: E402

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  --  {detail}" if detail else ""))
        _failures.append(name)


# ---------------------------------------------------------------------------
# The graph: unbounded store, bounded view
# ---------------------------------------------------------------------------

def test_graph() -> None:
    print("\nbelief graph")
    g = HypothesisGraph()
    g.add_or_update(id="d1", statement="LC3 puncta indicate autophagosomes",
                    confidence=0.6, kind="domain", step=1)
    g.add_or_update(id="d1", statement="LC3 puncta indicate autophagosomes",
                    confidence=0.6, kind="domain", step=5)
    check("a no-op update is counted and does not refresh",
          g.noop_updates == 1 and g.nodes["d1"].updated_step == 1)
    g.add_or_update(id="d1", confidence=0.8, step=6)
    check("a real change refreshes", g.nodes["d1"].updated_step == 6)
    g.add_or_update(id="d1", evidence=["Q3: puncta seen"], step=9)
    check("evidence alone does not refresh",
          g.nodes["d1"].updated_step == 6 and g.nodes["d1"].evidence == ["Q3: puncta seen"])
    g.add_or_update(id="d1", status="locked", step=10)
    check("an unknown status is dropped", g.nodes["d1"].status == "active")

    g.add_dependency("d2", "d1", step=2)
    try:
        g.add_dependency("d1", "d2", step=3)
        check("a cycle is rejected", False)
    except CycleError:
        check("a cycle is rejected", True)

    for i in range(30):
        g.add_or_update(id=f"h{i}", statement=f"claim {i}", kind="domain", step=i)
    check("the store is unbounded (the point of the arm)", len(g.nodes) > 16)
    view = g.to_prompt_summary(max_items=12)
    check("the view is bounded", view.count("\n- [") + view.startswith("- [") <= 12)
    check("the view names what it hides", "more hypotheses not shown" in view)

    g2 = HypothesisGraph()
    g2.add_or_update(id="s1", statement="perception: describe before reading choices",
                     kind="strategy", step=50)
    for i in range(8):
        g2.add_or_update(id=f"o{i}", statement=f"Q{i} image shows X", kind="observation",
                         confidence=0.5, step=100 + i)
    view2 = g2.to_prompt_summary(max_items=12)
    check("strategies render first", view2.splitlines()[0].startswith("- [s1]"))
    check("observations are capped in the view",
          view2.count("(observation") == MAX_OBSERVATION_IN_PROMPT, view2)

    g3 = HypothesisGraph()
    for i in range(12):
        g3.add_or_update(id=f"s{i}", statement=f"strategy {i}", kind="strategy", step=i)
    g3.add_or_update(id="dom", statement="a domain rule learned late", kind="domain",
                     confidence=0.9, step=90)
    view3 = g3.to_prompt_summary(max_items=12)
    check("strategies cannot buy the whole view",
          view3.count("(strategy") == MAX_STRATEGY_IN_PROMPT, view3)
    check("the newest strategy displaces the oldest",
          "[s11]" in view3 and "[s0]" not in view3, view3)
    check("a late non-strategy node stays visible", "[dom]" in view3, view3)
    g3.add_or_update(id="s2", confidence=0.9, step=95)
    check("a strategy updated late re-enters the view",
          "[s2]" in g3.to_prompt_summary(max_items=12))

    with tempfile.TemporaryDirectory() as tmp:
        g.save(Path(tmp) / "graph.json")
        loaded = HypothesisGraph.load(Path(tmp) / "graph.json")
        check("save/load round-trips",
              loaded.nodes.keys() == g.nodes.keys()
              and loaded.nodes["d1"].evidence == g.nodes["d1"].evidence)
        g.write_markdown(Path(tmp) / "hyp")
        check("the projection is greppable",
              "autophagosomes" in (Path(tmp) / "hyp" / "d1.md").read_text())


# ---------------------------------------------------------------------------
# The discipline: structural rules that must bind
# ---------------------------------------------------------------------------

def test_discipline() -> None:
    print("\ndiscipline")
    g = HypothesisGraph()
    d = Discipline(g)

    g.add_or_update(id="a1", statement="the answer to Q4 is B because of the cristae",
                    confidence=0.95, status="confirmed", kind="answer",
                    evidence=["Q4: dense parallel membranes"], step=4)
    d.enforce()
    n = g.nodes["a1"]
    check("a one-source confirmation is reverted",
          n.status == "active" and n.confidence == REVERTED_CONFIDENCE)
    check("the statement is marked, not just the status",
          n.statement.startswith(UNVERIFIED_MARK))
    check("the reversion is counted", d.counters["confirm_reverted"] == 1)

    g.add_or_update(id="a1", evidence=["Q9: same morphology, same call"],
                    status="confirmed", step=9)
    d.enforce()
    check("two distinct questions let a confirmation stand",
          g.nodes["a1"].status == "confirmed"
          and not g.nodes["a1"].statement.startswith(UNVERIFIED_MARK))
    g.add_or_update(id="a1", confidence=0.95, step=10)
    d.enforce()
    check("a confirmed node keeps headroom above the band",
          g.nodes["a1"].status == "confirmed" and g.nodes["a1"].confidence == 0.95)

    g.add_or_update(id="d9", statement="all confocal here is airyscan",
                    confidence=0.99, kind="domain", step=5)
    g.add_or_update(id="d10", statement="the run's EM is cryo", confidence=0.99,
                    kind="domain", evidence=["Q3: grid metadata"], step=5)
    g.add_or_update(id="d11", statement="the stain is H&E throughout",
                    confidence=0.99, kind="domain",
                    evidence=["Q3: pink-purple palette", "Q7: same palette"], step=7)
    d.enforce()
    check("an uncited belief is priced at the guess tier",
          g.nodes["d9"].confidence == UNCITED_CEILING)
    check("one independent source buys one tier up",
          g.nodes["d10"].confidence == SINGLE_SOURCE_CEILING)
    check("two sources buy the top of the band, not past it",
          g.nodes["d11"].confidence == ACTIVE_CEILING
          and g.nodes["d11"].status == "active")

    g.add_or_update(id="t1", statement="hypothesis_gen rewards mechanism words",
                    confidence=0.5, kind="strategy", step=0)
    note = None
    for q in range(TEST_BUDGET_QUESTIONS + 1):
        note = d.track_testing("t1", q)
    check("the test budget retires a belief that does not move",
          g.nodes["t1"].status == "stale" and note is not None
          and d.counters["stale_by_budget"] == 1)

    g.add_or_update(id="a2", statement="Q12: committed C, spindle poles",
                    confidence=0.5, kind="answer", evidence=["Q12: two asters"], step=12)
    touched = d.apply_outcome(12, True, step=13)
    check("a graded outcome moves the answer node it names",
          touched == ["a2"] and abs(g.nodes["a2"].confidence - 0.75) < 1e-9)
    check("the outcome lands as evidence, not as a status",
          any("graded correct" in e for e in g.nodes["a2"].evidence)
          and g.nodes["a2"].status == "active")
    d.apply_outcome(99, False, step=14)
    check("an outcome with no matching node touches nothing",
          d.counters["outcomes_applied"] == 1)


# ---------------------------------------------------------------------------
# Frame identity: independence is specimens, not question numbers
# ---------------------------------------------------------------------------

def test_frame_identity() -> None:
    print("\nframe identity")
    g = HypothesisGraph()
    d = Discipline(g)
    d.frame_ids = {4: frozenset({"aaa"}), 9: frozenset({"aaa"}),
                   12: frozenset({"bbb"}), 15: frozenset(), 16: frozenset()}

    g.add_or_update(id="same", statement="the cristae here are dense",
                    confidence=0.9, status="confirmed", kind="domain",
                    evidence=["Q4: dense membranes", "Q9: still dense"], step=9)
    d.enforce()
    check("two questions over the same frames are one source",
          g.nodes["same"].status == "active"
          and g.nodes["same"].statement.startswith(UNVERIFIED_MARK))

    g.add_or_update(id="cross", statement="the run's confocal is airyscan",
                    confidence=0.9, status="confirmed", kind="domain",
                    evidence=["Q4: metadata", "Q12: second specimen agrees"], step=12)
    d.enforce()
    check("distinct frame sets keep a confirmation",
          g.nodes["cross"].status == "confirmed")

    g.add_or_update(id="textonly", statement="stems repeat the specimen history",
                    confidence=0.9, status="confirmed", kind="strategy",
                    evidence=["Q15: no image", "Q16: no image either"], step=16)
    d.enforce()
    check("image-less questions count as their own sources",
          g.nodes["textonly"].status == "confirmed")

    d2 = Discipline(HypothesisGraph())
    d2.graph.add_or_update(id="legacy", statement="x", confidence=0.9,
                           status="confirmed", kind="domain",
                           evidence=["Q1: a", "Q2: b"], step=2)
    d2.enforce()
    check("unfed frame_ids degrade to distinct-questions-only",
          d2.graph.nodes["legacy"].status == "confirmed")

    # The retrieval face of the same identity: what the act prompt gets told.
    check("seen-before finds the earlier question over the same pixels",
          d.seen_before(9) == [(4, True)])
    d.frame_ids[20] = frozenset({"aaa", "bbb"})
    check("an overlap is reported as overlap, not identity",
          d.seen_before(20) == [(4, False), (9, False), (12, False)])
    check("seen-before never looks forward or at itself", d.seen_before(4) == [])
    check("a text-only question has no seen-before", d.seen_before(15) == [])


# ---------------------------------------------------------------------------
# The workspace: seeds, truncation, integrity, the outcome channel
# ---------------------------------------------------------------------------

def test_workspace() -> None:
    print("\nworkspace")
    with tempfile.TemporaryDirectory() as tmp:
        ws = WorldModelWorkspace(Path(tmp) / "w", outcome_feedback=False)
        ws.seed_world_model()
        docs = sorted(p.name for p in ws.world_model_dir.glob("*.md"))
        check("the five documents are seeded (upstream's taxonomy)",
              docs == ["causal.md", "dynamics.md", "procedural.md",
                       "semantic.md", "spatial.md"], str(docs))
        check("no events channel without feedback", not ws.events_path.exists())

        zoom = ws.root / "tools" / "zoom.py"
        check("the zoom tool is written and executable",
              zoom.exists() and os.access(zoom, os.X_OK))
        check("the zoom tool does not pin the runner's interpreter",
              zoom.read_text().startswith("#!/usr/bin/env python"))

        (ws.world_model_dir / "semantic.md").write_text("# S\n" + "x" * 5000)
        summary = ws.world_model_summary(per_doc_chars=100)
        check("per-doc truncation binds and names the file",
              "[truncated; read semantic.md in full]" in summary)
        check("truncating one document does not evict another",
              "procedural" in summary.lower())

        stamps = ws.doc_stamps()
        check("no rewrite -> zero docs touched", ws.docs_touched(stamps) == 0)
        (ws.world_model_dir / "causal.md").write_text("# C\nnew content")
        check("a rewrite is seen by the tripwire", ws.docs_touched(stamps) == 1)

        (ws.root / "logs.txt").write_text("Question 0\nQuestion 1\n")
        (ws.root / "AGENTS.md").write_text("system prompt")
        before = ws.snapshot_harness_files()
        (ws.root / "logs.txt").write_text("Question 0\n")
        bad = ws.assert_harness_files_intact(before)
        check("a shrunk harness file is reported", bad and "logs.txt" in bad[0])

        ws.append_outcome(0, "perception", True)
        check("append_outcome is a no-op without feedback", not ws.events_path.exists())

        fb = WorldModelWorkspace(Path(tmp) / "f", outcome_feedback=True)
        fb.append_outcome(0, "perception", True)
        fb.append_outcome(1, "hypothesis_gen", False)
        lines = fb.events_path.read_text().strip().splitlines()
        check("the feedback channel records outcomes",
              len(lines) == 2 and '"outcome":"incorrect"' in lines[1])


# ---------------------------------------------------------------------------
# The ops channel: contained failures, consumed files
# ---------------------------------------------------------------------------

def test_ops() -> None:
    print("\nops channel")
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        g = HypothesisGraph()
        d = Discipline(g)

        (ws / "hypotheses_ops.json").write_text("{not json")
        out = read_ops(ws)
        check("a malformed file returns its error", out["error"] is not None)
        check("the file is consumed either way", not (ws / "hypotheses_ops.json").exists())

        (ws / "hypotheses_ops.json").write_text(
            '{"hypotheses": [{"id": "h1", "statement": "s", "kind": "domain",'
            ' "confidence": 0.6, "evidence": "Q1: seen"},'
            ' {"no_id": true},'
            ' {"id": "h2", "statement": "t", "depends_on": ["h1"]}],'
            ' "testing": "h2"}')
        out = read_ops(ws)
        touched, notes = apply_ops(g, d, out["ops"], step=3)
        check("good ops apply around a bad one",
              touched == ["h1", "h2"] and g.nodes["h1"].evidence == ["Q1: seen"]
              and "h1" in g.nodes["h2"].depends_on)
        check("the ops file is consumed", not (ws / "hypotheses_ops.json").exists())

        (ws / "hypotheses_ops.json").write_text(
            '{"hypotheses": [{"id": "h1", "depends_on": ["h2"]}]}')
        _, notes = apply_ops(g, d, read_ops(ws)["ops"], step=4)
        check("a cycle via ops is rejected with a note",
              any("dependency rejected" in n for n in notes))

        _, _ = apply_ops(g, d, None, step=5)
        check("the warden runs even with no ops", True)  # reaching here is the check


def main() -> int:
    print("worldmodel_search selftest")
    test_graph()
    test_discipline()
    test_frame_identity()
    test_workspace()
    test_ops()
    print()
    if _failures:
        print(f"{len(_failures)} FAILED: " + ", ".join(_failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
