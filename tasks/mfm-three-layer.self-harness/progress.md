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
- 2026-09-07 23:0x og15 at 3.4k: 12/24 (mine_iron_ore 3318), 0 deaths; turn 1 read og14's
  life by itself (22 previous/ commands; "Prior-life evidence, NOT live results" in
  mine/notes.md, incl. og14's lava pocket and diamond site); it writes NEW scripts
  (descend_north_step, clear_north_step) rather than copying og14's seven from
  previous/life_1/mine/ (they are not in its mine/). Runs to ~07:49.
- 23:0x og20_mfm LAUNCHED (MCU c972f3af): og15's settings + `--own-reflexes` -- the user's
  "tell the self-harness arm what it can write, e.g. reflexes": `mine/reflexes/<name>.py`
  runs every 4 ticks on the live state (+ lava_frac, health_prev, pos_prev, entry,
  queue_len, runner_reflex), prints nothing or one `{stop, note, actions}`; 40-tick
  cooldown, off after 3 failures until edited, at most 4; the contract's added paragraph
  names the four things that killed earlier runs (lava while walking/digging, a 4+ block
  drop, health falling with no lava, any Nether walk with lava in view) as the reflexes
  to write first; the runner's guards stay on. Also the digest note (own + previous):
  the model's first act is its own mine/digest.md. Seeded with og14's life only (og15's
  pair: the difference is the reflex hook + the two contract paragraphs + the Nether
  lock). Verified 23:05: no Traceback, flags on the purple, mine/digest.md written in
  turn 1 (og14's verified places and each script's assumptions), mine/reflexes/ empty so
  far. Read-outs: `cursor_stats` own_reflex_runs / fires / failures, `[REFLEX` notes,
  the scripts under mine/reflexes/, milestones per step vs og15. Tests:
  tests/test_own_reflex.py (3); stage s26_own_reflex 6/6 (a halt reflex stops a raw
  walk 2-4 blocks out with its note and runs its own watch; a broken one is switched
  off after three failures; the turn message lists both).
- 2026-09-08 00:13 og21_mfm LAUNCHED (MCU d505367c, live MFM-grid/MCU fast-forwarded): og20's
  settings + `--no-harness-reflexes --skills` -- the user's three-layer direction (00:0x:
  the memory layer USES our multimodal memory; the skill and reflex layers get meta-level
  advice; example scripts; all packed as a skill the way wz1119 packs its play
  instructions). skills/{memory,procedures,reflexes,harness}/SKILL.md + scripts written
  once per life; the four starter reflexes (lava_ahead, fell, hit, starving) installed
  under mine/reflexes/ and active from tick 1; the runner's guards, escapes, governor and
  nudges OFF; survival.md says so. Seeded with og14's life (the third of og15/og20/og21).
  Ports 9125/9135, cap ~10:13. Verified: no Traceback, flags on the purple, skills/ (4)
  and mine/reflexes/ (4) in the workspace, the contract carries Skills + reflexes + digest.
  Stage s27_starters 8/8 (guards off: fell notes a 6-block drop at the 2-blocks-in-4-ticks
  window; lava_ahead stops a walk 3 blocks short of a lava basin at y 30 with its 1.5%
  band -- the 4% first draft let the walk reach the basin, and a burn's flames read as
  lava, so the drop test runs first). Tests: tests/test_skills.py (5).
  Status of the others at 00:13: og15 5.6k 12/24; og19 4.4k 12/24, 1 death (a cave fight
  at y 30: fight(diamond_sword) took it 11 -> 0 in 160 ticks, the flee came at 0 hp --
  the underground-melee cluster's 4th case); og20 3.6k 12/24, no reflex written yet.
