# Task Plan: spatial-grid

## Stable Anchor
- Question: does a harness-maintained 3D cell map (built from exact positions and the runner's own
  events, no benchmark change) remove the navigation losses that eat the dragon budget: blind go_to,
  the pond trap, remembered-site re-opens, and the standing-still churn?
- Target claim: a half-task mfm run on the map-aware code spends fewer steps on those four losses
  (pond escape < 300 steps, reopen by pose succeeds, blocked go_to resolved via walked cells) and
  reaches the lake with more budget left than the ob chain (water at ~700, lake at 7600 in ob3).
- Success criterion: engine stages green (pond escape, reopen-by-pose, detour), replay over the 148
  logs shows walked detours existed for most blocked go_to's, then one half run beats ob3's
  water-to-lake leg and the churn fraction.
- Constraints: purple side only; observation/action/scoring untouched; branch `spatial-grid` in
  `Collab/MFM-grid` (MFM) and `Collab/MFM-grid/MCU` (MCU worktree, from dragon-obsidian 54ed3c9f);
  the `dragon-obsidian` worktree is being edited by another live session (seal slice): never touch it.
- Non-goals: no model-written maps; no hand-written coordinates; no Nether/End; no mob/combat work.

## Current Cycle
- Hypothesis: the four losses share one cause, the harness knows where the avatar has stood and what
  it did there, and throws it away; a map plus three map-aware macros recovers most of it.
- Main uncertainty: whether cell-exact facts (walked cells, placement pose) are enough without
  voxels, i.e. whether the detour over walked cells exists often enough (replay check answers this).
- Next decisive experiment: S1 grid + S2 consumers, engine stages s17-s19, replay over 148 logs.
- Expected signal: stages green in < 300 ticks each; replay: >50% of blocked go_to's had a walked
  cell within 3 blocks of the target's line. Fallback: if detours are rare, keep S2b (reopen by pose)
  and S2c (pond escape) and drop the go_to rewrite.

## Slices
- [ ] S1 `mcu_worldmodel/grid.py`: sparse cell map, per-tick fill (walked/floor, broken, placed +
      opening pose, water, lava, hazard, blocked), `memory/grid.jsonl` persisted, kept by the sweep.
- [ ] S2a map-aware go_to: on block, route via walked cells (BFS) toward the target; note names the route.
- [ ] S2b reopen by pose: use_until_gui(item=) first replays the pose that opened it.
- [ ] S2c pond escape: the water refusal names a walked cell >= 8 blocks from water and walks there.
- [ ] S2d `[MAP]` block in the turn message (5 lines: cell, routes to base/water/table, hazards).
- [ ] S3 cross-life: dry corridors from previous lives' [STATE] trajectories into [KNOWN SITES].
- [ ] S4 churn watchdog: plan-level null streak per cell, label-agnostic veto after 3 null entries of
      any label with no screen open, objective switch after 1200 null steps.
- [ ] Stages s17_pond, s18_reopen, s19_detour; replay tool over the 148 logs; unit tests.
- [ ] Half run on the map-aware code vs ob3/ob4.

## Decisions And Blockers
| Item | Decision | Evidence |
|---|---|---|
| branch/worktree | `spatial-grid` in MFM-grid + MFM-grid/MCU | user 2026-09-06 23:xx |
| dragon-obsidian worktree | owned by the other live session (agent.py edited 23:37, s16 stages) | ls/ps 23:42 |

## Verification Contract
- `cd MFM-grid && PYTHONPATH=.:<pytest_shim> MCU/.venv/bin/python -m pytest tests -q`
- `cd MFM-grid/MCU && bash probes/run_stage.sh -m mcu_worldmodel.stages.s17_pond` (and s18, s19)
- replay: `MCU/.venv/bin/python tools/grid_replay.py <logs.txt>...`

## Next Action
Await the user's go on the slice order (S1+S2 first), then implement S1.
