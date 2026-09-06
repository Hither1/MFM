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
