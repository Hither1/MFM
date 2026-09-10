#!/usr/bin/env bash
# One-screen status of a gen-4 arm, for the hourly monitoring checkpoints.
#   bash status_g4.sh <MCU dir> <arm>
# Reads only: logs/<arm>_*.log|pid, output/<arm>/episode_001/{codex_turns,memory/logs.txt}.
set -u
MCU=${1:?MCU dir}; ARM=${2:?arm}
EP="$MCU/output/$ARM/episode_001"; LOGS="$MCU/logs"; PL="$LOGS/${ARM}_purple.log"
echo "== $ARM @ $(date '+%F %T')"
for f in launch wall; do
  pid=$(cat "$LOGS/${ARM}_$f.pid" 2>/dev/null)
  if [ -n "${pid:-}" ] && ps -p "$pid" >/dev/null 2>&1; then
    echo "$f pid $pid alive, elapsed $(ps -o etime= -p "$pid" | tr -d ' ')"
  else echo "$f pid ${pid:-?} DEAD"; fi
done
echo "-- progress"
grep -oE "step [0-9]+: Environment-verified progress: [0-9]+/24" "$PL" | tail -1
grep -oE "\[milestone\] [a-z_]+ at step [0-9]+ \([0-9]+/24\)" "$PL" | sed 's/\[milestone\] //' | tr '\n' ';' ; echo
echo "-- deaths / lives"
grep -iE "died|death|respawn|new life|life [0-9]" "$PL" | grep -v "previous life" | tail -3 | cut -c1-200
grep -cE "YOU DIED" "$EP/memory/logs.txt" 2>/dev/null | sed 's/^/logs.txt YOU DIED notes (a portal trip taken with raw moves counts too -- check health): /'
echo "-- turns"
NT=$(ls "$EP/codex_turns"/turn_*.events.jsonl 2>/dev/null | wc -l)
STEP=$(grep -oE "^Action [0-9]+ \| Step [0-9]+" "$EP/memory/logs.txt" | tail -1 | grep -oE "[0-9]+$")
echo "turns=$NT last_step=${STEP:-?} steps/turn=$(( ${STEP:-0} / (NT>0?NT:1) ))"
grep -E "\[codex\] turn [0-9]+" "$PL" | tail -1 | cut -c1-120
echo "-- vitals (turn: health food) last 8"
for p in $(ls "$EP/codex_turns"/turn_*.prompt.txt 2>/dev/null | tail -8); do
  t=$(basename "$p" .prompt.txt | sed 's/turn_0*//'); v=$(grep -oE "health=[0-9./]+ food=[0-9./]+" "$p" | head -1)
  printf "%s:%s  " "$t" "$v"
done; echo
echo "-- reflex fires"
grep -oE "\[REFLEX [a-z_]+\]" "$EP/memory/logs.txt" | sort | uniq -c | tr '\n' ';'; echo
grep -E "\[REFLEX" "$EP/memory/logs.txt" | tail -3 | cut -c1-200
echo "-- looks (view_image / then-now / zoom) per turn"
for e in "$EP/codex_turns"/turn_*.events.jsonl; do
  n=$(grep -cE "view_image|then-now|zoom\.py" "$e"); [ "$n" -gt 0 ] && printf "%s:%s " "$(basename "$e" .events.jsonl | sed 's/turn_0*//')" "$n"
done; echo
grep -hoE "episodes\.py --then-now[^\"\\\\]{0,120}" "$EP"/codex_turns/turn_*.events.jsonl | tail -3
echo "-- view_image calls (codex rollout; the --json events never show them)"
RO=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes/$ARM/sessions
python3 - "$RO" <<'PY'
import json,sys,glob,os
n=0; last=[]
for f in sorted(glob.glob(os.path.join(sys.argv[1],"*/*/*/rollout-*.jsonl"))):
    for l in open(f):
        try: e=json.loads(l)
        except: continue
        p=e.get("payload",{})
        if p.get("type")=="function_call" and "view_image" in p.get("name",""):
            n+=1
            try: path=json.loads(p.get("arguments","{}")).get("path","")
            except Exception: path=p.get("arguments","")
            last.append((e.get("timestamp","")[11:19]+"Z", path.split("/memory/")[-1]))
print("total view_image calls:",n)
for t,pa in last[-6:]: print(" ",t,pa)
PY
echo "-- last plan"
grep -E "^\[PLAN\]" "$EP/memory/logs.txt" | tail -1 | cut -c1-240
echo "-- thread usage + compactions (codex rollout token_count / compacted records)"
python3 - "$RO" <<'PY'
import json,sys,glob,os
tot=None; n=0; ctx=None; last=[]
for f in sorted(glob.glob(os.path.join(sys.argv[1],"*/*/*/rollout-*.jsonl"))):
    for l in open(f):
        try: e=json.loads(l)
        except: continue
        t=e.get("type"); p=e.get("payload",{})
        if t=="compacted": n+=1; last.append((e.get("timestamp","")[11:19]+"Z", ctx))
        if t=="event_msg" and p.get("type")=="token_count" and p.get("info"):
            i=p["info"]; tot=i.get("total_token_usage"); li=i["last_token_usage"].get("input_tokens")
            if li: ctx=li
print("total input=%s cached=%s output=%s (thread-cumulative, NOT the sum of turn.completed usages, which are cumulative too)" % ((tot or {}).get("input_tokens"),(tot or {}).get("cached_input_tokens"),(tot or {}).get("output_tokens")))
print("context now=%s  compactions=%d (limit 100000; the --json-based report counter always says 0)" % (ctx,n))
for x in last[-3:]: print("  compacted at",x[0],"ctx before",x[1])
PY
echo "-- errors in purple (non agent-card)"
grep -iE "traceback|error" "$PL" | grep -v agent-card | wc -l
grep -iE "traceback|error" "$PL" | grep -v agent-card | tail -2 | cut -c1-200
