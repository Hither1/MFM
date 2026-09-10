"""What a life built for itself under `mine/`, and how much of it was inherited.

    python selfimprove.py <memory dir>...          # .../episode_001/memory
    python selfimprove.py <memory dir>... --quiet  # the table only

Source: the workspace on disk (read-only). Everything is counted by file name and, for
the record tools, by file content:

  procedures    `mine/procedures/*.py`. CARRIED when a file of the same name exists under
                any `previous/life_*/mine/procedures/`; NEW otherwise. (Same name, not
                same bytes -- an edited carried procedure is still carried.)
  reflexes      `mine/reflexes/*.py` outside the four the workspace ships as examples
                (lava_ahead, fell, hit, starving): a reflex class the life invented.
  record tools  any `.py` under `mine/` whose text names `logs.txt`, `index.jsonl` or
                `episodes` -- a script the life wrote to read its own record rather than
                to act in the world.
  skills        entries under `mine/skills/`, if the life made any.
  archives      files matching `working_archive*` or `*_history_*` anywhere under `mine/`:
                the life rotating its own working memory.

Nothing here says a file was USED; procedure_reuse.py answers that from the report's
call counts.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import print_table                                            # noqa: E402

EXAMPLE_REFLEXES = {"lava_ahead", "fell", "hit", "starving"}
RECORD_MARKS = ("logs.txt", "index.jsonl", "episodes")


def names(pattern):
    return sorted({os.path.basename(p)[:-3] for p in glob.glob(pattern)})


def reads_record(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return False
    return any(m in text for m in RECORD_MARKS)


def scan(mem):
    mine = os.path.join(mem, "mine")
    procs = names(os.path.join(mine, "procedures", "*.py"))
    carried_pool = set()
    for d in sorted(glob.glob(os.path.join(mem, "previous", "life_*", "mine", "procedures"))):
        carried_pool |= set(names(os.path.join(d, "*.py")))
    reflexes = names(os.path.join(mine, "reflexes", "*.py"))
    tools = sorted(os.path.relpath(p, mine)
                   for p in glob.glob(os.path.join(mine, "**", "*.py"), recursive=True)
                   if reads_record(p))
    skills = sorted(os.path.basename(p)
                    for p in glob.glob(os.path.join(mine, "skills", "*")))
    archives = sorted(
        os.path.relpath(p, mine)
        for p in glob.glob(os.path.join(mine, "**", "*"), recursive=True)
        if os.path.isfile(p) and (os.path.basename(p).startswith("working_archive")
                                  or "_history_" in os.path.basename(p)))
    return {"procedures": procs,
            "carried": [p for p in procs if p in carried_pool],
            "new": [p for p in procs if p not in carried_pool],
            "lives_carried": len(glob.glob(os.path.join(mem, "previous", "life_*"))),
            "new_reflexes": [r for r in reflexes if r not in EXAMPLE_REFLEXES],
            "reflexes": reflexes, "record_tools": tools, "skills": skills,
            "archives": archives}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("memory", nargs="+", help="a run's memory directory (holding mine/)")
    ap.add_argument("--quiet", action="store_true", help="table only, no per-life names")
    args = ap.parse_args(argv)

    rows, data = [], {}
    for mem in args.memory:
        name = os.path.basename(os.path.dirname(os.path.dirname(mem.rstrip("/")))) or mem
        s = data[name] = scan(mem)
        rows.append([name, s["lives_carried"], len(s["procedures"]), len(s["carried"]),
                     len(s["new"]), len(s["new_reflexes"]), len(s["record_tools"]),
                     len(s["skills"]), len(s["archives"])])
    print_table(["life", "lives carried", "procedures", "carried", "new", "new reflexes",
                 "record tools", "skills", "archives"], rows)
    if args.quiet:
        return 0
    for name, s in data.items():
        for label in ("carried", "new", "new_reflexes", "record_tools", "skills", "archives"):
            if s[label]:
                print(f"{name} {label}: " + ", ".join(s[label]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
