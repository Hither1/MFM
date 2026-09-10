"""Plan-grain stalls: how often one plan was re-issued while the avatar went nowhere.

    python stall.py <memory dir>...            # .../episode_001/memory
    python stall.py <memory dir>... --top 5 --min-len 3 --grain both

Source: `logs.txt` only (read-only). Every `Action N | Step S | Plan Step i/k` header
opens a SECTION -- one plan entry -- carrying that turn's `[PLAN]` block, its `EXPECT:`
line and the `moved=` of its `[STATE]`. Sections are grouped into TURNS (one model call)
by the plan-step counter: a new turn starts wherever `i` does not advance.

Both grains are counted because they answer different questions and disagree sharply:

  section  consecutive sections with the same EXPECT (or, without one, the same plan
           text) -- this is what `tail logs.txt` shows, and it counts the entries of ONE
           plan as repeats, because the harness reprints the plan under every entry.
  turn     consecutive MODEL TURNS that re-issued the same text -- the model actually
           saying the same thing again.

`spanning` is the number of section runs that cross a turn boundary: a section run that
does not is one plan of many entries, not a model repeating itself.

A run counts when it is at least `--min-len` units long AND the `moved=` of its sections
sums to less than 0.5 blocks: the same plan while something is moving is progress, not a
stall. Texts are compared after whitespace normalisation and lowercasing, exactly as
`mfm.memory.retrieve.plan_repeats` compares them. Deaths (`[NOTE] YOU DIED`) are counted
per life for context.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import print_table                                            # noqa: E402

HEADER_RE = re.compile(r"^Action (\d+) \| Step (\d+)(?: \| Plan Step (\d+)/(\d+))?")
MOVED_RE = re.compile(r"\bmoved=(-?\d+(?:\.\d+)?)")
EXPECT_RE = re.compile(r"^EXPECT:\s*(.+?)\s*$")


def sections(path):
    """[{action, step, plan_i, plan_k, plan, expect, moved, died}] for one logs.txt."""
    out, cur = [], None
    try:
        fh = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return out
    with fh:
        in_plan = False
        for ln in fh:
            ln = ln.rstrip("\n")
            m = HEADER_RE.match(ln)
            if m:
                cur = {"action": int(m.group(1)), "step": int(m.group(2)),
                       "plan_i": int(m.group(3)) if m.group(3) else None,
                       "plan_k": int(m.group(4)) if m.group(4) else None,
                       "plan": [], "expect": "", "moved": 0.0, "died": 0}
                out.append(cur)
                in_plan = False
                continue
            if cur is None:
                continue
            if ln.startswith("[PLAN]"):
                cur["plan"].append(ln[len("[PLAN]"):].strip())
                in_plan = True
                continue
            me = EXPECT_RE.match(ln)
            if me:
                cur["expect"] = me.group(1)
                in_plan = False
                continue
            if ln.startswith("["):
                in_plan = False
                if ln.startswith("[STATE]"):
                    mm = MOVED_RE.search(ln)
                    if mm:
                        cur["moved"] += abs(float(mm.group(1)))
                elif "YOU DIED" in ln:
                    cur["died"] += 1
                continue
            if in_plan and ln.strip():
                cur["plan"].append(ln.strip())
    for s in out:
        s["plan"] = " ".join(" ".join(s["plan"]).split())
    return out


def turns(secs):
    """Sections grouped into model turns by the plan-step counter."""
    out, prev = [], None
    for s in secs:
        i, k = s["plan_i"], s["plan_k"]
        if i is None:
            prev = None
            continue
        new = prev is None or i <= prev["plan_i"] or k != prev["plan_k"]
        if new:
            out.append({"sections": [], "moved": 0.0, "expect": "", "plan": "",
                        "step": s["step"], "action": s["action"], "died": 0})
        t = out[-1]
        s["turn_ix"] = len(out) - 1
        t["sections"].append(s)
        t["moved"] += s["moved"]
        t["died"] += s["died"]
        t["expect"] = t["expect"] or s["expect"]
        t["plan"] = t["plan"] or s["plan"]
        prev = s
    return out


def key(unit):
    text = (unit.get("expect") or "").strip() or (unit.get("plan") or "").strip()
    return " ".join(text.split()).lower()


def runs(units, min_len=3, max_moved=0.5):
    """Maximal consecutive runs of one key that together moved less than `max_moved`."""
    out, start = [], 0
    for i in range(1, len(units) + 1):
        if i == len(units) or key(units[i]) != key(units[start]):
            seg = units[start:i]
            moved = sum(u["moved"] for u in seg)
            if len(seg) >= min_len and key(seg[0]) and moved < max_moved:
                spans = {u.get("turn_ix") for u in seg}
                out.append({"n": len(seg), "moved": moved, "key": key(seg[0]),
                            "text": (seg[0].get("expect") or seg[0].get("plan") or ""),
                            "from": seg[0]["step"], "to": seg[-1]["step"],
                            "turns": len(spans - {None})})
            start = i
    return out


def scan(path, min_len):
    secs = sections(os.path.join(path, "logs.txt"))
    tns = turns(secs)                      # tags every section with its turn index
    out = {"sections": len(secs), "turns": len(tns),
           "deaths": sum(s["died"] for s in secs)}
    for name, units in (("sec", secs), ("turn", tns)):
        rs = runs(units, min_len)
        out[name + "_runs"] = len(rs)
        out[name + "_in"] = sum(r["n"] for r in rs)
        out[name + "_max"] = max((r["n"] for r in rs), default=0)
        out[name + "_top"] = sorted(rs, key=lambda r: -r["n"])
        if name == "sec":
            out["spanning"] = sum(1 for r in rs if r["turns"] > 1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("memory", nargs="+", help="a run's memory directory (holding logs.txt)")
    ap.add_argument("--min-len", type=int, default=3, help="shortest run counted (default 3)")
    ap.add_argument("--top", type=int, default=5, help="repeated texts to print per life")
    ap.add_argument("--grain", choices=("sec", "turn", "both"), default="both")
    ap.add_argument("--chars", type=int, default=80, help="width of a printed text")
    args = ap.parse_args(argv)

    rows, scans = [], {}
    for path in args.memory:
        name = os.path.basename(os.path.dirname(os.path.dirname(path.rstrip("/")))) or path
        s = scans[name] = scan(path, args.min_len)
        row = [name, s["sections"], s["turns"], s["deaths"]]
        extra = [s["spanning"]]
        for g in (("sec", "turn") if args.grain == "both" else (args.grain,)):
            row += [s[g + "_runs"], s[g + "_in"], s[g + "_max"]]
        rows.append(row + extra)
    head = ["life", "sections", "turns", "deaths"]
    for g in (("sec", "turn") if args.grain == "both" else (args.grain,)):
        head += [f"{g} runs>={args.min_len}", f"{g} units in", f"{g} longest"]
    head += ["sec runs spanning turns"]
    print_table(head, rows)
    for name in scans:
        for g in (("sec", "turn") if args.grain == "both" else (args.grain,)):
            top = scans[name][g + "_top"][: args.top]
            if not top:
                continue
            print(f"\n{name} [{g}] top {len(top)} repeated plan texts:")
            for r in top:
                print(f"  x{r['n']:<3} ({r['turns']} turn{'s' if r['turns'] != 1 else ''}) "
                      f"steps {r['from']}-{r['to']} moved {r['moved']:.1f}: "
                      f"{r['text'][:args.chars]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
