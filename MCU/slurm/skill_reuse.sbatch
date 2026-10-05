#!/usr/bin/env bash
# The skill-reuse experiment, one life after another on this node:
#
#   1. the source life: mine_diamond_from_scratch in its own world (seed 0), full MFM,
#      with scripts/mine_history.py recording what `mine/` held at each step;
#   2. its memory cut at each checkpoint (scripts/memory_at.py);
#   3. the probes: every new task (cook_meat, coal_torches, iron_shield; world seed 1)
#      once from nothing and once from each cut, carried with --carried-world other.
#
#   sbatch slurm/skill_reuse.sbatch
#
# Submit from MCU/ of the run worktree with a clean environment (no CLAUDE* of the
# submitting session) and a python >= 3.8 with PIL first on PATH: the model's shell
# inherits PATH and the workspace tools run `python3` from it. A life whose
# logs/<arm>_result.json exists is not run again, so the job can be resubmitted.
#
#   TAG          prefix of every arm name (default sr)
#   CHECKPOINTS  steps of the source life to cut at (default "4000 8000 12000")
#   TASKS        the probe tasks (default "cook_meat coal_torches iron_shield")
#   REP          a replicate label; with REP=2 the probes are <TAG>_r2_<task>_t<step>
#                and the source life and its cuts are the ones already made
#   SOURCE_STEPS / PROBE_STEPS  budgets (default 12000 / 6000)
#   STOP_AFTER   steps a probe plays on after its last milestone (default 400)
#   MODEL        default claude-opus-5 (effort high)
#SBATCH -p shared
#SBATCH -c 12
#SBATCH --mem=48G
#SBATCH -t 2-12:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="

TAG="${TAG:-sr}"
CHECKPOINTS="${CHECKPOINTS:-4000 8000 12000}"
TASKS="${TASKS:-cook_meat coal_torches iron_shield}"
REP="${REP:-}"
SOURCE_STEPS="${SOURCE_STEPS:-12000}"
PROBE_STEPS="${PROBE_STEPS:-6000}"
STOP_AFTER="${STOP_AFTER:-400}"
MODEL="${MODEL:-claude-opus-5}"

# The simulator: system JDK 8 and xvfb-run; MINESTUDIO_DIR node-local (sqlite and the
# JVM's working directory fail on NFS) with only the engine linked from shared storage.
export JAVA_HOME=/usr MCU_SKIP_ENV_SH=1
export MINESTUDIO_DIR="${TMPDIR:-/tmp}/minestudio-$SLURM_JOB_ID"
mkdir -p "$MINESTUDIO_DIR/runtime" "$MINESTUDIO_DIR/tmp"
[ -e "$MINESTUDIO_DIR/engine" ] || ln -s "${MINESTUDIO_SHARED:?}/engine" "$MINESTUDIO_DIR/engine"

python3 -c 'import sys, PIL; assert sys.version_info >= (3, 8)' 2>/dev/null || {
    echo "FATAL: python3 on PATH ($(command -v python3), $(python3 -V 2>&1)) is not >= 3.8 with PIL"; exit 1; }
echo "--- python3: $(command -v python3) $(python3 -V 2>&1)"

# The model channel: Claude Code on the account in MCU_CLAUDE_EVAL_DIR (claude-home.sh).
export MCU_CLAUDE_BIN="${MCU_CLAUDE_BIN:?}"
export MCU_CLAUDE_EVAL_DIR="${MCU_CLAUDE_EVAL_DIR:?}"

# Code provenance, once per job: the commit and the uncommitted changes on top of it.
mkdir -p logs
git -C .. rev-parse HEAD > "logs/skill_reuse-$SLURM_JOB_ID.commit"
git -C .. diff HEAD > "logs/skill_reuse-$SLURM_JOB_ID.patch"

N=0
# life <arm> <task> <steps> [run-arm.sh options...]: one life, skipped when it has a result.
life() {
    local arm="$1" task="$2" steps="$3"; shift 3
    N=$((N + 1))
    if [ -s "logs/${arm}_result.json" ]; then
        echo "--- $arm: has a result, not run again"; return 0
    fi
    # Ports and display from the job id and the life's place in the job.
    export MCU_DISPLAY_NUM=$(( (SLURM_JOB_ID % 10000) * 4 + 300 + (N % 4) ))
    local green=$(( 20000 + (SLURM_JOB_ID % 1400) * 32 + 2 * N ))
    echo "--- $arm task=$task steps=$steps display=:$MCU_DISPLAY_NUM ports=$green/$((green + 1)) $(date -Is)"
    cp "logs/skill_reuse-$SLURM_JOB_ID.commit" "logs/${arm}_code.commit"
    cp "logs/skill_reuse-$SLURM_JOB_ID.patch" "logs/${arm}_code.patch"
    bash scripts/run-arm.sh --arm "$arm" --memory mfm --task "$task" --steps "$steps" \
        --cli claude --model "$MODEL" --effort high --overwrite \
        --green-port "$green" --purple-port "$((green + 1))" "$@"
    echo "--- $arm exit=$? $(date -Is)"
}

# 1. The source life, with the history of its mine/ recorded from the first step.
SRC="${TAG}_src_diamond"
SRC_MEM="output/$SRC/episode_001/memory"
HIST="logs/${SRC}_mine_history"
if [ ! -s "logs/${SRC}_result.json" ]; then
    rm -rf "$HIST"
    python3 scripts/mine_history.py watch "$SRC_MEM" "$HIST" --every 15 --idle 1000000 &
    WATCH=$!
    life "$SRC" mine_diamond_from_scratch "$SOURCE_STEPS"
    sleep 45; kill "$WATCH" 2>/dev/null; wait "$WATCH" 2>/dev/null
else
    life "$SRC" mine_diamond_from_scratch "$SOURCE_STEPS"
fi
[ -s "logs/${SRC}_result.json" ] && [ -s "$HIST/history.jsonl" ] || {
    echo "FATAL: the source life has no result or no mine history"; exit 1; }

# 2. Its memory at each checkpoint.
for T in $CHECKPOINTS; do
    CUT="output/${TAG}_mem/t$(printf %05d "$T")"
    [ -d "$CUT" ] || python3 scripts/memory_at.py "$SRC_MEM" --step "$T" --out "$CUT" --history "$HIST" \
        > "logs/${TAG}_mem_t$(printf %05d "$T").json" || { echo "FATAL: cut at $T failed"; exit 1; }
done

# 3. The probes. The checkpoint order is rotated from task to task, so no checkpoint
# always runs first or last in the job.
export MCU_STOP_AFTER_COMPLETE="$STOP_AFTER"
POINTS=(0 $CHECKPOINTS)
k=0
for TASK in $TASKS; do
    for j in "${!POINTS[@]}"; do
        T="${POINTS[$(( (j + k) % ${#POINTS[@]} ))]}"
        ARM="${TAG}${REP:+_r$REP}_${TASK}_t$(printf %05d "$T")"
        if [ "$T" -eq 0 ]; then
            life "$ARM" "$TASK" "$PROBE_STEPS"
        else
            life "$ARM" "$TASK" "$PROBE_STEPS" \
                --seed-memory "$PWD/output/${TAG}_mem/t$(printf %05d "$T")" -- --carried-world other
        fi
    done
    k=$((k + 1))
done
echo "finished=$(date -Is)"
