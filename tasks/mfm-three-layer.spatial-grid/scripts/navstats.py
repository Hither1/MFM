"""Per-run navigation statistics from a workspace logs.txt (read-only analysis)."""
import re, sys, math, collections, glob, os

ACT = re.compile(r"^\[ACTION\] (\w+)\((.*?)\) -> (\d+) ticks")
STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
HDR = re.compile(r"^Action (\d+) \| Step (\d+)")
KEYS = {
 "goto_blocked": r"go_to .* is blocked",
 "goto_short": r"go_to .* ran out of ticks",
 "no_screen": r"no screen is open",
 "wall_stop": r"wall stopped|moved=0\.00|blocked by terrain",
 "water_trap": r"swim|drown|in water|near water|water under",
 "fell": r"\bfell\b|fall",
 "death": r"you DIED|DEATH|died at",
 "lava_ahead": r"LAVA AHEAD",
 "cave": r"\bcave\b|open air|drop ahead|pit",
 "out_of_reach": r"out of reach|cannot reach|not in reach|too far",
 "lost_site": r"where (is|was)|cannot find|can't find|not found|no (table|furnace) (is )?(in|within)",
}
def run(path):
    txt = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    ticks = collections.Counter(); calls = collections.Counter(); notes = collections.Counter()
    pos = []; last_step = 0; nact = 0
    for ln in txt:
        m = HDR.match(ln)
        if m: nact = int(m.group(1)); last_step = int(m.group(2)); continue
        m = ACT.match(ln)
        if m:
            fam = m.group(1); t = int(m.group(3)); ticks[fam] += t; calls[fam] += 1; continue
        m = STATE.match(ln)
        if m: pos.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), last_step)); continue
        if ln.startswith("[NOTE]") or ln.startswith("[EVENT]"):
            for k, pat in KEYS.items():
                if re.search(pat, ln, re.I): notes[k] += 1
    # revisits: cells (2-block bins) re-entered after having been > 12 blocks away
    seen = {}; revisits = 0; far = False; cur_cell=None
    for x,y,z,s in pos:
        c = (int(x//2), int(y//2), int(z//2))
        if c in seen:
            if far: revisits += 1; far = False
        else:
            seen[c] = s
        # far from all recently... approximate: distance from previous position > 12
        if pos and cur_cell is not None:
            px,py,pz = cur_cell
            if math.dist((x,y,z),(px,py,pz)) > 12: far = True
        cur_cell = (x,y,z)
    ys = [p[1] for p in pos]
    nav = sum(ticks[k] for k in ("go_to","travel","mine_forward","strip_mine","dig_down","stair_down","travel_bearing","pillar_up","bridge_forward","find_lava","explore_nether","mine_ahead"))
    tot = sum(ticks.values())
    return dict(run=os.path.basename(path.split("/episode_001")[0]), steps=last_step, actions=nact,
                tot_ticks=tot, nav_ticks=nav, nav_frac=(nav/tot if tot else 0),
                goto=calls["go_to"], goto_blocked=notes["goto_blocked"], goto_short=notes["goto_short"],
                mfwd=calls["mine_forward"]+calls["strip_mine"], digdown=calls["dig_down"]+calls["stair_down"],
                no_screen=notes["no_screen"], water=notes["water_trap"], death=notes["death"],
                lava=notes["lava_ahead"], reach=notes["out_of_reach"], lost=notes["lost_site"],
                ymin=min(ys) if ys else None, revisits=revisits, cells=len(seen))
if __name__ == "__main__":
    rows = [run(p) for p in sys.argv[1:] if os.path.exists(p)]
    keys = ["run","steps","actions","nav_frac","goto","goto_blocked","goto_short","mfwd","digdown","no_screen","water","death","lava","reach","lost","ymin","cells","revisits"]
    print("\t".join(keys))
    for r in rows:
        print("\t".join(f"{r[k]:.2f}" if isinstance(r[k], float) else str(r[k]) for k in keys))
