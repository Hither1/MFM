# CUABench-KiCad

The KiCad harness of the paper: visual GUI agents on 25 electronic-design tasks of
cua-bench, run through [cua-lite](https://github.com/cua-lite/cua-lite). Each task is a
desktop with KiCad in a container; the agent sees a screenshot and acts with low-level
mouse and keyboard actions; the score is cua-bench's own netlist comparison (the mean of
three exact checks: components, nets, net names).

## Arms

`gym_codex/run_eval.py --agent ...` runs one arm over the tasks.

| `--agent` | the paper's name | what the model has between steps |
|---|---|---|
| `direct` | Direct | a text list of its prior actions, resent each call |
| `prolong-logonly` | PRO-LONG | an append-only `logs.txt` and the screenshots it names; whatever else the model writes in its workspace is taken back every turn |
| `vista` | VISTA | one long thread calling `play`; the screenshot archive behind `inspect`; `GUIDE.md` / `WORKING.md` |
| `mfm` | MFM (no cross-task memory) | the log, one episode per action batch with its screenshot, the index and its query tool, a multi-batch plan queue |
| `mfm-carry` | MFM | the same, with the finished tasks' records under `previous/`, its own `notes/` kept across tasks, and the finished tasks' scores |

Every arm emits the same tool calls (`gym_codex/actions.py`). The settings of the two
MFM arms are `gym_codex/memory_agents.py` `ARMS`. A memory arm's workspace is created
empty for each task under `<out>/<task>/workspace`; `mfm-carry` runs the tasks in order
at concurrency 1 and keeps what it carries under `<out>/carry`.

## Layout

```
gym_codex/
  run_eval.py          the driver: tasks, order, environment, scoring, summary
  memory_agents.py     the memory arms and their settings
  prolong_agent.py     the log arm and the MFM arms (on mfm.agent.base)
  vista_agent.py       the VISTA arm (on mfm.vista)
  codex_gui_agent.py   the direct arm
  prompts_prolong.py, mfm_prompts.py   the contracts and the turn prompts
  actions.py           the action contract shared by all arms
  kicad_rescore.py     re-score saved projects offline
  kicad_task_orders.py summarise one arm across task-order seeds
  patch_kicad_tasks.py the one task fix (below)
prolong_search/        the model channel and its sandbox
  codex_sandbox.sh, claude_sandbox.sh, sandbox_proxy.py
scripts/
  run_kicad_arm.sh     one run of one arm, with what a node needs
  podman-docker-shim   `docker` on rootless podman, for cua-lite
```

## Running

Setup, accounts and the commands: [`docs/KICAD_RUNS.md`](docs/KICAD_RUNS.md). In short:

```bash
export WORK=/path/to/kicad-work
scripts/run_kicad_arm.sh mfm-carry gpt-6-astra low $WORK/runs/mfm_gpt6_s0 --task-order-seed 0
```

The run resumes where it stopped when the same command is given again. Its score is
`mean_reward` in `<out>/summary.json`; every task directory keeps the saved project and
the graded netlist.

## Two fixes to the benchmark

Both apply to every arm.

- **The project directory** (`--kicad-project-hint`, always passed by
  `run_kicad_arm.sh`). The grader reads `/home/cua/kicad_project` only. The
  design-from-scratch tasks start without that directory and never name it, so a
  correct schematic saved anywhere else scores 0. The driver creates the directory and
  appends its location to the instruction.
- **Task 34877be3** asks for an `LN271` LED; the reference netlist and KiCad's library
  have `LD271`. `gym_codex/patch_kicad_tasks.py` corrects the task text in the dataset
  cache.

## The sandbox

The memory arms give the model a shell in its workspace, so what the shell can reach is
part of the protocol. `prolong_search/codex_sandbox.sh` runs each model call in an
unprivileged mount and network namespace (bubblewrap):

| property | how |
|---|---|
| only the workspace is reachable | the mount namespace binds the workspace, the system directories and the toolchain read-only, and nothing else of the run: not the driver's output directory, not another task's workspace |
| no network but the model API | `--unshare-net` and an allowlisting CONNECT proxy on a unix socket (`sandbox_proxy.py`) |
| the model's own commands are confined | the CLI's inner sandbox, `workspace-write` |
| a declared tool surface | web search, account connectors and sub-agents are switched off on every call (`mfm/backend/codex_turn.py` `SAFE_CODEX_FLAGS`) |
| no account state in reach | one CLI home per task; the credential is bound into it read-only |

`claude_sandbox.sh` is the same for Claude Code. The direct arm has no shell and runs
the CLI bare.
