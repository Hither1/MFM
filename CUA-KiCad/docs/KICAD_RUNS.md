# Running KiCad cells on another cluster

These steps fill the empty cells of the KiCad results table in the [README](../README.md):
**VISTA × gpt-5.6-sol** and the four **Opus 5** cells (direct, ProLong, VISTA, MFM). They
reproduce the setup the gpt-6 column ran in: MFM branch `kicad-results-0913` (which pins this
repo), codex CLI 0.153.4, `--kicad-project-hint`, one task at a time, all 25 tasks.

## Before you start

- **Repo access.** `Hither1/MFM` and `Hither1/CUA-KiCad` are private.
- **Accounts.** gpt-5.6-sol is not on OpenRouter: it needs a ChatGPT account logged in to
  codex. Opus 5 has two routes:
  - **direct, ProLong, MFM:** a Claude subscription (Pro/Max) through the Claude Code CLI
    (`PROVIDER=claude`, `run_eval.py --cli claude`).
  - **VISTA:** OpenRouter with your own key (`PROVIDER=openrouter`). VISTA is built on the codex
    app-server, which Claude Code has no counterpart for.

  A Claude Code score is "Opus 5 via the Claude Code harness", so compare the Opus column
  within itself. Subscription usage limits apply: when one is hit, the affected steps fail
  (`quota_hits` in each task's audit) and the tasks should be re-run.
- **Opus has not run on KiCad before.** The route works for VISTA on the Minecraft benchmark,
  but every arm here gets a one-task smoke test before its full run.
- **On the node:** podman, slirp4netns, bwrap (bubblewrap), Python 3.12, Node.js, and the
  Claude Code CLI for the Opus runs on a subscription.

## 1. One-time setup

```bash
export WORK=/path/to/kicad-work          # needs ~15 GB
mkdir -p $WORK/shim $WORK/runs && cd $WORK

# Code: the MFM branch pins the KiCad harness (this repo, as the CUA-KiCad submodule)
git clone -b kicad-results-0913 git@github.com:Hither1/MFM.git
git -C MFM submodule update --init CUA-KiCad          # the MCU submodule is not needed

# cua-lite (environment + grader)
git clone https://github.com/cua-lite/cua-lite.git && git -C cua-lite checkout 65a61c4
cd cua-lite && python3.12 -m venv .venv && .venv/bin/pip install -e . \
  && .venv/bin/pip install cua-bench==0.2.11 cua-computer==0.5.19 cua-core==0.3.1 \
                           cua-sandbox==0.1.17 cua-auto==0.1.2 pillow && cd ..

# codex CLI 0.153.4 in its own node dir (older CLIs refuse newer models)
npm install -g --prefix $WORK/codex-node-0.153 @openai/codex@0.153.4
cp "$(command -v node)" $WORK/codex-node-0.153/bin/

# Claude Code CLI (Opus direct/ProLong/MFM on a subscription); must be on PATH for the runs
npm install -g @anthropic-ai/claude-code

# cua-lite drives containers through a `docker` CLI; this shim maps it onto rootless podman
cp MFM/CUA-KiCad/scripts/podman-docker-shim $WORK/shim/docker && chmod +x $WORK/shim/docker

# The desktop image (7.6 GB)
podman pull docker.io/trycua/cua-xfce:latest

# Checks
command -v podman slirp4netns bwrap
PYTHONPATH=$WORK/MFM:$WORK/MFM/CUA-KiCad cua-lite/.venv/bin/python -c "import gym_codex.run_eval; print('ok')"
```

Credentials:

```bash
# gpt-5.6-sol (the VISTA run): a ChatGPT account, logged in to a dedicated codex home
mkdir -p $WORK/codex-eval-home
CODEX_HOME=$WORK/codex-eval-home $WORK/codex-node-0.153/bin/codex login

# Opus direct / ProLong / MFM: a long-lived token from your Claude subscription. Use a token,
# not a login file: the runs never refresh it, so a long run cannot revoke your own session.
claude setup-token                       # prints the token; keep it out of shell history
export CLAUDE_CODE_OAUTH_TOKEN=...

# Opus VISTA
export OPENROUTER_API_KEY=sk-or-...
```

## 2. Smoke-test each arm on one task, then patch the dataset

```bash
cd $WORK
R=$WORK/MFM/CUA-KiCad/scripts/run_kicad_arm.sh
$R vista gpt-5.6-sol low $WORK/runs/smoke_vista_gpt56 --tasks 154d0750
PROVIDER=claude     $R direct          claude-opus-5           low $WORK/runs/smoke_direct_opus  --tasks 154d0750
PROVIDER=claude     $R prolong-logonly claude-opus-5           low $WORK/runs/smoke_prolong_opus --tasks 154d0750
PROVIDER=openrouter $R vista           anthropic/claude-opus-5 low $WORK/runs/smoke_vista_opus   --tasks 154d0750
PROVIDER=claude     $R mfm-carry       claude-opus-5           low $WORK/runs/smoke_mfm_opus     --tasks 154d0750 \
    --carry-outcomes --design-turn --design-effort high --conventions
```

A smoke passes when `runs/smoke_*/summary.json` exists with `n_errors` 0 and the task took more
than a couple of steps. If every step is empty, the model is not being reached: look for 401 or
403 errors in the output.

After the first smoke has downloaded the tasks, apply the task fix once (34877be3 asks for an
"LN271" LED; the reference netlist and KiCad's library have `LD271`):

```bash
CUA_BENCH_KICAD_CACHE=$WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad \
  cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/patch_kicad_tasks.py
grep -c LD271 $WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad/34877be3/main.py   # must be > 0
```

## 3. The five full runs

All 25 tasks, one node each; the five can run in parallel.

```bash
$R vista gpt-5.6-sol low $WORK/runs/kicad_vista_gpt56hint
PROVIDER=claude     $R direct          claude-opus-5           low $WORK/runs/kicad_direct_opus5hint
PROVIDER=claude     $R prolong-logonly claude-opus-5           low $WORK/runs/kicad_pllogonly_opus5hint
PROVIDER=openrouter $R vista           anthropic/claude-opus-5 low $WORK/runs/kicad_vista_opus5hint
PROVIDER=claude     $R mfm-carry       claude-opus-5           low $WORK/runs/kicad_mfm_opus5hint \
    --carry-outcomes --design-turn --design-effort high --conventions
```

- **Batch jobs:** wrap each line in a Slurm job with `-c 12 --mem=32G -t 3-00:00:00`. The gpt-6
  arms took 5-9 h each; Opus is untested, so allow the full 3 days.
- **One subscription, three runs:** the three `PROVIDER=claude` runs share one account's usage
  limit. If `quota_hits` shows up in the task audits, run them one after another instead.
- **One run per node, and never raise `--concurrency`:** KiCad's per-task install fails under
  concurrent load.
- **Resuming:** re-running the same command skips finished tasks. The MFM run carries memory
  across tasks, so keep its output directory intact.
- **Do not pass `--exclude-tasks`:** the table counts all 25 tasks.
- **Effort:** `low` matches every memory arm already in the table. The gpt-5.6 direct cell ran
  at `high`; change the third argument if you are told to match that instead. The design turn
  stays at `high` either way.

### Task-order ablation (carry arms)

Every run above takes the tasks in the registry's sorted-id order, so for a carry arm
the memory at task k is one fixed prefix. `--task-order-seed N` shuffles the selected
tasks with `random.Random(N)` (same seed, same order, on any machine; a resumed job
continues the same sequence and refuses a different seed). The order is written to
`<out>/task_order.json` and each `results.jsonl` row carries `order_index`. Run the
same arm under several seeds into separate `--out` dirs, then compare the spread across
orders with the spread across same-order reruns:

    python gym_codex/kicad_order_ablation.py runs/cua_bench_codex/kicad_mfmcarry3design_gpt6hint \
        runs/cua_bench_codex/kicad_mfmcarry3design_gpt6hint_order*

(per-run mean, per-task reward across orders, reward and steps by position third). The
no-carry arms do not depend on the order beyond model noise; a shuffled `--agent mfm`
run is the control for that.

## 4. Send back

```bash
tar czf kicad_runs.tgz -C $WORK/runs kicad_vista_gpt56hint kicad_direct_opus5hint \
    kicad_pllogonly_opus5hint kicad_vista_opus5hint kicad_mfm_opus5hint
```

Each run's score is `mean_reward` in its `summary.json`. Every task directory also keeps the
saved project and the graded netlist, so the runs can be re-scored offline with
`gym_codex/kicad_rescore.py`.
