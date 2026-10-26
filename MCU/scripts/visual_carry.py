"""Write a VISUAL-ONLY copy of an earlier life's record, to carry with --seed-memory and
--carried-visual: the frames and where they were taken, and no word of what happened.

    python scripts/visual_carry.py <life memory dir> <out dir> [--no-index]

What the copy keeps, per life (its own record only; the lives it carried itself are left
out):

    logs.txt            the `Action N | Step S` header of every entry and its `[STATE]`
                        line (position, pitch, yaw, moved) -- nothing else
    index.jsonl         one row per episode: id, kind, first/last step, x/y/z and the
                        paths of its folder and frame (not with --no-index)
    episodes/ep_N/      observation/image.png (hard-linked) and state/state.json reduced
                        to the position and the step

Everything that names what a life did or found is dropped: plans and briefings, EXPECT
lines, notes, events, inventories, milestones and verified counts, the episode
summaries, tags and outcomes, action.json, and the life's own files (mine/). A place is
then known by its frames alone. `.visual_carry.json` in the copy (a dot file, which the
carry does not link) names the source and what was kept.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path

HEADER = re.compile(r"^(Action \d+ \| Step \d+)\b")
STATE = re.compile(r"^\[STATE\] pos=")
ROW_KEYS = ("id", "kind", "first_step", "last_step", "x", "y", "z", "path", "image")


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def visual_copy(src: Path, out: Path, *, index: bool = True) -> dict:
    src, out = Path(src), Path(out)
    if not (src / "logs.txt").exists():
        raise SystemExit(f"{src} has no logs.txt: not a life's memory dir")
    if out.exists():
        raise SystemExit(f"{out} exists: refusing to write over it")
    out.mkdir(parents=True)
    kept_lines = 0
    with (src / "logs.txt").open(encoding="utf-8", errors="replace") as fin, \
            (out / "logs.txt").open("w", encoding="utf-8") as fout:
        for ln in fin:
            m = HEADER.match(ln)
            if m:
                fout.write(m.group(1) + "\n")
                kept_lines += 1
            elif STATE.match(ln):
                fout.write(ln if ln.endswith("\n") else ln + "\n")
                kept_lines += 1
    rows = []
    if (src / "index.jsonl").exists():
        for ln in (src / "index.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            rows.append({k: r[k] for k in ROW_KEYS if k in r})
    if index and rows:
        (out / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
                                         encoding="utf-8")
    frames = 0
    for ep in sorted((src / "episodes").glob("ep_*")):
        img = ep / "observation" / "image.png"
        if img.exists():
            _link(img, out / "episodes" / ep.name / "observation" / "image.png")
            frames += 1
        st = ep / "state" / "state.json"
        if st.exists():
            try:
                d = json.loads(st.read_text(encoding="utf-8"))
            except ValueError:
                d = {}
            small = {k: d[k] for k in ("pos", "step") if k in d}
            p = out / "episodes" / ep.name / "state" / "state.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(small, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    meta = {"source": str(src), "log_lines_kept": kept_lines, "episodes": len(rows),
            "frames": frames, "index": bool(index and rows),
            "kept": ["logs.txt: Action/Step headers and [STATE] lines",
                     "index.jsonl: " + ", ".join(ROW_KEYS) if index else "no index.jsonl",
                     "episodes/*/observation/image.png", "episodes/*/state/state.json: pos, step"]}
    (out / ".visual_carry.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", type=Path, help="an earlier life's memory dir (episode_001/memory)")
    ap.add_argument("out", type=Path, help="where to write the visual-only copy (must not exist)")
    ap.add_argument("--no-index", action="store_true", help="leave index.jsonl out")
    a = ap.parse_args()
    print(json.dumps(visual_copy(a.src, a.out, index=not a.no_index), indent=1))


if __name__ == "__main__":
    main()
