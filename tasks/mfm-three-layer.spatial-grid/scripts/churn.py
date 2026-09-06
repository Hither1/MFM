"""Churn = actions that change nothing. Per run: steps inside low-productivity windows,
where churn begins, what the actions are. Read-only."""
import re, sys, os, math, collections, statistics as st
HDR=re.compile(r"^Action (\d+) \| Step (\d+)"); STATE=re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
ACT=re.compile(r"^\[ACTION\] (\w+|\{)")
def parse(path):
    acts=[]; cur=None
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m=HDR.match(ln)
        if m:
            if cur: acts.append(cur)
            cur=dict(i=int(m.group(1)), step=int(m.group(2)), name=None, pos=None, inv=False, ev=False, gui=None, ms=False); continue
        if cur is None: continue
        m=ACT.match(ln)
        if m: cur["name"]="raw" if m.group(1)=="{" else m.group(1); continue
        m=STATE.match(ln)
        if m: cur["pos"]=(float(m.group(1)),float(m.group(2)),float(m.group(3))); continue
        if ln.startswith("[INV]"): cur["inv"]=True
        elif ln.startswith("[EVENT]"):
            cur["ev"]=True
            if "MILESTONE" in ln: cur["ms"]=True
        elif ln.startswith("[GUI]"): cur["gui"]=("open=True" in ln)
    if cur: acts.append(cur)
    return acts
def churn(acts, W=15, thr=0.2):
    # productive: moved > 1.0 from previous action's pos, or inv change, or event
    prod=[]; prev=None; pgui=None
    for a in acts:
        moved = (math.dist(a["pos"],prev) if (a["pos"] and prev) else 0.0)
        p = a["inv"] or a["ev"] or moved>1.0 or (a["gui"] is not None and pgui is not None and a["gui"]!=pgui)
        prod.append(p)
        if a["pos"]: prev=a["pos"]
        if a["gui"] is not None: pgui=a["gui"]
    n=len(acts); inwin=[False]*n
    for i in range(0, n-W+1):
        if sum(prod[i:i+W]) <= thr*W:
            for j in range(i,i+W): inwin[j]=True
    # steps in churn: sum over churn actions of the step gap to the next action
    steps=0; first=None; names=collections.Counter()
    for i,a in enumerate(acts):
        if inwin[i]:
            nxt = acts[i+1]["step"] if i+1<n else a["step"]
            steps += max(0, nxt-a["step"]); names[a["name"]]+=1
            if first is None: first=a["step"]
    total = acts[-1]["step"] if acts else 0
    last_ms = max([a["step"] for a in acts if a["ms"]], default=0)
    return dict(total=total, churn_steps=steps, churn_frac=steps/total if total else 0, first=first, last_ms=last_ms, names=names, nacts=n, nchurn=sum(inwin))
if __name__ == "__main__":
    rows=[]
    allnames=collections.Counter()
    for p in sys.argv[1:]:
        if not os.path.exists(p): continue
        acts=parse(p)
        if not acts or acts[-1]["step"]<3000: continue
        r=churn(acts); r["run"]=os.path.basename(p.split('/episode_001')[0]); rows.append(r); allnames.update(r["names"])
    if len(rows)<=10:
        print("run\ttotal\tchurn_steps\tchurn_frac\tchurn_starts\tlast_milestone\tchurn_actions/actions")
        for r in rows: print(f"{r['run']}\t{r['total']}\t{r['churn_steps']}\t{r['churn_frac']:.2f}\t{r['first']}\t{r['last_ms']}\t{r['nchurn']}/{r['nacts']}")
        for r in rows: print(r['run'], r['names'].most_common(6))
    else:
        fr=[r['churn_frac'] for r in rows]; 
        print(f"n={len(rows)} churn_frac med {st.median(fr):.2f} mean {st.mean(fr):.2f}; runs >30% churn: {sum(1 for f in fr if f>0.3)}; churn after last milestone: {sum(1 for r in rows if r['first'] and r['first']>=r['last_ms'])}/{sum(1 for r in rows if r['first'])}")
        tot=sum(allnames.values()); print("top churn actions:", [(k, f"{v/tot:.0%}") for k,v in allnames.most_common(14)])
