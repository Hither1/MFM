"""view_image calls from codex rollouts: which image, in which turn, what the model said next."""
import sys, os, json, glob, re
home=sys.argv[1]; limit=int(sys.argv[2]) if len(sys.argv)>2 else 40
files=sorted(glob.glob(os.path.join(home,"sessions","**","rollout-*.jsonl"), recursive=True))
print(f"{home}: {len(files)} rollouts")
n=0; kinds={}
for f in files:
    items=[]
    for ln in open(f, encoding="utf-8", errors="ignore"):
        try: e=json.loads(ln)
        except Exception: continue
        items.append(e)
    for i,e in enumerate(items):
        s=json.dumps(e)
        if "view_image" not in s: continue
        p=e.get("payload",e)
        t=p.get("type","")
        if t not in ("function_call","custom_tool_call","tool_call"): 
            # exec code-mode cell mentioning view_image
            if t!="function_call" and "tools.view_image" not in s: continue
        args=p.get("arguments") or p.get("input") or ""
        paths=re.findall(r"[\w./\-]+\.png", str(args) if args else s)
        for pth in paths[:3]:
            k = "sheet(/tmp)" if pth.startswith("/tmp") else ("previous/" if "previous/" in pth else ("episodes/" if "episodes/" in pth else ("frame.png" if pth.endswith("frame.png") else "other")))
            kinds[k]=kinds.get(k,0)+1
        # next assistant message
        nxt=""
        for e2 in items[i+1:i+15]:
            p2=e2.get("payload",e2)
            if p2.get("type")=="message" and p2.get("role")=="assistant":
                c=p2.get("content",[]); 
                nxt=" ".join(x.get("text","") for x in c if isinstance(x,dict))[:220].replace("\n"," "); break
        if n<limit: print(os.path.basename(f)[8:27], "|", (paths[:2] or [str(args)[:80]]), "\n     ->", nxt)
        n+=1
print("total view_image mentions:", n, "by image kind:", kinds)
