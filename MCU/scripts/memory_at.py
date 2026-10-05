#!/usr/bin/env python3
"""The memory of a life as it stood at step T, as a directory `--seed-memory` takes.

    memory_at.py <memory dir> --step T --out <dir> [--history <history dir>]

A life's record is indexed by step, so the cut is exact: the log's action blocks, the
index rows, the episodes and the grid rows that end at or before T. What the model wrote
for itself under `mine/` is edited in place and has no steps; its state at T comes from
the history `mine_history.py watch` recorded beside the life. Without a history only the
whole life can be taken (T at or past its last step), and `mine/` is then the final one.

Everything else the carry would link from the life (`previous.NOT_CARRIED` names what it
would not) is linked as it is. The cut is described in `<out>/.cut.json`, a dotfile the
carry skips, so the model that receives the memory never sees it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mine_history  # noqa: E402

#: What the carry does not link from a life (mcu_worldmodel/previous.py NOT_CARRIED):
#: its machinery. Kept here by value so this script runs without the package.
NOT_CARRIED = frozenset({"AGENTS.md", "CLAUDE.md", ".claude", "tools", "attach", "previous",
                         "sites.json", "references", "actions.json", "last_message.txt",
                         "workspace.codexhome", "previous_expedition_log.txt", "__pycache__"})
#: The parts of the record that carry a step, cut below; `mine/` comes from the history.
STEPPED = frozenset({"logs.txt", "index.jsonl", "grid.jsonl", "episodes", "mine"})

_HEADER = re.compile(r"^Action \d+ \| Step (\d+)")
_RULE = re.compile(r"^={20,}\s*$")


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def _link_tree(src: Path, dst: Path) -> int:
    n = 0
    for p in src.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            _link(p, dst / p.relative_to(src))
            n += 1
    return n


def cut_log(text: str, step: int) -> tuple[str, int, int]:
    """The log up to the last action block whose header step is <= `step`.

    A block is a rule line, its `Action N | Step M` header and what follows up to the
    next rule. Returns (text, blocks kept, last step kept)."""
    lines = text.splitlines(keepends=True)
    cut = len(lines)
    kept, last = 0, 0
    for i, line in enumerate(lines):
        m = _HEADER.match(line)
        if not m:
            continue
        if int(m.group(1)) > step:
            # the rule line above the header opens the block
            cut = i - 1 if i and _RULE.match(lines[i - 1]) else i
            break
        kept, last = kept + 1, int(m.group(1))
    return "".join(lines[:cut]), kept, last


def last_step(memory: Path) -> int:
    steps = [int(m.group(1)) for line in
             (memory / "logs.txt").read_text(encoding="utf-8", errors="replace").splitlines()
             if (m := _HEADER.match(line))]
    return steps[-1] if steps else 0


def cut(memory: Path, step: int, out: Path, history: Path | None = None) -> dict:
    memory, out = Path(memory), Path(out)
    if not (memory / "logs.txt").exists():
        raise SystemExit(f"{memory} is not a life's memory dir (no logs.txt)")
    if out.exists():
        raise SystemExit(f"{out} exists")
    end = last_step(memory)
    whole = step >= end
    if history is None and not whole:
        raise SystemExit(f"step {step} is inside the life (it ends at {end}) and no --history "
                         f"was given: `mine/` at that step is not recoverable from the record")
    out.mkdir(parents=True)
    info: dict = {"source": str(memory.resolve()), "step": step, "life_last_step": end}

    text, blocks, kept_step = cut_log(
        (memory / "logs.txt").read_text(encoding="utf-8", errors="replace"), step)
    (out / "logs.txt").write_text(text, encoding="utf-8")
    info["log"] = {"action_blocks": blocks, "last_step": kept_step}

    rows, dropped = [], 0
    idx = memory / "index.jsonl"
    if idx.exists():
        for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if int(r.get("last_step") or 0) <= step:
                rows.append(r)
            else:
                dropped += 1
        (out / "index.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    files = 0
    for r in rows:
        ep = memory / r["path"]
        if ep.is_dir():
            files += _link_tree(ep, out / r["path"])
    info["episodes"] = {"kept": len(rows), "dropped": dropped, "files": files}

    grid = memory / "grid.jsonl"
    if grid.exists():
        keep = [line for line in grid.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip() and int(json.loads(line).get("step") or 0) <= step]
        (out / "grid.jsonl").write_text("".join(line + "\n" for line in keep), encoding="utf-8")
        info["grid_rows"] = len(keep)

    if history is not None:
        row = mine_history.at(Path(history), step)
        if row is None:
            info["mine"] = {"from": "history", "files": 0, "row_step": None}
        else:
            for rel, sha in row["files"].items():
                target = out / "mine" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(history) / "blobs" / sha, target)
            info["mine"] = {"from": "history", "files": len(row["files"]),
                            "row_step": row["step"], "row_t": row["t"]}
    elif (memory / "mine").is_dir():
        info["mine"] = {"from": "final", "files": _link_tree(memory / "mine", out / "mine")}

    other = []
    for p in sorted(memory.iterdir()):
        if p.name in NOT_CARRIED or p.name in STEPPED or p.name.startswith("."):
            continue
        if p.is_dir():
            _link_tree(p, out / p.name)
        elif p.is_file():
            _link(p, out / p.name)
        other.append(p.name)
    info["linked_whole"] = other
    (out / ".cut.json").write_text(json.dumps(info, indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8")
    return info


#: The directories under mine/ that hold scripts the model can write.
SCRIPT_DIRS = ("procedures", "reflexes", "tools")


def shipped_scripts(memory: Path) -> dict[str, Path]:
    """The example scripts a life finds under skills/*/scripts and may copy into mine/
    unchanged on its first turn, by file name."""
    return {p.name: p for p in sorted((memory / "skills").glob("*/scripts/*.py"))} \
        if (memory / "skills").is_dir() else {}


def lives_of(memory: Path) -> list[Path]:
    """The lives a seed dir brings (previous.lives_of, by value): the lives it carried
    under previous/, oldest first, then itself."""
    prev = memory / "previous"
    lives = sorted(prev.glob("life_*"), key=lambda p: int(p.name.split("_")[1])) \
        if prev.is_dir() else []
    return lives + [memory]


def own_files(life: Path, shipped: dict[str, Path] | None = None) -> dict[str, str]:
    """What the model wrote as a script in one life: `mine/<dir>/<name>.py` -> "written"
    when no shipped example has that name, "edited" when one has and the bytes differ.
    A shipped example copied unchanged is not the model's."""
    shipped = shipped_scripts(life) if shipped is None else shipped
    out: dict[str, str] = {}
    for d in SCRIPT_DIRS:
        for p in sorted((life / "mine" / d).glob("*.py")):
            ex = shipped.get(p.name)
            if ex is None:
                out[f"{d}/{p.name}"] = "written"
            elif ex.read_bytes() != p.read_bytes():
                out[f"{d}/{p.name}"] = "edited"
    return out


def strip_own(memory: Path, out: Path) -> dict:
    """A copy of a seed dir with every script the model wrote removed, in every life it
    brings: the diary (notes, working, looks, the record) without the skills. Written
    scripts are dropped, edited shipped ones put back as shipped. The rest is hard-linked
    as it is; `<out>/.strip.json` says what went (a dotfile the carry skips)."""
    if out.exists():
        raise SystemExit(f"{out} exists")
    shipped_top = shipped_scripts(memory)
    info: dict = {"source": str(memory), "lives": {}}
    for life in lives_of(memory):
        rel = life.relative_to(memory)
        dst = out / rel
        shipped = shipped_scripts(life) or shipped_top
        own = own_files(life, shipped)
        for p in life.rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts or p.name.startswith("."):
                continue
            r = p.relative_to(life)
            if r.parts[0] == "previous":
                continue        # the carried lives are copied as lives of their own
            key = f"{r.parts[1]}/{r.name}" if r.parts[0] == "mine" and len(r.parts) == 3 else None
            if key in own:
                if own[key] == "edited":
                    _link(shipped[r.name], dst / r)
                continue
            _link(p, dst / r)
        info["lives"][str(rel)] = own
    out.mkdir(parents=True, exist_ok=True)
    (out / ".strip.json").write_text(json.dumps(info, indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("memory", type=Path, help="output/<arm>/episode_001/memory")
    ap.add_argument("--step", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--history", type=Path, default=None,
                    help="the directory `mine_history.py watch` wrote beside the life")
    ap.add_argument("--own", action="store_true",
                    help="only list the scripts the model wrote, per life the dir brings")
    ap.add_argument("--strip-own", action="store_true",
                    help="write to --out a copy of the dir with those scripts removed")
    args = ap.parse_args()
    if args.own:
        result = {str(life.relative_to(args.memory)): own_files(life)
                  for life in lives_of(args.memory)}
    elif args.strip_own:
        if args.out is None:
            ap.error("--strip-own needs --out")
        result = strip_own(args.memory, args.out)
    else:
        if args.step is None or args.out is None:
            ap.error("a cut needs --step and --out")
        result = cut(args.memory, args.step, args.out, args.history)
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
