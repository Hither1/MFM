import re, sys, os, math, collections, statistics as st
sys.path.insert(0, os.path.dirname(__file__))
from churn import parse
def seg(acts, lo, hi):
    a=[x for x in acts if lo<=x["step"]<hi]
    if len(a)<2: return None
    prev=None; prod=0; pts=[]
    for x in a:
        moved=(math.dist(x["pos"],prev) if (x["pos"] and prev) else 0.0)
        if x["inv"] or x["ev"] or moved>1.0: prod+=1
        if x["pos"]: prev=x["pos"]; pts.append(x["pos"])
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; zs=[p[2] for p in pts]
    diag=math.dist((min(xs),min(ys),min(zs)),(max(xs),max(ys),max(zs))) if pts else 0
    names=collections.Counter(x["name"] for x in a)
    return dict(n=len(a), prod=prod/len(a), diag=diag, steps_per_act=(hi-lo)/len(a), names=names)
rows=[]
for p in sys.argv[1:]:
    if not os.path.exists(p): continue
    acts=parse(p)
    if not acts or acts[-1]["step"]<6000: continue
    T=acts[-1]["step"]; q=T//4
    head=seg(acts,0,3*q); tail=seg(acts,3*q,T+1)
    if not head or not tail: continue
    rows.append((os.path.basename(p.split('/episode_001')[0]), head, tail))
if len(rows)<=8:
    for n,h,t in rows: print(f"{n}: head prod {h['prod']:.2f} diag {h['diag']:.0f} | tail prod {t['prod']:.2f} diag {t['diag']:.0f} acts {t['n']} steps/act {t['steps_per_act']:.0f} top {t['names'].most_common(5)}")
else:
    hp=[h['prod'] for _,h,_ in rows]; tp=[t['prod'] for _,_,t in rows]; hd=[h['diag'] for _,h,_ in rows]; td=[t['diag'] for _,_,t in rows]
    print(f"n={len(rows)} productive-action frac: head med {st.median(hp):.2f} -> tail med {st.median(tp):.2f}; tail<0.3: {sum(1 for x in tp if x<0.3)}; bbox diag head med {st.median(hd):.0f} -> tail med {st.median(td):.0f}; tail diag<8: {sum(1 for x in td if x<8)}")
    allt=collections.Counter()
    for _,_,t in rows:
        if t['prod']<0.3: allt.update(t['names'])
    tot=sum(allt.values()); print("tail actions in low-productivity tails:", [(k,f"{v/tot:.0%}") for k,v in allt.most_common(12)])
