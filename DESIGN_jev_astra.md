# The JEV + Astra arm

A port of [`rmalde/minecraft-agent`](https://github.com/rmalde/minecraft-agent) onto the
gen-4 MCU chassis, added 2026-09-27. Built and tested; **not launched** -- each model has
two or three possible routes and the state of every credential is in *The routes* below.

## What upstream does

Read off the repository on 2026-09-27 (`agent.mjs`, `nether-agent.mjs`, `model-relay.mjs`,
README):

| | |
| --- | --- |
| Planner | `openai/gpt-6-astra` (env `PLANNER_MODEL`; `openai/gpt-5.6-sol` the alternative), on chat completions. Called **only on a trigger**: the plan is null, the waypoint was reached, no option is useful, or three actions in a row failed. Sees the state, a `feedback.txt`, the review reason, and the available action descriptions. Answers with a plan object, printed as `PLAN`. |
| Selector | `typesafe/jev-1.13` (alias `~typesafe/jev-latest`), on `POST https://openrouter.ai/api/alpha/decisions`. Called **every loop iteration** with the state and the filtered option list. Not a chat model: the endpoint takes a `state` plus named typed `questions` (`choice`, `noul`, `score`) and returns one typed answer each, with per-option probabilities and a confidence. |
| Actions | Bounded, dynamically generated: mine a named block within 48-96 blocks, craft at an available table, travel to a waypoint, swim/detour/climb, boat control, attack a nearby hostile, eat, equip, sleep, recover air, and `wait` (observe one tick when nothing is useful). Each wrapped in `bounded()` with a 25 s ceiling. |
| Failure | A failed action increments an error count and goes on a cooldown map, excluded from the next candidate list; three consecutive errors null the plan. |
| Perception | **Structured state only, no screenshots** -- inventory, position, health, dimension, stage, recent actions, nearby entities, *blocks in loaded chunks*, the world seed `8398967436125155523`, the End portal centre `-1130, 34, 856`, and a read-only Java sensor giving the exact dragon head position. Mineflayer pathfinding does the walking. |
| Result claimed | The dragon down in under 9 minutes, via the Nether as a shortcut and bed explosions. |

## What ports, and what does not

The **method** ports: a planner consulted on events, a cheap decision model per action,
a bounded menu, a cooldown map. The **observation** does not. MCU's chassis is at human
parity -- "frame + position + inventory, no voxels" (`mcu_worldmodel/grid.py`) -- and the
decision of 2026-09-27 is that this arm stays in that lane, so its milestones-per-step sit
beside the other gen-4 arms instead of being an incomparable upper bound. Concretely:

* **No block data, no seed, no portal coordinates, no entity sensor.** The world knowledge
  is what the runner has itself walked and seen: `grid.summary` ([MAP], built only from
  cells the avatar stood in, bumped into or took damage at), the milestone ledger, the last
  six entry outcomes, and the harness's notes. A waypoint the planner invents is still
  walked by `go_to` over that ground.
* **The bounded action list is the chassis's atom set** (`procedures.ATOMS`), instantiated
  against the live state -- there is no Mineflayer here, and the atoms are what every other
  gen-4 arm composes from.
* **Every option is checked before it is offered.** A candidate is admitted only if
  `parse_actions` expands it against this `info` and a *copy* of this cursor -- the same
  precondition check `act_turn` makes for real. So the menu can never offer what the
  harness would refuse, and the selector never spends a decision on an impossible action.
  This is the one place the port is strictly kinder than upstream, which learns the same
  thing by burning a 25-second attempt.
* **The planner alone sees the current view.** Upstream shows its models no pixels;
  withholding the frame *and* the voxels would leave this arm blind where every other arm
  can see, so the frame stays and `--jev-no-planner-frames` is the text-only twin.
* **The GUI is offered composed, not per click**: `craft`, `place_and_open`,
  `furnace_load`, `furnace_take`, `stow_items`, `open_inventory`, `close_inventory`.
  Upstream's action space is recipe-level too, and the one-call `craft` atom is the
  measured path (a raw-cursor craft cost ~450 steps).
* **Two additions**, both for auditability rather than capability: every decision also asks
  a `replan` noul ("would a new objective help more than any option here?"), which becomes
  a trigger, and every decision is logged with its probability and runner-up so a run can
  be read back for how peaked the selector was. `--jev-no-replan-question` removes the first.

## The code

| File | What |
| --- | --- |
| `mfm/jev/decisions.py` | the selector's client: typed questions, both providers, the state ceiling, usage tally, `DecisionsBudgetExceeded` |
| `mfm/jev/planner.py` | Astra on chat completions (OpenRouter or OpenAI) with a `json_schema` plan, optional frame |
| `mfm/jev/menu.py` | the candidate menu: cooldowns (3/6/12/24 decisions), the consecutive-failure counter, the cap |
| `mfm/jev/session.py` | the two-tier loop: triggers, the decision, the fallback when the answer is off-menu |
| `mfm/jev/smoke.py` | one live call to each model, to tell broken wiring from a broken account |
| `mcu_worldmodel/jev.py` | the chassis bridge: the five hooks, the state block, the menu, `jev_events.jsonl`, and `CodexPlanner` (the planner through `codex exec`) |
| `tests/test_jev.py` | 31 tests, no network: the menu, the triggers, the wire shapes, both routes per model, the arm on the chassis |
| `scripts/jev_no_movement.py` | the fairness check: the other arms byte-identical with this one in the tree |

Everything on the MCU side is gated on `self.jev` or `memory_mode == "jev"`, and the
`AGENTS.md` this arm writes is a *record* of the two system prompts actually used, not a
contract anything read (`prompts.JEV_RECORD`) -- the models here are never shown a
document. Checked, not asserted:

```
$ python scripts/jev_no_movement.py <baseline MCU> <MCU with the arm>
unchanged: 5 system prompts, 2 arms driven 120 steps (logs, AGENTS.md, prompts, actions)
```

## The planner-free variant (`--jev-no-planner`, launcher `NOPLANNER=1`)

A second shape of the same arm, added the same day for two reasons: it isolates what the
planner contributes, and it needs **one credential** -- a Jev key and nothing else.

There is no planner. On exactly the triggers that would have called one, the selector is
asked one more typed question in the SAME decision call: `objective`, a `choice` over the
milestones the ledger has not scored yet (plus an `explore` fallback so the question always
has an answer). The chosen milestone becomes the objective the next decisions are taken
under -- the action in the call that sets it was chosen under the previous objective, which
is the honest cost of folding two turns into one.

It is a **variant of upstream's method, not the port**, and any table must say so: upstream
always has two models. What it changes, and only this: who sets the objective. Same
triggers, same menu, same cooldowns, same state. Model calls drop to exactly one per entry
(`session.model_calls` counts it that way, and the arm is tagged `g4_jev_jevonly_<task>` so
no row implies Astra was involved).

Its objective list is not privileged knowledge: the milestone checklist is in every arm's
turn prompt already (`ledger.progress_block`).

## The call shape

Measured on the gen-4 diamond runs (12,000 steps): the MFM arm made **79** model calls and
executed **504** plan entries; the logbook arm 83 calls. This arm's loop is one selector
call *per entry* plus one planner call per trigger, so the same budget is roughly:

| | MFM / logbook | jev + astra |
| --- | --- | --- |
| 12k-step diamond | 79-83 calls, all large | ~500 selector calls (small) + ~50-150 planner calls |
| 100k-step dragon | ~650 calls | ~4,200 selector calls + ~400-800 planner calls |

Astra at $10/M in, $50/M out is a few dollars per diamond run; JEV's OpenRouter price is
variable (the catalogue lists `-1`), so the real figure comes out of the run -- every
call's `usage.cost` is written to `jev_events.jsonl`.

## How to launch

```bash
cd $U/MFM/tasks/mfm-three-layer.spatial-grid/scripts
DRY=1 bash launch_g4_fasrc.sh jev diamond                          # selector=typesafe, planner=codex
DRY=1 PLANNER_ROUTE=openai bash launch_g4_fasrc.sh jev dragon      # planner on OpenAI instead
DRY=1 JEV_ROUTE=openrouter bash launch_g4_fasrc.sh jev diamond     # upstream's route for both
DRY=1 NOPLANNER=1 bash launch_g4_fasrc.sh jev diamond              # the planner-free variant
```

`MID` names the **planner** (default `gpt-6-astra`); `--jev-selector-model` pins the
selector. The launcher checks the credential each chosen route needs before submitting, and
refuses uncommitted changes under `mcu_worldmodel/` -- so the bridge must be committed in
`$MCU_ROOT` first (`git add mcu_worldmodel/jev.py`; `commit -am` alone will miss it).

## The routes

Each model can be reached more than one way, and the spelling differs per route, so the
arm names them explicitly (`--jev-provider`, `--jev-planner-provider`; `JEV_ROUTE` and
`PLANNER_ROUTE` in the launcher). Every line below was probed live on 2026-09-27:

| | Route | Endpoint / model | State on 2026-09-27 |
| --- | --- | --- | --- |
| **Selector** | `typesafe` *(default)* | `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, `JEV_API_KEY` | **the way in** -- the user has a Jev key; it never touches the OpenRouter budget. $0.042/MTok in, output free; 64k per request but 32k for state + longest question (the client trims to fit, `_fit_state`) |
| | `openrouter` | `POST /api/alpha/decisions`, model `typesafe/jev-1.13` | dead: `403 Workspace lifetime budget of $5000.00 exceeded` (`usage 5001.69`, the wall of 2026-09-12) |
| **Planner** | `codex` *(launcher default)* | `codex exec` through `CodexTurn`, bare model id, the subscription login | wired and reaching the CLI, but the login is stale: *"Your access token could not be refreshed. Please log out and sign in again."* Needs `codex login` |
| | `openai` | `POST https://api.openai.com/v1/chat/completions`, model `gpt-6-astra`, `OPENAI_API_KEY` | dead: `429 You have no credits remaining` |
| | `openrouter` | `POST /api/v1/chat/completions`, model `openai/gpt-6-astra` | dead: the same $5000 cap |

So the selector is unblocked and the planner needs exactly one of: `codex login` (cheapest
-- it is a subscription, not credit), OpenAI credits, or the OpenRouter cap raised.

Installing the Jev key, without it passing through a transcript:

```bash
read -rs -p 'Jev key: ' K && install -m 600 /dev/null ~/.codex-eval/jev.env \
  && printf 'JEV_API_KEY=%s\n' "$K" > ~/.codex-eval/jev.env && unset K
python -m mfm.jev.smoke --decider        # should answer, not 403
```

`mfm/jev/smoke.py` names the route each model took, so a failure says which credential is
the problem rather than "the arm does not work".

When the budget or the login returns, the first thing to check is the abort path -- the arm
ends the episode on a budget 403 rather than stepping blind, which is what 2026-09-12's
arms did for hours.

## What to look at first when it does run

1. `jev_events.jsonl`: the mean menu size, how often the chosen option's probability was
   under ~0.4 (a flat selector is a menu problem, not a model problem), and the runner-up.
2. `jev.plans` against `jev.decisions`: upstream re-plans rarely. A ratio near 1 means the
   triggers are firing on everything and the planner is doing the selector's job.
3. `entry_failures / entries_applied`: the menu promises every option is legal, so a high
   rate is the *outcome* heuristic (`_failure_note`) mislabelling harness notes, not an
   illegal action -- check before believing the cooldown map.
4. Whether `wait` dominates. Upstream's `wait` is one tick; here it is 20, and a selector
   that parks on it is the cheapest possible way to burn a step budget.
