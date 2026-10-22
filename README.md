# MFM: Multimodal Filesystem Memory for Long-Horizon Embodied Agents

[![arXiv](https://img.shields.io/badge/arXiv-2610.22686-b31b1b.svg)](https://arxiv.org/abs/2610.22686)
[![Project Page](https://img.shields.io/badge/Project-Page-327a62.svg)](https://hither1.github.io/MFM-project/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

A long-horizon agent must keep its experience and use it again much later. A complete
history is difficult to search. A summary is easy to search, but it can lose the visual
and spatial details that the agent needs later.

MFM keeps the memory of the agent as a directory of files. The harness records what
occurs: the frames, the states, the actions and their outcomes. An index connects each
record to its time, its place and its contents. The agent searches the index with
programs. When the text is not sufficient, the agent opens the original frames. The
agent writes what it learns as notes, scripts and plans in the same directory, with
references to the records that show them. The next task, or the next life in the same
world, starts with this memory.

This repository contains MFM and the direct baseline (no persistent memory) on two
benchmarks:

- **MCU-AgentBeats** (Minecraft): Mine Diamond from Scratch, Ender Dragon, and the Nether
  portal case study.
- **CUABench-KiCad**: 25 electronic-design tasks in the KiCad desktop application.

Results with GPT-6-Astra (mean of 3 seeds):

<!-- TODO(authors): keep this table equal to the final paper. -->

| Benchmark | Metric | Direct | MFM |
| --- | --- | ---: | ---: |
| Mine Diamond from Scratch | milestones (of 10) | 6.3 | 10.0 |
| Ender Dragon | milestones (of 24) | 6.3 | 16.0 |
| CUABench-KiCad | mean reward | 0.267 | 0.440 |

The Minecraft results of MFM in this table used the `mfm-atoms` arm (see
[Run](#minecraft)). The runs of the paper also had a `[RECALL]` block in the turn
prompt: a summary that the harness computed from the index. This code does not have it.

The code of the other baselines in the paper (PRO-LONG, VISTA) is not in this repository.

## How MFM works

### The workspace

The model works in one directory, the workspace, through a coding-agent CLI (Codex CLI
or Claude Code). In the workspace, the model reads and writes files, runs programs and
views images. The workspace has three parts. Together, they give the five memory
functions of the paper (Section 3.2). The table gives the names in Minecraft:

| Part | Files | Written by | Memory function |
| --- | --- | --- | --- |
| Episodic records | `episodes/ep_<N>/`: the frame at the start of a plan entry, the state, the action and the outcome. `logs.txt`: the append-only log of plans, states and events. | harness | episodic |
| Associative index | `index.jsonl`: one line for each episode, with its steps, position, tags and summary. `grid.jsonl`: the cells that the avatar visited, and the cells with water, lava or damage. | harness | episodic, spatial |
| Agent-written memory | `mine/GUIDE.md` and `mine/notes.md`: facts about the world. `mine/procedures/` and `mine/reflexes/`: scripts. `mine/working.md`: the current plan. | model | semantic, procedural, working |

The harness also writes the task and the rules: `CLAUDE.md` for Claude Code, `AGENTS.md`
for the Codex CLI. It adds reference text and skill files (`references/`, `skills/`)
and two search tools (`tools/`). The model must not change the files of the harness. If
a turn makes the log, the index or the rules shorter, the harness reports a fault.

### One turn

The harness calls the model when the current plan is complete or stopped. A turn has
four parts:

1. **Show.** The harness gives the model the current frame, the state, the new events
   and its working plan.
2. **Search** (Section 3.3). The model can run `tools/episodes.py` to find episodes by
   step, place, action, tag or text. This tool can also make a contact sheet of frames,
   or put a past frame next to the current view. `tools/zoom.py` magnifies a region of
   a frame. The model opens the frames that it needs.
3. **Consolidate** (Section 3.4). The model updates its notes, its guide, its working
   plan and its scripts. A note gives the episodes that show it, so that the model can
   examine the note against its frames later.
4. **Act.** The model writes its next plan to `actions.json`. A plan entry is a raw
   action that the harness holds for some steps, or one of the procedures of the model.
   The harness gives no built-in procedure: the model makes each skill (a walk, a dig,
   a craft) from raw actions. The harness runs the plan and writes one episode for each
   entry. It stops the plan early after an important event, for example a milestone, a
   death or damage. A reflex of the model can also stop the plan.

### Lives and tasks

The memory continues from one life or task to the next:

- **Minecraft.** A new life in the same world gets the workspaces of the earlier lives
  under `previous/life_<i>/`. Its first turn is a workshop turn: the model reads the
  earlier lives and writes its guide before it plays. The harness does not copy the
  old scripts into `mine/`. The model copies the scripts that it wants to keep.
  `previous/scripts.md` gives the calls and the last outcome of each old script.
- **KiCad.** Each task has the same log, episodes, index and tools. Before the first
  action, the model writes a design of the circuit (`design.md`). `previous/` holds the
  records and the scores of the finished tasks. `notes/` keeps the notes of the model
  from task to task.

The `direct` arm has no persistent memory. In Minecraft, each turn is a new model session
that shows only the present, and a plan entry is a raw action or one of 28 built-in
procedures (the atoms, for example `go_to`, `place_at` or `pillar_up`). In KiCad, each
call gets a text list of the earlier actions.

### From the paper to the code

| Paper | Code |
| --- | --- |
| Episodic records (Section 3.2) | `mfm/memory/store.py` (`EpisodeStore`), `MCU/mcu_worldmodel/episodes.py`, `CUA-KiCad/gym_codex/mfm_agent.py` |
| The log | `MCU/mcu_worldmodel/memory.py` (Minecraft), `mfm/memory/log.py` (KiCad) |
| Associative index and spatial memory | `mfm/memory/store.py`, `MCU/mcu_worldmodel/grid.py` |
| Agent-written memory, procedures and reflexes | `MCU/mcu_worldmodel/own.py`, `MCU/mcu_worldmodel/skills.py` |
| Search tools (Section 3.3) | `mfm/memory/tools/episodes.py`, `mfm/memory/tools/zoom.py` |
| Carried memory (Section 3.4) | `MCU/mcu_worldmodel/previous.py` (Minecraft), `mfm/memory/carry.py` and `mfm/memory/consolidate.py` (KiCad) |
| The settings of each arm (Section 4) | `MCU/mcu_worldmodel/arms.py`, `CUA-KiCad/gym_codex/mfm_agent.py` |
| The milestone score | the environment server (`MCU/src/`); `MCU/mcu_worldmodel/milestones.py` keeps the same count for the agent |
| The Nether portal case study (Section 4.4) | the task `nether_portal`, `MCU/mcu_worldmodel/portal.py`, `MCU/scripts/portal_stats.py` |

## Repository layout

```
mfm/                        the method, shared by the two benchmarks
  memory/                     episode store, index, carried memory, search tools
  agent/, backend/            the agent base and the Codex CLI channel
MCU/                        MCU-AgentBeats and the Minecraft harness (see MCU/README.md)
  src/, MCU_benchmark/        the environment server and the task configurations
  mcu_worldmodel/             the harness: arms, contracts, procedures, perception, memory
  scripts/run-arm.sh          the launcher of one life
CUA-KiCad/                  the KiCad harness on cua-lite (see CUA-KiCad/README.md)
  gym_codex/                  the driver, the two arms and the scoring
  model_channel/              the model channel and its sandbox
  scripts/run_kicad_arm.sh    the launcher of one run
scripts/env_setup/          the setup script of the Minecraft environment
```

## Setup

The code runs on Linux x86_64 and does not need a GPU. Each benchmark has its own Python
environment. The launchers put the repository root on `PYTHONPATH`, thus both
environments use the same `mfm/` package. You can set up only the benchmark that you
will use.

Do the steps in this order: first the model access (section 1), then the setup of the
benchmark (section 2 or 3).

| | Minecraft | KiCad |
| --- | --- | --- |
| Python | 3.11 (uv makes the environment) | 3.12 |
| Other software | JDK 8 and Xvfb (the setup script can install them without root) | podman, slirp4netns, bubblewrap, Node.js |
| Disk | approximately 9 GB, and approximately 2 GB for each Ender Dragon life | approximately 15 GB |

### 1. Model access

The two benchmarks call the model through a coding-agent CLI: the Codex CLI for OpenAI
models, or Claude Code for Claude models. This section installs the CLI and gives it a
credential. The other sections do not change the CLI.

The KiCad setup keeps all its parts in one directory. If you will use KiCad, set this
directory first:

```bash
export WORK=/path/to/kicad-work
```

Install the CLI of your model, at the version of the recorded runs:

```bash
# Claude Code, for the two benchmarks
curl -fsSL https://claude.ai/install.sh | bash -s 2.1.284

# Codex CLI, for Minecraft
npm install -g @openai/codex@0.160.0

# Codex CLI, for KiCad: a different version, in its own Node.js directory
npm install -g --prefix $WORK/codex-node-0.153 @openai/codex@0.153.4
cp "$(command -v node)" $WORK/codex-node-0.153/bin/
```

The KiCad sandbox mounts `$WORK/codex-node-0.153` in each model call, thus this
directory must also contain `node`.

Then give the CLI a credential. There are three routes. Each benchmark reads the
credential from a different location:

| Route | Minecraft | KiCad |
| --- | --- | --- |
| ChatGPT account (the default) | `codex login`. It writes `~/.codex/auth.json`. `MCU_CODEX_AUTH` can name a different file. | `mkdir -p $WORK/codex-eval-home`, then `CODEX_HOME=$WORK/codex-eval-home $WORK/codex-node-0.153/bin/codex login` |
| Claude account | `export MCU_CLAUDE_OAUTH_TOKEN=<token>`. Run with `--cli claude`. | `export CLAUDE_CODE_OAUTH_TOKEN=<token>`. Put `PROVIDER=claude` before the command. |
| OpenRouter key | `export MCU_OPENROUTER_ENV=<file>`. The file has the line `OPENROUTER_API_KEY=<key>`. Run with `--route openrouter`. | `export OPENROUTER_API_KEY=<key>`. Put `PROVIDER=openrouter` before the command. |

`claude setup-token` gives the Claude token. Use this long-lived token, not a login
file. A run does not refresh the token, thus a long run cannot stop the session of your
own login.

The Minecraft launcher uses `codex` and `claude` from `PATH`. To use a different binary,
set `CODEX_BIN` or `MCU_CLAUDE_BIN`. The KiCad launcher uses the Codex CLI in
`$WORK/codex-node-0.153` and `claude` from `PATH`.

### 2. Minecraft (MCU-AgentBeats)

1. Install [uv](https://docs.astral.sh/uv/).
2. Get the code and run the setup script:

   ```bash
   git clone https://github.com/Hither1/MFM.git MFM && cd MFM
   bash scripts/env_setup/minecraft.sh
   ```

   The script does not need root. It does these steps, and it skips each step that is
   already done:

   - It makes `MCU/.venv` from `MCU/uv.lock` (Python 3.11 and MineStudio).
   - It installs JDK 8 in `~/.local/opt/mcu/jdk8` if the host has no JDK 8.
   - It installs Xvfb in `~/.local/opt/mcu/xvfb` if the host has no `xvfb-run`. This
     step uses `apt-get download`. On a host without apt, install Xvfb as root.
   - It downloads the simulator engine (approximately 450 MB) to
     `~/.local/opt/mcu/MineStudio`.

   To use a directory other than `~/.local/opt/mcu`, set `MCU_PREFIX`.
3. Make sure that the simulator loads:

   ```bash
   cd MCU && source env.sh
   xvfb-run -a .venv/bin/python -c 'from minestudio.simulator import MinecraftSim'
   ```

`env.sh` puts JDK 8 and Xvfb on `PATH` and copies the engine to `MINESTUDIO_DIR` (default
`/tmp/MineStudio-$USER`). The launcher sources `env.sh` for each run. `MINESTUDIO_DIR`
must be on a local disk: the simulator keeps a sqlite database there, and sqlite locks
fail on NFS. On NFS, the simulator also stops at start with `NoClassDefFoundError: Could
not initialize class java.nio.file.FileSystems$DefaultFileSystemHolder`.

### 3. KiCad (CUABench-KiCad)

The KiCad launcher finds all parts of the setup in `$WORK` (section 1).

1. Get the code:

   ```bash
   mkdir -p $WORK/shim $WORK/runs && cd $WORK
   git clone https://github.com/Hither1/MFM.git MFM
   ```

2. Install cua-lite (the desktop environment and the grader) at the commit of the
   recorded runs:

   ```bash
   git clone https://github.com/cua-lite/cua-lite.git && git -C cua-lite checkout 65a61c4
   cd cua-lite && python3.12 -m venv .venv && .venv/bin/pip install -e . \
     && .venv/bin/pip install cua-bench==0.2.11 cua-computer==0.5.19 cua-core==0.3.1 \
                              cua-sandbox==0.1.17 cua-auto==0.1.2 pillow && cd ..
   ```

3. Get the tasks. The recorded runs used the cua-bench tasks of
   [trycua/cua](https://github.com/trycua/cua) at commit `49677ceeb`. The later commits (to
   12 October 2026) change only the format of the task files. Copy the tasks into the
   cache of cua-lite:

   ```bash
   git clone --filter=blob:none --no-checkout https://github.com/trycua/cua.git cua-src
   git -C cua-src checkout 49677ceeba38496e2a77f7baa3a5839c5c4cee1b -- libs/cua-bench/datasets
   mkdir -p cua-lite/lite/gym/envs/cua/.cache/datasets
   cp -R cua-src/libs/cua-bench/datasets/. cua-lite/lite/gym/envs/cua/.cache/datasets/
   ```

   Then apply the task fix one time. Task 34877be3 asks for an `LN271` LED, but the
   reference netlist and the KiCad library have `LD271`:

   ```bash
   CUA_BENCH_KICAD_CACHE=$WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad \
     cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/patch_kicad_tasks.py
   grep -c LD271 \
     $WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad/34877be3/main.py
   ```

   The `grep` count must be more than 0.

4. Install the `docker` shim. cua-lite controls the containers through a `docker`
   command, and the shim sends these commands to rootless podman:

   ```bash
   cp MFM/CUA-KiCad/scripts/podman-docker-shim $WORK/shim/docker
   chmod +x $WORK/shim/docker
   ```

5. Download the desktop image (7.6 GB):

   ```bash
   podman pull docker.io/trycua/cua-xfce:latest
   ```

6. Make sure that the tools are available and that the driver loads:

   ```bash
   command -v podman slirp4netns bwrap
   PYTHONPATH=$WORK/MFM:$WORK/MFM/CUA-KiCad \
     cua-lite/.venv/bin/python -c "import gym_codex.run_eval; print('ok')"
   ```

7. Run one task as a smoke test:

   ```bash
   $WORK/MFM/CUA-KiCad/scripts/run_kicad_arm.sh mfm gpt-6-astra high \
       $WORK/runs/smoke_mfm --tasks 154d0750
   ```

   The test passes when `$WORK/runs/smoke_mfm/summary.json` shows `n_errors` 0 and the
   task has more than a few steps. If all steps are empty, the CLI cannot get to the
   model. Look for 401 or 403 errors in the output.

## Run

### Minecraft

One command runs one life of one arm. It starts the environment server, the agent and
the evaluation client, and it stops them when the life ends. Run it from `MCU/`:

```bash
cd MCU
bash scripts/run-arm.sh --arm mfm_diamond --memory mfm \
    --task mine_diamond_from_scratch --green-port 9053 --purple-port 9063
```

- `--memory`: `mfm` (the default arm), `mfm-atoms` or `direct`. `mfm` has no built-in
  procedure: the model makes each skill from raw actions. `mfm-atoms` is MFM with the 28
  atoms of the `direct` arm and with example procedures and reflexes. The runs of the
  paper used this setting.
- `--task`: `mine_diamond_from_scratch` (12,000 steps), `ender_dragon` (36,000 steps) or
  `nether_portal` (6,000 steps). These are the step budgets of the paper. `--steps N`
  sets a different budget.
- `--world-seed N`: the Minecraft world. The default is 0 for the diamond and the dragon,
  and 42 for the portal.
- `--model`, `--effort`: the model and its reasoning effort (default `high`). The route
  options `--cli` and `--route` are in [Model access](#1-model-access).
- `bash scripts/run-arm.sh --help` shows all options and their defaults.

When the life ends, its score is in `logs/<arm>_result.json`. [Outputs](#outputs) gives
all the files of a life.

To run more lives in the same world, start each life after the previous life ends, and
give it the memory of that life. That memory also holds the earlier lives:

```bash
bash scripts/run-arm.sh --arm dragon_l1 --memory mfm --task ender_dragon \
    --green-port 9053 --purple-port 9063
bash scripts/run-arm.sh --arm dragon_l2 --memory mfm --task ender_dragon \
    --green-port 9053 --purple-port 9063 \
    --seed-memory output/dragon_l1/episode_001/memory
```

Runs can be at the same time if their names and ports are different. Give each run its
own X display with `MCU_DISPLAY_NUM`. To stop a run, use
`python3 scripts/stop_arm.py --go <arm>`.

### KiCad

```bash
export WORK=/path/to/kicad-work
$WORK/MFM/CUA-KiCad/scripts/run_kicad_arm.sh mfm gpt-6-astra high \
    $WORK/runs/mfm_s0 --task-order-seed 0
```

The arguments are the arm (`mfm` or `direct`), the model, the reasoning effort and the
output directory. `PROVIDER` before the command selects the route of
[Model access](#1-model-access).

- One run does the 25 tasks, one at a time. The `mfm` arm carries memory from each task
  to the next, thus the order of the tasks is part of the run. `--task-order-seed N`
  sets the order, and `<out>/task_order.json` records it.
- If a run stops, the same command continues it. Keep the output directory, because it
  holds the carried memory.
- Do only one run on a node at a time. The KiCad installation of a task fails under
  concurrent load. Give each run 12 cores and 32 GB. The recorded GPT-6-Astra runs took
  5 to 9 hours each.

When the run ends, its score is in `<out>/summary.json`. [Outputs](#outputs) gives all
the files of a run.

## Outputs

### Minecraft

A life writes its files under `MCU/`. The file names use the `--arm` name of the run:

```
logs/
  <arm>_result.json          the score of the life
  <arm>_purple.log           the log of the agent: the turns, the milestones, the progress
  <arm>_green.log            the log of the environment server
  <arm>_client.log           the log of the evaluation client
  <arm>.toml                 the scenario of the client: the servers, the task, the steps
output/<arm>/episode_001/
  memory/                    the workspace of the life (see "The workspace" above)
  codex_turns/               for each turn: the prompt, the CLI events and the CLI errors
  hires/                     the frame of each step, as the environment sent it (640x360)
  attach/                    the last frames that the harness gave to the model
  worldmodel_report.json     a summary: arm settings, steps, turns, milestones, CLI counts
output/<date>_<time>_<pid>/  the directory of the environment server
  result.txt                 the result as text
  <task>/episode_1.mp4       the video of the life
  <task>/milestone_tracking.json   each verified milestone, with its step
```

- **The score.** `sim_score` in `logs/<arm>_result.json` is the number of milestones that
  the environment verified. `score` is the same number as a percent of the milestones of
  the task. The `avg_*` fields come from the gpt-4o video rating. They are `N/A` when
  `OPENAI_API_KEY` is not set, and they do not change the score.
- **The next life.** `memory/` is the directory that `--seed-memory` gives to the next
  life. The model never sees `hires/`, and the next life does not get it.
- **The direct arm.** A `direct` life keeps no memory, thus its `memory/` has no log,
  episodes, index or tools.
- **The environment server.** The line `Milestone data saved to` in `<arm>_green.log`
  gives the name of its directory.
- **Disk.** One Ender Dragon life writes approximately 1.6 GB under `output/<arm>/`
  (approximately 1.4 GB of it is `hires/`) and approximately 0.2 GB of video.

### KiCad

A run writes all its files under the output directory `<out>`:

```
<out>/
  summary.json             the score of the run (mean_reward), the task counts, the settings
  results.jsonl            one line for each task: reward, steps, error, time
  task_order.json          the order of the tasks and its seed
  carry/                   mfm: the memory that goes from task to task
    manifest.json            the finished tasks in order, with their rewards
    notes/                   the notes of the model
  <task_id>/               one directory for each task
    instruction.txt          the task text that the agent got
    step_<NN>.png            the screenshot at each step
    trajectory.json          the reply and the actions of the model at each step
    codex/                   for each model call: the prompt, the CLI events, the CLI errors
    kicad_project/           the project files that the agent saved on the desktop
    graded.net               the netlist that the grader compared, if the grader made it
    workspace/               mfm: the workspace of the task (log, episodes, index, tools,
                             design.md, notes/, previous/)
```

- **The score.** `mean_reward` in `summary.json` is the mean reward of the tasks. The
  reward of a task is the mean of three exact checks of its netlist: the components, the
  nets and the net names.
- **Errors.** `n_errors` in `summary.json` counts the tasks that stopped with an error. A
  task with an error is not complete: the same command runs it again.
- **Model calls.** The directory `codex/` has this name for the two CLIs. In the `mfm`
  arm, `codex/design/` holds the design call.
- **The direct arm.** A `direct` run has no `carry/` and no `workspace/`.
- **The grader input.** The grader reads a `.net` file from the project. If the project
  has no `.net` file, the grader makes one from the schematic, and the run keeps it as
  `graded.net`.

To score a run again offline, or to compare the task orders of one arm, run these
commands from `$WORK`:

```bash
cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/kicad_rescore.py --run-dir runs/mfm_s0
cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/kicad_task_orders.py runs/mfm_s*
```

## Citation

```bibtex
@article{su2026mfm,
  title   = {Multimodal Filesystem Memory for Long-Horizon Embodied Agents},
  author  = {Su, Chloe and Li, Jiahan and Qi, Zhenting and Cheng, Chaoran and Chen, Haoyu and Jun, Sejoon and Ye, Weirui and Du, Yilun},
  journal = {arXiv preprint arXiv:2610.22686},
  year    = {2026}
}
```

## License

MIT, see [`LICENSE`](LICENSE). Some parts come from other projects.
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) gives the origin and the license of
each part.
