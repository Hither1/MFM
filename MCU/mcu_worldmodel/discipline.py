"""The rules the harness enforces on the belief graph, re-grounded for MCU.

Ported from `HypothesisAgent._enforce_discipline` / `_gate_esc` in MineExplorer, where
each rule was calibrated against a measured failure. The rules survive; their *trigger*
changes, because the mechanism they hung off does not exist here.

Upstream, the agent ended its own episode by pressing `ESC`, and that press was the
moment of truth: the harness compared the model's belief that it was finished against the
environment's verification, refused the press when they disagreed, and locked every goal
the model had convinced itself of. MCU's action space has no `ESC` -- an episode ends on
its step budget -- so there is no single moment to gate.

What replaces it is continuous. Every step, each goal hypothesis is checked against the
`MilestoneLedger`, which reads MineRL's own statistics and never sees a model output. A
goal the model marks "confirmed" that the ledger has not verified is reverted on the spot,
rather than at an ESC press that may never come. That is strictly stronger than the
upstream check: it fires at step 40 instead of step 300, and it fires every time.

The failure it exists to prevent is worth restating, because it is the whole reason the
belief store needs a warden. In MineExplorer's q35a campaign, one run self-confirmed "there
is a spruce door on the front wall" at step 2 from eight blocks away; the label was
reverted but the belief was not, so the node rode the prompt at confidence 0.95+ for the
remaining 198 steps and the agent spent the episode trying to open a door it had never
seen. 70 of 177 goal nodes finished >= 0.9 and unverified. A belief store that cannot be
corrected by the world is just a way to make a mistake permanent.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from mcu_worldmodel.hypotheses import HypothesisGraph

# Steps a hypothesis may stay "under test" with no movement in its confidence before the
# harness marks it stale and clears the plan. Upstream used 25 for 300-step episodes;
# scaled here for episodes 20-40x longer, but not by the same factor -- a test that has
# not moved a belief in 120 steps is not a test any more regardless of the budget, and
# these episodes contain genuinely slow operations (a strip-mine tunnel is ~100 ticks).
TEST_BUDGET_STEPS = 120

# How far a confidence must move from where the test started to count as progress and
# restart the clock. Upstream's v2.0 used 0.05, and 24 % of all updates cleared it -- so a
# belief could be kept alive indefinitely by jiggling 0.65 -> 0.70 -> 0.65 and the budget
# fired 13 times in 48 runs. A rewritten statement or a changed status also restarts it:
# those are real revisions.
TEST_PROGRESS_DELTA = 0.15

# The ceiling an unverified goal may sit at, and what a reverted confirmation drops to.
# REVERTED sits below the "up to 0.9" band the prompt allows for honest belief and above
# the 0.5 floor, so a reverted goal is neither trusted nor erased.
GOAL_ACTIVE_CEILING = 0.9
REVERTED_GOAL_CONFIDENCE = 0.6
UNVERIFIED_MARK = "[unverified: the environment has not confirmed this]"


def mark_unverified(statement: str) -> str:
    """Prefix a self-confirmed goal so the prompt renders the claim as the open question
    it still is. Idempotent -- a goal reverted twelve times is marked once.

    The *statement* is marked, not just the status, because the statement is what the
    prompt view renders back. Upstream reverted the label and left the wording, and the
    model went on reading its own unverified claim as established fact.
    """
    text = (statement or "").strip()
    if text.startswith(UNVERIFIED_MARK):
        return text
    return f"{UNVERIFIED_MARK} {text}"


class Discipline:
    """Warden for one episode's graph. Holds the state the rules need between steps."""

    def __init__(self, graph: HypothesisGraph, ledger) -> None:
        self.graph = graph
        self.ledger = ledger
        self.locked: set[str] = set()
        self.marked: set[str] = set()
        # (id, since_step, confidence_then, (statement_then, status_then))
        self.testing: tuple[str, int, float, tuple[str, str]] | None = None
        self.counters: dict[str, int] = {
            "goal_confirm_reverted": 0, "goal_confidence_capped": 0, "noop_ops": 0,
            "stale_by_budget": 0, "claim_rejected": 0, "locked_raise_capped": 0,
        }
        # Location verification: node id -> last step the player stood within reach of
        # the coordinates its statement names. Goals are verified by the ledger; places
        # are verified by being there. A model-written "vein at (x, y, z)" the player
        # has never reached stays unmarked, which is itself the fact.
        self.visits: dict[str, int] = {}

    # -- the goal rule ----------------------------------------------------

    def _linked_milestone(self, node) -> str | None:
        """Which milestone, if any, a goal hypothesis is about.

        Matched on the milestone identity appearing in the node id or statement. Loose on
        purpose: the agent names its own hypotheses, and requiring an exact id would mean
        the rule silently never fires -- which is the failure mode where a discipline
        looks enforced and is not. A goal that matches nothing is still held to the
        ceiling below; it just cannot be *confirmed* by a milestone.
        """
        hay = f"{node.id} {node.statement}".lower()
        for ident in self.ledger.order:
            if ident.lower() in hay:
                return ident
        return None

    def enforce(self, touched: list[str], step: int) -> None:
        """Apply every rule to the graph. Called once per turn, after the model's ops."""
        for hid in list(self.graph.nodes):
            node = self.graph.nodes[hid]
            if node.kind != "goal":
                continue

            ident = self._linked_milestone(node)
            verified = self.ledger.is_verified(ident) if ident else False

            if verified:
                # The environment agrees: clear the marks and let it stand confirmed.
                if hid in self.marked:
                    if node.statement.startswith(UNVERIFIED_MARK):
                        node.statement = node.statement[len(UNVERIFIED_MARK):].strip()
                    self.marked.discard(hid)
                self.locked.discard(hid)
                continue

            if node.status == "confirmed":
                node.status = "active"
                node.confidence = min(node.confidence, REVERTED_GOAL_CONFIDENCE)
                node.statement = mark_unverified(node.statement)
                self.marked.add(hid)
                self.counters["goal_confirm_reverted"] += 1
                logger.warning(
                    f"[discipline] goal '{hid}' self-confirmed but the environment has "
                    f"not verified it; reverted to active at {node.confidence:.2f}"
                )
            if node.confidence > GOAL_ACTIVE_CEILING:
                node.confidence = GOAL_ACTIVE_CEILING
                self.counters["goal_confidence_capped"] += 1
            if hid in self.locked and node.confidence > 0.5:
                node.confidence = 0.5
                self.counters["locked_raise_capped"] += 1

        self.counters["noop_ops"] = self.graph.noop_updates

    # -- the test budget --------------------------------------------------

    def track_testing(self, testing: Any, step: int) -> str | None:
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
        if step - since >= TEST_BUDGET_STEPS:
            node.status = "stale"
            self.testing = None
            self.counters["stale_by_budget"] += 1
            note = (f"hypothesis '{hid}' was under test for {step - since} steps with no "
                    f"change in confidence; marked stale and your plan was cleared. Pick "
                    f"a different hypothesis, or a different way to test this one.")
            logger.warning(f"[discipline] {note}")
            return note
        return None

    # -- the claim gate (what replaces ESC-gating) ------------------------

    def check_claim(self, claim: dict[str, Any] | None, step: int) -> str | None:
        """Check a `claim.json` the agent wrote against the ledger.

        The agent may assert it has completed named milestones. The assertion changes
        nothing on its own -- the ledger already knows -- but a *false* one is diagnostic,
        so it is checked and it costs something: every goal named in a false claim is
        locked to confidence 0.5 until the environment says otherwise. That is upstream's
        ESC lock, moved to the only place in MCU where the model volunteers a belief about
        being finished.
        """
        if not isinstance(claim, dict):
            return None
        claimed = claim.get("completed") or []
        if not isinstance(claimed, list):
            return None
        false_ones = [c for c in map(str, claimed) if not self.ledger.is_verified(c)]
        if not false_ones:
            return None

        self.counters["claim_rejected"] += 1
        for hid, node in self.graph.nodes.items():
            if node.kind != "goal":
                continue
            if any(c.lower() in f"{hid} {node.statement}".lower() for c in false_ones):
                self.locked.add(hid)
                node.confidence = min(node.confidence, 0.5)
                node.statement = mark_unverified(node.statement)
                self.marked.add(hid)
        note = (f"you claimed {false_ones} complete, but the environment has not verified "
                f"them. Those goals are locked at confidence 0.5 (shown as 'locked') "
                f"until it does. Re-verify them physically rather than re-claiming.")
        logger.warning(f"[discipline] {note}")
        return note

    # -- what the prompt is told ------------------------------------------

    def note_visits(self, pos: dict[str, float], step: int) -> None:
        """Record the player standing at the coordinates a location node names."""
        from mcu_worldmodel import sites

        for hid, node in self.graph.nodes.items():
            if node.kind != "location" or node.status in ("refuted", "stale"):
                continue
            c = sites.parse_coords(node.statement)
            if c and sites.near(pos, c, sites.VISIT_RADIUS):
                self.visits[hid] = step

    def flags(self, step: int) -> dict[str, str]:
        """Per-node tags rendered next to the graph view."""
        out = {hid: "locked" for hid in self.locked}
        if self.testing and self.testing[0] in self.graph.nodes:
            out[self.testing[0]] = (f"under test for {step - self.testing[1]} steps "
                                    f"(budget {TEST_BUDGET_STEPS})")
        for hid, s in self.visits.items():
            if hid in self.graph.nodes:
                tag = f"visited at step {s}"
                out[hid] = f"{out[hid]}, {tag}" if hid in out else tag
        return out

    def summary(self) -> str:
        """Facts about the agent's own graph, stated so it can act on them rather than be
        surprised by them. Only non-zero counters, so this section stays empty (and out of
        the prompt) on a run where nothing has gone wrong."""
        bits = []
        c = self.counters
        if c["goal_confirm_reverted"]:
            bits.append(f"{c['goal_confirm_reverted']} goal confirmation(s) reverted: only "
                        f"the environment confirms a goal.")
        if c["claim_rejected"]:
            bits.append(f"{c['claim_rejected']} completion claim(s) rejected as unverified.")
        if c["stale_by_budget"]:
            bits.append(f"{c['stale_by_budget']} hypothesis/es retired for sitting under "
                        f"test without moving.")
        if c["noop_ops"] > 20:
            bits.append(f"{c['noop_ops']} hypothesis ops changed nothing and were "
                        f"discarded -- re-sending the graph you were just shown costs you "
                        f"a turn's thinking and tells you nothing.")
        if self.locked:
            bits.append(f"locked goals: {', '.join(sorted(self.locked))}.")
        return "\n".join(f"- {b}" for b in bits)
