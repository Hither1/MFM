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
#           none     the shipped mfm arm, a fresh life: the 28 atoms and whatever it writes
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
#   CONTROLS (not claim rows; off unless named in ROWS; they hand the agent HARNESS-written
#   skills or doctrine, so they say what the harness's own macros are worth, never what
#   the agent learned)
#           fight    + the generic entity macros (face_entity, fight, shoot_bow)
#           macros   + the endgame macros (fight_blaze, enderman_pit, explore_nether,
#                    throw_eye, travel_bearing, fill_end_portal, enter_end, mine_end_stone,
#                    break_crystal, attack_dragon)
#           recipe   + references/endgame.md: the chain's doctrine as prose
#   GRANT_FIGHT / GRANT_MACROS   the procedure names the two control rows grant
#   LIVE    1: every life runs with --own-live (own.py, the closed-loop section): a script
#           the agent writes with `LOOP = True` is run during the plan on the live frame,
#           and its reflexes get the frame. A capability of the chassis, the same in every
#           row. Use a TAG of its own (TAG=sr3l) so its lives are not the blind chain's.
#   DEATHS  1 (default): every life runs with --near-deaths, so a death whose respawn is
#           close to where it happened is named to the agent (YOU DIED) and voids its plan.
#           These probes fight AT the spawn: the first pilot (job 50240421, run without it)
#           had 7 deaths and the harness named one. 0: the shipped rule (a teleport of 15+).
#   TAG     prefix of every arm name (default sr3); REP replicate label: the chain (none,
#           carry) is replicate 1's; a replicate re-runs the fresh rows (none, own, ownx,
#           the controls) on the same seeds
#   PROBE_STEPS (default 2000), STOP_AFTER (default 400: steps played on after the last
#   milestone), MODEL (default claude-opus-5, effort high)
#   QUOTA_GUARD (default 1), QUOTA_5H_CAP, QUOTA_7D_CAP (default off): scripts/quota_guard.py
#           runs beside the lives and cancels the job when a turn is REFUSED by the account's
#           limit (a refused turn is a no-op, and two lives of 10-04 played 1,424 of them),
#           or when a window passes its cap. Set the caps (0.80, 0.75) when the arms spend
#           an account somebody also works on; the dedicated arm account needs none. A life
#           it cuts has no result, is run again from scratch, and is never a chain source.
#
#   STAGE=probes  every task of TASKS, rows in the order of ROWS
#   STAGE=smoke   SMOKE=kill: blaze_tail driven by the FAKE codex (tests/fake_codex.py) that
#                 only ever calls the harness macro fight_blaze -- an ENGINE check, not a row:
#                 does `kill_entity` fire at all here (0 kills in 37 recorded lives), do the
#                 kill, the rod and the fire come as the game says. SMOKE=end: end_stone_tail
#                 with the fake that only looks around -- does /execute in land the avatar on
#                 the platform at (100, 49, 0) with no YOU DIED, do the frames show the End.
#                 SMOKE=cow: cook_meat_tail (three cows at the spawn) with the fake calling the
#                 harness fight on a cow, two sword hits -- the cheapest check that the
#                 `kill_entity` rule fires at all, when the blaze smoke lands no hit.
#                 SMOKE=raw: the kill_check task (one cow in a fence ring two blocks east) with
#                 NO grant: raw attack pulses on the cooldown at cow height -- the kill-rule
#                 check with nothing but atoms, on a target that cannot flee. (cook_meat_tail's
#                 cows took hits -- the red flash is in the frames -- and ran: smoke 50226471.)
#                 SMOKE=loop: kill_check with --own-live: the fake writes a LOOP procedure that
#                 pulses attack and records the frame it was handed at every call -- the
#                 engine check of the closed loop (calls 13 ticks apart, a different frame
#                 each call, the kill), again an instrument and not a skill.
#                 SMOKE=death: the death_check task (the avatar is dropped 40 blocks onto the
#                 spawn) with --own-live and a LOOP procedure that writes down every tick's
#                 health, pose and inventory: what a death AT the spawn looks like, and
#                 whether the harness names it.
#                 SMOKE=look: SMOKE_TASK (default enderman_tail) with the fake that only pans
#                 the camera -- what the scene of a probe looks like and whether it holds
#                 (the time of day, the summoned mobs still there after 300 steps).
#                 SMOKE=stare_eyes | stare_body: the stare_check task (one enderman, the
#                 avatar under Resistance V) with --own-live and a scripted loop that finds
#                 the eyes and keeps the crosshair ON them (eyes), or on the body once inside
#                 4.5 blocks (body): does a stared-at enderman teleport away at contact here?
#                 SMOKE=llm: one real PROBE_STEPS life of SMOKE_TASK/SMOKE_ROW.
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
OWNX_SEED="${OWNX_SEED:-}"
SMOKE_EXTRA="${SMOKE_EXTRA:-}"
LIVE="${LIVE:-0}"
LIVE_OPT=""; [ "$LIVE" = 1 ] && LIVE_OPT="--own-live"
DEATHS="${DEATHS:-1}"
[ "$DEATHS" = 1 ] && LIVE_OPT="$LIVE_OPT --near-deaths"
GRANT_FIGHT="${GRANT_FIGHT:-face_entity,fight,shoot_bow}"
GRANT_MACROS="${GRANT_MACROS:-$GRANT_FIGHT,fight_blaze,enderman_pit,explore_nether,throw_eye,travel_bearing,fill_end_portal,enter_end,mine_end_stone,break_crystal,attack_dragon}"

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
        fight)  echo "-- --grant $GRANT_FIGHT";;
        macros) echo "-- --grant $GRANT_MACROS";;
        recipe) echo "-- --endgame-recipes";;
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
    echo "--- $arm: kill_entity events $(grep -c '^\[EVENT\] kill_entity' "$log"), sword hits $(grep -c '^\[EVENT\] use_item [a-z_]*sword' "$log"), pickups $(grep -c '^\[EVENT\] pickup' "$log"), named deaths $(grep -c '^\[NOTE\] YOU DIED' "$log"), withheld/refused notes $(grep -c "^\[NOTE\] '[a-z_]*' is \(withheld in this run\|not in this run\)" "$log")"
    echo "--- $arm: first position $(grep -m1 -o '\[STATE\] pos=([^)]*)' "$log"), last $(grep -o '\[STATE\] pos=([^)]*)' "$log" | tail -1)"
    [ -f "$rep" ] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('--- milestones', d.get('milestones'), '| granted', d.get('granted'), '| start_dimension', d.get('start_dimension'))" "$rep"
}

export MCU_STOP_AFTER_COMPLETE="$STOP_AFTER"
if [ "$STAGE" = smoke ]; then
    SMOKE="${SMOKE:-kill}"
    if [ "$SMOKE" = llm ]; then
        T="${SMOKE_TASK:-blaze_tail}"; R="${SMOKE_ROW:-macros}"
        ARM="${TAG}_smoke_${T}_${R}"
        # shellcheck disable=SC2046
        X="$(row_opts "$R" "$T")" || exit 1
        # shellcheck disable=SC2046,SC2086
        life "$ARM" "$T" "${SMOKE_STEPS:-$PROBE_STEPS}" --cli claude --model "$MODEL" --effort high \
            $X $(task_extra "$T") $LIVE_OPT
        tell "$ARM"; echo "finished=$(date -Is)"; exit 0
    fi
    # The fake codex: a scripted model, so the engine and the macros are what is tested.
    FAKE="$(cd .. && pwd)/tests/fake_codex.py"
    [ -f "$FAKE" ] || { echo "FATAL: no fake codex at $FAKE"; exit 1; }
    case "$SMOKE" in
        kill) T=blaze_tail;     SCRIPT=slurm/smoke/kill.jsonl; STEPS="${SMOKE_STEPS:-400}"; GRANT="--grant $GRANT_FIGHT,fight_blaze";;
        end)  T=end_stone_tail; SCRIPT=slurm/smoke/end.jsonl;  STEPS="${SMOKE_STEPS:-200}"; GRANT="";;
        cow)  T=cook_meat_tail; SCRIPT=slurm/smoke/cow.jsonl;  STEPS="${SMOKE_STEPS:-400}"; GRANT="--grant $GRANT_FIGHT";;
        edge) T=edge_check;     SCRIPT=slurm/smoke/edge.jsonl; STEPS="${SMOKE_STEPS:-320}"; GRANT="";;
        raw)  T=kill_check;     SCRIPT=slurm/smoke/raw.jsonl;  STEPS="${SMOKE_STEPS:-400}"; GRANT="";;
        loop) T=kill_check;     SCRIPT=slurm/smoke/loop.jsonl; STEPS="${SMOKE_STEPS:-400}"; GRANT="--own-live";;
        death) T=death_check;   SCRIPT=slurm/smoke/death.jsonl; STEPS="${SMOKE_STEPS:-200}"; GRANT="--own-live $SMOKE_EXTRA";;
        stare_eyes|stare_body)
              T=stare_check; SCRIPT="slurm/smoke/$SMOKE.jsonl"; STEPS="${SMOKE_STEPS:-500}"; GRANT="--own-live";;
        scan) T="${SMOKE_TASK:-fortress_look}"; SCRIPT=slurm/smoke/scan.jsonl; STEPS="${SMOKE_STEPS:-400}"; GRANT="$SMOKE_EXTRA";;
        look) T="${SMOKE_TASK:-enderman_tail}"; SCRIPT=slurm/smoke/end.jsonl; STEPS="${SMOKE_STEPS:-300}"; GRANT="$(task_extra "$T") $SMOKE_EXTRA";;
        *) echo "FATAL: SMOKE must be kill, end, cow, raw, loop, death, look, stare_eyes, stare_body or llm"; exit 1;;
    esac
    ARM="${TAG}_smoke_${SMOKE}"
    cp "$SCRIPT" "logs/${ARM}_script.jsonl"; rm -f "logs/${ARM}_script.jsonl.idx" "logs/${ARM}_fake_calls.jsonl"
    printf '#!/usr/bin/env bash\nexec python3 %q "$@"\n' "$FAKE" > "logs/${ARM}_fake_codex.sh"; chmod +x "logs/${ARM}_fake_codex.sh"
    export CODEX_BIN="$PWD/logs/${ARM}_fake_codex.sh" MCU_CODEX_AUTH=none
    export FAKE_CODEX_SCRIPT="$PWD/logs/${ARM}_script.jsonl" FAKE_CODEX_CALLS="$PWD/logs/${ARM}_fake_calls.jsonl"
    # shellcheck disable=SC2046,SC2086
    life "$ARM" "$T" "$STEPS" --cli codex --model fake-codex --effort high \
        -- $(task_extra "$T") $GRANT
    tell "$ARM"
    echo "finished=$(date -Is)"; exit 0
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
        life "$ARM" "$TASK" "$PROBE_STEPS" --cli claude --model "$MODEL" --effort high \
            $X $(task_extra "$TASK") $LIVE_OPT
        tell "$ARM"
    done
done
echo "finished=$(date -Is)"
