#!/usr/bin/env bash
# One lane of the MFM ablation wave on Claude Opus: the arms given, one life each, one
# after the other on this node (two lanes run at once, on different nodes).
#
#   sbatch slurm/abl_lane.sbatch <arm>=<flags> [<arm>=<flags> ...]
#     <flags> is a comma list of purple-agent options, or `full` for none:
#     abl_opus_diamond_full=full abl_opus_diamond_noimg=--no-history-images
#
# Submit from MCU/ of the run worktree with a clean environment (no CLAUDE* of the
# submitting session): see the wave's launch notes. WORLD_SEED=N plays another world
# than the task's default (run-arm.sh --world-seed); TASK and STEPS as in run-arm.sh.
# The model is MODEL (default claude-opus-5-5) at reasoning effort high.
# The memory below carries a life of up to 100,000 steps (the recorder keeps every frame
# of a life in RAM), and the preflight further down refuses a lane that the job's memory
# or time limit cannot finish. PACE is the steps an hour its estimate assumes (default
# 2500); PREFLIGHT_ONLY=1 runs the checks and exits.
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

# The model's shell inherits this PATH, and the workspace tools run `python3` from it
# (tools/episodes.py is `#!/usr/bin/env python3`); the system python3 here is 3.6, which
# cannot parse them. Submit with a python >= 3.8 that has PIL first on PATH.
python3 -c 'import sys, PIL; assert sys.version_info >= (3, 8)' 2>/dev/null || {
    echo "FATAL: python3 on PATH ($(command -v python3), $(python3 -V 2>&1)) is not >= 3.8 with PIL"; exit 1; }
echo "--- python3: $(command -v python3) $(python3 -V 2>&1)"

# The model channel: Claude Code on the account in MCU_CLAUDE_EVAL_DIR (claude-home.sh).
# Without MCU_CLAUDE_BIN the CLI is the newest install of its own under
# ~/.local/share/claude-code-<version> (npm install -g --prefix; 2.1.288 since
# 2026-10-03, because claude-opus-5-5 needs 2.1.280 or newer), else the newest nvm
# install: the release's own default (~/.local/share/claude-code-npm) does not exist on
# this cluster. It is run once here, so a dead link stops the lane now and the CLI's
# version is in this log.
[ -n "${MCU_CLAUDE_BIN:-}" ] || MCU_CLAUDE_BIN="$(ls -d "$HOME"/.local/share/claude-code-[0-9]*/bin/claude 2>/dev/null | sort -V | tail -1)"
[ -n "${MCU_CLAUDE_BIN:-}" ] || MCU_CLAUDE_BIN="$(ls -d "$HOME"/.nvm/versions/node/*/bin/claude 2>/dev/null | sort -V | tail -1)"
"${MCU_CLAUDE_BIN:-/nonexistent}" --version >/dev/null 2>&1 || {
    echo "FATAL: no runnable claude CLI (MCU_CLAUDE_BIN=${MCU_CLAUDE_BIN:-none found under ~/.local/share or ~/.nvm})"; exit 1; }
export MCU_CLAUDE_BIN
echo "--- claude: $MCU_CLAUDE_BIN $("$MCU_CLAUDE_BIN" --version 2>&1 | head -1)"
export MCU_CLAUDE_EVAL_DIR="${MCU_CLAUDE_EVAL_DIR:?}"

# Preflight, before a life starts. The recorder (minestudio RecordCallback) keeps every
# 640x360 frame of a life in RAM until the life closes: 691,200 bytes a step, and the
# 36,000-step dragon life of job 49635876 peaked at 26.7 GB. A life therefore needs
# steps x 0.66 MiB plus 8 GiB for the rest of the harness, and the lane needs wall clock
# for every life in it. Opus 5 high ran 3,100 to 3,900 steps an hour here; PACE is the
# floor the estimate uses. A lane that cannot finish stops here, not at the OOM killer
# or the time limit hours in.
STEPS="${STEPS:-12000}"; PACE="${PACE:-2500}"; MODEL="${MODEL:-claude-opus-5-5}"
NEED_MB=$(( STEPS * 691200 / 1048576 + 8192 ))
HAVE_MB="${SLURM_MEM_PER_NODE:-$(( ${SLURM_MEM_PER_CPU:-0} * ${SLURM_CPUS_ON_NODE:-1} ))}"
[ "$HAVE_MB" -ge "$NEED_MB" ] || {
    echo "FATAL: a $STEPS-step life needs $NEED_MB MB and the job has $HAVE_MB MB -- sbatch --mem=$(( NEED_MB / 1024 + 1 ))G or more"; exit 1; }
NEED_MIN=$(( $# * (STEPS * 60 / PACE + 15) ))
LEFT_MIN=$(( (${SLURM_JOB_END_TIME:-0} - $(date +%s)) / 60 ))
[ "$LEFT_MIN" -ge "$NEED_MIN" ] || {
    echo "FATAL: $# life/lives of $STEPS steps need about $NEED_MIN min at $PACE steps/h and the job has $LEFT_MIN min -- a longer sbatch -t, fewer lives, or PACE=<measured steps/h>"; exit 1; }
echo "--- preflight: $MODEL effort high, $# x $STEPS steps, memory $NEED_MB of $HAVE_MB MB, wall $NEED_MIN of $LEFT_MIN min"

# One request to MODEL through the CLI and the account the lives will use, in a home of
# its own (claude-home.sh) that is removed again. A CLI too old for the model answers
# every turn with an API error and the life steps on as no-ops (the smoke of 2026-10-03:
# Claude Code 2.1.266 and claude-opus-5-5, 17 turns of 17), so the lane stops here unless
# the answer comes back and is billed to MODEL.
probe() {(
    eval "$(scripts/claude-home.sh "preflight-$SLURM_JOB_ID")" || exit 1
    trap 'rm -rf "$CLAUDE_RUNTIME_HOME"' EXIT
    cd "$MINESTUDIO_DIR/tmp" && echo "Reply with the single word ok." |
        CLAUDE_CONFIG_DIR="$CLAUDE_RUNTIME_HOME" timeout 300 "$MCU_CLAUDE_BIN" -p --model "$MODEL" \
            --effort high --setting-sources project --strict-mcp-config --disable-slash-commands \
            --tools "" --output-format json
)}
PROBE="$(probe | python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    d = [e for e in d if e.get("type") == "result"][-1] if isinstance(d, list) else d
    models = sorted(d.get("modelUsage") or {})
    ok = not d.get("is_error") and any(m.startswith(sys.argv[1]) for m in models)
    print("ok" if ok else "FAILED", "billed to", models, "answer", repr(str(d.get("result"))[:200]))
except Exception:
    print("FAILED", repr(raw[:300]))
' "$MODEL")"
case "$PROBE" in
    ok*) echo "--- model probe: $PROBE";;
    *) echo "FATAL: $MODEL did not answer through $MCU_CLAUDE_BIN -- $PROBE"; exit 1;;
esac
[ "${PREFLIGHT_ONLY:-0}" = 1 ] && { echo "preflight only: nothing run"; exit 0; }

# Code provenance, once per lane: the commit and the uncommitted port on top of it.
mkdir -p logs
git -C .. rev-parse HEAD > "logs/lane-$SLURM_JOB_ID.commit"
git -C .. diff HEAD > "logs/lane-$SLURM_JOB_ID.patch"

# The quota guard (scripts/quota_guard.py, as in skill_reuse3.sbatch): cancels this job on
# the first refused Claude turn of any arm named on the command line, or at the caps when
# given (QUOTA_5H_CAP / QUOTA_7D_CAP, fractions; off above 1.0). QUOTA_GUARD=0 turns it off.
if [ "${QUOTA_GUARD:-1}" = 1 ]; then
    python3 scripts/quota_guard.py --job "$SLURM_JOB_ID" --root output --prefix "${1%%=*}" \
        --cap-5h "${QUOTA_5H_CAP:-1.01}" --cap-7d "${QUOTA_7D_CAP:-1.01}" \
        --marker "logs/quota_stop-$SLURM_JOB_ID.json" &
    GUARD_PID=$!
    trap 'kill "$GUARD_PID" 2>/dev/null' EXIT
    echo "--- quota guard on (pid $GUARD_PID): 5-hour cap ${QUOTA_5H_CAP:-off}, 7-day cap ${QUOTA_7D_CAP:-off}"
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
    bash scripts/run-arm.sh --arm "$ARM" --memory mfm --task "${TASK:-mine_diamond_from_scratch}" \
        --cli claude --model "$MODEL" --effort high \
        --steps "$STEPS" --green-port "$GREEN" --purple-port "$PURPLE" \
        ${WORLD_SEED:+--world-seed "$WORLD_SEED"} \
        -- ${FLAGS//,/ }
    echo "--- $ARM exit=$? $(date -Is)"
done
echo "finished=$(date -Is)"
