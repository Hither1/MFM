"""The JEV + Astra arm: a planner consulted on events, a decision model on every entry.

Ported from `rmalde/minecraft-agent` (read 2026-09-27), which plays Minecraft 1.16.5
through Mineflayer with two models and no pixels:

  Astra   `openai/gpt-6-astra` (or `openai/gpt-5.6-sol`) as the PLANNER, called only on
          a trigger -- the waypoint was reached, there is no plan, no candidate is
          useful, or three actions in a row failed -- and answering with an objective.
  JEV     `typesafe/jev-1.13` as the ACTION SELECTOR, called on every loop iteration
          with the state and a filtered list of bounded actions, answering with one of
          them. Not a chat model: OpenRouter serves it at POST /api/alpha/decisions,
          which takes a `state` plus named typed `questions` (choice / noul / score)
          and returns a typed answer per question with per-option probabilities and a
          confidence (`mfm/jev/decisions.py`).

Upstream's own harness is the part that does NOT port. Its models read blocks in loaded
chunks, the world seed, the End portal's coordinates and a Java sensor giving the exact
dragon head position; MCU's chassis is at human parity -- frame, position, inventory, no
voxels (`mcu_worldmodel/grid.py`) -- and the user's decision of 2026-09-27 is that this
arm stays in that lane so its milestones-per-step sit beside the other gen-4 arms. So the
port is the METHOD, not the observation:

  * the bounded action list is the chassis's own atom set (`procedures.ATOMS`), and a
    candidate is admitted only if `parse_actions` expands it against the live state --
    the same precondition check every other arm's plan passes through, so the menu can
    never offer what the harness would refuse;
  * upstream's "blocks in loaded chunks" is replaced by what the runner has itself
    walked and seen: `grid.summary` ([MAP]), the milestone ledger, the last entries'
    outcomes and the harness's notes;
  * upstream's 25-second `bounded()` wrapper is the chassis's per-entry tick cap, and
    its cooldown map -- a failed action dropped from the next candidate list, three
    consecutive failures nulling the plan -- is `mfm/jev/menu.py`.

The planner alone is shown the current view, because that is the parity observation the
logbook, mfm and vista arms all get; JEV reads the symbolic state only, as upstream's
does. `--jev-planner-frames 0` takes the frame away for a text-only twin.

One JEV call per plan entry makes this the cheapest-per-decision arm on the ladder and
the most call-hungry: a 100k-step dragon run is ~1.2k decisions against a few hundred
Astra re-plans (`DESIGN_jev_astra.md` has the measured shape).
"""
from __future__ import annotations

from mfm.jev.decisions import (DecisionError, DecisionsBudgetExceeded, JevDecider, Question,
                               choice, noul, score)
from mfm.jev.menu import Candidate, CandidateMenu
from mfm.jev.planner import AstraPlanner, Plan, PlannerError
from mfm.jev.session import JevSession, Trigger

__all__ = ["AstraPlanner", "Candidate", "CandidateMenu", "DecisionError",
           "DecisionsBudgetExceeded", "JevDecider", "JevSession", "Plan", "PlannerError",
           "Question", "Trigger", "choice", "noul", "score"]
