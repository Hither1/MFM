"""The append-only episode log, the first layer of MFM's memory on KiCad.

The log follows the design of PRO-LONG, whose whole memory is such a log; the section
separator is the 80-`=` rule PRO-LONG uses. Section rendering is the caller's:
`write_initial(title, lines)` and `write_section(title, lines)` take the lines already
formatted.

Attachments (frames, screenshots) are written as files rather than inlined. That is the
point of the architecture -- grep the trace, open the payload only where it matters --
and it is the only way a long episode's pixels fit anywhere near a context window.

The model works in the record directory itself.
"""
from __future__ import annotations

import logging
import stat
import shutil
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

SEPARATOR = "=" * 80

_ZOOM_SRC = Path(__file__).with_name("tools") / "zoom.py"


def install_zoom_tool(record_dir: Path) -> Path:
    """Write `tools/zoom.py` into the record workspace, executable.

    The KiCad system prompt tells the model it can crop and magnify a saved screenshot
    with `./tools/zoom.py`, and the sandbox provisions a `python` with Pillow for exactly
    that. Before this function nothing wrote the file: every zoom attempt in the
    measured runs failed with "No such file or directory" (12 of 12 in one run), after
    which the model stopped trying to look at earlier screens at all.
    """
    dst = Path(record_dir) / "tools" / "zoom.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copyfile(_ZOOM_SRC, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


class EpisodeLog:
    """Writes `logs.txt` and the attachment tree under `record_dir`, the directory the
    model works in."""

    def __init__(
        self,
        record_dir: Path | str,
        *,
        attachment_dirs: Sequence[str] = ("frames", "docs"),
    ) -> None:
        self.record_dir = Path(record_dir)
        self.path = self.record_dir / "logs.txt"
        self.attachment_dirs = tuple(attachment_dirs)
        self.record_dir.mkdir(parents=True, exist_ok=True)
        for sub in self.attachment_dirs:
            (self.record_dir / sub).mkdir(parents=True, exist_ok=True)
        self.path.touch()
        self._pending_plan: str | None = None
        self._pending_briefing: str | None = None
        self._pending_notes: list[str] = []

    # -- writing ---------------------------------------------------------

    def set_plan(self, plan: str, briefing: str | None = None) -> None:
        """Take one analysis: the briefing and the plan are each written once, into the
        next section."""
        self._pending_plan = (plan or "").strip() or None
        self._pending_briefing = (briefing or "").strip() or None

    def add_note(self, note: str) -> None:
        """Hold a runner-side note (a rejected artifact, an ESC refusal) until the next
        section.

        Separate from `set_plan` deliberately: in an earlier version a note arriving
        in the same step as a fresh plan overwrote it, so the analyzer's own reasoning
        vanished from the log at exactly the steps where it was being overruled.
        """
        note = (note or "").strip()
        if note:
            self._pending_notes.append(note)

    def save_attachment(self, rel_name: str, payload: bytes | str) -> str:
        """Write one attachment under the record dir and return its log-visible path."""
        path = self.record_dir / rel_name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        else:
            path.write_text(payload, encoding="utf-8")
        return rel_name

    def write_initial(self, title: str, lines: Iterable[str]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"{SEPARATOR}\n")
            f.write(f"{title}\n\n")
            for line in lines:
                f.write(f"{line}\n")

    @staticmethod
    def _write_plan(f: Any, plan: str | None) -> None:
        if plan:
            f.write(f"[PLAN]\n{plan}\n\n")

    def _write_pending(self, f: Any) -> None:
        """The briefing, the plan, then the notes."""
        self._write_plan(f, self._pending_briefing)
        self._pending_briefing = None
        self._write_plan(f, self._pending_plan)
        self._pending_plan = None
        for note in self._pending_notes:
            f.write(f"[NOTE] {note}\n")
        self._pending_notes.clear()

    def write_section(self, title: str, lines: Iterable[str]) -> None:
        """One append-only section: the pending plan and notes, then the trace."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n{SEPARATOR}\n")
            f.write(f"{title}\n\n")
            self._write_pending(f)
            for line in lines:
                f.write(f"{line}\n")

    def append_lines(self, lines: Iterable[str], plan: str | None = None) -> None:
        """Append to the section already open, rather than starting a new one.

        An arm whose section is one *turn* (the GUI episode) knows half of it -- the
        actions taken, the note the agent chose to carry forward -- only after the
        analyzer has seen the other half.
        """
        with self.path.open("a", encoding="utf-8") as f:
            self._write_plan(f, plan)
            for note in self._pending_notes:
                f.write(f"[NOTE] {note}\n")
            self._pending_notes.clear()
            for line in lines:
                f.write(f"{line}\n")


def prepare_workspace(workspace: Path, resume: bool = False) -> Path:
    """Return the workspace (absolute), moving aside the debris of a crashed attempt.

    Without `resume`, reaching here means this episode has no result yet, so a
    workspace still sitting in place is a crash: left alone it would append a second
    episode to the same append-only `logs.txt` -- two initial states in one file -- and
    AGENTS.md's write-once guard would keep the *old* system prompt. Move it aside
    rather than deleting it: the crashed attempt is still evidence.

    With `resume`, that same workspace is the point: the caller is continuing the run
    that built this directory, so the log and the frames must survive untouched.

    Absolute from here on. Codex is run with cwd == the visible workspace, and every
    path derived from this one (`-i` frames, `-o last_message.txt`) is handed to codex
    verbatim; a relative workspace made all of them resolve against the wrong directory.
    """
    workspace = Path(workspace).resolve()
    if resume:
        if not (workspace / "logs.txt").exists():
            raise SystemExit(
                f"--resume was given but {workspace}/logs.txt does not exist; there is no "
                "run here to continue. Drop --resume to start one.")
        logger.info("[log] resuming into the existing workspace %s", workspace)
        return workspace
    if (workspace / "logs.txt").exists():
        n, suffix = 1, ".crashed"
        while workspace.with_name(workspace.name + suffix).exists():
            n += 1
            suffix = f".crashed{n}"
        workspace.rename(workspace.with_name(workspace.name + suffix))
        logger.warning("[log] found a stale workspace; moved it to %s%s", workspace, suffix)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace
