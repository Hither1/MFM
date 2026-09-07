# Progress: self-harness

- 2026-09-07 08:3x task opened; see task_plan.md.
- 09:3x S1-S4 done (MCU spatial-grid-merge ed34754c, live MFM-grid/MCU fast-forwarded):
  `--atoms` (procedures.ATOMS, 28: the closed-loop aims and walks, the GUI cursor and
  the one-call craft, placements, the bucket, watch/pillar/eat/throw), `--own`
  (mine/ kept by the sweep and carried; mine/procedures/<name>.py run in a subprocess
  with the state on stdin, its printed plan parsed with the same caps, depth 1; the
  [OWN] block lists scripts with call counts; failures are one [NOTE]). Thin contract
  with atoms+own: 16.7k characters (31k before). tests/test_own.py (7); the list of 13
  test files: 84 pass. Stage s22_own (real sim): the rig's chop.py ran as one [ACTION]
  chop(...) entry and broke the block, boom.py failed with its stderr line, chop_tree
  was refused under the atoms, mine/ survived the sweep -- 8 checks, 0 failed.
- 10:10 og14 at 1.8k steps, 11/24 (iron_ingot at 1064), 0 deaths, 3.1k steps/h (27 codex
  turns in 37 min, about 2 min each -- the exec cells are long: `mine/notes.md` holds 20
  dated observations by step 1738). FIRST OWN SCRIPT between steps 1525 and 1625:
  `mine/procedures/north_stair.py`, one staircase step north (equip_hotbar 1, four
  forward ticks, watch y_below, three aimed attack-40 bursts at pitch 8/47/64, finish at
  pitch 60), with guards (cleared=true, yaw 180 +-5, stable y, cell centre +-0.25, diamond
  pickaxe in hotbar slot 0) -- written after the sequence "worked twice by hand"
  (1309->1407, 1407->1525 in its notes), as the contract asks. Called at 1736 (246 ticks):
  advanced 0.86 without descending (its own note: the assumed lower floor was not there);
  at 1781 the script's guard refused ("standing near the cell center") = one [NOTE] FAILED,
  nothing ran, the rest of the plan ran. It fixed the hotbar-slot assumption (state slots
  0..8, equip_hotbar 1..9) in the script itself. Evidence for S5's mechanics: write, guard,
  call, revise, all inside 40 minutes; the cost is wall-clock (3.1k/h vs og13's 6.8k/h).
- 21:4x og14 FINAL (wall cap 19:30, 26412 steps, 467 codex turns): 15/24, 0 deaths --
  mine_iron_ore 3267, mine_obsidian 15505, flint_and_steel 16142, mine_diamond_ore 25730.
  Control og13 (thin, fixed library, scratch): 14/24 at 27755 steps, 2 deaths, last
  milestone 13358, never reached obsidian. Own harness: 7 scripts under mine/procedures
  (north_stair 55 calls, west_level 47, north_level 37, gravel_cycle 25, tunnel_gravel 8,
  west_foot_step 4, west_gravel_face 1), own_calls 177 / own_failures 2 (report cursor;
  172 `[ACTION] <own>(` lines in logs.txt). toolcalls.py: 2.8 commands/turn, episodes.py
  in 11% of turns, view_image 223 calls (codex counter), 53 png reads. compare.py: goto
  100/13/5/0, gov 172, churn 0.19 (og13: 30/3/8/0, 121, 0.07). Read: the self-built
  harness reached obsidian from scratch where the fixed thin library (og13) did not; one
  seed, so the per-step gap (obsidian at 15.5k) is the claim to test across lives (S6).
- 21:49 og15_mfm launched from the live MFM-grid/MCU (fast-forwarded to 3f8f541f, which
  adds `EXTRA_ONLY=1` to launch-og.sh: the seeds are EXTRA_SEEDS alone): og14's settings
  (thin + atoms + own, gpt-6-astra high, 320x180, 60k, session-turns 0 + compaction,
  10h cap ~07:49) seeded with og14's life ONLY (`EXTRA_SEEDS=.../og14_mfm/episode_001/memory`),
  ports 9122/9132, codex home under codex-homes/ (data3). Verified at 21:52: no Traceback,
  purple args carry `--reasoning-effort high --thin --atoms --own`, previous/life_1 holds
  og14's episodes, grid, index, logs and mine/ with the 7 scripts; turn 2 running.
  A first launch at 21:46 (ports 9121/9131) missed `--reasoning-effort high` (medium by
  default); stopped by pid after 4 minutes, its output and codex home set aside as
  `og15_mfm.medium-abort`, its stale wall watchdog (pid 17409) killed by pid.
