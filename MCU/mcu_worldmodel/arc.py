"""The arc-code arm on the world-model chassis (`--memory arc`).

`--memory arc` is the chassis (macros, cursor, vision, governor, the same action
reference and platform knowledge every rung of the ladder reads) driven the way
github.com/jerber/arc-code drives a game: one long coding-agent session -- `codex exec`
or `claude -p` -- in the workspace, with a shell and a filesystem, whose only way to act
is `./act do` (mfm/arc/act.py). The chassis's own `logs.txt` is the log upstream's
actuator writes: a section per entry with the plan, the entry, the [STATE], the [INV]
and [EVENT] ground truth, the [NOTE]s and the frame it produced. Files the model makes
(notes.md, its scripts) persist -- upstream's memory is the workspace -- where the
logbook arm sweeps them. See mfm/arc/__init__.py for what is upstream's and what is not.

The hooks the chassis calls, mirroring the vista arm's (mcu_worldmodel/vista.py):

    start        `WorldModelAgent.start`     install ./act, start the mailbox and the session
    act_turn     `_act_turn`                 the queue is dry: the finished batch's sections
                                             go back to the waiting `./act do`; the next
                                             batch is taken (up to the turn ceiling per
                                             tick), expanded and queued
    observe      every `observe` tick        the present, for `./act status`
    entry_done   `_log_entry_done`           the entry's frame, for its section's [FRAME]

Two threads meet in `act_turn`: the chassis (the green server's step) and the mailbox
server (inside the handler for a `do` request, blocked in `channel.play`). The chassis
waits for a request up to `codex_timeout` per tick, then runs a no-op tick and waits
again; the handler waits for the batch's outcome as long as the batch takes.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

import mfm.arc.act as _act_module
from mfm.arc.mailbox import MailboxServer
from mfm.arc.prompt import RESUME_TASK, TASK
from mfm.arc.session import SessionLoop, child_env, claude_argv, codex_argv
from mfm.backend.codex_turn import prepare_codex_home as seed_codex_home
from mfm.vista.channel import ActionChannel

from mcu_worldmodel.actions import parse_actions
from mcu_worldmodel.codex_backend import AUTO_COMPACT_TOKEN_LIMIT, SAFE_CODEX_FLAGS
from mcu_worldmodel.memory import norm_yaw
from mcu_worldmodel.milestones import (held_line, hotbar_line, inventory_counts, location,
                                       nearby_mobs, vitals)

#: Resolved from the installed `mfm` package, not from this file's parents: a wave runs
#: MCU from its own checkout (MCU_ROOT=<worktree>) with the MFM root on PYTHONPATH, so
#: `../../mfm/arc/act.py` is only right when MCU sits inside the MFM tree.
ACT_SOURCE = Path(_act_module.__file__).resolve()
DEFAULT_MAX_SESSIONS = 25
PROJECT_DOC_MAX_BYTES = 262144
DEFAULT_CLAUDE_MODEL = "claude-opus-5"


class ArcCodexShim:
    """What the chassis reads off `self.codex`, for an arm that runs no `codex exec`
    turns of its own (the session is the model's, started once)."""

    session_max_turns = 0

    def __init__(self, bridge: "ArcBridge") -> None:
        self.bridge = bridge

    @property
    def calls(self) -> int:
        return self.bridge.decisions

    def write_system_prompt(self, text: str) -> None:
        # The brief: AGENTS.md is what codex reads from the workspace it is started in,
        # CLAUDE.md what Claude Code reads (upstream writes CLAUDE.md). Both are written
        # so the workspace is the same whichever CLI plays.
        for name in ("AGENTS.md", "CLAUDE.md"):
            (self.bridge.root / name).write_text(text, encoding="utf-8")
        self.bridge.brief = text

    def vision_audit(self) -> dict[str, Any]:
        loop = self.bridge.loop
        stream = loop.audit()["stream"] if loop else {}
        return {"frames_attached": 0, "view_image_calls": stream.get("image_views", 0),
                "image_attach_failures": 0, "vision_audit_source": "arc"}

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        from mcu_worldmodel.codex_backend import CodexTurn
        return CodexTurn.split_briefing(message)

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("the arc arm runs no codex exec turns")


class ArcBridge:
    def __init__(self, agent: Any, *, model: str, effort: str, codex_home: Path | None,
                 transcript_dir: Path | None, timeout: float, base_url: str | None = None,
                 options: dict[str, Any] | None = None) -> None:
        if base_url:
            raise ValueError("the arc arm runs the account's hosted models through the "
                             "coding agent's CLI; a local server is not wired")
        opts = dict(options or {})
        self.agent = agent
        self.root: Path = agent.memory.root
        self.kind = str(opts.get("agent", "codex"))
        if self.kind not in ("codex", "claude"):
            raise ValueError(f"arc agent must be codex or claude, not {self.kind!r}")
        self.model = model if self.kind == "codex" else str(opts.get("model") or DEFAULT_CLAUDE_MODEL)
        self.effort = effort
        self.timeout = float(timeout)
        self.codex_home = Path(codex_home) if codex_home else None
        self.transcript_dir = (Path(transcript_dir) if transcript_dir
                               else self.root.parent / "arc_sessions")
        self.max_sessions = int(opts.get("max_sessions", DEFAULT_MAX_SESSIONS))
        self.relaunch_delay = float(opts.get("relaunch_delay", 5.0))
        self.close_timeout = float(opts.get("close_timeout", 30.0))
        self.poll = float(opts.get("poll", 0.2))
        self.codex_bin = str(opts.get("codex_bin") or os.environ.get("CODEX_BIN") or "codex")
        self.claude_bin = str(opts.get("claude_bin") or os.environ.get("CLAUDE_BIN") or "claude")
        self.brief = ""
        self.channel = ActionChannel()
        self.mailbox: MailboxServer | None = None
        self.loop: SessionLoop | None = None
        self._lock = threading.Lock()
        self._last_info: dict | None = None
        self._owed: dict[str, Any] | None = None
        self._running = False
        self._log_offset = 0
        self._batch_total = 0
        self._batch_action_start = 0
        self._batch_started_step = 0
        self._tick_step: int | None = None
        self._tick_deadline = 0.0
        self._idle_since_last = 0
        self.decisions = 0
        self.idle_ticks = 0
        self.refused_batches = 0
        self.batches_applied = 0
        self.entries_applied = 0
        self.entries_dropped = 0
        self._finished = False

    # -- the chassis's calls ------------------------------------------------------------

    def start(self, info: dict, png: bytes | None) -> None:
        if self.kind == "codex" and self.codex_home is None:
            self.codex_home = seed_codex_home(Path(str(self.root) + ".codexhome"), hosted=True)
        self._last_info = info
        self._install_actuator()
        self.mailbox = MailboxServer(self.root / ".act", self._handle, poll=self.poll)
        self.mailbox.start()
        brief_file = "AGENTS.md" if self.kind == "codex" else "CLAUDE.md"
        env = child_env(dict(os.environ), codex_home=self.codex_home, kind=self.kind)
        self.loop = SessionLoop(
            make_argv=self._argv, workspace=self.root, env=env, io_dir=self.transcript_dir,
            kind=self.kind, first_prompt=TASK.format(brief_file=brief_file),
            resume_prompt=RESUME_TASK.format(brief_file=brief_file),
            episode_over=lambda: self._finished, max_sessions=self.max_sessions,
            relaunch_delay=self.relaunch_delay)
        self.loop.start()
        logger.info(f"[arc] session loop started: agent={self.kind} model={self.model} "
                    f"effort={self.effort} home={self.codex_home} mailbox={self.root / '.act'} "
                    f"max_sessions={self.max_sessions}")

    def observe(self, info: dict, step: int) -> None:
        self._last_info = info

    def act_turn(self, info: dict) -> None:
        """The chassis's queue is dry: answer the batch that just finished, wait for the
        next `./act do` within this tick's share of the turn ceiling, expand it, queue it."""
        agent = self.agent
        if self.mailbox is None:
            return
        step = agent.step
        if self._tick_step != step:
            self._tick_step = step
            self._tick_deadline = time.monotonic() + self.timeout
        # An entry drained inside `next_action` (a raw hold cut short by a break) has
        # no section yet and `next_action` would clear `_entry_index` after two empty
        # turns; written here the way the marker path writes it (see vista.py).
        if agent._entry_index is not None and not agent.queue:
            agent._log_entry_done(agent._entry_index)
            agent._entry_index = None
        if self._running:
            # The batch drained: what the log gained since it started is its answer.
            self._owed = self._batch_outcome(info)
            self._running = False
        self._deliver()
        remaining = self._tick_deadline - time.monotonic()
        if remaining <= 0 or self.channel.closed:
            return
        request = self.channel.take(remaining)
        if request is None:
            self.idle_ticks += 1
            self._idle_since_last += 1
            return
        self.decisions += 1
        entries = request.get("actions") or []
        plan_text = str(request.get("plan") or "").strip()
        # Upstream records the batch's --plan beside every action of the batch.
        agent.memory.set_plan(plan_text, None)
        plan = parse_actions(json.dumps({"actions": entries}), entry_cap=agent.entry_cap,
                             repeat_cap=agent.repeat_cap, step_cap=agent.step_cap,
                             allow_optional=agent.extended_actions, info=info,
                             cursor=agent.cursor.copy())
        for n in plan.notes:
            agent.memory.add_note(n)
        if not plan.steps:
            # Refused: the reasons are the answer (upstream: "act refuses anything
            # invalid and tells you why"), not [NOTE]s in the next batch's section.
            self.refused_batches += 1
            self._forget_notes(plan.notes)
            self._owed = self._error("; ".join(plan.notes) or "the batch expanded to no ticks")
            return
        self._log_offset = self._log_size()
        self._batch_action_start = agent.action_num
        agent._enqueue(plan)
        if not agent._plan_entries:
            # The governor dropped the plan (one no-op queued, a note pending).
            self.refused_batches += 1
            self._owed = self._error(agent.memory._pending_notes[-1]
                                     if agent.memory._pending_notes
                                     else "the governor refused the batch")
            return
        self._running = True
        self._batch_total = len(agent._plan_entries)
        self._batch_started_step = step
        self.batches_applied += 1

    def entry_done(self, index: int) -> None:
        """The entry finished (`_log_entry_done`, before its section is written): the
        view now is the section's [FRAME]."""
        agent = self.agent
        if not (0 <= index < len(agent._plan_entries)):
            return
        info = self._last_info
        if info is not None:
            agent._save_frame(info, agent.step)
        self.entries_applied += 1

    def finish(self) -> None:
        """The episode's last step: a waiting `./act do` is told so, the mailbox and the
        session are closed."""
        if self._finished or self.mailbox is None:
            return
        self._finished = True
        self.channel.close({"stdout": "", "stderr": "act: the episode is over -- the step budget "
                            "is spent", "rc": 1})
        if self.loop is not None:
            self.loop.close(self.close_timeout)
        self.mailbox.stop()

    def audit(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "agent": self.kind, "model": self.model,
            "decisions": self.decisions, "batches_applied": self.batches_applied,
            "entries_applied": self.entries_applied, "entries_dropped": self.entries_dropped,
            "refused_batches": self.refused_batches, "idle_ticks": self.idle_ticks,
            "turn_ceiling_s": self.timeout,
            "channel": {"plays": self.channel.plays, "deliveries": self.channel.deliveries},
        }
        if self.mailbox is not None:
            out["act_calls"] = dict(self.mailbox.by_command)
        if self.loop is not None:
            out.update(self.loop.audit())
        return out

    # -- the mailbox's handler (its own thread) -------------------------------------------

    def _handle(self, request: dict[str, Any]) -> dict[str, Any]:
        cmd = request.get("cmd")
        if cmd == "status":
            return {"stdout": self._status_text(), "rc": 0}
        if cmd == "view":
            rel = self.agent._last_frame
            if not rel:
                return {"stdout": "", "stderr": "act: no view recorded yet", "rc": 1}
            return {"stdout": f"{rel}\n", "rc": 0}
        if cmd != "do":
            return {"stdout": "", "stderr": f"act: unknown command {cmd!r}", "rc": 1}
        entries = request.get("actions")
        if not isinstance(entries, list) or not entries or not all(isinstance(e, dict) for e in entries):
            return self._error("`do` needs one or more entries")
        if self._finished:
            return {"stdout": "", "stderr": "act: the episode is over", "rc": 1}
        outcome = self.channel.play(request)
        if outcome is None:
            return {"stdout": "", "stderr": "act: the episode is over", "rc": 1}
        return outcome

    # -- helpers ---------------------------------------------------------------------------

    def _argv(self, prompt: str) -> list[str]:
        if self.kind == "claude":
            return claude_argv(claude_bin=self.claude_bin, model=self.model,
                               effort=self.effort or None, prompt=prompt)
        # The brief is ~75 KB and codex reads AGENTS.md only up to `project_doc_max_bytes`
        # (32 KiB by default: measured 2026-09-06 on 0.149, a logbook rollout carried the
        # first 32 KB of its 80 KB AGENTS.md and nothing past "Skills by situation").
        # Raised here so the session's instructions are the whole brief, the way the
        # vista arm's developerInstructions are; the model is also told to read the file.
        extra: list[str] = ["-c", 'sandbox_mode="workspace-write"',
                            "-c", f"project_doc_max_bytes={PROJECT_DOC_MAX_BYTES}"]
        if AUTO_COMPACT_TOKEN_LIMIT:
            extra += ["-c", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}"]
        extra += list(SAFE_CODEX_FLAGS)
        return codex_argv(codex_bin=self.codex_bin, model=self.model, effort=self.effort,
                          prompt=prompt, extra_args=tuple(extra))

    def _install_actuator(self) -> None:
        """`act.py` and the `./act` shim, the way upstream's launcher copies its client
        into the workspace: the shim names this interpreter so `./act` works from any
        shell the agent opens."""
        shutil.copy(ACT_SOURCE, self.root / "act.py")
        shim = self.root / "act"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{self.root / "act.py"}" "$@"\n',
                        encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (self.root / ".act").mkdir(exist_ok=True)

    def _deliver(self) -> None:
        if self._owed is None:
            return
        outcome, self._owed = self._owed, None
        if not self.channel.owed():
            return
        if self._idle_since_last:
            outcome["stdout"] += (f"(the environment ran {self._idle_since_last} no-op tick(s) "
                                  f"waiting for this batch)\n")
            self._idle_since_last = 0
        self.channel.deliver(outcome)

    def _error(self, error: str) -> dict[str, Any]:
        # Exit 1, the way upstream's ActError exits: one code for every refusal.
        return {"stdout": "", "stderr": f"act: {error}", "rc": 1}

    def _forget_notes(self, notes: list[str]) -> None:
        pending = self.agent.memory._pending_notes
        for n in notes:
            if n in pending:
                pending.remove(n)

    def _log_size(self) -> int:
        try:
            return self.agent.memory.logs_path.stat().st_size
        except OSError:
            return 0

    def _batch_outcome(self, info: dict) -> dict[str, Any]:
        """What `./act do` prints: the sections the batch added to the log, verbatim,
        then upstream's summary lines."""
        agent = self.agent
        path = agent.memory.logs_path
        try:
            with path.open("rb") as f:
                f.seek(self._log_offset)
                sections = f.read().decode("utf-8", errors="replace")
        except OSError:
            sections = ""
        ran = agent.action_num - self._batch_action_start
        total = self._batch_total
        dropped = max(0, total - ran)
        self.entries_dropped += dropped
        lines = [sections.rstrip("\n"), "", f"ran {ran}/{total} entries in "
                 f"{agent.step - self._batch_started_step} ticks"]
        if dropped:
            fired = [e for e in agent._pending_events if e.startswith("MILESTONE")]
            why = ("a milestone verified" if fired or "MILESTONE" in sections[-4000:]
                   else "the plan was cut short")
            lines.append(f"stopped early: {why}, {dropped} entr{'y' if dropped == 1 else 'ies'} dropped")
        pending = list(agent.memory._pending_notes)
        for n in pending:
            lines.append(f"note: {n}")
        lines.append(self._status_line())
        lines.append(f"log: logs.txt (through Action {agent.action_num})")
        return {"stdout": "\n".join(lines) + "\n", "rc": 0}

    def _status_line(self) -> str:
        agent = self.agent
        ms = (f" | milestones {len(agent.ledger.achieved)}/{len(agent.ledger.cfg)} verified"
              if agent.ledger.cfg else "")
        return (f"step {agent.step}/{agent.max_steps} ({max(0, agent.max_steps - agent.step)} "
                f"ticks left){ms} | stall_turns {agent._stall_turns}")

    def _status_text(self) -> str:
        agent = self.agent
        info = self._last_info or {}
        inv = inventory_counts(info)
        pos = location(info)
        pos_line = (f"pos=({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}) "
                    f"pitch={pos['pitch']:.0f} yaw={norm_yaw(pos['yaw']):.0f}") if pos else "unknown"
        free = _empty_slot_count(info)
        lines = [
            self._status_line(),
            f"position: {pos_line}",
            f"vitals: {vitals(info)}",
            f"inventory: {', '.join(f'{k}x{v}' for k, v in sorted(inv.items())) or 'empty'}"
            + (f" ({free} free slots)" if free is not None else ""),
            f"hotbar: {hotbar_line(info)}",
            f"held: {held_line(info)}",
            f"nearby entities: {nearby_mobs(info)}",
            f"GUI open: {bool(info.get('isGuiOpen', False))}",
            agent.cursor.line(inv),
        ]
        grid = agent._grid_line()
        if grid:
            lines.append(grid)
        if agent.ledger.cfg:
            lines.append(agent.ledger.progress_block())
        if agent._last_frame:
            lines.append(f"view: {agent._last_frame}")
        return "\n".join(lines) + "\n"


def _empty_slot_count(info: dict) -> int | None:
    from mcu_worldmodel.agent import _empty_slot_count as f
    return f(info)
