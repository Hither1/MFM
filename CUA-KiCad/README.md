# CUABench-KiCad

This is the KiCad harness of the paper. It runs visual GUI agents on 25 electronic-design
tasks of cua-bench through [cua-lite](https://github.com/cua-lite/cua-lite). Each task is
a KiCad desktop in a container. The agent sees a screenshot and acts with low-level
mouse and keyboard actions. The score is the netlist comparison of cua-bench: the mean
of three exact checks (components, nets, net names).

## Arms

`gym_codex/run_eval.py --agent <arm>` runs one arm over the tasks.

| `--agent` | Name in the paper | What the model has between steps |
|---|---|---|
| `direct` | Direct | a text list of its earlier actions, sent again at each call |
| `mfm` (default) | MFM | the log, one episode for each action batch with its screenshot, the index and its query tool, a plan queue of more than one batch; the records of the finished tasks under `previous/` with their scores, and its own `notes/` across tasks |

Both arms make the same tool calls (`gym_codex/actions.py`). The `mfm` arm has no
settings. It runs as in the paper (`gym_codex/mfm_agent.py`): before the first action of
each task, one design call at reasoning effort `high` writes `design.md` and
`intent.json`, and the system prompt has a paragraph of schematic conventions. For each
task, the `mfm` arm gets an empty workspace under `<out>/<task>/workspace`. It runs the
tasks in order, one at a time, and keeps what it carries under `<out>/carry`.

## Layout

```
gym_codex/
  run_eval.py          the driver: tasks, order, environment, scoring, summary
  mfm_agent.py         the mfm arm on mfm.agent.base (log, episodes, plan queue)
  mfm_prompts.py       the prompts of the mfm arm
  codex_gui_agent.py   the direct arm
  actions.py           the action contract of both arms
  kicad_rescore.py     scores saved projects again, offline
  kicad_task_orders.py summarizes one arm across task-order seeds
  patch_kicad_tasks.py the task fix (below)
model_channel/         the model channel and its sandbox
  codex_sandbox.sh, claude_sandbox.sh, sandbox_proxy.py
scripts/
  run_kicad_arm.sh     one run of one arm, with what a node needs
  podman-docker-shim   `docker` on rootless podman, for cua-lite
```

## Run

For the setup, the accounts and the commands, see the [README](../README.md) at the top
of the repository. In short:

```bash
export WORK=/path/to/kicad-work
scripts/run_kicad_arm.sh mfm gpt-6-astra high $WORK/runs/mfm_s0 --task-order-seed 0
```

If a run stops, the same command continues it. The score of the run is `mean_reward` in
`<out>/summary.json`. Each task directory keeps the saved project and the graded netlist.

## Two fixes to the benchmark

Both fixes apply to both arms.

- **The project directory.** The grader reads only `/home/cua/kicad_project`. The tasks
  that start a design from nothing do not have this directory and do not name it. Thus
  a correct schematic saved in a different directory scores 0. On a KiCad task, the
  driver makes the directory and adds its location to the instruction
  (`run_eval.py` `_apply_kicad_project_hint`).
- **Task 34877be3** asks for an `LN271` LED. The reference netlist and the KiCad library
  have `LD271`. `gym_codex/patch_kicad_tasks.py` corrects the task text in the dataset
  cache.

## The sandbox

The `mfm` arm gives the model a shell in its workspace. Thus what the shell can reach is
part of the protocol. `model_channel/codex_sandbox.sh` runs each model call in an
unprivileged mount and network namespace (bubblewrap):

| Property | How |
|---|---|
| Only the workspace is reachable | the mount namespace binds the workspace, the system directories and the toolchain read-only, and nothing else of the run: not the output directory of the driver, not the workspace of a different task |
| No network except the model API | `--unshare-net` and an allowlist CONNECT proxy on a unix socket (`sandbox_proxy.py`) |
| The commands of the model are confined | the inner sandbox of the CLI, `workspace-write` |
| A declared tool surface | web search, account connectors and sub-agents are off for each call (`mfm/backend/codex_turn.py` `SAFE_CODEX_FLAGS`) |
| No account state in reach | one CLI home for each task; the credential is bound into it read-only |

`claude_sandbox.sh` does the same for Claude Code. The direct arm has no shell and runs
the CLI without the sandbox.
