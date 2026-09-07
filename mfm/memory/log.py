"""The append-only episode log that is PRO-LONG's entire memory mechanism.

One implementation for both benchmarks. It is the KiCad port's `prolong_search/log.py`
(itself a near-verbatim port of MineExplorer's `prolong_mc/log.py`) with the two things
the MCU copy did differently folded in as options:

  persistent_plan   MCU writes the model's [PLAN] into *every* section until the next
                    analysis replaces it, and the briefing once; the search and GUI
                    ports write a one-shot plan. `set_plan(plan, briefing=None)` serves
                    both.
  window == -1      MCU's No-Log control: no log file at all, only the frame the turn
                    attaches.

Section rendering is the caller's: `write_initial(title, lines)` and
`write_section(title, lines)` take the lines already formatted, so the MCU state block
and the KiCad [FEEDBACK]/[SCREEN] lines are the same writer. The section separator is
the 80-`=` rule PRO-LONG uses, because the log-window ablation splits on it, and
`publish` enforces the ablations by *building the directory the agent sees* rather than
by asking it not to look.

Attachments (frames, screenshots, documents) are written as files rather than inlined.
That is the point of the architecture -- grep the trace, open the payload only where it
matters -- and it is the only way a long episode's pixels fit anywhere near a context
window.
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
# Harness-written files an ablation view keeps: the log, the system prompt, the frame
# tool a benchmark may install beside the frames (`install_zoom_tool`), and the netlist
# read-back a benchmark may refresh from the environment (`netlist.txt`; KiCad's
# `--netlist-readback`). Naming a file here costs nothing while no arm writes it.
_HARNESS_FILES = {"logs.txt", "AGENTS.md", "tools/zoom.py", "netlist.txt"}

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

    `record_dir` is where the canonical record lives. In the unablated arm that is also
    the directory Codex works in; under an ablation it is not, and `publish` is what
    decides how much of the record crosses into the directory that is.
    """

    def __init__(
        self,
        record_dir: Path | str,
        *,
        attachment_markers: Sequence[str] = ("FRAME", "DOC"),
        attachment_dirs: Sequence[str] = ("frames", "docs"),
        stateless: bool = False,
        persistent_plan: bool = False,
        log_only: bool = False,
    ) -> None:
        """`log_only`: the log-only ablation (KiCad `prolong-logonly`, 2026-09-06). The
        full log and every frame stay visible, the plan is carried forward as usual,
        but whatever the agent writes into its workspace is taken back at the next
        publish (stashed under `<record>/scratch/<publish>/` for the analysis), so the
        log is the only memory that persists between turns. The PRO-LONG baseline's
        model kept a `plan.txt` in 20 of 24 KiCad tasks, a second channel its
        protocol never named."""
        self.record_dir = Path(record_dir)
        self.log_only = log_only
        self._publish_n = 0
        self.path = self.record_dir / "logs.txt"
        self.plans_path = self.record_dir / "plans.txt"
        self.attachment_markers = tuple(attachment_markers)
        self.attachment_dirs = tuple(attachment_dirs)
        self._attach_re = _attachment_re(self.attachment_markers)
        self.stateless = stateless
        self.persistent_plan = persistent_plan
        self.record_dir.mkdir(parents=True, exist_ok=True)
        for sub in self.attachment_dirs:
            (self.record_dir / sub).mkdir(parents=True, exist_ok=True)
        self.path.touch()
        self._pending_plan: str | None = None
        self._plan: str | None = None
        self._pending_briefing: str | None = None
        self._pending_notes: list[str] = []

    # -- writing ---------------------------------------------------------

    def set_plan(self, plan: str, briefing: str | None = None) -> None:
        """Take one analysis.

        The briefing is written once, into the next section. The plan is written into
        the next section and, under `persistent_plan`, into every section after it until
        the next analysis replaces it: the log's definition includes "your own prior
        analyses", and the section a `tail` lands on always says what the agent was
        doing when it issued that action.
        """
        plan = (plan or "").strip() or None
        if self.persistent_plan:
            self._plan = plan
        else:
            self._pending_plan = plan
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

    def _write_plan(self, f: Any, title: str, plan: str | None) -> None:
        """Emit one [PLAN] block, honouring the stateless ablation.

        Under stateless the plan is kept for our records but is not carried forward: the
        next turn sees only the objective trace. Shared by both writers so an ablation
        cannot bind on one path and leak on the other.
        """
        if not plan:
            return
        block = f"[PLAN]\n{plan}\n"
        if self.stateless:
            with self.plans_path.open("a", encoding="utf-8") as pf:
                pf.write(f"\n{SEPARATOR}\n{title}\n{block}")
        else:
            f.write(f"{block}\n")

    def _write_pending(self, f: Any, title: str) -> None:
        """The briefing (once), the plan (once, or every section), then the notes."""
        if self._pending_briefing:
            self._write_plan(f, title, self._pending_briefing)
            self._pending_briefing = None
        if self.persistent_plan:
            self._write_plan(f, title, self._plan)
        else:
            self._write_plan(f, title, self._pending_plan)
            self._pending_plan = None
        for note in self._pending_notes:
            f.write(f"[NOTE] {note}\n")
        self._pending_notes.clear()

    def write_section(self, title: str, lines: Iterable[str],
                      plans_title: str | None = None) -> None:
        """One append-only section: the pending plan and notes, then the trace.

        `plans_title` names the section in `plans.txt` under the stateless ablation
        when that should differ from the log's header (MCU writes `Action N` there).
        """
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n{SEPARATOR}\n")
            f.write(f"{title}\n\n")
            self._write_pending(f, plans_title or title)
            for line in lines:
                f.write(f"{line}\n")

    def append_lines(self, lines: Iterable[str], plan: str | None = None,
                     title: str = "") -> None:
        """Append to the section already open, rather than starting a new one.

        An arm whose section is one *turn* (the GUI episode) knows half of it -- the
        actions taken, the note the agent chose to carry forward -- only after the
        analyzer has seen the other half. Two sections per turn would work but would
        silently redefine `--log-window N`, whose unit is documented as N sections.
        """
        with self.path.open("a", encoding="utf-8") as f:
            self._write_plan(f, title, plan)
            for note in self._pending_notes:
                f.write(f"[NOTE] {note}\n")
            self._pending_notes.clear()
            for line in lines:
                f.write(f"{line}\n")

    # -- reading ---------------------------------------------------------

    def sections(self, titles_startswith: str = "") -> list[tuple[str, str]]:
        """The log as (title, body) pairs, in order. Read from disk, because the log --
        not this object -- is the record, and a resumed episode has sections no live
        instance wrote."""
        if not self.path.exists():
            return []
        out: list[tuple[str, str]] = []
        for chunk in self.path.read_text(encoding="utf-8").split(f"{SEPARATOR}\n"):
            if not chunk.strip():
                continue
            title, _, body = chunk.partition("\n")
            title = title.strip()
            if titles_startswith and not title.startswith(titles_startswith):
                continue
            out.append((title, body.strip("\n")))
        return out

    def truncate_to(self, n_questions: int) -> int:
        """Drop every `Question k` section with k >= n_questions; return how many.

        A run that dies mid-question has already appended that question's section but
        not its checkpoint record, so a resume would append the section a second time.
        Trimming to the checkpoint first keeps the log and the checkpoint agreeing.
        """
        if not self.path.exists():
            return 0
        text = self.path.read_text(encoding="utf-8")
        marker = f"\n{SEPARATOR}\nQuestion {n_questions} |"
        at = text.find(marker)
        if at < 0:
            return 0
        kept = text[:at + 1]
        dropped = sum(1 for chunk in text[at:].split(f"{SEPARATOR}\n")
                      if chunk.strip().startswith("Question "))
        self.path.write_text(kept, encoding="utf-8")
        return dropped

    # -- publishing ------------------------------------------------------

    def windowed_copy(self, dest: Path, window: int | None) -> Path:
        """Write the copy the agent actually reads.

        `window` follows PRO-LONG: None keeps everything, 0 keeps the header plus the
        latest section, N keeps the header plus the last N sections, -1 writes no log
        at all (the No-Log control: the current state travels in the turn prompt, and
        whatever the agent wants to remember it must write itself).
        """
        text = self.path.read_text(encoding="utf-8")
        if window is None:
            dest.write_text(text, encoding="utf-8")
            return dest
        if window == -1:
            dest.unlink(missing_ok=True)
            return dest
        parts = re.split(rf"(?={re.escape(SEPARATOR)}\n)", text)
        head = parts[0] if parts and not parts[0].startswith(SEPARATOR) else ""
        sections = [p for p in parts if p.startswith(SEPARATOR)]
        if window == 0:
            kept = sections[:1] + (sections[-1:] if len(sections) > 1 else [])
        else:
            kept = sections[:1] + sections[-window:] if len(sections) > window else sections
        dest.write_text(head + "".join(kept), encoding="utf-8")
        return dest

    def publish(self, visible: Path, window: int | None, stateless: bool,
                current: str | None = None) -> dict[str, Any]:
        """Build the directory the agent is given, and remove what the ablation denies it.

        Upstream keeps the canonical record in the run directory and hands Codex a
        *sandbox* underneath it, so a truncated log is the only log there is. Writing
        both files into one directory makes every ablation a request rather than a
        constraint. So, when an ablation is active, `self.record_dir` is the record and
        *visible* is what Codex gets:

        - `logs.txt` in *visible* is the windowed copy, and the full log is not there;
        - attachments are linked in only where the copy still names them, because
          history here is pixels and documents as well as text, and a window that
          leaves `frames/` whole leaves history readable by another route;
        - under `window == -1` only `current` (the attachment this turn sends) is linked;
        - under stateless, everything else the agent wrote is deleted, matching
          upstream's `keep = {logs.txt, AGENTS.md}`.

        No-op when *visible* is the record directory itself, which is the unablated arm:
        it must keep writing exactly the layout its finished runs were produced under.
        """
        if visible == self.record_dir:
            return {"published": False, "attachments_visible": 0, "frames_visible": 0,
                    "removed": 0}

        visible.mkdir(parents=True, exist_ok=True)
        view = self.windowed_copy(visible / "logs.txt", window)
        allowed = (set(self._attach_re.findall(view.read_text(encoding="utf-8")))
                   if view.exists() else set())
        if window == -1:
            allowed = {current} if current else set()

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
            # Outside stateless (and log-only) the workspace is meant to persist; only
            # the attachments the window has dropped are taken back, and they are the
            # harness's files.
            if not stateless and not self.log_only and not rel.startswith(attachment_prefixes):
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

        logger.info(
            "[prolong] ablation view: %d attachment(s) visible, %d file(s) removed "
            "(window=%s stateless=%s log_only=%s)", len(allowed), removed, window,
            stateless, self.log_only,
        )
        return {"published": True, "attachments_visible": len(allowed),
                "frames_visible": len(allowed), "removed": removed}


def prepare_workspace(workspace: Path, ablated: bool,
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
    record = workspace.with_name(f"{workspace.name}_record") if ablated else workspace
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
