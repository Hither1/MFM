"""The workspace of one life: the directory the model runs in, and the harness's half
of what is written into it.

    logs.txt            append-only trace: every plan entry, the state that followed it,
                        the model's briefing and plan, the harness's [NOTE] and [EVENT]
                        lines. Grepped, never read whole. (Not in the direct arm.)
    grid.jsonl          the runner's own cell map (grid.py)
    references/         the contract's long sections, read on demand (`thin`)
    skills/             the skill package (skills.py)
    episodes/, index.jsonl, tools/, previous/, mine/
                        the mfm arm's: written by the episode store (episodes.py), the
                        carry (previous.py) and the model itself (own.py)

The harness owns logs.txt and the contract; whatever else the model leaves in the
workspace that its arm's contract does not keep is swept at the end of the turn.
"""
from __future__ import annotations

import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

SEPARATOR = "=" * 80

# Files the harness writes and the model must not: `assert_harness_files_intact` reports
# a shrink of one rather than silently repairing it.
HARNESS_OWNED_FILES = ("logs.txt", "AGENTS.md", "CLAUDE.md", "index.jsonl")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """A filename for an arbitrary phrase the model produced. Bounded, because these
    become paths and a model asked for a location name will occasionally return a
    paragraph."""
    s = _SLUG_RE.sub("_", (text or "").strip().lower()).strip("_")
    return (s or "unnamed")[:60]


def _xz(pos: dict[str, Any] | None) -> tuple[float, float] | None:
    if not isinstance(pos, dict):
        return None
    x, z = pos.get("x"), pos.get("z")
    return (float(x), float(z)) if x is not None and z is not None else None


def norm_yaw(yaw: float) -> float:
    """A yaw as an angle in [-180, 180), for display.

    The wire reports yaw cumulatively -- two and a half left turns print as -898 -- and
    every reader of the log was left to do the mod-360 arithmetic itself. Angles are
    equal mod 360, so normalising the displayed value changes no fact.
    """
    return (float(yaw) + 180.0) % 360.0 - 180.0


def state_line(pos: dict[str, Any] | None, prev: dict[str, Any] | None) -> str:
    """`[STATE] pos=(x, y, z) pitch=P yaw=Y moved=D`.

    The format is fixed: the prompt teaches the agent to trust this line over its own
    read of a frame, and log-analysis scripts split on it. (The yaw *value* is displayed
    normalised to [-180, 180); the format the scripts split on is unchanged.)
    """
    if not isinstance(pos, dict) or pos.get("x") is None:
        return "[STATE] unavailable"
    here, before = _xz(pos), _xz(prev)
    moved = math.dist(here, before) if here and before else 0.0
    return (
        f"[STATE] pos=({pos['x']:.2f}, {pos.get('y', 0.0):.2f}, {pos['z']:.2f}) "
        f"pitch={pos.get('pitch', 0.0):.0f} yaw={norm_yaw(pos.get('yaw', 0.0)):.0f} "
        f"moved={moved:.2f}"
    )


class MultimodalMemory:
    """Owns the directory tree, and the harness's half of what is written into it."""

    def __init__(self, root: str | Path, direct: bool = False, episodes: bool = False,
                 zoom_tool: bool = False, own: bool = False) -> None:
        # Absolute, always. The Codex backend runs with cwd == this root and resolves
        # image paths against it, so a relative root silently points nowhere.
        self.root = Path(root).resolve()
        # The direct arm: NO memory at all -- no log, no frames, no tools, no window.
        self.direct = direct
        # The MFM arm: the log plus the episode store beside it
        # (`episodes/`, `index.jsonl`, `tools/episodes.py`), kept between turns. See
        # mcu_worldmodel/episodes.py.
        assert not (episodes and direct), "the direct arm keeps no episodes"
        self.episodes = episodes
        # `own` (mcu_worldmodel/own.py): `mine/` is the model's and survives the sweep.
        self.own = bool(own)
        self.log = not direct
        # The current view is attached from ONE scratch file outside the workspace;
        # the earlier views are the episode store's (mfm arm only).
        self.attach_dir = self.root.parent / "attach"
        self.swept = 0
        self.logs_path = self.root / "logs.txt"

        self.root.mkdir(parents=True, exist_ok=True)
        self.attach_dir.mkdir(parents=True, exist_ok=True)
        if episodes and zoom_tool:
            # The mfm arm's `frames` option: the pixel-level crop tool beside
            # tools/episodes.py.
            (self.root / "tools").mkdir(parents=True, exist_ok=True)
            self._write_zoom_tool()
        if self.log:
            self.logs_path.touch()

        self._plan: str | None = None
        self._pending_briefing: str | None = None
        self._pending_notes: list[str] = []

    def _write_zoom_tool(self) -> None:
        zoom = self.root / "tools" / "zoom.py"
        if zoom.exists():
            return
        zoom.write_text(f'''#!{sys.executable}
"""Crop a frame region and magnify it, for reading detail a full frame hides.

    ./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]

x,y = top-left of the region in the frame's own pixels (640x360); the crop is scaled
4x nearest-neighbour (pixel-accurate, no smoothing) into out.png (default ./zoom.png).
Then open the result with view_image. Compare two frames by zooming the same region in
both and viewing them in sequence.
"""
import sys
from PIL import Image

frame, x, y, w, h = sys.argv[1], *map(int, sys.argv[2:6])
out = sys.argv[6] if len(sys.argv) > 6 else "zoom.png"
img = Image.open(frame).convert("RGB")
x = max(0, min(img.width - 1, x)); y = max(0, min(img.height - 1, y))
w = max(1, min(img.width - x, w)); h = max(1, min(img.height - y, h))
img.crop((x, y, x + w, y + h)).resize((w * 4, h * 4), Image.NEAREST).save(out)
print(f"wrote {{out}}: {{w}}x{{h}} region at ({{x}},{{y}}), 4x")
''', encoding="utf-8")
        zoom.chmod(0o755)

    # -- the append-only trace -------------------------------------------

    def set_plan(self, plan: str, briefing: str | None = None) -> None:
        """One analysis from the agent: the briefing is written once into the next
        section, the plan into every section it governs.

        Both, not just the plan. A log that keeps the plan and drops the briefing leaves
        the reasoning behind a stretch of actions only inside the resumed model
        conversation -- invisible to `grep`, and gone entirely on a context overflow. The
        log is supposed to be the memory of record; that means it holds the thinking too.
        """
        self._plan = (plan or "").strip() or None
        self._pending_briefing = (briefing or "").strip() or None

    def add_note(self, note: str) -> None:
        """Hold a harness-side note (a rejected claim, a dropped action) for the next
        section. Kept separate from set_plan so a note arriving on the same step as a
        fresh plan does not overwrite it."""
        note = (note or "").strip()
        if note:
            self._pending_notes.append(note)

    def take_notes(self) -> list[str]:
        """Drain the pending notes. In the direct arm they are dropped (logged by the
        agent, never served); the log arms drain them into the next section."""
        notes, self._pending_notes = self._pending_notes, []
        return notes

    #: What a workspace may hold between turns: the system prompt, the log, the turn
    #: artefacts the backend clears before every turn.
    KEEP_BETWEEN_TURNS = frozenset({
        "AGENTS.md", "logs.txt", "actions.json", "last_message.txt",
        # The claude channel's system-prompt file and the CLI's own project-state dir
        # (claude_backend.write_system_prompt). Swept, the arm lost its contract after
        # turn 1 (one run); harness-owned, so a rewrite is a fault.
        "CLAUDE.md", ".claude",
        "grid.jsonl",      # the runner's cell map (grid.py), harness-written
        "references",      # thin: the contract's long sections, read on demand
        "skills",          # skills: the meta-level skill package (skills.py), read on demand
    })

    def write_references(self, files: dict[str, str]) -> None:
        """`thin`: the contract sections moved out of AGENTS.md, one file each
        under references/ (written once, like AGENTS.md)."""
        d = self.root / "references"
        d.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            p = d / name
            if not p.exists():
                p.write_text(text, encoding="utf-8")

    def sweep_foreign(self) -> list[str]:
        """Remove whatever the model left in the workspace that the arm's contract
        does not keep: direct keeps nothing, mfm keeps the log, the
        store, the carried lives and `mine/`. Called at the end of every model turn, so
        a notes file, a zoomed PNG or a `.git` the model created never survives into the
        next turn in an arm whose protocol does not grant it."""
        keep = set(self.KEEP_BETWEEN_TURNS)
        if self.episodes:
            # `previous/`: the earlier lives' records the mfm arm carries (previous.py).
            keep |= {"episodes", "index.jsonl", "tools", "previous"}
        if self.own:
            keep.add("mine")
        removed: list[str] = []
        for p in sorted(self.root.iterdir()):
            if p.name in keep:
                continue
            try:
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed.append(p.name)
            except OSError as e:
                logger.warning(f"[memory] could not sweep {p.name}: {e}")
        if removed:
            self.swept += len(removed)
            logger.info(f"[memory] swept {len(removed)} foreign workspace entries: "
                        f"{removed[:8]}")
        return removed

    def save_frame(self, step: int, png_bytes: bytes) -> str:
        """The current view, written to the ONE scratch file outside the workspace that
        is attached to the call (never listed, overwritten every turn)."""
        path = self.attach_dir / "frame.png"
        path.write_bytes(png_bytes)
        return str(path)

    def write_initial(self, task_text: str, pos: dict | None, frame: str | None) -> None:
        if not self.log:
            return
        with self.logs_path.open("a", encoding="utf-8") as f:
            f.write(f"{SEPARATOR}\nAction 0 | Step 0 | INITIAL STATE\n\n")
            f.write(f"Task: {task_text}\n{state_line(pos, None)}\n")

    def write_action(
        self, *, action_num: int, step: int, entry_desc: str, pos: dict | None,
        prev_pos: dict | None, frame: str | None, plan_step: str = "",
        verified: str = "", events: Iterable[str] = (),
        inventory_delta: str = "", gui_open: bool | None = None,
        cursor_line: str = "",
    ) -> None:
        if not self.log:
            return
        with self.logs_path.open("a", encoding="utf-8") as f:
            head = f"{SEPARATOR}\nAction {action_num} | Step {step}"
            if plan_step:
                head += f" | Plan Step {plan_step}"
            if verified:
                head += f" | {verified}"
            f.write(head + "\n\n")
            if self._pending_briefing:
                f.write(f"[PLAN] {self._pending_briefing}\n")
                self._pending_briefing = None
            if self._plan:
                f.write(f"[PLAN] {self._plan}\n")
            f.write(f"{entry_desc}\n{state_line(pos, prev_pos)}\n")
            # What the entry actually changed in the inventory, and whether a GUI is up.
            # This is the feedback channel for GUI work: the frame shows where the cursor
            # is, and this line says whether the last click moved anything. Without it a
            # `grep` over the log cannot tell a click that landed from one that did not.
            if gui_open is not None:
                f.write(f"[GUI] open={gui_open}\n")
            if cursor_line:
                f.write(f"{cursor_line}\n")
            if inventory_delta:
                f.write(f"[INV] {inventory_delta}\n")
            for e in events:
                f.write(f"[EVENT] {e}\n")
            for n in self._pending_notes:
                f.write(f"[NOTE] {n}\n")
            self._pending_notes.clear()

    # -- integrity --------------------------------------------------------

    def snapshot_harness_files(self) -> dict[str, int]:
        return {
            rel: (self.root / rel).stat().st_size
            for rel in HARNESS_OWNED_FILES if (self.root / rel).exists()
        }

    def assert_harness_files_intact(self, before: dict[str, int]) -> list[str]:
        """Harness files only ever grow. A shrink means the agent rewrote the record it
        is supposed to be reasoning from, which invalidates every claim checked against
        it -- so this is reported, not silently repaired."""
        bad = []
        for rel, size in before.items():
            now = (self.root / rel).stat().st_size if (self.root / rel).exists() else 0
            if now < size:
                bad.append(f"{rel}: {size} -> {now} bytes")
        if bad:
            logger.error(f"[memory] agent modified harness-owned files: {bad}")
        return bad

    def archive_crashed(self) -> None:
        """Move a leftover workspace aside instead of appending a second episode to the
        same logs.txt. The debris of a crashed attempt is evidence, so it is renamed
        rather than deleted."""
        if not self.logs_path.exists() or self.logs_path.stat().st_size == 0:
            return
        n, suffix = 1, ".crashed"
        while self.root.with_name(self.root.name + suffix).exists():
            n += 1
            suffix = f".crashed{n}"
        dest = self.root.with_name(self.root.name + suffix)
        shutil.move(str(self.root), str(dest))
        logger.warning(f"[memory] stale workspace moved to {dest}")
