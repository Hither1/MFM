# Systemic problems in the three-layer framework, from of1/of2/of3 and their reuse lives (2026-09-09 01:xx)

Six full-task lives on one setting (minimal contract, atoms, own scripts + own reflexes as the only tick layer,
no event sheet, 320x180, one thread, 8h wall extended to 12h for the reuse lives). Numbers from
`scripts/{compare,churn,stuckcost,pitstalls,procedure_reuse,repeat_deaths,vision_use}.py`, the purple logs and
the codex rollouts (parsers in the session transcript); the qualitative reads are `traj_of1_of1r.md` and
`traj_of2_of3_reuse.md` (two read-only subagents; some of their claims are second-hand, the numbers below are not).

## 1. The numbers (as of 00:44, reuse lives still running)

| arm | model | turns | steps | steps/turn | s/turn (med, p90) | ms | deaths | go_to blocked / pit stalls / lost steps | churn | cut-short notes | reflex firings |
|---|---|---|---|---|---|---|---|---|---|---|---|
| of1  | sol high    | 417 | 56,800 | 136 | 64 / 114  | 8  | 3 | 200 / 89 / 9,931 (17%) | 32% | 0   | 17 |
| of2  | gpt-6 med   | 428 | 34,000 | 79  | 53 / 106  | 9  | 1 | 5 / 1 / 0              | 4%  | 399 | 3  |
| of3  | gpt-6 high  | 278 | 30,200 | 109 | 80 / 213  | 10 | 0 | 0 / 0 / 0              | 6%  | 299 | 6  |
| of1r | sol high    | 417 | 61,600 | 148 | 64 / 98   | 13 | 1 | 95 / 18 / 13,029 (21%) | 10% | 0   | 12 |
| of2r | gpt-6 med   | 382 | 33,800 | 88  | 52 / 90   | 13 | 1 | 5 / 0 / 0              | 6%  | 379 | 8  |
| of3r | gpt-6 high  | 214 | 22,800 | 107 | 73 / 207  | 13 | 0 | 0 / 0 / 0              | 8%  | 340 | 4  |

Milestone step gaps (where the budget went):

| arm | to furnace | furnace -> iron ore | iron ore -> iron pickaxe | iron pickaxe -> diamond ore | after |
|---|---|---|---|---|---|
| of1  | 8,494 | 13,239 | never (3 ingots at 22k) | - | 34,582 steps at 8/24 |
| of2  | 4,639 | 7,148  | 1,096 | never (died at y10 @ 23,285) | 21,117 |
| of3  | 2,806 | 2,519  | 918   | never (17k at y11, then flint_and_steel) | 7,168 |
| of1r | 5,509 | 18,010 | 9,585 | 22,444 | diamond -> sword 2,673 |
| of2r | 4,123 | 4,684  | 1,710 | 16,741 | diamond -> obsidian 4,653 |
| of3r | 2,507 | 2,526  | 1,027 | 11,861 | diamond -> sword 482 |

Reading: everything up to the iron pickaxe costs gpt-6 5-6k steps and is not the problem. The FULL task is
decided by one step, "find ore you have never seen" (iron for sol, diamond for everyone): 12-22k steps in every
life that got there, with nothing in the harness or the memory that shortens it unless the previous life already
found it (of3r's digest had life 1's shallow iron to the block; iron came at 5,033 vs 5,325 -- but life 1 never
saw diamond, so the diamond search was again blind).

## 2. How the multimodal memory system was actually used

Per-turn counts from the codex rollouts (`view_image(...)` inside the exec tool calls; `tools/episodes.py`; grep
over logs.txt):

| arm | view_image / turn | turns with a view | frames: this life / previous life | episodes.py calls (% turns) | --sheet/--then-now | zoom | grep logs.txt |
|---|---|---|---|---|---|---|---|
| of1  | 0.49 | 27% | 132 / 0 | 65 (11%) | 13 | 23 | 5  |
| of2  | 0.14 | 14% | 47 / 0  | 0 (0%)   | 0  | 3  | 1  |
| of3  | 0.34 | 31% | 74 / 0  | 0 (0%)   | 0  | 1  | 2  |
| of1r | 0.28 | 19% | 56 / 2  | 49 (9%), 10 with --previous | 19 | 14 | 15 |
| of2r | 0.15 | 15% | 41 / 2  | 6 (1%)   | 0  | 1  | 2  |
| of3r | 0.34 | 30% | 44 / 6  | 6 (2%)   | 0  | 3  | 23 |

(`vision_use.py` counts the same calls in every syntax and runs 1.5-3x higher: of1 608, of1r 341, of3r 236; the
ranking is the same. `previous/` paths appear in 60 / 17 / 35 shell commands of of1r / of2r / of3r, most in the
workshop turn, a trickle afterwards -- of1r's 10 `episodes.py --previous` queries and of3r's 6 previous-life
frames are the whole across-life visual use.)

- The visual memory is used as a **re-look at the current situation**, not as memory: the frames opened are
  this life's latest episodes (the frame the turn just produced, or the one before). The query tool's memory
  functions (`--near X Z`, `--then-now`, `--sheet`) are used by sol only (of1: 20 `--near`, 13 sheets; of1r: 6
  `--near`, 19 sheets, 1 then-now) and by the gpt-6 arms never (0 and 0 in the first lives, 6 calls total in
  each reuse life). gpt-6 treats the log as text: `grep logs.txt` 23 times in of3r, `episodes.py` 6 times.
- Across lives the picture is the same: the digest is written from `logs.txt` lines (grep for YOU DIED / MILESTONE /
  coordinates), the previous life's frames are opened 2-6 times per life. of3r is the only arm that wrote a frame
  path into its digest ("Frame previous/life_1/episodes/ep_000008/observation/image.png viewed during workshop").
- The judged value of a view is in the second half of a life going DOWN for the gpt-6 arms (of3 0.42 -> 0.27
  views/turn, of3r 0.45 -> 0.24) and UP for sol (of1 0.26 -> 0.72) -- sol looks more when stuck, gpt-6 looks less
  once its tunnel scripts run; neither pattern is "look when the outcome surprised you" (the contract's rule).
- Nothing in the memory stack indexes the thing the task is bottlenecked on. There is no "ore seen / ore mined /
  y-level of the last N cells" view of the episode store; `--near` is by x/z only; the digest of a life that found
  no diamond carries no diamond information. So the memory shortens what the previous life did well (early game,
  known iron, known lava, known deaths) and is silent exactly where the budget goes.

## 3. Systemic problems, ranked by steps lost

1. **Ore search is blind and single-cell.** All six lives search by "cut one or two cells, look at the face,
   repeat" scripts (deep_stair_step, north_level, west_level, east_level...). 12-15 steps per horizontal block,
   ~60 per vertical block with a torch (traj_of2_of3 §5). of3 repeated "Mine two blocks west, EXPECT x=-3109.7"
   30+ times after movement had already stopped; of3r did the same toward its remembered gravel (movement=0
   undetected for 15+ plans). No arm ever branch-mined, strip-mined at spacing, or used the y-level systematically
   (of3 stayed at y11 for 17k steps; diamond in this seed was found at y4-9 by the others). The contract says
   nothing about how to search, the skills package has no search doctrine, and the model does not derive one.
   The atoms mode removed mine_forward/strip_mine/stair_down and the model rewrote single-cell versions of them.
2. **The harness note recommends tools that do not exist.** `attack-hold entry cut short at step N: a block broke
   ... To mine several blocks in a row use mine_forward/strip_mine/stair_down` appears 300-400 times per gpt-6
   life (agent.py:1991); none of the three is in `procedures.ATOMS`. Every mining turn carries a stale hint.
3. **go_to is a step sink for sol and unused by gpt-6.** of1/of1r: 200/95 blocked notes, 89/18 pit stalls (the
   walk drops into its own excavation and cannot climb), 17-21% of all steps inside stuck episodes; the grid
   navigator detours "over cells you walked earlier" and queues pillar_up(6) which is where of1's third and of1r's
   only death happened (6 blocks apart, repeat_deaths). gpt-6 barely calls go_to (3-5 notes per life) and moves by
   its own scripts; the navigation-loss problem is model-specific, and the mine-grid + navigator pair is the one
   harness layer that still acts on its own in this setting.
4. **Reflexes are the wrong four, and two of them killed.** The examples (fell, hit, lava_ahead, starving) fired
   3-17 times per life; no arm wrote a new class. There is no drowning reflex (of1 died twice in water with the
   harness noting "drowning reduced health to 4" in plain text), no burning reflex; `hit` assumes a mob ("no lava
   in view: a mob is at you") and dropped of2r's escape from under its own obsidian; `lava_ahead` stepped of2 back
   6 ticks into the lava it was climbing out of. Both deaths at the obsidian/lava site had a water bucket in the
   hotbar that was never poured on the fire. The tick layer is "one line of shell per tick" but the model uses it
   as a nag, not as an escape policy.
5. **Nobody eats.** 0 eat actions in six lives, no food ever carried (no animal killed, no crop). Natural
   regeneration needs food >= 18/20, so every life spends its second half at reduced health: of1 sat at 2/20 for
   16k steps and the "deliberate drowning as teleport" was its only way home; of3r is at 11-13/20 now. The atom
   `eat` exists; the contract, skills and digests never mention food as a prerequisite, and `starving` only
   writes a note.
6. **Reuse works where life 1 succeeded, and the workshop only happens if the contract says so.** The three
   reuse lives went 8->13, 9->13, 10->13 with 0-1 deaths, all through the digest (known iron, known lava, known
   deaths, kept scripts): the model does digest its own memory. But (a) the first of1r never opened previous/ in
   27 turns until the minimal contract got the carried-lives paragraph (fixed b2f8c832); (b) the digest is a text
   summary of coordinates and deaths, the frames are cited once; (c) it cannot help with the blind search, and it
   can mislead: of3r spent 4.5k steps tunneling toward life 1's gravel at x=-3169 (60 blocks away) instead of
   looking for gravel nearby; of1r died 6 blocks from life 1's third death although the digest named it.
7. **Turn wall time, not game steps, is the budget.** 52-103 s median per turn, p90 90-213 s; gpt-6 high runs
   ~107 steps/turn -> 30k steps in 8h. A model that thinks longer gets fewer game steps; the 8h wall therefore
   compares "steps affordable" as much as competence. Discarded sessions: 1 in of1, 1 in of2, none since.
   **Compaction is constant and invisible to the harness** (checked 01:1x): the rollouts hold 57 / 32 / 33 / 58 /
   34 / 28 `"type":"compacted"` records (of1..of3r) -- of3r about 5 per hour, one every ~12 minutes = every 8-10
   turns -- while `worldmodel_report.json` says `compactions: 0` for all six, because codex_backend.py:860 counts
   compaction events in the `codex exec --json` stdout stream, where codex 0.147 never reports them; only the
   rollout file does. So "one compacted thread" is in practice a chain of ~10-turn windows joined by codex's own
   summaries; the model's durable state is `working.md`, which it therefore rewrites every turn and which grows to
   40-68 KB -- and that file, put in front of the model every turn, is itself the biggest token item and the
   reason the 100k limit is hit every ~10 turns. It also explains the repeated identical plans (§3.1): the summary
   does not carry "the last 30 plans were this same plan".
8. **GUI/crafting state is read from stale frames.** Recurring notes and self-notes in all six: "craft macro slot
   report named the old matching item, not the actual output", "GUI reports open while the image shows the
   world", "5 cells already hold leftovers ... plan dropped", furnace slot mis-click costing 135 ticks; the models
   invented a "watch 10-12 ticks after opening" rule each on their own (of3 and of2r both wrote it into working.md).
   Cheap in steps (a few hundred per life) but every crafting turn pays it, and the fix is one settle in the atom.
9. **Working memory is the wrong grain.** `working.md` is rewritten almost every turn (of2 425 / of3 279 / of2r
   377 writes) and grows to 40-68 KB in the sol lives (of1r 68 KB, of2r keeps two archives); it is put in front of
   the model every turn. Notes.md, the across-life channel, gets 1-3 lines per life.

## 4. What would change the outcome (for the user to pick; nothing launched)

- A search doctrine the model can own: a `skills/mining/SKILL.md` example with branch mining at y 5-12, 2-cell
  spacing, "if 40 cells show no ore change y", plus a stall rule ("three plans with the same EXPECT and moved=0 ->
  stop and re-plan"), and an `episodes.py --ores` / `--y-profile` view over the episode index so the memory can
  answer "where have I already looked". This is example + tooling, not a pushed fact.
- Retire the stale cut-short hint in atoms mode (name the atoms, or say nothing).
- Give the reflex example set a drowning/burning class and make `hit` say "damage source unknown: air? fire?
  mob?"; the pour-water-on-fire move belongs in the survival reference.
- Food as a stated prerequisite before y<40 (one line in the contract or the survival skill), or a `hunt`/`eat`
  example script.
- For sol specifically: either fix the navigator's pit behaviour (do not queue pillar_up inside a shaft) or hide
  go_to in atoms mode; gpt-6 does not need it.
- A per-turn settle inside the GUI atoms (open -> watch 10) so the stale-frame rule stops being rediscovered.

## Correction (2026-09-09 06:0x): the unit of the "repeated plan"

The "30+ times", "15+ plans" and "repeated 11-17x" counts above (and the 04:40 progress line
"345 plans since mine_obsidian") count logs.txt SECTIONS -- one per plan entry, the [PLAN]/EXPECT
text reprinted under every entry -- not model turns. At the turn grain no life re-issued an
identical EXPECT three turns running (scripts/stall.py, analysis/worker_recall_2026-09-09.md:
653 dead section runs across six lives, 652 inside one turn; consecutive EXPECT similarity
median 0.48). The stall the record shows is ONE LONG PLAN of 15-24 entries that achieves
nothing: 34% (of1r) to 43% (of3r) of all plan entries sat inside such plans. The RECALL line
is therefore outcome-based (mfm/memory/retrieve.py plan_stall): "nothing happened for N turns"
or "your last plan ran K entries and changed nothing", with "the same EXPECT each time (numbers
aside)" when the rephrased text collapses to one. §3.1's conclusion (single-cell search, no
change of y) stands; §3.7's "repeated identical plans" should read "long plans that check
nothing on the way".
