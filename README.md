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
| seed | `--world-seed N` |
| model | `--model gpt-6-astra` (default) \| `gpt-5.6-sol`; `--cli claude --model claude-opus-5` |
| reasoning effort | `--effort high` (default) |
| an earlier life in the same world | `--seed-memory output/<arm>/episode_001/memory` (mfm and mfm-matched, repeatable), `--seed-log <logs.txt>` (logbook) |

Every arm reads a short contract (12 to 18 KB) and acts through raw actions and the same
28 primitive procedures (`procedures.ATOMS`); no arm is given a task-shaped macro (a
tree, a strip mine, a shaft, the portal). The arms that can read files (`logbook`, `mfm`,
`mfm-matched`) have the longer rules under `references/`; `direct` and `vista` cannot,
and have the procedures' full descriptions in the contract instead.

The two MFM arms have the same memory (the log, the episodes with their frames, the
index and its query tool, the carried lives) and differ in the harness around it:

- `mfm` is the arm of the paper's tables. The model writes its own procedures and
  reflexes under `mine/`, has the skill package, and the runner's own guards are off.
- `mfm-matched` has the contract and the runner guards of `logbook`, so that what it
  adds to `logbook` is the memory alone (the `MFM_MEMORY` settings of
  `mcu_worldmodel/arms.py`). It writes no procedures and has no `mine/`. No result of
  the paper was recorded with it.

The result is `logs/<arm>_result.json`; the workspace, with the whole memory of the
life, is `output/<arm>/episode_001/memory/`. The header of `scripts/run-arm.sh`
documents every option and environment variable.

<!-- TODO(authors): the three world seeds of Tables 2 and 4, and the lives carried into
     the Ender Dragon runs. -->

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
differences between the two. No experiment of the paper was re-run for this release.

## License

MIT, see `LICENSE`. `MCU/` is MCU-AgentBeats and MineStudio, `CUA-KiCad/` builds on
cua-lite and cua-bench, `mfm/vista/` is a port of the VISTA release and the log protocol
is PRO-LONG's; each keeps its own license and citation, listed in
`THIRD_PARTY_NOTICES.md`.
