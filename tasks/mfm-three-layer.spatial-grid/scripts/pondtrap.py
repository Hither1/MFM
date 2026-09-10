import re, sys, os, statistics as st
HDR=re.compile(r"^Action (\d+) \| Step (\d+)"); STATE=re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
rows=[]
for p in sys.argv[1:]:
    if not os.path.exists(p): continue
    step=0; fill=None; y_fill=None; escape=None; refused=0; blocked=0; last=0
    for ln in open(p, encoding="utf-8", errors="ignore"):
        m=HDR.match(ln)
        if m: step=int(m.group(2)); last=step; continue
        m=STATE.match(ln)
        if m:
            y=float(m.group(2))
            if fill is not None:
                if y_fill is None: y_fill=y
                elif escape is None and y < y_fill-8: escape=step
            continue
        if fill is None and ln.startswith("[INV]") and "water_bucket +1" in ln: fill=step; continue
        if fill is not None and escape is None:
            if "dig_down REFUSED: water" in ln: refused+=1
            if "is blocked at" in ln: blocked+=1
    if fill is None: continue
    rows.append((os.path.basename(p.split('/episode_001')[0]), fill, (escape-fill) if escape else None, refused, blocked, last))
print("run\tfill_step\tsteps_to_descend_8\trefused_water\tgoto_blocked\tlast_step")
for r in rows: print("\t".join(str(x) for x in r))
v=[r[2] for r in rows if r[2] is not None]
print(f"n={len(rows)} escaped={len(v)} med_steps_to_descend={st.median(v) if v else None} p75={sorted(v)[int(0.75*len(v))-1] if v else None} never={sum(1 for r in rows if r[2] is None)}")
