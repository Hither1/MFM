"""Do the arms die where something already told them it was dangerous.

    python repeat_deaths.py --arm og10 --arm og8
    python repeat_deaths.py --arm og10 --quiet           # table only, no per-death detail
    python repeat_deaths.py --arm og10 --json

Every `[NOTE] YOU DIED at (x, y, z)` in this life's logs.txt is matched against the hazard
record that existed BEFORE it:

  death   an earlier death in the same log, or any death in a previous life
  lava    `[NOTE] LAVA AHEAD: ... lava at (x, y, z)` -- the sighting cell, this life or earlier
  doused  `[NOTE] the runner DOUSED you ... now at (x, y, z)` -- where the runner pulled it out

Distances are xz only (a death 30 blocks below a recorded surface site is not the same
mistake as one 30 blocks away). A death within 8 blocks of a record is counted as a repeat,
separately for records made in this life and records carried in from previous/life_*.
Dimension is read off the x coordinate: |x| < 1000 is the Nether, which is compressed 8:1,
so overworld and nether distances are not comparable and are reported apart.
"""
import glob, json, os, re, sys

from _kit import (base_parser, dist_xz, episode_dir, log_steps, print_table, read_lines,
                  roots_of)

NEAR = 8.0
DIED_RE = re.compile(r"YOU DIED at \((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\)")
LAVA_RE = re.compile(r"lava at \((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\)")
DOUSED_RE = re.compile(r"now at \((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\)")


def dimension(x: float) -> str:
    return "nether" if abs(x) < 1000 else "overworld"


def parse_log(path: str, life: str) -> tuple:
    """(deaths, hazards) from one logbook; both carry step, xz and dimension."""
    lines = read_lines(path)
    steps, _ = log_steps(lines)
    deaths, hazards = [], []
    for i, ln in enumerate(lines):
        if "YOU DIED at" in ln:
            m = DIED_RE.search(ln)
            if m:
                x, y, z = (float(v) for v in m.groups())
                rec = {"kind": "death", "step": steps[i], "life": life,
                       "xz": (x, z), "y": y, "dim": dimension(x)}
                deaths.append(rec)
                hazards.append(rec)
        elif "LAVA AHEAD" in ln:
            m = LAVA_RE.search(ln)
            if m:
                x, y, z = (float(v) for v in m.groups())
                hazards.append({"kind": "lava", "step": steps[i], "life": life,
                                "xz": (x, z), "y": y, "dim": dimension(x)})
        elif "DOUSED" in ln:
            m = DOUSED_RE.search(ln)
            if m:
                x, y, z = (float(v) for v in m.groups())
                hazards.append({"kind": "doused", "step": steps[i], "life": life,
                                "xz": (x, z), "y": y, "dim": dimension(x)})
    return deaths, hazards


def scan(arm: str, roots) -> dict:
    ep = episode_dir(arm, roots)
    if not ep:
        return {}
    mem = ep + "/memory"
    deaths, this_hz = parse_log(mem + "/logs.txt", "this")
    prev_hz, lives = [], 0
    for d in sorted(glob.glob(mem + "/previous/life_*")):
        p = os.path.join(d, "logs.txt")
        if os.path.isfile(p):
            lives += 1
            _, hz = parse_log(p, os.path.basename(d))
            prev_hz.extend(hz)

    res = {"arm": arm, "episode": ep, "deaths": len(deaths), "prev_lives": lives,
           "this_life_records": len(this_hz), "prev_life_records": len(prev_hz),
           "near_same_life": 0, "near_prev_life": 0, "nether": 0, "overworld": 0,
           "detail": []}
    for d in deaths:
        res[d["dim"]] += 1
        same = [h for h in this_hz if h["step"] < d["step"]]
        best_s = min(((dist_xz(d["xz"], h["xz"]), h) for h in same), key=lambda t: t[0],
                     default=(None, None))
        best_p = min(((dist_xz(d["xz"], h["xz"]), h) for h in prev_hz), key=lambda t: t[0],
                     default=(None, None))
        if best_s[0] is not None and best_s[0] <= NEAR:
            res["near_same_life"] += 1
        if best_p[0] is not None and best_p[0] <= NEAR:
            res["near_prev_life"] += 1

        def fmt(pair):
            dist, h = pair
            if h is None:
                return None
            return {"dist_xz": round(dist, 1), "kind": h["kind"], "step": h["step"],
                    "life": h["life"], "xz": list(h["xz"])}
        res["detail"].append({"step": d["step"], "xz": list(d["xz"]), "y": d["y"],
                              "dim": d["dim"], "nearest_same_life": fmt(best_s),
                              "nearest_prev_life": fmt(best_p)})
    return res


def main(argv=None) -> int:
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--quiet", action="store_true", help="table only, skip the per-death lines")
    args = p.parse_args(argv)
    roots = roots_of(args)
    if not args.arm:
        p.error("give at least one --arm")

    results = [r for r in (scan(a, roots) for a in args.arm) if r]
    missing = [a for a in args.arm if not any(r["arm"] == a for r in results)]

    if args.json:
        print(json.dumps({"arms": results, "near_blocks": NEAR, "missing": missing}, indent=2))
        return 0

    keys = ["deaths", "nether", "overworld", "near_same_life", "near_prev_life",
            "this_life_records", "prev_lives", "prev_life_records"]
    headers = ["arm", "deaths", "nether", "overwld", "near_same", "near_prev",
               "recs_this", "prev_lives", "recs_prev"]
    rows = [[r["arm"]] + [r[k] for k in keys] for r in results]
    if rows:
        rows.append(["TOTAL"] + [sum(r[k] for r in results) for k in keys])
        print_table(headers, rows)
    if missing:
        print("\nnot found: " + ", ".join(missing))

    if not args.quiet:
        for r in results:
            if not r["detail"]:
                continue
            print("\n-- %s: %d death(s) --" % (r["arm"], r["deaths"]))
            for d in r["detail"]:
                print("   step %-7d (%.0f, %.0f) y=%.0f %s"
                      % (d["step"], d["xz"][0], d["xz"][1], d["y"], d["dim"]))
                for label in ("nearest_same_life", "nearest_prev_life"):
                    n = d[label]
                    if n is None:
                        print("      %-18s none" % label)
                    else:
                        print("      %-18s %6.1f blocks  %-6s %s step %d"
                              % (label, n["dist_xz"], n["kind"], n["life"], n["step"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
