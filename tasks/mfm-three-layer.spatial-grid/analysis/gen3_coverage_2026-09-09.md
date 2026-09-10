# Do the gen-3 changes address the systemic problems of the finished gen-2 arms? (2026-09-09 08:40)

Sources: the final records of of1r / of2r / of3r (MFM-grid/MCU/output/*_mfm/episode_001/memory),
`scripts/{stall,memory_use,selfimprove}.py` run on them at 08:12, the milestone lines of the purple
logs, `analysis/systemic_of_2026-09-09.md` (the six-life review, with its correction), the worker's
`analysis/worker_recall_2026-09-09.md`, and `analysis/traj_gen2_final.md` (a read-only subagent's
qualitative pass; its step numbers for of1r/of2r deaths and its GUI counts did NOT survive checking
against the logs -- the numbers below are the log's, the report is used only for what it quotes).
Gen-3 code = MCU spatial-grid-merge f943269a (1ac1c7f7 + 121d500a + 3a63e24a + f943269a) and
MFM-grid 4b727d2+ (retrieve.plan_stall, episodes tool --ores/--y-profile).

## 1. The three lives, final

| | of1r (sol high) | of2r (gpt-6 med) | of3r (gpt-6 high) |
|---|---|---|---|
| steps / turns / wall | 84.4k / 690 / 12h | 52.4k / 704 / 12h | 43.5k / 519 / stopped 08:06 by the user |
| milestones / deaths | 13 / 4 | 15 / 1 | 16 / 1 |
| iron pickaxe -> diamond ore | 22.4k (33,104 -> 55,548) | 16.7k (10,517 -> 27,258) | 11.9k (6,060 -> 17,921) |
| after the diamond tools | 26k steps, nothing banked | obsidian +4.3k, death +0.4k, flint 17.1k later, sword | flint 9.6k, obsidian 4.7k, portal->Nether 8.9k, Nether death +0.4k |
| deaths (step, place) | 28,147 (-2998,56,-5583) fall in own shaft; 72,966 & 73,299 skeleton at 2/20 hp; 74,587 (-2997,54,-5582) fall, 2 blocks from death 1 | 32,270 (-3007,8,-5680) under its own obsidian cap, burning | 41,983 Nether (-408,43,-704): health 20 at entry (41,584) to 0 in 400 steps, no food, fires + piglin |
| entries inside dead long plans (stall.py) | 800 / 2,342 = 34% | 816 / 2,886 = 28% | 1,126 / 2,662 = 42% |
| previous/ commands after turn 1 | 41 | 8 | 24 |
| own digest re-read after turn 1 / notes | 0 / 0 | 0 / 1 | 13 / 3 |
| previous-life frames viewed / --then-now | 2 / 2 | 2 / 0 | 8 / 0 |
| eat / kill_entity / food picked | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 1 / 0 |
| procedures carried / new; new reflex classes; record tools; mine/skills | 1/2; 0; 0; 0 | 2/4; 0; 0; 0 | 2/4; 0; 0; 0 |
| harness GUI notes: no screen / leftovers / wrong screen / plan dropped | 34 / 7 / 5 / 54 | 16 / 6 / 2 / 17 | 6 / 1 / 2 / 5 |
| compactions (rollout) | 96 | 63 | 70 |

of3r's portal phase (steps 32,685-41,584): 812 entries in 145 turns, 10 `place_at(obsidian)`, 22
`mine_block obsidian` (its own frame mined back and re-placed), one ignition action in the log;
its own portal_history_35477.md: "IGNITION FAILED 35276 ... player burning HP13->11". It entered
the Nether at health 20 with no food and was dead 400 steps later.

## 2. Problem -> change -> status

Status key: **H** = fixed in the harness (mechanical, holds regardless of the model);
**K** = given to the model as knowledge/routine/tool (holds only if the model uses it; unverified
until gen 3 runs); **-** = not addressed.

| # | problem (evidence) | gen-3 change | status | what gen 3 must show |
|---|---|---|---|---|
| 1 | Blind single-cell ore search: 12-22k steps per life from iron pickaxe to diamond; of3r spent 59% of its life in the y 8-11 band; no life changed y or heading deliberately | `skills/mining` (branch mining at y 11-12, 2-cell spacing, change y after 40 empty cells, caves, one segment per script call); `episodes.py --ores / --y-profile`; Rules "budget tools, lighting, return route" | K | steps iron->diamond < 8k; `--y-profile` spread over >= 3 bands; the mining skill read in the rollout (`skills/mining/SKILL.md`) |
| 2 | Long dead plans: 28-42% of entries in plans that moved nothing and banked nothing (of1r 24-entry, of3r 21-entry plans); EXPECT rephrased every turn | `retrieve.plan_stall` -> first RECALL line ("your last plan ran N entries and changed nothing" / "nothing happened for N turns"); Routine "stop, grep own logs.txt, change target/tool/place"; mining skill "check after a few entries" | H (the line) + K (the reaction) | RECALL stall lines fire; dead-entry share falls below 20% |
| 3 | Nobody eats: 0 eat, 0 food in nine full-task lives; of1r 26k steps at 2/20 hp; of3r died in the Nether at health 20->0 with no food | `skills/minecraft` hunger section (heal only >= 18 food; animals, cooking, berries); Rules "no natural healing below 18: kill animals and cook before the first descent"; Routine pre-descent checklist "food in the inventory"; Nether entry "health 16+ and cooked food" | K | at least one `eat` action per life; food picked before y < 40 |
| 3b | Animals are never reported: entities are not in the observation, `vision.entity_hint` exists but is not wired into the turn message | nothing | - | the model must SEE animals in the frame; if gen 3 still never eats, wire a frame-based animal hint (harness perception, not a fact) |
| 4 | Wrong reflex set: `hit` assumed a mob (of2r burned under its own obsidian cap while the note said "a mob"); no drowning/burning class; 3 of 8 deaths reflex-assisted | `hit.py` "source unknown: look at the frame"; `burning.py` and `drowning.py` examples; reflex state carries `fire_frac`/`water_frac`; classes text | H (state) + K (the model must copy the examples) | reflex firings named correctly; no death "burning while told a mob" |
| 5 | Navigator pit: `go_to` re-queued from the top of a `pillar_up(6)`, the walk stepped off it (of1 death 3, of1r death 1) | pillar, then the plan STOPS with a note; no go_to from the pillar top | H | no death within 6 blocks of a pillar note |
| 5b | Deaths at recorded places: of1r death 4 two blocks from death 1; known_hazards.py example never copied in six lives | Routine after `YOU DIED`: death sheet + digest line + copy `known_hazards.py` into mine/reflexes | K | known_hazards present in mine/reflexes after the first death |
| 6 | Memory only helps where life 1 succeeded; digest re-read 0/0/13 after turn 1; then-now used twice in six lives; remote remembered targets misled (of3r 4.5k steps toward gravel 60 blocks away) | `[DIGEST]` beside `[WORKING]` every turn; Routine "a remembered place is a hypothesis until [STATE] confirms it; --then-now on arrival"; minecraft skill: gravel is at water's edge and in caves (walk to the nearest, not the remembered one); gen-3 seeds carry the diamond y, the lava lake and the portal site | H (re-feed) + K | digest lines quoted in briefings; then-now >= 5 per life; steps to obsidian < 4k |
| 7 | Stale cut-short hint naming macros that do not exist (300-400 per life) | atoms-aware hint | H | 0 occurrences of "mine_forward/strip_mine/stair_down" in gen-3 logs |
| 8 | GUI: frame trails `isGuiOpen`; leftovers precheck reads emptied cells as busy (7/6/1 false refusals, plan drops 54/17/5); models added watch(10-12) themselves | `_opengui_tick` idles 3 ticks after the flag; `CRAFT_SETTLE` 2->6 | H | leftovers notes ~0; no "watch 12 between crafts" rule in working.md |
| 8b | Stale station: a table/furnace mined back up stayed in [MAP] / stall hint / use_until_gui aim (of3 carried "map placement STALE" 10k steps) | `_station_picked_up` pops `_placed` and `grid.placed` on the mine_block event, with a note | H | no "STALE" station remarks in working.md |
| 9 | Turn wall time is the budget (52-103 s median; gpt-6 high ~107 steps/turn -> 30k steps / 8h); compactions every 8-10 turns, counted as 0 | compactions counted from the rollouts (reporting); SESSION_TURNS kept at 0+compact for comparability; contract 12.6 KB (was 13.9) | reporting only | steps/turn and s/turn compared with gen 2 |
| 10 | Portal geometry: of3r 8.9k steps, 812 entries, 10 obsidian placed into an invalid frame, 22 mined back; burned at ignition; of2r died under its own cap | minecraft skill portal section (4x5, 10 blocks, 2x3 air inside, light on an inner face; "a frame is geometry: one verified block per plan, LOOK from 3-4 blocks before igniting"); Rules "geometry task: one verified block per plan with a look between placements"; burning reflex; water-on-fire rule | K | portal lit in < 3k steps after the 10th obsidian; frames viewed during the build |
| 11 | Flint: of3r 9.6k steps, of2r 17k (after its death) tunnelling toward remembered gravel | minecraft skill: gravel at riverbeds, shores, beaches, cave floors, 1-in-10 flint, re-dig | K | flint_and_steel < 3k steps after the iron for it is in hand |
| 12 | Nether: entered at health 20 with no food, died in 400 steps (fires, piglin) | minecraft skill Nether section (health 16+ and food to enter, leave below 12, sneak, bridge, blazes in fortresses); Routine pre-Nether checklist | K | survives the first 2k Nether steps |
| 13 | Self-improvement stayed at movement macros: 0 new reflex classes, 0 scripts over the record, mine/skills never used | "Improve yourself" paragraph (hazard->reflex, question asked twice->script, worked twice->procedure, doctrine->skill); codex-native catalog lists `mine/skills/<name>` next turn; memory skill's example scripts | K | >= 1 new reflex class, >= 1 record tool, >= 1 own skill per life |
| 14 | Skills were never in codex's catalog; triggers lived in a once-read file | `.agents/skills` catalog synced every turn (smoke: codex re-scans roots and re-reads AGENTS.md every turn of a resumed thread); descriptions are triggers | H | `### Available skills` in the rollout lists six + own skills; SKILL.md reads after turn 1 |
| 15 | RECALL noise (`hotbar.6` 61 calls) | hotbar.1-9 in RECALL_IGNORE_KINDS; `hotbar_only` in retrieve.streaks | H | no hotbar lines in RECALL |

## 3. What is NOT covered, honestly

- **3b, food perception.** The green layer sends no entities and the harness does not describe animals
  from the frame. Every food rule now in the contract needs the model to notice a cow in a 320x180
  frame by itself. If gen 3 still never eats, the next step is a frame-based animal hint in the turn
  message (perception, not a world fact) -- a harness change we have not made.
- **The K rows are advice.** Rows 1, 3, 10, 11, 12, 13 are knowledge and routines the model must
  choose to apply; gen 2 showed the model applies concrete, triggered instructions (the workshop
  paragraph: 3/3) and ignores standing advice ("look when surprised": 0). The K rows were therefore
  written as triggers + files + actions and put where they recur (AGENTS.md every turn, the catalog
  every turn, [DIGEST]/[RECALL] every turn). Whether that is enough is exactly what gen 3 measures.
- **Portal geometry has no harness verifier.** A `portal_check` view (is the 4x5 frame complete, from
  the block record) would be mechanical and neutral; not built. The model is told to look instead.
- **Turn wall time.** Unchanged and unchangeable from our side; SESSION_TURNS stays 0+compact.
- **The entry cap** (40 entries / 400 ticks) still allows a 24-entry blind plan; RECALL names it
  afterwards rather than preventing it. Capping entries would take a decision away from the model.

## 4. Read-outs to run on gen 3 (all exist)

`scripts/compare.py`, `stall.py`, `memory_use.py`, `selfimprove.py`, `vision_use.py`; the
episodes tool's `--ores` / `--y-profile`; grep counts for the rows above (eat actions, hotbar RECALL
lines, cut-short hint text, leftovers notes, STALE remarks, SKILL.md reads and `### Available
skills` in the rollouts).
