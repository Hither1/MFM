import re, sys, os, math, statistics as st, collections
HDR = re.compile(r"^Action (\d+) \| Step (\d+)"); STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
BLK = re.compile(r"go_to \((-?[\d.]+), (-?[\d.]+)\) is blocked at \((-?[\d.]+), (-?[\d.]+)\), ([\d.]+) blocks short")
def run(path):
    step=0; states=[]; blocks=[]
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m=HDR.match(ln)
        if m: step=int(m.group(2)); continue
        m=STATE.match(ln)
        if m: states.append((step,(float(m.group(1)),float(m.group(2)),float(m.group(3))))); continue
        m=BLK.search(ln)
        if m: blocks.append((step,(float(m.group(1)),float(m.group(2))),(float(m.group(3)),float(m.group(4))),float(m.group(5))))
    out=[]
    for s,tgt,at,short in blocks:
        # steps until within 1.5 of target, or until > 3 blocks from the stuck spot, whichever first
        reach=None; away=None
        for s2,p in states:
            if s2<=s: continue
            if reach is None and math.hypot(p[0]-tgt[0],p[2]-tgt[1])<=2.0: reach=s2-s
            if away is None and math.hypot(p[0]-at[0],p[2]-at[1])>3.0: away=s2-s
            if reach is not None and away is not None: break
        out.append((short, reach, away))
    return out
res=collections.defaultdict(list)
for p in sys.argv[1:]:
    if not os.path.exists(p): continue
    n=os.path.basename(p.split('/episode_001')[0])
    grp = 'ob-new' if n.startswith('ob') else ('hist-half' if n.startswith('hd') else 'hist-full/diamond')
    res[grp].extend(run(p))
for g,v in res.items():
    shorts=[a for a,_,_ in v]; reach=[b for _,b,_ in v if b is not None]; away=[c for _,_,c in v if c is not None]
    never=sum(1 for _,b,_ in v if b is None)
    print(f"{g}: {len(v)} blocked events; short med {st.median(shorts):.1f} blocks; reached target later: {len(reach)} (med {st.median(reach) if reach else 0:.0f} steps, p90 {sorted(reach)[int(0.9*len(reach))-1] if reach else 0}); never reached: {never} ({never/len(v):.0%}); moved >3 blocks away after med {st.median(away) if away else 0:.0f} steps")
