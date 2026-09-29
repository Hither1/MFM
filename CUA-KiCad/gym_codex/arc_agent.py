"""arc-code on a cua-lite GUI episode (the KiCad benchmark).

Presents the interface ``run_eval.py`` drives -- ``predict(instruction, screenshot_png,
step_idx, max_steps) -> (reply, tool_calls, done)``, ``add_feedback``, ``audit``,
``finish`` -- and emits exactly the direct arm's tool calls through
``gym_codex.actions.parse_batch``. What differs is the memory: one long coding-agent
session (``codex exec --json``, or ``claude -p`` with ``--arc-agent claude``) living in
the workspace with a shell and a filesystem, whose only way to touch the environment is
``./act do`` (``mfm/arc/act.py``). The harness-written ``logs.txt`` is the log upstream's
actuator writes into -- a section per step with the plan, the actions, the feedback and
the frame -- and the files the model makes (``notes.md``, its scripts) persist. See
``mfm/arc/__init__.py`` for what is upstream's and what is not, and
``gym_codex/arc_prompts.py`` for the brief and the re-nouned method.

Two threads meet in ``predict``: the driver's step and the mailbox server (inside the
handler for a ``do`` request, blocked in ``ActionChannel.play``). ``predict`` answers
the batch that just ran with the log section it produced, then waits for the next
``./act do`` up to the turn ceiling. A batch the parser rejects whole is answered at
once with the feedback the other arms would read next turn, and the step is NOT
consumed (upstream semantics: act refuses invalid input and says why); a step with no
``do`` inside the ceiling is a no-op step, as a memory arm's turn without an artifact
is.

The MCU arm of the same baseline is ``MCU/mcu_worldmodel/arc.py``; this file is what is
KiCad -- the log sections, the brief, and what ``./act do`` accepts.
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import mfm.arc.act as _act_module
from gym_codex import arc_prompts
from gym_codex.actions import ParsedBatch, parse_batch
from mfm.arc.mailbox import MailboxServer
from mfm.arc.prompt import RESUME_TASK, TASK
from mfm.arc.session import SessionLoop, child_env, claude_argv, codex_argv
from mfm.backend.codex_turn import prepare_codex_home as seed_codex_home
from mfm.backend.codex_turn import resolve_codex_bin
from mfm.vista.channel import ActionChannel
from prolong_search.log import EpisodeLog, prepare_workspace

logger = logging.getLogger("gym_codex.arc")

#: Resolved from the installed `mfm` package, not from this file's parents: a wave runs
#: the KiCad checkout from a worktree with the MFM root on PYTHONPATH.
ACT_SOURCE = Path(_act_module.__file__).resolve()

#: How long one step waits for a `./act do` before running as a no-op. The session is
#: writing scripts and grepping the log between batches, so this is generous.
DEFAULT_TURN_CEILING = 900.0
DEFAULT_MAX_SESSIONS = 25
DEFAULT_CLAUDE_MODEL = "claude-opus-5"
#: codex reads AGENTS.md only up to `project_doc_max_bytes` (32 KiB by default); the
#: brief is smaller than that here, but the cap is raised for the same reason the MCU
#: arm raises it -- the session's instructions must be the whole brief.
PROJECT_DOC_MAX_BYTES = 262144

#: What `./act` prints for `--help`. act.py's own docstring is the MCU one (procedures,
#: milestones, inventory); the adapter owns what `do` accepts, so it owns this too.
ACT_DOC = '''\
"""`act`, as the agent sees it -- the one way it touches the environment.

A stdlib-only shim in the workspace. Every command is a request file under `.act/`;
the harness answers with a response file, and what came back is printed. `do` blocks
until the batch has played -- a batch is one environment step -- so a batch is one call.

    ./act do ENTRY [ENTRY ...] [--plan "..."]     play the actions in order; one step
    ./act do --file batch.json [--plan "..."]     the same batch from {"actions": [...]}
    ./act status                                  step, budget, how the episode stands
    ./act view                                    the path of the current screenshot

An ENTRY is one action object as JSON: {"action": "click", "coordinate": [500, 500]}.
To end the episode, play the terminate entry as the only entry of a batch:
{"terminate": {"status": "success"}}. See AGENTS.md for the action space.
"""
'''


class ArcGuiAgent:
    """One coding-agent session in the workspace; `./act do` is its only actuator."""

    arm = "arc"

    def __init__(self, *, workspace: Path, model: str, effort: str, max_steps: int,
                 transcript_dir: Optional[Path] = None, codex_home: Optional[str] = None,
                 timeout: float = DEFAULT_TURN_CEILING, base_url: Optional[str] = None,
                 arc_agent: str = "codex", max_sessions: int = DEFAULT_MAX_SESSIONS) -> None:
        if base_url:
            raise ValueError("the arc arm runs the account's hosted models through the "
                             "coding agent's CLI; a local server is not wired")
        if arc_agent not in ("codex", "claude"):
            raise ValueError(f"arc agent must be codex or claude, not {arc_agent!r}")
        self.kind = arc_agent
        self.visible, self.record = prepare_workspace(Path(workspace), ablated=False)
        self.log = EpisodeLog(self.record, attachment_markers=("SCREEN",),
                              attachment_dirs=("frames",))
        self.model = model if self.kind == "codex" else DEFAULT_CLAUDE_MODEL
        self.effort = effort
        self.max_steps = max_steps
        self.timeout = float(timeout)
        self.max_sessions = int(max_sessions)
        self.codex_home = Path(codex_home) if codex_home else None
        self.transcript_dir = (Path(transcript_dir) if transcript_dir
                               else Path(workspace).parent / "arc_sessions")
        self.codex_bin = resolve_codex_bin(str(os.environ.get("CODEX_BIN") or "codex"))
        self.claude_bin = str(os.environ.get("CLAUDE_BIN") or "claude")

        self.channel = ActionChannel()
        self.mailbox: MailboxServer | None = None
        self.loop: SessionLoop | None = None
        self._lock = threading.Lock()
        self._task: str | None = None
        self._pending_feedback: str | None = None
        self._open: dict[str, Any] | None = None
        self._finished = False
        self._log_offset = 0
        self._last_frame = ""
        self._step = 0

        self.turn = 0
        self.act_turns = 0
        self.no_op_turns = 0
        self.invalid_batches = 0
        self.terminate_batches = 0
        self.sessions_exhausted = False
        self._call_seq = 0

    # -- driver interface ---------------------------------------------------------------

    def reset(self) -> None:
        self._pending_feedback = None

    def add_feedback(self, msg: str) -> None:
        msg = (msg or "").strip()
        if not msg:
            return
        self._pending_feedback = (
            f"{self._pending_feedback} | {msg}" if self._pending_feedback else msg)[:1500]

    def predict(self, instruction: str, screenshot_png: bytes,
                step_idx: int, max_steps: int) -> tuple[str, list[dict], bool]:
        self.max_steps = max_steps
        step = step_idx + 1
        self._step = step
        if self.loop is None:
            self._start(instruction, screenshot_png or b"", step)
        else:
            self._close_previous(screenshot_png or b"", step)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.channel.closed:
                self.no_op_turns += 1
                self.log.add_note(f"step {step}: no ./act do within {self.timeout:.0f}s; "
                                  f"the step ran as a no-op")
                return "", [], False
            if (self.loop is not None and not self.loop.alive
                    and not self.channel.pending()):
                # The session loop has given up (every session died, or it ran out of
                # `max_sessions`): no `./act do` can ever arrive, and waiting out the
                # ceiling on every remaining step would burn the whole budget in
                # 900-second no-ops -- measured at 19 steps in 4.7 h before job 45077536
                # was killed. End the episode instead, so the state that exists is
                # still priced.
                self.sessions_exhausted = True
                self.log.add_note("the coding-agent session loop is no longer running; "
                                  "ending the episode rather than waiting out the budget")
                logger.error("[arc] session loop dead at step %d; terminating", step)
                pb = parse_batch({"terminate": {"status": "failure",
                                                "reason": "the arc session loop stopped"}},
                                 self._tool_call)
                return "", pb.calls, True
            request = self.channel.take(remaining)
            if request is None:
                continue
            pb = self._parse(request)
            if not pb.calls:
                # Refused whole: the reason is the answer, now, and the step is not
                # spent (upstream: "act refuses anything invalid and tells you why").
                self.invalid_batches += 1
                self.channel.deliver({"stdout": "", "rc": 1,
                                      "stderr": f"act: {pb.feedback or pb.log_line}"})
                continue
            self.turn += 1
            self.act_turns += 1
            if pb.feedback:
                self.add_feedback(pb.feedback)
            if pb.done:
                self.terminate_batches += 1
            self._open = {"batch": pb, "step": step,
                          "plan": str(request.get("plan") or "").strip()}
            self._log_offset = self._log_size()
            return "", pb.calls, pb.done

    def finish(self, reward: Any = None, error: Any = None, **outcome: Any) -> None:
        """The episode is over: a waiting `./act do` is told so, then the session and the
        mailbox are stopped. Idempotent -- the driver may call it after an error."""
        if self._finished:
            return
        self._finished = True
        self.channel.close({"stdout": "", "stderr": "act: the episode is over", "rc": 1})
        if self.loop is not None:
            try:
                self.loop.close(30.0)
            except Exception:  # noqa: BLE001 — a stuck CLI must not sink the result
                logger.warning("[arc] closing the session loop failed", exc_info=True)
        if self.mailbox is not None:
            self.mailbox.stop()
        self.log.add_note(f"episode over: reward={reward} error={error}")

    def audit(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "arm": self.arm, "agent": self.kind, "turns": self.turn,
            "act_turns": self.act_turns, "no_op_turns": self.no_op_turns,
            "invalid_batches": self.invalid_batches,
            "terminate_batches": self.terminate_batches,
            "sessions_exhausted": self.sessions_exhausted,
            "turn_ceiling_s": self.timeout, "workspace": str(self.visible),
            "channel": {"plays": self.channel.plays, "deliveries": self.channel.deliveries},
        }
        if self.mailbox is not None:
            out["act_calls"] = {"served": self.mailbox.served,
                                "by_command": dict(self.mailbox.by_command)}
        if self.loop is not None:
            try:
                out["sessions"] = self.loop.audit()
            except Exception:  # noqa: BLE001
                logger.warning("[arc] session report failed", exc_info=True)
        notes = self.visible / "notes.md"
        out["notes_bytes"] = notes.stat().st_size if notes.exists() else 0
        out["files_written"] = sorted(
            p.name for p in self.visible.iterdir()
            if p.is_file() and p.name not in ("logs.txt", "AGENTS.md", "CLAUDE.md",
                                              "act", "act.py"))
        return out

    # -- the episode ---------------------------------------------------------------------

    def _start(self, instruction: str, png: bytes, step: int) -> None:
        self._task = instruction
        brief_file = "AGENTS.md" if self.kind == "codex" else "CLAUDE.md"
        brief = arc_prompts.build_brief(instruction, self.max_steps, brief_file)
        (self.record / brief_file).write_text(brief, encoding="utf-8")
        if self.visible != self.record:
            (self.visible / brief_file).write_text(brief, encoding="utf-8")
        self._last_frame = self.log.save_attachment(f"frames/step_{step:04d}.png", png)
        self.log.write_initial("Step 0 | EPISODE START", [
            f"[TASK] {instruction.strip()}",
            f"Step budget: {self.max_steps}. One section per step follows. No section "
            f"carries a score: nothing tells you whether the task is going well.",
            f"[SCREEN] {self._last_frame}",
        ])
        if self.kind == "codex" and self.codex_home is None:
            wrapped = Path(self.codex_bin).name == "codex_sandbox.sh"
            self.codex_home = seed_codex_home(Path(str(self.visible) + ".codexhome"),
                                              hosted=not wrapped)
        self._install_actuator()
        self.mailbox = MailboxServer(self.visible / ".act", self._handle)
        self.mailbox.start()
        env = child_env(dict(os.environ), codex_home=self.codex_home, kind=self.kind)
        self.loop = SessionLoop(
            make_argv=self._argv, workspace=self.visible, env=env,
            io_dir=self.transcript_dir, kind=self.kind,
            first_prompt=TASK.format(brief_file=brief_file),
            resume_prompt=RESUME_TASK.format(brief_file=brief_file),
            episode_over=lambda: self._finished, max_sessions=self.max_sessions)
        self.loop.start()
        logger.info("[arc] session started: agent=%s model=%s effort=%s mailbox=%s",
                    self.kind, self.model, self.effort, self.visible / ".act")

    def _close_previous(self, png: bytes, step: int) -> None:
        """Write the finished batch's section, then hand it back to the waiting `do`."""
        rel = self.log.save_attachment(f"frames/step_{step:04d}.png", png)
        self._last_frame = rel
        open_batch = self._open
        self._open = None
        feedback = self._pending_feedback
        self._pending_feedback = None
        lines = []
        if open_batch is not None:
            if open_batch["plan"]:
                lines.append(f"[PLAN] {open_batch['plan']}")
            lines.append(f"[ACTIONS] {open_batch['batch'].log_line}")
        if feedback:
            lines.append(f"[FEEDBACK] {feedback}")
        lines.append(f"[SCREEN] {rel}")
        title = f"Step {step - 1} -> {step}" if open_batch else f"Step {step}"
        self.log.write_section(title, lines)
        if open_batch is not None:
            self.channel.deliver(self._batch_outcome())

    def _batch_outcome(self) -> dict[str, Any]:
        """What `./act do` prints: the section the batch added to the log, verbatim,
        then the status line -- upstream's shape."""
        try:
            with (self.record / "logs.txt").open("rb") as f:
                f.seek(self._log_offset)
                section = f.read().decode("utf-8", errors="replace")
        except OSError:
            section = ""
        lines = [section.rstrip("\n"), "", self._status_line(),
                 f"log: logs.txt (through step {self._step})"]
        return {"stdout": "\n".join(lines) + "\n", "rc": 0}

    # -- the actuator --------------------------------------------------------------------

    def _handle(self, request: dict[str, Any]) -> dict[str, Any]:
        cmd = request.get("cmd")
        if cmd == "status":
            return {"stdout": self._status_line() + "\n", "rc": 0}
        if cmd == "view":
            if not self._last_frame:
                return {"stdout": "", "stderr": "act: no view recorded yet", "rc": 1}
            return {"stdout": f"{self._last_frame}\n", "rc": 0}
        if cmd != "do":
            return {"stdout": "", "stderr": f"act: unknown command {cmd!r}", "rc": 1}
        entries = request.get("actions")
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            return {"stdout": "", "stderr": "act: `do` needs one or more entries", "rc": 1}
        if self._finished:
            return {"stdout": "", "stderr": "act: the episode is over", "rc": 1}
        outcome = self.channel.play(request)
        if outcome is None:
            return {"stdout": "", "stderr": "act: the episode is over", "rc": 1}
        return outcome

    def _parse(self, request: dict[str, Any]) -> ParsedBatch:
        """The request's entries as the batch object `parse_batch` reads.

        A lone `{"terminate": ...}` entry is the episode's end -- act.py has no `done`
        command (it is shared with the MCU arm, whose pins cover it), so the terminate
        travels as an entry and is lifted here. Everything else is `{"actions": [...]}`
        and goes through the same parser every other arm uses.
        """
        entries = list(request.get("actions") or [])
        if len(entries) == 1 and ("terminate" in entries[0] or "response" in entries[0]):
            obj = entries[0]
        else:
            obj = {"actions": entries}
        return parse_batch(obj, self._tool_call)

    def _install_actuator(self) -> None:
        """`act.py` and the `./act` shim, the way upstream's launcher copies its client
        into the workspace, with this benchmark's help text."""
        source = ACT_SOURCE.read_text(encoding="utf-8")
        head, sep, tail = source.partition('"""')
        body = tail.split('"""', 1)[1] if sep else source
        dst = self.visible / "act.py"
        dst.write_text(ACT_DOC + body, encoding="utf-8")
        shim = self.visible / "act"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{dst}" "$@"\n', encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (self.visible / ".act").mkdir(exist_ok=True)
        if self.visible != self.record:
            shutil.copy(dst, self.record / "act.py")

    def _argv(self, prompt: str) -> list[str]:
        if self.kind == "claude":
            return claude_argv(claude_bin=self.claude_bin, model=self.model,
                               effort=self.effort or None, prompt=prompt)
        extra = ["-c", 'sandbox_mode="workspace-write"',
                 "-c", f"project_doc_max_bytes={PROJECT_DOC_MAX_BYTES}"]
        return codex_argv(codex_bin=self.codex_bin, model=self.model, effort=self.effort,
                          prompt=prompt, extra_args=tuple(extra))

    def _status_line(self) -> str:
        left = max(0, self.max_steps - self._step)
        return (f"step {self._step}/{self.max_steps} ({left} steps left) | "
                f"batches {self.act_turns} | refused {self.invalid_batches}")

    def _log_size(self) -> int:
        try:
            return (self.record / "logs.txt").stat().st_size
        except OSError:
            return 0

    def _tool_call(self, name: str, args: dict) -> dict:
        self._call_seq += 1
        return {"id": f"call_{self._call_seq:04d}", "type": "function",
                "function": {"name": name, "arguments": args}}
