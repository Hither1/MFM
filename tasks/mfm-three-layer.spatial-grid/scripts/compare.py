"""One line per run: the navigation-loss metrics of the spatial-grid claim, from a
workspace logs.txt (read-only). Usage: python compare.py <logs.txt>...

  steps       last step in the log
  ms          milestones verified (count) and the step of the last one
  fill        step of the first water_bucket +1
  fill>desc8  steps from the fill to the first [STATE] 8+ blocks below the fill's y
  fill>lava   steps from the fill to the first LAVA AHEAD note (None: never)
  deaths      YOU DIED notes
  goto b/d/a  go_to calls / "is blocked" notes / detours queued / detours that arrived
  esc reop gov water escapes queued / pose re-opens / governor refusals (tabu or plan watchdog)
  churn       churn.py's low-productivity fraction (W=15, thr=0.2)
  prev        turns whose briefing mentions previous/ (the carry being read)
"""
import os, re, sys, math
sys.path.insert(0, os.path.dirname(__file__))
from churn import parse as parse_acts, churn as churn_of   # noqa: E402

HDR = re.compile(r"^Action (\d+) \| Step (\d+)")
STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)")
ACT = re.compile(r"^\[ACTION\] (\w+)")


def run(path):
    step = 0; fill = None; y_fill = None; desc = None; lava = None; deaths = 0
    goto = 0; blocked = 0; detours = 0; arrived = 0; esc = 0; reop = 0; wd = 0; prev = 0
    ms = []; in_briefing = False; briefing_prev = False
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m = HDR.match(ln)
        if m:
            step = int(m.group(2)); in_briefing = True; briefing_prev = False; continue
        if in_briefing and not ln.startswith("["):
            if "previous/" in ln and not briefing_prev:
                prev += 1; briefing_prev = True
        m = ACT.match(ln)
        if m:
            in_briefing = False
            if m.group(1) == "go_to": goto += 1
            continue
        m = STATE.match(ln)
        if m:
            y = float(m.group(2))
            if fill is not None:
                if y_fill is None: y_fill = y
                elif desc is None and y < y_fill - 8: desc = step
            continue
        if fill is None and ln.startswith("[INV]") and "water_bucket +1" in ln:
            fill = step; continue
        if ln.startswith("[EVENT] MILESTONE"): ms.append((ln.split()[2], step)); continue
        if not ln.startswith("[NOTE]"): continue
        if "LAVA AHEAD" in ln and lava is None and fill is not None: lava = step
        if "YOU DIED" in ln: deaths += 1
        if "is blocked at" in ln: blocked += 1
        if "detouring over" in ln: detours += 1
        if "detour" in ln and "arrived" in ln: arrived += 1
        if "along your own trail" in ln: esc += 1
        if "replayed" in ln and "pose" in ln: reop += 1
        if "will be refused before it spends steps" in ln or "change the OBJECTIVE" in ln: wd += 1
    acts = parse_acts(path)
    ch = churn_of(acts) if acts else {"churn_frac": 0.0}
    name = os.path.basename(path.split("/episode_001")[0])
    return dict(run=name, steps=step, ms=f"{len(ms)}@{ms[-1][1] if ms else '-'}", fill=fill,
                fill_desc=(desc - fill) if (fill is not None and desc) else None,
                fill_lava=(lava - fill) if (fill is not None and lava) else None,
                deaths=deaths, goto=f"{goto}/{blocked}/{detours}/{arrived}",
                esc=esc, reop=reop, gov=wd, churn=f"{ch['churn_frac']:.2f}", prev=prev)


if __name__ == "__main__":
    rows = [run(p) for p in sys.argv[1:] if os.path.exists(p)]
    keys = ["run", "steps", "ms", "fill", "fill_desc", "fill_lava", "deaths", "goto", "esc",
            "reop", "gov", "churn", "prev"]
    print("\t".join(keys))
    for r in rows:
        print("\t".join(str(r[k]) for k in keys))
