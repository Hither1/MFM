#!/usr/bin/env python
"""Compose one labelled contact sheet from a staged endgame run.

The frames are the evidence; this is just the index -- one panel per milestone, captioned
with the identity the scorer uses and whether the run's own statistics recorded it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

PANELS = [
    ("kill_blaze", "12_blaze0_aimed", "blaze in the crosshair, Nether fortress"),
    ("kill_blaze", "12_blaze0_killed", "blaze dead, rod on the floor"),
    ("blaze_rod", "13_blaze_rod0_picked_up", "rod picked up"),
    ("blaze_powder", "20_blaze_powder_output_shown", "rod -> powder in the 2x2 grid"),
    ("end_stone", "31_end_island", "the End island"),
    ("end_stone", "33_end_stone_broken", "end stone mined"),
    ("kill_enderman", "34_enderman0_aimed", "enderman at melee range"),
    ("ender_pearl", "35_ender_pearl1_picked_up", "pearl picked up"),
    ("eye_of_ender", "36_eye_of_ender_output_shown", "powder + pearl -> eye of ender"),
]

#: The dragon usually comes from a separate episode -- the kill is flaky enough to be worth
#: running on its own -- so its two panels name their own run.
DRAGON = [
    ("kill_ender_dragon", "40_dragon_portrait0_0", "held in hover, 22 blocks out"),
    ("kill_ender_dragon", "41_dragon_fight0_swing0", "the death beams"),
]


def find(frames: Path, stem: str) -> Path | None:
    hits = sorted(frames.glob(f"*_{stem}.png"))
    return hits[0] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="an endgame_frames output directory")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--dragon-alive", help="RUN:STEM for the living-dragon panel")
    ap.add_argument("--dragon-death", help="RUN:STEM for the death panel")
    args = ap.parse_args()

    run = Path(args.run)
    frames = run / "frames"
    achieved = set()
    mt = run / "milestone_tracking.json"
    if mt.exists():
        achieved = {m["identity"] for m in json.loads(mt.read_text())["milestones"]}

    wanted = [(i, s_, c, frames) for i, s_, c in PANELS]
    for arg, (identity, stem, caption) in zip((args.dragon_alive, args.dragon_death),
                                              DRAGON):
        if arg:
            run_dir, _, stem = arg.rpartition(":")
            dragon_run = Path(run_dir)
            if (dragon_run / "milestone_tracking.json").exists():
                achieved |= {m["identity"] for m in json.loads(
                    (dragon_run / "milestone_tracking.json").read_text())["milestones"]}
            wanted.append((identity, stem, caption, dragon_run / "frames"))

    panels = []
    for identity, stem, caption, frames_dir in wanted:
        path = find(frames_dir, stem)
        if path is None:
            continue
        img = cv2.imread(str(path))
        if img is None:
            continue
        img = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA)
        bar = np.full((54, 480, 3), 22, np.uint8)
        mark = "scored" if identity in achieved else "not scored"
        colour = (120, 230, 120) if identity in achieved else (120, 120, 235)
        cv2.putText(bar, identity, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                    (240, 240, 240), 1, cv2.LINE_AA)
        cv2.putText(bar, f"[{mark}]", (8 + 11 * len(identity), 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, colour, 1, cv2.LINE_AA)
        cv2.putText(bar, caption, (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (185, 185, 185), 1, cv2.LINE_AA)
        panels.append(np.vstack([img, bar]))

    cols = args.cols
    rows = [panels[i:i + cols] for i in range(0, len(panels), cols)]
    ph, pw = panels[0].shape[:2]
    blank = np.full((ph, pw, 3), 12, np.uint8)
    grid = np.vstack([np.hstack(r + [blank] * (cols - len(r))) for r in rows])
    out = Path(args.out or (run / "endgame_contact_sheet.png"))
    cv2.imwrite(str(out), grid)
    print(f"{len(panels)} panels -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
