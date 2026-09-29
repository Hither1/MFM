#!/usr/bin/env python3
"""Stop ONE arm (or several) by name: the run-arm.sh wrapper whose command line names it
exactly, plus every descendant. SIGTERM the tree, wait up to 30 s, SIGKILL the stragglers
(the java engine ignores SIGTERM). Targets are resolved by pid before any signal is sent;
nothing is matched by a loose pattern.

    scripts/stop_arm.py mfm_diamond_s0 mfm_diamond_s1        # dry run
    scripts/stop_arm.py --go mfm_diamond_s0 mfm_diamond_s1   # stop them
"""
import os, signal, subprocess, sys, time


def ps():
    out = subprocess.run(["ps", "-eo", "pid,ppid,args"], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def tree(root, rows):
    kids = {}
    for pid, ppid, _ in rows:
        kids.setdefault(ppid, []).append(pid)
    out, stack = [root], [root]
    while stack:
        p = stack.pop()
        for k in kids.get(p, []):
            out.append(k)
            stack.append(k)
    return out


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def main():
    args = [a for a in sys.argv[1:] if a != "--go"]
    go = "--go" in sys.argv
    if not args:
        print(__doc__)
        return 2
    rows = ps()
    targets = {}
    for arm in args:
        needle = f"run-arm.sh --arm {arm} "
        wrappers = [pid for pid, _, cmd in rows if needle in cmd and "stop_arm.py" not in cmd]
        if not wrappers:
            print(f"{arm}: no wrapper found")
            continue
        pids = []
        for w in wrappers:
            pids += tree(w, rows)
        targets[arm] = sorted(set(pids))
        print(f"{arm}: wrapper(s) {wrappers}, tree of {len(targets[arm])} pids")
    if not go:
        print("dry run -- rerun with --go to send the signals")
        return 0
    allpids = sorted({p for ps_ in targets.values() for p in ps_})
    for p in allpids:
        try:
            os.kill(p, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(30):
        if not any(alive(p) for p in allpids):
            break
        time.sleep(1)
    left = [p for p in allpids if alive(p)]
    for p in left:
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(1)
    still = [p for p in allpids if alive(p)]
    print(f"stopped {len(allpids) - len(still)} of {len(allpids)} pids"
          + (f"; still alive: {still}" if still else "") + (f"; SIGKILLed {len(left)}" if left else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
