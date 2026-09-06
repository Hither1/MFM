# Findings: spatial-grid track (2026-09-06, decision-relevant only)

Evidence: `MFM/MCU/output/ob*` (dragon-obsidian code, 2026-09-06) and `MCU-AgentBeats/output/*`
(148 historical runs). Scripts in `scripts/` reproduce every number from `episode_001/memory/logs.txt`.

1. **Observation is at human parity** (green `src/agent.py:367-375`): pov + position/pitch/yaw +
   inventory/held/GUI/health/food + cumulative stats. No voxels, no mobs. MineStudio's VoxelsCallback
   is green-side, so a map can only be built from: the per-tick position (`agent.py:857`), the macros'
   own reports, mine/use events with their aim, frame detectors (lava %, water, ore), damage/death.
   Positions are exact and the world is deterministic; frame-derived cells are approximate.
2. **The mfm/logbook arm has no spatial surface**: `append_visited` is a no-op unless structured
   (`memory.py:447`), the harness-facts block exists only in the worldmodel branch (`agent.py:3514`);
   the model sees one [STATE] line per action, `_placed` (one estimated cell per item,
   `macros_gui.py:736`), and [KNOWN SITES] (cross-life points, no routes).
3. **go_to is blind** (straight line, stops after 3 stuck ticks, `agent.py:2383`). Historical
   full/diamond runs: 1170 blocked events, median 4.7 blocks short, 30% of targets never reached,
   reached ones median 178 steps later (p90 1036). Half runs: 110 events, 50% never reached. New ob
   runs: 52 events, 33% never, median 456 steps. 35-45% of all go_to calls end blocked in every arm;
   the worldmodel arm's model-written visited.csv changes nothing (0.36 vs logbook 0.35).
4. **Pond trap** (fill, then dig_down refused near water and go_to away blocked): steps from
   `water_bucket +1` to 8 blocks lower, 39 half runs: median 612, p75 825; tail ob3 2981, hd41z 3833,
   hd43z 1545, ob1 948; 7 never. The current code did not fix it (ob3: 9 refusals, 5 blocked go_to).
5. **Remembered-site re-open fails**: the placed cell is a 55-degree-ray estimate; `use_until_gui(item=)`
   aims only there (`agent.py:1540-1566`). obf1: 8 failures, 5 placements, ~10k steps (iron_ingot at
   5973, iron_pickaxe at 16089). obf2 (running): 4 failures by step 1073, 3 more tables; at step 880
   the avatar stood at (-3004.3, 67, -5563.3), inside the column of the remembered cell
   (-3005, 68, -5564), so the estimate was wrong by at least one cell.
6. **Churn is not circles, it is standing still**: ob1/ob2 last quarter: bounding box 5-7 blocks
   (70+ before), 35-42 steps per action, actions = look_abs/use_at/raw/mine_obsidian/gui clicks.
   Historical: median 21% of steps inside 15-action windows with <=20% productive actions, 49/183
   runs above 30%; those actions are 58% GUI micro-ops + 13% raw. 34/153 runs have <30% productive
   actions in the last quarter. The governor counts nulls per (label, 8-block cell) and vetoes only
   `VETOABLE` labels (`governor.py:44`); every loop seen is made of non-vetoable labels
   (equip_hotbar, close_inventory, craft, use_until_gui, gui_click, cursor_to_*, raw).
7. Deaths (ob1b, ob2, ob4: melee mobs in dark tunnels; ob3: lava at the lip) are the concurrent
   session's flee-and-seal slice on `dragon-obsidian`; not this track.

## Image / episodic memory use (2026-09-07, from worldmodel_report.json `codex.*` and the codex rollouts)

- Every turn attaches the current frame (frames_attached = turns). Past frames are seen only through
  `view_image`, which the events stream does not record; the rollout audit counts it.
- mfm chain: view_image per run ob1 17, ob1b 2, ob2 10, ob3 1, obf1 6, ob4 2, obf2 8 (0.02-0.18 per turn);
  `tools/episodes.py` in 16-46% of turns, mostly `--last N --json` (text); `--sheet` 1-10 per run, viewed
  about 1:1; ONE view of a previous life's frame in the whole chain (ob1b, the 52% lake). `[RECALL]`
  (`--retrieval`, text streaks) was off in every run (mfm.recalls = 0).
- Historical arms (views per turn, median): worldmodel 0.37 (38 per run), wmlite 0.33, logbook 0.14,
  direct 0; plus zoom.py 2333 (wm) / 440 (lb) calls. The mfm arm looks 2-10x less than wm did.
- What the views did: correct stall diagnoses (flow pushed the avatar; bucket still selected during the
  dig; crosshair through an underwater gap; furnace one block above the remembered cell; blockage opens
  into the pond), always after several null turns. Never used before a decision (ob2 went to the tainted
  32% sighting without opening its frame; ob3 poured from the lip without opening ep_000097/98).
- Views vs milestones (historical, thirds by view rate): wm diamond 5.6 -> 7.3, wm full 6.9 -> 7.3,
  lb reversed (7.5 -> 4.8, 7.6 -> 7.3): confounded, no usable effect. lad3's retrieval block scored 90
  vs 60-70 but no briefing cited it (PLAN_episodic_memory.md:247-252).

## VISTA (github.com/joshhhhhan/VISTA, MIT, ARC-AGI-3 harness) vs our chassis (read 2026-09-07)

- One thread per game (Codex app-server `thread/start`, or Claude Code `--session-id`/`--resume`); every
  frame after `play` is steered into the thread as a native image (`turn/steer` with a base64 PNG and a
  `<current_visual turn= frame= frame_count=>` label). Frames are 64x64 cells upscaled x8/x16 nearest with
  darkened grid lines (a few KB). Tools: `play`, `inspect` (<=16 views by turn/frame/region, crops upscaled
  to 1024 nearest, a required `question`), `read_pixels` (exact colours), `history` (objective records),
  read/write GUIDE.md (<=64 KB) and WORKING.md (<=16 KB). Shell and file tools are OFF (`shell_tool=false`,
  Claude `--tools ""` + `mcp__game__*` only).
- Prompt is four sentences; the protocol line: "Before each `play`, briefly state what you expect to see.
  Afterward, briefly state all visible changes, expected or not."
- Compaction: Codex `model_auto_compact_token_limit` = window - 72k (272k -> 200k), a forced
  `save_compact_checkpoint` (working memory required), then a fresh thread with the environment record
  (current observation JSON, last action result, level history), the notes, and the current image.
  Claude: 90% of 1M, 600-image cap. No tool-usage statistics or ablations are published.
- Ours: `--session-turns 1` (codex_backend.py:59-70 sets the compaction limit ABOVE the window on purpose
  so the thread cold-starts onto logs.txt; resumed threads read 40k/88k/147k/243k tokens for turns 1-4),
  one 640x360 PNG (77 KB) per turn, shell on (1.2-2.4 commands per turn, mostly grep logs.txt), past
  frames only via `view_image` by path; the mfm sweep keeps only `tools/episodes.py` (no zoom.py).
