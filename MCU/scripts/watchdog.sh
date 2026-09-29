#!/usr/bin/env bash
# Resource watchdog for running arms: one line a minute into logs/watchdog.log.
# Observation only -- it never kills anything. A pkill from tooling has taken out
# four running arms on this project before (see run-arm.sh's header); if a threshold
# trips, the ALERT line is the signal and a human (or the session driving the run)
# decides what dies. Exits on its own after 30 consecutive minutes with no arm
# processes, so it does not outlive the campaign it was started for.
#
#   scripts/watchdog.sh &        # from the repo root
set -u
cd "$(dirname "$0")/.."
LOG="logs/watchdog.log"
# 2026-08-29: an instance died after ~90 min with no exit path of its own -- external
# signal on this shared box. Log what arrives instead of dying silently; HUP is the
# one worth surviving (a controlling-terminal drop is not a reason to stop watching).
trap 'echo "$(date -Is) watchdog: SIGHUP ignored" >> "$LOG"' HUP
trap 'echo "$(date -Is) watchdog: SIGTERM, exiting" >> "$LOG"; exit 0' TERM
trap 'echo "$(date -Is) watchdog: SIGINT, exiting" >> "$LOG"; exit 0' INT
IDLE=0
while :; do
    ts=$(date -Is)
    mem_avail=$(awk '/MemAvailable/{printf "%.0fG", $2/1048576}' /proc/meminfo)
    load=$(awk '{print $1}' /proc/loadavg)
    # Bounded: a df/du against the shared pool can block indefinitely in an I/O
    # storm -- one hung here for 2.5 hours on 2026-08-29 (last line load=214).
    root_avail=$(timeout 10 df -BG --output=avail / 2>/dev/null | tail -1 | tr -dc '0-9')
    pool_avail=$(timeout 10 df -BG --output=avail /datapool 2>/dev/null | tail -1 | tr -dc '0-9')
    # Everything belonging to the arms: servers, purple agents, eval clients, the
    # simulator's java, xvfb, and codex runs against the per-arm homes.
    pids=$(pgrep -u "$(id -un)" -f 'MCU-AgentBeats|MineStudio-ruihan|mcu-codex|mcu-record-ab' || true)
    ours=0; rss_kb=0; java=0
    for p in $pids; do
        [ -d "/proc/$p" ] || continue
        ours=$((ours+1))
        rss_kb=$((rss_kb + $(awk '/VmRSS/{print $2}' "/proc/$p/status" 2>/dev/null || echo 0)))
        [ "$(cat "/proc/$p/comm" 2>/dev/null)" = java ] && java=$((java+1))
    done
    rss=$(awk -v k="$rss_kb" 'BEGIN{printf "%.1fG", k/1048576}')
    out_sz=$(timeout 20 du -s output 2>/dev/null | awk '{printf "%.0fM", $1/1024}')
    codex_sz=$(timeout 20 du -s /var/tmp/mcu-codex-"$(id -un)" 2>/dev/null | awk '{printf "%.0fM", $1/1024}')
    line="$ts mem_avail=$mem_avail root_avail=${root_avail}G pool_avail=${pool_avail}G load=$load ours=$ours java=$java rss=$rss output=$out_sz codex=$codex_sz"
    alerts=""
    [ "${mem_avail%G}" -lt 100 ] 2>/dev/null && alerts="$alerts MEM_LOW"
    [ "${root_avail:-99}" -lt 8 ] && alerts="$alerts ROOTDISK_LOW"
    [ "${rss_kb}" -gt $((200*1048576)) ] && alerts="$alerts RSS_HIGH"
    [ "$java" -gt 14 ] && alerts="$alerts JAVA_COUNT"
    awk -v l="$load" 'BEGIN{exit !(l>200)}' && alerts="$alerts LOAD_HIGH"
    [ -n "$alerts" ] && line="$line ALERT:$alerts"
    echo "$line" >> "$LOG"
    if [ "$ours" -eq 0 ]; then IDLE=$((IDLE+1)); else IDLE=0; fi
    [ "$IDLE" -ge 30 ] && { echo "$(date -Is) watchdog exiting: no arm processes for 30 min" >> "$LOG"; exit 0; }
    sleep 60
done
