# Metrics kit -- baseline over og6..og22

Four read-only scripts under `tasks/mfm-three-layer.spatial-grid/scripts/`, standard library
only, sharing `_kit.py` (the same in-tree import style as `churn.py` / `tailchurn.py`). Each
takes `--arm NAME` (repeatable), `--root DIR` (repeatable; default: both output roots),
`--json`, and prints one row per arm plus a TOTAL row. Nothing writes into an arm directory.

Roots searched by default:
`/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output` (og10-og15, og19-og22)
and `/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output` (og6-og9,
og16-og18).

Exact commands, run from the scripts directory with `/usr/bin/python3` and

    ARMS="--arm og6 --arm og7 --arm og8 --arm og9 --arm og10 --arm og11 --arm og12 --arm og13 --arm og14 --arm og15 --arm og16 --arm og17 --arm og18 --arm og19 --arm og20 --arm og21 --arm og22"

    python match_rate.py $ARMS
    python recall_retarget.py $ARMS
    python repeat_deaths.py $ARMS --quiet
    python procedure_reuse.py $ARMS --quiet

Captured 2026-09-08 03:05 CST. **og19, og20, og21 and og22 were still running** at capture time (their
`logs.txt` mtime was within seconds of the run), so their rows grow between invocations;
og6-og18 were finished.

## 1. match_rate.py -- the model's own OBSERVED vs EXPECTED verdict

```
arm     steps  verdicts  matched  partial  failed  unclear  matched%  verdicts/1k  matched/1k
-----  ------  --------  -------  -------  ------  -------  --------  -----------  ----------
og6     11996        62        9       15      24       14      14.5          5.2         0.8
og7     11995        71        3        8      34       26       4.2          5.9         0.3
og8     34431       251       49        2      35      165      19.5          7.3         1.4
og9     30220       227       54        5      29      139      23.8          7.5         1.8
og10    54668       329       91        7      42      189      27.7          6.0         1.7
og11    34954       374      103        5      40      226      27.5         10.7         2.9
og12    33869       241       53        3      34      151      22.0          7.1         1.6
og13    27755       236       73        0      30      133      30.9          8.5         2.6
og14    26412       426      114        1      38      273      26.8         16.1         4.3
og15    15990       371      243        0      16      112      65.5         23.2        15.2
og16    43372       407      136        0      39      232      33.4          9.4         3.1
og17    20416       369       68        8      36      257      18.4         18.1         3.3
og18    17233       390      254        4      11      121      65.1         22.6        14.7
og19    16629       201       48        0      24      129      23.9         12.1         2.9
og20    12237       249      167        1      11       70      67.1         20.3        13.6
og21     9872       159      116        1       7       35      73.0         16.1        11.8
og22     6059       141       63       23      19       36      44.7         23.3        10.4
TOTAL  408108      4504     1644       83     469     2308      36.5         11.0         4.0
```

`unclear` is large by construction. The rule only calls a verdict `matched` when the sentence
*starts* with Matched / Yes / As expected / Confirmed / Match, so the very common
"X and Y matched; Z did not run" form is neither matched nor failed and lands in unclear
rather than being scored either way. `--verbose` prints five per arm so the rule can be tuned;
for og14:

```
$ python match_rate.py --arm og14 --verbose   # tail
-- og14: 273 unclear, first 5 --
   step 1       Initial state has no credited milestones; diamonds and iron ingots are absent from inventory.
   step 57      Drops and crafting matched; diamond and crafting_table are credited, with the GUI closed.
   step 79      Table placement succeeded, but neither craft ran; the GUI is now reported open with no items on the cursor.
   step 249     Furnace and both diamond crafts succeeded exactly; progress is 5/24, but the diamond tools need moving to the hotbar.
   step 351     The tools reached the hotbar, but the aim overshot and mined grass; mine_cobblestone remains unmet.
```

Read the `matched%` column as "share of verdicts the prefix rule could confidently call a
match", not as "share of turns that went as planned".

## 2. recall_retarget.py -- uptake of the harness's [RECALL] block

```
arm    turns  recall  cited/turn  lines/turn  retarget  retarget%  mention  mention%  frame
-----  -----  ------  ----------  ----------  --------  ---------  -------  --------  -----
og6       64      63         0.2         5.4         1        1.6        7      11.1      0
og7      102     101         0.0         6.2         0        0.0        6       5.9      0
og8      266     265         0.0         6.8         5        1.9       71      26.8      2
og9      251     250         0.1         6.6        11        4.4       88      35.2      0
og10     347     346         0.1         5.9         2        0.6       80      23.1      0
og11     400     399         0.0         6.5         1        0.3      188      47.1      0
og12     249     248         0.2         6.2        30       12.1       80      32.3      0
og13     251     250         0.1         6.3        17        6.8      129      51.6      0
og14     468     467         0.1         7.5         9        1.9      225      48.2      0
og15     386     385         0.1         7.7         6        1.6      241      62.6      0
og16     433     432         0.1         6.9         1        0.2      209      48.4      0
og17     398       0         0.0         0.0         0        0.0        0       0.0      0
og18     391     389         0.0         9.1         0        0.0      206      53.0      0
og19     210     209         0.0         6.9         1        0.5      134      64.1      0
og20     260     259         0.1         7.2         4        1.5      172      66.4      0
og21     159     158         0.0         7.7         0        0.0       79      50.0      0
og22     143     140         0.0         7.6         0        0.0       59      42.1      0
TOTAL   4778    4361         0.1         7.1        88        2.0     1974      45.3      2
```

Two things in this table are findings rather than parser artifacts, and both were confirmed
with an independent grep:

- `cited/turn` is near zero everywhere. The [RECALL] blocks in these arms cite *episodes and
  steps* (`ep_000334 step 5104: ...`), almost never world coordinates. og14 has exactly 30
  coordinate-bearing lines across its 467 recall blocks
  (`grep -h -A30 '^\[RECALL\]' *.prompt.txt | grep -cE '\(\s*-?[0-9]+...'` = 30, the same
  number the script counts). With so little cited geometry, `retarget%` is bounded near zero
  by the input, so the mention column is the more informative one for now.
- og17 shows 0 recall turns out of 398. Its prompts contain no `RECALL` string at all
  (`grep -l RECALL codex_turns/*.prompt.txt | wc -l` = 0) although its
  `worldmodel_report.json` says `memory_mode: mfm`. Recall never fired for that arm.

`frame` (a `view_image` on an `episodes/` path in that turn's events) is 0 for every arm but
og8, which did it twice.

## 3. repeat_deaths.py -- deaths at places already on record

```
arm    deaths  nether  overwld  near_same  near_prev  recs_this  prev_lives  recs_prev
-----  ------  ------  -------  ---------  ---------  ---------  ----------  ---------
og6         1       0        1          0          0          1          13         24
og7         0       0        0          0          0          0          15         29
og8         3       0        3          2          3         12          15         29
og9         3       2        1          2          0         15          16         29
og10        3       0        3          2          0         11           0          0
og11        2       0        2          1          0          8           0          0
og12        1       1        0          1          0         27           0          0
og13        2       1        1          1          0         15           0          0
og14        0       0        0          0          0          0           0          0
og15        0       0        0          0          0          0           1          0
og16        2       0        2          1          0         14           0          0
og17        0       0        0          0          0          0           0          0
og18        0       0        0          0          0          0           0          0
og19        2       0        2          1          2          4          23        112
og20        0       0        0          0          0          0           1          0
og21        0       0        0          0          0          0           1          0
og22        0       0        0          0          0          0           1          0
TOTAL      19       4       15         11          5        107          86        223
```

`near_same` / `near_prev` count deaths within 8 blocks (xz only) of a hazard record that
existed before them: an earlier death, a `LAVA AHEAD ... lava at (x, y, z)` sighting, or a
`DOUSED ... now at (x, y, z)` rescue. 11 of 19 deaths repeat a site this life already recorded;
5 repeat one carried in from a previous life. Dimension comes from `|x| < 1000` => Nether.

Per-death detail is the default output (`--quiet` suppresses it):

```
$ python repeat_deaths.py --arm og8 --arm og9 --arm og10 --arm og19

-- og8: 3 death(s) --
   step 2603    (-3008, -5569) y=9 overworld
      nearest_same_life  none
      nearest_prev_life     2.2 blocks  death  life_2 step 5790
   step 14349   (-2987, -5558) y=11 overworld
      nearest_same_life     1.0 blocks  lava   this step 14284
      nearest_prev_life     2.2 blocks  lava   life_6 step 7052
   step 18261   (-2988, -5559) y=11 overworld
      nearest_same_life     1.0 blocks  lava   this step 14284
      nearest_prev_life     3.6 blocks  lava   life_1 step 4532

-- og9: 3 death(s) --
   step 17976   (-389, -688) y=26 nether
      nearest_same_life     1.0 blocks  lava   this step 17916
      nearest_prev_life  5508.2 blocks  lava   life_4 step 10488
   step 19286   (-3005, -5581) y=9 overworld
      nearest_same_life    24.2 blocks  lava   this step 7004
      nearest_prev_life    10.0 blocks  death  life_13 step 2721
   step 26939   (-317, -681) y=27 nether
      nearest_same_life     1.0 blocks  lava   this step 26888
      nearest_prev_life  5548.7 blocks  lava   life_4 step 10488

-- og10: 3 death(s) --
   step 8870    (-2958, -5511) y=9 overworld
      nearest_same_life  none
      nearest_prev_life  none
   step 35834   (-2957, -5511) y=10 overworld
      nearest_same_life     0.0 blocks  lava   this step 8870
      nearest_prev_life  none
   step 45621   (-2962, -5512) y=10 overworld
      nearest_same_life     1.0 blocks  lava   this step 43776
      nearest_prev_life  none

-- og19: 2 death(s) --
   step 4356    (-2999, -5579) y=28 overworld
      nearest_same_life     8.5 blocks  doused this step 4278
      nearest_prev_life     6.3 blocks  death  life_21 step 19286
   step 10178   (-3008, -5576) y=17 overworld
      nearest_same_life     7.8 blocks  doused this step 4278
      nearest_prev_life     4.2 blocks  death  life_13 step 2721
```

## 4. procedure_reuse.py -- own scripts carried across lives

```
arm    procs  inherit  same  new  calls_inh  calls_new  calls_orph  digest_B  digest_turns  turns
-----  -----  -------  ----  ---  ---------  ---------  ----------  --------  ------------  -----
og6        0        0     0    0          0          0           0         0             0     64
og7        0        0     0    0          0          0           0         0             0    102
og8        0        0     0    0          0          0           0         0             0    266
og9        0        0     0    0          0          0           0         0             0    251
og10       0        0     0    0          0          0           0         0             0    347
og11       0        0     0    0          0          0           0         0             0    400
og12       0        0     0    0          0          0           0         0             0    249
og13       0        0     0    0          0          0           0         0             0    251
og14       7        0     0    7          0        177           0         0             0    468
og15       9        0     0    9          0        248           0         0             0    386
og16       0        0     0    0          0          0           0         0             0    433
og17       0        0     0    0          0          0           0         0             0    398
og18      24        0     0   24          0        356           0         0             0    391
og19       1        0     0    1          0          6           0     12407            38    210
og20       6        1     0    5         27        100           0      6945            27    261
og21       7        2     2    5         65         19           0      6877            17    159
og22       5        3     0    2         27          3           0      3005             8    143
TOTAL     59        6     2   53        119        909           0     29234            90   4779
```

Per-procedure detail is the default output, here for the two arms that inherited anything:

```
$ python procedure_reuse.py --arm og21 --arm og22
-- og21: 7 procedure(s), digest digest.md (6877 B), named in 17/159 turns --
   gravel_pair              new                 1 calls  
   north_level              inherited/same     10 calls  life_1
   north_stair              inherited/same     55 calls  life_1
   south_level              new                 3 calls  
   stair_torch              new                12 calls  
   step_up                  new                 2 calls  
   west_leaves              new                 1 calls  

-- og22: 5 procedure(s), digest digest.md (3005 B), named in 8/143 turns --
   north_level              inherited/edited    0 calls  life_1
   north_stair              inherited/edited   27 calls  life_1
   south_stair_ascent       new                 1 calls  
   upshaft_step             new                 2 calls  
   west_level               inherited/edited    0 calls  life_1
```

Caveat on `inherit`: it matches on file name, then compares sha1 to split same/edited. og15
reads as 0 inherited even though its previous life carried 7 procedures -- og15's own nine are
all named differently (`clear_north_level.py` vs the carried `north_level.py`), so a rewrite
under a new name is invisible to a name match. Treat `inherit` as a lower bound.

`digest_B` is the size of `mine/digest.md` (or `mine/GUIDE.md`); `digest_turns` counts turns
whose `events.jsonl` mentions either name anywhere -- a shell command touching it, or the model
naming it in a message. It is evidence of contact, not of use.

## Sanity checks against the known reference numbers

| reference | measured | verdict |
| --- | --- | --- |
| og10: 3 deaths at steps 8870 / 35834 / 45621 within 5 blocks of (-2958, 9, -5511) | exactly those three steps, at (-2958,9,-5511), (-2957,10,-5511), (-2962,10,-5512) | agrees |
| og8: deaths at 14349 and 18261 are 1 block apart | (-2987,-5558) and (-2988,-5559), 1.4 blocks xz | agrees |
| og14 `own.calls` has 7 scripts (north_stair 55, west_level 47, ...) | 7 scripts, north_stair 55, west_level 47 | agrees |
| og14 has 426 "OBSERVED vs EXPECTED" lines | 426 | agrees |
| og22 about 94 "OBSERVED vs EXPECTED" lines | 140 at capture time | **disagrees** |
| og19 touched digest.md in 32 of 177 turns | 38 of 209 turns at capture time | **disagrees** |

The two disagreements point the same way and have the same likely cause: og19 and og22 were
still running while this was captured, and both counts are monotonically increasing. og22's raw
`grep -c 'OBSERVED vs EXPECTED' logs.txt` is 140 with no filtering, and og19's raw
`grep -l 'digest.md\|GUIDE.md' codex_turns/*.events.jsonl | wc -l` is 38 of 209 event files, so
the scripts are reporting what is on disk now, not mis-parsing. The reference figures are
consistent with an earlier snapshot of the same two live runs. Reported as measured; not
adjusted to match.

Direct evidence that these two are moving targets: re-running the same two greps a few minutes
after the capture gave og22 = 143 (was 140) and og19 = 210 event files (was 209). Both counts
only ever go up, so a reference taken earlier being lower is what one would expect.

One narrower reading of the og19 number is worth recording in case the reference meant it:
restricting the digest match to the *command string* of `command_execution` items (rather than
any mention anywhere in the events file) gives 24 of 201 turns as of an earlier capture -- still
not 32 of 177.
