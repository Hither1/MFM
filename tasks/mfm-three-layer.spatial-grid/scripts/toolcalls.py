"""Classify the model's shell commands in codex_turns/*.events.jsonl (read-only)."""
import sys, os, json, re, glob, collections
def classify(cmd):
    c=cmd
    kinds=[]
    if "episodes.py" in c: kinds.append("episodes.py")
    if "previous/" in c: kinds.append("previous/")
    if "zoom.py" in c: kinds.append("zoom.py")
    if re.search(r"\.png", c) and "episodes.py" not in c: kinds.append("png")
    if re.search(r"\b(rg|grep|ag)\b", c) and "logs.txt" in c: kinds.append("grep logs")
    elif re.search(r"\b(sed|cat|head|tail|awk|less|wc)\b", c) and "logs.txt" in c: kinds.append("read logs")
    if "actions.json" in c and re.search(r"cat >|tee|printf|echo|python", c): kinds.append("write actions")
    if re.search(r"world_model|hypotheses|rules\.md|spatial\.md|visited\.csv|events\.jsonl", c): kinds.append("wm docs")
    if not kinds: kinds.append("other")
    return kinds
def ep_flags(cmd):
    return sorted(set(re.findall(r"--(last|steps|near|tag|grep|sheet|json|previous|radius)\b", cmd)))
rows=collections.defaultdict(lambda: collections.Counter()); turns=collections.Counter(); ep_turns=collections.Counter(); flags=collections.defaultdict(collections.Counter); cmds_per=collections.defaultdict(list); imgs=collections.Counter()
for d in sys.argv[1:]:
    run=d.split("/output/")[1].split("/")[0]
    grp = run if len(sys.argv)<=12 else ('wm' if ('_wm' in run or 'worldmodel' in run) else 'lb' if ('_lb' in run or 'logbook' in run) else 'lt' if '_lt' in run else 'direct' if '_direct' in run else 'mfm' if '_mfm' in run else 'other')
    for f in sorted(glob.glob(os.path.join(d,"*.events.jsonl"))):
        turns[grp]+=1; n=0; ep=False
        for ln in open(f, encoding="utf-8", errors="ignore"):
            try: e=json.loads(ln)
            except Exception: continue
            it=e.get("item") or {}
            if e.get("type")!="item.completed": continue
            t=it.get("type")
            if t=="command_execution":
                n+=1
                for k in classify(it.get("command","")): rows[grp][k]+=1
                if "episodes.py" in it.get("command",""):
                    ep=True
                    for fl in ep_flags(it.get("command","")): flags[grp][fl]+=1
            elif t in ("image_view","view_image") or "image" in str(t): imgs[grp]+=1
            else: rows[grp]["item:"+str(t)]+=1
        cmds_per[grp].append(n)
        if ep: ep_turns[grp]+=1
for g in sorted(turns):
    cp=cmds_per[g]; 
    print(f"{g}: turns {turns[g]}, commands/turn mean {sum(cp)/len(cp):.1f} (turns with 0 cmds: {sum(1 for x in cp if x==0)}), turns with episodes.py: {ep_turns[g]} ({ep_turns[g]/turns[g]:.0%}), image items {imgs[g]}")
    print("   kinds:", dict(rows[g].most_common(12)))
    if flags[g]: print("   episodes.py flags:", dict(flags[g].most_common()))
