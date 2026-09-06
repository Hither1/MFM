"""Pit stalls: go_to notes ("is blocked" / "stalled") where the avatar stands 1.5+ blocks
below the highest [STATE] it recorded within 10 blocks (xz) over the previous 25 sections
-- it walked down into a hole its walk cannot climb out of. Read-only."""
import re, sys, os, math, collections
HDR = re.compile(r"^Action (\d+) \| Step (\d+)")
ST = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
rows = []
for p in sys.argv[1:]:
    if not os.path.exists(p): continue
    step = 0; hist = collections.deque(maxlen=25); pos = None
    blocked = 0; pit = 0; pit_steps = 0; first_pit = None; last_pit_step = None
    for ln in open(p, encoding="utf-8", errors="ignore"):
        m = HDR.match(ln)
        if m:
            step = int(m.group(2))
            if pos: hist.append(pos)
            continue
        m = ST.match(ln)
        if m: pos = (float(m.group(1)), float(m.group(2)), float(m.group(3))); continue
        if ln.startswith("[NOTE] go_to") and (" is blocked at " in ln or " stalled at " in ln):
            blocked += 1
            if pos and hist:
                near = [h[1] for h in hist if math.hypot(h[0]-pos[0], h[2]-pos[2]) <= 10]
                if near and max(near) - pos[1] >= 1.5:
                    pit += 1
                    if first_pit is None: first_pit = step
                    last_pit_step = step
    if blocked:
        rows.append((os.path.basename(p.split("/episode_001")[0]), blocked, pit, first_pit, last_pit_step, step))
print("run\tgoto_blocked_notes\tpit_stalls\tfirst_pit_step\tlast_pit_step\tlast_step")
for r in rows: print("\t".join(str(x) for x in r))
tb = sum(r[1] for r in rows); tp = sum(r[2] for r in rows)
print(f"runs={len(rows)} blocked_notes={tb} pit_stalls={tp} ({100*tp/max(tb,1):.0f}%) runs_with_pit={sum(1 for r in rows if r[2])}")
