# Plan-grain recall, the two missing episode views, and the six-life read-outs

Worktree `MFM-grid-wk-recall`, branch `spatial-grid-recall` (based on `spatial-grid`
@744d078). Three commits: `3de1122` (A), `42aa5e7` (B), `729d42d` (C).

Everything below was run against the finished records of the six full-task lives
(`MFM-grid/MCU/output/{of1,of2,of3,of1r,of2r,of3r}_mfm/episode_001/memory`) read-only.

## The headline, first, because it contradicts the brief

The brief said the model "re-issued the same [PLAN]/EXPECT 15-30 turns running with zero
movement". At the grain of `logs.txt` sections that is exactly what it looks like: runs
of 8-24 consecutive sections carrying one identical EXPECT with `moved=0.00`. At the
grain of MODEL TURNS it does not happen at all: **653 such section runs across the six
lives, of which 652 sit inside ONE model turn** (`stall.py`, table below), and **not one
run of three consecutive turns re-issuing an identical EXPECT exists in any of the six
lives** -- with or without the movement condition.

What produces the appearance is the harness reprinting the current plan under every
entry of that plan, and plans running long: of3r turn at `Action 1232` issued a plan
with **21 entries** (`Plan Step 1/21` ... `21/21`, steps 24067-24188, moved 0.0), and
of1r has one of 24. So the plan-grain stall is real but its unit is *one long plan that
achieved nothing*, not *N turns saying the same thing*.

Consequence for A: `plan_repeats` as specified (identical text at turn grain) is
implemented and tested, and it **would have fired zero times in all six lives** (checked
at every turn prefix of every life, 2,855 turn prefixes: 0 fires). Turn-to-turn wording
is near-identical but not identical -- consecutive EXPECT similarity median 0.48, and the
longest run above 0.80 similarity in of3r is 14 turns (101-114), which was *descending
steadily* (Y37 -> Y25, inventory changing every turn) and correctly reports nothing.
If the parent wants the line to fire, the minimal change is a digits-stripped key (the
`_note_keys` treatment already used for repeated notes) plus letting the run be counted
over ENTRIES of one plan rather than turns; both are one-line changes to `_plan_key` and
`turns_of`, and neither was made here because it is a scientific-direction call.

## A. `mfm/memory/retrieve.py` -- plan-grain recall (commit 3de1122)

### A.1 storage: nothing was added

Per-turn briefings are already stored. `EpisodeStore.plan` (`mfm/memory/store.py:130`)
keeps `{"turn": agent.codex.calls, "briefing": ..., "plan": ...}`, `_new_episode`
(`store.py:243-254`) writes `turn` into **every** episode's `action.json` and
`briefing`/`plan` into the first entry of each turn. The EXPECT line lives inside the
plan text (the model writes it after `[PLAN]`; `mcu_worldmodel/agent.py:4051`).

Measured on of3r: 2,256 `action.json`, **all** with a `turn`; 388 distinct turns; **all
388** carry a `plan`, and all 388 contain an `EXPECT:` line. `index.jsonl` rows carry
none of it.

So the minimal change was a reader, not a writer: `turns_of` reads the tail's
`action.json` exactly as `repeated_note` reads the tail's `outcome.json`. Benefits: the
index does not grow, the two `episodes/`+`index.jsonl` pins (`tests/pins/mcu_episodes.txt`,
`kicad_episodes.txt`) do not churn, and the six finished lives can be analysed with the
same code. A row that already carries `turn`/`expect`/`plan` keys is used as it stands,
so a future caller that does put them in the index needs no change here.

### A.2 the functions

- `retrieve.py:388 turns_of(rows, root, recent=200)` -- index rows grouped into the model
  turns that issued them: `turn`, `expect`, `plan`, `moved` (summed from the rows'
  summaries), `inventory` (any row tagged `milestone`/`inventory_changed`),
  `first_step`/`last_step`, `rows`.
- `retrieve.py:445 plan_repeats(turns, min_len=3)` -- pure; the run of consecutive turns
  ending at the latest that share the normalised EXPECT (fallback: plan text) while the
  run moved < 0.5 blocks in total and changed no inventory. A turn that moved or banked
  something *ends* the run rather than disqualifying the turns after it.
- `retrieve.py:484 plan_repeat_line(run, root, limit=120)` -- one line, e.g.
  `The same EXPECT 3 turns running (turns 1-3, steps 100-315) with moved=0.0 and no
  inventory change: \`...\`. Latest frame: episodes/ep_000007/observation/image.png`
- `retrieve.py:500 recall_block(...)` -- new kwargs `plan_repeat_min=3`,
  `plan_recent=200`; the plan-repeat line is prepended as the FIRST line when present.
  No MCU call-site change is needed (`mcu_worldmodel/episodes.py:410` still compiles).

### A.3 hotbar noise

`retrieve.py:59-66` adds `hotbar_only(kind)` (a kind matching `^hotbar\.\d$`,
`equip_hotbar`, or a `+`-joined key set made only of those) and `streaks`
(`retrieve.py:176`) skips such kinds unconditionally. of3r pressed `hotbar.6` 67 times,
`hotbar.1` 28, `hotbar.2` 19 -- these were the source of the "`hotbar.6` changed nothing
in its last 61 calls" line.

**The one-line MCU change that would make it explicit** (not made; MCU is out of scope):

    # mcu_worldmodel/episodes.py:158
    RECALL_IGNORE_KINDS = frozenset({...}) | {f"hotbar.{i}" for i in range(1, 10)}

With that line the exclusion would be the caller's declared policy; without it,
`retrieve.streaks` enforces it for every caller.

### A.4 verification

    cd MFM-grid-wk-recall
    MFM_MCU_ROOT=.../MFM-grid-merge-mcu .../MFM-grid-merge-mcu/.venv/bin/python \
        -m pytest tests/ -q -p no:cacheprovider

- `tests/test_retrieve_plan.py` (new, 3 tests): a three-turn repeat is reported and is
  the first line of the block; a repeat with movement and a repeat that banked something
  are not; the PLAN fallback; a `hotbar.6`/`equip_hotbar` streak produces no line while a
  real kind in the same rows still does. **3 passed.**
- Whole suite: **11 failed, 137 passed, 1 skipped**. The same 11 failures occur on
  unmodified `HEAD` (checked by restoring `git show HEAD:mfm/memory/retrieve.py` and
  re-running: 11 failed, 132 passed, 1 skipped, identical names). They are environment,
  not this change: 6 are `ModuleNotFoundError: gym_codex` (the CUA-KiCad submodule is not
  checked out in this worktree) and 5 are skew against the uncommitted MCU edits in
  `MFM-grid-merge-mcu` (`test_skills`, `test_own_reflex`, `test_grid`, `test_carry`).
- `tests/test_store.py::test_mcu_store` passes, which is the evidence that the store's
  `episodes/` tree and `index.jsonl` are byte-identical to the pin.

## B. `mfm/memory/tools/episodes.py` -- `--ores` and `--y-profile` (commit 42aa5e7)

- `--ores` (`episodes.py:163-221, 397`): episodes whose `outcome.json` `events` say
  `mine_block`/`pickup` of an ore, or whose `inventory_delta` gained one. `craft_item` is
  excluded (a furnace output is not a place where ore was found). ORES = the eight bases
  (`iron_ore`, `gold_ore`, `diamond_ore`, `coal_ore`, `redstone_ore`, `lapis_ore`,
  `emerald_ore`, `ancient_debris`) plus any `deepslate_` prefixed form. One line each:
  id, step, y, position, life (under `--previous`), what, frame path.
  There are **no harness ore-sighting notes** in these records -- `grep` over the six
  lives' `outcome.json` finds no "in view"/"sighted" ore note -- so mined/picked-up is
  all the record holds.
- `--y-profile [--band N]` (`episodes.py:223-258, 390`): game steps (`last_step -
  first_step`) per y band, credited to the band of the y the episode started at; one
  block per carried life under `--previous`. Existing filters (`--steps`, `--near`,
  `--tag`, ...) apply to both views; the plain listing is unchanged.
- `tests/test_episodes_views.py` (new, 3 tests) covers both views on a tiny synthetic
  index, both with `--previous`, and pins the unchanged listing line. **3 passed.**

Run on of3r's real index (`cwd` = that memory dir, read-only):

    ./tools/episodes.py --root . --ores            -> 50 lines
    ./tools/episodes.py --root . --ores --previous -> life 1's ore, same shape
    ./tools/episodes.py --root . --y-profile
    ./tools/episodes.py --root . --y-profile --previous
    ./tools/episodes.py --root . --y-profile --steps 14000 16000

of3r's own profile, which is the "where have I already looked" answer in one screen:

    [this life] 39145 steps over 16 y bands of 4
      y   68..71      1469   y   64..67      4199   y   60..63      4466
      y   56..59       237   ...                    y   12..15       639
      y    8..11     23090      <- 59% of the life in one 4-block band

## C. Read-out scripts (commit 729d42d), run on all six lives

All three take `argparse`, stdlib only, and reuse `_kit.print_table`. Commands used for
the tables below (`$B = MFM-grid/MCU/output`, `$PY = MFM-grid-merge-mcu/.venv/bin/python`):

    $PY tasks/mfm-three-layer.spatial-grid/scripts/stall.py \
        $B/of{1,2,3,1r,2r,3r}_mfm/episode_001/memory --top 2
    $PY .../scripts/memory_use.py of1_mfm of2_mfm of3_mfm of1r_mfm of2r_mfm of3r_mfm
    $PY .../scripts/selfimprove.py $B/of{1,2,3,1r,2r,3r}_mfm/episode_001/memory

### stall.py -- plan repeats from logs.txt, at two grains

    life      sections turns deaths | sec runs>=3 sec units in sec longest | turn runs>=3 turn units in turn longest | sec runs spanning turns
    of1_mfm       1148   411      3 |          67          286           8 |            0             0            0 |                       1
    of2_mfm       1315   426      1 |          82          416          12 |            0             0            0 |                       0
    of3_mfm       1104   277      0 |          80          473          15 |            0             0            0 |                       0
    of1r_mfm      2342   679      4 |         156          800          24 |            0             0            0 |                       0
    of2r_mfm      2787   677      1 |         136          772          20 |            0             0            0 |                       0
    of3r_mfm      2203   405      0 |         132          946          21 |            0             0            0 |                       0

A "unit" is a section for the `sec` columns and a model turn for the `turn` columns; a run
counts when it is >= 3 units and its sections' `moved=` sums to < 0.5. `sec units in` is
therefore the number of plan entries spent inside a dead plan: **946 of 2,203 entries
(43%) in of3r, 800 of 2,342 (34%) in of1r**. The last column is the load-bearing one: one
single run in six lives crosses a turn boundary.

Top repeated plan texts (80 chars, `--top 2`), with how many turns each run spans:

    of1_mfm   x8  (1 turn)  steps 18191-18207 moved 0.0: Position/vitals unchanged, GUI closed, fresh stone pick held in hotbar 6, worn p
              x8  (2 turns) steps 55262-55394 moved 0.0: Two stone picks, 47 cobblestone, stable health, a craft event, and an eastward f
    of2_mfm   x12 (1 turn)  steps 6129-6290   moved 0.0: Torch count decreases, height reaches about y63, and the view shows a lit stone
              x12 (1 turn)  steps 15839-15864 moved 0.0: Same position, fresh pickaxe held, three torches, empty cursor, and the lit tunn
    of3_mfm   x15 (1 turn)  steps 7301-7418   moved 0.0: One iron ingot, eleven torches, four sticks, and the charcoal furnace visible af
              x14 (1 turn)  steps 2981-3183   moved 0.0: [INV] gains four torches and retains three sticks; [EVENT] records crafting. Hea
    of1r_mfm  x24 (1 turn)  steps 61714-61857 moved 0.0: Y near 6, mined-stone drops, stable health, three ingots retained, and the craft
              x19 (1 turn)  steps 47881-48082 moved 0.1: X near -2977.6, stable Y4, mining events, pick wear, cobblestone gains, and a we
    of2r_mfm  x20 (1 turn)  steps 12550-12694 moved 0.4: One ingot enters inventory, followed by gravel or flint pickups; the view return
              x16 (1 turn)  steps 12309-12429 moved 0.4: Gravel or flint is collected, followed by iron ingots; the furnace screen become
    of3r_mfm  x21 (1 turn)  steps 24067-24188 moved 0.0: Sticks4, planks1, crafting-table screen open, and unchanged position, health13,
              x17 (1 turn)  steps 11910-12072 moved 0.0: Three logs smelting, two logs safely banked, all 17 andesite recovered, and an e

Read it as: the model commits to a 15-24 entry plan, the plan achieves nothing, and it
only finds out at the end of the turn. That is a *plan length* problem, not a *plan
repetition* problem.

### memory_use.py -- what each life read, from the rollouts

`of1_mfm` and `of2_mfm` each have two rollouts: a 0.5 MB stub written *after* the real
441 MB / 216 MB one, so the script picks the LARGEST, not the newest, and says which it
ignored. (The brief expected the duplicate at of1r; the record has it at of1 and of2.)

    life      turns cmds | prev/ t1 prev/ later | digest later notes later | view_image of episodes/ of previous/ | --then-now --previous | compactions
    of1_mfm     416  272 |       0           0 |            0           0 |        165          126            0 |          0          0 |          57
    of2_mfm     427  506 |       1           0 |            0           1 |         59           47            0 |          0          0 |          32
    of3_mfm     278  450 |       0           0 |            0           4 |         93           72            0 |          0          0 |          33
    of1r_mfm    690  277 |       3          41 |            0           0 |        109           60            2 |          2         12 |          96
    of2r_mfm    676  820 |       3           8 |            0           1 |        101           79            2 |          0          1 |          59
    of3r_mfm    407  786 |       4          22 |           12           2 |        159          118            8 |          0          6 |          55

A turn is a user message carrying an `input_image`; turn 1 is the opening turn.
Reading the carried life is rare and almost all of it is the opening turn plus a thin
tail (of1r 41 later commands over 690 turns = 6% of turns at most); carried FRAMES are
looked at 2-8 times per life against 60-126 looks at this life's own frames; `--then-now`
was used **twice in six lives** (both in of1r). The from-scratch lives touch `previous/`
0-1 times, as they should (there is nothing there) -- those hits are the word appearing
in an unrelated command.

### selfimprove.py -- what each life built under mine/

    life      lives carried  procedures  carried  new  new reflexes  record tools  skills  archives
    of1_mfm               0           1        0    1             0             0       0         0
    of2_mfm               0           7        0    7             0             0       0         0
    of3_mfm               0           4        0    4             0             0       0         0
    of1r_mfm              1           3        1    2             0             0       0         0
    of2r_mfm              1           6        2    4             0             0       0         3
    of3r_mfm              1           6        2    4             0             0       0         3

    of1_mfm  new: deep_stair_step
    of2_mfm  new: clear_north, descend_north, level_north, north_stair, north_step, soil_north_step, stone_north_step
    of3_mfm  new: north_cell, recover_north_torch, west_level, west_stairs
    of1r_mfm carried: deep_stair_step | new: horizontal_tunnel_step, safe_stair_step
    of2r_mfm carried: level_north, north_stair | new: east_coordinate, east_level, gravel_cycle, tunnel_gravel
             archives: working_archive29179.md, working_archive_21677.md, working_history_40423.md
    of3r_mfm carried: west_level, west_stairs | new: north_level, obsidian_hold, torch_west_relay, west_close
             archives: portal_history_35477.md, portal_history_35696.md, portal_history_38706.md

Three facts worth carrying forward: a reuse life carries **1-2 of its parent's 1-7
procedures** and writes 2-4 of its own; **no life wrote a single reflex class of its own**
beyond the four shipped examples; and **no life wrote a script that reads its own record**
(`logs.txt`, `index.jsonl`, `episodes/`) -- the record was only ever queried through the
harness's `tools/episodes.py`. `mine/skills/` was never used. Only the two reuse lives
that ran longest rotated their working memory at all (3 archive files each).

### `--ores` across the six lives (the B view, as a read-out)

    life      ore episodes  from previous/  y range of the sightings
    of1                  9               0  19-66
    of2                 22               0  43-53
    of3                 29               0  11-63
    of1r                53               9   3-54
    of2r                47              22  10-49
    of3r                50              29  10-63

What the ore actually was, counted independently with
`grep -hoE "(mine_block|pickup) (deepslate_)?(iron|gold|coal|diamond|redstone|lapis|emerald)_ore"`
over each life's `episodes/*/outcome.json` (the tool's own `--ores` line names it too):

    of1   coal_ore, iron_ore
    of2   coal_ore, iron_ore
    of3   gold_ore, iron_ore, redstone_ore
    of1r  iron_ore 28, coal_ore 30, diamond_ore 5, redstone_ore 4, gold_ore 2, lapis_ore 2
    of2r  iron_ore 26, coal_ore 23, diamond_ore 8, redstone_ore 4
    of3r  iron_ore 29, coal_ore 14, diamond_ore 5, redstone_ore 7

The three reuse lives each broke diamond ore (5-8 events) and none of the three
from-scratch lives did. That is the fact the record holds and nothing in the memory
surfaced: `--ores` now answers it in one call, with the frame beside each hit.

## What is NOT verified

- `plan_repeats` has never fired on a real record (0 of 2,855 turn prefixes across the
  six lives). Its behaviour is verified only against synthetic turns in
  `tests/test_retrieve_plan.py`. Whether the line, when it does fire, changes anything the
  model does is untested -- as is every other line of the recall block.
- `recall_block` now reads up to 200 `action.json` per call (about 200 small file reads
  per model turn). Measured cost was not benchmarked; the existing `repeated_note` and
  `left_behind` already read `outcome.json` on the same path, and `turns_of` caps at
  `plan_recent`.
- The `--ores` list follows the brief's names plus `deepslate_` forms. `copper_ore`,
  `nether_gold_ore` and `nether_quartz_ore` are NOT counted (the brief did not list them);
  none appears in these six records, so the choice is untested either way.
- `memory_use.py` counts a command as "touching previous/" by substring, so a command
  that merely prints a path containing `previous/` counts. The from-scratch lives' 0-1
  hits are that noise floor.
- `stall.py`'s turn boundary is inferred from the `Plan Step i/k` counter, not from a
  turn number in the log. It gives 405 turns for of3r against the 399 turns the store's
  `action.json` records and 407 image messages in the rollout: within 2%, and none of the
  conclusions depend on the exact count.
- The 11 pre-existing test failures were not investigated beyond confirming they are
  identical on unmodified HEAD; 6 are a missing submodule and 5 are skew against
  uncommitted MCU edits owned by another session.
- Nothing was pushed; `MCU`, `MFM-grid`, `MFM-grid/MCU` and `MFM-grid-merge-mcu` were
  read only.
