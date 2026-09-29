"""The VISTA arm's adapter: the chassis driven one entry at a time from a codex thread.

`--memory vista` is the world-model chassis (macros, cursor, vision, governor, the
reflexes -- everything every rung of the ladder shares) with VISTA's memory protocol
in place of the logbook's: no filesystem the model can read, no `logs.txt` it greps,
no frames it opens by path. One codex app-server thread calls `play` with ONE plan
entry -- a procedure call or a raw action held for N ticks, the unit `_log_entry_done`
writes one log section for -- and gets back, when the entry has run, exactly the facts
that section carries (the entry as it ran, [STATE] with `moved`, [INV], [EVENT]s,
[NOTE]s) plus the present state block the logbook arm's turn prompt renders, with the
resulting view steered into the thread. Earlier views are revisited with `inspect`;
`history` is the record of every play; `GUIDE.md` and `WORKING.md` are the model's
two notes; a full context is handed off to a fresh thread through a checkpoint. See
`mfm/vista/__init__.py` for the method and its provenance.

The chassis still writes `logs.txt` (the harness record every arm leaves for analysis;
the model never reads it here) with the model's stated expectation as the [PLAN].

The chassis calls in at four moments, the same shape as the mfm arm's bridge:

    start        `WorldModelAgent.start`     archive the initial view, start the thread
    act_turn     `_act_turn`                 deliver the finished entry's outcome to the
                                             waiting `play`, wait for the next `play`
                                             (up to the turn ceiling), expand and enqueue
    observe      every `observe` tick        intermediate frames of the running entry
    entry_done   `_log_entry_done`           the outcome record, before the section

Two threads meet in `act_turn`: the chassis (the green server's step) and the codex
driver (inside the `play` tool). The chassis waits for a play up to `codex_timeout`
per tick -- the same ceiling the logbook arm gives one codex call -- then runs a no-op
tick and waits again on the next; the driver waits for the outcome as long as the entry
takes. Neither thread ever holds the other's lock.
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from mfm.backend.codex_turn import prepare_codex_home as seed_codex_home
from mfm.vista.archive import FrameArchive
from mfm.vista.channel import ActionChannel
from mfm.vista.controller import Outcome, Validation, VistaController
from mfm.vista.prompt import PLAYER_BASE_INSTRUCTIONS
from mfm.vista.recovery import initial_prompt
from mfm.vista.runner import DEFAULT_IDLE_TIMEOUT, DEFAULT_THREAD_BYTES_BUDGET, AppServerRunner
from mfm.vista.session import VistaSession
from mfm.vista.tools import build_play_tool, build_tools

from mcu_worldmodel.actions import describe_entry, parse_actions
from mcu_worldmodel.memory import norm_yaw, state_line
from mcu_worldmodel.milestones import (held_line, hotbar_line, inventory_counts, location,
                                       nearby_mobs, vitals)

#: The objective sentence the initial prompt and every recovery prompt end with
#: (upstream: "Complete the game with as few game actions as possible.").
OBJECTIVE = ("Complete as many of the task's milestones as you can within the step budget: "
             "every play spends the ticks its entry takes, and the episode ends at the budget.")
EMPTY_GUIDE = "No reliable model yet."

PLAY_DESCRIPTION = (
    "Execute exactly ONE plan entry and observe its result. An entry is either "
    '{"procedure": "<name>", "args": {...}} -- a named procedure from the reference -- or '
    '{"action": {<raw keys>}, "repeat": N} -- a raw action held for N ticks. The result '
    "carries the entry as it ran and the ticks it spent, the [STATE] line with the "
    "distance moved, the inventory delta, the game's own [EVENT] statistics (the ground "
    "truth for what happened), the harness's [NOTE]s (why a procedure stopped, what a "
    "guard refused), the present state block (step budget, milestones, vitals, inventory, "
    "hotbar, held item, nearby entities, GUI, cursor) and the resulting view. The next "
    "call sees this result before another entry can run. An entry the procedure refuses "
    "against the present state returns an error without spending ticks."
)
PLAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "procedure": {"type": "string", "minLength": 1,
                      "description": "A procedure name from the reference (with `args`)."},
        "args": {"type": "object", "description": "The procedure's arguments."},
        "action": {"type": "object",
                   "description": "Raw action keys held for `repeat` ticks (with `repeat`)."},
        "repeat": {"type": "integer", "minimum": 1, "maximum": 400},
    },
}

#: Ticks between archived intermediate frames while an entry runs. A macro is tens of
#: ticks; every tenth frame keeps the archive at ~1,200 frames per 12,000-step run.
DEFAULT_FRAME_EVERY = 10


class VistaCodexShim:
    """What the chassis reads off `self.codex`, for an arm that runs no `codex exec`."""

    session_max_turns = 0

    def __init__(self, bridge: "VistaBridge") -> None:
        self.bridge = bridge

    @property
    def calls(self) -> int:
        return self.bridge.decisions

    def write_system_prompt(self, text: str) -> None:
        (self.bridge.root / "AGENTS.md").write_text(text, encoding="utf-8")
        self.bridge.developer_instructions = text

    def vision_audit(self) -> dict[str, Any]:
        runner = self.bridge.runner
        return {"frames_attached": runner.images_sent if runner else 0,
                "view_image_calls": (runner.dispatcher.calls.get("inspect", 0) if runner else 0),
                "image_attach_failures": 0, "vision_audit_source": "vista"}

    @staticmethod
    def split_briefing(message: str) -> tuple[str, str]:
        from mcu_worldmodel.codex_backend import CodexTurn
        return CodexTurn.split_briefing(message)

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("the vista arm runs no codex exec turns")


class VistaBridge:
    def __init__(self, agent: Any, *, model: str, effort: str, codex_home: Path | None,
                 transcript_dir: Path | None, timeout: float, base_url: str | None = None,
                 options: dict[str, Any] | None = None) -> None:
        opts = dict(options or {})
        # --base-url (the OpenRouter route, gen 4): the provider reaches the app-server
        # thread through its config.toml (mfm/vista/runner.py write_codex_config), the
        # twin of codex_backend's -c set (model_provider=local, name/base_url/wire_api,
        # CODEX_LOCAL_AUTH_COMMAND, CODEX_MODEL_CONTEXT_WINDOW). None keeps the account's
        # hosted models, as every vista run before gen 4 did.
        self.base_url = base_url or None
        self.agent = agent
        self.root: Path = agent.memory.root
        self.model, self.effort = model, effort
        self.timeout = float(timeout)
        self.codex_home = Path(codex_home) if codex_home else None
        self.transcript_dir = Path(transcript_dir) if transcript_dir else self.root.parent / "codex_turns"
        self.thread_bytes = int(opts.get("thread_bytes", DEFAULT_THREAD_BYTES_BUDGET) or 0) or None
        self.frame_every = max(1, int(opts.get("frame_every", DEFAULT_FRAME_EVERY)))
        self.idle_timeout = float(opts.get("idle_timeout", DEFAULT_IDLE_TIMEOUT))
        self.max_invalid_retries = int(opts.get("max_invalid_retries", 15))
        self.close_timeout = float(opts.get("close_timeout", 60.0))
        self.codex_bin = opts.get("codex_bin")
        self.developer_instructions = ""
        self.channel = ActionChannel()
        self.archive: FrameArchive | None = None
        self.controller: VistaController | None = None
        self.runner: AppServerRunner | None = None
        self.session: VistaSession | None = None
        self._lock = threading.Lock()
        self._present: dict[str, Any] = {}
        self._owed: Outcome | None = None
        self._running = False
        self._entry_start_step = 0
        self._last_archived = -10 ** 9
        self._tick_step: int | None = None
        self._tick_deadline = 0.0
        self._idle_since_last = 0
        self.decisions = 0
        self.idle_ticks = 0
        self.refused_entries = 0
        self.dropped_entries = 0
        self.plays_applied = 0
        self._finished = False

    # -- the chassis's calls ------------------------------------------------------------

    def start(self, info: dict, png: bytes | None) -> None:
        if self.codex_home is None:
            self.codex_home = seed_codex_home(Path(str(self.root) + ".codexhome"), hosted=True)
        self.archive = FrameArchive(self.root / "frames")
        if png:
            self.archive.add(0, png)
        width, height = self.archive.size if png else (640, 360)
        with self._lock:
            self._present = self._present_block(info)
        guide = self.root / "GUIDE.md"
        if not guide.exists():
            guide.write_text(EMPTY_GUIDE + "\n", encoding="utf-8")
        self.controller = VistaController(
            bridge=self, archive=self.archive, private_dir=self.root.parent / "vista",
            codex_home=self.codex_home, guide_path=guide, working_path=self.root / "WORKING.md",
            max_invalid_retries=self.max_invalid_retries)
        tools = build_tools(build_play_tool(PLAY_SCHEMA, PLAY_DESCRIPTION), width, height)
        self.runner = AppServerRunner(
            workspace=self.root, codex_home=self.codex_home, io_dir=self.transcript_dir,
            controller=self.controller, tools=tools, base_instructions=PLAYER_BASE_INSTRUCTIONS,
            developer_instructions=self.developer_instructions, model=self.model,
            reasoning_effort=self.effort, codex_bin=self.codex_bin, base_url=self.base_url,
            idle_timeout=self.idle_timeout, thread_bytes_budget=self.thread_bytes,
            objective=OBJECTIVE)
        prompt = initial_prompt(self.controller.initial_metadata(), OBJECTIVE)
        self.session = VistaSession(runner=self.runner, controller=self.controller,
                                    initial_prompt=prompt,
                                    initial_images=tuple(self.controller.initial_image_paths()))
        self.session.start()
        logger.info(f"[vista] session started: home={self.codex_home} frames={self.archive.dir} "
                    f"thread_bytes={self.thread_bytes} frame_every={self.frame_every}")

    def observe(self, info: dict, step: int) -> None:
        """An intermediate frame of the running entry every `frame_every` ticks, under
        the turn the play in progress will get."""
        if not self._running or self.archive is None or self.controller is None:
            return
        if step - self._last_archived < self.frame_every:
            return
        png = self.agent._encode_pov(info.get("pov"), step)
        if png:
            self.archive.add(self.controller.turn + 1, png)
            self._last_archived = step

    @property
    def session_failed(self) -> BaseException | None:
        """The exception that ended the session thread, or None while it can still answer.

        `VistaSession._run` records the failure and forces the controller terminal, but
        nothing on the chassis side reads either, so a dead loop is indistinguishable from
        a slow one: `act_turn` keeps waiting out the full turn ceiling for a play no
        thread will ever make. Measured on abaw_vista (2026-09-07): the loop died at
        step 800 on a checkpoint failure and the arm spent 9.8 h of a 12-core node
        advancing at roughly six steps an hour, which no log line called an error.
        """
        if self.session is None or self.session.alive:
            return None
        return self.session.failure

    def act_turn(self, info: dict) -> None:
        """The chassis's queue is dry: hand the last outcome over, wait for the next
        play within this tick's share of the turn ceiling, expand it, queue it."""
        agent = self.agent
        if self.session is None or self.controller is None:
            return
        if self.session_failed is not None:
            # Nothing will answer. Returning at once costs this tick a noop instead of
            # the whole turn ceiling; the adapter ends the episode on the same signal.
            self.idle_ticks += 1
            return
        step = agent.step
        if self._tick_step != step:
            self._tick_step = step
            self._tick_deadline = time.monotonic() + self.timeout
        # An entry drained inside `next_action` -- a raw attack hold cut short by a
        # break (`_cut_attack_hold`) -- reaches this turn before the next `observe`
        # could write its section, and `next_action` clears `_entry_index` after two
        # empty turns: the section would never be written and the play never answered
        # (lad12a stalled 48 min on `{"attack":1} x100`). Written here the way the
        # marker path writes it: observe has run this tick already.
        if agent._entry_index is not None and not agent.queue:
            agent._log_entry_done(agent._entry_index)
            agent._entry_index = None
        self._deliver(info)
        if self.channel.owed():
            # The play is still unanswered after `_deliver`, so nothing set `_owed`:
            # the entry left the queue without reaching `entry_done`. The guard above
            # only catches an entry that still holds `_entry_index`; the chassis also
            # drops a *running* entry and clears `_entry_index` in the same breath --
            # `queue.clear()` on a gui_click that lifted nothing (agent.py), and seven
            # other sites like it. `take` below would then park with the play owed and
            # both threads would sleep until the walltime (vista1_dragon, step 6109,
            # `craft furnace` on the open table screen). Answer it here instead, with
            # the notes that say why the plan was dropped, and let the model replan.
            self.dropped_entries += 1
            self._owed = self._dropped_outcome()
            self._deliver(info)
        remaining = self._tick_deadline - time.monotonic()
        if remaining <= 0 or self.channel.closed:
            return
        parsed = self.channel.take(remaining)
        if parsed is None:
            self.idle_ticks += 1
            self._idle_since_last += 1
            return
        self.decisions += 1
        plan = parse_actions(json.dumps({"actions": [parsed]}), entry_cap=1,
                             repeat_cap=agent.repeat_cap, step_cap=agent.step_cap,
                             allow_optional=agent.extended_actions, info=info,
                             cursor=agent.cursor.copy())
        # The model's words before the play (its stated expectation) are the section's
        # [PLAN]: the record keeps the prediction beside what happened.
        briefing = (self.runner.last_agent_message if self.runner else "").strip()
        agent.memory.set_plan("", briefing)
        for n in plan.notes:
            agent.memory.add_note(n)
        if not plan.steps:
            self.refused_entries += 1
            self._owed = self._error_outcome(
                "; ".join(plan.notes) or "the entry expanded to no ticks", parsed)
            return
        agent._enqueue(plan)
        if not agent._plan_entries:
            # The governor dropped the plan (one no-op queued, a note pending).
            self.refused_entries += 1
            self._owed = self._error_outcome(
                agent.memory._pending_notes[-1] if agent.memory._pending_notes
                else "the governor refused the entry", parsed)
            return
        self._running = True
        self._entry_start_step = step
        self._last_archived = step

    def entry_done(self, index: int) -> None:
        """The entry finished (`_log_entry_done`, before the section is written): the
        facts the section is about to carry become the play's outcome."""
        agent = self.agent
        if not (0 <= index < len(agent._plan_entries)):
            return
        entry = agent._plan_entries[index]
        sp, cp = agent._entry_start_pos, agent._cur_pos
        moved = (math.hypot(cp["x"] - sp["x"], cp["z"] - sp["z"]) if (sp and cp) else 0.0)
        descended = (sp["y"] - cp["y"]) if (sp and cp) else 0.0
        events = list(agent._pending_events)
        notes = list(agent.memory._pending_notes)
        inv_delta = agent._inventory_delta()
        verified = f"{len(agent.ledger.achieved)}/{len(agent.ledger.cfg)}"
        cursor = ""
        if agent._gui_open:
            cursor = agent.cursor.line(agent._cur_inv, agent._screen)
            grid = agent._grid_line()
            if grid:
                cursor += "\n" + grid
        result: dict[str, Any] = {
            "entry": describe_entry(entry), "ticks": agent.step - self._entry_start_step,
            "state": state_line(cp, sp), "moved": round(moved, 2),
            "descended": round(descended, 2), "inventory_delta": inv_delta,
            "events": events, "notes": notes, "gui_open": bool(agent._gui_open),
            "milestones_verified": verified,
        }
        if cursor:
            result["cursor"] = cursor
        event = {"step": agent.step, "entry": result["entry"], "ticks": result["ticks"],
                 "moved": result["moved"], "descended": result["descended"],
                 "inventory_delta": inv_delta, "events": events, "notes": notes,
                 "milestones_verified": verified}
        self._owed = Outcome(applied=True, result=result, event=event)
        self._running = False
        self.plays_applied += 1

    def finish(self) -> None:
        """The episode's last step: a waiting play gets a terminal result and the
        session is closed."""
        if self._finished or self.controller is None or self.session is None:
            return
        self._finished = True
        self.controller.force_terminal("episode_end")
        with self._lock:
            present = dict(self._present)
        self.channel.close(Outcome(applied=False, result={"present": present}, terminal=True))
        self.session.close(self.close_timeout)

    def audit(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "decisions": self.decisions, "plays_applied": self.plays_applied,
            "refused_entries": self.refused_entries,
            "dropped_entries": self.dropped_entries, "idle_ticks": self.idle_ticks,
            "frame_every": self.frame_every, "turn_ceiling_s": self.timeout,
            "channel": {"plays": self.channel.plays, "deliveries": self.channel.deliveries},
        }
        if self.session is not None:
            out.update(self.session.audit())
        return out

    # -- the controller's bridge (the codex driver's thread) ---------------------------------

    def validate(self, arguments: Any) -> Validation:
        if not isinstance(arguments, dict):
            return Validation(False, "play takes one object: {procedure, args} or {action, repeat}.")
        extra = set(arguments) - {"procedure", "args", "action", "repeat"}
        if extra:
            return Validation(False, f"unknown keys {sorted(extra)}; an entry is {{procedure, args}} "
                                     f"or {{action, repeat}}.")
        has_proc, has_act = "procedure" in arguments, "action" in arguments
        if has_proc == has_act:
            return Validation(False, "give exactly one of `procedure` (with `args`) or `action` "
                                     "(with `repeat`).")
        if has_proc:
            name, args = arguments.get("procedure"), arguments.get("args", {})
            if not isinstance(name, str) or not name.strip():
                return Validation(False, "`procedure` must be a non-empty name.")
            if args is None:
                args = {}
            if not isinstance(args, dict):
                return Validation(False, "`args` must be an object.")
            if "repeat" in arguments:
                return Validation(False, "`repeat` belongs to a raw `action`, not a procedure.")
            entry = {"procedure": name.strip(), "args": dict(args)}
        else:
            action, repeat = arguments.get("action"), arguments.get("repeat", 1)
            if not isinstance(action, dict) or not action:
                return Validation(False, "`action` must be a non-empty object of raw keys.")
            if type(repeat) is not int or repeat < 1:
                return Validation(False, "`repeat` must be a positive integer.")
            if "args" in arguments:
                return Validation(False, "`args` belongs to a procedure, not a raw action.")
            entry = {"action": dict(action), "repeat": repeat}
        return Validation(True, parsed=entry, public=entry)

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

    # -- helpers (the chassis's thread) ----------------------------------------------------

    def _deliver(self, info: dict) -> None:
        if self._owed is None:
            return
        outcome, self._owed = self._owed, None
        if not self.channel.owed():
            return
        present = self._present_block(info)
        with self._lock:
            self._present = present
        if outcome.applied:
            outcome.png = self.agent._encode_pov(info.get("pov"), self.agent.step)
            for n in self.agent.memory._pending_notes:
                if n not in outcome.result["notes"]:
                    outcome.result["notes"].append(n)
        outcome.result["present"] = present
        if self._idle_since_last:
            outcome.result["noop_ticks_waiting_for_play"] = self._idle_since_last
            self._idle_since_last = 0
        self.channel.deliver(outcome)

    def _dropped_outcome(self) -> Outcome:
        """The outcome for a play whose entry was dropped mid-flight. Not `applied`:
        the entry did not run to completion, and the model is told so in the words the
        chassis already wrote into its pending notes."""
        agent = self.agent
        notes = list(agent.memory._pending_notes)
        return Outcome(
            applied=False,
            error="the entry was dropped before it finished, so it has no outcome; "
                  "read the notes and the present block, then replan from what you see.",
            result={"entry": "dropped", "notes": notes,
                    "milestones_verified": f"{len(agent.ledger.achieved)}/{len(agent.ledger.cfg)}"})

    def _error_outcome(self, error: str, entry: Any) -> Outcome:
        return Outcome(applied=False, error=error,
                       result={"entry": describe_entry(entry) if "steps" in entry
                               else json.dumps(entry, separators=(",", ":"))})

    def _present_block(self, info: dict) -> dict[str, Any]:
        agent = self.agent
        inv = inventory_counts(info)
        free = _empty_slot_count(info)
        pos = location(info)
        pos_line = (f"pos=({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}) "
                    f"pitch={pos['pitch']:.0f} yaw={norm_yaw(pos['yaw']):.0f}") if pos else "unknown"
        block: dict[str, Any] = {
            "step": agent.step, "max_steps": agent.max_steps,
            "steps_remaining": max(0, agent.max_steps - agent.step),
            "stall_turns": agent._stall_turns,
            "position": pos_line, "vitals": vitals(info),
            "inventory": ", ".join(f"{k}x{v}" for k, v in sorted(inv.items())[:24]) or "empty",
            "free_slots": free, "hotbar": hotbar_line(info), "held": held_line(info),
            "nearby_entities": nearby_mobs(info),
            "gui_open": bool(info.get("isGuiOpen", False)),
            "cursor": agent.cursor.line(inv),
        }
        if agent.ledger.cfg:
            block["milestones"] = agent.ledger.progress_line()
            block["milestones_block"] = agent.ledger.progress_block()
        grid = agent._grid_line()
        if grid:
            block["grid"] = grid
        return block


def _empty_slot_count(info: dict) -> int | None:
    from mcu_worldmodel.agent import _empty_slot_count as f
    return f(info)
