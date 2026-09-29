"""The belief DAG, moved out of the prompt and into the filesystem.

This is a port of MineExplorer's `mc_agent/hypothesis.py`. The data model and the
constants are kept -- they were tuned against a 719-node, 11,577-update campaign and the
reasons are recorded inline -- but one structural assumption is dropped.

Upstream, the graph *was* a prompt section. Every node the agent held had to be re-sent
on every step, so `to_prompt_summary` capped the rendering at 8 nodes and spent real
design effort deciding which 8 (goals first, at most 2 mechanisms, then the frontier).
That cap is not a belief about how many hypotheses an agent should have; it is the
context window showing through.

Here the graph is a file. It can hold thousands of nodes, and the prompt shows a
*view* -- the frontier plus the goal spine -- while the agent reaches the rest with
`grep` over `hypotheses/`. So the cap stays, but it now bounds what is *rendered*, not
what is *known*, and nodes that fall out of the view are still there to be found. That
is the whole reason for putting the DAG in the filesystem rather than leaving it where
it was.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

HypothesisStatus = Literal["active", "confirmed", "refuted", "stale"]
STATUSES = ("active", "confirmed", "refuted", "stale")

# The prompt shows harness words next to a node ("locked", "under test for 12 steps"), and
# the model sometimes sends one back as a `status` -- 19 nodes across MineExplorer's q35a
# campaign ended on "locked" or "under test". Those are not states any rule knows: a goal
# sitting on "locked" is neither `active` (so frontier() and the test budget skip it) nor
# `confirmed` (so the goal discipline never looks at it), which is a way out of the
# discipline by typo. Unrecognised statuses are dropped, leaving the node where the
# harness last put it.

MAX_EVIDENCE_PER_NODE = 8

# How many "mechanism" nodes may occupy the prompt view at once. 47 % of q35a's nodes were
# mechanism ("the button opens the door") against 22 % location, and the graph the model
# reads back is the graph it extends -- so an unbounded mechanism share feeds itself.
#
# Raised from upstream's 2 to 4 for MCU. There the tasks were find-and-reach, where a
# mechanism hypothesis was usually a distraction from the only question that mattered
# (where is it). Both tasks here are *crafting and combat* pipelines, where "smelting iron
# ore needs fuel in the furnace" and "the crystals heal the dragon" are the load-bearing
# beliefs, not distractions. The kind that deserves prompt space follows the task.
MAX_MECHANISM_IN_PROMPT = 4

HypothesisKind = Literal["goal", "location", "mechanism", "state", "resource", "other"]
# `resource` is new here: on a crafting pipeline, "I have 3 of the 5 iron I need" is a
# claim with a quantity in it that the inventory can settle outright, and folding those
# into `state` made a single node absorb an entire episode's inventory history.
KINDS = ("goal", "location", "mechanism", "state", "resource", "other")


class Hypothesis(BaseModel):
    id: str
    statement: str
    confidence: float = 0.5
    status: HypothesisStatus = "active"
    kind: HypothesisKind = "other"
    depends_on: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    created_step: int = 0
    updated_step: int = 0


class CycleError(ValueError):
    """Raised when adding a dependency edge would create a cycle in the DAG."""


class HypothesisGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Hypothesis] = {}
        # Updates that named an existing id but changed nothing. 71 % of q35a's 11,577
        # updates were these -- the model re-sending the graph it had just been shown.
        # Counted, and (see add_or_update) they do not refresh `updated_step`.
        self.noop_updates: int = 0

    # -- mutation ---------------------------------------------------------

    def add_or_update(
        self, *, id: str, statement: Optional[str] = None,
        confidence: Optional[float] = None, status: Optional[str] = None,
        evidence: Optional[List[str]] = None, step: int = 0,
        kind: Optional[str] = None,
    ) -> Hypothesis:
        if status is not None and status not in STATUSES:
            status = None
        node = self.nodes.get(id)
        if node is None:
            self.nodes[id] = node = Hypothesis(
                id=id, statement=statement or "(unspecified)",
                confidence=confidence if confidence is not None else 0.5,
                status=status or "active",
                kind=kind if kind in KINDS else "other",
                evidence=(list(evidence) if evidence else [])[-MAX_EVIDENCE_PER_NODE:],
                created_step=step, updated_step=step,
            )
            return node

        changed = False
        if kind in KINDS and kind != node.kind:
            node.kind, changed = kind, True
        if statement and statement.strip() != node.statement.strip():
            node.statement, changed = statement, True
        if confidence is not None:
            new_conf = max(0.0, min(1.0, float(confidence)))
            if new_conf != node.confidence:
                node.confidence, changed = new_conf, True
        if status and status != node.status:
            node.status, changed = status, True
        if evidence:
            # Evidence is an audit trail, not a belief: the prompt view never renders it,
            # so a node whose statement/confidence/status did not move is not a newer
            # belief just because a phrase was appended. 91 % of q35a's ops carried one --
            # counting them as changes would refresh `updated_step` for almost every
            # re-send and undo the rule below.
            for e in evidence:
                if e not in node.evidence:
                    node.evidence.append(e)
            node.evidence = node.evidence[-MAX_EVIDENCE_PER_NODE:]
        # `updated_step` is read as "how stale is this belief" -- by frontier() as its
        # tie-break and by the prompt view to fill its remaining slots. Bumping it for an
        # op that changed nothing made a node the model retypes verbatim every step look
        # permanently fresh, so noise held the slots evidence should have.
        if changed:
            node.updated_step = step
        else:
            self.noop_updates += 1
        return node

    def _reachable(self, start: str) -> set:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if (node := self.nodes.get(cur)) is not None:
                stack.extend(node.depends_on)
        return seen

    def add_dependency(self, child_id: str, parent_id: str, step: int = 0) -> None:
        if child_id == parent_id:
            raise CycleError(f"hypothesis '{child_id}' cannot depend on itself")
        if parent_id not in self.nodes:
            self.add_or_update(id=parent_id, step=step)
        if child_id in self._reachable(parent_id):
            raise CycleError(f"adding edge {child_id} -> {parent_id} would create a cycle")
        child = self.nodes.get(child_id) or self.add_or_update(id=child_id, step=step)
        if parent_id not in child.depends_on:
            child.depends_on.append(parent_id)
        child.updated_step = step

    # -- queries ----------------------------------------------------------

    def frontier(self, k: int = 5) -> List[Hypothesis]:
        """Active hypotheses whose dependencies are all resolved, most-uncertain first
        (confidence closest to 0.5), tie-broken by staleness."""
        candidates = []
        for node in self.nodes.values():
            if node.status != "active":
                continue
            deps = [self.nodes.get(d) for d in node.depends_on]
            if any(d is not None and d.status == "active" for d in deps):
                continue
            candidates.append(node)
        candidates.sort(key=lambda n: (abs(n.confidence - 0.5), n.updated_step))
        return candidates[:k]

    def to_prompt_summary(self, max_items: int = 12, flags: Optional[Dict[str, str]] = None,
                          max_mechanisms: int = MAX_MECHANISM_IN_PROMPT,
                          now_step: Optional[int] = None) -> str:
        """The *view*, not the graph. Goals first (they are the task's map and the
        discipline rules act on them), then at most `max_mechanisms` mechanism nodes, then
        the frontier, then whatever is freshest.

        What falls off the end is still in `hypotheses/graph.json` and still greppable;
        the footer says so, because a model that believes the view is the whole graph will
        re-propose nodes it already has.
        """
        if not self.nodes:
            return ""
        goals = sorted((n for n in self.nodes.values() if n.kind == "goal"),
                       key=lambda n: n.created_step)
        ranked = goals[:max_items]
        shown = {n.id for n in ranked}
        mechanisms = sum(1 for n in ranked if n.kind == "mechanism")

        def take(n: Hypothesis) -> bool:
            nonlocal mechanisms
            if n.id in shown or len(ranked) >= max_items:
                return False
            if n.kind == "mechanism" and mechanisms >= max_mechanisms:
                return False
            ranked.append(n)
            shown.add(n.id)
            if n.kind == "mechanism":
                mechanisms += 1
            return True

        for n in self.frontier(k=max_items):
            take(n)
        for n in sorted((n for n in self.nodes.values() if n.id not in shown),
                        key=lambda n: n.updated_step, reverse=True):
            take(n)

        lines = []
        for n in ranked:
            deps = f" (depends on: {', '.join(n.depends_on)})" if n.depends_on else ""
            flag = f", {flags[n.id]}" if flags and n.id in flags else ""
            # Staleness, shown once it is old enough to mean something: goal_furnace
            # sat at confidence 0.80 through 2,400 steps of failed attempts (dm5) and
            # nothing in the view said so. A fact, not advice -- repricing is the
            # model's job.
            idle = ""
            if now_step is not None and n.status == "active":
                gap = now_step - n.updated_step
                if gap >= 300:
                    idle = f", updated {gap} steps ago"
            lines.append(
                f"- [{n.id}] ({n.kind}, {n.status}, confidence={n.confidence:.2f}"
                f"{flag}{idle}) {n.statement}{deps}"
            )
        hidden = len(self.nodes) - len(ranked)
        if hidden > 0:
            lines.append(
                f"\n({hidden} more hypotheses not shown. This is a view, not the whole "
                f"graph -- the full DAG is `hypotheses/graph.json` and one .md per node "
                f"under `hypotheses/`. Grep there before proposing a node you may already "
                f"have.)"
            )
        return "\n".join(lines)

    def counts_by_kind(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for n in self.nodes.values():
            out[n.kind] = out.get(n.kind, 0) + 1
        return out

    # -- persistence ------------------------------------------------------

    def to_dict(self) -> dict:
        return {"nodes": [n.model_dump() for n in self.nodes.values()]}

    @classmethod
    def from_dict(cls, data: dict) -> "HypothesisGraph":
        graph = cls()
        for raw in data.get("nodes", []):
            node = Hypothesis(**raw)
            graph.nodes[node.id] = node
        return graph

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "HypothesisGraph":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def write_markdown(self, directory: str | Path) -> None:
        """One .md per node, so the DAG is greppable by content and not only by id.

        `graph.json` is the authority and this is a projection of it -- the agent is told
        to send hypothesis ops rather than edit these files, because a node edited here
        would be silently overwritten on the next step. The projection exists so that
        `grep -rl "iron ore" hypotheses/` works, which on a graph too large to render is
        the only way the agent finds a belief it formed 400 steps ago.
        """
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for node in self.nodes.values():
            body = [
                f"# {node.id}", "",
                f"- kind: {node.kind}", f"- status: {node.status}",
                f"- confidence: {node.confidence:.2f}",
                f"- created_step: {node.created_step}",
                f"- updated_step: {node.updated_step}",
            ]
            if node.depends_on:
                body.append(f"- depends_on: {', '.join(node.depends_on)}")
            body += ["", "## Statement", "", node.statement]
            if node.evidence:
                body += ["", "## Evidence", ""] + [f"- {e}" for e in node.evidence]
            body += ["", "<!-- projection of hypotheses/graph.json; edits here are "
                     "overwritten. Change a belief by sending a hypothesis op. -->", ""]
            (d / f"{node.id}.md").write_text("\n".join(body), encoding="utf-8")
