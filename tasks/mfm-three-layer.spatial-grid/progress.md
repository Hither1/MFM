# Progress

## 2026-09-06
- 23:25-23:45 evidence pass over ob1-ob4/obf1/obf2 and the 148 historical runs (findings.md;
  scripts/). Worktrees created: MFM-grid (spatial-grid @ f0fdb77), MFM-grid/MCU (spatial-grid @
  54ed3c9f), `.venv` symlink to MCU-AgentBeats/.venv. No code yet.
- Running arms (other session's): ob4_mfm (half, died at step 1365 to a mob at y 26, rebuilding),
  obf2_mfm (full, 4 table re-open failures by step 1073).

## 2026-09-07
- Layering (user): harness-level changes live in `mcu_worldmodel/` and apply to every arm
  (grid, map-aware macros, watchdog, presentation); MFM-mechanism changes are flags on the mfm
  arm (`--corridors`, `--expect`, `--frames`, `--session-turns N --frame-size`).
- Slice 1 (harness) DONE: `mcu_worldmodel/grid.py` (walked/floor/blocked/water/lava/hazard/
  placed/opened cells, edges from the walk, BFS routes, `grid.jsonl` beside the log, kept by
  the sweep, carried under previous/); runner hooks: per-tick `grid.observe`, hazards on hits
  and deaths, water from the water guard, lava cells from the guard's sighting, the placed cell
  + pose from place_and_open, the opening pose from every use_until_gui success;
  `go_to` detours once over walked cells (`_goto_stalled`), `use_until_gui(item=)` replays the
  opening pose before the cell estimate (`_pose_replay_tick`), the dig_down water refusal queues
  a walk along the trail to a cell 8+ blocks from water (`_queue_water_escape`); the turn
  message gains [RECENT] (last 6 entries, harness record), [MAP] (grid.summary) and a 2x2
  event-frame sheet as a second image (every arm but direct). Tests: tests/test_grid.py 14
  green; chassis pins re-recorded for prompts/report keys/workspace (+grid.jsonl,
  +attach/events.png) and the recall prompt; logbook logs.txt and actions unchanged.
  MCU commit: see git log (spatial-grid).
