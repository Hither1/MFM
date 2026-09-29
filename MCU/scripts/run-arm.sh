#!/usr/bin/env bash
# Run one experiment arm end to end: green server, purple agent, evaluation client.
#
#   scripts/run-arm.sh --arm dm2_wm --agent worldmodel --task mine_diamond_from_scratch \
#                      --green-port 9053 --purple-port 9063
#
# Arms are independent by construction -- own ports, own output directory, own codex
# home -- so several can run at once as long as their ports differ. Nothing here matches
# processes by name: a `pkill` in a launcher has taken out four running arms on this
# project before, and every port is checked as free rather than cleared. The only
# processes this script ever stops are the two servers it started itself, by their own
# PIDs, when it exits (result written or launch aborted): a finished dragon arm used to
# leave a green server holding 5-8 GB of frames and 64 threads plus a purple agent with
# 66 threads, and ~50 such leftovers exhausted the user's pids cgroup.
#
# Options:
#   --arm NAME          output/NAME and the codex home name. Required.
#   --agent KIND        worldmodel | wmlite | logbook | direct | prolong | mfm | vista | steve1.
#                       vista = VISTA's protocol on the chassis (mcu_worldmodel/vista.py):
#                       one codex app-server thread calling `play` one entry at a time,
#                       no filesystem the model reads, the frame archive behind `inspect`,
#                       GUIDE.md/WORKING.md, a checkpoint handoff when the context (or
#                       the wire, --vista-thread-bytes via --wm-extra) fills.
#                       mfm = the logbook arm + the episode store (PLAN_episodic_memory.md);
#                       `--wm-extra --retrieval` adds the harness-computed [RECALL]
#                       block to its turn prompt (the lad3 variant);
#                       `--wm-extra "--retrieval --refuse"` also vetoes plans from
#                       the record (streaks anywhere; descending away from the table).
#                       Required.
#                       `wmlite` is the simplification arm: the logbook substrate plus
#                       ONE induction-maintained world_model/world.md -- no belief
#                       graph, no five-document taxonomy, no events channel.
#                       `logbook` is the claim-M control: the worldmodel chassis
#                       (same skills, perception, caps, knowledge) with PRO-LONG's
#                       memory protocol -- append-only logs.txt + grep and NOTHING
#                       else (no frame archive, no tools, files of its own swept at
#                       turn end), no compiled documents, no belief graph, no induction.
#                       `direct` is the ladder's no-memory rung: the same chassis with
#                       NO memory at all -- read-only codex, 1-turn sessions, no
#                       window, no feedback from the last batch: each turn is the
#                       present (the memory arms' state block) plus the current view.
#                       `prolong` remains the vanilla upstream implementation, kept as
#                       a reference arm.
#   --task NAME         task_category for the evaluation. Default mine_diamond_from_scratch.
#   --green-port N      A2A port for the green agent (the environment). Required.
#   --purple-port N     A2A port for the agent under test. Required.
#   --steps N           max_steps. Default 12000 -- the benchmark's own long-task
#                       budget, and the frozen protocol's. The dm4 dev campaign ran
#                       6000 to iterate faster and was cutting the worldmodel arms
#                       mid-climb (4th-6th milestone landing at steps 3467-4760, and
#                       at 12000 ked_final1 banked #4-#6 at 4949-7884) while both
#                       prolong runs had plateaued (dm4_pl: nothing after 3883;
#                       dm4_plk1: 5451 steps stuck on one milestone).
#   --step-timeout SEC  seconds a purple agent may take per observation. Default 600 --
#                       a planning agent spends a whole model turn on a re-plan, and the
#                       60 s default fills those steps with noops.
#   --session-turns N   turns one codex session is resumed for before it is dropped and
#                       the next call cold-starts. Default 1. 0 means unbounded, which
#                       does not work here -- see below.
#   --compact           let codex compact a full conversation instead of cold-starting
#                       it. Only does anything with --session-turns greater than 1.
#   --seed-memory DIR   a previous run's episode memory dir. worldmodel/wmlite copy its
#                       distilled documents in; the mfm arm carries its RECORD under
#                       previous/ and pushes the sites its log verified into the turn
#                       prompt (mcu_worldmodel/previous.py). Repeatable, oldest first.
#   --dry-run           print the plan and exit.
#
# Why sessions default to one turn. Every act turn attaches the current frame, because
# the observation in this benchmark is pixels. On a resumed session the old frames stay
# in the thread and codex re-sends the whole conversation on every call, so the request
# grows by ~0.4 MB a turn without bound. Measured on three independent arms (2026-08-25):
# below ~5 MB a turn costs 42s + 11.2s per MB; between 5.15 and 6.15 MB it steps to a
# flat ~600s and stays there however much further it grows. All three arms crossed it at
# turn 11-18 and effectively stopped, ~1 step per 10 minutes.
#
# A 12,000-step episode needs 1,500-2,000 turns (5.6-7.6 steps per turn, measured), so
# nothing that grows per turn survives the horizon: at one turn per session the payload
# is a constant 0.48 MB and the wall is unreachable. The previous campaign ran this way
# for 1,878 consecutive sessions with no latency drift (53-71s median throughout), so
# session accumulation costs nothing but disk -- about 513 KB per session.
#
# What it gives up is conversation memory, and both agents are built to survive that:
# `_discard_session` drops a thread on any unclean ending precisely because logs.txt, the
# world model documents and the hypothesis graph are on the filesystem. Raising this is
# how you measure what the conversation was worth on top of that; it is not free above
# ~5 turns, and above ~12 it hits the wall.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

ARM="" AGENT="" TASK="mine_diamond_from_scratch" GREEN_PORT="" PURPLE_PORT=""
STEPS=12000 STEP_TIMEOUT=600 COMPACT=0 SESSION_TURNS=1 DRY=0 WM_EXTRA="" SEEDS="" CLI="codex"
while [ $# -gt 0 ]; do
    case "$1" in
        --arm) ARM="$2"; shift 2;;
        --cli) CLI="$2"; shift 2;;
        --agent) AGENT="$2"; shift 2;;
        --task) TASK="$2"; shift 2;;
        --green-port) GREEN_PORT="$2"; shift 2;;
        --purple-port) PURPLE_PORT="$2"; shift 2;;
        --steps) STEPS="$2"; shift 2;;
        --wm-extra) WM_EXTRA="$2"; shift 2;;
        --step-timeout) STEP_TIMEOUT="$2"; shift 2;;
        --compact) COMPACT=1; shift;;
        --session-turns) SESSION_TURNS="$2"; shift 2;;
        --seed-memory) SEEDS="$SEEDS --seed-memory $2"; shift 2;;
        --seed-log) SEEDS="$SEEDS --seed-log $2"; shift 2;;
        --dry-run) DRY=1; shift;;
        *) echo "unknown option: $1" >&2; exit 2;;
    esac
done
: "${ARM:?--arm is required}" "${AGENT:?--agent is required}"
: "${GREEN_PORT:?--green-port is required}" "${PURPLE_PORT:?--purple-port is required}"
case "$CLI" in codex|claude) ;; *) echo "unknown --cli: $CLI (codex|claude)" >&2; exit 2;; esac

# Above any plausible context window, so auto-compaction can never fire and a full
# conversation cold-starts. Below it, compaction fires first and the thread survives
# summarised. Both arms of a comparison must set this: leaving it unset hands the
# choice to whatever codex defaults to, which is neither measured nor guaranteed equal.
COMPACT_LIMIT=1048576
[ "$COMPACT" -eq 1 ] && COMPACT_LIMIT=100000

RUN_DIR="$ROOT/output/$ARM"
LOG_DIR="$ROOT/logs"
CFG="$LOG_DIR/$ARM.toml"
mkdir -p "$LOG_DIR"

echo "arm=$ARM agent=$AGENT task=$TASK steps=$STEPS cli=$CLI"
echo "  ports        green=$GREEN_PORT purple=$PURPLE_PORT"
echo "  output       $RUN_DIR"
if [ -n "$SEEDS" ]; then echo "  seeds       $SEEDS"; fi
echo "  overflow     $([ "$COMPACT" -eq 1 ] && echo 'compact and carry on' || echo 'cold start')"
echo "  sessions     $([ "$SESSION_TURNS" -eq 0 ] \
    && echo 'resumed without limit -- crosses the payload wall around turn 12' \
    || echo "dropped after $SESSION_TURNS turn(s)")"
[ "$DRY" -eq 1 ] && exit 0

for port in "$GREEN_PORT" "$PURPLE_PORT"; do
    if (echo >"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        echo "port $port is already in use -- pick another rather than clearing it" >&2
        exit 1
    fi
done

# JDK8, Xvfb and MINESTUDIO_DIR. Sourced here so a caller cannot forget it.
#
# MCU_SKIP_ENV_SH=1 for a host env.sh does not describe. It targets a rootless box with
# a user-local JDK and Xvfb under $MCU_PREFIX; on the FASRC cluster that prefix does not
# exist, system java is already 1.8, and the engine comes from netscratch through
# mcu_worldmodel/setup_env.sh. Sourcing it there sets JAVA_HOME to a missing directory
# and fails copying an engine that is not on this disk. A caller that sets this must
# export JAVA_HOME and MINESTUDIO_DIR itself -- see slurm/arm.sbatch.
[ "${MCU_SKIP_ENV_SH:-0}" = 1 ] || source ./env.sh
if [ "$CLI" = "claude" ]; then
    # The claude twin of codex-home.sh: a per-arm CLAUDE_CONFIG_DIR, the credential
    # route (subscription file, setup-token, or the OpenRouter key helper), and the
    # deny-read list the backend turns into sandbox + Read-tool rules.
    eval "$(scripts/claude-home.sh "$ARM")"
    RUNTIME_HOME="$CLAUDE_RUNTIME_HOME"
    # CODEX_AUTO_COMPACT_TOKEN_LIMIT's twin, inverted to fit the CLI: empty disables
    # auto-compaction outright (overflow cold-starts), a token count is the window
    # compaction fires at (--compact -> 100000, the same number as codex's).
    export CLAUDE_AUTOCOMPACT="$([ "$COMPACT" -eq 1 ] && echo "$COMPACT_LIMIT" || echo "")"
    export CLAUDE_SESSION_MAX_TURNS="$SESSION_TURNS"
    export CLAUDE_MAX_CALLS="${CLAUDE_MAX_CALLS:-4000}"
    export CLAUDE_TIMEOUT="${CLAUDE_TIMEOUT:-${CODEX_TIMEOUT:-1800}}"
else
    eval "$(scripts/codex-home.sh "$ARM")"
    RUNTIME_HOME="$CODEX_RUNTIME_HOME"
fi
export CODEX_AUTO_COMPACT_TOKEN_LIMIT="$COMPACT_LIMIT"
# 0 is codex's own "unbounded"; every other value is a turn cap it enforces itself.
# Also passed to every purple agent as --session-turns: the agents no longer read
# this variable, it stays exported for anything else in the tree that does.
export CODEX_SESSION_MAX_TURNS="$SESSION_TURNS"
# Runaway ceiling on total model calls per episode -- infrastructure, NOT a scored
# protocol knob. The episode's scored budget is max_steps (env ticks) -- the same
# quantity upstream PRO-LONG's arc-agi-3 harness calls --max-actions (500/game,
# one action = one env step there; research/arc-agi-3/README.md).
# Decision count stays a *measured outcome* both arms report; this ceiling only
# bounds the degenerate case (a retry storm is analyzer_retries x steps = 60k calls
# worst case). Healthy usage at 12,000 steps: ~2,200 calls (prolong), ~130 (wm) --
# 4,000 is ~2x the highest healthy arm, and a run that touches it reports
# call_ceiling_hits > 0 and is not a result.
export CODEX_MAX_CALLS="${CODEX_MAX_CALLS:-4000}"
# The codex binary: the API-key account's wrapper (~/ccr/bin/codex, 2026-09-06), not
# whatever `codex` is first on PATH (the ChatGPT-plan wrapper under ~/.local/bin).
# The credential is chosen by codex-home.sh; this picks the wrapper and its home.
export CODEX_BIN="${CODEX_BIN:-$HOME/ccr/bin/codex}"
# The mfm arm imports the `mfm` package from the MFM checkout this repo is the
# submodule of; the run venv does not carry it.
export PYTHONPATH="${MFM_ROOT:-$ROOT/..}${PYTHONPATH:+:$PYTHONPATH}"

rm -rf "$RUN_DIR"
cat > "$CFG" <<TOML
[green_agent]
endpoint = "http://127.0.0.1:$GREEN_PORT"
[[participants]]
role = "agent"
endpoint = "http://127.0.0.1:$PURPLE_PORT"
[config]
task_category = "$TASK"
max_steps = $STEPS
step_timeout = $STEP_TIMEOUT
TOML

# The two servers below are stopped again when this script exits -- by the PIDs it
# recorded, never by name. SIGTERM to the whole tree (xvfb-run, Xvfb, the python server,
# its Minecraft java; the purple agent and any codex turn still in flight), then
# SIGKILL whatever is still alive after 30 s. `descendants` walks /proc via pgrep -P.
GREEN_PID=""; PURPLE_PID=""
descendants() { local p; for p in $(pgrep -P "$1"); do descendants "$p"; echo "$p"; done; }
stop_tree() {
    local root="$1" pids i
    [ -n "$root" ] || return 0
    pids="$(descendants "$root") $root"
    kill -TERM $pids 2>/dev/null
    for i in $(seq 30); do sleep 1; kill -0 $pids 2>/dev/null || return 0; done
    kill -KILL $pids 2>/dev/null
}
trap 'stop_tree "$PURPLE_PID"; stop_tree "$GREEN_PID"' EXIT

# Minecraft and pyglet want an X display at python *import* time, so the green agent is
# wrapped. The purple agents never touch the display and are not.
# A display number from the job id rather than `xvfb-run -a`. `-a` scans for a free
# display and races: two jobs starting together on one node can pick the same number and
# share one X server, and cancelling either kills Minecraft in the other with a
# "Connection refused" that reads like an agent crash. See slurm/worldmodel.sbatch, where
# this was measured. Unset (the default) keeps the old behaviour.
XVFB=(-a)
[ -n "${MCU_DISPLAY_NUM:-}" ] && XVFB=(--server-num="$MCU_DISPLAY_NUM" -s "-screen 0 1024x768x24")

xvfb-run "${XVFB[@]}" .venv/bin/python -u src/server.py --host 127.0.0.1 --port "$GREEN_PORT" \
    > "$LOG_DIR/${ARM}_green.log" 2>&1 &
GREEN_PID=$!

case "$AGENT" in
    worldmodel)
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --session-turns "$SESSION_TURNS" $WM_EXTRA $SEEDS \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    wmlite)
        # The simplification arm: the logbook substrate plus one compiled world.md
        # kept by induction -- no belief graph, no five-document taxonomy.
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --memory wmlite \
            --session-turns "$SESSION_TURNS" $WM_EXTRA $SEEDS \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    logbook)
        # The claim-M control arm: identical chassis, PRO-LONG's memory protocol.
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --memory logbook \
            --session-turns "$SESSION_TURNS" $WM_EXTRA $SEEDS \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    direct)
        # The ladder's no-memory rung: identical chassis, no filesystem memory,
        # read-only codex, 1-turn sessions -- a rolling window of the model's own
        # replies is its only past (see --window-chars).
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --memory direct \
            --session-turns "$SESSION_TURNS" $WM_EXTRA $SEEDS \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    prolong)
        # The matched-knowledge control: the same task facts the worldmodel prompt
        # carries, in the file prolong_mc/prompts.py reads (empty env = original arm).
        # Diamond-specific text, so only that task sets it. Caps are the CLI defaults,
        # matched to the worldmodel arm's (40 entries / repeat 200 / 400 ticks).
        if [ "$TASK" = "mine_diamond_from_scratch" ]; then
            export PROLONG_EXTRA_KNOWLEDGE="$ROOT/prolong_mc/matched_knowledge_diamond.md"
        fi
        .venv/bin/python -u prolong_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" \
            --task "$TASK" --max-steps "$STEPS" --session-turns "$SESSION_TURNS" \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    mfm)
        # The MFM arm on the ladder: the logbook arm plus the episode store beside the
        # log (`episodes/`, `index.jsonl`, `tools/episodes.py`) and one paragraph of
        # the system prompt naming it. Same chassis, caps, knowledge and codex policy
        # as logbook; the diff against it is exactly the memory claim.
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --memory mfm \
            --session-turns "$SESSION_TURNS" $WM_EXTRA $SEEDS \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    vista)
        # The VISTA baseline on the ladder's chassis: same macros, perception, caps,
        # knowledge and governor as logbook/mfm; the memory protocol is VISTA's (one
        # long codex thread, tools instead of files). --session-turns is not read by
        # this arm (the thread's lifetime is the checkpoint protocol's); passed through
        # so the launcher's argv keeps one shape. codex only: the thread is codex
        # app-server (mfm/vista/runner.py); there is no claude twin of it.
        [ "$CLI" = codex ] || { echo "--agent vista runs codex app-server only (--cli $CLI)" >&2; exit 2; }
        .venv/bin/python -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" --cli "$CLI" \
            --task "$TASK" --max-steps "$STEPS" --memory vista \
            --session-turns "$SESSION_TURNS" $WM_EXTRA \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    plmfm)
        # The PRO-LONG-based MFM arm (the dmw3 wave): the prolong arm with the episode
        # store on -- same prompts, caps, knowledge file and codex policy; `episodes/`
        # and `tools/episodes.py` beside the log, and one paragraph in AGENTS.md.
        if [ "$TASK" = "mine_diamond_from_scratch" ]; then
            export PROLONG_EXTRA_KNOWLEDGE="$ROOT/prolong_mc/matched_knowledge_diamond.md"
        fi
        .venv/bin/python -u prolong_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
            --workspace "output/$ARM" --codex-home "$RUNTIME_HOME" \
            --task "$TASK" --mfm --max-steps "$STEPS" --session-turns "$SESSION_TURNS" \
            > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    steve1)
        # A neural policy, unlike the other two: it needs a GPU and no codex at all.
        xvfb-run "${XVFB[@]}" .venv/bin/python -u test_purple_agent.py --host 127.0.0.1 \
            --port "$PURPLE_PORT" --model steve1 > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
        ;;
    *) echo "unknown --agent: $AGENT (worldmodel|wmlite|logbook|mfm|vista|direct|prolong|plmfm|steve1)" >&2; exit 2;;
esac
PURPLE_PID=$!

# How long a server may take to answer its agent card before the launch is abandoned.
# 90 x 10s, not the 30 it was. The green server imports gym, minestudio and the a2a
# stack off NFS, and that import time is wildly node-dependent: measured 2026-09-04 on
# four launches of the same commit, one node bound the port in under 60 s while two
# others had printed only gym's deprecation banner when the old 300 s ceiling fired and
# killed the arm ("a server did not come up -- abort", green log 0-500 bytes). Nothing
# was wrong with those runs but a cold page cache. The ceiling exists for a server that
# is genuinely dead, which is a different timescale, so it costs a lost run to keep it
# tight and costs nothing to keep it loose. The wait happens before the first
# observation, so it cannot touch what an arm scores.
echo "waiting for both servers..."
.venv/bin/python - "$GREEN_PORT" "$PURPLE_PORT" <<'PYEOF' || { echo "a server did not come up -- abort"; exit 1; }
import os, sys, time, json, urllib.request
tries = int(os.environ.get("MCU_SERVER_WAIT_TRIES", "90"))
for port in sys.argv[1:]:
    t0 = time.time()
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/.well-known/agent-card.json", timeout=5) as r:
                print(f"  port {port} up -> {json.load(r)['name']} "
                      f"({time.time() - t0:.0f}s)", flush=True); break
        except Exception:
            # A heartbeat, so a slow import is visibly a slow import rather than a
            # silent five minutes followed by an abort.
            if attempt and attempt % 6 == 0:
                print(f"  port {port} still starting ({time.time() - t0:.0f}s)", flush=True)
            time.sleep(10)
    else:
        print(f"  port {port} DOWN after {time.time() - t0:.0f}s"); sys.exit(1)
PYEOF

# A server that lost its bind still answers on the old process, so the card check above
# passes while the run writes into someone else's episode.
if grep -q "address already in use" "$LOG_DIR/${ARM}_green.log" "$LOG_DIR/${ARM}_purple.log" 2>/dev/null; then
    echo "a server reported 'address already in use' -- abort" >&2
    exit 1
fi

.venv/bin/python -u test_evaluation.py "$CFG" "$LOG_DIR/${ARM}_result.json" \
    > "$LOG_DIR/${ARM}_client.log" 2>&1
echo "$ARM finished -- $LOG_DIR/${ARM}_result.json"
