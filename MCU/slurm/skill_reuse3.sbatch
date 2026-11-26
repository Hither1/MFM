#!/usr/bin/env bash
# Skill reuse, third design: the dragon chain's LAST EIGHT milestones (17-24: kill a blaze,
# the rod, kill an enderman, the pearl, blaze powder, the eye, end stone, the dragon), each
# as a short tail probe with the SEARCH handed over. No life on any chassis ever banked one
# of the eight (the ceiling is 16/24; the Nether continuations died within 60 blocks of the
# portal), so no earlier life holds a skill for them: the skills under test are the ones the
# agent WRITES ITSELF while playing the probe, and the rows are a chain of lives, as in the
# second design. Nothing hand-written is given to any claim row.
#
#   TASKS   blaze_tail       3 blazes at the spawn: kill_blaze, blaze_rod, blaze_powder
#           enderman_tail    3 endermen + 2 powder: kill_enderman, ender_pearl, eye_of_ender
#           eye_craft_tail   rods + pearls given: blaze_powder, eye_of_ender (the crafting control)
#           end_stone_tail   start on the End's arrival platform: end_stone
#           dragon_tail      the same start with bow and arrows: kill_ender_dragon (the ceiling)
#   ROWS (the claim rows, run in this order, each the source of the next)
#           none     the shipped mfm arm, a fresh life: the raw keys and whatever it writes
#                    for itself in mine/ (procedures, reflexes, notes). This life is also
#                    the chain's life 1.
#           carry    life 2: the same probe carrying the none life's whole memory
#                    (--seed-memory, same world, --install-carried; its workshop turn is
#                    where life 1's lessons can become procedures)
#           carry3, carry4, ...  life N: the same probe carrying life N-1's whole memory
#                    (which carries the lives before it): a longer chain of learning for a
#                    probe one or two lives do not crack (the enderman: both lives wrote the
#                    right facts -- head-gaze aggro, 40 hp, 6-10 damage, teleports -- and
#                    died with 1-3 of the ~6 hits a kill needs). Name them in ROWS in order.
#           own      a fresh life with ONLY the scripts the chain's LAST carry life wrote
#                    (and the lives it carried) installed in
#                    mine/ (--install-scripts: no notes, no record, no previous/) -- the
#                    skills-only row; none vs own is the clean reuse comparison
#           ownx     a fresh life with the scripts of ANOTHER probe's chain installed
#                    (OWNX_SEED=<that chain's carry memory dir>): transfer across probes
#   DEATHS  1 (default): every life runs with --near-deaths, so a death whose respawn is
#           close to where it happened is named to the agent (YOU DIED) and voids its plan.
#           These probes fight AT the spawn: the first pilot (job 50240421, run without it)
#           had 7 deaths and the harness named one. 0: the shipped rule (a teleport of 15+).
#   TAG     prefix of every arm name (default sr3); REP replicate label: the chain (none,
#           carry) is replicate 1's; a replicate re-runs the fresh rows (none, own, ownx,
#           the controls) on the same seeds
#   PROBE_STEPS (default 2000), STOP_AFTER (default 400: steps played on after the last
#   milestone), MODEL (default claude-opus-5, effort high)
#   CLI     claude (default) or codex: the model channel of every life. codex needs
#           CODEX_NODE_DIR (the codex install, as slurm/codex_lane.sbatch) and MCU_CODEX_AUTH,
#           and a MODEL the account serves (gpt-6-astra); the quota guard reads Claude turns
#           only and is not started.
#   QUOTA_GUARD (default 1), QUOTA_5H_CAP, QUOTA_7D_CAP (default off): scripts/quota_guard.py
#           runs beside the lives and cancels the job when a turn is REFUSED by the account's
#           limit (a refused turn is a no-op, and two lives of 10-04 played 1,424 of them),
#           or when a window passes its cap. Set the caps (0.80, 0.75) when the arms spend
#           an account somebody also works on; the dedicated arm account needs none. A life
#           it cuts has no result, is run again from scratch, and is never a chain source.
#
#   STAGE=probes  every task of TASKS, rows in the order of ROWS
#   STAGE=smoke   SMOKE=llm (the only smoke): one real PROBE_STEPS life of
#                 SMOKE_TASK/SMOKE_ROW. (The scripted fake-model smokes drove the harness
#                 macros, which are gone.)
#
# Submit from MCU/ of the run worktree with a clean environment, as skill_reuse.sbatch:
#   env -i HOME USER PATH=$HOME/miniforge3/bin:/usr/bin:/bin MINESTUDIO_SHARED=... \
#       MCU_CLAUDE_BIN=... MCU_CLAUDE_EVAL_DIR=... sbatch -J sr3 slurm/skill_reuse3.sbatch
# A life whose logs/<arm>_result.json exists is not run again.
#SBATCH -p shared
#SBATCH -c 12
#SBATCH --mem=48G
#SBATCH -t 1-12:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="

STAGE="${STAGE:-probes}"
TAG="${TAG:-sr3}"
ROWS="${ROWS:-none carry own}"
TASKS="${TASKS:-blaze_tail enderman_tail eye_craft_tail end_stone_tail dragon_tail}"
REP="${REP:-}"
PROBE_STEPS="${PROBE_STEPS:-2000}"
STOP_AFTER="${STOP_AFTER:-400}"
MODEL="${MODEL:-claude-opus-5}"
CLI="${CLI:-claude}"
if [ "$CLI" = codex ]; then
    export PATH="${CODEX_NODE_DIR:?}/bin:$PATH" CODEX_BIN="$CODEX_NODE_DIR/bin/codex"
    export MCU_CODEX_AUTH="${MCU_CODEX_AUTH:?}"
    "$CODEX_BIN" --version >/dev/null 2>&1 || { echo "FATAL: no runnable codex at $CODEX_BIN"; exit 1; }
    echo "--- codex: $CODEX_BIN $("$CODEX_BIN" --version 2>&1 | tail -1)"
    QUOTA_GUARD=0
fi
OWNX_SEED="${OWNX_SEED:-}"
SMOKE_EXTRA="${SMOKE_EXTRA:-}"
LIVE_OPT=""
DEATHS="${DEATHS:-1}"
[ "$DEATHS" = 1 ] && LIVE_OPT="--near-deaths"
# FRONTIER=1: every life of this job gets --frontier (grid.py), chain rows included, so a
# carried life also counts the ground its earlier lives saw (previous/*/grid.jsonl).
[ "${FRONTIER:-0}" = 1 ] && LIVE_OPT="$LIVE_OPT --frontier"

export JAVA_HOME=/usr MCU_SKIP_ENV_SH=1
export MINESTUDIO_DIR="${TMPDIR:-/tmp}/minestudio-$SLURM_JOB_ID"
mkdir -p "$MINESTUDIO_DIR/runtime" "$MINESTUDIO_DIR/tmp"
[ -e "$MINESTUDIO_DIR/engine" ] || ln -s "${MINESTUDIO_SHARED:?}/engine" "$MINESTUDIO_DIR/engine"

python3 -c 'import sys, PIL; assert sys.version_info >= (3, 8)' 2>/dev/null || {
    echo "FATAL: python3 on PATH ($(command -v python3), $(python3 -V 2>&1)) is not >= 3.8 with PIL"; exit 1; }
echo "--- python3: $(command -v python3) $(python3 -V 2>&1)"

mkdir -p logs
git -C .. rev-parse HEAD > "logs/skill_reuse3-$SLURM_JOB_ID.commit"
git -C .. diff HEAD > "logs/skill_reuse3-$SLURM_JOB_ID.patch"

# The quota guard: stops this job on the first refused turn, or at the caps when given.
if [ "${QUOTA_GUARD:-1}" = 1 ]; then
    python3 scripts/quota_guard.py --job "$SLURM_JOB_ID" --root output --prefix "$TAG" \
        --cap-5h "${QUOTA_5H_CAP:-1.01}" --cap-7d "${QUOTA_7D_CAP:-1.01}" \
        --marker "logs/quota_stop-$SLURM_JOB_ID.json" &
    GUARD_PID=$!
    trap 'kill "$GUARD_PID" 2>/dev/null' EXIT
    echo "--- quota guard on (pid $GUARD_PID): 5-hour cap ${QUOTA_5H_CAP:-off}, 7-day cap ${QUOTA_7D_CAP:-off}"
fi

# What a task needs the purple side told beyond its config: the two End probes start
# in the End, which the engine's biome id cannot say.
task_extra() {
    case "$1" in
        end_stone_tail|dragon_tail|dragon_diamond) echo "--start-dimension end";;
        dragon_respawn) echo "--start-dimension end --respawn-dimension end";;
        nether_search) echo "--start-dimension nether --respawn-dimension nether";;
        # a start teleport inside the Overworld is an arrival too, not a death (job 50998371)
        stronghold_tail) echo "--start-dimension overworld";;
        *) ;;
    esac
}
# The chain's memories (replicate 1's lives): life 1 is the none row, life 2 the carry row,
# life N the carry<N> row. `last_carry` is the newest carry life that has a memory.
mem() { echo "$PWD/output/${TAG}_$1_$2/episode_001/memory"; }
# A life that can be a source: it has a memory AND a result. One cut short (the quota
# guard, a cancelled job, a server that never came up) has a memory and no result.
lived() { [ -d "$(mem "$1" "$2")/mine" ] && [ -s "logs/${TAG}_$1_$2_result.json" ]; }   # task row
last_carry() {   # task
    local n
    for n in 9 8 7 6 5 4 3; do lived "$1" "carry$n" && { echo "carry$n"; return; }; done
    lived "$1" carry && echo carry
}
# A row's options for run-arm.sh, with its purple-side options after the `--`. The chain
# rows read the earlier life's memory; a missing one is a launch error, never a silent
# fresh life.
row_opts() {   # row task
    case "$1" in
        none)   echo "--";;
        # none + the --frontier cell map (grid.py: where the avatar has NOT been)
        frontier) echo "-- --frontier";;
        carry)  lived "$2" none || { echo "FATAL: carry needs the finished none life at $(mem "$2" none)" >&2; exit 1; }
                echo "--seed-memory $(mem "$2" none) -- --install-carried";;
        carry[3-9])
                local prev; prev=$(( ${1#carry} - 1 )); [ "$prev" = 2 ] && prev=""
                lived "$2" "carry$prev" || { echo "FATAL: $1 needs the finished carry$prev life at $(mem "$2" carry$prev)" >&2; exit 1; }
                echo "--seed-memory $(mem "$2" carry$prev) -- --install-carried";;
        own)    local lc; lc=$(last_carry "$2"); [ -n "$lc" ] || { echo "FATAL: own needs a finished carry life of $2" >&2; exit 1; }
                echo "-- --install-scripts $(mem "$2" $lc)";;
        ownx)   [ -d "$OWNX_SEED/mine" ] || { echo "FATAL: ownx needs OWNX_SEED=<another chain's carry memory dir>" >&2; exit 1; }
                echo "-- --install-scripts $OWNX_SEED";;
        *) echo "FATAL: unknown row $1" >&2; exit 1;;
    esac
}

N=0
life() {   # life ARM TASK STEPS [run-arm options...] -- [purple options...]
    local arm="$1" task="$2" steps="$3"; shift 3
    N=$((N + 1))
    if [ -s "logs/${arm}_result.json" ]; then
        echo "--- $arm: has a result, not run again"; return 0
    fi
    export MCU_DISPLAY_NUM=$(( (SLURM_JOB_ID % 10000) * 4 + 300 + (N % 4) ))
    local green=$(( 20000 + (SLURM_JOB_ID % 1400) * 32 + 2 * N ))
    echo "--- $arm task=$task steps=$steps display=:$MCU_DISPLAY_NUM ports=$green/$((green + 1)) $(date -Is)"
    cp "logs/skill_reuse3-$SLURM_JOB_ID.commit" "logs/${arm}_code.commit"
    cp "logs/skill_reuse3-$SLURM_JOB_ID.patch" "logs/${arm}_code.patch"
    bash scripts/run-arm.sh --arm "$arm" --memory mfm --task "$task" --steps "$steps" \
        --overwrite --green-port "$green" --purple-port "$((green + 1))" "$@"
    echo "--- $arm exit=$? $(date -Is)"
}
# What the smokes read back: the kill_entity events, the milestones, the deaths, where it stood.
tell() {
    local arm="$1" log="output/$1/episode_001/memory/logs.txt" rep="output/$1/episode_001/worldmodel_report.json"
    [ -f "$log" ] || { echo "--- $arm: no logs.txt"; return; }
    # line-anchored: the model quotes "[EVENT] kill_entity" and "YOU DIED" in its own plans
    echo "--- $arm: kill_entity events $(grep -c '^\[EVENT\] kill_entity' "$log"), sword hits $(grep -c '^\[EVENT\] use_item [a-z_]*sword' "$log"), pickups $(grep -c '^\[EVENT\] pickup' "$log"), named deaths $(grep -c '^\[NOTE\] YOU DIED' "$log")"
    echo "--- $arm: first position $(grep -m1 -o '\[STATE\] pos=([^)]*)' "$log"), last $(grep -o '\[STATE\] pos=([^)]*)' "$log" | tail -1)"
    [ -f "$rep" ] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('--- milestones', d.get('milestones'), '| start_dimension', d.get('start_dimension'))" "$rep"
}

export MCU_STOP_AFTER_COMPLETE="$STOP_AFTER"
if [ "$STAGE" = smoke ]; then
    SMOKE="${SMOKE:-llm}"
    if [ "$SMOKE" = llm ]; then
        T="${SMOKE_TASK:-blaze_tail}"; R="${SMOKE_ROW:-none}"
        ARM="${TAG}_smoke_${T}_${R}"
        # shellcheck disable=SC2046
        X="$(row_opts "$R" "$T")" || exit 1
        # shellcheck disable=SC2046,SC2086
        life "$ARM" "$T" "${SMOKE_STEPS:-$PROBE_STEPS}" --cli "$CLI" --model "$MODEL" --effort high \
            $X $(task_extra "$T") $LIVE_OPT
        tell "$ARM"; echo "finished=$(date -Is)"; exit 0
    fi
    echo "FATAL: SMOKE must be llm"; exit 1
fi

[ "$STAGE" = probes ] || { echo "FATAL: STAGE must be probes or smoke"; exit 1; }
# The rows run in the order given (none before carry before own: each is the next one's
# source). The chain's lives are replicate 1's: a replicate (REP=2, ...) never re-runs
# carry, it re-runs the fresh rows on the same seeds.
for TASK in $TASKS; do
    for ROW in $ROWS; do
        ARM="${TAG}${REP:+_r$REP}_${TASK}_${ROW}"
        case "$ROW" in carry|carry[3-9])
            [ -z "$REP" ] || [ "$REP" = 1 ] || continue
            ARM="${TAG}_${TASK}_${ROW}";;
        esac
        X="$(row_opts "$ROW" "$TASK")" || exit 1
        # shellcheck disable=SC2046,SC2086
        life "$ARM" "$TASK" "$PROBE_STEPS" --cli "$CLI" --model "$MODEL" --effort high \
            $X $(task_extra "$TASK") $LIVE_OPT
        tell "$ARM"
    done
done
echo "finished=$(date -Is)"
