"""The MFM arm on a cua-lite GUI episode (cua.bench.local.kicad).

Presents the interface ``run_eval.py`` drives -- ``predict(instruction, screenshot_png,
step_idx, max_steps) -> (reply, tool_calls, done)``, ``add_feedback``, ``audit`` -- and
emits exactly the direct arm's tool calls through ``gym_codex.actions.parse_batch``.
What the model has between steps:

- an append-only ``logs.txt`` (one section per turn: feedback, screenshot path,
  executed actions, the model's own plan), a persistent workspace, and a codex thread
  resumed across turns under an age cap;
- the episode store beside the log: one episode per action batch (screenshot, state,
  action, outcome), the index and its query tool, and recall of earlier episodes;
- a plan of up to ``PLAN_CAP`` batches, drained one batch per step under the flush
  rules of ``flush_reason``;
- with ``carry_dir``, the records of the finished tasks under ``previous/`` with their
  scores, and its own ``notes/`` across tasks (``mfm/memory/carry.py``).

As in the paper's runs, one design call at reasoning effort ``DESIGN_EFFORT`` comes
before the first action turn (``mfm_prompts.DESIGN_PROMPT``), and the system prompt
has the schematic conventions (``mfm_prompts.CONVENTIONS_NOTE``).

The turn protocol, the retry loop and the memory hooks are
``mfm.agent.base.MemoryAgent``; this file is what is KiCad: the section rendering, the
prompts, the batch parser, and the driver shim.

An episode is one task: the workspace lives under the task's output directory and is
created empty for it.

Failure semantics match the direct arm at the driver boundary: a turn that produced no
usable ``actions.json`` after the arm's own retries is a no-op step with feedback (a
model behaviour to measure), and a turn the infrastructure would not run at all
raises, so ``run_eval``'s backoff-then-force-terminate path applies identically. A
retried ``predict`` continues the turn it opened rather than logging a second one.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from gym_codex import mfm_prompts
from gym_codex.actions import ParsedBatch, parse_batch
from gym_codex.mfm_prompts import (DESIGN_EXISTING, DESIGN_PROMPT, MFM_MEMORY_NOTE,
                                   PLAN_QUEUE_NOTE, RECALL_NOTE)
from mfm.agent.base import MemoryAgent, Observation, Plan
from mfm.backend import errors as backend_errors
from mfm.backend.codex_turn import CodexTurn
from mfm.memory.carry import CarrySink
from mfm.memory.log import EpisodeLog, install_zoom_tool, prepare_workspace
from mfm.memory.store import EpisodeStore

logger = logging.getLogger("gym_codex.mfm")

#: In-arm attempts per turn before it is scored as a no-op.
DEFAULT_ANALYZER_RETRIES = 3
#: A memory turn greps a log, opens frames and writes files before it answers; the
#: direct arm's 360 s is for a single-shot call.
DEFAULT_ACT_TIMEOUT = 900
#: The design call: its ceiling, and its reasoning effort (the action turns run at the
#: run's own effort).
DEFAULT_DESIGN_TIMEOUT = 1800
DESIGN_EFFORT = "high"
#: The resumed thread re-sends every prior screenshot (~500 KB each) with each call;
#: past ~5.5 MB on the wire the first call of a turn stalls (mfm/backend/codex_turn.py).
#: Six turns of 1920x1080 PNG stay under it.
DEFAULT_SESSION_TURNS = 6

RETRY_NUDGE = ("Your previous attempt at this turn produced no usable ./actions.json. "
               "Write it now, before anything else.")

NO_ARTIFACT_FEEDBACK = ("Your turn produced no parseable ./actions.json; nothing was "
                        "executed. Write the file as instructed.")

#: Batches one turn may queue (the plan contract in `mfm_prompts.PLAN_QUEUE_NOTE`).
PLAN_CAP = 5
#: Actions after which an unchanged screen means the GUI did not take the input.
_INPUT_ACTIONS = {"click", "double_click", "right_click", "type", "key", "hotkey", "drag"}


class MfmGuiAgent(MemoryAgent):
    """MFM: the full log every turn, the current screenshot attached, one thread
    resumed under an age cap, the episode store and the plan queue."""

    arm = "mfm"
    # This arm's loop: a refusal or a capacity error extends the budget (the latter
    # with backoff); anything else spends it; a transient infrastructure failure at the
    # end is the driver's to retry.
    retry_policy = "extend"
    retry_nudge = RETRY_NUDGE
    unusable_error = "actions.json did not parse as a JSON object"
    write_system_prompt_on_first_step = True
    cli = "codex"

    def __init__(self, *, workspace: Path, model: str, effort: str, max_steps: int,
                 transcript_dir: Optional[Path] = None, codex_home: Optional[str] = None,
                 timeout: int = DEFAULT_ACT_TIMEOUT, session_turns: Optional[int] = None,
                 analyzer_retries: int = DEFAULT_ANALYZER_RETRIES,
                 base_url: Optional[str] = None,
                 carry_dir: Optional[Path] = None, task_id: Optional[str] = None,
                 cli: str = "codex") -> None:
        # Which CLI carries the model (`run_eval.py --cli`): codex, or Anthropic models
        # through Claude Code on the same workspace, prompt, log and actions.json.
        self.cli = cli
        # The design turn: one call at its own reasoning effort before the first action
        # turn, on a CodexTurn of its own in the same workspace, whose output is
        # `design.md` + `intent.json`. The action turns build from those files; the
        # system prompt says so (DESIGN_NOTE). Every design error measured on the
        # from-scratch tasks was in the plan the model wrote at effort low and then
        # executed faithfully, so the plan is what is spent on.
        self.design_effort = DESIGN_EFFORT
        self.design_result: dict[str, Any] | None = None
        # On a task whose project already holds a schematic, the driver reads its
        # netlist back before the design call and `seed_design` keeps the summary the
        # call is shown (DESIGN_EXISTING); None on a from-scratch task.
        self.design_existing: str | None = None
        record = prepare_workspace(Path(workspace))
        log = EpisodeLog(record, attachment_dirs=("frames",))
        # The frame tool the system prompt promises (`./tools/zoom.py`).
        install_zoom_tool(record)
        # The episode store beside the log, and a multi-batch plan drained one batch per
        # step with the flush rules below.
        self.store = EpisodeStore(record, recall=True)
        self.mfm_memory_note = "\n\n".join(
            (MFM_MEMORY_NOTE, RECALL_NOTE, PLAN_QUEUE_NOTE.replace("{plan_cap}", str(PLAN_CAP))))
        # The carry rung (mfm/memory/carry.py): the finished tasks' records with their
        # scores, and a persistent notes/ inside this task's workspace.
        self.carry = (CarrySink(Path(carry_dir), task_id or Path(workspace).parent.name,
                                record, outcomes=True) if carry_dir else None)
        if cli == "claude":
            # model_channel/claude_backend.py: CodexTurn's surface on `claude -p`, with a
            # per-episode config dir beside the workspace.
            from model_channel.claude_backend import ClaudeTurn
            codex = ClaudeTurn(
                record, model=model, artifact_name="actions.json",
                reasoning_effort=effort, timeout=timeout,
                transcript_dir=Path(transcript_dir) if transcript_dir else None,
                session_max_turns=(DEFAULT_SESSION_TURNS if session_turns is None
                                   else session_turns),
                base_url=base_url,
            )
        elif cli == "codex":
            codex = CodexTurn(
                record, model=model, artifact_name="actions.json",
                reasoning_effort=effort, timeout=timeout,
                codex_home=Path(codex_home) if codex_home else None,
                transcript_dir=Path(transcript_dir) if transcript_dir else None,
                session_max_turns=(DEFAULT_SESSION_TURNS if session_turns is None
                                   else session_turns),
                base_url=base_url,
            )
        else:
            raise ValueError(f"unknown cli {cli!r} (codex|claude)")
        super().__init__(visible=record, record_dir=record, log=log, codex=codex,
                         analyzer_retries=analyzer_retries,
                         sinks=[s for s in (self.store, self.carry) if s])
        self.max_steps = max_steps
        self._prev_hash: str | None = None
        self._call_seq = 0
        self._pending_feedback: str | None = None
        # The turn the driver is currently asking about, once its section is written.
        # A `predict` retried by the driver after an infra failure re-enters here and
        # must not log a second section for the same step.
        self._open: dict[str, Any] | None = None
        self._task: str | None = None
        self._last_message = ""
        self._noop: tuple[ParsedBatch, str] | None = None
        self._open_hash: str | None = None

    # -- driver interface ------------------------------------------------------

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
        if self._open is None:
            self.max_steps = max_steps
            if self._task is None:
                self._task = instruction
            self.turn += 1
            step = step_idx + 1
            rel = self.log.save_attachment(f"frames/step_{step:04d}.png", screenshot_png or b"")
            feedback = self._pending_feedback
            self._pending_feedback = None
            title = f"Turn {self.turn} | Step {step}/{max_steps}"
            if self.queue:
                head = self.queue[0]
                title += f" | Plan Step {head['index']}/{head['total']}"
            self._prev_hash = self._open_hash
            self._open_hash = _png_hash(screenshot_png)
            self._open = {"title": title, "step": step, "rel": rel, "feedback": feedback,
                          "abs": self.visible / rel, "png_hash": self._open_hash}
            self.observe(Observation(step=step, attachment=rel,
                                     state={"png_hash": self._open["png_hash"],
                                            "feedback": feedback}, raw=self._open))
            if self.turn == 1 and self.design_result is None:
                # After the first section and AGENTS.md exist, before the first act
                # call: the design files are in the workspace when it is published.
                self._run_design_turn()
        item = self.act(self._obs)
        if item is None:
            assert self._noop is not None
            pb, message = self._noop
        else:
            pb, message = item["entry"]["batch"], item["entry"]["message"]
        self._close_turn(pb, message)
        return message, pb.calls, pb.done

    def audit(self) -> dict[str, Any]:
        out = super().audit()
        out["mfm"] = {**self.store.audit(self), "plan_queue": True,
                      "plan_flushes": self.plan_flushes}
        if self.carry is not None:
            out["carry"] = self.carry.audit()
        out["design"] = self.design_result or {"ok": False, "error": "not run"}
        out["conventions"] = True
        return out

    def finish(self, reward: Any = None, error: Any = None, **outcome: Any) -> None:
        super().finish(reward=reward, error=error, **outcome)

    # -- the turn protocol, as MemoryAgent hooks ------------------------------

    def _tool_call(self, name: str, args: dict) -> dict:
        self._call_seq += 1
        return {"id": f"call_{self._call_seq:04d}", "type": "function",
                "function": {"name": name, "arguments": args}}

    def system_prompt(self) -> str:
        return mfm_prompts.build_system_prompt(self.max_steps)

    # -- the design turn ----------------------------------------------------------

    def _design_codex(self) -> CodexTurn:
        """A CodexTurn of the design turn's own: same workspace, model, home and
        endpoint as the act thread, its own effort, closing-message file and transcript
        dir, never resumed -- and never resumed *from*: the act thread starts cold."""
        main = self.codex
        if self.cli == "claude":
            from model_channel.claude_backend import ClaudeTurn
            return ClaudeTurn(
                self.visible, model=main.model, artifact_name=".design.unused",
                reasoning_effort=self.design_effort, base_url=main.base_url,
                claude_bin=main.claude_bin, config_dir=main.config_dir,
                timeout=DEFAULT_DESIGN_TIMEOUT,
                transcript_dir=(main.transcript_dir / "design" if main.transcript_dir else None),
                session_max_turns=1,
            )
        return CodexTurn(
            self.visible, model=main.model, artifact_name=".design.unused",
            message_name=".design.msg", reasoning_effort=self.design_effort,
            base_url=main.base_url, codex_bin=main.codex_bin, codex_home=main.codex_home,
            timeout=DEFAULT_DESIGN_TIMEOUT,
            transcript_dir=(main.transcript_dir / "design" if main.transcript_dir else None),
            session_max_turns=1,
        )

    def seed_design(self, netlist: str) -> bool:
        """Hand the design call the project's existing schematic (a KiCad netlist as
        `kicad-cli` exports it), summarised to parts and nets. Returns whether the
        netlist held any part; an empty project seeds nothing."""
        summary = netlist_summary(netlist)
        self.design_existing = summary
        return summary is not None

    def _run_design_turn(self) -> None:
        assert self._task is not None
        t0 = time.time()
        turn = self._design_codex()
        existing = (DESIGN_EXISTING.format(summary=self.design_existing)
                    if self.design_existing else "")
        prompt = DESIGN_PROMPT.format(task=self._task.strip(), existing=existing)
        result: dict[str, Any] = {"ok": False, "message": "", "error": "not attempted"}
        for attempt in range(1 + backend_errors.FILTER_RETRIES):
            result = turn.run(prompt, images=(), expect_artifact=False,
                              timeout=DEFAULT_DESIGN_TIMEOUT)
            if result["ok"] or not backend_errors.is_filter_refusal(result.get("error")):
                break
            logger.warning("[%s] design turn declined (attempt %d)", self.arm, attempt + 1)
        design_md = self.visible / "design.md"
        intent = _load_intent(self.visible / "intent.json")
        seconds = round(time.time() - t0, 1)
        self.design_result = {
            "ok": bool(result.get("ok")), "error": result.get("error"),
            "effort": self.design_effort, "seconds": seconds,
            "design_md": design_md.exists(),
            "intent_json": intent is not None,
            "parts": len(intent["parts"]) if intent else None,
            "nets": len(intent["nets"]) if intent else None,
            "existing": self.design_existing is not None,
            # The design thread's own counters (the act thread's audit never sees it).
            "codex_calls": turn.calls,
            **{f"codex_{k}": v for k, v in turn.audit().items()
               if k.endswith("_tokens") or k in ("timeout_resets", "session_resets")},
        }
        if design_md.exists():
            what = "./design.md"
            if intent is not None:
                what += (f" and ./intent.json ({len(intent['parts'])} parts, "
                         f"{len(intent['nets'])} nets)")
            seen = ", given the existing schematic" if self.design_existing else ""
            self.note(f"design turn (reasoning effort {self.design_effort}, {seconds:.0f}s"
                      f"{seen}) wrote {what}; the action turns build from it")
        else:
            self.note(f"design turn (reasoning effort {self.design_effort}, {seconds:.0f}s) "
                      f"produced no ./design.md ({result.get('error') or 'no file'}); "
                      f"design as you build")
        logger.info("[%s] design turn: %s", self.arm, json.dumps(self.design_result))

    def initial_section(self, obs: Observation) -> tuple[str, list[str]]:
        assert self._task is not None
        return "Turn 0 | EPISODE START", [
            f"[TASK] {self._task.strip()}",
            f"Step budget: {self.max_steps}. One section per turn follows. No section "
            f"carries a score: nothing tells you whether the task is going well.",
        ]

    def section(self, prev_item: dict[str, Any] | None,
                obs: Observation) -> tuple[str, list[str]] | None:
        assert self._open is not None
        lines = []
        if self._open["feedback"]:
            lines.append(f"[FEEDBACK] {self._open['feedback']}")
        lines.append(f"[SCREEN] {self._open['rel']}")
        return self._open["title"], lines

    def turn_prompt(self, obs: Observation) -> str:
        assert self._open is not None
        return mfm_prompts.build_turn_prompt(
            is_first=self.turn == 1, turns=self.turn - 1, step=self._open["step"],
            max_steps=self.max_steps)

    def parse_plan(self, result: dict[str, Any]) -> Plan | None:
        obj = _load_artifact(result["artifact"])
        if obj is None:
            return None
        message = result.get("message") or ""
        batches = [obj]
        if isinstance(obj.get("plan"), list) and obj["plan"]:
            # `{"plan": [batch, ...]}`: each batch parses exactly as a one-batch turn
            # would; a non-object batch is that turn's "no JSON" no-op.
            batches = [b if isinstance(b, dict) else None for b in obj["plan"][:PLAN_CAP]]
        pbs = [parse_batch(b, self._tool_call, no_json_feedback=NO_ARTIFACT_FEEDBACK)
               for b in batches]
        return Plan(entries=[{"batch": pb, "message": message} for pb in pbs],
                    ticks=[1] * len(pbs), steps=pbs, think=_briefing_and_plan(message),
                    extra=message)

    def flush_reason(self, obs: Observation) -> str | None:
        """The plan queue's flush rules. After a one-batch plan the queue is empty
        here and nothing fires."""
        if not self.queue:
            return None
        assert self._open is not None
        if self._open["feedback"]:
            return "env feedback arrived for the last batch"
        prev = self._prev_item
        if prev is not None and self._prev_hash is not None \
                and self._open_hash == self._prev_hash:
            pb = prev["entry"]["batch"]
            if any(a.get("action") in _INPUT_ACTIONS
                   for c in pb.calls for a in (c["function"]["arguments"].get("actions") or [])):
                return "screen unchanged after an input batch"
        if self.queue[0]["entry"]["batch"].done:
            return "a queued terminate must be decided on the current screen"
        return None

    def adopt_plan(self, plan: Plan, result: dict[str, Any]) -> None:
        # The plan is appended to the open section at close, with the actions.
        pass

    def on_no_plan(self, result: dict[str, Any]) -> None:
        self.parse_failures += 1
        self.no_op_turns += 1
        reason = result.get("error") or "no usable actions.json"
        key = backend_errors.default_reason_key(str(reason))
        # Attribute honestly: the note is history the model reads back as its own.
        if key in ("other",):
            self.log.add_note(f"turn {self.turn} produced no usable ./actions.json after "
                              f"{self.analyzer_retries} attempts; nothing was executed")
            feedback = NO_ARTIFACT_FEEDBACK
        else:
            self.log.add_note(f"turn {self.turn}: the backend failed ({key}: "
                              f"{str(reason)[:200]}); nothing was executed and the "
                              f"turn was not the model's to lose")
            feedback = None
        pb = ParsedBatch([], False, feedback, "(no actions.json; nothing executed)")
        self._noop = (pb, result.get("message") or "")

    # -- what the episode store records ----------------------------------------------

    def episode_state(self, obs: Observation) -> dict[str, Any]:
        return {"step": obs.step, "max_steps": self.max_steps,
                "png_sha256": obs.state.get("png_hash"), "feedback": obs.state.get("feedback")}

    def episode_action(self, item: dict[str, Any]) -> Any:
        pb = item["entry"]["batch"]
        return {"actions": pb.calls, "log_line": pb.log_line, "done": pb.done,
                "message": item["entry"]["message"][:2000]}

    def episode_action_kind(self, item: dict[str, Any]) -> str | None:
        pb = item["entry"]["batch"]
        if not pb.calls:
            return "noop"
        fn = pb.calls[0]["function"]
        if fn["name"] == "computer":
            return "+".join(a.get("action", "?") for a in fn["arguments"].get("actions") or [])
        return fn["name"]

    def episode_outcome(self, entry: Any, first: dict[str, Any], last: dict[str, Any],
                        notes: list[str], flushed: bool) -> tuple[dict[str, Any], list[str], str]:
        pb = entry["batch"]
        observed_after = last.get("step") != first.get("step")
        screen_changed = observed_after and last.get("png_sha256") != first.get("png_sha256")
        feedback = last.get("feedback") if observed_after else None
        tags = []
        if feedback:
            tags.append("feedback")
        if observed_after and not screen_changed:
            tags.append("screen_unchanged")
        if pb.done:
            tags.append("terminate")
        return ({"feedback": feedback, "next_png_sha256": last.get("png_sha256"),
                 "screen_changed": screen_changed, "terminate": pb.done}, tags, pb.log_line[:120])

    def _close_turn(self, pb: ParsedBatch, message: str) -> None:
        assert self._open is not None
        self.act_turns += 1
        think = _briefing_and_plan(message)
        self.log.append_lines([f"[ACTIONS] {pb.log_line}"], plan=think)
        if pb.feedback:
            self.add_feedback(pb.feedback)
        self._open = None
        self._noop = None


# -- helpers ------------------------------------------------------------------------

def _png_hash(png: bytes) -> str:
    return hashlib.sha256(png or b"").hexdigest()


def _sexpr(text: str) -> list:
    """A KiCad S-expression as nested lists of strings (quoted strings unquoted)."""
    stack: list[list] = [[]]
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|([()])|([^\s()"]+)', text):
        if m.group(2) == "(":
            stack.append([])
        elif m.group(2) == ")":
            if len(stack) > 1:
                node = stack.pop()
                stack[-1].append(node)
        elif m.group(1) is not None:
            stack[-1].append(m.group(1))
        else:
            stack[-1].append(m.group(3))
    while len(stack) > 1:                     # unbalanced input: close what is open
        node = stack.pop()
        stack[-1].append(node)
    return stack[0][0] if stack[0] and isinstance(stack[0][0], list) else []


def netlist_summary(text: str) -> str | None:
    """A KiCad netlist (`kicad-cli sch export netlist`) as the lines a design call
    can use: each part's designator, library symbol and value, and each net's name
    with its `REF.pin(function)` nodes. None when the netlist holds no part."""
    tree = _sexpr(text)
    def section(name: str) -> list:
        return next((n for n in tree[1:] if isinstance(n, list) and n[:1] == [name]), [])
    def field(node: list, name: str) -> list:
        return next((n for n in node[1:] if isinstance(n, list) and n[:1] == [name]), [])
    def value(node: list, name: str) -> str:
        f = field(node, name)
        return f[1] if len(f) > 1 and isinstance(f[1], str) else ""
    parts = []
    for comp in section("components")[1:]:
        if not isinstance(comp, list) or comp[:1] != ["comp"]:
            continue
        lib = field(comp, "libsource")
        symbol = f"{value(lib, 'lib')}:{value(lib, 'part')}" if lib else "?"
        parts.append(f"  {value(comp, 'ref')}  {symbol}  {value(comp, 'value')}")
    if not parts:
        return None
    nets = []
    for net in section("nets")[1:]:
        if not isinstance(net, list) or net[:1] != ["net"]:
            continue
        nodes = []
        for node in net[1:]:
            if isinstance(node, list) and node[:1] == ["node"]:
                fn = value(node, "pinfunction")
                nodes.append(f"{value(node, 'ref')}.{value(node, 'pin')}"
                             + (f"({fn})" if fn else ""))
        nets.append(f"  {value(net, 'name')}: {' '.join(nodes)}")
    return "\n".join([f"Existing parts ({len(parts)}):", *parts,
                      f"Existing nets ({len(nets)}):", *nets])


def _load_intent(path: Path) -> dict | None:
    """`intent.json` as {"parts": [...], "nets": [...]}, or None when it is missing or
    not that shape."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("parts"), list) \
            or not isinstance(obj.get("nets"), list):
        return None
    return obj


def _load_artifact(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _briefing_and_plan(message: str) -> str:
    """The briefing and the [PLAN] for the log, capped so one long turn cannot flood
    its own section. A thread that starts cold loses anything not written here."""
    message = (message or "").strip()
    m = re.search(r"\[PLAN\]\s*(.+)", message, re.DOTALL)
    if not m:
        return message[-400:]
    briefing = message[:m.start()].strip()[:600]
    plan = m.group(1).strip()[:400]
    return "\n".join(p for p in (briefing, plan) if p)
