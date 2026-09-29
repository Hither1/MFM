#!/usr/bin/env python3
"""Stop the green/purple servers that FINISHED arms left behind, by exact PID tree.

A port pair (green G / purple G+10) is a target only if
  * no live run-arm.sh wrapper names G or G+10 (the arm is not running), and
  * G is not in FOREIGN (servers that belong to another session in this repo).
Nothing is matched by name pattern: every PID is taken from its own cmdline
(`src/server.py --port N` or `purple_agent.py --port N`) plus its descendants.

    scripts/cleanup_finished_arms.py          # dry run: print the plan, signal nothing
    scripts/cleanup_finished_arms.py --go     # SIGTERM, wait up to 30 s, SIGKILL stragglers

Background: run-arm.sh never stopped its servers, so each finished dragon arm kept a
green server (64 threads, 5-8 GB of retained frames) and a purple agent (66 threads)
alive; ~50 finished arms exhausted the user's pids cgroup (21,626) and new arms
died at java start ("Cannot create GC thread").
"""
import os
import re
import signal
import subprocess
import sys
import time

FOREIGN = {9785, 9790, 9795, 9800}  # worktrees/claude-code -- another session's servers
CGROUP = "/sys/fs/cgroup/pids/user.slice/user-%d.slice" % os.getuid()


def pids_now():
    try:
        return open(os.path.join(CGROUP, "pids.current")).read().strip()
    except OSError:
        return "?"


def ps():
    out = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "pid=,ppid=,args="],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split(None, 2)
        if len(p) == 3:
            rows.append((int(p[0]), int(p[1]), p[2]))
    return rows


def main():
    go = sys.argv[1:] == ["--go"]
    rows = ps()
    live_ports = set()
    live_arms = set()
    for _, _, a in rows:
        if "run-arm.sh --arm" not in a:
            continue
        live_arms.update(re.findall(r"--arm (\S+)", a))
        for key in ("--green-port", "--purple-port"):
            m = re.search(key + r" (\d+)", a)
            if m:
                live_ports.add(int(m.group(1)))
    targets = {}
    for pid, _, a in rows:
        m = re.search(r"--port (\d+)", a)
        if not m:
            continue
        port = int(m.group(1))
        if "src/server.py" in a:
            role, gport = "green", port
        elif "purple_agent.py" in a:
            role, gport = "purple", port - 10
        else:
            continue
        if gport in FOREIGN or port in FOREIGN or port in live_ports or gport in live_ports:
            continue
        targets.setdefault(gport, []).append((pid, role, a[:80]))

    def descendants(pid):
        out = []
        for kid in [p for p, pp, _ in rows if pp == pid]:
            out += [kid] + descendants(kid)
        return out

    plan = []
    for gport in sorted(targets):
        for pid, role, a in targets[gport]:
            plan.append((gport, role, pid, [pid] + descendants(pid), a))
    print(f"pids.current before: {pids_now()}")
    print(f"live arms (untouched): {sorted(live_arms)}")
    print(f"targets: {len(plan)} servers on {len(targets)} port pairs")
    for gport, role, pid, tree, a in plan:
        print(f"  green={gport:<5d} {role:6s} pid={pid:<7d} tree={tree} :: {a}")
    if not go:
        print("dry run -- rerun with --go to send the signals")
        return
    allpids = sorted({p for *_, tree, _ in plan for p in tree})

    def alive(p):
        try:
            os.kill(p, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    for p in allpids:
        try:
            os.kill(p, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(30):
        time.sleep(1)
        if not any(alive(p) for p in allpids):
            break
    left = [p for p in allpids if alive(p)]
    for p in left:
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(2)
    print(f"SIGTERM to {len(allpids)} pids; SIGKILL needed for {left}; "
          f"still alive: {[p for p in allpids if alive(p)]}")
    print(f"pids.current after: {pids_now()}")


if __name__ == "__main__":
    main()
