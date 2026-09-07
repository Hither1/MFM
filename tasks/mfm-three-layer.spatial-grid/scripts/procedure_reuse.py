"""Which of an arm's own scripts it inherited from a previous life, and which it actually ran.

    python procedure_reuse.py --arm og14 --arm og19
    python procedure_reuse.py --arm og19 --quiet         # table only, no per-procedure lines
    python procedure_reuse.py --arm og14 --json

An arm's procedures are `memory/mine/procedures/*.py`; a carried life's are
`memory/previous/life_*/mine/procedures/*.py`. A procedure is INHERITED when a previous life
has a file of the same name, and `same` when the sha1 of the bytes also matches -- inherited
but not `same` means the arm edited what it was handed. Call counts come from
worldmodel_report.json `own.calls`, so "calls to inherited" is uptake of carried code and
"calls to new" is uptake of code this life wrote. A name in own.calls with no file on disk is
reported as `missing_file` rather than silently dropped.

The digest line is separate bookkeeping: the size of `mine/digest.md` (or `mine/GUIDE.md`),
and how many turns' events.jsonl mention either name at all -- a mention is the model reading
or writing the file in a shell command, or naming it in a message, not proof it used it.
"""
import glob, hashlib, json, os, sys

from _kit import (base_parser, episode_dir, own_calls, print_table, roots_of, turn_files)


def sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def procs(d: str) -> dict:
    """{name: sha1} for the .py files in a procedures directory."""
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "*.py"))):
        try:
            out[os.path.basename(p)[:-3]] = sha1(p)
        except OSError:
            pass
    return out


def digest_mentions(ep: str) -> tuple:
    turns = turn_files(ep)
    hits = 0
    for _, _, epath in turns:
        if not os.path.isfile(epath):
            continue
        with open(epath, encoding="utf-8", errors="ignore") as fh:
            if any("digest.md" in ln or "GUIDE.md" in ln for ln in fh):
                hits += 1
    return hits, len(turns)


def scan(arm: str, roots) -> dict:
    ep = episode_dir(arm, roots)
    if not ep:
        return {}
    mem = ep + "/memory"
    mine = procs(mem + "/mine/procedures")

    prev = {}          # name -> {life: sha1}
    lives = 0
    for d in sorted(glob.glob(mem + "/previous/life_*")):
        pd = os.path.join(d, "mine", "procedures")
        if not os.path.isdir(pd):
            continue
        lives += 1
        for name, h in procs(pd).items():
            prev.setdefault(name, {})[os.path.basename(d)] = h

    calls = own_calls(ep)
    items, n_inh, n_new, c_inh, c_new = [], 0, 0, 0, 0
    for name, h in sorted(mine.items()):
        carried = prev.get(name, {})
        same = h in carried.values()
        n = calls.get(name, 0)
        if carried:
            n_inh += 1
            c_inh += n
        else:
            n_new += 1
            c_new += n
        items.append({"name": name, "inherited": bool(carried), "same_content": same,
                      "calls": n, "in_lives": sorted(carried)})
    orphans = {k: v for k, v in calls.items() if k not in mine}

    dsize, dname = 0, ""
    for cand in ("digest.md", "GUIDE.md"):
        p = os.path.join(mem, "mine", cand)
        if os.path.isfile(p):
            dsize, dname = os.path.getsize(p), cand
            break
    hits, turns = digest_mentions(ep)

    return {"arm": arm, "episode": ep, "procedures": len(mine), "inherited": n_inh,
            "new": n_new, "same_content": sum(1 for i in items if i["same_content"]),
            "calls_inherited": c_inh, "calls_new": c_new,
            "calls_missing_file": sum(orphans.values()), "missing_file": sorted(orphans),
            "prev_lives_with_mine": lives, "prev_procedures": len(prev),
            "digest": dname, "digest_bytes": dsize,
            "digest_turns": hits, "turns": turns, "items": items}


def main(argv=None) -> int:
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--quiet", action="store_true", help="table only, skip the per-procedure lines")
    args = p.parse_args(argv)
    roots = roots_of(args)
    if not args.arm:
        p.error("give at least one --arm")

    results = [r for r in (scan(a, roots) for a in args.arm) if r]
    missing = [a for a in args.arm if not any(r["arm"] == a for r in results)]

    if args.json:
        print(json.dumps({"arms": results, "missing": missing}, indent=2))
        return 0

    keys = ["procedures", "inherited", "same_content", "new", "calls_inherited", "calls_new",
            "calls_missing_file", "digest_bytes", "digest_turns", "turns"]
    headers = ["arm", "procs", "inherit", "same", "new", "calls_inh", "calls_new",
               "calls_orph", "digest_B", "digest_turns", "turns"]
    rows = [[r["arm"]] + [r[k] for k in keys] for r in results]
    if rows:
        rows.append(["TOTAL"] + [sum(r[k] for r in results) for k in keys])
        print_table(headers, rows)
    if missing:
        print("\nnot found: " + ", ".join(missing))

    if not args.quiet:
        for r in results:
            print("\n-- %s: %d procedure(s), digest %s (%d B), named in %d/%d turns --"
                  % (r["arm"], r["procedures"], r["digest"] or "none", r["digest_bytes"],
                     r["digest_turns"], r["turns"]))
            for i in r["items"]:
                tag = ("inherited/same" if i["same_content"] else
                       "inherited/edited" if i["inherited"] else "new")
                print("   %-24s %-16s %4d calls  %s"
                      % (i["name"], tag, i["calls"], ",".join(i["in_lives"])))
            if r["missing_file"]:
                print("   own.calls names with no file on disk: " + ", ".join(r["missing_file"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
