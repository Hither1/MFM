# World Model as/from Multimodal Filesystem Memory

An embodied agent for MCU's two long-horizon tasks, whose memory is a filesystem it reads
programmatically and whose understanding of the world is a set of documents it periodically
re-derives from that filesystem.

## Why this shape

It is the union of two agents in the sibling `MineExplorer` repo, plus the one box neither
of them has.

| | what it contributes | what it lacked alone |
|---|---|---|
| a belief DAG in the prompt (`mc_agent/hypothesis_agent.py`) | a typed DAG of beliefs, and a *harness-enforced* discipline on it | the DAG was a prompt section, so it could never outgrow the context window |
| an append-only log on disk (`mc_agent/prolong_agent.py`) | an append-only log + persistent workspace the agent greps | no structure over the record; it re-derived its beliefs from raw log lines every turn |
| **this** | the DAG lives *in* the filesystem, and an induction pass compiles the trace into structured documents | — |

The consequence is two kinds of turn instead of one:

- **act turn** — cheap, frequent. Reads the current frame, the milestone checklist, the
  compiled world model and a *view* of the belief graph; writes `actions.json`.
- **induction turn** — expensive, every `--induction-every` steps. Reads the accumulated
  filesystem and rewrites the five world-model documents, and settles beliefs that acting
  never got back to.

Acting is driven by what is in front of you; nothing in an act turn ever goes back to look
at step 400. That is what the induction turn is for.

## Layout

```
memory/
  logs.txt              append-only trace: action, resulting state, prior analyses. GREP.
  events/events.jsonl   ground truth from MineRL's statistics. The agent cannot write here.
  maps/visited.csv      every position occupied, with step number.
  episodes/*/frames/    the first-person view per step, PNG at full 640x360 render size.
  hypotheses/           graph.json + one .md per belief (a projection, for grepping).
  world_model/          spatial.md semantic.md dynamics.md procedural.md causal.md
  entities/ locations/ procedures/   the agent's to organise.
```

Who writes what is enforced, not conventional: `assert_harness_files_intact` fails loudly
if the agent shrinks a harness-owned file. A belief and the fact that checks it must not
share a source, or the discipline layer has nothing to check against.

## Ground truth, and the discipline

MineRL reports `mine_block`, `craft_item`, `pickup`, `kill_entity`, `inventory` and
`location_stats`. `MilestoneLedger` turns those into the ordered progression each task is
scored on, and it never reads a model output.

Upstream, the agent ended its own episode with `ESC`, and that press was where the harness
caught a premature "I'm done". **MCU's action space has no `ESC`**, so the check is
continuous instead: every turn, a goal hypothesis the model marked `confirmed` that the
ledger has not verified is reverted, its confidence dropped, and its *statement* marked
`[unverified: ...]` — the statement, because that is what the prompt renders back. A
`claim.json` naming an unverified milestone locks those goals at 0.5.

This exists because of a measured failure: in MineExplorer's q35a campaign one run
self-confirmed a goal at step 2 from eight blocks away, and rode that belief at confidence
0.95+ for the remaining 198 steps. 70 of 177 goal nodes finished ≥0.9 and unverified.

## Crafting: why there is no crafting action, and what to do instead

`HumanSurvival` does not install `CraftAction` / `CraftNearbyAction` / `SmeltItemNearby` /
`PlaceBlock` / `EquipAction`, even though all five are fully implemented on the Python side.
The obvious fix is to install them. **It does not work, and the reason is in the engine.**

`com.minerl.multiagent.env.EnvServer` is the command dispatcher, and its entire verb
vocabulary is:

```
attack back camera chat drop dwheel equip forward hotbar
inventory jump left pickItem right sneak sprint swapHands use ESC
```

- `craft`, `nearbyCraft`, `nearbySmelt` and `place` **do not exist**. Sending one gives
  `NumberFormatException: For input string: "none"` in `EnvServerSocketHandler`, the step
  returns nothing, and the Python side dies in `struct.unpack` on a `None` reply.
- `equip` exists but **parses its argument as a number**, while `EquipAction` sends an item
  name. Installing it makes `reset()` itself throw, because `MinecraftSim.reset` sends a
  full `env.action_space.no_op()` — carrying `equip none` — for its empty frames.

The Malmo classes in the jar are a red herring: `com.microsoft.Malmo.Schemas` holds the
generated JAXB bindings (including a `NearbyCraftCommand` enum literally containing
`craftNearby`) and `Utils.CraftingHelper` is present, but the jar has **no
`MissionHandlers` package at all** — not even for the commands that work. The schema is
vestigial; the engine dispatches natively.

`mcu_worldmodel/craft_env.py` records all of this and installs the one thing that is both
supported and missing: `drop`. Run `python -m mcu_worldmodel.craft_env` on a compute node
to re-verify against the engine rather than trusting this file.

### Rebuilding from MCU-AgentBeats does not change this

`KWSMooBang/MCU-AgentBeats` was checked as a possible source of a craft-enabled build. It
is not one, and the reasons are worth recording so nobody re-tries it:

- Its `src/engine_util.py` downloads **the same artifact** — `CraftJarvis/SimulatorEngine`
  → `engine.zip` → `mcprec-6.13.jar`. That HF repo holds exactly `['.gitattributes',
  'engine.zip']`, last modified 2024-12-23. There is no other engine to get.
- It installs upstream MineStudio (1.1.5, git `278aa85`) rather than a vendored copy, but
  `HumanSurvival.create_actionables()` is **byte-identical** to the vendored one. The only
  difference in that whole file is one extra *observation*, `ObserveFromFullStats("custom")`.
- Its own README documents the same action space: "Format 3: Environment Format" lists
  `forward/back/left/right/jump/sneak/sprint/attack/use/drop/inventory/hotbar.1-9/camera`.
  No craft.

`SimpleHumanEmbodimentEnvSpec` in `human_controls.py` *does* install `CraftAction`,
`CraftNearbyAction`, `EquipAction` and `PlaceBlock` — but it is legacy MineRL support
targeting the old Malmo build, and against this engine it fails the same way. That path was
tested, not assumed.

### How crafting actually works here — and how any agent does it

Through the inventory GUI, exactly as a human does it. The engine has no craft command, so
this is the only route, and it is the route the benchmark's own baselines take: **VPT and
STEVE-1 are behaviour-cloned from human play, so they learned the visuomotor loop** — move
the mouse, watch the screen, click the slot. Nothing about crafting is special-cased for
them either.

The primitives are all present: `inventory` opens the screen (in **one** tick), `camera`
moves the cursor, `attack` is left-click, `use` is right-click, `hotbar.N` selects, `drop`
discards.

**The cursor is directly observable**, which is what finally made this tractable. With the
GUI up, a camera delta changes ~2.4–3.1k pixels (the cursor sprite plus the slot highlight
under it); with the GUI down the same delta changes ~141k (the whole world rotates). So
diffing two frames locates the cursor, and `locate_cursor.py` uses that to measure the
mapping instead of deriving it.

**The measurement that mattered:** `GUIConstants.MOUSE_MULTIPLIER = 0.1` suggests 10 px per
degree. That is the *human-play interface's* mouse→camera conversion and does not describe
cursor motion inside a GUI. Sweeping the cursor right in 6° steps puts x at 310 → 460
across 36°, i.e. **4.17 px/degree**. An 18px slot is therefore **~4.32°, not 1.8°**.

Everything that failed follows from that one number. Three separate open-loop craft macros
emitted well-formed sequences that moved nothing, because every move overshot by ~2.4×.
It also explains the cost of the runs that *did* succeed: with `CURSOR_DEG_PER_SLOT = 1.8`
the agent's `cursor_to(dx=2)` moved slightly under one slot, so it converged only by
repeated visual correction — visible in the log as sub-slot nudges (`dx=0.25`) near the end
of a craft, and ~450 steps for one 2×2 craft.

**So the design here is closed-loop, not open-loop.** The open-loop `craft` macro is
deliberately *not registered* — it would spend the step budget on a no-op that looks like a
real attempt. What is provided instead:

- correct slot units, so `cursor_to(dx=2)` really is two slots;
- recipe knowledge in the prompt (`gui.RECIPES`, `gui.can_craft`), so the agent knows what a
  recipe needs and whether it holds the ingredients before opening anything;
- `[GUI] open=` and `[INV]` delta lines per plan entry in `logs.txt`, so a `grep` can tell a
  click that landed from one that did not — the feedback a closed loop needs.

Two runs crafted before any of this: `crafting_table` at step 514 and `wooden_pickaxe` at
step 1142 (a 2×2 and a 3×3), both verified by `craft_item`.

### Probes, and what each settled

| module | question | answer |
|---|---|---|
| `craft_env.py` | can the craft handlers be installed? | no — engine has no such verb; `equip` takes a number |
| `probe_cursor.py` | does camera move the GUI cursor? | yes; and it clamps at the screen edge (45° → 447 px changed) |
| `locate_cursor.py` | where is the cursor, and what is the scale? | 4.17 px/degree, measured by frame-diff centroid |
| `calibrate_gui.py` | *(superseded)* | its 1089-candidate scan was invalid — see below |

`calibrate_gui.py`'s null result should not be trusted: it toggled the inventory twice per
candidate, and the toggle is edge-triggered on a single tick, so one missed edge inverts the
phase for every candidate after it. Its own output ends with `gui_open_after: false`, which
is the tell. Kept for the record, not for its conclusion.

### Corrections to the action space this implies

`entry.py`'s hardcoded `action_type="env"` dict is **not** the real action space. The
authority is `spec.actionables`, which additionally includes `pickItem`, `chat`, `mobs` and
`voxels`. `actions.py` follows the real one, and deliberately refuses `chat`: a from-scratch
run that can send `/give` can hand itself the entire tech tree.

Missing keys are harmless — `_process_action` skips any handler whose name is absent from
the action dict — so partial actions are valid and a fully populated no-op is never needed.

## The skill library (2026-09-03): one call per thing a human does

The macros above ended at the iron pickaxe, and every plan the models wrote was 57-72%
cursor micro-work. The library now covers what the whole MCU task suite exercises, as
closed-loop procedures that verify themselves on the game's statistics and say what
happened in a `[NOTE]`. Every module registers through `macros.py` (a marker key ->
tick function table), so `agent.py` is not edited per macro.

| module | procedures | verified on |
|---|---|---|
| `macros_gui.py` | `craft(item, count)`, `place_and_open(item)`, `furnace_load / furnace_take`, `mine_until(item)`, `drop_and_pickup(slot)` | `craft_item`, `use_item`, inventory deltas, the frame at the grid cells |
| `macros_world.py` | `place_at(x,y,z,item,face)`, `use_at(...)`, `fill_bucket()`, `fetch_water()`, `use_held(item,hold)`, `throw(item)`, `eat()`, `pillar_up(n)`, `build_wall / build_row / build_column`, `bridge_forward(n)`, `scan_around(steps)`, `sleep_in_bed(x,y,z)` | `use_item`, inventory, the held tool's wear, the measured position / y |
| `macros_nether.py` | `find_lava(n,y,leg)`, `make_obsidian(x,y,z)`, `mine_obsidian(x,y,z)`, `build_portal_frame(dist)`, `light_portal(dist)`, `enter_portal(dist|x,z)` | the lava mass's centroid and near edge (`vision.lava_view`) turned into the pool and RIM cells by one frame's ray geometry, bucket swaps, `mine_block obsidian`, `use_item`, portal purple in the frame, `biome_id` / the coordinate jump |
| `macros_container.py` | `container_take / container_put` (chest, double chest, barrel), `brew / brew_take`, `enchant(item, option)`, `stonecut(item, output)`; `vision.screen_kind` knows all of these screens plus the anvil | inventory deltas, the lapis count (an enchanted item reports no NBT), the frame at the cells |
| `macros_entity.py` | `face_entity(label)`, `fight(ticks, retreat_hp)`, `shoot_bow(shots)`, `block_with_shield`, `use_on_entity(item)`, `boat_forward`, `leave_boat`; `vision.find_moving_blob` + `entity_hint` (colours measured in the sim) | `kill_entity`, `custom.damage_dealt`, `use_item.<weapon>` (hits landed), inventory, position |
| `macros_end.py` | `throw_eye()` (the eye's flight tracked as a moving blob -> bearing), `travel_bearing(yaw, blocks)`, `fill_end_portal(x,y,z)`, `enter_end(x,y,z)`, `mine_end_stone()`, `break_crystal(shots)`, `attack_dragon(ticks)` | the eye count, `use_item`, the coordinate jump to the spawn platform, `pickup.end_stone`, the crystal vanishing, `custom.damage_dealt` / `kill_entity.ender_dragon` |

Facts the sim settled while building it (each is recorded next to the code that depends
on it; `stages/` replays them):

- **sneak + click in a GUI is shift-click** (quick-move). The craft output is taken with
  one such click: it crafts everything the grid holds and lands in the inventory, so no
  stack ever rides the cursor and the bank click that lost every s1 product is gone.
- **Furnace output is `craft_item`, never `pickup`.** `pickup` counts items picked up off
  the ground only; a milestone written `pickup iron_ingot` needs `drop_and_pickup`.
- **The inventory observation lags a GUI click by 5-15 ticks; `use_item` lags the
  inventory.** Lifts are judged on the frame (the slot renders empty at once); craft
  checks wait for the inventory; furnace loads are verified on inventory deltas (a single
  coal is consumed the instant smelting starts, so the fuel cell reads empty).
- **A milestone firing no longer clears a running GUI or module macro.** `craft_item`
  fires the moment the output is lifted; the entries behind it are what bank it.
- **Placement is trigonometry from `[STATE]`.** Aim at the shared plane between the
  target cell and its support (0.5 in for placing, 0.45 in for using a block -- a bed is
  0.56 high). Standing off a block's centre and aiming 55 degrees down hits the cell your
  own hitbox overlaps, which the game refuses. A support's top face is hidden once it is
  above the eye, and a click on its front face puts the block in front: `_build` tests
  face visibility against the ground and what it has placed, and tall walls / the portal
  frame pillar up first (rows 0-1 from the ground, then `height-2` blocks under the feet).
- **Sneaking does not stop the avatar at an edge here**, but the hitbox stands up to
  ~0.25 past it: `bridge_forward` walks to the edge + 0.2 one sneak-tick at a time
  (0.055 blocks each), turns around, and clicks the side face at 82-85 degrees.
- **Attack must be tapped to hit an entity**; a held attack never lands. Hits show as
  `use_item.<weapon>`, damage as `custom.damage_dealt` (tenths of a heart).
- **The E pressed on the tick a screen opens is swallowed**: opens and closes are closed
  loop on `isGuiOpen` (`_opengui` / `_closegui`), and `use_until_gui` settles a tick.

`gui.RECIPES` carries 83 vanilla recipes (tools of every tier, containers, furniture,
ranged gear, food, the `@wool` family) so `craft` compiles any of them from the real
inventory. `prompts.py` renders a generic **Skills by situation** section for every task
and the from-scratch mining doctrine only when `prompts.task_family(cfg)` says the
milestone list is that chain; a task with no milestone list is told so instead of being
told it is scored by one.

### Stage tests: the runner against the real engine

`stages/rig.py` runs the SAME `WorldModelAgent` against `MinecraftSim` with a scripted
backend: a stage prepares a world state with commands the evaluation never allows
(`/give`, `/tp`, `/setblock`, `/fill`, `/summon`), hands the runner one plan at a time,
and asserts on statistics, inventory and position. Run from the repo root:

```bash
source ./env.sh
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s1_gui         # crafts, furnace     30/30
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s2_world       # place/build/bridge/fetch_water  44/44
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s3_containers  # chest/brew/enchant  41/41
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s4_entities    # face/fight/shoot    20/23 *
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s5_nether      # obsidian -> Nether  7/7
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s6_ore         # ore sighting -> dug 9/9
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s7_chain       # deferred macros    7/7
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s8_bunker      # bunker + flee + lava escape + melee cadence + fightback 25/25
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s9_fortress    # fortress/blaze/enderman/eye 29/30 **
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s10_end        # eye -> portal -> End -> dragon 18/18
MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s11_lava       # find_lava -> rim -> obsidian 13/13
```

\* The three open s4 checks are measured limits, not missing code: shearing a sheep moves
no observation channel (the wool is an item entity that lands beside the sheep -- walk
there), and `shoot_bow` gets 1-2 of 3 arrows off at a skeleton that keeps moving (the
aim loop waits three still frames per shot because the rendered frame lags the state by
a tick).

\*\* s9 (the Nether leg, milestones 17-22, 2026-09-04): the fortress detector, the walk
that tunnels netherrack and bridges lava, `fight_blaze` on a NoAI and a live blaze, the
rod, `enderman_pit` + `fight(label="enderman")` on a NoAI enderman at the rim, the pearl,
blaze powder and the eye of ender all pass. The open check is a LIVE enderman from the
pit: a free one wanders out of the rim's view before the loop's three still frames (3 of
3 attempts) -- the stage's setup, not the macro; in the open the model's look at it is
what angers it and brings it to the rim. Everything ran on an Overworld netherrack
platform at midday, not in the Nether itself.

s11 (finding the lava, milestone 14, 2026-09-04) measures the geometry rather than
assuming it: in a lit stone room at y 11 with a 3x3 lava pool at a known offset, one
frame places the pool's near edge within 0.12 blocks dead ahead and 0.61 blocks at 30
degrees off the heading, and the fitted horizontal field of view is 101.6 degrees against
the 102 the code assumes. Two facts came out of it. A pool crosses the 2% sighting
threshold at about 3 blocks, not at the 7.5 where it is already visible (0.7% there), so
`find_lava` stops in pouring range on its own. And a pool sunk one block below the floor
is hidden behind its own lip beyond `width * 1.62 / drop` blocks -- a 3-wide one is
invisible past ~4.8 -- which is why the search walks the pools' own level instead of
looking for them from a ledge.

Every check reads statistics, the inventory or the position -- never the frame alone -- and
a failing macro must SAY so in a note. The frames and `memory/logs.txt` of a stage land
under `MCU_STAGE_OUT/<stage>_<time>/`.

### What is deliberately not in the harness

Nothing here reads the benchmark's grading criteria (`MCU_benchmark/auto_eval/`) or the
`thinking` hints in the task yamls: the capability list came from the public task texts,
the starting items and the game's own mechanics, and no macro keys on a task name. A
model chooses every parameter (what to build, where, how high); the harness only makes
the motor act reliable and reports what the world did.

## Running

The mfm arm of branch `spatial-grid` (the thin contract, the atoms, own scripts and
reflexes, the skill package, the carry of earlier lives) is launched with
`scripts/launch-og.sh`; its options and recipes are in [../README-mfm-arms.md](../README-mfm-arms.md).

```bash
python -m mcu_worldmodel.selftest          # no Java, GPU, or Codex needed

export MINESTUDIO_DIR=/n/netscratch/sham_lab/Lab/chloe00/MineStudio
sbatch slurm/worldmodel.sbatch diamond outputs/d1
sbatch slurm/worldmodel.sbatch dragon  outputs/g1
```

Outputs: `milestone_tracking.json` in the RDI-Foundation format (so a run is directly
comparable to their VPT/STEVE-1 baselines), `episode_0.mp4`, and
`worldmodel_report.json` with turn counts, belief statistics and discipline counters.

## Tasks

Both are `custom_init_commands: []` — genuinely from scratch, scored by milestone depth.

- `mine_diamond_from_scratch` — 10 milestones, log → crafting table → wooden pickaxe →
  cobblestone → stone pickaxe → iron ore → furnace → iron ingot → iron pickaxe → diamond.
- `kill_ender_dragon` — 24 milestones, the same spine continuing through diamond gear,
  obsidian, the Nether, blaze rods, ender pearls, eyes of ender, the End, and the dragon.
