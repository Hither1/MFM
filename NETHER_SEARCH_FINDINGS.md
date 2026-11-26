# Nether search: why lives stop at 16/24 (milestone 17, kill_blaze)

2026-11-23. Worktree `MFM-frontier` @ dff80cc + uncommitted changes. GPT-6 Astra high, MFM arm, 20k steps per life.

## Question

Every Dragon life that reaches the Nether stops at 16/24. Is the blocker exploration (it does not know
where it has not been), and would a map of unexplored ground help it find a fortress by itself?

## Setup

- **`--frontier`** (new, off by default): the cell map (`grid.py`) also records, per dimension, the ground
  seen within 24 blocks of where the avatar walked. Along 8 bearings from the arrival cell it records how
  far the seen ground runs and the first unseen point. Two `[MAP]` lines name these each turn, and
  `grid.jsonl` gets `coverage` rows. Off, the output is byte-identical to before (recorded pins pass).
- **Task `nether_search`**: start at the old portal exit (-374, 50, -685) in the default world, with the
  fortress task's kit. The respawn point is set on that cell (`--respawn-dimension nether`), so a death
  does not end the search. The text says no fortress has been seen.
- **Fortresses**, mapped from the engine's voxel channel and never shown to the agent:
  - NE: bricks x -338..-126, z -1040..-813; edge ~133 blocks NNE of the start.
  - SW: x -694..-503, z -342..-151; edge ~366 blocks.
- **Lives:** 2 frontier and 4 controls. Two of the controls were frontier lives that a bug ran without the
  frontier lines (the agent's first frame was already in the Nether, so the code never assigned a
  dimension; fixed, with regression tests).

## Results

| Life | Farthest from start | Bearings > 32 blocks | Closest to NE fortress | Deaths | New milestones |
|---|---|---|---|---|---|
| frontier r1 | 191 | 2 | 128 | 2 | none |
| frontier r2 | 142 | 6 | 101 | 2 | none |
| control r1 (ended at 14.8k) | 186 | 4 | 128 | 10 | none |
| control r2 | 156 | 1 | 124 | 5 | none |
| control r3 (bug-run frontier) | 172 | 3 | 127 | 19 | none |
| control r4 (bug-run frontier) | 207 | 5 | **0** (from step ~16k) | 9 | none |

- **No life killed a blaze.** One control reached the NE fortress at ~16k steps, but it had lost its kit to
  earlier deaths (empty inventory) and found no blaze before the budget ran out.
- **The frontier lines were read but rarely acted on:** 41 of 390 turns and 1 of 362 turns referred to
  them. With n = 2 per cell there is no measurable effect.

## Why: travel speed and one guess at a direction, not memory

1. **The fortress cannot be seen from afar.** Render distance is 8 chunks, so the Nether fog ends around
   64 blocks. Frames taken from 61 blocks, facing the fortress, show only haze. No life failed to
   recognise a fortress it had on screen.
2. **Travel is slow: 87–244 steps per block of new distance.** The farthest point stops growing by ~10k
   steps in five of the six lives. Sneak-walking covers 0.05–0.07 blocks per step, against 0.12–0.18 for
   walking. Sneaking is 64–95% of all walking steps in four lives, and digging plus placing blocks is 13–35%
   of steps in five. A typical plan is "crouch, inspect, dig, place" at 20–60 ticks per entry.
3. **The sneaking comes from the shared text,** and it does protect the agent. `skills/harness/SKILL.md`
   says "In the Nether: sneak, no sprint, no moving jump, dig the way down, bridge over lava", and
   `references/survival.md` repeats it. The harness's forced-sneak lock is not active in this arm (its
   built-in reflexes are off). The lives that sneaked least died most (18 and 10 deaths, from falls and
   lava), so the caution buys survival at about 3–4x the step cost.
4. **Direction is a guess.** Lives covered 140–200 blocks, but mostly SE, S/SW or E. About 90 blocks due
   north reaches viewing range of the NE fortress. At the current speed a life tries one or two directions;
   a systematic 8-bearing sweep (~1,600 blocks out and back) needs travel roughly 5–10x faster.

## Implications

- **A memory of unexplored ground cannot pay off here** until safe travel is several times faster or the
  budget several times larger. The 16 → 17 gap is a travel and survival problem.
- **Stale shared text:** `references/skills.md` (`prompts.py:340`) still describes the `explore_nether`
  macro deleted on 10-24, plus "a fortress runs along x or z, one leg per axis". Lives mention the macro in
  2–6 turns but cannot call it. Removing it is a correction, but it changes the recorded baseline output;
  leave it for the next pin re-record.

## Where things are

- **Code (uncommitted):** `MCU/mcu_worldmodel/grid.py`, `agent.py`, `worldmodel_purple_agent.py`
  (`--frontier`, `--respawn-dimension`). Task `MCU_benchmark/task_configs/tasks/nether_search/`. Launcher:
  the `frontier` row and the `nether_search` entry in `slurm/skill_reuse3.sbatch`.
- **Tests:** `tests/test_frontier.py` (10) and `tests/test_respawn_dimension.py`. The recorded-output and
  related tests pass.
- **Instruments:** `MCU/scripts/nether_search_measure.py`, `nether_step_budget.py`, `fortress_in_view.py`.
- **Lives:** `MCU/output/nsf_r{1,2}_nether_search_{none,frontier}`, `nsfx_r{1,2}_nether_search_frontier`.
- **Engine probe and frame sheets:** `/n/netscratch/sham_lab/Lab/$USER/nether_search_probe/`.

## Rerun after the start fixes (2026-11-24, tag `nsf2`)

The first turn now waits for the teleport (the arrival note fired in all four lives), and the start
moved to (-363, 47, -679), 10 blocks from any drop. Same cells: GPT-6 Astra high, 20k steps.

| Life | Farthest | Bearings > 32 | Closest NE | Deaths | Tools lost at |
|---|---|---|---|---|---|
| frontier r1 | 114 | 4 | 61 | 0 | never |
| frontier r2 | 120 | 4 | 128 | 7 | ~574 |
| control r1 | 71 | 3 | 126 | 5 | ~2,607 |
| control r2 | 177 | 5 | 70 | 5 | ~11,001 |

No life killed a blaze or came within 48 blocks of a fortress. The turn-1 walk-off is gone, but one
life still lost its kit by step ~574. The life that never died and kept its kit all 20k steps
(frontier r1) still got no farther than 114 blocks. Kit loss is not the binding constraint;
travel speed and direction are, as above. Over 10 lives in two waves: 0 blazes.
