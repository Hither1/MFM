# MCU recall probes: when pixels carry what the text summary threw away

Purpose: isolate the one claim the campaign has never tested. Not "does structured memory
help" (the ladder measures that) but **"does keeping the pixels help, holding the text
memory constant"**. The design manipulates two things and holds everything else fixed:

- **Predictability** of the future query at observation time (known / partial / unknown).
- **Textual expressibility** of the discriminating feature (nameable in one word /
  verbose / not resolvable without magnification).

Predicted: text ≈ multimodal when relevance is known; multimodal ≫ text when it is not,
and the gap widens as expressibility falls.

---

## 0. The control that makes the claim clean

Do **not** make the text control `logbook`. It differs from `mfm` in five ways (no index,
no structured state, no per-episode outcome, no query tool, no zoom), so a win would be
unattributable. Use instead:

| arm | store | past frames | purpose |
|---|---|---|---|
| `mfm-text` | full episode store: index rows, state.json, action.json, outcome.json, `tools/episodes.py`, zoom on the **current** frame | **deleted at episode close** | the text control. Lossless *structured text* memory of every episode. |
| `mfm` | same | kept | the treatment. Differs **only** in whether past pixels survive. |
| `mfm-push` | same | kept, and the harness injects the candidate frames (or a contact sheet) into the reveal turn | upper bound: what the memory could give if the agent always asked |
| `oracle` | irrelevant | irrelevant | told the answer at reveal. Measures the motor floor, separating memory from navigation. |
| `logbook`, `wmlite` | log only / log + compiled `world.md` | none | secondary reference: raw log vs *summarised* text |

`mfm` minus `mfm-text` is attributable to pixels alone. Everything else is a reference
point. `oracle` is not optional: the MCU chassis burns thousands of steps on motor loops,
and without it a null result cannot be told apart from "nobody could execute it".

---

## 1. The environment: a gallery corridor

Built entirely from `custom_init_commands` in a task yaml, so it is deterministic and
needs no new engine features. Coordinates are relative to MCU's fixed spawn
(-3009.5, 71, -5572.5); the exact numbers come from the build probe (§6).

```
corridor  x -3008 .. -2944 (64 long), z -5573 .. -5571 (3 wide), floor y70, air y71-72, ceiling y73
alcoves   on the +z wall at x = -3004, -2996, -2988, -2980, -2972, -2964, -2956, -2948   (K = 8)
          each 3x3x3 at z -5570 .. -5568, opening onto the corridor
```

Per alcove `i`, four things:

| element | role | command sketch |
|---|---|---|
| chest with one item | **forces a stop** (see §5, pitfall 1) | `/setblock X 71 -5569 minecraft:chest{Items:[{id:"minecraft:iron_ingot",Count:1b,Slot:0b}]}` |
| wool block, unique colour | the **answer** (statistics-verifiable when broken) | `/setblock X 71 -5568 minecraft:<colour>_wool` |
| back-wall feature | the **key** the query names | see the expressibility ladder below |
| glowstone in the ceiling | fixed lighting | `/setblock X 73 -5569 minecraft:glowstone` |

Determinism: `/gamerule doMobSpawning false`, `/gamerule doDaylightCycle false`,
`/time set day`, `/weather clear`. Mobs in the corridor would confound everything.

### The expressibility ladder (the key feature)

| level | feature | build | legible at capture? | text cost to record |
|---|---|---|---|---|
| **L1** nameable | wool colour on the back wall | `/setblock` | yes | one word |
| **L2** verbose | 3x3 quilt of 9 coloured wool blocks | 9 `/setblock` | yes | nine words |
| **L3** sub-glance | 5x5 pattern of grey stones (stone / cobblestone / andesite / diorite / granite) at 6+ blocks | 25 `/setblock` | **no** — needs `zoom.py` | effectively unrecordable |
| **L4** semantic | painting art (`/summon minecraft:painting {Motive:...}`) or an item frame with a specific item | `/summon` | no | one word, *if* you zoomed |

L3 is the sharp case: the pattern is preserved perfectly in a 640x360 archived frame and
recoverable by a 4x crop, but at capture distance it is a grey smear that no honest text
summary can encode. L4 is the same point with a semantic label attached, at the cost of
NBT risk on this engine (§6). Start with L3.

Randomise, per run seed: which alcove holds which key, which wool colour, and **which
alcove is the target**. Counterbalance target position across cells so distance to the
target is balanced.

---

## 2. The three phases

1. **Observation (≈400 steps).** Cover task: *"Collect the iron ingot from each of the
   eight chests along this corridor."* Eight stops, eight `pickup` events, statistics-verified.
   Nothing about the decorations matters, and the task never mentions them.
2. **Delay (≈1,500–2,000 steps).** A real, unrelated task away from the gallery: *"Dig
   down and collect 20 cobblestone."* This fills `logs.txt` with unrelated sections and
   moves the agent 40+ blocks away, so re-walking the gallery costs travel.
3. **Reveal + query (budget B, ≈500 steps).** At step R the harness injects one note,
   identical in every arm:

   > `[NOTE] TASK UPDATE: return to the alcove whose back wall shows <key description> and
   > break the wool block in it. Nothing else scores from here.`

   The key description names the pattern **as it would be seen**, not the alcove index
   ("the back wall that is mostly cobblestone with a diagonal of andesite"). It must not
   leak the answer, the coordinates, or the alcove number.

Implementation of the reveal: a small hook that at step R calls `memory.add_note(...)` and
sets a goal line rendered by `_turn_prompt`. `[NOTE]` already reaches every log arm and is
dropped by `direct`, which is fine since `direct` is not in this experiment.

---

## 3. Conditions (predictability)

Injected at t=0, in the task text, identical wording across arms:

| condition | what the agent is told at t=0 |
|---|---|
| **Known (K)** | "Later you will be asked to return to the alcove whose back wall shows *<the exact key>*." |
| **Partial (P)** | "Later you will be asked to return to one alcove, identified by its back wall." |
| **Unknown (U)** | nothing. The cover task only. |

K lets both arms encode at capture time: the text arm can zoom the live frame and write
one line. P tells it the category but not the value, so the text arm must record **all
eight** back walls, at eight zooms. U gives it no reason to look at all.

The design is 3 conditions × 2 expressibility levels (L1 as the easy control, L3 as the
hard case) × arms. The minimal version (§7) runs one cell.

---

## 4. Metrics, all offline-scoreable

Two levels, deliberately separated because the chassis's motor competence is poor and
would otherwise swamp the memory signal.

**Recall (the memory measure).**
- *Named target*: does the agent's first post-reveal `[PLAN]`/briefing name the correct
  alcove, its coordinates, or the correct wool colour? Regex on plan text; also record
  the first alcove it heads for.
- *First alcove entered after R*, from `maps/visited.csv` / `ticks.jsonl` positions,
  by proximity. Chance = 1/K = 12.5%.

**Execution (the motor measure).**
- *First wool broken after R*, from the statistics (`mine_block <colour>_wool`). Correct /
  wrong / none.
- *Steps from R to the break.* Compare against the `oracle` arm's median as the floor.

**Process (what the arm actually did).**
- Retrieval calls after R: `tools/episodes.py` invocations and their flags, image opens,
  `zoom.py` calls, greps of `logs.txt`. Already instrumented via the rollout scan.
- **Encoding check, the most important diagnostic:** does the arm's text *before* R
  contain the discriminating feature? Grep `logs.txt` (and `world_model/` for `wmlite`)
  for the key description and the target colour. This splits a failure into
  *never encoded* versus *encoded but not retrieved*, which the score alone cannot.

**Cost of insurance (the secondary result).**
- Phase-1 steps and turns per arm per condition. Prediction: `mfm-text`'s phase 1 grows
  from U → P → K as it must record more up front, while `mfm`'s stays flat. That
  quantifies the thesis directly: text memory pays at capture for everything it might
  need; multimodal memory pays on demand.

---

## 5. Four pitfalls that would silently ruin the experiment

1. **Frame cadence is tied to decision boundaries, not to novelty.** The store writes one
   `observation/image.png` per *plan entry*, at the entry's first step. If the agent walks
   the whole corridor in one `go_to(n=330)`, **one** frame is saved and no alcove is
   photographed. The cover task (a chest in every alcove) exists to force one entry per
   alcove. Verify per run: every alcove has at least one episode whose position is within
   4 blocks of it, and open those frames by hand once. This pitfall is also a finding: a
   "save a frame when the view changes" rule would be a real improvement to the store.
2. **Zoom must exist in the arm.** `install_zoom_tool` lives in `mfm/memory/log.py` and
   the ladder workspaces did ship `tools/{episodes.py,zoom.py}`, but the plan records
   `tools/zoom.py` being dropped from the MCU mfm arm on 2026-09-05 because it was never
   called. L3/L4 are unanswerable without it. Restore it for these probes and confirm the
   file is present in the workspace before the run counts.
3. **The agent may never look.** Across all MCU MFM runs the model opened a stored image
   **zero** times and never used `--near` or `--tag`. So `mfm` can land at chance for lack
   of use rather than lack of information. `mfm-push` is what separates "the memory cannot
   support it" from "the agent does not use it", and the reveal note should say plainly
   that earlier frames are on disk and name the tool.
4. **Re-exploration makes the task free.** If phase 3's budget is generous, every arm just
   re-walks the corridor and looks again, and only efficiency differs. Set B from the
   pilot: B ≈ 2× the `oracle` median, which should be under the cost of re-searching K
   alcoves. Report the search cost explicitly (alcoves entered before the correct one).

---

## 6. Build order

1. **Build probe** (`probe_gallery.py`, in the style of the existing `probes/`): run the
   init commands, walk the corridor with a scripted plan, save one frame per alcove, and
   eyeball them. Confirms the corridor is walkable, the alcoves are visible from the
   corridor, the lighting is fixed, and each L3 pattern is (a) a grey smear at capture and
   (b) unambiguous under a 4x zoom. If `/summon painting` misbehaves on this engine, L4
   falls back to item frames or is dropped; L3 needs only `/setblock` and cannot fail this
   way.
2. **Oracle run**: the answer given at reveal. Fixes B and proves the task is executable.
3. **G1 minimal cell** (§7).
4. **Full grid** if G1 separates.

---

## 7. G1: the minimal existence proof

One cell, two arms, three runs each. Enough to see whether the effect exists before
spending a grid.

- K = 3 alcoves, corridor 24 long. Expressibility **L3**. Condition **Unknown**.
- Phase 1 ≈ 150 steps, delay ≈ 600, phase 3 budget from the oracle.
- Arms: `mfm-text` and `mfm`. (Add `mfm-push` if both land at chance.)
- Chance = 33%, so this cell cannot prove much on its own; it is a smoke test for the
  machinery: does every alcove get photographed, does zoom resolve the pattern, does the
  reveal reach the prompt, does the scoring read out cleanly.

Pass condition for G1 is procedural, not statistical: three `mfm` runs where the agent
*could* have answered from its own store, verified by a human opening the archived frames
and zooming them.

---

## 8. Predicted result matrix

Rows are the interesting contrast only (`mfm` vs `mfm-text`). Chance = 1/K.

| condition | expressibility | mfm-text | mfm | why |
|---|---|---|---|---|
| Known | L1 | high | high | one word, written at capture |
| Known | L3 | high | high | text arm zooms the live frame once and records it |
| Partial | L1 | high | high | eight colour words is cheap |
| Partial | L3 | medium | high | text arm must zoom all eight at capture; costly and error-prone |
| Unknown | L1 | low | high | it *could* have written the colour and had no reason to |
| Unknown | L3 | ≈ chance | high | it *could not* have written it, and cannot go back |

The two diagonal cells are the paper's figure: **Known/L3 ≈, Unknown/L3 ≫**. The Unknown/L1
cell separates *summarisation* loss (the model chose not to record) from Unknown/L3's
*representational* loss (the text channel could not carry it).

---

## 9. Two further probes worth building after the gallery

**C1, change detection.** One room, visited in phase 1. During phase 2 the harness alters
one block (`/setblock`). Reveal: *"one block in the room you passed has changed; restore
it."* The answer requires comparing the current view to an archived frame. Text has no
representation of "the wall looked like this", so `mfm-text` is at chance by construction
and the only question is whether `mfm` retrieves. This is the purest multimodal case in
the set and the cheapest to build.

**O1, the ecological one.** No new blocks: during a normal mining phase, place an iron
vein visible in a wall but out of reach (behind glass, or across a ravine). Reveal 3,000
steps later: *"return to the iron you saw and mine it."* This is the campaign's real
failure mode (agents re-derive ore locations they had already seen; the ore sentinel
already writes a `_ore` frame). A win here transfers directly to the benchmark score
rather than to a synthetic room.

---

## 10. What the hand-written Q&A pilot showed (2026-09-06), and what it changes

*Both probes were removed on 2026-09-06 once they had served their purpose: the
hand-written set below, and the channel set of §11. Their run outputs are kept under
`probes/out/` as the evidence for what these two sections claim.*

A probe (since removed) was built and run before any gallery work: a workspace seeded with
lad3_mfmr's 304-episode store, one question per Codex turn, no simulator. Three arms:
`prior` (no store at all), `mfm-text` (store with every image deleted), `mfm` (store as
written). Ten questions, six intended as vision-only.

| question | kind | chance | prior | text | mfm | mfm views |
|---|---|---|---|---|---|---|
| forest_view | V | 25% | OK | OK | OK | 1 |
| toast | V | 25% | OK | OK | OK | 1 |
| grid_size | V | 50% | miss | OK | OK | 1 |
| ceiling_material | V | 25% | miss | miss | miss | 1 |
| chamber_texture | V | 25% | miss | OK | OK | 1 |
| ore_where | V | 25% | miss | OK | miss | 2 |
| iron_y | T | - | miss | OK | OK | 0 |
| cobble_5399 | T | - | miss | OK | OK | 0 |
| most_common | T | - | miss | OK | OK | 0 |
| flag_4172 | VT | 50% | OK | OK | OK | 1 |
| **total** | | | **3/10** | **9/10** | **8/10** | |

Five findings, each of which changes the gallery design above.

1. **The store is read and is informative.** Text control questions: prior 0/3, memory
   arms 3/3. The agent parses `index.jsonl`, `state.json` and `outcome.json` competently
   and used `episodes.py` to do it. The substrate is not the problem.
2. **Pixels added nothing here, and cost one answer.** On the four vision questions that
   priors could not answer: text 3/4, mfm 2/4. `mfm` lost `ore_where` by looking at both
   frames and answering "both", where the text arm reasoned correctly from the inventory
   deltas of *later* episodes. Structured text about what happened next can beat looking.
3. **Three of ten questions were answerable with no memory at all** and must be discarded.
   A prior-only arm is therefore not optional: **run it first and delete every question it
   gets right**, before spending a single treatment run. This is now step 0 of any probe.
4. **The store's text leaks the answer whenever the feature is task-relevant.** Every
   question here was about scenery incidental to an episode whose action record described
   the task, so the record implied the scenery. The gallery avoids this by construction,
   because the decorations are irrelevant to the cover task and appear in no action,
   outcome or index row. That property is now the gallery's central requirement, not a
   nicety: **if the action record can imply the feature, the probe is void.**
5. **The model looked but misread, and never magnified.** It opened a frame on every
   vision question, so "the agent never looks" is not the whole story once the task *is*
   the question. But it called a brown dirt ceiling "iron ore" with high confidence, and
   it ran `zoom.py` **zero** times across all ten questions despite the tool being present
   and documented. So a sub-glance feature (L3/L4) may fail for want of magnification
   rather than for want of pixels.

Two additions to the build order in §6, before step 3:

- **0. Prior-only screening.** Ask the questions with an empty workspace. Anything
  answered correctly is cut.
- **2b. Perception pre-test.** Show the model the frame directly, with the discriminating
  question, and confirm it reads the feature correctly at close to 100%. `ceiling_material`
  failed this test unknowingly, and a gallery built on a feature the model cannot read
  measures perception, not memory. If the model will not zoom on its own, either the
  reveal note must tell it to, or the feature must be legible without magnification.

The caveat that stands: these are single runs per cell on one model at medium effort, and
`ceiling_material` was also a badly worded question, since naming the episode as "the one
that scored the mine_iron_ore milestone" primes the wrong answer for both arms.

---

## 11. The channel test: pixels demonstrably carry what the text cannot (2026-09-06)

Section 10's question set failed because a natural run's text implies its own scenery. The
fix was a question whose ground truth is **computed from the PNG** rather than judged, so
the leak is closed by construction: for each of 12 frames, *is the left half or the right
half brighter, ignoring the HUD strip*. Frames were selected only where the gap is at
least 10 grey levels. No field in any arm encodes frame luminance; chance is exactly 50%
whatever the model knows about Minecraft; and grading is arithmetic, which removes the
false pass that let "brown flecks" count as correct in §10.

| arm | graded | correct | accuracy | p vs chance | median s/question | frames opened | confidence |
|---|---|---|---|---|---|---|---|
| `prior` (no store) | 11 | 5 | 45% | 0.73 | 12 | 0 | low x12 |
| `mfm-text` (store, images deleted) | 9 | 6 | 67% | 0.25 | 70 | 0 (8 failed attempts) | low x11 |
| `mfm` (store with images) | 12 | **12** | **100%** | **0.0002** | 18 | 12 | high x12 |

Pooled text-only arms: 11/20, 55%, p = 0.41. Indistinguishable from chance.

**This is the existence proof the campaign lacked.** Given a store it can address by path,
the agent opens exactly one frame per question, reads a fact no text field carries, and is
right 12 times out of 12 (1 in 4,096 by chance) with high confidence throughout.

Three details worth keeping.

- **The text arm knew it was blind and said so.** Every `mfm-text` answer states outright
  that the frame is absent; its 6/9 is explicit guessing, and its confidence is `low` on
  all 11 answers it produced. It is not a weak reader, it is a correctly blind control.
- **Pixels were also cheaper.** `mfm` median 18 s per question against `mfm-text`'s 70 s,
  including one 600 s timeout. The blind arm spends its budget searching for something
  that is not there. Multimodal memory saved time here, it did not cost it.
- **Instrumentation caveat:** `view_image_calls` from the rollout audit counts *attempts*,
  not successful views. `mfm-text` shows 8 while having zero PNGs in its workspace
  (verified). Any campaign figure using this counter is an upper bound on real looks.

**What this does and does not license.** It licenses the claim that the archived frame is
a real, retrievable information channel that the structured text does not duplicate, and
that the agent will use it when the task is a question addressed to a named episode. It
does **not** show that the channel helps on a task, that the agent will consult it
unprompted mid-run, or that it can read a subtle feature: the agent still ran `zoom.py`
zero times across all 34 turns of §10 and §11, and it misread a dirt ceiling as iron ore
in §10. The gallery probes remain the test of whether the channel pays off when nobody
tells the agent which episode to open.

---

## 12. The gallery is built and renders (2026-09-06)

`MCU-ladder/mcu_worldmodel/gallery.py` generates the world as 103 `/fill` and `/setblock`
commands; `stages/s12_gallery.py` raises it and photographs every alcove. Build probe
job 44914124: **10 checks, 0 failed, 18 frames**. Figure: `MFM/figures/gallery_alcoves.png`.

Six things the probe caught that the design on paper did not. Each would have been found
only after a wave of full runs, or not at all.

| # | found | fix |
|---|---|---|
| 1 | `env.sh` restores the engine by copying from `$MCU_PREFIX/MineStudio`, which does not exist on this cluster | don't source it; use the cluster java 1.8 + node-local `setup_env.sh`, as `arm.sbatch` documents |
| 2 | the ladder venv carries a **frozen copy** of `mfm` as a site package, older than the repo | put the MFM root first on `PYTHONPATH`, which precedes site-packages |
| 3 | every `/fill` printed "Changed the block at ..." into chat, covering the lower-left third of **every frame**, including the ones the store archives | `/gamerule sendCommandFeedback false` as the first command |
| 4 | `smooth_stone` and `stone` are indistinguishable at 4x, so a key mixing them measures eyesight | palette is four textures that differ in STRUCTURE: stone (flat), cobblestone (lumpy), andesite (mottled), stone_bricks (regular grid) |
| 5 | **the chest and the answer block occluded the bottom row of a 3x3 key** from the corridor | key moved to 3x2 at y72..73, above the y71 furniture; whole key visible from the corridor |
| 6 | seed 0's first draw had both rows identical (three vertical stripes), and dominance was unconstrained | reject row-symmetric keys and keys where one texture fills 5 of 6 cells |

Item 5 is the one that mattered most: with a 3x3 key the target wall could not have been
read from the archived frame at all, so the experiment would have measured navigation
rather than memory, and every arm would have looked equally blind.

**Where the difficulty actually landed.** Cell-mean contrast across the key at corridor
distance is 35-42 grey levels, so the wall is not a uniform smear: a cobblestone-heavy key
(alcove 5) is obviously different in character from a stone-heavy one (alcove 4) even in
the wide frame. The hard discrimination is `stone` vs `stone_bricks`. So the key sits
between L2 and L3 of §1's ladder rather than squarely at L3, and the honest reading is
that an agent *could* encode "the cobblestone room" cheaply if it had reason to. Whether
it can encode the full six-cell key without magnification is the perception pre-test
(§10, step 2b), which is the next thing to run: show the model a corridor frame, ask it
to read that alcove's key, and compare against the answer key `s12_gallery.py` writes.
The removed probe did this shape of thing; a perception test needs only a few lines
against the gallery frames, and does not need that harness back.

**Still to build before a wave**: the reveal hook (inject the query note at step R), the
`mfm-text` control (delete `observation/image.png` at episode close), the task yaml wiring
`build_commands` into `custom_init_commands` with the cover task text, and the offline
scorer (first alcove entered, first wool broken, encoding grep).

---

## 13. Five probes beyond the gallery (2026-09-06)

The gallery tests one mechanism -- a feature too fine to put in words -- in one setting, a
corridor of alcoves. Five more probes now exist in `MCU-ladder/mcu_worldmodel/probes/`,
each built around a *different* reason the text channel loses the information, and none of
them a corridor. They share a chassis (`probe_run.py`, `driver.py`, `score.py`) so an arm
is comparable across them, and every one is scored arithmetically with no judge.

| | probe | text loses because | primary readout | chance |
|---|---|---|---|---|
| P1 | `vista` | a bearing is not a position: the fix needs two frames | error in blocks of the stated coordinate | none (continuous) |
| P2 | `ledge` | a sentence keeps the object and discards the geometry | 3 stated plan facts | 1/8 for all three |
| P3 | `cavein` | nobody records a wall's composition, and the wall is gone | **6 cells, graded** | 1/4 per cell |
| P4 | `pantry` | container contents and absences are in no text field | the named pair | 1/66 |
| P5 | `doppel` | the exhaustive object summary is identical for all four | the named cabin | 1/4 |

### 13.1 The three design rules these probes added

**The evidence must be destroyed before the query.** Every probe except P2 alters the world
during the delay phase: the tower collapses, the wall caves in, the chest is robbed, the
water drains. Without this, an agent can walk back and look, and the probe measures
navigation efficiency rather than memory -- pitfall 4 of §5, which the gallery only priced
rather than closed. The driver records how far the agent was when the alteration landed
(`agent_distance_at_mutation`), and a run where it was within 40 blocks is **void**: it
watched the answer being removed.

**Score the plan, not only the act.** Each reveal asks the agent to *state* something before
it moves -- the coordinates, the wall and the depth, the two rows, the two item names, the
cabin's ordinal. That statement is the memory readout; arrival and retrieval are the motor
readout, reported separately. MCU's traversal is poor enough that a probe scored only on
arrival would mostly measure walking. It also makes P3 graded rather than binary, which at
three runs per cell is the difference between a tally and a measurement.

**The query must not contain its own answer.** Enforced by tests, not by care:
`test_reveal_states_no_coordinates`, `test_cavein_reveal_does_not_name_the_pattern`,
`test_doppel_reveal_does_not_name_the_cabin`, `test_pantry_reveal_does_not_name_the_missing_items`,
and the converse `test_oracle_does_contain_the_answer` -- because a motor floor that was
not actually told the answer is not a floor.

### 13.2 Two things the code found that the prose had not

**`[GRID]` carries occupancy, never identity.** P4's go/no-go, checked against a real run's
`logs.txt` before the probe was written: `[GRID] inventory screen, occupied: 2x2 cells [-]
out=FULL`. No item names, no counts -- and it is computed from the frame by
`vision.slot_occupied` in the first place. `state.json` records the *player's* inventory and
has no field for a container's. So the screenshot of an open chest is the only record of
what that chest held, in every arm. Had `[GRID]` named items, P4 would not exist.

**The spawn is not reproducible, so the probes bring their own world.**
`env.make_sim` registers `FastResetCallback(biomes=["plains","forest"], random_tp_range=1000)`,
which re-rolls the spawn until it lands in a plains or forest. A probe whose ground truth
was "the ravine you passed" would be a different experiment every run. Everything is
therefore built from `/fill` and `/setblock` on a flat deck at y80 (`probes/arena.py`),
raised *after* `sim.reset()` with settling ticks rather than through `custom_init_commands`,
which fires its list without settling. What the designs called "natural" was never
load-bearing; the information structure is.

### 13.3 Why a single-process runner

The ladder arms run split: a green server owns the simulator, a purple A2A agent owns the
memory, and the purple side has no simulator handle at all. These probes need to alter the
world mid-run (host-side `execute_cmd`) *and* inject the query into the agent's memory
(agent-side), so `mcu_worldmodel/probe_run.py` owns both. Every probe arm runs through that
one file, which is what keeps the arms comparable to each other -- the comparison the
experiment is actually about. The ladder's own runner and pins are untouched.

The `mfm-text` control is implemented in the driver, not in `mfm.memory.store`: it sweeps
archived PNGs from the workspace after each step, keeping the newest (the design's own
definition of the control -- zoom still works on the *current* frame). External, verifiable
by counting files at the end, and it cannot change what any pinned arm does.

`direct` is refused by the runner rather than supported: it drops harness notes, so it
would never receive the query and would be a silently blind arm rather than a control.

### 13.4 How to run them

```bash
# what a probe builds, with no engine at all
PYTHONPATH=. python3 -m mcu_worldmodel.probes.preview [--probe cavein] [--dump out/cmds]

# raise the worlds in the simulator and photograph them  <- do this first
sbatch slurm/probe_build.sbatch all 0        # or: <probe> <seed>

# one arm of one probe
sbatch slurm/probe_arm.sbatch cavein oracle   unknown 0   # the motor floor, run FIRST
sbatch slurm/probe_arm.sbatch cavein mfm      unknown 0
sbatch slurm/probe_arm.sbatch cavein mfm-text unknown 0

# score, pooled, with the void runs called out
PYTHONPATH=. python3 -m mcu_worldmodel.probes.score output/pr_*
```

`test/test_probes.py` covers the builds, the leak rules, the answer keys, the geometry and
every scorer, with no engine (76 tests).

### 13.5 What the build probe found (jobs 44927151, 44930127, 44930574;
final clean run 44932441: **48 checks, 0 failed**)

Seven things, in the same spirit as §12's six for the gallery. Two of them would have
produced a wave of runs that measured nothing at all, and neither was findable on paper.

| # | found | fix |
|---|---|---|
| 1 | **Minecraft truncates any command over 256 characters, silently.** The cave-in supply chest (389 chars) and both pantry chests (339 and 538) came back as `Expected '}'` / `Unclosed quoted string` with `Count:8b<--[HERE]`. No exception, no non-zero status: **the chests simply were not there**, and the pantry probe had no chest to open | `arena.chest()` emits an empty chest plus one short `/replaceitem` per stack; longest command across all five probes is now 74 chars, asserted per probe per seed |
| 2 | `sendCommandFeedback false` silences successes but **nothing silences command errors** -- six red `No blocks were filled` lines across the lower-left of every cave-in frame, the same disease §12.3 cured for successes | issue no failing commands (carve before painting), and wait 260 ticks after the build in both the stage and the runner, because Minecraft holds a chat line for ten seconds |
| 3 | every `/give` printed `MineRLAgent0 has made the advancement [Stone Age]` across the bottom of every vista frame | `/gamerule announceAdvancements false`, and `/give` moved ahead of the build so the toast expires during it |
| 4 | the cave-in wall was **too dark to read**: the nearest glowstone was behind the camera | light the face from three sides, and back the close viewpoint off to four blocks |
| 5 | with the light fixed the six cells were **still** unreadable -- not because the textures are subtle but because the key was flush in a wall of the same grey stone, so nothing said where the key ended | the tunnel opens into a 5x4 chamber and the whole face is laid in brick with the 3x2 key inset. Locating the key is now free, which is right: the difficulty is READING six textures, not finding them |
| 6 | **the doppelgangers' horizon was a second discriminator**: a green hillside over the wall behind one cabin, bare sky behind another, different per cabin and *surviving the drought* -- so the four were not identical at query time after all | that arena's rim raised to 12 blocks, and asserted |
| 7 | the same trap one level down: the deck's floor glowstone sits on a grid, and a grid out of phase with the cabin spacing would put a different lighting pattern around each cabin, which also survives the drought. It held **by luck** (18 divides 36) | `LIGHT_EVERY` must divide the cabin spacing, now a checked property |

Two more, from stage 14 (the model-free run smoke), both of which would have produced a
wave of runs in which no arm ever answered the question:

| # | found | fix |
|---|---|---|
| 8 | **the query would never have been READ.** `_turn_prompt` serves harness notices inline to the `worldmodel` and `wmlite` arms, but `logbook` and `mfm` -- the arms this experiment is actually about -- get only *"Your memory is ./logs.txt, grep it"*. A query delivered as a `[NOTE]` lands in the log and nowhere else, and the agent has no reason to grep for a question it does not know was asked | the driver renders the standing objective at the top of every turn prompt, in the same words for every arm. The note is kept as well: it is what puts the query into `logs.txt` and `outcome.json`, which is the record the leak audit reads |
| 9 | the phase schedule was absolute, so in any harness whose step counter also counts the world build, every boundary was already in the past when the driver attached: smoke job 44930995 fired **nothing** and reported only `start` and `end` | phases are compared relative to a run `origin`; everything recorded stays absolute, so the track, the events and the scorer all speak the same step numbers |

Item 8 is the one to remember. It is not a bug in any component -- every part behaved as
documented -- and no unit test could have caught it, because the failure is in the seam
between what the harness offers and what the design assumed it offered.

Items 6 and 7 are the ones worth carrying to any future probe: **when you destroy the
evidence, enumerate everything else that correlates with the answer and survives.** The
drought removes the pond; it does not remove the hill behind the cabin, or the lamp in the
floor beside it. A probe is only as blind as its least-controlled background.

**What the frames settle.** The vista's notched tower is legible from *both* survey sites
and the collapse leaves nothing but faint rubble, so triangulation is possible and
re-observation is not. The cave-in key reads correctly cell by cell at four blocks
(verified against the answer key: top *stone brick, plain stone, stone brick*; bottom
*andesite, plain stone, stone brick*) and is a **grey smear inside a visible frame** from
mid-tunnel -- exactly the gradient the design asks for. The pantry's chest screen opens and
its item icons are identifiable at 640x360. The drought leaves the water cabin and the
birch cabin indistinguishable.

**Stage 14** (`slurm/probe_smoke.sbatch`) passes 15/15 for `mfm` and 16/16 for `mfm-text`
(jobs 44931621, 44931652). It drives a whole run with no model and asserts the driver's
half: the query reaches `logs.txt`, the world changes at the right step, the track
and plans and frames are intercepted, statistics are snapshotted at both ends, and
`mfm-text` really is left with at most one PNG. It exists because `ProbeDriver` wraps
methods on objects it does not own (`memory.set_plan`, `memory.save_frame`,
`MCUEpisodes._observation`), and if one of those signatures moves the wrapper still runs,
the run still completes, and the scorer reads an empty file as "the agent said nothing".

### 13.6 What the build probe still has to answer

The same two questions the gallery's did, per probe, and no assertion can answer them:

1. Is the discriminating feature legible in the frame the cover task actually takes?
   If not, the probe measures perception rather than memory (§10, step 2b).
2. Is it a smear at capture distance -- would an honest text summary written at that moment
   have failed to record it? If it is plainly legible from the path, the `unknown` condition
   is not testing what it claims to.

Per probe, the specific worry: **P1** whether the tower is in an archived frame from *both*
sites (the driver checks this per run and voids it otherwise -- one `go_to` across the
plateau photographs nothing); **P2** whether the far alcove is legible from the walking lip,
34 degrees below the horizontal; **P3** whether the four textures are separable at tunnel
distance and under `zoom.py`; **P4** whether item icons in a chest GUI are identifiable at
640x360, which is this probe's whole go/no-go; **P5** whether the drought leaves the four
cabins genuinely identical, checked by diffing the `_AFTER` frames.

### 13.7 The cell where text should win

Worth running, and worth reporting. `index.jsonl` and `outcome.json` carry ordinality and
event history exactly, and pixels carry them badly -- §10's `ore_where` already showed the
text arm beating `mfm` by reasoning from later inventory deltas. A probe asking "which
shaft did you dig first" or "where were you when your pickaxe broke" belongs in the suite
for the same reason a placebo does: without it, this is a set of probes we win, rather than
a map of which channel carries what.

---

## 14. The nether portal (2026-09-09) -- the case where the un-expressible feature is ten integers

`DESIGN_portal_case_study.md`, `MCU_benchmark/task_configs/tasks/nether_portal{,_slack}/`.

Every probe above builds a world in which the discriminating feature is hard to write
down: a texture at distance, an item icon in a chest, four identical cabins. The portal
task is the same argument with the difficulty removed from the perception and put
entirely in the bookkeeping. The feature is not subtle at all -- it is which ten cells
hold obsidian -- and yet no channel the agent can read carries it: `inventory` counts
blocks, `use_item` counts placements, `mine_block` counts undoings, and none of them
says where. An arm that keeps its frames can check by looking; an arm that keeps a text
trace has recorded that ten blocks were spent.

It is also the only probe in this set drawn from an observed failure rather than
designed: arm `of3r` placed all ten obsidian, believed the frame finished, and spent
8,900 steps and 812 log entries recovering. That makes it the natural first thing to
show, and the scoring is a cell list rather than a score.
