"""The two-tier loop: Astra on a trigger, JEV on every entry.

Upstream's cadence (`rmalde/minecraft-agent`, agent.mjs) is the whole method:

    plan model    called when the plan is null, the waypoint was reached, no option is
                  useful, or three actions in a row failed
    decide model  called every loop iteration with the state and the filtered options,
                  and its choice is executed immediately

This module is that loop with the game abstracted away: it is handed the state and the
candidates, it calls the two clients, and it hands back the chosen entry. The chassis
bridge (`mcu_worldmodel/jev.py`) supplies the state and executes the choice.

Two departures from upstream, both to keep the decision auditable rather than to change
the method: every decision also asks JEV a `replan` noul -- "would a new objective help
more than any option here?" -- which becomes one of the triggers, and every decision is
recorded (`events`) with the chosen key, the probability it carried and the runner-up, so
a run can be read back for how peaked the selector actually was.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from loguru import logger

from mfm.jev.decisions import (Decision, DecisionError, DecisionsBudgetExceeded, JevDecider,
                               choice, noul)
from mfm.jev.menu import WAIT_KEY, Candidate, CandidateMenu
from mfm.jev.planner import AstraPlanner, Plan, PlannerError


class Trigger:
    """Why the planner was called. Upstream's four, plus the selector's own ask."""
    NO_PLAN = "there is no plan yet"
    WAYPOINT = "the waypoint was reached"
    TARGETS = "the objective's targets are in hand"
    ERRORS = "three actions in a row failed"
    NO_OPTIONS = "no candidate action was useful"
    SELECTOR = "the selector asked for a new objective"
    STALLED = "nothing has changed for a long run of decisions"
    PLANNER_FAILED = "the previous planning call failed"


#: A waypoint counts as reached inside this many blocks (upstream checks a distance on
#: its pathfinder's target; the chassis's `go_to` stops within about two).
WAYPOINT_RADIUS = 3.0
#: Decisions of no ground-truth progress before the planner is called again.
STALL_LIMIT = 12
#: Decisions the planner is not called again within, so one bad objective cannot burn a
#: planning call per entry. NO_PLAN ignores it.
PLAN_COOLDOWN = 2

DECIDE_INSTRUCTIONS = (
    "You are the action selector for an agent playing Minecraft. Pick the ONE action "
    "from the options that best advances the objective from the state you are given. "
    "Every option is already legal here -- the harness checked it against the live state "
    "-- so choose on usefulness, not feasibility. Prefer an action that changes the world "
    "over one that only looks at it, and do not repeat an action the recent outcomes show "
    "changed nothing."
)
REPLAN_INSTRUCTIONS = (
    "Would a NEW objective from the planner help more than any option on this menu?"
)
OBJECTIVE_INSTRUCTIONS = (
    "Pick the ONE milestone to work toward from here. This is the objective the next "
    "actions will be chosen under, so pick what is reachable from this state -- the "
    "milestone that is one or two actions away, not the one at the end of the chain."
)


@dataclass
class Chosen:
    """One decision, ready for the chassis to enqueue."""
    candidate: Candidate
    trigger: str = ""
    plan: Plan | None = None
    probability: float | None = None
    confidence: float | None = None
    runner_up: str = ""
    replan_asked: bool = False
    decision: Decision | None = None
    fallback: str = ""                          # set when the choice had to be repaired


@dataclass
class JevSession:
    decider: JevDecider
    #: None only with `no_planner`: then there is no planner to call.
    planner: AstraPlanner | None
    task: str = ""
    #: `--jev-no-planner`: no planner at all. The selector sets the objective itself, as
    #: one more typed question in the SAME decision call, chosen from the milestones the
    #: ledger has not scored yet -- asked on exactly the triggers that would have called
    #: the planner, so the ablation against the two-model arm changes one thing only.
    #: The objective takes effect from the NEXT decision: the action in the call that
    #: sets it was chosen under the previous one (or under none, on the first call).
    no_planner: bool = False
    menu: CandidateMenu = field(default_factory=CandidateMenu)
    ask_replan: bool = True
    waypoint_radius: float = WAYPOINT_RADIUS
    stall_limit: int = STALL_LIMIT
    plan_cooldown: int = PLAN_COOLDOWN
    #: Called with (Plan, trigger) whenever a new objective arrives, for the log.
    on_plan: Callable[[Plan, str], None] | None = None

    plan: Plan | None = None
    plans: int = 0
    planner_failures: int = 0
    decision_failures: int = 0
    invalid_choices: int = 0
    replans_asked: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    _last_plan_decision: int = -10 ** 9
    _selector_asked: bool = False
    _no_options: bool = False
    _planner_failed: bool = False

    # -- one decision ------------------------------------------------------------------

    def decide(self, state: dict[str, Any], candidates: Sequence[Candidate], *,
               frame_png: bytes | None = None,
               objectives: Sequence[tuple[str, str]] = ()) -> Chosen | None:
        """Plan if a trigger fired, then choose one candidate. None = ask again next tick.

        `DecisionsBudgetExceeded` is left to propagate: the account cannot spend and the
        arm must stop rather than step blind.
        """
        trigger = self._trigger(state)
        if trigger and not self.no_planner:
            self._replan(state, trigger, frame_png)
        ask_objective = bool(trigger and self.no_planner and objectives)
        menu = self.menu.offer(candidates, avoid=(self.plan.avoid if self.plan else ()))
        if not menu:
            # Nothing at all is on offer (everything cooled down): upstream's "no useful
            # option" trigger, which is also the one case the loop has to spend a tick on.
            self._no_options = True
            return None
        questions = {"next_action": choice(self._decide_instructions(), self.menu.criteria(menu))}
        if ask_objective:
            questions["objective"] = choice(OBJECTIVE_INSTRUCTIONS, dict(objectives))
        if self.ask_replan and not ask_objective:
            # Asking "would a new objective help?" in the call that is already choosing
            # one is noise.
            questions["replan"] = noul(
                REPLAN_INSTRUCTIONS,
                "The objective is wrong, finished, or unreachable from here.",
                "The objective still fits and one of these options advances it.")
        try:
            decision = self.decider.decide(self._for_selector(state, menu), questions)
        except DecisionsBudgetExceeded:
            raise
        except DecisionError as exc:
            self.decision_failures += 1
            logger.warning(f"[jev] no decision this tick: {exc}")
            return None
        self.menu.note_decision()
        answer = decision.get("next_action")
        cand = self.menu.resolve(answer.value if answer else None)
        fallback = ""
        if cand is None:
            # JEV answered with a key that is not on the menu. Upstream would execute
            # nothing; taking the menu's own `wait` keeps the loop honest and countable.
            self.invalid_choices += 1
            fallback = f"off-menu choice {answer.value!r}" if answer else "no answer"
            cand = self.menu.resolve(WAIT_KEY) or menu[0]
        if ask_objective:
            self._objective_from(decision, dict(objectives), trigger,
                                 step=int(state.get("step") or 0))
        replan = decision.get("replan")
        asked = bool(replan and replan.is_true)
        if asked:
            self.replans_asked += 1
            self._selector_asked = True
        probs = (answer.probabilities if answer else {}) or {}
        ranked = sorted(probs.items(), key=lambda kv: -kv[1])
        chosen = Chosen(candidate=cand, trigger=trigger, plan=self.plan,
                        probability=probs.get(cand.key),
                        confidence=answer.confidence if answer else None,
                        runner_up=ranked[1][0] if len(ranked) > 1 else "",
                        replan_asked=asked, decision=decision, fallback=fallback)
        self.events.append({
            "step": state.get("step"), "decision": self.menu.decisions,
            "key": cand.key, "entry": cand.entry, "ticks": cand.ticks,
            "probability": chosen.probability, "confidence": chosen.confidence,
            "runner_up": chosen.runner_up, "options": len(menu),
            "objective": self.plan.objective if self.plan else "",
            "trigger": trigger, "replan_asked": asked, "fallback": fallback,
            "latency_ms": decision.latency_ms, "request_id": decision.request_id,
        })
        return chosen

    def record_outcome(self, key: str, *, ok: bool) -> None:
        """What became of the executed entry, for the cooldown map."""
        if ok:
            self.menu.note_success(key)
        else:
            self.menu.note_failure(key)

    # -- the planner -------------------------------------------------------------------

    def _objective_from(self, decision: Decision, options: dict[str, str], trigger: str,
                        *, step: int = 0) -> None:
        """The selector's own objective, in place of a planning turn."""
        answer = decision.get("objective")
        key = str(answer.value) if answer and answer.value is not None else ""
        if key not in options:
            self.invalid_choices += 1
            return
        plan = Plan(objective=options[key], targets=[key] if _looks_like_item(key) else [],
                    reasoning="chosen by the selector (no planner in this arm)",
                    trigger=trigger, step=step)
        self.plan = plan
        self.plans += 1
        self._last_plan_decision = self.menu.decisions
        self.menu.clear_errors()
        logger.info(f"[jev] objective #{self.plans} ({trigger}): {plan.objective}")
        if self.on_plan is not None:
            self.on_plan(plan, trigger)

    def _trigger(self, state: dict[str, Any]) -> str:
        if self.plan is None:
            return Trigger.NO_PLAN
        if self._planner_failed:
            self._planner_failed = False
            return Trigger.PLANNER_FAILED
        if self.menu.decisions - self._last_plan_decision < self.plan_cooldown:
            return ""
        if self._no_options:
            self._no_options = False
            return Trigger.NO_OPTIONS
        if self.menu.replan_due:
            return Trigger.ERRORS
        if self._selector_asked:
            self._selector_asked = False
            return Trigger.SELECTOR
        if self._waypoint_reached(state):
            return Trigger.WAYPOINT
        if self._targets_in_hand(state):
            return Trigger.TARGETS
        if int(state.get("decisions_without_progress") or 0) >= self.stall_limit:
            return Trigger.STALLED
        return ""

    def _replan(self, state: dict[str, Any], trigger: str, frame_png: bytes | None) -> None:
        if self.planner is None:
            return
        try:
            plan = self.planner.plan(task=self.task, state=state, trigger=trigger,
                                     frame_png=frame_png)
        except PlannerError as exc:
            self.planner_failures += 1
            self._planner_failed = self.plan is None   # retry only when there is no plan
            logger.warning(f"[jev] planner failed on {trigger!r}: {exc}")
            return
        self.plan = plan
        self.plans += 1
        self._last_plan_decision = self.menu.decisions
        self.menu.clear_errors()
        logger.info(f"[jev] plan #{self.plans} ({trigger}): {plan.line()}")
        if self.on_plan is not None:
            self.on_plan(plan, trigger)

    def _waypoint_reached(self, state: dict[str, Any]) -> bool:
        plan, pos = self.plan, state.get("position")
        if not (plan and plan.waypoint and isinstance(pos, dict)):
            return False
        try:
            dx = float(pos["x"]) - float(plan.waypoint["x"])
            dz = float(pos["z"]) - float(plan.waypoint["z"])
        except (KeyError, TypeError, ValueError):
            return False
        return (dx * dx + dz * dz) ** 0.5 <= self.waypoint_radius

    def _targets_in_hand(self, state: dict[str, Any]) -> bool:
        plan, inv = self.plan, state.get("inventory")
        if not (plan and plan.targets and isinstance(inv, dict)):
            return False
        return all(int(inv.get(t) or 0) > 0 for t in plan.targets)

    # -- what each model is shown ------------------------------------------------------

    def _decide_instructions(self) -> str:
        if not self.plan:
            return DECIDE_INSTRUCTIONS
        return f"{DECIDE_INSTRUCTIONS}\n\nOBJECTIVE\n{self.plan.line()}"

    def _for_selector(self, state: dict[str, Any], menu: Iterable[Candidate]) -> dict[str, Any]:
        """The selector's state: the parity observation, no image, plus the objective."""
        out = {k: v for k, v in state.items() if k != "frame"}
        if self.plan:
            out["objective"] = self.plan.objective
            out["objective_targets"] = self.plan.targets
            if self.plan.waypoint:
                out["objective_waypoint"] = self.plan.waypoint
        out["consecutive_action_failures"] = self.menu.errors
        cooled = self.menu.audit()["on_cooldown"]
        if cooled:
            out["actions_on_cooldown"] = cooled
        return out

    @property
    def model_calls(self) -> int:
        """One per decision, plus one per planning turn -- and with no planner the
        objective rides inside a decision, so it is not a second call."""
        return self.menu.decisions + (0 if self.no_planner else self.plans)

    def audit(self) -> dict[str, Any]:
        return {"no_planner": self.no_planner,
                "plans": self.plans, "planner_failures": self.planner_failures,
                "decision_failures": self.decision_failures,
                "invalid_choices": self.invalid_choices,
                "replans_asked_by_selector": self.replans_asked,
                "objective": self.plan.objective if self.plan else "",
                "menu": self.menu.audit(), "decider": self.decider.audit(),
                "planner": self.planner.audit() if self.planner is not None else None}


def _looks_like_item(key: str) -> bool:
    """A milestone identity that names an item can double as a target to hold; one that
    names an act ("kill_dragon", "enter_the_end") cannot."""
    return not key.startswith(("kill", "enter", "reach", "visit", "survive", "travel"))
