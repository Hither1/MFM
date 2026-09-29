"""`--visual-only`: the model sees the world through the frame alone.

User, 2026-09-07 (before sleeping): "只有 visual input 的 settings" -- to make vision
load-bearing and to align with wz1119/Codex-Minecraft-Gameplay, where the agent plays from
screenshots, bounded key/mouse input and checked sequences, with no coordinates at all;
and "事件帧不给": no event sheet is pushed, the model queries the frames in its memory.

What changes for the MODEL (the runner keeps every number for its own reflexes and
guards -- the ablation is what the model is served, not what the harness knows):
- the turn prompt carries no [STATE]/vitals/inventory/hotbar/cursor/[GRID] text, no
  [MAP], no retrieval block, no event sheet; only the milestone ledger, the step budget,
  the [RECENT] outcomes (without distances) and the harness notes;
- logs.txt carries no [STATE]/[GUI]/[CURSOR]/[INV] lines; harness notes are scrubbed of
  coordinates and headings (`scrub`); the episodes' state.json and index.jsonl carry no
  position, inventory or vitals; no grid.jsonl is written into the workspace;
- the procedure set is VISUAL_ATOMS: the atoms minus the five that take a coordinate.
"""
from __future__ import annotations

import re

_COORD3 = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)")
_COORD2 = re.compile(r"\(\s*-?\d{2,}(?:\.\d+)?\s*,\s*-?\d{2,}(?:\.\d+)?\s*\)")
_POS = re.compile(r"\s*pos=\([^)]*\)")
_YAW = re.compile(r"\s*(?:facing\s+)?(?:yaw|heading)\s*[-+]?\d+(?:\.\d+)?(?:\s*degrees)?", re.I)
_XZ_WORDS = re.compile(r"\b(?:x|y|z)\s*=\s*-?\d+(?:\.\d+)?(?:\s*,\s*(?:x|y|z)\s*=\s*-?\d+(?:\.\d+)?)*", re.I)


def scrub(text: str) -> str:
    """A harness note without the numbers the model does not have in this run:
    coordinates become "a spot near you", headings and `pos=(...)` are dropped."""
    t = _POS.sub("", text)
    t = _COORD3.sub("(a spot near you)", t)
    t = _COORD2.sub("(a spot)", t)
    t = _XZ_WORDS.sub("a spot near you", t)
    t = _YAW.sub("", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


#: The contract section (kept in the thin contract: it sits before the first moved heading).
VISUAL_NOTE = """\
**Visual input only.** In this run the world reaches you through the FRAME alone, like a
player at the screen: no [STATE] line, no position or heading numbers, no inventory or
vitals text, no [MAP], no retrieval block, no event sheet. Read from the attached view:
where you are and what is ahead, your footing, the light, and the HUD at the bottom --
hearts = health, drumsticks = hunger, the hotbar with its item icons and counts, the
selected slot's brighter border -- and any open screen with its slots. Text still tells
you the milestone ledger and the step budget (the task's clock), each entry's outcome
(what broke, what was picked up, what was refused and why, damage taken) and the
harness's notes, with places named only as "a spot near you". Places live in your
memory of FRAMES: every entry's starting view is `episodes/ep_NNNNNN/observation/
image.png`; `./tools/episodes.py --last N | --steps A B | --tag T | --grep text` lists
them with their paths; `view_image` opens one; a script (numpy, PIL) can compare many.
Nothing is shown to you unasked: when a note says something happened, LOOK at the
frames yourself, and keep your own landmarks in your briefing (what you saw, which way
you turned). Procedures that take a coordinate (go_to, look_at, look_abs, place_at,
use_at) are not in this run's set: steer with `look(pitch=, yaw=)` deltas and raw
`camera`, walk with `forward` ticks and `watch(until=...)`, mine with `mine_ahead`,
place a block by aiming at a face and pressing `use`."""

#: The line under the procedure index.
VISUAL_LINE = ("This run's procedure set is the VISUAL ATOMS above: none takes a coordinate, "
               "because you have none -- steer by the frame with `look` deltas, raw keys and "
               "`watch`; the task-shaped macros are not provided.")
