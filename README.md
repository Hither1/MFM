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

The `mfm` arm was run on this code (commit d186ac7) on the tasks' default worlds, one
chain of lives per model and task, life 2 carrying life 1 and so on. Closed lives, as
`total_score` (milestones), on 2026-10-01:

| task, budget per life | model, effort | life 1 | life 2 | life 3 |
|---|---|---|---|---|
| Nether portal, 6,000 | gpt-6-astra high | 100 (2/2) | 100 | |
| | claude-opus-5-5 high | 100 | 100 | |
| | gpt-6.1-sol xhigh | 100 | 100 | |
| Diamond, 12,000 | gpt-6-astra high | 90 (9/10) | 90 | 90 |
| | claude-opus-5-5 high | 60 (6/10) | 80 (8/10) | |
| Ender Dragon, 36,000 | gpt-6-astra high | 37.5 (9/24) | | |
| | claude-opus-5-5 high | 54.17 (13/24) | 50 (12/24) | |

The three gpt-6 diamond lives all banked the iron pickaxe by step 6,000 and none the
diamond: two died in lava at the diamond level (the runner's lava stop is off for every
arm), the third ran out of steps. The dragon chains, on 40,000-step lives from life 3
on, and further Opus and gpt-6.1-sol chains were still running when this was written;
the lives of the paper's own runs are on the dataset (`Ced-Collab/MCUData`,
`carry-only-era/`).

## License

MIT, see `LICENSE`. `MCU/` is MCU-AgentBeats and MineStudio, `CUA-KiCad/` builds on
cua-lite and cua-bench, `mfm/vista/` is a port of the VISTA release and the log protocol
is PRO-LONG's; each keeps its own license and citation, listed in
`THIRD_PARTY_NOTICES.md`.
