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
