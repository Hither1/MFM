"""The belief DAG, moved out of the prompt and into the filesystem.

Ported from `MCU-AgentBeats:mcu_worldmodel/hypotheses.py`, which is itself the port of
the DAG this repo's hypothesis arm keeps in `memory_search_agent.HypothesisMemory` --
with the structural assumption both of those inherited finally dropped on the arm that
exists to drop it.

In `HypothesisMemory` the graph *is* a prompt section: MAX_HYPOTHESES = 16, and past the
cap the lowest-confidence node is evicted. That cap is not a belief about how many
hypotheses an agent should hold; it is the context window showing through. Here the
graph is a file. It can hold as many nodes as the run produces, the prompt shows a
*view* (strategies first, then the frontier, then whatever is freshest), and nodes that
fall out of the view are still there to be found with `grep` over `hypotheses/`.

The kinds are re-grounded for a question run. Minecraft's goal/location/mechanism map onto
what a question run accumulates:

    observation  a visual claim about a specific question's images ("Q7's EM panel
                 shows dense parallel membranes"). Numerous and image-anchored -- the
                 view caps them so old groups' observations do not crowd out the rest.
    domain       a reusable biology/microscopy rule ("LC3 puncta under starvation
                 indicate autophagosome formation"). The load-bearing accumulating kind.
    strategy     how to answer a task type ("for experiment_proposal, eliminate choices
                 that do not control the stated confounder"). Few, rendered first: they
                 are the map the act turn executes and the induction pass re-evaluates.
    answer       the committed answer of one question, as a claim that can later be
                 tested -- by recurrence, or by the outcome ledger when that is on.
    other        everything else.

Implemented with stdlib dataclasses rather than pydantic, because this repository does
not otherwise depend on pydantic and the model is five fields and a list.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

STATUSES = ("active", "confirmed", "refuted", "stale")

# The prompt shows harness words next to a node ("under test for 12 questions"), and the
# model sometimes sends one back as a `status`. Those are not states any rule knows, and
# a node sitting on one would be skipped by every rule -- a way out of the discipline by
# typo. Unrecognised statuses are dropped, leaving the node where the harness put it.

MAX_EVIDENCE_PER_NODE = 8

KINDS = ("observation", "domain", "strategy", "answer", "other")

# How many `observation` nodes may occupy the prompt view at once. They are the most
# numerous kind by construction (every question can mint several) and they are anchored
# to images the run may never revisit; the view is for what the next answer needs, and
# the rest stays greppable.
MAX_OBSERVATION_IN_PROMPT = 4

# How many `strategy` nodes may occupy the prompt view at once. Strategies seed the
# view first, and `strategy` is a self-assigned label that bought permanent top-priority
# space: in g56low_v1 twelve of them -- four being single-question answer recipes --
# held every slot from Q85 on, freezing the view while 176 nodes stayed invisible and
# the frontier never ran again (WORLDMODEL_MECHANISM_AUDIT.md §2). Capped, the map
# stays visible without becoming the whole view.
MAX_STRATEGY_IN_PROMPT = 5


@dataclass
class Hypothesis:
    id: str
    statement: str
    confidence: float = 0.5
    status: str = "active"
    kind: str = "other"
    depends_on: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    created_step: int = 0
    updated_step: int = 0


class CycleError(ValueError):
    """Raised when adding a dependency edge would create a cycle in the DAG."""


class HypothesisGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Hypothesis] = {}
        # Updates that named an existing id but changed nothing: the model re-sending
        # the graph it was just shown. 71 % of updates in the campaign this constant
        # was tuned against were these. Counted, and they do not refresh `updated_step`.
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
            # Evidence is an audit trail, not a belief: a node whose statement,
            # confidence and status did not move is not a newer belief just because a
            # phrase was appended, so appending evidence alone does not refresh
            # `updated_step` -- otherwise a node the model retypes verbatim every turn
            # looks permanently fresh and noise holds the view slots.
            for e in evidence:
                if e not in node.evidence:
                    node.evidence.append(e)
            node.evidence = node.evidence[-MAX_EVIDENCE_PER_NODE:]
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
                          max_observations: int = MAX_OBSERVATION_IN_PROMPT,
                          max_strategies: int = MAX_STRATEGY_IN_PROMPT) -> str:
        """The *view*, not the graph. Strategies first (they are the map the act turn
        executes and the discipline acts on), then the frontier, then whatever is
        freshest -- with `observation` AND `strategy` capped throughout, and every
        kind ranked freshest-first. Both halves are load-bearing: uncapped, the
        self-assigned `strategy` label bought the whole view (g56low_v1 froze on
        twelve of them from Q85 on), and ranked by creation, a strategy learned at
        Q92 could never displace one from Q7.

        What falls off the end is still in `hypotheses/graph.json` and still greppable;
        the footer says so, because a model that believes the view is the whole graph
        will re-propose nodes it already has.
        """
        if not self.nodes:
            return ""
        strategies = sorted((n for n in self.nodes.values() if n.kind == "strategy"),
                            key=lambda n: n.updated_step, reverse=True)
        ranked = strategies[:min(max_strategies, max_items)]
        shown = {n.id for n in ranked}
        counts = {"strategy": len(ranked), "observation": 0}
        caps = {"strategy": max_strategies, "observation": max_observations}

        def take(n: Hypothesis) -> bool:
            if n.id in shown or len(ranked) >= max_items:
                return False
            if n.kind in caps and counts[n.kind] >= caps[n.kind]:
                return False
            ranked.append(n)
            shown.add(n.id)
            if n.kind in counts:
                counts[n.kind] += 1
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
            lines.append(
                f"- [{n.id}] ({n.kind}, {n.status}, confidence={n.confidence:.2f}{flag}) "
                f"{n.statement}{deps}"
            )
        hidden = len(self.nodes) - len(ranked)
        if hidden > 0:
            lines.append(
                f"\n({hidden} more hypotheses not shown. This is a view, not the whole "
                f"graph -- the full DAG is `hypotheses/graph.json` and one .md per node "
                f"under `hypotheses/`. Grep there before proposing a node you may "
                f"already have.)"
            )
        return "\n".join(lines)

    def counts_by_kind(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for n in self.nodes.values():
            out[n.kind] = out.get(n.kind, 0) + 1
        return out

    def counts_by_status(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for n in self.nodes.values():
            out[n.status] = out.get(n.status, 0) + 1
        return out

    # -- persistence ------------------------------------------------------

    def to_dict(self) -> dict:
        return {"nodes": [asdict(n) for n in self.nodes.values()]}

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

        `graph.json` is the authority and this is a projection of it -- the agent is
        told to send hypothesis ops rather than edit these files, because a node edited
        here would be silently overwritten on the next turn. The projection exists so
        that `grep -rl "cristae" hypotheses/` works, which on a graph too large to
        render is the only way the agent finds a belief it formed 200 questions ago.
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
