"""Cost of local-navigation failures per run: go_to blocked episodes, remembered-site
re-open failures, re-placements, governor stalls. Read-only."""
import re, sys, os, math, collections, statistics as st
HDR = re.compile(r"^Action (\d+) \| Step (\d+)")
STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
def run(path):
    step = 0; pos = None; events = []; states = []
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m = HDR.match(ln)
        if m: step = int(m.group(2)); continue
        m = STATE.match(ln)
        if m: pos = (float(m.group(1)), float(m.group(2)), float(m.group(3))); states.append((step, pos)); continue
        if "is blocked at" in ln and ln.startswith("[NOTE] go_to"): events.append(("blocked", step, pos))
        elif "aimed at the remembered" in ln: events.append(("reopen_fail", step, pos))
        elif ln.startswith("[NOTE] placed the "): events.append(("placed", step, pos))
        elif "finished 2 times in a row changing nothing" in ln: events.append(("gov", step, pos))
        elif "YOU DIED" in ln: events.append(("died", step, pos))
    # stuck episodes: consecutive blocked/gov/reopen_fail events within 3 blocks; cost = steps from first to when the avatar is >3 blocks away
    stuck = []
    i = 0
    ev = [e for e in events if e[0] in ("blocked", "reopen_fail", "gov")]
    used = set()
    for k, (kind, s, p) in enumerate(ev):
        if k in used or p is None: continue
        # find the first later state > 3 blocks away
        end = None
        for s2, p2 in states:
            if s2 > s and math.dist(p, p2) > 3.0: end = s2; break
        if end is None: end = states[-1][0] if states else s
        for k2 in range(k, len(ev)):
            if ev[k2][1] <= end: used.add(k2)
        stuck.append((s, end - s, kind))
    total = states[-1][0] if states else 0
    lost = sum(c for _, c, _ in stuck if c >= 100)
    return dict(run=os.path.basename(path.split("/episode_001")[0]), steps=total,
                n_blocked=sum(1 for e in events if e[0]=="blocked"),
                n_reopen_fail=sum(1 for e in events if e[0]=="reopen_fail"),
                n_placed=sum(1 for e in events if e[0]=="placed"),
                n_gov=sum(1 for e in events if e[0]=="gov"),
                stuck_eps=len([c for _,c,_ in stuck if c>=100]),
                lost_steps=lost, lost_frac=(lost/total if total else 0),
                worst=max([c for _,c,_ in stuck], default=0))
rows = [run(p) for p in sys.argv[1:] if os.path.exists(p)]
keys = ["run","steps","n_blocked","n_reopen_fail","n_placed","n_gov","stuck_eps","lost_steps","lost_frac","worst"]
print("\t".join(keys))
for r in rows: print("\t".join(f"{r[k]:.2f}" if isinstance(r[k], float) else str(r[k]) for k in keys))
