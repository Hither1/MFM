# Multimodal Filesystem Memory (MFM)

Code for *Multimodal Filesystem Memory for Long-Horizon Embodied Agents*.

MFM gives an agent a directory as its memory. The harness writes an immutable record
into it: an append-only log, and one episode per action with the frame it started from,
the state, the action and the outcome, indexed by when, where and what. The model
searches that record with programs, opens the frames it needs, and writes its own
knowledge, procedures and working plan beside it.

This repository holds the method, the two baselines it is compared with (PRO-LONG,
VISTA) and direct evaluation, on the two benchmarks of the paper:

| benchmark | directory | arms |
|---|---|---|
| MCU-AgentBeats (Minecraft): Mine Diamond from Scratch, Ender Dragon, the Nether portal case study | `MCU/` | `direct`, `logbook` (PRO-LONG), `vista`, `mfm` (MFM), `mfm-matched` (MFM without procedures of its own) |
| CUABench-KiCad (25 tasks) | `CUA-KiCad/` | `direct`, `prolong-logonly` (PRO-LONG), `vista`, `mfm` (no cross-task memory), `mfm-carry` (MFM) |

## Layout

```
mfm/                    the method, benchmark-neutral
  memory/log.py           the append-only log and the workspace the model is given
  memory/store.py         the episode store and index.jsonl
  memory/tools/           episodes.py (query the index), zoom.py (magnify a frame):
                          copied into every MFM workspace, run by the model
  memory/recall.py        situation and action keys, screen hashes
  memory/carry.py         the finished tasks' records carried into the next task
  memory/consolidate.py   the situation table folded from the carried index
  agent/base.py           the turn protocol: observe, refill the plan queue, act
  backend/                one resumable Codex CLI conversation
  vista/                  the VISTA baseline
MCU/                    MCU-AgentBeats with the Minecraft chassis
  mcu_worldmodel/         the chassis: turn loop, contracts, procedures, perception
  worldmodel_purple_agent.py   the chassis served to the benchmark's green agent
  scripts/run-arm.sh      one life of one arm, end to end
CUA-KiCad/              the KiCad harness on cua-lite
  gym_codex/run_eval.py   one run of one arm over the tasks
  scripts/run_kicad_arm.sh
docs/
  PAPER_TO_CODE.md        each part of the paper and the code that implements it
  pseudocode.md           the MFM turn loop in pseudocode
tests/                  the offline suite; tests/pins_release/ pins what every arm
                        shows the model
```

## Install

```bash
git clone <this repository> MFM && cd MFM

# Minecraft
cd MCU && uv sync && cd ..            # the benchmark's own environment, MCU/.venv
# JDK 8, xvfb-run and the simulator engine: MCU/mcu_worldmodel/SETUP.md

# KiCad: cua-lite, podman and the desktop image: CUA-KiCad/docs/KICAD_RUNS.md
```

The arms call a model through a coding-agent CLI: the Codex CLI (`codex`, 0.153.4 in
the recorded runs) for the GPT models and Claude Code (`claude`) for Claude Opus 5.
Log the CLI in, or use `--route openrouter` with a key file.

## Running the arms of the paper

### Minecraft

One command runs one life: the environment server, the agent and the evaluation
client. From `MCU/`:

```bash
bash scripts/run-arm.sh --arm mfm_diamond_s0 --memory mfm \
    --task mine_diamond_from_scratch --world-seed 0 \
    --green-port 9053 --purple-port 9063
```

| | option |
|---|---|
| method | `--memory direct` \| `logbook` \| `vista` \| `mfm` \| `mfm-matched` |
| task | `--task mine_diamond_from_scratch` (12,000 steps) \| `ender_dragon` (36,000) \| `nether_portal` (6,000); `--steps` overrides |
| seed | `--world-seed N`; without it the task's own world (0 for the diamond and the dragon, 42 for the portal) |
| model | `--model gpt-6-astra` (default) \| `gpt-5.6-sol` \| `gpt-6.1-sol`; `--cli claude --model claude-opus-5` (the paper) \| `claude-opus-5-5` |
| reasoning effort | `--effort high` (default) \| `xhigh` |
| an earlier life in the same world | `--seed-memory output/<arm>/episode_001/memory` (mfm and mfm-matched, repeatable), `--seed-log <logs.txt>` (logbook) |

Every arm reads a short contract (7 to 14 KB) and acts through raw actions alone: no arm
is given a built-in procedure of any grain (no aim, walk, craft or mine, no tree, shaft or
portal macro); the `mfm` arm's own scripts under `mine/procedures/` are the only
procedures there are. The arms that can read files (`logbook`, `mfm`, `mfm-matched`) have
the longer rules under `references/`; `direct` and `vista` cannot, and have the GUI facts
and the recipe list in the contract instead. The runner's own
guards (the lava stop, the pillar on a hit, the refusal of a repeated plan) are off for
every arm, and each contract says so.

The two MFM arms have the same memory (the log, the episodes with their frames, the
index and its query tool, the carried lives, and the `[RECENT]`, `[MAP]` and
`[OBSERVED]` blocks of the turn message, which `logbook` and `vista` do not get) and
differ in the harness around it:

- `mfm` is the arm of the paper's tables. The model writes its own procedures and
  reflexes under `mine/` and has the skill package.
- `mfm-matched` has the contract of `logbook`, so that what it adds to `logbook` is
  the memory alone (the `MFM_MEMORY` settings of
  `mcu_worldmodel/arms.py`). It writes no procedures and has no `mine/`. No result of
  the paper was recorded with it.

The result is `logs/<arm>_result.json`; the workspace, with the whole memory of the
life, is `output/<arm>/episode_001/memory/`. The header of `scripts/run-arm.sh`
documents every option and environment variable.

**Lives.** A life is one run of one budget. The Ender Dragon result of the paper
(16/24) was reached by the second and third lives of one chain: each life started with
the records of the lives before it (`--seed-memory`), on a 100,000-step budget under a
13 to 14 hour wall clock; the first life of that chain, from nothing, reached 10/24. To
run a chain, give each life the memory directory of the one before it:

```bash
bash scripts/run-arm.sh --arm dragon_l1 --memory mfm --task ender_dragon ...
bash scripts/run-arm.sh --arm dragon_l2 --memory mfm --task ender_dragon \
    --seed-memory output/dragon_l1/episode_001/memory ...
bash scripts/run-arm.sh --arm dragon_l3 --memory mfm --task ender_dragon \
    --seed-memory output/dragon_l2/episode_001/memory ...   # carries l1 and l2
```

<!-- TODO(authors): the three world seeds of Tables 2 and 4. -->

### KiCad

```bash
export WORK=/path/to/kicad-work
CUA-KiCad/scripts/run_kicad_arm.sh mfm-carry gpt-6-astra low $WORK/runs/mfm_gpt6_s0 \
    --task-order-seed 0
```

The first argument is the arm: `direct`, `prolong-logonly`, `vista`, `mfm`,
`mfm-carry`. The seed of a run is its task order. The score is `mean_reward` in
`<out>/summary.json`. Setup and accounts: `CUA-KiCad/docs/KICAD_RUNS.md`.

<!-- TODO(authors): the three task-order seeds and the reasoning effort of Table 3. -->

## Tests

```bash
bash scripts/run_tests.sh
```

The suite is offline: the simulator, the desktop container and the model are replaced
by stand-ins. `tests/pins_release/` holds, for every arm, the contract, the turn
prompts, the log, the index and a hash of every file of the workspace; a change to any
text a model is shown fails there.

## What the code does and does not reproduce

`docs/PAPER_TO_CODE.md` maps each section of the paper to the code and lists the
differences between the two.

### Runs made on this release

The `mfm` arm was run on this code on the tasks' default worlds, one chain of lives per
model and task, life 2 carrying life 1 and so on: every life of 2026-09-30 to 2026-10-04
is below. A closed life is its `total_score` (milestones); a life stopped by hand before
its budget (an account's limit, the API key's credits, a stalled turn loop, or our call)
is in parentheses with its distinct milestones and last step. The "examples" column says
which shipped examples and shared text the chain read: the ones before commit 1d96da8,
1d96da8's, b98270f's or 18cf214's (described below).

| task, budget per life | model, effort | examples | life 1 | life 2 | life 3 | life 4 | life 5 |
|---|---|---|---|---|---|---|---|
| Nether portal, 6,000 | gpt-6-astra high | before 1d96da8 | 100 (2/2) | 100 | | | |
| | claude-opus-5-5 high | before 1d96da8 | 100 | 100 | | | |
| | claude-opus-5-5 xhigh | before 1d96da8 | (1/2 at 994) | | | | |
| | gpt-6.1-sol xhigh | before 1d96da8 | 100 | 100 | | | |
| Diamond, 12,000 (the last life 40,000) | gpt-6-astra high | before 1d96da8 | 90 (9/10) | 90 | 90 | (6/10 at 2,270) | |
| | claude-opus-5-5 high | before 1d96da8 | 60 (6/10) | 80 (8/10) | (9/10 at 22,950) | | |
| Diamond, 40,000 | claude-opus-5-5 xhigh | before 1d96da8 | (6/10 at 2,709) | | | | |
| | claude-fable-5-1 high | before 1d96da8 | (9/10 at 9,708) | | | | |
| | gpt-6.1-sol xhigh | before 1d96da8 | (9/10 at 15,343) | | | | |
| | claude-opus-5-5 high | 1d96da8 | 100 (10/10) | | | | |
| | gpt-6.1-sol xhigh | 1d96da8 | (9/10 at 31,009) | | | | |
| Ender Dragon, 36,000 (lives 3-4 40,000) | gpt-6-astra high | before 1d96da8 | 37.5 (9/24) | 37.5 (9/24) | 41.67 (10/24) | (10/24 at 32,758) | |
| | claude-opus-5-5 high | before 1d96da8 | 54.17 (13/24) | 50 (12/24) | 54.17 (13/24) | 37.5 (9/24) | |
| Ender Dragon, 40,000 (sol life 2 80,000) | claude-opus-5-5 xhigh | before 1d96da8 | 37.5 (9/24) | (6/24 at 3,696) | | | |
| | claude-fable-5-1 high | before 1d96da8 | (6/24 at 11,294) | | | | |
| | gpt-6.1-sol xhigh | before 1d96da8 | 50 (12/24) | (10/24 at 31,265) | | | |
| Ender Dragon, 40,000, then 80,000 | gpt-6-astra high | 1d96da8 | 54.17 (13/24) | (14/24 at 42,934) | | | |
| | gpt-6-astra high | life 2 b98270f | (the life 1 above) | (12/24 at 21,834) | | | |
| | claude-opus-5-5 high | 1d96da8 | (12/24 at 11,697) | (15/24 at 61,229) | 62.5 (15/24) | 58.33 (14/24) | 62.5 (15/24) |
| | claude-opus-5-5 high | life 5 b98270f | (lives 1-4 above) | | | | 58.33 (14/24) |
| | gpt-6.1-sol xhigh | 1d96da8 | 41.67 (10/24) | (13/24 at 30,125) | | | |
| Ender Dragon, 80,000 | gpt-6.1-sol high | 18cf214 | (6/24 at 11,805) | | | | |

The two rows marked "life 2 b98270f" and "life 5 b98270f" are second branches of the
chains above them: each carried the same earlier lives and read b98270f's examples. The
14/24 of the astra life stopped at 42,934 includes `netherrack`, which that life mined
from a ruined portal at the surface of the default world: the milestone counts the
item, not the Nether.

Everything the agent wrote in each of these lives (its `mine/`: notes, guide, working
note, procedures, reflexes), and the full trajectories of the Opus and gpt-6-astra
dragon chains on 1d96da8 (with the Opus fifth life on b98270f), are on the dataset
(`Ced-Collab/MCUData`, `release-runs/`).

The three gpt-6 diamond lives on the 12,000-step budget all banked the iron pickaxe by
step 6,000 and none the diamond: two died in lava at the diamond level (the runner's
lava stop is off for every arm), the third ran out of steps. The lives of the paper's
own runs are on the dataset (`Ced-Collab/MCUData`, `carry-only-era/`).

What the dragon lives died of, and where their steps went (read from those
trajectories and the logs): Opus reaches the diamond pickaxe in 5,600 to
7,100 steps and the obsidian at 18,700 to 35,100, then dies at the lake or, at night,
at the surface (33 deaths in four lives, 22 to mobs, 7 of them dropping the diamond
pickaxe); gpt-6-astra spent its first two diamonds on the sword in every life and never
held a pickaxe at the lake; of the five lives that held obsidian, one tried to build a
portal. No life of this series entered the Nether.

The first lives ran with the earlier shipped examples: a `strip_segment` that never
looked at the next column's floor, and a starter `lava_ahead` keyed on the plan entry,
which inside any procedure of the model's own is the script's name, so it could not fire
there. Commit 1d96da8 changed both (the strip looks at the floor before every step; a
reflex sees the atom running, `atom`) and a scripted in-game check stopped the strip at
a lava floor; chains started after it are named `pub3_*` in the task notes.

Of the lives that mined obsidian, the ones that died next died of the portal itself:
`lava_ahead` read a lit portal and the burning overlay as lava and pulled the avatar back
into the fire, a frame cell went to a fallback face unannounced, and nothing told the
model that the inside must stay air or that a death at the lake burns the diamond
pickaxe. Commit b98270f changed the two reflex examples (flames are left to the plan,
the escape runs on lava's damage rate), gave reflexes `fire_frac` and `mainhand`, made
`place_at` name a fallback face and an unsettled aim, kept `look_at`'s heading for a cell
straight overhead, and added the portal recipe and the lake rule to the shared text. The
old and new reflex were replayed on the recorded episodes (16 -> 2 stops at the portal
fire, 5 -> 5 at a lava lake) and the portal task still completes; chains started after
it are `pub4_*`. The commit after it, from the deaths in the table above, added three
sentences to the shared text (the first three diamonds are the pickaxe; after a death
at night dig in before a step, and make the bed; never work from an open screen at the
lake, where reflexes are quiet) and `previous/scripts.md`, the carried lives' scripts
with their calls, refusals and last outcome, so a life copies what worked rather than
what has a name. One gpt-6.1-sol high life ran on it and was stopped at 11,805 steps
(6/24): too slow to finish (about 1,300 steps an hour on one-block plans).

### Continued lives (2026-10-05 and 10-06)

The Opus 5.5 dragon chain on 1d96da8 was continued from its second life, which held 12
obsidian, the diamond tools and a flint and steel at step 39,136 and then burned at its
own portal. A world cannot be resumed (it is generated at every reset), so a continued
life is a new life in the same world with the chain's memory carried, that kit given
back and the earlier milestones settled (`given_settled` in the task config: the
checklist shows them as done in the earlier life, and the scorer's total then counts
only what the life itself earns). "Distinct" below is the settled milestones plus the
new ones. All lives: claude-opus-5-5 high, `--own-live --near-deaths`,
`--install-carried` (`--own-live` is no longer a flag: the closed loops are part of the
mfm arm).

| life | start (task) | carried | steps | new in the life | distinct |
|---|---|---|---|---|---|
| `resume_opus55_l3` | the spawn, the kit (`ender_dragon_resume`) | lives 1-2 and the two lives of the blaze probe | 40,000 | `netherrack` (14,050); it re-earned the 15 as well | 16/24 |
| `resume2_opus55_l6` | the same, with food | those and `resume_opus55_l3` | 40,000 | `netherrack` (8,665) | 16/24 |
| `fort_opus55_l6` | a bridge of the Nether fortress (`ender_dragon_fortress`) | the same five | 30,000 | `kill_blaze` (2,293) | 17/24 |
| `fort2_opus55_l7` | the same bridge, the respawn point set on it | those and `fort_opus55_l6` | 30,000 | `kill_blaze` (421), `blaze_rod` (431), `blaze_powder` (458) | 19/24 |

The two fortress lives are STAGED: the search is handed over. The nearest fortress is
488 blocks from where the spawn-linked portal lands, and every life that entered the
Nether died within 70 blocks of that landing, a shelf over the lava sea. The avatar is
put on a brick bridge 19 blocks from a blaze spawner (found with `/locate` and
`MCU/scripts/fortress_map.py`, which reads the engine's voxel channel and is never shown
to an agent), with the chain's kit, food, and the shield and iron armour of the blaze
probe; the second fortress life also respawns on the bridge. What they show is that the
fight loop an earlier life wrote in the blaze probe (`blaze_fight`, a closed loop on the
live frame) kills blazes in the real fortress inside the full task, and that the life
after it does so sooner: 2,293 steps and seven calls to the first kill, then 421 steps,
with the rod and the powder inside the next 40. No life killed an enderman, so the
pearl, the eye and the End remain open.

Three changes to the shared chassis came out of these lives, for every arm (the pins
were re-recorded; lives run before them are not on the same text):

- An item named by a plan entry is brought to hand when the entry RUNS. Every entry was
  compiled against the inventory at the start of the turn, so an earlier entry's
  inventory trip made a later one stale: one life's `pillar_up(item=cobblestone)` built
  its pillar from its last three obsidian, and the note said cobblestone.
- Head under lava is read as lava (`vision.lava_submerged`, the reflex state's
  `in_lava`, the harness note, the `hit` and `lava_ahead` examples). The view from
  inside lava is a flat red that the lava and flame detectors both read as nothing;
  three deaths in the lava sea were reported to the model as a mob's hits.
- `go_to(sneak=true)` walks holding sneak, which does not step off a block edge
  (checked in the engine: `edge_check`). The plain walk sprint-jumps and took three
  lives over the edge of the landing shelf.

None of the three kept a life out of the lava sea by itself: the first life on the fixed code
mined the block it stood on at the landing and fell through. The shared text also gained
the enderman sentence of the endgame probes (an enderman looked in the eye from under
four blocks teleports away).

## License

MIT, see `LICENSE`. `MCU/` is MCU-AgentBeats and MineStudio, `CUA-KiCad/` builds on
cua-lite and cua-bench, `mfm/vista/` is a port of the VISTA release and the log protocol
is PRO-LONG's; each keeps its own license and citation, listed in
`THIRD_PARTY_NOTICES.md`.
