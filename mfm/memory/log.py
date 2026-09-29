"""The append-only episode log: PRO-LONG's entire memory, and the first layer of MFM's.

One implementation for the memory arms. Section rendering is the caller's:
`write_initial(title, lines)` and `write_section(title, lines)` take the lines already
formatted. The section separator is the 80-`=` rule PRO-LONG uses.

Attachments (frames, screenshots) are written as files rather than inlined. That is the
point of the architecture -- grep the trace, open the payload only where it matters --
and it is the only way a long episode's pixels fit anywhere near a context window.

`publish` builds the directory the model works in. For MFM that directory is the record
itself. For the PRO-LONG arm (`log_only`) it is a view of the record: the log and the
frames it names, with whatever the model wrote there in its last turn taken back, so
that the log is the only memory that persists between turns.
"""
from __future__ import annotations

import logging
import os
import stat
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

SEPARATOR = "=" * 80

# Written by the harness, not by the agent, and required for the turn to happen at all.
# Harness-written files the log-only view keeps: the log, the system prompt and the
# frame tool a benchmark may install beside the frames (`install_zoom_tool`).
# CLAUDE.md is AGENTS.md on the Claude Code channel (the system prompt file); a codex
# workspace never holds one, so the codex arms' views are unchanged.
_HARNESS_FILES = {"logs.txt", "AGENTS.md", "CLAUDE.md", "tools/zoom.py"}

_ZOOM_SRC = Path(__file__).with_name("tools") / "zoom.py"


def install_zoom_tool(record_dir: Path) -> Path:
    """Write `tools/zoom.py` into the record workspace, executable.

    The KiCad PRO-LONG prompt has always told the model it can crop and magnify a
    saved screenshot with `./tools/zoom.py`, and the sandbox provisions a `python` with
    Pillow for exactly that -- but nothing ever wrote the file: every zoom attempt in
    the measured runs failed with "No such file or directory" (12 of 12 in one run),
    after which the model stopped trying to look at earlier screens at all. Both arms
    get it, because both arms' prompts promise it.
    """
    dst = Path(record_dir) / "tools" / "zoom.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copyfile(_ZOOM_SRC, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def _attachment_re(markers: Sequence[str]) -> re.Pattern[str]:
    """The log names its own attachments, so the log decides which the agent may see."""
    alt = "|".join(re.escape(m) for m in markers)
    return re.compile(rf"^\[(?:{alt})\] (\S+)", re.M)


class EpisodeLog:
    """Writes `logs.txt` and the attachment tree, and publishes the view the agent gets.

    `record_dir` is where the canonical record lives. For MFM that is also the directory
    the model works in; under `log_only` it is not, and `publish` decides how much of
    the record crosses into the directory that is.
    """

    def __init__(
        self,
        record_dir: Path | str,
        *,
        attachment_markers: Sequence[str] = ("FRAME", "DOC"),
        attachment_dirs: Sequence[str] = ("frames", "docs"),
        log_only: bool = False,
    ) -> None:
        """`log_only`: the PRO-LONG arm. The full log and every frame stay visible and
        the plan is carried forward as usual, but whatever the agent writes into its
        workspace is taken back at the next publish (stashed under
        `<record>/scratch/<publish>/` for the analysis), so the log is the only memory
        that persists between turns."""
        self.record_dir = Path(record_dir)
        self.log_only = log_only
        self._publish_n = 0
        self.path = self.record_dir / "logs.txt"
        self.attachment_markers = tuple(attachment_markers)
        self.attachment_dirs = tuple(attachment_dirs)
        self._attach_re = _attachment_re(self.attachment_markers)
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

        Separate from `set_plan` deliberately: in the MineExplorer port a note arriving
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

    # -- publishing ------------------------------------------------------

    def publish(self, visible: Path) -> dict[str, Any]:
        """Build the directory the agent is given.

        No-op when *visible* is the record directory itself (MFM). Under `log_only`
        *visible* is a view: `logs.txt` is copied in, the attachments it names are
        linked in, and every other file the agent left there is stashed and removed.
        """
        if visible == self.record_dir:
            return {"published": False, "attachments_visible": 0, "frames_visible": 0,
                    "removed": 0}

        visible.mkdir(parents=True, exist_ok=True)
        text = self.path.read_text(encoding="utf-8")
        (visible / "logs.txt").write_text(text, encoding="utf-8")
        allowed = set(self._attach_re.findall(text))

        for name in sorted(allowed):
            src, dst = self.record_dir / name, visible / name
            if not src.exists() or dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                # A hardlink, so a long episode's attachments are not stored twice. They
                # are written once and never rewritten, so the two names cannot diverge.
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)

        removed = 0
        self._publish_n += 1
        attachment_prefixes = tuple(f"{d}/" for d in self.attachment_dirs)
        for path in sorted(visible.rglob("*"), reverse=True):
            if not path.is_file():
                continue
            rel = path.relative_to(visible).as_posix()
            if rel in _HARNESS_FILES or rel in allowed:
                continue
            # Outside log-only the workspace is meant to persist; only attachments the
            # log does not name are taken back, and they are the harness's files.
            if not self.log_only and not rel.startswith(attachment_prefixes):
                continue
            if self.log_only and not rel.startswith(attachment_prefixes):
                stash = self.record_dir / "scratch" / f"{self._publish_n:04d}" / rel
                stash.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copyfile(path, stash)
                except OSError:
                    pass
            path.unlink(missing_ok=True)
            removed += 1

        logger.info("[log] view: %d attachment(s) visible, %d file(s) removed (log_only=%s)",
                    len(allowed), removed, self.log_only)
        return {"published": True, "attachments_visible": len(allowed),
                "frames_visible": len(allowed), "removed": removed}


def prepare_workspace(workspace: Path, view: bool,
                      resume: bool = False) -> tuple[Path, Path]:
    """Return (visible_dir, record_dir), moving aside the debris of a crashed attempt.

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
    # `view`: the model works in a view of the record (log_only), not in the record.
    record = workspace.with_name(f"{workspace.name}_record") if view else workspace
    if resume:
        if not (record / "logs.txt").exists():
            raise SystemExit(
                f"--resume was given but {record}/logs.txt does not exist; there is no "
                "run here to continue. Drop --resume to start one.")
        logger.info("[prolong] resuming into the existing workspace %s", record)
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace, record
    if (record / "logs.txt").exists():
        n, suffix = 1, ".crashed"
        while any((d.with_name(d.name + suffix)).exists() for d in {workspace, record}):
            n += 1
            suffix = f".crashed{n}"
        for d in {workspace, record}:
            if d.exists():
                d.rename(d.with_name(d.name + suffix))
                logger.warning("[prolong] found a stale workspace; moved it to %s%s", d, suffix)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace, record
