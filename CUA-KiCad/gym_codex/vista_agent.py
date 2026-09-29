"""VISTA on a cua-lite GUI episode (the KiCad benchmark).

Presents the interface ``run_eval.py`` drives -- ``predict(instruction, screenshot_png,
step_idx, max_steps) -> (reply, tool_calls, done)``, ``add_feedback``, ``audit``,
``finish`` -- and emits exactly the direct arm's tool calls through
``gym_codex.actions.parse_batch``. What differs is the memory: one codex app-server
thread whose ``play`` executes one action batch (the same JSON the other arms write to
``actions.json``) and returns the step's result with the next screenshot steered into
the thread; ``inspect`` over every archived screenshot; ``history``; ``GUIDE.md`` and
``WORKING.md``; a checkpoint handoff when the context (or the wire) fills. No shell,
no log, no frames by path. See ``mfm/vista/__init__.py``.

One episode is one task. ``run_eval`` calls ``predict`` once per step: the previous
play's outcome (the new screenshot, the environment's feedback, whether the screen
changed) is delivered to the thread, then the step waits for the next ``play`` up to the
turn ceiling. A batch the parser rejects whole is answered at once with the feedback
the other arms would read next turn, and the step is NOT consumed (upstream semantics:
an invalid action does not reach the environment); a step with no play within the
ceiling is a no-op step, as a memory arm's turn without an artifact is.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from gym_codex import prompts_prolong
from gym_codex.actions import ACTION_REFERENCE, MAX_BATCH, ParsedBatch, parse_batch
from mfm.backend.codex_turn import prepare_codex_home as seed_codex_home
from mfm.backend.codex_turn import resolve_codex_bin
from mfm.vista.archive import FrameArchive
from mfm.vista.channel import ActionChannel
from mfm.vista.controller import Outcome, Validation, VistaController
from mfm.vista.prompt import PLAYER_BASE_INSTRUCTIONS, method_lines
from mfm.vista.recovery import initial_prompt
from mfm.vista.runner import DEFAULT_IDLE_TIMEOUT, DEFAULT_THREAD_BYTES_BUDGET, AppServerRunner
from mfm.vista.session import VistaSession
from mfm.vista.tools import build_play_tool, build_tools

logger = logging.getLogger("gym_codex.vista")

DEFAULT_ACT_TIMEOUT = 900
OBJECTIVE = ("Complete the task in as few steps as possible and terminate as soon as it is "
             "durably done (saved); every play result states the step and the budget.")
EMPTY_GUIDE = "No reliable model yet."
NO_ACTIONS_FEEDBACK = ('Your play had no "actions" list (and no terminate). Nothing was executed.')

PLAY_DESCRIPTION = (
    "Execute exactly one action batch and observe the screen afterwards. The call is "
    '{"actions": [ ...1-%d action objects... ]} or, to END the episode, '
    '{"terminate": {"status": "success"}} / {"terminate": {"status": "failure", "reason": '
    '"..."}}. An empty actions list is read as terminate(success). The batch is one '
    "environment step; the result carries the step number, the environment's feedback on "
    "the batch (an unknown action, a dropped coordinate, an env error), whether the screen "
    "changed, and the screenshot taken after the whole batch. The next call sees this "
    "result before another batch can run. A batch with no valid action is refused without "
    "spending a step." % MAX_BATCH
)
PLAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "actions": {"type": "array", "maxItems": MAX_BATCH, "items": {"type": "object"},
                    "description": "The action objects of the action contract, in order."},
        "terminate": {"type": "object", "additionalProperties": False, "required": ["status"],
                      "properties": {"status": {"type": "string", "enum": ["success", "failure"]},
                                     "reason": {"type": "string"}}},
    },
}

SYSTEM_PROMPT = """\
You are a desktop agent controlling a GUI through a visual interface: one `play` call
executes one action batch and returns the screenshot taken after it.

{task_framing}

The episode runs over at most {max_steps} steps; a batch is one step whether it holds
one action or {max_batch}. Complete the task in as few steps as possible and terminate as
soon as it is durably done (saved).

{method}

**Action contract**. {action_reference}

A `play` call is `{{"actions": [ ...1-{max_batch} action objects... ]}}` or, to END the
episode, `{{"terminate": {{"status": "success"}}}}` / `{{"terminate": {{"status": "failure",
"reason": "..."}}}}`. An empty `actions` list is read as terminate(success). Keep batches
short (1-3 actions) so you see the result before continuing.

**Rules that have cost episodes before**:
- Before typing into any app or field, verify in the CURRENT screenshot that the target
  window/field exists and is focused -- text typed blind goes to whatever is active and
  is lost.
- Never batch input in the same turn that opens the app or dialog it targets; open,
  look, then act.
- After typing something long, check the screenshot that it appears complete before
  pressing enter.
- Save the project (ctrl+s, confirm any dialog) and verify the title bar no longer shows
  an unsaved marker before terminating. Terminate as soon as the task is durably done;
  every further step is budget, not progress.
- If the screen has not changed after the same action twice, the action is not doing
  what you think: `inspect` the region, compare with an earlier turn, and change approach.
"""


def build_system_prompt(max_steps: int) -> str:
    return SYSTEM_PROMPT.format(
        task_framing=prompts_prolong.TASK_FRAMING, max_steps=max_steps, max_batch=MAX_BATCH,
        method=method_lines(world="desktop and the application", understanding="task understanding",
                            action="action batch"),
        action_reference=ACTION_REFERENCE)


def _png_hash(png: bytes) -> str:
    return hashlib.sha256(png or b"").hexdigest()[:16]


class VistaGuiAgent:
    arm = "vista"

    def __init__(self, *, workspace: Path, model: str, effort: str, max_steps: int,
                 transcript_dir: Optional[Path] = None, codex_home: Optional[str] = None,
                 timeout: int = DEFAULT_ACT_TIMEOUT, session_turns: Optional[int] = None,
                 base_url: Optional[str] = None, thread_bytes: Optional[int] = DEFAULT_THREAD_BYTES_BUDGET,
                 idle_timeout: float = DEFAULT_IDLE_TIMEOUT, max_invalid_retries: int = 15,
                 close_timeout: float = 60.0, codex_bin: Optional[str] = None,
                 cli: str = "codex") -> None:
        if cli not in ("codex", "claude"):
            raise ValueError(f"vista cli must be codex or claude, not {cli!r}")
        self.cli = cli
        if base_url:
            raise ValueError("the vista arm runs codex app-server against the account's hosted "
                             "models; a local server is not wired")
        self.visible = Path(workspace).resolve()
        self.visible.mkdir(parents=True, exist_ok=True)
        self.private = self.visible.parent / "vista"
        self.model, self.effort = model, effort
        self.max_steps = max_steps
        self.timeout = float(timeout)
        self.transcript_dir = Path(transcript_dir) if transcript_dir else self.private / "codex_io"
        self.thread_bytes = int(thread_bytes) if thread_bytes else None
        self.idle_timeout = float(idle_timeout)
        self.max_invalid_retries = max_invalid_retries
        self.close_timeout = close_timeout
        self.codex_bin = resolve_codex_bin(codex_bin or os.environ.get("CODEX_BIN", "codex"))
        if cli == "claude":
            # The Claude Code channel (mfm/vista/claude_runner.py): the markers and the
            # CLI's config live in <workspace>.claudehome, the twin of .codexhome.
            self.codex_home = Path(codex_home) if codex_home else Path(str(self.visible) + ".claudehome")
        elif codex_home:
            self.codex_home = Path(codex_home)
        elif os.environ.get("CODEX_HOME"):
            self.codex_home = Path(os.environ["CODEX_HOME"])
        else:
            # The same derivation as the other arms' backend: the wrapper, if it is in
            # use, bind-mounts this exact path as the episode's home.
            wrapped = Path(self.codex_bin).name == "codex_sandbox.sh"
            self.codex_home = seed_codex_home(Path(str(self.visible) + ".codexhome"),
                                              hosted=not wrapped)
        self.channel = ActionChannel()
        self.archive: FrameArchive | None = None
        self.controller: VistaController | None = None
        self.runner: Any = None  # AppServerRunner, or ClaudeCodeRunner on the Claude Code channel
        self.session: VistaSession | None = None
        self._lock = threading.Lock()
        self._present: dict[str, Any] = {}
        self._task: str | None = None
        self._pending_feedback: str | None = None
        self._open: dict[str, Any] | None = None
        self._last_hash: str | None = None
        self._call_seq = 0
        self.turn = 0
        self.act_turns = 0
        self.no_op_turns = 0
        self.invalid_batches = 0
        self._finished = False

    # -- driver interface ------------------------------------------------------------------

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
        if self.session is None:
            self._start(instruction, screenshot_png or b"", step)
        else:
            self._deliver(screenshot_png or b"", step)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.channel.closed:
                self.no_op_turns += 1
                return "", [], False
            obj = self.channel.take(remaining)
            if obj is None:
                continue
            pb = parse_batch(obj, self._tool_call, no_json_feedback=NO_ACTIONS_FEEDBACK)
            if not pb.calls:
                # Rejected whole: the feedback the other arms read next turn, now,
                # and the step is not spent.
                self.invalid_batches += 1
                with self._lock:
                    present = dict(self._present)
                self.channel.deliver(Outcome(applied=False, error=pb.feedback or pb.log_line,
                                             result={"present": present}))
                continue
            self.turn += 1
            self.act_turns += 1
            if pb.feedback:
                # An action the parser dropped: said in the next result, as the other
                # arms say it in the next turn's [FEEDBACK].
                self.add_feedback(pb.feedback)
            self._open = {"batch": pb, "step": step, "png_hash": self._last_hash}
            reply = (self.runner.last_agent_message if self.runner else "").strip()
            return reply, pb.calls, pb.done

    def finish(self, reward: Any = None, error: Any = None, **outcome: Any) -> None:
        if self._finished or self.controller is None or self.session is None:
            return
        self._finished = True
        self.controller.force_terminal("episode_end")
        with self._lock:
            present = dict(self._present)
        result = {"present": present, "reward": reward}
        if self._open is not None:
            # The terminate (or the last batch) ran; its outcome is the episode's end.
            self._open = None
        self.channel.close(Outcome(applied=False, result=result, terminal=True))
        self.session.close(self.close_timeout)
        if hasattr(self.runner, "close"):
            self.runner.close()

    def audit(self) -> dict[str, Any]:
        out: dict[str, Any] = {"arm": self.arm, "cli": self.cli, "turns": self.turn, "act_turns": self.act_turns,
                               "no_op_turns": self.no_op_turns, "invalid_batches": self.invalid_batches,
                               "turn_ceiling_s": self.timeout, "workspace": str(self.visible),
                               "channel": {"plays": self.channel.plays, "deliveries": self.channel.deliveries}}
        if self.session is not None:
            out["vista"] = self.session.audit()
        return out

    # -- the controller's bridge (the codex driver's thread) ------------------------------------

    def validate(self, arguments: Any) -> Validation:
        if not isinstance(arguments, dict):
            return Validation(False, 'play takes one object: {"actions": [...]} or {"terminate": {...}}.')
        extra = set(arguments) - {"actions", "terminate"}
        if extra:
            return Validation(False, f"unknown keys {sorted(extra)}; give `actions` or `terminate`.")
        if ("actions" in arguments) == ("terminate" in arguments):
            return Validation(False, "give exactly one of `actions` or `terminate`.")
        if "actions" in arguments and not isinstance(arguments["actions"], list):
            return Validation(False, "`actions` must be a list of action objects.")
        if "terminate" in arguments and not isinstance(arguments["terminate"], dict):
            return Validation(False, "`terminate` must be an object with a `status`.")
        return Validation(True, parsed=dict(arguments), public=dict(arguments))

    def execute(self, parsed: Any) -> Outcome:
        outcome = self.channel.play(parsed)
        if outcome is None:
            with self._lock:
                present = dict(self._present)
            return Outcome(applied=False, result={"present": present}, terminal=True)
        return outcome

    def present(self) -> tuple[dict[str, Any], bytes | None]:
        with self._lock:
            return dict(self._present), None

    @property
    def terminal(self) -> bool:
        return self._finished

    # -- helpers (the driver's thread) --------------------------------------------------------------

    def _tool_call(self, name: str, args: dict) -> dict:
        self._call_seq += 1
        return {"id": f"call_{self._call_seq:04d}", "type": "function",
                "function": {"name": name, "arguments": args}}

    def _present_block(self, step: int, feedback: str | None) -> dict[str, Any]:
        block: dict[str, Any] = {"task": self._task, "step": step, "max_steps": self.max_steps,
                                 "steps_remaining": max(0, self.max_steps - step + 1)}
        if feedback:
            block["feedback"] = feedback
        return block

    def _start(self, instruction: str, png: bytes, step: int) -> None:
        self._task = instruction
        self._last_hash = _png_hash(png)
        (self.visible / "AGENTS.md").write_text(build_system_prompt(self.max_steps), encoding="utf-8")
        guide = self.visible / "GUIDE.md"
        if not guide.exists():
            guide.write_text(EMPTY_GUIDE + "\n", encoding="utf-8")
        self.archive = FrameArchive(self.visible / "frames")
        if png:
            self.archive.add(0, png)
        width, height = self.archive.size if png else (1920, 1080)
        with self._lock:
            self._present = self._present_block(step, None)
        self.controller = VistaController(
            bridge=self, archive=self.archive, private_dir=self.private, codex_home=self.codex_home,
            guide_path=guide, working_path=self.visible / "WORKING.md",
            max_invalid_retries=self.max_invalid_retries)
        tools = build_tools(build_play_tool(PLAY_SCHEMA, PLAY_DESCRIPTION), width, height)
        if self.cli == "claude":
            from mfm.vista.claude_runner import ClaudeCodeRunner
            self.runner = ClaudeCodeRunner(
                workspace=self.visible, config_dir=self.codex_home, io_dir=self.transcript_dir,
                controller=self.controller, tools=tools, base_instructions=PLAYER_BASE_INSTRUCTIONS,
                developer_instructions=(self.visible / "AGENTS.md").read_text(encoding="utf-8"),
                model=self.model, reasoning_effort=self.effort,
                claude_bin=os.environ.get("CLAUDE_BIN") or None,
                idle_timeout=self.idle_timeout, thread_bytes_budget=self.thread_bytes, objective=OBJECTIVE)
        else:
            self.runner = AppServerRunner(
                workspace=self.visible, codex_home=self.codex_home, io_dir=self.transcript_dir,
                controller=self.controller, tools=tools, base_instructions=PLAYER_BASE_INSTRUCTIONS,
                developer_instructions=(self.visible / "AGENTS.md").read_text(encoding="utf-8"),
                model=self.model, reasoning_effort=self.effort, codex_bin=self.codex_bin,
                idle_timeout=self.idle_timeout, thread_bytes_budget=self.thread_bytes, objective=OBJECTIVE)
        prompt = initial_prompt(self.controller.initial_metadata(), OBJECTIVE)
        self.session = VistaSession(runner=self.runner, controller=self.controller,
                                    initial_prompt=prompt,
                                    initial_images=tuple(self.controller.initial_image_paths()))
        self.session.start()

    def _deliver(self, png: bytes, step: int) -> None:
        """The outcome of the batch the previous step ran, to the play that issued it."""
        feedback, self._pending_feedback = self._pending_feedback, None
        new_hash = _png_hash(png)
        present = self._present_block(step, feedback)
        with self._lock:
            self._present = present
        if self._open is None or not self.channel.owed():
            self._last_hash = new_hash
            return
        pb: ParsedBatch = self._open["batch"]
        changed = new_hash != self._open["png_hash"]
        result = {"batch": pb.log_line, "screen_changed": changed, "present": present,
                  "feedback": feedback}
        event = {"step": self._open["step"], "batch": pb.log_line, "screen_changed": changed,
                 "feedback": feedback}
        self._open = None
        self._last_hash = new_hash
        self.channel.deliver(Outcome(applied=True, result=result, event=event, png=png or None))
