#!/usr/bin/env python3
"""Stop EVERY running experiment arm of this user: each live run-arm.sh wrapper and its
whole process tree (green xvfb-run/python/Minecraft java, purple agent, any codex turn
in flight), by exact PID -- never by name pattern. Ports in FOREIGN (another session's
servers) are left alone, and so is anything not under a run-arm.sh wrapper.

    scripts/stop_running_arms.py          # dry run: list what would be stopped
    scripts/stop_running_arms.py --go     # SIGTERM the trees, wait up to 30 s, SIGKILL stragglers

The result files of stopped arms are never written (test_evaluation.py dies with the
tree), so a stopped arm shows as "no result" and must be relaunched from scratch.
"""
import os
import re
import signal
import subprocess
import sys
import time

FOREIGN = {9785, 9790, 9795, 9800}
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

    def descendants(pid):
        out = []
        for kid in [p for p, pp, _ in rows if pp == pid]:
            out += [kid] + descendants(kid)
        return out

    plan = []
    for pid, _, a in rows:
        if "run-arm.sh --arm" not in a:
            continue
        arm = re.search(r"--arm (\S+)", a)
        g = re.search(r"--green-port (\d+)", a)
        p = re.search(r"--purple-port (\d+)", a)
        ports = {int(x.group(1)) for x in (g, p) if x}
        if ports & FOREIGN:
            continue
        tree = [pid] + descendants(pid)
        plan.append((arm.group(1) if arm else "?", sorted(ports), pid, tree))
    # Servers whose wrapper already exited but whose arm is still listed (old launcher
    # arms keep their servers after landing) are NOT touched here; that is
    # cleanup_finished_arms.py's job.
    print(f"pids.current before: {pids_now()}")
    print(f"running arms: {len(plan)}")
    for arm, ports, pid, tree in plan:
        print(f"  {arm:16s} ports={ports} wrapper={pid} tree_size={len(tree)}")
    if not go:
        print("dry run -- rerun with --go to stop them")
        return
    allpids = sorted({p for *_, tree in plan for p in tree})

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
