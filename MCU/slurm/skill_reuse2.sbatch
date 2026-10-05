#!/usr/bin/env bash
# Skill reuse, second design: the checkpoints are LIVES, and the probes measure the tail.
#
# The first design (skill_reuse.sbatch) cut one diamond life's memory at 4k/8k/12k steps
# and found nothing: within a life memory grows as notes, procedures are written at the
# workshop turn of the NEXT life, and three quarters of each probe was the spawn-luck
# opening (find a tree ... cobblestone). Here:
#
#   STAGE=source  Diamond life 2 in world 0, carrying life 1 (sr_src_diamond, done), with
#                 its mine/ history recorded. Its workshop turn is where life 1's lessons
#                 can become procedures. Check output/<L2>/episode_001/memory/mine before
#                 spending on probes: if it wrote nothing of its own, say so.
#   STAGE=probes  Three new tasks in world seed 1 that START from the opening (a stone
#                 pickaxe, a table, logs, cobblestone handed over by the task config) and
#                 end in an iron item: iron_shield_tail, shears_tail, bucket_tail. Rows:
#                   none       no memory
#                   life1      previous/ = diamond life 1
#                   life2      previous/ = diamond lives 1 and 2
#                   life2_nosk previous/ = lives 1 and 2 with every agent-written
#                              procedure, reflex and tool removed (diary only)
#                   skills     NO previous/: only the scripts lives 1 and 2 wrote,
#                              installed in mine/ (--install-scripts). Against `none`
#                              this is the clean comparison for skills: nothing of
#                              the earlier lives is there but their scripts. The
#                              diary rows cannot give it, because the notes describe
#                              the scripts well enough for a probe to rebuild them.
#                 A row's seeds are built once under output/<TAG>_mem/. Every carried
#                 row runs with --install-carried: the scripts the carried lives wrote are
#                 installed in the probe's mine/, armed and callable, and the contract
#                 lists them. Without it a probe reused a skill only if it chose to copy
#                 it out of previous/, and the rows measured that choice. In life2_nosk
#                 the install is empty (the seed holds no script of its own) and the
#                 contract says so; that row is the diary-only control.
#   STAGE=all     both.
#   STAGE=smoke   one short tail probe from no memory (SMOKE_TASK, default
#                 iron_shield_tail; SMOKE_STEPS, default 400), to see the kit arrive at
#                 step 0 and the first rule fire; nothing else.
#
#   TAG          prefix of every arm name (default sr2)
#   ROWS         default "none life1 life2 life2_nosk"
#   TASKS        default "iron_shield_tail shears_tail bucket_tail"; the other tails
#                are coal_torches_tail and cook_meat_tail (three cows summoned at the spawn);
#                iron_shield_vein is iron_shield_tail with an ore vein placed and named
#   REP          replicate label: probes become <TAG>_r<REP>_<task>_<row>
#   SOURCE_STEPS / PROBE_STEPS  budgets (default 12000 / 4000)
#   STOP_AFTER   steps a probe plays on after its last milestone (default 400)
#   MODEL        default claude-opus-5 (effort high)
#
# Submit from MCU/ of the run worktree with a clean environment (see skill_reuse.sbatch).
# A life whose logs/<arm>_result.json exists is not run again.
#SBATCH -p shared
#SBATCH -c 12
#SBATCH --mem=48G
#SBATCH -t 2-12:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="

STAGE="${STAGE:-all}"
TAG="${TAG:-sr2}"
ROWS="${ROWS:-none life1 life2 life2_nosk}"
TASKS="${TASKS:-iron_shield_tail shears_tail bucket_tail}"
REP="${REP:-}"
SOURCE_STEPS="${SOURCE_STEPS:-12000}"
PROBE_STEPS="${PROBE_STEPS:-4000}"
STOP_AFTER="${STOP_AFTER:-400}"
MODEL="${MODEL:-claude-opus-5}"
L1="output/sr_src_diamond/episode_001/memory"       # diamond life 1, from the first design
L2_ARM="${TAG}_src_diamond_l2"
L2="output/$L2_ARM/episode_001/memory"

export JAVA_HOME=/usr MCU_SKIP_ENV_SH=1
export MINESTUDIO_DIR="${TMPDIR:-/tmp}/minestudio-$SLURM_JOB_ID"
mkdir -p "$MINESTUDIO_DIR/runtime" "$MINESTUDIO_DIR/tmp"
[ -e "$MINESTUDIO_DIR/engine" ] || ln -s "${MINESTUDIO_SHARED:?}/engine" "$MINESTUDIO_DIR/engine"

python3 -c 'import sys, PIL; assert sys.version_info >= (3, 8)' 2>/dev/null || {
    echo "FATAL: python3 on PATH ($(command -v python3), $(python3 -V 2>&1)) is not >= 3.8 with PIL"; exit 1; }
echo "--- python3: $(command -v python3) $(python3 -V 2>&1)"
export MCU_CLAUDE_BIN="${MCU_CLAUDE_BIN:?}"
export MCU_CLAUDE_EVAL_DIR="${MCU_CLAUDE_EVAL_DIR:?}"

mkdir -p logs
git -C .. rev-parse HEAD > "logs/skill_reuse2-$SLURM_JOB_ID.commit"
git -C .. diff HEAD > "logs/skill_reuse2-$SLURM_JOB_ID.patch"

N=0
life() {
    local arm="$1" task="$2" steps="$3"; shift 3
    N=$((N + 1))
    if [ -s "logs/${arm}_result.json" ]; then
        echo "--- $arm: has a result, not run again"; return 0
    fi
    export MCU_DISPLAY_NUM=$(( (SLURM_JOB_ID % 10000) * 4 + 300 + (N % 4) ))
    local green=$(( 20000 + (SLURM_JOB_ID % 1400) * 32 + 2 * N ))
    echo "--- $arm task=$task steps=$steps display=:$MCU_DISPLAY_NUM ports=$green/$((green + 1)) $(date -Is)"
    cp "logs/skill_reuse2-$SLURM_JOB_ID.commit" "logs/${arm}_code.commit"
    cp "logs/skill_reuse2-$SLURM_JOB_ID.patch" "logs/${arm}_code.patch"
    bash scripts/run-arm.sh --arm "$arm" --memory mfm --task "$task" --steps "$steps" \
        --cli claude --model "$MODEL" --effort high --overwrite \
        --green-port "$green" --purple-port "$((green + 1))" "$@"
    echo "--- $arm exit=$? $(date -Is)"
}

[ -d "$L1/mine" ] || { echo "FATAL: diamond life 1 memory missing at $L1"; exit 1; }

if [ "$STAGE" = smoke ]; then
    export MCU_STOP_AFTER_COMPLETE="$STOP_AFTER"
    SMOKE_TASK="${SMOKE_TASK:-iron_shield_tail}"
    life "${TAG}_smoke_${SMOKE_TASK}_none" "$SMOKE_TASK" "${SMOKE_STEPS:-400}"
    echo "finished=$(date -Is)"; exit 0
fi

# 1. Diamond life 2, carrying life 1 in the same world.
if [ "$STAGE" = source ] || [ "$STAGE" = all ]; then
    HIST="logs/${L2_ARM}_mine_history"
    if [ ! -s "logs/${L2_ARM}_result.json" ]; then
        rm -rf "$HIST"
        python3 scripts/mine_history.py watch "$L2" "$HIST" --every 15 --idle 1000000 &
        WATCH=$!
        life "$L2_ARM" mine_diamond_from_scratch "$SOURCE_STEPS" --seed-memory "$PWD/$L1"
        sleep 45; kill "$WATCH" 2>/dev/null; wait "$WATCH" 2>/dev/null
    fi
    [ -s "logs/${L2_ARM}_result.json" ] || { echo "FATAL: life 2 has no result"; exit 1; }
    echo "--- life 2 wrote (not shipped):"
    python3 scripts/memory_at.py "$L2" --own || true
fi
[ "$STAGE" = source ] && { echo "finished=$(date -Is)"; exit 0; }

# 2. The row seeds.
[ -d "$L2/mine" ] || { echo "FATAL: diamond life 2 memory missing at $L2"; exit 1; }
# Life 2's memory carries life 1 under previous/, so seeding it brings both lives
# (previous.lives_of). The diary-only seed is a hard-linked copy with every agent-written
# procedure, reflex and tool removed from both lives.
MEM="output/${TAG}_mem"
mkdir -p "$MEM"
[ -e "$MEM/life1" ] || ln -s "$PWD/$L1" "$MEM/life1"
[ -e "$MEM/life2" ] || ln -s "$PWD/$L2" "$MEM/life2"
if [ ! -d "$MEM/life2_nosk" ]; then
    # built aside and moved into place, so replicate jobs on other nodes never read a
    # half-built seed; the loser of the move throws its copy away
    TMP="$MEM/.life2_nosk.$SLURM_JOB_ID"
    python3 scripts/memory_at.py "$L2" --strip-own --out "$TMP" \
        > "logs/${TAG}_mem_life2_nosk.$SLURM_JOB_ID.json" || { echo "FATAL: stripping life 2 failed"; exit 1; }
    mv -T "$TMP" "$MEM/life2_nosk" 2>/dev/null || rm -rf "$TMP"
fi
seeds() {   # the --seed-memory options of one row
    case "$1" in
        none|skills) ;;
        life1)      echo "--seed-memory $PWD/$MEM/life1";;
        life2)      echo "--seed-memory $PWD/$MEM/life2";;
        life2_nosk) echo "--seed-memory $PWD/$MEM/life2_nosk";;
        *) echo "FATAL: unknown row $1" >&2; exit 1;;
    esac
}

# 3. The probes, row order rotated from task to task and from replicate to replicate.
export MCU_STOP_AFTER_COMPLETE="$STOP_AFTER"
read -r -a ROWARR <<< "$ROWS"
k=$(( ${REP:-1} - 1 ))
for TASK in $TASKS; do
    for j in "${!ROWARR[@]}"; do
        ROW="${ROWARR[$(( (j + k) % ${#ROWARR[@]} ))]}"
        ARM="${TAG}${REP:+_r$REP}_${TASK}_${ROW}"
        S="$(seeds "$ROW")" || exit 1
        if [ "$ROW" = skills ]; then
            life "$ARM" "$TASK" "$PROBE_STEPS" -- --install-scripts "$PWD/$MEM/life2"
        elif [ -z "$S" ]; then
            life "$ARM" "$TASK" "$PROBE_STEPS"
        else
            # shellcheck disable=SC2086
            life "$ARM" "$TASK" "$PROBE_STEPS" $S -- --carried-world other --install-carried
        fi
    done
    k=$((k + 1))
done
echo "finished=$(date -Is)"
