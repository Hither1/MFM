# Evidence: six memory capabilities in the runs we have (2026-09-05)

Every claim below is traced to a file on disk. "Code supports X" is not counted as evidence;
only run artefacts are. Cells are n=1 runs unless stated.

**Arms and evidence bases**

| arm | runs used | what is on disk |
|---|---|---|
| MCU world model (live run) | `MCU/output/wm_dragon1/episode_001/` (dragon, 11,800 steps, 6/24, 104 model turns) | `memory/{logs.txt, hypotheses/graph.json + *.md, world_model/*.md, events/, maps/, procedures/, episodes/ep_0000/frames/}`, `worldmodel_report.json`, `codex_turns/turn_*.{prompt.txt,events.jsonl}` |
| MCU world model (relay lineage) | `MFM/MCU/data/MCUData/relay-era/lineage/{dm14x,dm15,dm16,kd14x,kd15,kd16}_wm_high_final_memory/` | distilled memory only: `world_model/`, `hypotheses/graph.json`, `locations/ore_registry.md`, `procedures/`, `rules.md`. **No logs, frames or events.** |
| MCU MFM (episode store on the logbook chassis) | `MCU-ladder/output/lad2_mfm/` (8/10), `lad3_mfmr/` (retrieval block on, 9/10); control `lad2_logbook/` (8/10) | `memory/{episodes/ep_N/{observation/image.png, state/state.json, state/ticks.jsonl, action.json, outcome.json}, index.jsonl, logs.txt, tools/}`, `codex_turns/` |
| KiCad world model | `mllm-search/runs/cua_bench_codex/kicad_wm_v2_projdir/` (15 tasks), `kicad_wm_v2/`, `kicad_wm_v1/` | per task `workspace/{logs.txt, frames/, hypotheses/, world_model/, notes/}`, `codex/`; `campaign_world_model/{manifest.json, history/NN_task/}` |
| KiCad MFM and carry | `kicad_mfm_gpt6hint/` (24 tasks), `kicad_mfm_gpt6low/`, `kicad_mfm_projdir/`, `kicad_mfmcarry_gpt6hint/`, `kicad_plcarry_gpt6hint/`; control `kicad_prolong_gpt6hint/` | per task `workspace/{episodes/, index.jsonl, logs.txt, frames/}`; carry: `workspace/previous/<task>/`, `carry/notes/kicad.md`, `carry/manifest.json` |

**The one structural caveat that colours everything:** the run with full traces (wm_dragon1)
has the thinnest memory (29 belief nodes, no rules, empty entities and locations), and the
memories with the richest structure (relay lineage, 209 to 275 nodes) have no traces at all.
Where the two are combined below, it is said which base the evidence comes from.

---

## 1. Lossless episodic storage

Screenshots, crops, action traces, environment metadata, artifact versions.

| arm | verdict |
|---|---|
| MCU world model | partial: state lossless, vision sparse, no versions |
| MCU MFM | strong, with two named losses |
| KiCad world model | absent as an episodic store |
| KiCad MFM / carry | strong, including cross-task carry |

**MCU MFM (lad2_mfm, lad3_mfmr).** Every environment tick is recorded exactly once:
`state/ticks.jsonl` totals **11,999 lines with 11,999 distinct step values** for an 11,999-step
run (step 0 is `ep_000000/state/state.json`). 426 and 304 episode directories, one
640x360 `observation/image.png` each. Nothing in the main channels is lost relative to the
log: `[NOTE]` lines in `logs.txt` 422 = notes in `outcome.json` summed 422; `[EVENT]` 748 =
748. `action.json` carries the model's `plan` and `briefing` on exactly the 89 act turns.
A full example (`lad3_mfmr/.../ep_000138`):

```
action.json   {"turn": 33, "plan_index": 1, "plan_total": 5, "first_step": 5399,
               "entry": {"procedure": "aim_at_ore", "args": {"ticks": 40}},
               "briefing": "The newly exposed iron vein is the priority; ...",
               "plan": "Center on the detected ore, mine it, and sweep up its drops ..."}
outcome.json  {"last_step": 5406, "moved": 0.0, "events": [], "inventory_delta": {},
               "notes": ["aim_at_ore: the speckle cluster is no longer detected (6 frames). ..."],
               "tags": ["note"], "verified_after": "7/10", "flushed": false}
state.json    {"step": 5399, "pos": {...}, "inventory": {"cobblestone": 38, "iron_ore": 1, ...},
               "hotbar": [...9 slots...], "gui_open": false, "vitals": {...},
               "goals": {"done": [...7...], "next": "iron_ingot"}}
```

Losses: `[GRID]` and `[CURSOR]` lines (159 each in `logs.txt`) exist only in the log, not in
any `state.json`, so GUI cursor geometry is not reconstructible from the store.
`observation_hash` and `attachment` are null in 426/426 index rows. `crops/` is empty in
every episode of every run (805 directories across MCU and KiCad; dropped on 09-05).
`ticks` in `action.json` is a placeholder value (`1000000000`). No artifact versioning exists.

**KiCad MFM / carry.** Frames to steps are exactly 1:1 in every task
(e.g. `kicad_mfm_gpt6hint/83490c3a`: 111 driver PNGs, 111 agent frames, 112 episodes
including the initial one). The episode image is a hard link to `frames/step_NNNN.png`
(same inode), while the driver-side `step_NN.png` is a true duplicate.
`state/state.json` = `{"step", "max_steps", "png_sha256", "feedback"}`;
`outcome.json` = `{"feedback", "next_png_sha256", "screen_changed", "flushed", "notes",
"tags", "terminate", "last_step"}`; `action.json` carries the tool calls, `log_line` and the
plan text. Cross-task carry is materialised: `kicad_mfmcarry_gpt6hint/ff6dfdde/workspace/
previous/` holds 23 prior task records and a merged `previous/index.jsonl` with **1,071
rows** (202 MB). Deliverables are saved in the hint arms: `kicad_project/` 24 of 24 and
`graded.net` 22 of 24.

Artifact versions exist only in the KiCad world-model arm:
`kicad_wm_v2_projdir/campaign_world_model/history/00_34877be3 ... 14_ff6dfdde/` holds 15
snapshots of the five documents, and `manifest.json` records reward, act turns and per-doc
byte sizes for each publication.

**MCU world model (wm_dragon1).** `maps/visited.csv` has 12,001 rows, one per step;
`events/events.jsonl` 440 lines (434 stat, 6 milestone); `logs.txt` 541 action blocks with
`[STATE]` 541, `[FRAME]` 541, `[GUI]` 540, `[EVENT]` 440, `[GRID]`/`[CURSOR]` 308, `[INV]` 96.
But frames are **102 for 11,800 steps** (one per model call, not per step), so the log
re-points at stale frames (Actions 1 to 3 all cite `step_0000.png`; one frame is cited 20
times). Exactly one suffixed frame exists, `step_1914_ore.png`. `events.jsonl` carries no
position field; the `biome` column is empty on every row; `memory/.git` exists with 0
commits; `world_model/*.md` are overwritten on each induction. The relay snapshots strip
logs, frames and events entirely, so episodic storage does not survive a relay generation.

Three KiCad workspaces were lost mid-run and restarted (`workspace.crashed` in
`kicad_wm_v2_projdir/34877be3`, `kicad_wm_v2/d1c655da`, `kicad_prolong_projdir/458f5f5c`),
so "lossless" fails under crash.

---

## 2. Structured abstractions

Objects, locations, inventory, components, subgoals, failures, causal hypotheses.

| arm | verdict |
|---|---|
| MCU world model (live) | strong, but harness-authored node classes absent |
| MCU world model (relay) | strong |
| MCU MFM | partial: harness tags and structured state only |
| KiCad world model | strong |
| KiCad MFM / carry | absent / partial (an accreted notes file) |

**MCU relay lineage** is the richest instance. Node counts by generation:

| gen | nodes | location | resource | mechanism | goal | state | registry entries | procedures |
|---|---|---|---|---|---|---|---|---|
| dm14x | 138 | 79 | 26 | 16 | 11 | 6 | 6 | 13 |
| dm15 | 173 | 101 | 35 | 20 | 11 | 6 | 13 | 13 |
| dm16 | 209 | 115 | 50 | 27 | 11 | 6 | 21 | 13 |
| kd16 | 275 | 102 | 39 | 39 | 24 | 71 | 5 | 12 |

Failures distilled to rules with hit counters, `dm16_.../world_model/rules.md`:
"After a zero-result, obstruction, two-cycle stall, or governor stop, change aim, route,
position, or method before retrying [x74]". Hazard nodes exist
(`hazard_live_lava_pocket_10604.md`, `hazard_unseen_hostile_y41_6089.md`).

**MCU world model live (wm_dragon1).** 29 nodes (goal 9, mechanism 8, resource 7,
location 5), 63 dependency edges. A causal node written from a failure:

> `mechanism_ore_watch_surface_false_positive_001` (confirmed, 0.9, created step 1914):
> "Ore watch can falsely classify spruce foliage as iron speckles at the surface; disable
> it until exposed stone, then re-enable underground."

Documents: `dynamics.md:3` "`dig_down` y67->55 cost 215 ticks and 14 blocks; never repeat
below y40." `causal.md:3` "Verified chain: log -> table -> wooden pick -> re-mined cobble ->
stone pick + furnace (6 milestones)." Four slot-level recipes in `procedures/`, e.g.
`craft_stone_pickaxe.md` "right-click one stick into 3x3 cells 4 and 7 ... Verified:
`craft_item stone_pickaxe` at step 5727." `[PLAN]` present in every action block (638 lines).

Gaps: the harness-written `site_*`, `vein_*` and `coverage` node classes defined in
`sites.py` appear in **none** of the seven memory snapshots inspected. wm_dragon1 has no
`state` nodes, no `rules.md`, and empty `entities/`, `locations/`, `notes/`. The dragon
lineage is state-heavy (60 to 71 `state` nodes) and 83 to 96 of those are `stale`.

**KiCad world model.** 580 nodes across 15 tasks in `kicad_wm_v2_projdir` (observation 262,
strategy 63, answer 248, domain 6, other 1); per task 4 to 112. `spatial.md` carries UI
coordinates: "Maximized Schematic Editor: menus y~58, main toolbar y~86; canvas
x~177-982,y~103-947 (task ff6dfdde T126 [SCREEN] frames/step_0126.png)". `procedural.md`
carries recipes, failures and a goal check: "**Wire:** exact pin, `w`; click bends ... **Failed:**
nearby snaps caused shorts; audit junctions. Plain Delete failed; context-menu Delete worked
(task ff6dfdde T53-T55)". All 15 history snapshots contain at least one `**Failed:**` entry.
Subgoal checklists in `notes/checklist.md` for 15/15 tasks ("- [ ] Add microphone bias: +12 V
through one 56 kΩ resistor ..."). Gaps: the kind taxonomy is used unevenly (one task 98/106
observation, another 32/35 answer; `domain` 6/580), and `ff6dfdde` has 106 nodes but 0
per-node `.md` files.

**MCU MFM.** Abstractions are all harness-computed: index tags (lad2_mfm: note 272, gui 160,
inventory_changed 69, stuck 10, milestone 8, flushed 2, damage 1), 33 `action_kind`s, x/y/z on
426/426 rows, structured inventory/hotbar/goals in every `state.json`, plan text per turn in
`action.json`. Governor failure notes are stored in `outcome.notes` ("governor: 'craft' at
this spot has now finished 2 times in a row changing nothing"). Hypotheses: 0 in all three
ladder arms. The index row carries no `turn` or plan field, so the tool output never shows
a subgoal.

**KiCad MFM / carry.** No graph, no typed documents; a free-text `plan.txt` in 17 of 24
tasks. The carry arm's `carry/notes/kicad.md` is a 23-paragraph accreted procedural memory
("Task 12: H-bridge motor driver: ... clicks inside red pin graphics failed to finish wires.").

---

## 3. Cross-modal links

observation ↔ entity/location ↔ action ↔ outcome ↔ subgoal.

| arm | verdict |
|---|---|
| MCU world model (live) | partial: prose citations, one real image path |
| MCU world model (relay) | strong |
| MCU MFM | strong within an episode, partial to milestones and plans |
| KiCad world model | strong |
| KiCad MFM / carry | weak: hashes exist, almost nothing matches |

**KiCad world model.** 567 of 580 nodes cite a frame; 579 cite a turn id. Every bullet in
the final campaign documents carries a frame citation. Node `h_app_start` (task 458f5f5c):
"T1 [SCREEN] frames/step_0001.png: default-settings dialog was ready; T2 [SCREEN]
frames/step_0002.png: the distinct project-manager screen is visible behind the
update-check prompt".

**MCU relay.** Registry entries bind pixels, coordinate, aim and event in one line,
`dm16_.../locations/ore_registry.md`: "Ore watcher flagged tan speckles in
`step_7717_ore.png`; current-prefix ground truth records `mine_block iron_ore` at step 7893
and `pickup iron_ore` at 7903 while fixed at this pose." Counts over graph text: dm16 156
"frame N" refs, 20 `.png` paths, 58 events refs, 87 map refs, 299 coordinate tuples.

**MCU world model live.** 35 graph strings cite a frame, 16 cite `events.jsonl`, 11 cite
`visited.csv`, 109 cite a step. `goal_crafting_table` evidence: "events.jsonl verifies the
milestone/craft at 698; step-1200 frame shows the table in hotbar." Only one node cites an
actual `.png` path (the `_ore` frame). Event-to-coordinate joins are done in prose by the
model, since `events.jsonl` has no position.

**MCU MFM.** The episode directory binds frame, state, ticks, action and outcome under one
id, and the index row adds position, so a row is visual, spatial and symbolic at once. The
scoring row for a milestone (`lad2_mfm/index.jsonl`):

```
{"id":"ep_000015","action_kind":"craft","first_step":521,"last_step":562,"gui_open":true,
 "image":"episodes/ep_000015/observation/image.png",
 "summary":"[ACTION] craft(item=crafting_table,count=1) -> 1 ticks: moved 0.0, inv {'crafting_table': 1, 'spruce_planks': -4}, milestone ['crafting_table']",
 "tags":["milestone","inventory_changed","gui","note"],"x":-3007.996,"y":69.0,"z":-5563.609}
```

All 8 (lad2) and 9 (lad3) milestones have such a row, and lad3's retrieval block renders the
link: "Milestones so far, with the entry that scored each: mine_log step 17 (ep_000010:
harvest_tree(logs=4,n=360)); crafting_table step 530 (ep_000029: craft(...))". Gaps: only 75
of 426 episodes carry any event; the episode-to-subgoal link lives only inside `action.json`.

**KiCad MFM.** Index rows carry `observation_hash` and the frame path, but genuine repeat
screens occurred in 2 tasks per arm, and **zero hashes are shared between any two tasks**,
even for the identical first-run desktop. So the `--same-screen --previous` query could never
have matched.

---

## 4. Multi-scale retrieval

Semantic search, temporal lookup, spatial lookup, exact programmatic queries.

| arm | verdict |
|---|---|
| MCU world model (live) | partial: text strong, visual rare, no semantic |
| MCU MFM | partial: temporal and exact only |
| KiCad world model | strong (text, frames, zoom) |
| KiCad MFM / carry | absent: the tool was used twice corpus-wide |

Semantic search does not exist in any arm (no embedding index anywhere).

**MCU world model live**, 214 shell commands over 104 turns: `logs.txt` 154, `tail` 149,
`rg`/`grep` 130, `events.jsonl` 116, `world_model/` 93, `sed -n` ranged reads 69,
`visited.csv` 66, `hypotheses/` 61, `procedures/` 14, `tools/zoom.py` **4** (2 turns),
`tools/frames.py` **0** (not written in this run), `view_image_calls` 10 in the audit.
Scales visible: `tail -n 220 logs.txt`; `rg -n 'Action [0-9]+ \| Step|\[STATE\]|...' logs.txt`;
`sed -n '1,220p'` on one hypothesis file; `./tools/zoom.py episodes/ep_0000/frames/step_1914_ore.png 210 0 100 80` (turn 31).

**MCU MFM**, `tools/episodes.py` invocations from `codex_turns`:

| | lad2_mfm | lad3_mfmr | lad2_logbook |
|---|---|---|---|
| episodes.py calls (turns with a call) | 25 (22/89) | 22 (21/68) | 0 |
| `--last` / `--steps` / `--grep` / `--sheet` | 20 / 5 / 1 / 1 | 10 / 12 / 1 / 1 | |
| `--near` (spatial) / `--tag` (semantic-ish) / `--action` | **0 / 0 / 0** | **0 / 0 / 0** | |
| grep/rg/tail/sed over `logs.txt` | 126 | 94 | 129 |
| stored images opened | **0** | **0** | 0 |

Examples: turn 14 `./tools/episodes.py --steps 330 390 --json | tail -n 30`; turn 69
`--steps 8990 9040 --grep "harvest_tree" --json`; turn 13 `--last 8 --sheet /tmp/recent.png`
(the sheet was written and never viewed). Log grepping outnumbers episode queries 5 to 1, and
the logbook control greps the log about as often (129 vs 126), so the tool is additive, not a
substitute. The CLI defines `--near`, `--radius`, `--tag`, `--action` (`mfm/memory/tools/
episodes.py:185-189`); none was ever used.

**KiCad world model** (`kicad_wm_v2_projdir`, 824 completed commands): `logs.txt` 554,
`world_model/` 301, `hypotheses/` 263, frame references 141 of which **126 re-open a frame
older than the previous turn** (lag histogram 2:19, 3:29, 4:14, 5:18, 6:23, 7:15, 8:7, one
at lag 80), `tools/zoom.py` **98**, `view_image_calls` 138. 642 distinct command shapes.
Example (task 34877be3 turn 42): `./tools/zoom.py frames/step_0040.png 760 300 680 230
/tmp/circuit_zoom.png && ./tools/zoom.py frames/step_0040.png 750 0 500 90 /tmp/title_zoom.png`.

**KiCad MFM / carry.** `cat logs.txt` 449 times and `tail -N logs.txt` dominate (54 distinct
command shapes over 1,074 commands). `tools/episodes.py` was invoked **twice in the entire
corpus** (`kicad_mfm_projdir/4c913e30` turn 121 `--last 8`; `c4baee36` turn 20
`--tag screen_unchanged --last 8`). `--previous`, `--same-screen`, `--steps`, `--grep`,
`--sheet`: 0 uses. `previous/` was read in 3 turns (mfmcarry) and 5 (plcarry) of ~1,070.
`view_image_calls`: mfm_gpt6hint 0, mfmcarry 0, prolong_gpt6hint 0. No command failed; the
gap is non-use. `AGENTS.md:95` advertised the tool explicitly.

---

## 5. Belief revision and versioning

Current facts vs obsolete hypotheses; rollback after failure.

| arm | verdict |
|---|---|
| MCU world model (live) | partial |
| MCU world model (relay) | strong (the strongest evidence in the corpus) |
| MCU MFM | absent (untestable for rollback: no death occurred) |
| KiCad world model | strong |
| KiCad MFM / carry | absent |

**MCU relay lineage.** Every node id carries forward (138/138 dm14x→dm15, 173/173
dm15→dm16) and 40 of 138 changed status or statement in one hop. One belief over three
lives, `location_diamond_block_11861`:

```
dm14x: refuted   conf=0.00  "Refuted as future-trajectory contamination..."
dm15 : active    conf=0.35  "...only an unverified cross-trajectory visual estimate; no diamond mine/pickup event..."
dm16 : confirmed conf=1.00  "The live diamond-ore block was at the targeted centre near (-3060.5,12.5,-5558.5)
                             and was successfully broken at step 11261."
```

`goal_diamond` follows the same arc to confirmed at step 11444, the 10/10 run. Status mix
moves from 72 refuted / 52 confirmed (dm14x) to 96 refuted / 94 confirmed / 15 stale / 4
active (dm16). `rules.md` is versioned with counters: rule 1 "Trust only current-prefix
events ... [x37]" → "[x55]" → "[x73]"; total hits 121 → 243 → 259. Death handling exists as
inherited-record cleanup: `state_death_diamond_run_10624.md` "This death-at-step-10624
record belongs to a prior trajectory and is stale; it is not a live state constraint at step
5400." The ore registry is append-only (dm15→dm16: 8 additions, 0 edits, 0 deletions).

**KiCad world model.** Final graphs: 580 nodes, 348 confirmed, 139 active, 68 stale, **25
refuted**, 425 updated after creation, 57 evidence strings containing "conflicts --".
Verbatim refutation (task 4c913e30, `h18`, created 76, updated 176, confidence 0.1):

> "T68 [SCREEN] frames/step_0068.png: VIN and GND are visibly committed at J1 ..."
> "T168 [SCREEN] frames/step_0168.png: conflicts -- later close inspection visibly showed J1
> pin 1 still had an open endpoint circle and VIN was offset, so the early visual
> interpretation was wrong."

Turn-by-turn trajectories are visible in the prompt graph view: `h2` climbs "under test for
1 ... 17 turns (budget 15)" from turn 9 to 25, then turn 27 `stale conf=0.70`, matching
`discipline.stale_by_budget: 1` in `results.jsonl`. Discipline counters over 15 tasks:
`stale_by_budget` fired in 5, `confidence_capped` in 2, `confirm_reverted` 0, `outcomes_applied` 0.
Cross-task document evolution, `history/00_34877be3/procedural.md` vs `01_458f5f5c`:

> v00: "## Labels / power symbols / (unverified) Not exercised; inspect current UI and verify attachment."
> v01: "- Power: hover pin, `p`; verify chooser, replace query, Enter; verify floating anchor,
> click pin, Esc; check persistence (task 458f5f5c T145,T151 [SCREEN] frames/step_0145.png ...)."

**MCU world model live.** 2 refuted, 2 stale of 29. `resource_stone_pickaxe_sticks_001`
(refuted, 0.99): "Step-2563 STATE reports stick x2, contradicting this belief's claim that
replacements were required." `goal_mine_iron_ore` decays to confidence 0.02;
`goal_iron_ingot_001` to stale 0.05. Counters: `goal_confidence_capped` 2, `stale_by_budget` 1,
`goal_confirm_reverted` 0, `claim_rejected` 0; the stale event surfaces in 12 prompts as
"1 hypothesis/es retired for sitting under test without moving."

**Gaps across all world-model arms.** The `[unverified: ...]` statement mark defined in both
`discipline.py` files appears in **zero** artefacts; the bare `(unverified)` hedge appears
twice in KiCad. `confirm_reverted` and `claim_rejected` never fired anywhere. Documents are
rewritten wholesale, so history snapshots record *what* changed but no artefact records *why*
a claim was dropped. No death occurred in wm_dragon1, so no in-run rollback is observed.

**MCU MFM.** No beliefs (`hypotheses.n = 0`). Verified facts and model claims are separated
structurally (`state.verified`, `outcome.milestone_transition`, `outcome.events` are
environment-emitted; the claim lives in `action.plan`), but nothing ever revised anything.
`outcome.flushed` is true on 2 lad2_mfm episodes (neither at a milestone). No death occurred
in either MFM arm (minimum health 18/20 in lad2_mfm), so rollback is untested. The control
did die (`lad2_logbook/logs.txt:2779` "YOU DIED at (-3018, 36, -5552) ...") and revised its
plan from the log ("The inventory was lost on death; eight milestones remain banked").

---

## 6. Closed-loop use

Retrieved memory modifying plan, action selection, verification, recovery.

| arm | verdict |
|---|---|
| MCU world model (live) | strong (one complete traced loop; plans cite nodes) |
| MCU world model (relay) | inferred only (no action logs exist) |
| MCU MFM | strong in lad3 (retrieval block), partial in lad2 (tool output → plan) |
| KiCad world model | partial (verification hold real; plans do not cite memory) |
| KiCad MFM / carry | partial (four `[SEEN BEFORE]` cases, two clear notes→action cases) |

**MCU world model live, the cleanest trace (step 1914).**

1. `logs.txt:2965` `[NOTE] mining stopped: iron-ore-like speckles on screen at (244, 7), 13 px.
   The flag-time frame is saved at episodes/ep_0000/frames/step_1914_ore.png -- zoom THAT file`
2. `codex_turns/turn_0031.events.jsonl`: `./tools/zoom.py episodes/ep_0000/frames/step_1914_ore.png 210 0 100 80`
   then `rg -n "ore.*flag|false positive|speckle|sentinel" hypotheses world_model` (no prior belief)
3. `logs.txt:2970` `[PLAN] The ore flag was a spruce-foliage false positive; no stone was exposed.
   Ore detection is disabled while pushing below the surface.` → `:2974 [ACTION] stair_down(depth=10,ore_watch=False)`
4. Belief written: `mechanism_ore_watch_surface_false_positive_001` (created step 1914)
5. Prescription obeyed later: `logs.txt:3512 [ACTION] strip_mine(length=370,ore_watch=True)` once stone was exposed.
   Totals: 33 `ore_watch=True`, 13 `ore_watch=False`.

Plan-to-graph coupling: **406 of 638 `[PLAN]` lines (64%) cite a hypothesis node id** (top:
`goal_wooden_pickaxe` 88, `goal_mine_iron_ore` 70, `resource_sticks_001` 60). 0 plan lines cite
a document or procedure file by name.

**MCU relay.** `dm16_.../hypotheses/location_registered_iron_target_3822.md`: "the seed-stable
iron target itself remains valid in ore_registry near player poses (-2993.3,55,-5564.7) ...
approach it through the current y55 east tunnel", a parent of `location_fresh_y55_east_4078`
which records "aim_at_ore centered it at 4418, and the environment recorded mine_block
iron_ore at 4446", matching dm16's milestone line `mine_iron_ore@4446`. Corroborated by the
memory's own evidence strings; **no relay run has a logs.txt**, so this is not independently
traced.

**MCU MFM, lad3_mfmr (retrieval block on).** 67 of 68 prompts carried the `[RECALL]` block;
36 carried a "changed nothing in its last N calls" streak line. Three block → plan pairs:

- turn 46: "`pillar_up` changed nothing in its last 3 calls (since step 7175 ...): 'pillar_up: a
  screen is open; close it first.'" → next procedure `close_inventory` (turns 46, 47, 49, 50);
  turn 50 briefing: "The furnace underfoot was reopening its GUI whenever pillar placement
  was attempted."
- turn 17: "`craft` changed nothing in its last 4 calls ... 'craft furnace: no screen is open --
  place_and_open(item="crafting_table") first'" → "a spruce trunk is directly ahead. One new
  log will provide enough planks for a replacement table" → `harvest_tree`.
- turn 25: "The same harness note ended the last 3 entries that carried one (since step 3094;
  dig_down x3)" → plan "Turn north and strip-mine horizontally", entries `equip_hotbar`,
  `look_abs`, `strip_mine(length=378)` (ep_000114). Caveat: turn 24's own plan already said
  "otherwise, begin an ore-watching horizontal tunnel", so the switch was partly pre-planned;
  the block coincided with it.

Counter-example: turns 34 to 38 carried the same `collect_drops` streak line five times while
the model kept planning around it.

**MCU MFM, lad2_mfm (no block).** Tool output entering the next plan verbatim: turn 14 ran
`--steps 330 390 --json`, which returned `ep_000010 ... milestone ['mine_log'] ... x -3007.939,
z -5563.973`; the plan reads "Travel to (-3008, -5564), where wood was previously found."
Turn 25 ran `--steps 1308 1308 --json` (`x=-3008.08, z=-5566.30`) and wrote "A prior successful
chop occurred beside it at (-3008.08, 69, -5566.30), so I'm using that grounded target rather
than spending the turn on another blind harvest." Turn 69 ran `--grep "harvest_tree"` and
concluded "The prior 'tree' was a detection miss, not a successful harvest."

Ore sentinel responses in both MFM arms (steps 8535, 10480; 4172, 5399, 6897, 8205) were
decided on the live attached frame plus the note; **no stored image was opened** before any
of them. The loop closed through the current frame, not through episodic memory.

**KiCad world model.** The verify-before-terminate hold fired once per task (15/15) and
changed the action in **12 of 15** (`wm_verify_outcome` "continued: ..." vs 3 "terminated").
`kicad_wm_v2_projdir/34877be3/workspace/logs.txt:405-413`: "The verification close-up found
BT1 still labeled `Battery` instead of `9V` ... Open BT1 properties, change its value to `9V`,
save again" → `[ACTIONS] mouse_move(420,430); key(e)`. Every prompt embeds the documents and
a graph view ("(29 more hypotheses not shown ... Grep there before proposing a node you may
already have.)"). But `[PLAN]` lines cite `procedural.md`, `world_model`, `checklist` 0 to 2
times per task, all in turn 1, and cite a hypothesis id **0** times.

**KiCad carry.** Four `[SEEN BEFORE]` injections in the corpus, all "earlier in this task"
(never cross-task, which follows from the zero cross-task hash matches). One changed the
action: `733d278a` turn 28 "[SEEN BEFORE] this exact screen appeared earlier in this task:
step 26: mouse_move(602,692); key(w); wait." → "The previous target was inside M1's pin
graphic ... route left" → coordinate moved 602 → 572, and turn 29's click succeeded. One
notes→action case: `kicad_mfmcarry_gpt6hint/34877be3` turn 7 read `notes/kicad.md` ("Toolbar
zoom-fit at normalized (254,86) restores page view; scroll zoom proved unreliable"), still
used scroll and over-zoomed, then turn 8 executed `key(esc); click(254,86)`, the note's
coordinate. Scores show no downstream effect: prolong_gpt6hint 0.406 ≥ plcarry 0.375 =
mfm_gpt6hint 0.375 > mfmcarry 0.361; wm_v2_projdir 0.111 vs prolong_projdir 0.133.

---

## Summary matrix

| capability | MCU WM live | MCU WM relay | MCU MFM | KiCad WM | KiCad MFM / carry |
|---|---|---|---|---|---|
| 1 Lossless episodic storage | partial | absent (stripped) | **strong** | absent | **strong** |
| 2 Structured abstractions | strong | **strong** | partial | **strong** | absent / partial |
| 3 Cross-modal links | partial | **strong** | strong in-episode | **strong** | weak |
| 4 Multi-scale retrieval | partial | n/a | partial (temporal only) | **strong** | absent |
| 5 Belief revision | partial | **strong** | absent | **strong** | absent |
| 6 Closed-loop use | **strong** | inferred | strong (lad3) / partial | partial | partial |

**Reading.** The two agent families are complementary and neither has all six. The
world-model arms demonstrate abstractions, cross-modal citation, belief revision and,
in wm_dragon1 and the KiCad verification hold, a real closed loop; they do not keep a
lossless episodic record. The MFM arms keep the lossless record with structured
state/action/outcome and, when the retrieval block is on, close the loop through
harness-computed text; they have no beliefs, no revision, and their spatial, semantic and
visual retrieval paths were never exercised by the model. Semantic search and rollback are
absent everywhere. In no arm did the model's own initiative reach into stored images
(MCU MFM 0 opens; KiCad MFM 0 to 8 `view_image` calls per 24 tasks); the only substantial
visual look-back is the KiCad world-model arm's 98 zooms and 126 older-frame re-opens.
