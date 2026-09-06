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
- Slice 2 DONE: harness -- `governor.check_plan` (CELL_STREAK_VETO 4 null entries of any label
  at an 8-block cell, or STALL_STEPS 600 without a productive one -> a plan that neither moves
  nor opens a screen is dropped for one no-op; SWITCH_STEPS 1200 adds "change the objective";
  `_stall_hint` names the placed table/furnace with a walked route or the farthest walked cell
  within 12 blocks). MFM options (mfm arm only, flags on worldmodel_purple_agent.py):
  `--expect` (EXPECT line parsed from the briefing, echoed as [EXPECTED]/[OBSERVED] next turn,
  MFM_EXPECT_NOTE in the contract), `--frames` (tools/zoom.py written for mfm, MFM_FRAMES_NOTE,
  `frame=` pointers on lava/pour/death/water lines of [KNOWN SITES] via previous.frame_for),
  `--corridors` (previous.corridors_from_log: runs of log sections at y<=14 with no damage/lava/
  death, <=8 blocks apart, >=8 blocks long; merged; up to 3 nearest rendered as DRY CORRIDOR when
  obsidian/diamond/iron is open; MFM_CORRIDOR_NOTE), `--frame-size WxH`. Tests:
  tests/test_watchdog.py 8 green; pins: only chassis_logbook_report_keys moved (+watchdog);
  logbook logs/actions unchanged (the fake's drift keeps its cells short of the streak).
- Replay (tools/grid_replay.py, trail interpolated between per-action positions = a lower
  bound): ob chain 13 runs: 120 blocked go_to, detour available 69 (57%); water refusals 28,
  escape available 27 (96%). Historical half 43 runs: 110 blocked, 72 detours (65%); 41
  refusals, 35 escapes (85%). Historical full/diamond 202 runs: 1148 blocked, 744 detours (65%).
  Gate (>= 50%) passed: S2a stays in the main line.
- Grid edges now only join cells <= 2 apart (a death/portal jump is not a walk).
- Stages written: s17_pond (walk to the rim, fill, refused dig -> escape along the trail, dig),
  s18_reopen (flat + the obf2 hole case, re-open by pose), s19_detour (L trail, 2-high wall,
  go_to detours and arrives).
- Stage s18_reopen: 13/13 green (flat and the hole case: the replayed pose re-opens the table in
  45 ticks after a 6-block walk away; `pose_reopens` 1 each). Stage s17_pond run 1: 9/10 (refusal,
  escape along the trail in 33 ticks, 8+ blocks from the rim; the last dig failed only because the
  stage never equipped the pickaxe -- fixed, rerunning). s19 running.
- Stages green on the engine (MFM-grid/MCU/logs): s17_pond run 2 10/10 (`logs/stages/s17_pond_*`),
  s18_reopen 13/13, s19_detour 8/8 (stalled 7.8 blocks short of D, detoured over 37 walked cells,
  arrived in 162 ticks). Gate for the half run passed.

## 2026-09-07 02:11-02:40 -- og1/og2 launched, then stopped: protocol change

- 02:11 `og1_mfm` (sites+corridors, 22 seeds incl. ob1..obf3) and 02:15 `og2_mfm` (same +
  session-turns 8, 320x180) launched from MFM-grid/MCU. Before the stop og1 showed the
  harness mechanisms in the wild: fill_bucket at the remembered pond (step ~600), the
  refused dig queued the walk along its own trail (15 cells, "8+ blocks from every water
  cell"), one blocked go_to detoured over 9 walked cells. `[MAP]`/`[RECENT]`/
  `[EXPECTED]`/`[OBSERVED]` all present in the turn-2 codex prompt (rollout inspected).
- 02:20 user: no previous-life memory except MFM's own reuse; the earlier mfm reuse was
  contaminated. Both arms stopped with `scripts/stop_arm.py --go` (24/24 pids).
- Slice 3 (this commit): `--sites` mfm option (default off) gates known_sites / corridors
  / frame pointers / `previous/sites.json`; `--corridors` requires `--sites`. The carry
  keeps linking the lives' records under `previous/` (widened from logs/index/episodes/grid
  to the whole record minus machinery: `previous.NOT_CARRIED`), merged `previous/index.jsonl`
  for `tools/episodes.py --previous`. Contract: MFM_PREVIOUS_NOTE rewritten as the carry
  note (the model reads), MFM_SITES_NOTE / MFM_FRAMES_SITES_NOTE only with --sites, the
  chain section's two [KNOWN SITES] sentences only with --sites (`prompts._with_sites`).
  Pins re-recorded: logbook/mfm AGENTS.md lose those two inert sentences (logbook never
  had the block); logs/actions pins unchanged. Tests: test_previous +1 (carry without
  sites), suites test_previous/pins/grid/watchdog/obsidian/retrieve/torch/seal green.
- Launcher renamed `scripts/launch-og.sh` (ARM/GP/PP/STEPS/SESSION_TURNS/WM_EXTRA/OB_SEEDS);
  default seeds = 12 first-gen lives, `--expect --frames --retrieval`.
- 03:10 og4 (step 5577-5657): LAVA AHEAD at 1% of the lower view ((-2991, 11, -5561), y 11);
  the model poured at the rim from 0.3 blocks ("something behind blocks the way back"),
  then `mine_obsidian` broke 3 blocks, none obsidian -- the ob1/ob1b failure (a sliver seen
  from afar is flowing lava: cobblestone after the pour; only SOURCE blocks turn to obsidian).
  The LAVA AHEAD note says "THIS IS THE LAVA THE OBSIDIAN NEEDS" at any fraction; the
  sliver-vs-lake distinction (LAKE_FRAC 8%) lived only in the [KNOWN SITES] digest. Candidate
  harness slice for the next generation: the note itself names a <8% sighting a sliver
  (likely flowing) and a >=30% one a lake; not changed mid-run.
- 03:40 merged dragon-obsidian into spatial-grid. MCU: hither/dragon-obsidian (bunker at the
  first hit bcb009bb, standoff/scoop/mine_obsidian aims 52a452ef, kit milestones open ce4d9404,
  carry-the-workshop doctrine 2eb053fb) merged cleanly in a scratch worktree
  `Collab/MFM-grid-merge-mcu` on branch `spatial-grid-merge` (da93083e) -- NOT in the live
  `MFM-grid/MCU`, which og3/og4 import from; fast-forward it when they end. MFM: origin/
  dragon-obsidian merged in place (tests/test_seal.py, test_obsidian additions, pins); conftest
  gained `MFM_MCU_ROOT` so the suite can run against another MCU checkout; pins re-recorded on
  the merged MCU; 60 tests green (`MFM_MCU_ROOT=.../MFM-grid-merge-mcu`). The MCU submodule
  pointer stays at c6bbf978 until the live worktree moves.
- og3 died at step ~2700 to a zombie in its dark shaft at y 32->23 (health 10 -> 6 -> 2 while
  the plan said "dig down to Y12"; the runner's counter-attack dealt 0 and the sprint back was
  blocked) -- the case the merged bunker slice addresses. It had read the carried logs
  itself (rg over previous/life_*/logs.txt, then sed of life_2/life_3 sections) and cited a
  lava pool near (-3049, 7, -5537) from them.
- 04:05 sliver slice (harness, all arms; MCU spatial-grid-merge 019b91de, MFM 5ef3287): the
  LAVA AHEAD advice under 8% of the lower view names a SLIVER, keeps its cells off the
  no-argument pour's record (`lava_slivers` stat) and asks for a closer 8%+ sighting; at lake
  size the pour sentence stands. tests/test_lava_note.py (2). og4 lost its water on the
  sliver at (-2991, 11, -5561) and is bucket-less at y 10 with ~3000 steps left; og3 found no
  drops at its death site and is rebuilding from cobblestone.
- Next generation (when og3/og4 end): fast-forward `MFM-grid/MCU` to `spatial-grid-merge`
  (bunker at the first hit, standoff/scoop aims, kit milestones open, workshop doctrine,
  --sites off, sliver note), bump the MFM MCU pointer, relaunch og5 (single-turn) / og6
  (8-turn, 320x180) with seeds = 12 first-gen + og3 + og4 (clean lives: no pushed sites).
