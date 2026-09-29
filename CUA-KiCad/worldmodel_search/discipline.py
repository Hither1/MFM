"""The rules the harness enforces on the belief graph, re-grounded for a question run.

Ported from `MCU-AgentBeats:mcu_worldmodel/discipline.py`, where every rule hung off a
ground-truth channel the environment provided for free: MineRL's own statistics, read by
a MilestoneLedger that never saw a model output. A question run has no such channel
while it runs -- the protocol, enforced by the evaluators, is that no arm sees gold
labels during a run -- so the rules that survive
are the *structural* ones, and the ledger-backed rule returns only under the explicit
`--outcome-feedback` variant.

What survives without any ground truth:

  the evidence rule    a node the model marks `confirmed` must cite at least two
                       independent sources: distinct questions whose frames are not
                       the same images. One question cannot confirm a claim minted
                       from that same question -- and neither can a second question
                       about the same pixels, which the first campaign showed is the
                       common case: a benchmark asks several questions per specimen, so
                       one misreading yields two "independent" confirmations unless
                       frame identity is checked. The harness keys independence on the
                       frames' content hashes (fed by the evaluator as it saves them);
                       a question with no images counts as its own source. This is the
                       same anti-self-confirmation stance as upstream's, checked
                       against the only objective records available -- the log's
                       question sections and the frame store -- instead of a milestone
                       ledger.
  the ceiling          confidence is priced by evidence structure, not the model's
                       mood: a node citing no question sits at or below 0.7, one
                       independent source buys 0.8, two or more buy 0.9, and only a
                       `confirmed` node may sit higher. Reserve 1.0 for things the
                       world has said. The flat 0.9 ceiling this replaces was measured
                       failing in g56low_v1: 98 of 190 nodes parked at exactly 0.9,
                       174 in [0.78, 0.9], and the frontier's most-uncertain-first
                       query degenerated into surfacing whichever old nodes happened
                       to be written lower.
  the test budget      a hypothesis "under test" whose confidence has not moved across
                       enough questions is retired as stale, because a test that stops
                       moving a belief is not a test any more.

The failure all of this exists to prevent is measured, not hypothetical: upstream's
sibling campaign had one run self-confirm a goal at step 2 and ride it at confidence
0.95+ for the remaining 198 steps; 70 of 177 goal nodes finished >= 0.9 and unverified.
A belief store that cannot be corrected is just a way to make a mistake permanent.

Under `--outcome-feedback` the evaluator writes each question's graded outcome into
`events/events.jsonl` (harness-written; the agent cannot write there), and
`apply_outcome` folds it into the graph's `answer` nodes the same way the hypothesis
arm's outcome-driven reweighting does (+0.25 / -0.15 on the model's own committed
answer) -- as confidence evidence, never as a status change, because a correct letter
on a 5-way MCQ is evidence and not proof.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from worldmodel_search.hypotheses import HypothesisGraph

logger = logging.getLogger(__name__)

# Questions a hypothesis may stay "under test" with no movement in its confidence before
# the harness marks it stale. Upstream used 120 steps of a 12,000-step episode; a
# question run is a few hundred questions, and a belief that fifteen questions' worth of
# evidence has not moved is not being tested by answering more of them.
TEST_BUDGET_QUESTIONS = 15

# How far a confidence must move from where the test started to count as progress and
# restart the clock. Upstream's 0.05 let a belief live forever on 0.65 -> 0.70 -> 0.65
# jiggle; a rewritten statement or changed status also restarts it (real revisions).
TEST_PROGRESS_DELTA = 0.15

# The ceilings, by what the node's evidence actually cites. Confidence is a claim
# about support, so the harness prices it by the support's structure: no cited
# question is a guess, one independent source is a single look, two or more is as far
# as an unconfirmed belief goes. REVERTED sits below every ceiling and above the 0.5
# floor, so a reverted claim is neither trusted nor erased.
ACTIVE_CEILING = 0.9            # two+ independent sources, until confirmed
SINGLE_SOURCE_CEILING = 0.8     # one independent source
UNCITED_CEILING = 0.7           # no Q citation in evidence
REVERTED_CONFIDENCE = 0.6
UNVERIFIED_MARK = "[unverified: fewer than two independent sources in evidence]"

# The outcome-driven reweighting deltas, taken verbatim from
# `memory_search_agent.HypothesisMemory` so the feedback variant of this arm moves its
# answer beliefs exactly as the hypothesis arm moves its.
CONFIRM_DELTA = 0.25
CONTRADICT_DELTA = 0.15

_QREF_RE = re.compile(r"\bQ(\d+)\b")


def distinct_question_refs(node, ref_re: re.Pattern[str] = _QREF_RE) -> set[str]:
    """The distinct questions a node's evidence cites, as 'Q<n>' tokens.

    The statement does not count -- a claim naming its own question is not evidence for
    itself -- and neither does anything outside the evidence list. `ref_re` is the
    token pattern; a benchmark whose unit of evidence is not a question (the KiCad
    port cites turns, `T<n>`) passes its own, with one capture group for the number.
    """
    refs: set[str] = set()
    for e in node.evidence:
        refs.update(ref_re.findall(str(e)))
    return refs


def mark_unverified(statement: str) -> str:
    """Prefix a self-confirmed claim so the prompt renders it as the open question it
    still is. Idempotent -- a claim reverted twelve times is marked once.

    The *statement* is marked, not just the status, because the statement is what the
    prompt view renders back. Upstream measured the alternative: revert the label,
    leave the wording, and the model goes on reading its own unverified claim as
    established fact.
    """
    text = (statement or "").strip()
    if text.startswith(UNVERIFIED_MARK):
        return text
    return f"{UNVERIFIED_MARK} {text}"


class Discipline:
    """Warden for one run's graph. Holds the state the rules need between questions."""

    def __init__(self, graph: HypothesisGraph, *,
                 ref_re: re.Pattern[str] = _QREF_RE, unit: str = "questions",
                 same_source_note: str = "one specimen asked twice is one look, not two",
                 test_budget: int = TEST_BUDGET_QUESTIONS) -> None:
        self.graph = graph
        self.marked: set[str] = set()
        # The unit of evidence. A question run's is the question (`Q<n>` tokens, frames per
        # question); a GUI episode's is the turn (`T<n>`, one screenshot per turn).
        # Only the token pattern and the words the harness says change; the rules
        # do not.
        self.ref_re = ref_re
        self.unit = unit
        self.same_source_note = same_source_note
        self.test_budget = test_budget
        # q_idx -> content hashes of that question's frames, fed by the evaluator as it
        # saves them. Empty when unfed, which degrades the independence rule to
        # distinct-questions-only -- the pre-frame-identity behaviour.
        self.frame_ids: dict[int, frozenset[str]] = {}
        # (id, since_question, confidence_then, (statement_then, status_then))
        self.testing: tuple[str, int, float, tuple[str, str]] | None = None
        self.counters: dict[str, int] = {
            "confirm_reverted": 0, "confidence_capped": 0, "noop_ops": 0,
            "stale_by_budget": 0, "outcomes_applied": 0,
        }

    # -- the evidence rule and the ceiling --------------------------------

    def independent_sources(self, node) -> int:
        """How many genuinely independent sources a node's evidence cites.

        Two cited questions collapse into one source when their frame sets carry the
        same content hashes: the run's specimens recur across questions, and a second
        question about the same pixels re-states the first look rather than checking
        it. A question whose frames are unknown (unfed, or no images) stands as its
        own source -- there is nothing to collapse it with.
        """
        keys: set[Any] = set()
        for q in distinct_question_refs(node, self.ref_re):
            frames = self.frame_ids.get(int(q))
            keys.add(("frames", frames) if frames else ("question", q))
        return len(keys)

    def seen_before(self, q_idx: int) -> list[tuple[int, bool]]:
        """Earlier questions whose stored frames share pixels with question q_idx's.

        Returns (earlier_q, identical) pairs ascending -- `identical` when the two
        questions' frame sets carry exactly the same content hashes, else they merely
        overlap. Empty when the current question's frames are unfed, which also makes
        this safe on a text-only question.

        This is the retrieval face of the identity the independence rule uses to
        *collapse* sources: the evaluator surfaces it to the act prompt, because
        g56low_v1 measured the model never re-opening a frame more than 7 questions
        back -- the run's one 25-question-gap revisit of an image set went entirely
        unrecognised (WORLDMODEL_MECHANISM_AUDIT.md, third round). The harness knows
        the identity either way; withholding it just tests recall of a fact we have.
        """
        mine = self.frame_ids.get(q_idx)
        if not mine:
            return []
        return [(q, theirs == mine)
                for q, theirs in sorted(self.frame_ids.items())
                if q < q_idx and theirs and (mine & theirs)]

    def enforce(self) -> None:
        """Apply every structural rule to the graph. Called once per turn, after the
        model's ops have been folded in."""
        for hid in list(self.graph.nodes):
            node = self.graph.nodes[hid]
            sources = self.independent_sources(node)

            if sources >= 2:
                if hid in self.marked and node.statement.startswith(UNVERIFIED_MARK):
                    node.statement = node.statement[len(UNVERIFIED_MARK):].strip()
                self.marked.discard(hid)
                # Only a confirmation buys headroom above the band; a multi-source
                # node still awaiting one sits at the top of it.
                if node.status != "confirmed" and node.confidence > ACTIVE_CEILING:
                    node.confidence = ACTIVE_CEILING
                    self.counters["confidence_capped"] += 1
                continue

            if node.status == "confirmed":
                node.status = "active"
                node.confidence = min(node.confidence, REVERTED_CONFIDENCE)
                node.statement = mark_unverified(node.statement)
                self.marked.add(hid)
                self.counters["confirm_reverted"] += 1
                logger.warning(
                    "[discipline] '%s' marked confirmed with %d distinct question(s) "
                    "but %d independent source(s) in evidence; reverted to active "
                    "at %.2f",
                    hid, len(distinct_question_refs(node, self.ref_re)), sources,
                    node.confidence,
                )
            ceiling = SINGLE_SOURCE_CEILING if sources == 1 else UNCITED_CEILING
            if node.confidence > ceiling:
                node.confidence = ceiling
                self.counters["confidence_capped"] += 1
        self.counters["noop_ops"] = self.graph.noop_updates

    # -- the test budget --------------------------------------------------

    def track_testing(self, testing: Any, step: int) -> Optional[str]:
        """Follow the hypothesis the agent says it is testing; retire it when the test
        stops producing movement. Returns a note for the log if the budget fired."""
        hid = str(testing) if testing else None
        if hid is None or hid not in self.graph.nodes:
            self.testing = None
            return None

        node = self.graph.nodes[hid]
        sig = (node.statement.strip(), node.status)
        if self.testing is None or self.testing[0] != hid:
            self.testing = (hid, step, node.confidence, sig)
            return None

        _, since, conf0, sig0 = self.testing
        moved = (abs(node.confidence - conf0) >= TEST_PROGRESS_DELTA) or (sig != sig0)
        if moved:
            self.testing = (hid, step, node.confidence, sig)
            return None
        if step - since >= self.test_budget:
            node.status = "stale"
            self.testing = None
            self.counters["stale_by_budget"] += 1
            note = (f"hypothesis '{hid}' was under test for {step - since} {self.unit} "
                    f"with no change in confidence; marked stale. Pick a different "
                    f"hypothesis, or a different way to test this one.")
            logger.warning("[discipline] %s", note)
            return note
        return None

    # -- the outcome ledger (--outcome-feedback only) ---------------------

    def apply_outcome(self, q_idx: int, correct: bool, step: int) -> list[str]:
        """Fold one graded outcome into the `answer` nodes that committed to Q<q_idx>.

        Matched on the question reference appearing in the node id, statement or
        evidence -- loose on purpose: the agent names its own hypotheses, and requiring
        an exact id would mean the rule silently never fires. Returns the ids touched.
        """
        token = f"Q{q_idx}"
        touched: list[str] = []
        for hid, node in self.graph.nodes.items():
            if node.kind != "answer":
                continue
            hay = f"{hid} {node.statement} {' '.join(node.evidence)}"
            if not re.search(rf"\b{re.escape(token)}\b", hay):
                continue
            delta = CONFIRM_DELTA if correct else -CONTRADICT_DELTA
            node.confidence = max(0.0, min(1.0, node.confidence + delta))
            verdict = "correct" if correct else "incorrect"
            node.evidence.append(f"events.jsonl: {token} graded {verdict}")
            node.updated_step = step
            touched.append(hid)
            self.counters["outcomes_applied"] += 1
        return touched

    # -- what the prompt is told ------------------------------------------

    def flags(self, step: int) -> dict[str, str]:
        """Per-node tags rendered next to the graph view."""
        out: dict[str, str] = {}
        if self.testing and self.testing[0] in self.graph.nodes:
            out[self.testing[0]] = (f"under test for {step - self.testing[1]} {self.unit} "
                                    f"(budget {self.test_budget})")
        return out

    def summary(self) -> str:
        """Facts about the agent's own graph, stated so it can act on them rather than
        be surprised by them. Only non-zero counters, so this section stays empty (and
        out of the prompt) on a run where nothing has gone wrong."""
        bits = []
        c = self.counters
        if c["confirm_reverted"]:
            bits.append(f"{c['confirm_reverted']} confirmation(s) reverted: a claim is "
                        f"confirmed only by evidence citing two distinct {self.unit} "
                        f"whose frames are not the same images -- "
                        f"{self.same_source_note}.")
        if c["stale_by_budget"]:
            bits.append(f"{c['stale_by_budget']} hypothesis/es retired for sitting "
                        f"under test without moving.")
        if c["confidence_capped"]:
            bits.append(f"{c['confidence_capped']} confidence value(s) clamped to "
                        f"their evidence tier: {UNCITED_CEILING} with no cited "
                        f"{self.unit[:-1] if self.unit.endswith('s') else self.unit}, "
                        f"{SINGLE_SOURCE_CEILING} with one independent "
                        f"source, {ACTIVE_CEILING} with two or more -- cite more, "
                        f"or claim less.")
        if c["noop_ops"] > 20:
            bits.append(f"{c['noop_ops']} hypothesis ops changed nothing and were "
                        f"discarded -- re-sending the graph you were just shown costs "
                        f"you a turn's thinking and tells you nothing.")
        return "\n".join(f"- {b}" for b in bits)
