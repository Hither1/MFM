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
  memory/retrieve.py      the [RECALL] block computed from the index
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

Every arm reads a short contract (12 to 18 KB) and acts through raw actions and the same
28 primitive procedures (`procedures.ATOMS`); no arm is given a task-shaped macro (a
tree, a strip mine, a shaft, the portal). The arms that can read files (`logbook`, `mfm`,
`mfm-matched`) have the longer rules under `references/`; `direct` and `vista` cannot,
and have the procedures' full descriptions in the contract instead. The runner's own
guards (the lava stop, the pillar on a hit, the refusal of a repeated plan) are off for
every arm, and each contract says so.

The two MFM arms have the same memory (the log, the episodes with their frames, the
index and its query tool, the carried lives) and differ in the harness around it:

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
model and task, life 2 carrying life 1 and so on. Closed lives, as `total_score`
(milestones), 2026-09-30 to 2026-10-03; a life stopped before its budget is in
parentheses with its last step. The "examples" column says which shipped examples the
chain read: the ones before commit 1d96da8, 1d96da8's, or b98270f's (both described
below).

| task, budget per life | model, effort | examples | life 1 | life 2 | life 3 | life 4 | life 5 |
|---|---|---|---|---|---|---|---|
| Nether portal, 6,000 | gpt-6-astra high | before 1d96da8 | 100 (2/2) | 100 | | | |
| | claude-opus-5-5 high | before 1d96da8 | 100 | 100 | | | |
| | gpt-6.1-sol xhigh | before 1d96da8 | 100 | 100 | | | |
| Diamond, 12,000 | gpt-6-astra high | before 1d96da8 | 90 (9/10) | 90 | 90 | | |
| | claude-opus-5-5 high | before 1d96da8 | 60 (6/10) | 80 (8/10) | | | |
| Diamond, 40,000 | claude-opus-5-5 high | 1d96da8 | 100 (10/10) | | | | |
| | gpt-6.1-sol xhigh | 1d96da8 | (9/10 at 30,400) | | | | |
| Ender Dragon, 36,000-40,000, then 40,000 | gpt-6-astra high | before 1d96da8 | 37.5 (9/24) | 37.5 (9/24) | 41.67 (10/24) | (10/24 at 32,800) | |
| | claude-opus-5-5 high | before 1d96da8 | 54.17 (13/24) | 50 (12/24) | 54.17 (13/24) | 37.5 (9/24) | |
| | claude-opus-5-5 xhigh | before 1d96da8 | 37.5 (9/24) | | | | |
| | gpt-6.1-sol xhigh | before 1d96da8 | 50 (12/24) | (10/24 at 31,300) | | | |
| Ender Dragon, 40,000, then 80,000 | gpt-6-astra high | 1d96da8 | 54.17 (13/24) | (14/24 at 42,900) | | | |
| | claude-opus-5-5 high | 1d96da8; life 5 b98270f | (12/24 at 11,700) | (15/24 at 61,200) | 62.5 (15/24) | 58.33 (14/24) | 58.33 (14/24) |
| | gpt-6.1-sol xhigh | 1d96da8 | 41.67 (10/24) | (13/24 at 30,100) | | | |

Two Opus lives ran on 1d96da8 and the paper's chain budget (80,000 steps) and closed at
62.5 and 58.33; a fifth life on the same chain and b98270f's examples closed at 58.33.
The 14/24 of the astra life stopped at 42,900 includes `netherrack`, which that life
mined from a ruined portal at the surface of the default world: the milestone counts
the item, not the Nether.

The three gpt-6 diamond lives on the 12,000-step budget all banked the iron pickaxe by
step 6,000 and none the diamond: two died in lava at the diamond level (the runner's
lava stop is off for every arm), the third ran out of steps. The lives of the paper's
own runs are on the dataset (`Ced-Collab/MCUData`, `carry-only-era/`).

What the dragon lives died of, and where their steps went, is in the task notes
(`tasks/.../analysis/final_analysis.md`): Opus reaches the diamond pickaxe in 5,600 to
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
what has a name. No chain has run on it.

## License

MIT, see `LICENSE`. `MCU/` is MCU-AgentBeats and MineStudio, `CUA-KiCad/` builds on
cua-lite and cua-bench, `mfm/vista/` is a port of the VISTA release and the log protocol
is PRO-LONG's; each keeps its own license and citation, listed in
`THIRD_PARTY_NOTICES.md`.
