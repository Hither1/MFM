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
