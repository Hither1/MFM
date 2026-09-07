"""Shared read-only helpers for the metrics kit (stdlib only).

Every script in the kit takes `--arm NAME` (repeatable) and `--root DIR` (repeatable,
defaulting to the two output roots), prints one table row per arm plus a TOTAL row, and
takes `--json` for machine output. Nothing here writes to an arm directory.
"""
import argparse, json, os, re

ROOTS = [
    "/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output",
    "/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output",
]

HEADER_RE = re.compile(r"^Action (\d+) \| Step (\d+)")
# (x, z) or (x, y, z), integers or decimals -- the form the logbook and the prompts use.
TUPLE_RE = re.compile(
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*(?:,\s*(-?\d+(?:\.\d+)?)\s*)?\)")
KWARG_RE = re.compile(r"x\s*=\s*(-?\d+(?:\.\d+)?)[^)]*?z\s*=\s*(-?\d+(?:\.\d+)?)")


def base_parser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--arm", action="append", default=[], metavar="NAME",
                   help="arm name, e.g. og14 (repeatable)")
    p.add_argument("--root", action="append", default=[], metavar="DIR",
                   help="output root to search (repeatable; default: both known roots)")
    p.add_argument("--json", action="store_true", help="machine output")
    return p


def roots_of(args) -> list:
    return args.root or ROOTS


def episode_dir(arm: str, roots) -> str:
    """<root>/<arm>_mfm/episode_001 for the first root that has it, else ''."""
    name = arm if arm.endswith("_mfm") else arm + "_mfm"
    for r in roots:
        d = os.path.join(r, name, "episode_001")
        if os.path.isdir(d):
            return d
    return ""


def read_lines(path: str) -> list:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read().splitlines()


def log_steps(lines) -> tuple:
    """(step per line, last step) from the `Action N | Step S` headers."""
    steps, cur, last = [], 0, 0
    for ln in lines:
        m = HEADER_RE.match(ln)
        if m:
            cur = int(m.group(2))
            last = max(last, cur)
        steps.append(cur)
    return steps, last


def xz_tuples(text: str) -> list:
    """World (x, z) pairs in `text`: a 3-tuple gives (x, z), a 2-tuple is already (x, z)."""
    out = []
    for a, b, c in TUPLE_RE.findall(text):
        out.append((float(a), float(c)) if c else (float(a), float(b)))
    return out


def plan_targets(text: str) -> list:
    """Coordinate targets in a plan: go_to(x=..., z=...) / x=... z=... pairs and (x, z) tuples."""
    return [(float(a), float(b)) for a, b in KWARG_RE.findall(text)] + xz_tuples(text)


def dist_xz(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def turn_files(ep: str) -> list:
    """[(turn_number, prompt_path, events_path)] sorted by turn number."""
    d = os.path.join(ep, "codex_turns")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        m = re.match(r"turn_(\d+)\.prompt\.txt$", fn)
        if m:
            n = int(m.group(1))
            out.append((n, os.path.join(d, fn),
                        os.path.join(d, "turn_%04d.events.jsonl" % n)))
    return out


def own_calls(ep: str) -> dict:
    p = os.path.join(ep, "worldmodel_report.json")
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8", errors="ignore") as fh:
            rep = json.load(fh)
    except (ValueError, OSError):
        return {}
    own = rep.get("own") or {}
    calls = own.get("calls")
    return calls if isinstance(calls, dict) else {}


def print_table(headers, rows, aligns=None):
    cols = [list(map(str, col)) for col in zip(*([headers] + [list(map(str, r)) for r in rows]))] \
        if rows else [[h] for h in headers]
    w = [max(len(c) for c in col) for col in cols]
    aligns = aligns or ["<"] + [">"] * (len(headers) - 1)
    def line(cells):
        return "  ".join(("{:%s%d}" % (aligns[i], w[i])).format(str(c))
                         for i, c in enumerate(cells)).rstrip()
    print(line(headers))
    print("  ".join("-" * x for x in w))
    for r in rows:
        print(line(r))
