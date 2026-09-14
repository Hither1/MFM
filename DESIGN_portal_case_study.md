# The nether portal as a case study: the one goal no text state can settle

`MCU_benchmark/task_configs/tasks/nether_portal/`. Built 2026-09-09, narrowed the same
day after the first wave (see section 2).

## 1. What was observed, and why it deserves its own task

On the dragon chain the portal is the only goal that is purely geometric. Its frame is a
vertical rectangle four wide and five tall; the four corners are not part of the portal,
so ten obsidian is exactly enough -- two under the interior, two over it, three up each
side -- and the 2x3 interior must be air. A flint and steel struck inside a correct frame
opens it. Struck inside a frame that is one cell wrong, it starts a fire.

A dragon run measured 2026-09-08 (arm `of3r`) did this: it carried ten obsidian, placed all ten, wrote
ten consumptions into its own notes, and could not tell that the shape was wrong. Its own
record said the obsidian had been spent; it did not say into which cells, and nothing in
the environment says so either. It then mined twenty-two times to take blocks back and
re-place them, set itself on fire for two hearts while lighting, and spent **8,900 steps
and 812 log entries** between holding the obsidian and standing in the Nether.

Those figures are **as reported, not re-derived here**: the `of*` arms' episode data
lives in the `MFM-grid` tree on another host, and nothing under `MFM`, `MCU` or the
scratch space on this filesystem holds an `of3r` run. Nothing in the task's design
depends on the exact numbers -- the shape of the failure is what it is built around --
but a later reader should not take them for something read off a log here.

That is not a planning failure and not a perception failure. It is a bookkeeping failure
with no channel to detect it in: `inventory` says how many obsidian are left, `use_item`
says how many placements happened, `mine_block` says how many came back, and not one of
them says *where*. The only way to check is to look at the frame -- which makes this the
cleanest scenario in the benchmark for the claim the campaign exists to test, that
keeping the pixels buys something the text summary threw away. See
`DESIGN_recall_probes.md` for the rest of that argument; this task is its most concrete
instance, because here the un-expressible feature is not a subtle texture, it is a list
of ten integer triples.

## 2. The task

Everything before the portal -- wood, stone, iron, diamonds, finding lava, quenching it
-- is cut away, **and so is scarcity**. The agent starts on a cleared 21x21 stone pad
holding **64 obsidian, 64 cobblestone, a flint and steel and a diamond pickaxe**, and
the goal is a portal and a step through it.

The task asks one thing and only one thing: can the agent arrange blocks into a shape
that no statistic it can read describes? Nothing is scarce, nothing is timed, and there
is no way to be stuck. Every failure is a failure to put blocks in the right cells and
to notice that they are not.

**This is a deliberate narrowing (2026-09-09), made after the first wave.** The original
version handed out exactly ten obsidian, the minimum, so that a misplacement had to be
mined back with the pickaxe. That made the episode partly a measurement of *recovery
cost*, and the wave showed it was the wrong variable: all four arms failed, the
fourteen-block control did **worse** than the ten-block one, and the failing arms were
not stuck for blocks, they were re-striking identical wrong frames. Supply was never the
binding constraint, so supply is gone -- along with the health column, which recorded
that lighting a fire you are standing in hurts and nothing else.

Design choices and the reason for each:

| choice | why |
|---|---|
| a flat stone pad, cleared five blocks up | uneven ground is a second cause of misplacement, and this task is about the first one. Obsidian on grey stone is also the most legible thing a vision check can be asked to count |
| `doMobSpawning false`, clock stopped at day, everything within 48 blocks killed | nothing may walk into the frame or into the measurement |
| `keepInventory true` | a death should not end the episode as a supply problem |
| a full stack of obsidian | a portal needs ten. Handing over sixty-four makes it impossible to fail for want of a block, which is the only way the shape is the sole variable |
| a full stack of cobblestone and a diamond pickaxe | something to stand on to reach the upper rows, and a way to move any block already placed. Both remove "stuck" as an explanation for failure |
| `world_seed: 42`, `spawn_biome: plains` | two arms are only comparable in one world. `MCU_WORLD_SEED` still sweeps it across a campaign |
| the recipe is spelled out in the task text | the observed failure is not ignorance of the recipe -- the arms place blocks in portal-shaped attempts. Stating it isolates bookkeeping from knowledge |
| the text does **not** say that only looking can verify the cells | that would be the hint under test |

## 3. What is scored, and by what

The milestone ledger carries two bits and **neither of them is the measurement**:

- `place_obsidian` (`use_item: obsidian`) -- the build has begun.
- `enter_nether` (`mine_block: netherrack`, gated `after: [place_obsidian]`) -- the only
  event that proves a portal actually worked. It matches `ender_dragon`'s own rule, so a
  portal here is the same event as a portal there.

There is deliberately **no `use_item: flint_and_steel` milestone**. That statistic moves
on a strike into a broken frame, and an agent told "milestone verified" for setting
itself on fire would be worse off than one told nothing -- the config would be *causing*
the failure it is meant to measure. `tests/test_portal.py` pins its absence.

The measurement is `portal_report.json`, written by `mcu_worldmodel.portal_probe` from
the engine's privileged voxel channel. Four numbers no agent-readable statistic can give:

| number | what it means |
|---|---|
| **cells right at strike 1** | how many of the ten required cells held obsidian the first time the flint and steel was used. An agent that knows where its blocks are strikes at 10/10 |
| **blocks left in the interior** | blocks standing in the 2x3 that has to be air. The error an agent can neither see nor name |
| **placed into unused cells** | obsidian put in a cell the finished frame does not use: the bookkeeping error, made visible |
| **repeat strikes** | strikes that re-fired a geometry an earlier strike had already failed with. This is the sharpest column the first wave produced, and it is the one to read |

plus the full placement history -- every cell, with the step it was filled and the step
it was emptied -- which is the ground-truth version of the record the agent kept without
cells. `scripts/portal_stats.py` turns a directory of episodes into the table;
`--cells` prints the history.

The probe also saves a PNG at every strike, at the first moment a legal frame exists,
and at the end, into `portal_frames/`. A number in a JSON file is not a check a person
can make about a geometric claim, and the failure this task measures is one you can see
in a single frame.

## 4. The privileged channel, and why it stops at the host

`action["voxels"] = [x0, x1, y0, y1, z0, z1]` makes the client answer with one record per
non-air block in that box. Read out of `EnvServer` (decompiled 2026-09-09), four
properties that the scorer depends on and that nothing raises about if they are wrong:

- coordinates are **offsets from the player's block position**, not absolutes, so a trace
  has to add `floor(player x/y/z)` back before it can accumulate anything across steps --
  the agent walks while it builds;
- **air is never reported**, so "this interior cell is clear" is proved by a cell being
  inside the queried box and missing from the answer, and cannot be proved at all for a
  cell the box did not cover. `portal.World` therefore keeps two maps, `solid` and
  `seen`, and a frame with any unknown cell is never scored complete;
- the loops are `range(x0, x1)`, so **the upper bounds are exclusive**;
- names are full ids (`minecraft:obsidian`), from `ResourceLocation.getFullName()`.

None of this reaches the agent. `voxels` is not in the green runner's
`INFO_PASSTHROUGH`, the callback writes nothing into `info`, and both facts are pinned by
tests. This is not fastidiousness: an environment that can say "your left column is one
block short" has answered the question the task asks.

Because all four properties came from a jar and not from a run,
`mcu_worldmodel.portal_voxel_probe` settles them live -- does the key come back, are the
offsets relative, is air omitted, is the top bound open, and does a portal assembled by
`/setblock` read back as complete and then as lit. **Run it before the wave.** Getting
this wrong does not crash anything: every frame scores 0/10 and a wave of arms looks
like it failed at geometry when it failed at plumbing.

**Run 2026-09-09, job 45606038: 9 checks, 0 failed, in 1 m 58 s.** The channel behaves
exactly as decompiled -- the pad's stone floor came back at the player's feet minus one,
the air over it came back as nothing at all, a `/setblock` marker three east landed at
the cell the arithmetic predicted, a box stopping at that column excluded it, and a
`/setblock` frame read 10/10 complete and then lit once fire was put inside. The kit
arrived as configured (10 obsidian, flint and steel, 16 cobblestone, diamond pickaxe).

## 5. Three traps in the plumbing, and what each would have cost

None of these is findable by reading the scorer; all three produce a report that looks
healthy and means nothing.

| found | fix |
|---|---|
| **`MinecraftSim._wrap_obs_info` accumulates info keys and never clears them** -- it copies every key it has ever seen into one `self.info` and returns a copy. So `info["voxels"]` survives from the step that requested it into every later step. Folding it in again would place the same block list against a new player position, filling the map with obsidian that was never there and inventing "placements" every time the agent walked | the callback records whether it *asked* on the step it is reading, and ignores `info["voxels"]` otherwise |
| **a strike scored from the last cadence sample can be up to `every` steps stale.** An agent that places its tenth block and strikes four steps later would be recorded as having struck at 9/10 -- and "cells right at strike 1" is the headline number | a strike is held, forces a voxel query on the very next step, and is scored from that. A strike on the final step is resolved at close from what is known |
| **`use_item: flint_and_steel` moves on a strike into a broken frame.** As a milestone it would tell the agent its portal was fine, which is the failure being measured -- the config would be causing its own result | there is no such milestone, and `tests/test_portal.py` pins its absence |

## 6. How to run

```bash
# 0. settle the voxel channel first (2 minutes, no model calls)
sbatch slurm/portal_probe.sbatch

# 1. the arms
sbatch slurm/arm.sbatch mfm     portal_mfm     nether_portal 6000
sbatch slurm/arm.sbatch logbook portal_logbook nether_portal 6000
sbatch slurm/arm.sbatch arc     portal_arc     nether_portal 6000

# 2. single process, no A2A split
PYTHONPATH=. python3 -m mcu_worldmodel.run --task portal --steps 6000 --output output/p1

# 3. score. NOTE the reports land under the GREEN server's output tree, not the arm's:
#    map arm -> dir with  grep '\[portal\] wrote' logs/<arm>_green.log
scripts/portal_stats.py output/2026*_*/nether_portal
scripts/portal_stats.py --cells output/2026*_*/nether_portal   # placement history
```

The task name is in `Agent.LONG_TASKS`; without that `--max-steps` is silently
clamped to 1,200, which on this task ends the episode mid-build.

The probe runs on `$HOME/miniforge3/envs/minestudio/bin/python`, the interpreter
`worldmodel.sbatch` and `solo.sbatch` use, overridable with `MCU_PYTHON`. Not
`.venv/bin/python`: in this checkout `.venv` is a symlink to another tree whose
uv-managed interpreter is gone, so that path is a dangling link and the job exits in
nine seconds with `No such file or directory` and an empty stderr. `slurm/aba_probe.sbatch`
still points at it and would fail the same way.

`tests/test_portal.py` covers the geometry, the voxel arithmetic, the trace, the
callback and the two configs with no engine (38 tests).

## 7. What the first wave measured (2026-09-09)

Four arms, 6000 steps each, on the original ten-block version. **No arm built a legal
frame, lit a portal, or reached the Nether.**

| arm | kit | strike 1 | best | blocked | wasted | strikes | repeats |
|---|---|---|---|---|---|---|---|
| arc | 10 | 4/10 | 6/10 | 0 | 7 of 13 | 2 | 0 |
| mfm | 10 | 6/10 | 6/10 | 2 | 4 of 10 | 5 | 4 |
| logbook | 10 | 5/10 | 7/10 | 0 | 3 of 10 | 7 | 5 |
| mfm | 14 | -- | 4/10 | 2 | 6 of 10 | 4 | 2 |

**The pass rate is a floor; the repeat column is the finding.** `mfm` struck five times
at *exactly* 6/10 with the *same two interior blocks* every time. `logbook` struck seven
times, six of them at exactly 7/10. They re-fire an identical failed geometry because
nothing available to them says which cell is wrong -- which is the claim this task was
built to make, arrived at from the other direction: not "the agent could not fix its
mistake" but "the agent could not tell it had made one".

Three things this settled:

- **Supply was never the constraint.** The fourteen-block control did worse than the
  ten-block runs. Hence the narrowing in section 2.
- **The macro did not solve it for everyone here.** `arc`, `mfm` and `logbook` made zero
  `build_portal_frame` calls in this wave (counted in the chassis `logs.txt`, not the
  adapter's stdout, which does not carry them). They hand-built. **This does not carry
  over to the narrowed task -- see section 8.**
- **The channel was healthy** -- 44 to 105 act turns in 6000 steps, ~600 voxel samples
  per arm, none unreadable. Not the silent no-op trap.

It also found a real bug in `macros_nether.build_portal_frame`, from the one arm that
used it: it refuses to *resume* a frame it started, once the filler leaves the hotbar
("keep 4 cobblestone in your HOTBAR") and again once obsidian drops below its threshold
("8 obsidian carried; a frame needs 10"). A half-built frame cannot be continued by the
macro that built it. Worth fixing before the next wave.

**Still open.** At zero for four the headline outcome does not discriminate between
memory conditions -- only the strike and waste columns do. Whether the narrowed version
produces a gradient, or whether every arm still fails, is the next thing to find out.

## 8. What the narrowed task measured (2026-09-09, second wave)

Three arms, 6000 steps, full stack. **The task now discriminates.**

| arm | legal frame | lit | Nether | strike 1 | strikes | placed | into unused cells |
|---|---|---|---|---|---|---|---|
| arc | step 231 | step 240 | step 364 | **10/10** | 1 | 14 | **0** |
| mfm | step 241 | step 376 | step 2398 | **10/10** | 1 | 14 | **0** |
| vista | never | -- | -- | 8/10 | 8 | 55 | 45 |
| logbook | never | -- | -- | 7/10 | 2 | 14 | 4 |
| direct | never | -- | -- | 6/10 | 1 | -- | -- |

**`direct` row (2026-09-11, job 46078952, cancelled at step ~2200 of 6000 and recorded
as a 6/10 failure).** Same worktree, task, budget and base model (gpt-5.6-sol) as the
other three; the no-memory rung. It struck once, at step 723, into a 6/10 frame with a
clear interior, and never touched the frame again. From step 1378 it planned
`scan_around` on almost every turn; the governor's stall rule dropped each as a no-op,
and with only a rolling window of its own replies the arm never registered the drop and
proposed it again -- 608 dropped `scan_around` plans in 638 codex turns by the time it
was cancelled (mfm needed 30 turns for the whole episode). The step rate had fallen to
~200 per 25 min, i.e. ~8 h and ~4,000 model calls to reach 6000 with the frame
unchanged, so the run was stopped. No `portal_report.json` was written (the probe writes
at close); the strike and the stall are read from `logs/portal2_direct_{green,purple}.log`.
Placed/wasted columns are therefore blank. Treat the row as "failed, one strike, 6/10" and
not as a 6000-step episode.

**THE FULL STACK UNLOCKED THE MACRO, AND THAT IS MOST OF THE DIFFERENCE.**
`macros_nether.build_portal_frame` refuses below fourteen obsidian in its "full" mode, so
the ten-block wave could barely reach it -- zero calls from `arc`, `mfm` and `logbook`.
With sixty-four, every arm used it: `arc` 2 calls, `mfm` 4, `logbook` 1, `vista` 13.
The macro computes the fourteen cells itself, remembers which are filled, skips those,
and reports "placed 4 of 4 obsidian. Done." So the second wave measures **how well an arm
drives the macro**, much more than it measures the arm's own spatial bookkeeping. The
predicted risk in the original design -- "the macro may solve it for everyone" -- did not
materialise at ten blocks and largely did at sixty-four. Read the 2-for-4 with that in
mind, and note that the two failures still failed *with* the macro in hand.

`arc` is the clearest case. It solved the task with **zero image views and zero files
written** (`stream.image_views: 0`, `file_changes: 0`, one session, 511 s of model time,
11 `./act do` batches). It never looked at what it was building and never wrote a note;
it called `build_portal_frame` twice and `light_portal` once. On this task the memory
that mattered was the macro's, not the arm's. The same "never opens a frame" finding is
on record for `arc` on diamond and dragon -- see the arc-arm notes -- so it is the arm's
habit, not an accident here.

**VISTA is the sharpest failure in the set, and the most awkward for the hypothesis.**
It is the arm that keeps pixels rather than text, so it should own this task -- and it
finished two blocks short. Its frame was 8/10 with a clear interior; the only cells
missing were the two in the middle of the top row. It struck the flint and steel **eight
times between steps 2,061 and 5,550, and the geometry never changed once**. It placed
fifty-five obsidian to get there, forty-five of them into cells the frame does not use,
and mined four back. Holding the frames did not tell it which two cells were empty. n=1,
and worth repeating across seeds before it is leaned on.

`figures/portal_frames_built.png` draws all three frames cell by cell. No screenshot
does: the agent's camera never steps back from what it is building, so every saved PNG
is a close-up. The picture worth having came from the voxel channel, not the pixels.

Removing scarcity turned 0-for-4 into 2-for-3, which is the gradient the first design
could not produce. `arc` and `mfm` each struck the flint and steel exactly **once**, at a
frame that was already 10/10, and walked into the Nether. The benchmark scored both
100/100 and `logbook` 50/100, and here that agrees with the geometry.

**`logbook`'s two strikes were 4,678 steps apart at the identical 7/10 geometry**, with
the same three blocks standing in the interior both times. It had 64 obsidian and a
diamond pickaxe; fixing it was three clicks. It never did, because nothing it could read
said which cells were wrong. That is the claim of this task in one line, and it is now
made against an arm that could not have been short of anything.

**The winners were precise, not bulky.** All three arms placed exactly fourteen blocks
-- the ten required cells plus the four corners, which is what both the macro and a
careful hand-build do. `arc` and `mfm` put all fourteen where they belong and wasted
nothing. `logbook` put four in the wrong place, three of them inside the 2x3 that has to
be air, and never moved them.

**A scoring bug had to be fixed before that could be read, and it inverted the answer.**
`PortalTrace` keyed its map by absolute cell and kept folding voxel answers after the
agent stepped through. Nether coordinates are Overworld coordinates over eight, so the
two do not collide -- they accumulate -- and the Nether side of any portal is a
game-generated, perfectly legal, already-lit frame. `best_fit` therefore ranked *the
engine's own portal* above the agent's, and both winners came back with
`best_frame.anchor` in the Nether, which scored all fourteen of their real placements as
"into a cell the frame does not use". Reported at first as 28-29 blocks placed with half
wasted, and read as bulk beating precision: the exact opposite of what happened.
`PortalTrace.observe` now refuses every sample after `dimension_step`, and
`test_the_nether_side_portal_cannot_be_scored_as_the_agents_work` pins it. Nothing about
the timings was affected -- `first_complete_step`, `first_lit_step` and the Nether
arrival all predate the transit -- so the pass/fail column was right throughout.
