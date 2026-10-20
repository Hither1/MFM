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
import os
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
                                       main_rows_line, nearby_mobs, vitals)

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

#: `--no-primitives`: the play tool with no procedure to name -- a raw action per call.
PLAY_DESCRIPTION_RAW = (
    PLAY_DESCRIPTION
    .replace("An entry is either "
             '{"procedure": "<name>", "args": {...}} -- a named procedure from the reference -- or '
             '{"action": {<raw keys>}, "repeat": N} -- a raw action held for N ticks.',
             'An entry is {"action": {<raw keys>}, "repeat": N} -- a raw action held for N '
             "ticks; this run has no named procedures.")
    .replace("(why a procedure stopped, what a guard refused)", "(what the harness saw)")
    .replace("hotbar, held item,", "hotbar, main rows, held item,")
    .replace(" An entry the procedure refuses against the present state returns an error "
             "without spending ticks.", ""))
assert PLAY_DESCRIPTION_RAW.count("procedure") == 1, PLAY_DESCRIPTION_RAW
PLAY_SCHEMA_RAW: dict[str, Any] = {
    **PLAY_SCHEMA,
    "properties": {k: v for k, v in PLAY_SCHEMA["properties"].items()
                   if k in ("action", "repeat")},
    "required": ["action"],
}

#: The controller's termination reasons that mean a budget ran out (`--model-step-budget`,
#: `--turn-budget`): the life goes on idle.
BUDGET_REASONS = frozenset({"model_step_budget", "turn_budget"})

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
        # --base-url (the OpenRouter route): the provider reaches the app-server
        # thread through its config.toml (mfm/vista/runner.py write_codex_config), the
        # twin of codex_backend's -c set (model_provider=local, name/base_url/wire_api,
        # CODEX_LOCAL_AUTH_COMMAND, CODEX_MODEL_CONTEXT_WINDOW). None keeps the account's
        # hosted models, as the vista runs on the account did.
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
        #: `--vista-aligned`: a `play` runs a plan (the other arms' 40 entries / 400 ticks);
        #: the results of the plan's entries so far, and the plan's first step.
        self.aligned = bool(getattr(agent, "vista_aligned", False))
        self._plan_results: list[dict[str, Any]] = []
        self._plan_start_step = 0

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
        if self.aligned:
            play = play_plan_tool(self.agent.primitives, self.agent.entry_cap,
                                  self.agent.step_cap)
        else:
            play = ((PLAY_SCHEMA, PLAY_DESCRIPTION) if self.agent.primitives
                    else (PLAY_SCHEMA_RAW, PLAY_DESCRIPTION_RAW))
        tools = build_tools(build_play_tool(*play), width, height)
        self.runner = AppServerRunner(
            workspace=self.root, codex_home=self.codex_home, io_dir=self.transcript_dir,
            controller=self.controller, tools=tools, base_instructions=PLAYER_BASE_INSTRUCTIONS,
            developer_instructions=self.developer_instructions, model=self.model,
            reasoning_effort=self.effort, codex_bin=self.codex_bin, base_url=self.base_url,
            idle_timeout=self.idle_timeout, thread_bytes_budget=self.thread_bytes,
            objective=OBJECTIVE,
            model_step_limit=getattr(self.agent, "model_step_budget", None),
            play_limit=getattr(self.agent, "turn_budget", None),
            **({"compact_thresholds": aligned_thresholds(self.model, self.codex_home)}
               if self.aligned else {}))
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
        thread will ever make. Measured: the loop died at
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
        if self.controller.termination_reason in BUDGET_REASONS:
            # The budget is spent: the rest of the life runs idle, with no play to wait for.
            self.idle_ticks += 1
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
        # (one run stalled 48 min on `{"attack":1} x100`). Written here the way the
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
            # both threads would sleep until the walltime (one run, step 6109,
            # `craft furnace` on the open table screen). Answer it here instead, with
            # the notes that say why the plan was dropped, and let the model replan.
            self.dropped_entries += 1
            self._owed = (self._plan_outcome(cut_short=True)
                          if self.aligned and self._plan_results else self._dropped_outcome())
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
        plan = parse_actions(json.dumps({"actions": parsed if self.aligned else [parsed]}),
                             entry_cap=agent.entry_cap if self.aligned else 1,
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
        self._plan_results, self._plan_start_step = [], step

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
        if self.aligned:
            # One plan per play: answered once its last entry is done (a plan the chassis
            # drops part-way is answered in `act_turn`, with the entries that ran).
            self._plan_results.append(result)
            self._entry_start_step = agent.step
            last = index >= len(agent._plan_entries) - 1
            if not last and agent.queue:
                return
            # an entry that is not the last, with nothing queued behind it: the chassis
            # dropped the rest of the plan (a milestone verified, a click that missed)
            self._owed = self._plan_outcome(cut_short=not last)
            return
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
        if not self.aligned:
            return self._validate_entry(arguments)
        cap = self.agent.entry_cap
        if not isinstance(arguments, dict) or set(arguments) != {"actions"}:
            return Validation(False, "play takes one object: {\"actions\": [entry, ...]}.")
        entries = arguments["actions"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= cap:
            return Validation(False, f"`actions` must be a list of 1 to {cap} entries.")
        parsed = []
        for i, e in enumerate(entries):
            v = self._validate_entry(e)
            if not v.ok:
                return Validation(False, f"entry {i + 1}: {v.error}")
            parsed.append(v.parsed)
        return Validation(True, parsed=parsed, public={"actions": parsed})

    def _validate_entry(self, arguments: Any) -> Validation:
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
            # `--vista-aligned`: an empty action is a wait, as the exec arms' plans allow
            if not isinstance(action, dict) or (not action and not self.aligned):
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
            # (a plan's entries carry their own notes: only what came after them is added)
            seen = {n for e in outcome.result.get("entries", ()) for n in e.get("notes", ())}
            for n in self.agent.memory._pending_notes:
                if n not in outcome.result["notes"] and n not in seen:
                    outcome.result["notes"].append(n)
        outcome.result["present"] = present
        if self._idle_since_last:
            outcome.result["noop_ticks_waiting_for_play"] = self._idle_since_last
            self._idle_since_last = 0
        self.channel.deliver(outcome)

    def _plan_outcome(self, *, cut_short: bool) -> Outcome:
        """`--vista-aligned`: one plan's outcome -- each entry that ran, as the one-entry
        play reports it, and the plan's total ticks; `cut_short` when the chassis dropped
        the rest of it (the notes say why)."""
        agent = self.agent
        entries, self._plan_results = self._plan_results, []
        result: dict[str, Any] = {
            "entries": entries, "ticks": agent.step - self._plan_start_step,
            "notes": list(agent.memory._pending_notes) if cut_short else [],
            "milestones_verified": f"{len(agent.ledger.achieved)}/{len(agent.ledger.cfg)}"}
        if cut_short:
            result["cut_short"] = (f"{len(entries)} of {len(agent._plan_entries)} entries ran; "
                                   "the rest of the plan was dropped")
        event = {"step": agent.step, "entries": [e["entry"] for e in entries],
                 "ticks": result["ticks"], "cut_short": cut_short,
                 "events": [ev for e in entries for ev in e["events"]],
                 "milestones_verified": result["milestones_verified"]}
        self._running = False
        self.plays_applied += 1
        return Outcome(applied=True, result=result, event=event)

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
            "free_slots": free, "hotbar": hotbar_line(info),
            # `--no-primitives`: with no `craft` to find the ingredients, a click needs
            # the slot NUMBER
            **({} if agent.primitives else {"main_rows": main_rows_line(info)}),
            "held": held_line(info),
            "nearby_entities": nearby_mobs(info),
            "gui_open": bool(info.get("isGuiOpen", False)),
            "cursor": agent.cursor.line(inv),
        }
        budget = getattr(agent, "model_step_budget", None)
        if budget is not None:
            used = self.runner.model_steps() if self.runner else 0
            block["model_steps"] = f"{used} of {budget} used"
        turns = getattr(agent, "turn_budget", None)
        if turns is not None:
            used = self.runner.dispatcher.calls.get("play", 0) if self.runner else 0
            block["turns"] = f"your next play is turn {used + 1} of {turns}"
        if agent.ledger.cfg:
            block["milestones"] = agent.ledger.progress_line()
            block["milestones_block"] = agent.ledger.progress_block()
        grid = agent._grid_line()
        if grid:
            block["grid"] = grid
        return block


#: `--vista-aligned`: the play tool takes a plan, at the other arms' caps.
def play_plan_tool(primitives: bool, entry_cap: int, step_cap: int) -> tuple[dict[str, Any], str]:
    entry = ('{"procedure": "<name>", "args": {...}} -- a named procedure from the reference -- or '
             '{"action": {<raw keys>}, "repeat": N} -- a raw action held for N ticks'
             if primitives else
             '{"action": {<raw keys>}, "repeat": N} -- a raw action held for N ticks; this run '
             'has no named procedures')
    description = (
        f"Execute ONE plan -- a list of at most {entry_cap} entries, totalling at most "
        f"{step_cap} environment ticks, run in order -- and observe its result. An entry is "
        f"{entry}. The result carries, for every entry that ran, the entry as it ran and "
        "the ticks it spent, the [STATE] line with the distance moved, the inventory delta, "
        "the game's own [EVENT] statistics (the ground truth for what happened) and the "
        "harness's [NOTE]s; then the present state block and the view after the plan. "
        "When the harness drops the rest of a plan (a milestone verified, a click that "
        "changed nothing), `cut_short` says how many entries ran. The next call sees "
        "this result before another plan can run.")
    schema: dict[str, Any] = {
        "type": "object", "additionalProperties": False, "required": ["actions"],
        "properties": {"actions": {
            "type": "array", "minItems": 1, "maxItems": entry_cap,
            "items": {"type": "object", "description": (
                "{procedure, args} or {action, repeat}" if primitives
                else "{action, repeat}: raw keys held for `repeat` ticks")}}}}
    return schema, description


def aligned_thresholds(model: str, codex_home: Path | None):
    """`--vista-aligned`: the checkpoint handoff fires where the exec arms' CLI
    compacts (CODEX_AUTO_COMPACT_TOKEN_LIMIT, run-arm.sh's 100k for a one-session life),
    not at the model's window less a reserve."""
    from mfm.vista.runner import (CHECKPOINT_TURN_HEADROOM, CompactThresholds,
                                  resolve_compact_thresholds)
    base = resolve_compact_thresholds(model, codex_home=codex_home)
    limit = int(os.environ.get("CODEX_AUTO_COMPACT_TOKEN_LIMIT") or 100_000)
    return CompactThresholds(base.model_context_window, limit,
                             min(limit + CHECKPOINT_TURN_HEADROOM,
                                 base.checkpoint_auto_compact_limit),
                             f"aligned with the exec arms ({limit})")


def _empty_slot_count(info: dict) -> int | None:
    from mcu_worldmodel.agent import _empty_slot_count as f
    return f(info)
