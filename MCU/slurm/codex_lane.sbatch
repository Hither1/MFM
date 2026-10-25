#!/usr/bin/env bash
# The codex twin of abl_lane.sbatch: the arms given, one life each, one after the other
# on this node, on a GPT model through the codex CLI.
#
#   sbatch slurm/codex_lane.sbatch <arm>=<flags> [<arm>=<flags> ...]
#     <flags> is a comma list of purple-agent options, or `full` for none.
#
# Submit from MCU/ of the run worktree with a clean environment. TASK, STEPS, WORLD_SEED,
# PACE and PREFLIGHT_ONLY as in abl_lane.sbatch; MEMORY is the --memory of every arm in the
# lane (default mfm; logbook, vista or direct for the baselines). The model is MODEL (default gpt-6-astra)
# at reasoning effort high, on the account whose auth.json is MCU_CODEX_AUTH
# (scripts/codex-home.sh), through the codex of CODEX_NODE_DIR (its bin/ holds `codex`
# and the `node` that runs it; gpt-6-astra needs 0.153 or newer).
#SBATCH -p shared
#SBATCH -c 12
#SBATCH --mem=96G
#SBATCH -t 2-20:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="

# The simulator: system JDK 8 and xvfb-run; MINESTUDIO_DIR node-local (sqlite and the
# JVM's working directory fail on NFS) with only the engine linked from shared storage.
export JAVA_HOME=/usr MCU_SKIP_ENV_SH=1
export MINESTUDIO_DIR="${TMPDIR:-/tmp}/minestudio-$SLURM_JOB_ID"
mkdir -p "$MINESTUDIO_DIR/runtime" "$MINESTUDIO_DIR/tmp"
[ -e "$MINESTUDIO_DIR/engine" ] || ln -s "${MINESTUDIO_SHARED:?}/engine" "$MINESTUDIO_DIR/engine"

# The model's shell inherits this PATH, and the workspace tools run `python3` from it:
# submit with a python >= 3.8 that has PIL first on PATH (see abl_lane.sbatch).
python3 -c 'import sys, PIL; assert sys.version_info >= (3, 8)' 2>/dev/null || {
    echo "FATAL: python3 on PATH ($(command -v python3), $(python3 -V 2>&1)) is not >= 3.8 with PIL"; exit 1; }
echo "--- python3: $(command -v python3) $(python3 -V 2>&1)"

# The model channel: one codex for every arm of a wave (the CLI version is part of the
# measurement), run once here so a dead install stops the lane now and its version is
# in this log.
export PATH="${CODEX_NODE_DIR:?}/bin:$PATH"
export CODEX_BIN="$CODEX_NODE_DIR/bin/codex"
"$CODEX_BIN" --version >/dev/null 2>&1 || { echo "FATAL: no runnable codex at $CODEX_BIN"; exit 1; }
echo "--- codex: $CODEX_BIN $("$CODEX_BIN" --version 2>&1 | tail -1)"
export MCU_CODEX_AUTH="${MCU_CODEX_AUTH:?}"

# Preflight, before a life starts: memory for the recorder's frames and wall clock for
# every life in the lane (the arithmetic of abl_lane.sbatch).
STEPS="${STEPS:-12000}"; PACE="${PACE:-2500}"; MODEL="${MODEL:-gpt-6-astra}"; MEMORY="${MEMORY:-mfm}"
NEED_MB=$(( STEPS * 691200 / 1048576 + 8192 ))
HAVE_MB="${SLURM_MEM_PER_NODE:-$(( ${SLURM_MEM_PER_CPU:-0} * ${SLURM_CPUS_ON_NODE:-1} ))}"
[ "$HAVE_MB" -ge "$NEED_MB" ] || {
    echo "FATAL: a $STEPS-step life needs $NEED_MB MB and the job has $HAVE_MB MB -- sbatch --mem=$(( NEED_MB / 1024 + 1 ))G or more"; exit 1; }
NEED_MIN=$(( $# * (STEPS * 60 / PACE + 15) ))
LEFT_MIN=$(( (${SLURM_JOB_END_TIME:-0} - $(date +%s)) / 60 ))
[ "$LEFT_MIN" -ge "$NEED_MIN" ] || {
    echo "FATAL: $# life/lives of $STEPS steps need about $NEED_MIN min at $PACE steps/h and the job has $LEFT_MIN min -- a longer sbatch -t, fewer lives, or PACE=<measured steps/h>"; exit 1; }
echo "--- preflight: --memory $MEMORY, $MODEL effort high, $# x $STEPS steps, memory $NEED_MB of $HAVE_MB MB, wall $NEED_MIN of $LEFT_MIN min"

# One request to MODEL through the CLI and the account the lives will use, in a home of
# its own (codex-home.sh) that is removed again. A CLI too old for the model, or a login
# that no longer answers, fails every turn and the life steps on as no-ops, so the lane
# stops here unless the answer comes back.
probe() {(
    eval "$(scripts/codex-home.sh "preflight-$SLURM_JOB_ID")" || exit 1
    trap 'rm -rf "$CODEX_RUNTIME_HOME"' EXIT
    cd "$MINESTUDIO_DIR/tmp" && CODEX_HOME="$CODEX_RUNTIME_HOME" timeout 300 "$CODEX_BIN" exec \
        --skip-git-repo-check -s read-only -m "$MODEL" -c model_reasoning_effort=high \
        -o "$MINESTUDIO_DIR/tmp/probe.txt" "Reply with the single word ok." > "$MINESTUDIO_DIR/tmp/probe.log" 2>&1
    cat "$MINESTUDIO_DIR/tmp/probe.txt" 2>/dev/null
)}
PROBE="$(probe | tr -d '[:space:]' | tr 'A-Z' 'a-z')"
case "$PROBE" in
    ok*) echo "--- model probe: ok ($MODEL answered)";;
    *) echo "FATAL: $MODEL did not answer through $CODEX_BIN -- $(tail -5 "$MINESTUDIO_DIR/tmp/probe.log" 2>/dev/null)"; exit 1;;
esac
[ "${PREFLIGHT_ONLY:-0}" = 1 ] && { echo "preflight only: nothing run"; exit 0; }

# Code provenance, once per lane: the commit and the uncommitted changes on top of it.
mkdir -p logs
git -C .. rev-parse HEAD > "logs/lane-$SLURM_JOB_ID.commit"
git -C .. diff HEAD > "logs/lane-$SLURM_JOB_ID.patch"

# The codex thread store (the rollouts: every tool call, view_image included) lives on
# this node's /var/tmp (scripts/codex-home.sh) and is lost with it: keep a copy.
keep_rollouts() {
    local sess="${MCU_CODEX_ROOT:-/var/tmp/mcu-codex-$(id -un)}/$1/sessions"
    if [ -d "$sess" ]; then
        mkdir -p "output/$1/codex_sessions" && cp -a "$sess/." "output/$1/codex_sessions/" \
            && echo "--- $1 rollouts kept: $(find "output/$1/codex_sessions" -name 'rollout*.jsonl' | wc -l)"
    fi
}

# The usage-limit guard. A codex account past its limit refuses every turn ("You've hit
# your usage limit" in the turn's events), and the life plays on as no-ops; the MCU
# harness only records the refusal in codex_turns/*.events.jsonl. On the first such turn
# this keeps the arm's rollouts and cancels the job. It only ever stops the job;
# QUOTA_GUARD=0 turns it off.
if [ "${QUOTA_GUARD:-1}" = 1 ]; then
    (
        while sleep 60; do
            for spec in "$@"; do
                arm="${spec%%=*}"
                last=$(ls -t "output/$arm/episode_001/codex_turns/"*.events.jsonl 2>/dev/null | head -1)
                if [ -n "$last" ] && grep -q '"message":"You.ve hit your usage limit' "$last"; then
                    echo "--- usage-limit guard: $arm refused by the account ($(basename "$last")), cancelling $(date -Is)"
                    date -Is > "logs/quota_stop-$SLURM_JOB_ID.txt"
                    keep_rollouts "$arm"
                    scancel "$SLURM_JOB_ID"; exit 0
                fi
            done
        done
    ) &
    GUARD_PID=$!
    trap 'kill "$GUARD_PID" 2>/dev/null' EXIT
    echo "--- usage-limit guard on (pid $GUARD_PID)"
fi

i=0
for spec in "$@"; do
    ARM="${spec%%=*}"; FLAGS="${spec#*=}"
    [ "$FLAGS" = full ] && FLAGS=""
    i=$((i + 1))
    # Ports and display from the job id and the arm's place in the lane.
    export MCU_DISPLAY_NUM=$(( (SLURM_JOB_ID % 10000) * 4 + 200 + i ))
    GREEN=$(( 20000 + (SLURM_JOB_ID % 2000) * 8 + i ))
    PURPLE=$(( GREEN + 4 ))
    echo "--- $ARM flags=[${FLAGS}] display=:$MCU_DISPLAY_NUM ports=$GREEN/$PURPLE $(date -Is)"
    cp "logs/lane-$SLURM_JOB_ID.commit" "logs/${ARM}_code.commit"
    cp "logs/lane-$SLURM_JOB_ID.patch" "logs/${ARM}_code.patch"
    bash scripts/run-arm.sh --arm "$ARM" --memory "$MEMORY" --task "${TASK:-mine_diamond_from_scratch}" \
        --cli codex --model "$MODEL" --effort high \
        --steps "$STEPS" --green-port "$GREEN" --purple-port "$PURPLE" \
        ${WORLD_SEED:+--world-seed "$WORLD_SEED"} \
        -- ${FLAGS//,/ }
    echo "--- $ARM exit=$? $(date -Is)"
    keep_rollouts "$ARM"
done
echo "finished=$(date -Is)"
