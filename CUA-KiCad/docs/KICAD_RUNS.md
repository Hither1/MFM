# Running the KiCad arms

One run is one arm over the 25 tasks, one task at a time. The recorded runs used the
Codex CLI 0.153.4, cua-lite at commit `65a61c4` and the project-directory hint.

## Requirements

- On the node: podman, slirp4netns, bubblewrap (`bwrap`), Python 3.12, Node.js.
- A model account: a ChatGPT account logged in to codex, or an OpenRouter key, for the
  GPT models; a Claude subscription through Claude Code, or an OpenRouter key, for
  Claude Opus 5.
- About 15 GB of disk for the desktop image and the task cache.

## 1. One-time setup

```bash
export WORK=/path/to/kicad-work
mkdir -p $WORK/shim $WORK/runs && cd $WORK

git clone <this repository> MFM

# cua-lite (environment and grader)
git clone https://github.com/cua-lite/cua-lite.git && git -C cua-lite checkout 65a61c4
cd cua-lite && python3.12 -m venv .venv && .venv/bin/pip install -e . \
  && .venv/bin/pip install cua-bench==0.2.11 cua-computer==0.5.19 cua-core==0.3.1 \
                           cua-sandbox==0.1.17 cua-auto==0.1.2 pillow && cd ..

# The Codex CLI in its own node directory
npm install -g --prefix $WORK/codex-node-0.153 @openai/codex@0.153.4
cp "$(command -v node)" $WORK/codex-node-0.153/bin/

# Claude Code, for the Claude runs; must be on PATH
npm install -g @anthropic-ai/claude-code

# cua-lite drives containers through a `docker` CLI; this shim maps it onto rootless podman
cp MFM/CUA-KiCad/scripts/podman-docker-shim $WORK/shim/docker && chmod +x $WORK/shim/docker

# The desktop image (7.6 GB)
podman pull docker.io/trycua/cua-xfce:latest

# Checks
command -v podman slirp4netns bwrap
PYTHONPATH=$WORK/MFM:$WORK/MFM/CUA-KiCad cua-lite/.venv/bin/python -c "import gym_codex.run_eval; print('ok')"
```

Credentials, one of:

```bash
# A ChatGPT account, logged in to a dedicated codex home
mkdir -p $WORK/codex-eval-home
CODEX_HOME=$WORK/codex-eval-home $WORK/codex-node-0.153/bin/codex login

# A Claude subscription: a long-lived token. Use a token, not a login file: the runs
# never refresh it, so a long run cannot revoke your own session.
claude setup-token
export CLAUDE_CODE_OAUTH_TOKEN=...

# OpenRouter
export OPENROUTER_API_KEY=sk-or-...
```

## 2. One task as a smoke test, then the task fix

```bash
cd $WORK
R=$WORK/MFM/CUA-KiCad/scripts/run_kicad_arm.sh
$R mfm-carry gpt-6-astra low $WORK/runs/smoke_mfm --tasks 154d0750
PROVIDER=claude $R mfm-carry claude-opus-5 low $WORK/runs/smoke_mfm_opus --tasks 154d0750
```

A smoke passes when `runs/smoke_*/summary.json` exists with `n_errors` 0 and the task
took more than a couple of steps. If every step is empty the model is not being
reached: look for 401 or 403 errors in the output.

After the first smoke has downloaded the tasks, apply the task fix once (34877be3 asks
for an `LN271` LED; the reference netlist and KiCad's library have `LD271`):

```bash
CUA_BENCH_KICAD_CACHE=$WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad \
  cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/patch_kicad_tasks.py
grep -c LD271 $WORK/cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad/34877be3/main.py   # must be > 0
```

## 3. A full run

```
[PROVIDER=openrouter|claude] run_kicad_arm.sh AGENT MODEL EFFORT OUT_DIR [run_eval options]
```

The arms of one model over three task orders, for example:

```bash
for seed in 0 1 2; do
  $R direct          gpt-6-astra low $WORK/runs/direct_gpt6_s$seed  --task-order-seed $seed
  $R prolong-logonly gpt-6-astra low $WORK/runs/prolong_gpt6_s$seed --task-order-seed $seed
  $R vista           gpt-6-astra low $WORK/runs/vista_gpt6_s$seed   --task-order-seed $seed
  $R mfm             gpt-6-astra low $WORK/runs/mfm_gpt6_s$seed     --task-order-seed $seed
  $R mfm-carry       gpt-6-astra low $WORK/runs/mfmc_gpt6_s$seed    --task-order-seed $seed
done
```

- **Effort.** The third argument is the reasoning effort of the action turns; the
  design call of the MFM arms runs at `high` whatever it is.
- `PROVIDER` unset: the ChatGPT account under `$WORK/codex-eval-home`.
  `PROVIDER=openrouter`: codex against OpenRouter (model ids as OpenRouter names them,
  for example `anthropic/claude-opus-5`). `PROVIDER=claude`: Claude Code on a
  subscription.
- **The seed is the task order.** `--task-order-seed N` shuffles the tasks with
  `random.Random(N)`: the same seed gives the same order on any machine, a resumed run
  continues its sequence and refuses a different seed. The order is written to
  `<out>/task_order.json`. Without the option the tasks run in sorted-id order.
- **One run per node, and never raise `--concurrency`.** KiCad's per-task install fails
  under concurrent load, and `mfm-carry` depends on the order.
- **Resuming.** The same command skips the finished tasks. `mfm-carry` carries memory
  across tasks: keep its output directory intact.
- **Batch jobs.** 12 cores and 32 GB per run; the recorded GPT-6-Astra runs took 5 to
  9 hours each.
- **Usage limits.** Runs that share one subscription share its limit. A step that hit it
  fails and is counted as `quota_hits` in the task's audit; re-run those tasks.

## 4. Reading the results

Each run's score is `mean_reward` in `<out>/summary.json`. Every task directory keeps
the saved project and the graded netlist, so a run can be re-scored offline:

```bash
cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/kicad_rescore.py --run-dir $WORK/runs/mfmc_gpt6_s0
```

One arm across its seeds (mean reward per run, per task across orders, reward and steps
by position in the order):

```bash
cua-lite/.venv/bin/python MFM/CUA-KiCad/gym_codex/kicad_task_orders.py $WORK/runs/mfmc_gpt6_s*
```
