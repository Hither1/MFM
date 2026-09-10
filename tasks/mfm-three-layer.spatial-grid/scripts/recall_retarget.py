"""Did the [RECALL] block the harness computed change where the model then went.

    python recall_retarget.py --arm og14 --arm og19
    python recall_retarget.py --arm og19 --verbose        # + 5 retargeted turns
    python recall_retarget.py --arm og14 --json

For every codex turn whose prompt carries a [RECALL] block: pull the coordinates the block
cites, then read the plan the model actually wrote for that turn -- the [PLAN]/[ACTION] lines
in logs.txt between this turn's step (the prompt opens with `Step S/60000`) and the next
turn's step -- and ask three separate questions:

  retarget  a coordinate target in the plan lies within 8 blocks (xz) of a cited coordinate
  mention   the plan text says recall / earlier / before / last time / cited
  frame     that turn's events.jsonl has a view_image call on an episodes/ frame

They are counted independently and do not have to agree: retargeting without a mention is the
uptake that matters, a mention without retargeting is lip service. Coordinates on lines that
talk about `px` or `screen` are dropped -- those are screen-pixel readings, not world cells.
"""
import json, os, re, sys

from _kit import (base_parser, dist_xz, episode_dir, log_steps, plan_targets, print_table,
                  read_lines, roots_of, turn_files, xz_tuples)

NEAR = 8.0
STEP_RE = re.compile(r"\bStep (\d+)")
MENTION_RE = re.compile(r"recall|earlier|before|last time|cited", re.I)


def recall_block(lines) -> list:
    """The [RECALL] line plus the '- '/indented lines under it; [] if the prompt has none."""
    for i, ln in enumerate(lines):
        if ln.startswith("[RECALL]"):
            block = [ln]
            for nxt in lines[i + 1:]:
                if not nxt.strip() or nxt.startswith("["):
                    break
                if nxt[0] in " \t-":
                    block.append(nxt)
                else:
                    break
            return block
    return []


def cited_coords(block) -> list:
    out = []
    for ln in block:
        low = ln.lower()
        if "px" in low or "screen" in low:
            continue
        out.extend(xz_tuples(ln))
    return out


def viewed_frame(events_path: str) -> bool:
    if not os.path.isfile(events_path):
        return False
    with open(events_path, encoding="utf-8", errors="ignore") as fh:
        return any("view_image" in ln and "episodes/" in ln for ln in fh)


def scan(arm: str, roots) -> dict:
    ep = episode_dir(arm, roots)
    if not ep:
        return {}
    log = read_lines(ep + "/memory/logs.txt")
    steps, _ = log_steps(log)
    turns = turn_files(ep)
    if not turns or not log:
        return {}

    # Each turn's own step, from the prompt header; used to window the logbook.
    prompts = []
    for n, ppath, epath in turns:
        plines = read_lines(ppath)
        m = STEP_RE.search("\n".join(plines[:5]))
        prompts.append((n, plines, epath, int(m.group(1)) if m else None))

    res = {"arm": arm, "episode": ep, "turns": len(turns), "recall_turns": 0,
           "retarget": 0, "mention": 0, "frame": 0, "cited_coords": 0,
           "block_lines": 0, "examples": []}
    for idx, (n, plines, epath, step) in enumerate(prompts):
        block = recall_block(plines)
        if not block or step is None:
            continue
        res["recall_turns"] += 1
        res["block_lines"] += len(block)
        coords = cited_coords(block)
        res["cited_coords"] += len(coords)

        nxt = next((s for _, _, _, s in prompts[idx + 1:] if s is not None), None)
        plan = [ln for i, ln in enumerate(log)
                if steps[i] >= step and (nxt is None or steps[i] < nxt)
                and (ln.startswith("[PLAN]") or ln.startswith("[ACTION]"))]
        text = "\n".join(plan)
        targets = plan_targets(text)

        best = min((dist_xz(t, c) for t in targets for c in coords), default=None)
        hit = best is not None and best <= NEAR
        if hit:
            res["retarget"] += 1
            if len(res["examples"]) < 5:
                res["examples"].append({"turn": n, "step": step, "nearest": round(best, 1),
                                        "cited": len(coords), "targets": len(targets)})
        if MENTION_RE.search(text):
            res["mention"] += 1
        if viewed_frame(epath):
            res["frame"] += 1

    rt = res["recall_turns"]
    res["retarget_share"] = res["retarget"] / rt if rt else 0.0
    res["mention_share"] = res["mention"] / rt if rt else 0.0
    res["avg_block_lines"] = res["block_lines"] / rt if rt else 0.0
    res["avg_cited_coords"] = res["cited_coords"] / rt if rt else 0.0
    return res


def main(argv=None) -> int:
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--verbose", action="store_true", help="print up to 5 retargeted turns per arm")
    args = p.parse_args(argv)
    roots = roots_of(args)
    if not args.arm:
        p.error("give at least one --arm")

    results = [r for r in (scan(a, roots) for a in args.arm) if r]
    missing = [a for a in args.arm if not any(r["arm"] == a for r in results)]

    if args.json:
        print(json.dumps({"arms": results, "near_blocks": NEAR, "missing": missing}, indent=2))
        return 0

    headers = ["arm", "turns", "recall", "cited/turn", "lines/turn", "retarget", "retarget%",
               "mention", "mention%", "frame"]
    rows = []
    tot = dict.fromkeys(("turns", "recall_turns", "retarget", "mention", "frame",
                         "cited_coords", "block_lines"), 0)
    for r in results:
        rows.append([r["arm"], r["turns"], r["recall_turns"], "%.1f" % r["avg_cited_coords"],
                     "%.1f" % r["avg_block_lines"], r["retarget"],
                     "%.1f" % (100 * r["retarget_share"]), r["mention"],
                     "%.1f" % (100 * r["mention_share"]), r["frame"]])
        for k in tot:
            tot[k] += r[k]
    if rows:
        rt = tot["recall_turns"]
        rows.append(["TOTAL", tot["turns"], rt,
                     "%.1f" % (tot["cited_coords"] / rt if rt else 0),
                     "%.1f" % (tot["block_lines"] / rt if rt else 0), tot["retarget"],
                     "%.1f" % (100 * tot["retarget"] / rt if rt else 0), tot["mention"],
                     "%.1f" % (100 * tot["mention"] / rt if rt else 0), tot["frame"]])
        print_table(headers, rows)
    if missing:
        print("\nnot found: " + ", ".join(missing))

    if args.verbose:
        for r in results:
            print("\n-- %s: %d retargeted turns, first 5 --" % (r["arm"], r["retarget"]))
            for e in r["examples"]:
                print("   turn %-5d step %-7d nearest %5.1f blocks  (%d cited, %d targets)"
                      % (e["turn"], e["step"], e["nearest"], e["cited"], e["targets"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
