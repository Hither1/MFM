"""One live call to each model, to tell a broken wiring from a broken account.

    python -m mfm.jev.smoke            # both, with the launcher's key file
    python -m mfm.jev.smoke --decider  # the decisions endpoint only

Prints the answer, or the classified failure, naming the route each model took. A
`DecisionsBudgetExceeded` means the wiring is right and the OpenRouter workspace cannot
spend -- which is where that account stood on 2026-09-27 ($5001.69 of a $5000 lifetime
cap, every call 403) and why the arm ends the episode on it rather than stepping blind.
With a TypeSafe key (`JEV_API_KEY`, or a JEV_API_KEY= line in ~/.codex-eval/jev.env) the
selector goes to TypeSafe's own API instead and never touches that budget.
"""
from __future__ import annotations

import argparse
import sys

from mfm.jev.decisions import DecisionError, JevDecider, choice, noul
from mfm.jev.planner import AstraPlanner, PlannerError

STATE = {"step": 120, "position": {"x": -3009.5, "y": 71.0, "z": -5572.5},
         "vitals": "health=20/20 food=18/20", "inventory": {"oak_log": 3},
         "milestones": "2/24 verified",
         "recent_outcomes": [{"key": "mine_ahead", "ok": True, "ticks": 31,
                              "inventory_delta": "+1 oak_log"}]}
MENU = {"mine_ahead": "Hold attack on the block the crosshair is on until it breaks.",
        "open_inventory": "Open the inventory screen and its 2x2 craft grid.",
        "wait": "Do nothing for 20 ticks and see what changes."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decider", action="store_true", help="the decisions endpoint only")
    ap.add_argument("--planner", action="store_true", help="the planner only")
    ap.add_argument("--key-file", default=None)
    ap.add_argument("--provider", default=None, choices=["typesafe", "openrouter"],
                    help="where the selector is served (default: the first whose key is "
                         "present, typesafe before openrouter)")
    ap.add_argument("--planner-provider", default=None, choices=["openai", "openrouter"],
                    help="where the planner is served (default: the first whose key is "
                         "present, openai before openrouter)")
    args = ap.parse_args(argv)
    both = not (args.decider or args.planner)
    rc = 0
    if args.decider or both:
        try:
            d = JevDecider(provider=args.provider, key_file=args.key_file,
                           session_id="smoke")
            out = d.decide(STATE, {
                "next_action": choice("Pick the next action.", MENU),
                "replan": noul("Would a new objective help more?",
                               "the objective is finished or unreachable",
                               "one of these options advances it")})
            a = out.get("next_action")
            print(f"[decider] {d.provider}/{d.model}: {a.value} (confidence {a.confidence}) "
                  f"probabilities={a.probabilities} latency={out.latency_ms} ms "
                  f"cost=${out.cost:.6f}")
        except DecisionError as exc:
            print(f"[decider] {type(exc).__name__}: {exc}", file=sys.stderr)
            rc = 1
    if args.planner or both:
        try:
            p = AstraPlanner(provider=args.planner_provider)
            plan = p.plan(task="Mine a diamond from nothing.", state=STATE,
                          trigger="there is no plan yet")
            print(f"[planner] {p.provider}/{p.model}: {plan.line()}")
        except PlannerError as exc:
            print(f"[planner] {type(exc).__name__}: {exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
