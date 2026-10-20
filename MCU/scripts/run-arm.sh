#!/usr/bin/env bash
# Run one life of one arm end to end: the green agent (the Minecraft environment and its
# scorer), the purple agent (the arm under test), and the evaluation client.
#
#   scripts/run-arm.sh --arm mfm_diamond_s0 --memory mfm --task mine_diamond_from_scratch \
#                      --world-seed 0 --green-port 9053 --purple-port 9063
#
# Arms are independent by construction -- own ports, own output directory, own model-CLI
# home -- so several can run at once as long as their names and ports differ. Nothing
# here matches processes by name, and a busy port is reported rather than cleared. The
# only processes this script stops are the two servers it started, by their own pids,
# when it exits.
#
# Options
#   --arm NAME          names output/NAME, logs/NAME_* and the model-CLI home. Required,
#                       and given first (scripts/stop_arm.py finds the run by it).
#   --memory ARM        direct | mfm | mfm-noprim. Required.
#                         direct      no persistent memory: each turn is the present
#                         mfm         Multimodal Filesystem Memory; the agent writes its
#                                     own procedures and reflexes
#                         mfm-noprim  mfm without the 28 atoms: the agent builds every
#                                     skill from raw actions
#                       The settings of each arm: mcu_worldmodel/arms.py
#   --task NAME         mine_diamond_from_scratch (default) | ender_dragon | nether_portal
#   --steps N           the step budget. Default by task: 12000 (diamond), 36000
#                       (dragon), 6000 (portal) -- the paper's budgets.
#   --world-seed N      the Minecraft world seed (MCU_WORLD_SEED). Default: the task
#                       config's `world_seed` (0 for the diamond and the dragon, 42
#                       for the portal), else the simulator's own.
#   --green-port N      A2A port of the green agent. Required.
#   --purple-port N     A2A port of the purple agent. Required.
#   --cli NAME          codex (default) | claude: the CLI that carries the model.
#   --model ID          default gpt-6-astra (codex) or claude-opus-5 (claude).
#   --effort LEVEL      reasoning effort, default high.
#   --route NAME        account (default): the CLI's own login.
#                       openrouter: a key file named by MCU_OPENROUTER_ENV holding
#                       OPENROUTER_API_KEY=...; the key is read by the CLI through a
#                       command and is never in any process environment.
#   --seed-memory DIR   mfm: the memory dir of an earlier life in the same world
#                       (output/<arm>/episode_001/memory), carried under previous/.
#                       Repeatable, oldest first.
#   --overwrite         replace output/NAME if it exists (refused otherwise).
#   --dry-run           print the settings and the purple agent's command, and exit.
#   -h, --help          print this help.
#
# Fixed settings: one model session for the life (mfm; compacted by the CLI) or one turn
# per session (direct); 600 s per observation; at most 4000 model calls per life.
#
# Environment
#   MCU_PYTHON          the interpreter, default .venv/bin/python
#   MCU_SKIP_ENV_SH=1   do not source ./env.sh (JAVA_HOME and MINESTUDIO_DIR are then
#                       the caller's to export)
#   MCU_DISPLAY_NUM     a fixed X display number instead of `xvfb-run -a`; set it when
#                       several arms start together on one node
#   MCU_CLAUDE_OAUTH_TOKEN  --cli claude: a token from `claude setup-token`. Without it,
#                       the login in MCU_CLAUDE_EVAL_DIR (a directory holding its
#                       .credentials.json, default ~/.claude-eval; scripts/claude-home.sh)
#   MCU_CODEX_AUTH      the auth.json of `codex login`, default ~/.codex/auth.json
#   CODEX_BIN, MCU_CLAUDE_BIN   the CLI binaries, default `codex` and `claude` on PATH
#   CODEX_MAX_CALLS     ceiling on model calls per life, default 4000. Not a scored
#                       knob: a run that touches it reports call_ceiling_hits > 0 and
#                       is not a result.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

ARM="" MEMORY="" TASK="mine_diamond_from_scratch" GREEN_PORT="" PURPLE_PORT=""
STEPS="" STEP_TIMEOUT=600 DRY=0 OVERWRITE=0 WORLD_SEED=""
CLI="codex" MODEL_ID="" EFFORT="high" ROUTE="account"
SEEDS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --arm) ARM="$2"; shift 2;;
        --memory) MEMORY="$2"; shift 2;;
        --task) TASK="$2"; shift 2;;
        --steps) STEPS="$2"; shift 2;;
        --world-seed) WORLD_SEED="$2"; shift 2;;
        --green-port) GREEN_PORT="$2"; shift 2;;
        --purple-port) PURPLE_PORT="$2"; shift 2;;
        --cli) CLI="$2"; shift 2;;
        --model) MODEL_ID="$2"; shift 2;;
        --effort) EFFORT="$2"; shift 2;;
        --route) ROUTE="$2"; shift 2;;
        --seed-memory) SEEDS+=(--seed-memory "$2"); shift 2;;
        --overwrite) OVERWRITE=1; shift;;
        --dry-run) DRY=1; shift;;
        -h|--help) sed -n '2,/^set -euo pipefail/{/^set -euo/d;s/^# \{0,1\}//;p;}' \
                       "$ROOT/scripts/run-arm.sh"; exit 0;;
        *) echo "unknown option: $1" >&2; exit 2;;
    esac
done
: "${ARM:?--arm is required}" "${MEMORY:?--memory is required}"
: "${GREEN_PORT:?--green-port is required}" "${PURPLE_PORT:?--purple-port is required}"
case "$MEMORY" in direct|mfm|mfm-noprim) ;;
    *) echo "unknown --memory: $MEMORY (direct|mfm|mfm-noprim)" >&2; exit 2;; esac
case "$CLI" in codex|claude) ;; *) echo "unknown --cli: $CLI (codex|claude)" >&2; exit 2;; esac
case "$ROUTE" in account|openrouter) ;;
    *) echo "unknown --route: $ROUTE (account|openrouter)" >&2; exit 2;; esac

if [ -z "$STEPS" ]; then
    case "$TASK" in
        ender_dragon) STEPS=36000;;
        nether_portal) STEPS=6000;;
        *) STEPS=12000;;
    esac
fi
if [ "$MEMORY" = direct ]; then SESSION_TURNS=1; else SESSION_TURNS=0; fi
if [ -z "$MODEL_ID" ]; then
    if [ "$CLI" = claude ]; then MODEL_ID=claude-opus-5; else MODEL_ID=gpt-6-astra; fi
fi

# One session for the life is compacted by the CLI when its window fills; a session
# dropped after N turns never gets there, and the limit is put above any window so that
# an overflow cold-starts instead.
if [ "$SESSION_TURNS" -eq 0 ]; then COMPACT_LIMIT=100000; else COMPACT_LIMIT=1048576; fi

PYTHON="${MCU_PYTHON:-.venv/bin/python}"
RUN_DIR="$ROOT/output/$ARM"
LOG_DIR="$ROOT/logs"
CFG="$LOG_DIR/$ARM.toml"

MODEL_ARGS=(--model "$MODEL_ID" --reasoning-effort "$EFFORT")
if [ "$ROUTE" = openrouter ]; then
    KEYFILE="${MCU_OPENROUTER_ENV:?--route openrouter needs MCU_OPENROUTER_ENV=<file with OPENROUTER_API_KEY=...>}"
    [ -r "$KEYFILE" ] || { echo "no readable key file at $KEYFILE" >&2; exit 1; }
    if [ "$CLI" = claude ]; then
        export MCU_CLAUDE_ACCOUNT=openrouter
        export MCU_CLAUDE_BIN="${MCU_CLAUDE_BIN:-$ROOT/scripts/claude-openrouter.sh}"
        MODEL_ARGS=(--model "anthropic/$MODEL_ID" --reasoning-effort "$EFFORT"
                    --base-url https://openrouter.ai/api)
    else
        export CODEX_BIN="${CODEX_BIN:-$ROOT/scripts/codex-openrouter.sh}" MCU_CODEX_AUTH=none
        export CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
        # codex has no catalog entry for a model served by another provider
        export CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-1050000}"
        MODEL_ARGS=(--model "openai/$MODEL_ID" --reasoning-effort "$EFFORT"
                    --base-url https://openrouter.ai/api/v1)
    fi
fi

# What the purple agent is started with (beside --host, --port and the per-arm
# --codex-home made below).
PURPLE_ARGS=(--memory "$MEMORY" --task "$TASK" --max-steps "$STEPS" --workspace "output/$ARM"
             --cli "$CLI" "${MODEL_ARGS[@]}" ${SEEDS[@]+"${SEEDS[@]}"})

echo "arm=$ARM memory=$MEMORY task=$TASK steps=$STEPS world_seed=${WORLD_SEED:-task default}"
echo "  model        $MODEL_ID effort=$EFFORT cli=$CLI route=$ROUTE"
echo "  ports        green=$GREEN_PORT purple=$PURPLE_PORT"
echo "  output       $RUN_DIR"
echo "  sessions     $([ "$SESSION_TURNS" -eq 0 ] && echo 'one for the life, compacted by the CLI' \
    || echo "dropped after $SESSION_TURNS turn(s)")"
[ ${#SEEDS[@]} -eq 0 ] || echo "  carried      ${SEEDS[*]}"
echo "  green        task_category=$TASK max_steps=$STEPS step_timeout=$STEP_TIMEOUT"
echo "  purple       worldmodel_purple_agent.py ${PURPLE_ARGS[*]}"
[ "$DRY" -eq 1 ] && exit 0

if [ -e "$RUN_DIR" ]; then
    [ "$OVERWRITE" -eq 1 ] || { echo "$RUN_DIR exists -- another --arm name, or --overwrite" >&2; exit 1; }
    rm -rf "$RUN_DIR"
fi
for port in "$GREEN_PORT" "$PURPLE_PORT"; do
    if (echo >"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        echo "port $port is already in use -- pick another rather than clearing it" >&2
        exit 1
    fi
done
mkdir -p "$LOG_DIR"

# JDK 8, Xvfb and MINESTUDIO_DIR.
[ "${MCU_SKIP_ENV_SH:-0}" = 1 ] || source ./env.sh
[ -z "$WORLD_SEED" ] || export MCU_WORLD_SEED="$WORLD_SEED"
# The harness talks to its own servers on 127.0.0.1; a proxy in the launching shell
# must not sit between them.
export no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"

# A home of its own for the model CLI: no thread store, credential refresh or personal
# instruction file is shared between arms (scripts/codex-home.sh, claude-home.sh).
if [ "$CLI" = claude ]; then
    eval "$(scripts/claude-home.sh "$ARM")"
    RUNTIME_HOME="$CLAUDE_RUNTIME_HOME"
    # Empty disables auto-compaction (an overflow cold-starts); a token count is the
    # window compaction fires at.
    export CLAUDE_AUTOCOMPACT="$([ "$SESSION_TURNS" -eq 0 ] && echo "$COMPACT_LIMIT" || echo "")"
    export CLAUDE_SESSION_MAX_TURNS="$SESSION_TURNS"
    export CLAUDE_MAX_CALLS="${CLAUDE_MAX_CALLS:-${CODEX_MAX_CALLS:-4000}}"
    export CLAUDE_TIMEOUT="${CLAUDE_TIMEOUT:-1800}"
else
    eval "$(scripts/codex-home.sh "$ARM")"
    RUNTIME_HOME="$CODEX_RUNTIME_HOME"
fi
export CODEX_AUTO_COMPACT_TOKEN_LIMIT="$COMPACT_LIMIT"
export CODEX_SESSION_MAX_TURNS="$SESSION_TURNS"
export CODEX_MAX_CALLS="${CODEX_MAX_CALLS:-4000}"
export CODEX_BIN="${CODEX_BIN:-codex}"
# The `mfm` package is the repository root this directory sits in.
export PYTHONPATH="${MFM_ROOT:-$ROOT/..}${PYTHONPATH:+:$PYTHONPATH}"

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

# The two servers are stopped when this script exits -- by the pids recorded here.
# SIGTERM to each tree (xvfb-run, Xvfb, the python server, its Minecraft java; the
# purple agent and a model turn still in flight), SIGKILL what is alive after 30 s.
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

# Minecraft and pyglet want an X display at python import time, so the green agent is
# wrapped; the purple agent never touches the display. `xvfb-run -a` scans for a free
# display and races when two arms start together: MCU_DISPLAY_NUM pins the number.
XVFB=(-a)
[ -n "${MCU_DISPLAY_NUM:-}" ] && XVFB=(--server-num="$MCU_DISPLAY_NUM" -s "-screen 0 1024x768x24")

xvfb-run "${XVFB[@]}" "$PYTHON" -u src/server.py --host 127.0.0.1 --port "$GREEN_PORT" \
    > "$LOG_DIR/${ARM}_green.log" 2>&1 &
GREEN_PID=$!

"$PYTHON" -u worldmodel_purple_agent.py --host 127.0.0.1 --port "$PURPLE_PORT" \
    --codex-home "$RUNTIME_HOME" "${PURPLE_ARGS[@]}" \
    > "$LOG_DIR/${ARM}_purple.log" 2>&1 &
PURPLE_PID=$!

# The green server imports gym, minestudio and the a2a stack; on a cold page cache that
# alone has taken over five minutes. 180 x 10 s (MCU_SERVER_WAIT_TRIES) before the launch
# is abandoned; the wait is before the first observation and cannot touch a score.
echo "waiting for both servers..."
"$PYTHON" - "$GREEN_PORT" "$PURPLE_PORT" <<'PYEOF' || { echo "a server did not come up -- abort"; exit 1; }
import os, sys, time, json, urllib.request
tries = int(os.environ.get("MCU_SERVER_WAIT_TRIES", "180"))
for port in sys.argv[1:]:
    t0 = time.time()
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/.well-known/agent-card.json", timeout=5) as r:
                print(f"  port {port} up -> {json.load(r)['name']} "
                      f"({time.time() - t0:.0f}s)", flush=True); break
        except Exception:
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

"$PYTHON" -u test_evaluation.py "$CFG" "$LOG_DIR/${ARM}_result.json" \
    > "$LOG_DIR/${ARM}_client.log" 2>&1
echo "$ARM finished -- $LOG_DIR/${ARM}_result.json"
