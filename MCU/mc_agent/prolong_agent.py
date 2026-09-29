"""PRO-LONG's programmatic memory, as a MineExplorer agent mode.

The point of this file is what it does *not* do. It is a drop-in for `DefaultAgent`,
so the episode loop, the loading steps, the frame buffer, `MilestoneChecker.check`,
`RenderWrapper`'s episode.mp4 and result.json all stay exactly as the baseline runs
them. The only difference between the two arms is where the agent's memory lives:

    DefaultAgent   20-frame deque re-sent every step + a `memory_update` string
    ProlongAgent   one append-only logs.txt the agent greps, plus a persistent
                   workspace, plus a plan queue so one analysis covers many steps

A plan-based harness fits the per-step interface through the queue: `get_action`
returns the next queued action and only fires a Codex turn when the queue runs dry,
which is how PRO-LONG's own ActionQueue behaves.

The queue, the retry loop and the memory hooks are `mfm.agent.base.MemoryAgent`
(shared with the KiCad arm). This file is what is Minecraft: the driver interface
`eval_benchmark` calls, the section rendering, the plan parser, the verification flush,
the goal-review layer, and the audit `save_state` writes. `tests/` in the MFM repo pins
its `logs.txt`, prompts, attachments and returned actions against the pre-refactor code.
"""
from __future__ import annotations

import io
import json
import time
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from PIL import Image

from mc_agent.action_space import BaseActionSpace
from mc_agent.llm_provider import BaseLLMProvider
from mfm.agent.base import MemoryAgent, Observation, Plan
from mfm.memory.store import EpisodeStore
from prolong_mc import prompts
from prolong_mc.mfm_prompts import MFM_MEMORY_NOTE
from prolong_mc.actions import describe_entry, parse_actions
from prolong_mc.codex_backend import CodexTurn
from prolong_mc.goals import GoalTracker
from prolong_mc.log import (
    _hotbar_slots, _inventory_counts, _num, _xz, action_section, initial_section, make_log,
    prepare_workspace, state_line,
)

RETRY_NUDGE = (
    "Your previous response did not produce a valid ./actions.json. Write one with "
    'the shape {"actions": [{"action": {...}, "repeat": N}]}.'
)


class ProlongAgent(MemoryAgent):
    """Same constructor shape as DefaultAgent so eval_benchmark can swap it in."""

    arm = "prolong"
    # MCU keeps its fixed loop: `analyzer_retries` attempts, the nudge after a failure,
    # no budget extension, a default action at the end.
    retry_policy = "fixed"
    retry_nudge = RETRY_NUDGE
    #: Patched out by tests; the wait between attempts after a contentless failure.
    retry_sleep = staticmethod(time.sleep)

    def before_retry(self, result: dict, attempt: int, budget: int) -> None:
        """The same escalating wait the world-model chassis puts between attempts.

        A failure with no message at all is the environment's (auth blip, capacity,
        the account's usage limit), not the model's, and retrying it hot burned five
        attempts in seconds per tick -- 1,551 of dg_pl's 2,394 calls. The wait is
        skipped for a call the backend's usage-limit gate did not make (`skipped`):
        those cost nothing and the gate's own probe cadence is the retry schedule.
        The prompts, the log and the actions returned are the same either way."""
        if result.get("ok") or result.get("message") or result.get("skipped"):
            return
        self.retry_sleep(min(30, 2 ** (attempt + 1)))

    def __init__(
        self,
        action_space: BaseActionSpace,
        provider: BaseLLMProvider,
        context_builder_class: type | None = None,
        model: str | None = None,
        *,
        workspace: str | Path,
        transcript_dir: str | Path | None = None,
        reasoning_effort: str = "low",
        base_url: str | None = None,
        codex_home: str | Path | None = None,
        action_cap: int = 15,
        repeat_cap: int = 20,
        step_cap: int = 40,
        log_window: int | None = None,
        stateless: bool = False,
        analyzer_retries: int = 5,
        milestone_hint: bool = False,
        goal_budget_steps: int = 0,
        episodes: bool = False,
        # The Codex channel's lifecycle knobs, passed through explicitly by the purple
        # agent. None leaves the backend's environment fallback in force (0 turns =
        # never drop the session; 1800 s), which is what a launcher that forgot to set
        # CODEX_SESSION_MAX_TURNS got: sessions resumed forever and turns 12-18+ ran
        # 600 s each.
        session_max_turns: int | None = None,
        timeout: int | None = None,
    ) -> None:
        self.action_space = action_space
        self.provider = provider          # unused: Codex is the model channel here
        self.model = model
        self.task_desc = ""
        self.platform_prompt = ""
        self.action_cap = action_cap
        self.repeat_cap = repeat_cap
        self.step_cap = step_cap
        self.milestone_hint = milestone_hint
        # The layer above the plan. Off by default and off in the ported arm: with it
        # off this file is the byte-for-byte mechanism the comparison was run on, and
        # `goals` is not constructed at all. See prolong_mc/goals.py for why it exists.
        self.goals = GoalTracker(goal_budget_steps) if goal_budget_steps else None
        self._esc_rejected_at: list[int] = []

        # Absolute, always -- the same rule CodexTurn applies to the workspace it is
        # handed. Under an ablation the canonical record moves out of the directory
        # Codex is given (`<workspace>_record`) and `EpisodeLog.publish` decides each
        # turn how much of the record crosses back in. A workspace left by a crashed
        # attempt is moved aside, not appended to. Both in `prepare_workspace`.
        visible, record = prepare_workspace(
            Path(workspace), ablated=log_window is not None or stateless)
        log = make_log(record, stateless=stateless)
        codex = CodexTurn(
            visible,
            model=model or "gpt-5.6-sol",
            reasoning_effort=reasoning_effort,
            base_url=base_url,
            codex_home=Path(codex_home) if codex_home else None,
            transcript_dir=Path(transcript_dir) if transcript_dir else None,
            **({"session_max_turns": int(session_max_turns)}
               if session_max_turns is not None else {}),
            **({"timeout": int(timeout)} if timeout is not None else {}),
        )
        # The MFM arm: the same history a second time, structured, one directory per
        # plan entry, plus one paragraph in AGENTS.md telling the model it is there.
        self.store = EpisodeStore(record) if episodes else None
        self.mfm_memory_note = MFM_MEMORY_NOTE if episodes else None
        super().__init__(visible=visible, record_dir=record, log=log, codex=codex,
                         analyzer_retries=analyzer_retries, log_window=log_window,
                         stateless=stateless, sinks=[self.store] if self.store else ())
        self._action_num = 0
        self._tick_prev_pos: dict | None = None
        self._prev_pos: dict | None = None
        self._pos_before: dict | None = None
        self._last_pos: dict | None = None
        self._last_info: dict | None = None
        self._verified: str | None = None
        self._last_milestone_hint = ""
        self._last_desc = ""
        self._last_step = 0
        self._last_plan_step: tuple[int, int] | None = None
        self._esc_rejections = 0
        self._current_frame: str | None = None
        self._review_pending = False
        logger.info(
            f"ProlongAgent  workspace={self.workspace}  model={model}  "
            f"log_window={log_window}  stateless={stateless}"
        )

    # -- DefaultAgent-compatible surface ---------------------------------

    def load_system_prompt(self, task_desc: str, platform_prompt: str = "") -> None:
        self.task_desc = task_desc
        self.platform_prompt = platform_prompt
        if self.goals is not None:
            # The review turn restates the task, because restating it is the thing the
            # agent stopped doing.
            self.goals.task_text = task_desc
        self.codex.write_system_prompt(self.full_system_prompt())

    def system_prompt(self) -> str:
        return prompts.build_system_prompt(
            task_text=self.task_desc,
            platform_prompt=self.platform_prompt,
            action_cap=self.action_cap,
            step_cap=self.step_cap,
            repeat_cap=self.repeat_cap,
            log_window=self.log_window,
            stateless=self.stateless,
            milestone_hint=self.milestone_hint,
        )

    def get_default_action(self, is_call_failed: bool = True) -> tuple[str, dict]:
        # A wire dict, not an ActionState: the caller feeds this straight to
        # env.step() and to checker.augment_action_with_queries().
        if is_call_failed:
            logger.warning("[prolong] falling back to a no-op action")
        return "", self.action_space.dump_action_to_dict(
            self.action_space.load_default_action()
        )

    def _milestone_note(self, hint: str) -> str:
        hint = (hint or "").strip()
        if not hint or hint == self._last_milestone_hint:
            return ""
        self._last_milestone_hint = hint
        return f"[MILESTONE] {hint}"

    def on_esc_rejected(self, step: int) -> None:
        # Collected, not written here: under the hint protocol a model that believes
        # it is finished presses ESC on every remaining step, and one log line per
        # rejection would bury the trace it is supposed to annotate. One line per
        # action section, carrying the count, says the same thing.
        self._esc_rejected_at.append(step)
        self._esc_rejections += 1

    def save_state(self, output_dir) -> None:
        """The workspace *is* the state; record what the agent built in it. The
        episode is over: the open episode in every sink is closed first."""
        self.finish()
        self.write_audit(output_dir)

    def write_audit(self, output_dir) -> None:
        """The audit as it stands, without ending the episode -- flushed periodically
        by the purple agent, because MCU episodes end on step count with no final call
        into the agent, and a run stopped by a deadline must still leave one."""
        kept = sorted(p.name for p in self.workspace.glob("*") if p.is_file())
        out = Path(output_dir)
        (out / "prolong_workspace_files.txt").write_text(
            "\n".join(kept), encoding="utf-8"
        )
        # How much vision this episode actually got, next to its score. Without it a
        # comparison cannot tell a memory effect from a "one arm was blind" effect.
        (out / "prolong_vision_audit.json").write_text(
            json.dumps(
                {
                    "analyzer_turns": self.codex.calls,
                    # From the rollout, not the event stream: codex 0.147 hides the
                    # model's nested tool calls from `--json`. `image_attach_failures`
                    # must be 0.
                    **self.codex.vision_audit(),
                    "overflow_resets": self.codex.overflow_resets,
                    # Cold starts from the other unclean endings and from the hosted
                    # session-age cap; nonzero age_resets means CODEX_SESSION_MAX_TURNS
                    # was in force and names the protocol variant.
                    "timeout_resets": self.codex.timeout_resets,
                    "empty_resets": self.codex.empty_resets,
                    "age_resets": self.codex.age_resets,
                    "session_max_turns": self.codex.session_max_turns,
                    # Expected 0. Nonzero means codex compacted the conversation, which
                    # is a different memory architecture than the one being measured.
                    "compactions": self.codex.compactions,
                    "actions_logged": self._action_num,
                    "esc_rejections": self._esc_rejections,
                    # Plans cut short because the verification state changed (R2).
                    "plan_flushes": self.plan_flushes,
                    # Which arm this is, and -- for the ablations -- what the last
                    # turn's enforcement actually did. `frames_visible` below the
                    # frame count above is the evidence for the window arm, and a
                    # nonzero `files_removed` is it for stateless.
                    "log_window": self.log_window,
                    "stateless": self.stateless,
                    "ablation_enforced": bool((self._published or {}).get("published")),
                    "frames_visible": (self._published or {}).get("frames_visible"),
                    "files_removed": self.files_removed,
                    # Absent in the ported arm.
                    **(self.goals.audit() if self.goals is not None else {}),
                    # Absent in the ported arm: the MFM store's counts, and how often
                    # the model reached for its tool.
                    **({"mfm": self.store.audit(self)} if self.store is not None else {}),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def get_action(
        self,
        frame_buffer: list[np.ndarray],
        thought_history: list,
        action_history: list,
        current_step: int | None = None,
        return_messages: bool = False,
        return_messages_with_pic: bool = False,
        long_term_memory: str = "",
        milestone_hint: str = "",
        camera_hint: str = "",
        movement_hint: str = "",
        info: dict | None = None,
    ) -> tuple[Any, ...]:
        step = current_step or 0
        pos = (info or {}).get("player_pos")
        self._last_pos = pos
        self._last_info = info
        if self.goals is not None:
            # Before the section is written and before the refill asks whether a review
            # is due, so both see this tick.
            self.goals.observe_step(step, info)

        # The newest frame is the observation this decision is made from.
        frame_name = None
        if frame_buffer:
            frame_name = self.log.save_attachment(
                f"frames/step_{step:04d}.png", _png(frame_buffer[-1]))
        self._current_frame = frame_name

        obs = Observation(step=step, attachment=frame_name, state={"pos": pos},
                          raw={"info": info, "milestone_hint": milestone_hint})
        item = self.step(obs)
        if item is None:
            # Three values, not two: eval_benchmark unpacks a triple, and returning a
            # pair here turns a recoverable analyzer failure into a ValueError that
            # kills the episode instead of hitting its retry path.
            return "", None, ""
        # (thought, wire action dict, memory_update) -- the same triple DefaultAgent
        # returns. PRO-LONG has no memory_update: the log is the memory.
        return item["think"], item["payload"], ""

    # -- the mechanism, as MemoryAgent hooks ------------------------------

    def flush_reason(self, obs: Observation) -> str | None:
        # Upstream's `Score:` and its queue flush (`action_queue.py:55-62`,
        # `runner.py:113-114`): when the environment's verification state changes the
        # rest of the plan is discarded and the analyzer is called again at once.
        # Without the flush a 40-tick program kept running after the environment had
        # verified the task (c4h-0306: verified at step 52, plan drain to step 300).
        verified = _verified_state(obs.raw["milestone_hint"])
        reason = None
        if verified != self._verified and self._verified is not None and self.queue:
            reason = f"verification state {self._verified!r} -> {verified!r}"
        self._verified = verified
        return reason

    def initial_section(self, obs: Observation) -> tuple[str, list[str]]:
        pos = obs.state["pos"]
        title, lines = initial_section(self.task_desc, pos, obs.attachment,
                                       info=obs.raw["info"])
        self._prev_pos = pos
        return title, lines

    def section(self, prev_item: dict[str, Any] | None,
                obs: Observation) -> tuple[str, list[str], str | None] | None:
        if prev_item is None:
            return None
        pos = obs.state["pos"]
        if self._esc_rejected_at:
            steps = self._esc_rejected_at
            where = f"step {steps[0]}" if len(steps) == 1 else f"steps {steps[0]}-{steps[-1]}"
            self.note(
                f"ESC was rejected at {where} ({len(steps)}x): the environment has "
                f"not verified the task as complete. Keep working."
            )
            self._esc_rejected_at = []
        title, lines = action_section(
            action_num=self._action_num,
            step=self._last_step,
            entry_desc=self._last_desc,
            pos=pos,
            prev_pos=self._prev_pos,
            frame_name=obs.attachment,
            # Only on change. An append-only log would otherwise accumulate 150 copies
            # of the same sentence; the transition -- the whole signal -- is still
            # recorded the step it happens.
            milestone_note=self._milestone_note(obs.raw["milestone_hint"]),
            plan_step=self._last_plan_step,
            verified=self._verified,
            info=obs.raw["info"],
            subgoal=self.goals.current if self.goals is not None else "",
        )
        self._pos_before = self._prev_pos
        self._prev_pos = pos
        return title, lines, f"Action {self._action_num}"

    def _state_text(self) -> str:
        """The current state as the No-Log turn prompt shows it (upstream's
        `INPROMPT_RESUME_PROMPT`: score, action count, last actions, board)."""
        lines = [state_line(self._last_pos, self._pos_before)]
        if self._verified is not None:
            lines.append(f"Verified: {self._verified}")
        lines.append(f"Actions so far: {self._action_num}")
        if self._last_desc:
            lines.append(f"Last action: {self._last_desc}")
        return "\n".join(lines)

    def turn_prompt(self, obs: Observation) -> str:
        # The file is always ./logs.txt, as upstream's sandbox copy is: naming the
        # windowed one differently advertised that a fuller log exists somewhere.
        base = prompts.build_turn_prompt(
            "logs.txt", self._action_num == 0, self.log_window, bool(obs.attachment),
            # The No-Log control carries the current state in the prompt, as upstream's
            # in-prompt mode carries the current board.
            state_text=self._state_text() if self.log_window == -1 else "",
        )
        # A due review is prepended to the turn prompt, not buried in the log: the log
        # is where the agent's own hundred agreeing plans live, and a question asked
        # there is answered by them. It is *also* written into the log, so the record
        # shows the interruption where a later reader lands on it.
        self._review_pending = False
        if self.goals is not None and self.goals.review_due:
            review = self.goals.review_prompt()
            self.log.add_note(self.goals.review_note())
            logger.info(f"[prolong] step {obs.step}: subgoal review due ({self.goals.current!r})")
            base = review + base
            self._review_pending = True
        return base

    def parse_plan(self, result: dict[str, Any]) -> Plan | None:
        plan = parse_actions(
            result["actions_json"],
            action_cap=self.action_cap,
            repeat_cap=self.repeat_cap,
            step_cap=self.step_cap,
        )
        if not plan:
            logger.warning("[prolong] no usable entries")
            return None
        briefing, think = CodexTurn.split_briefing(result["message"])
        return Plan(entries=plan.entries, ticks=[e["repeat"] for e in plan.entries],
                    steps=plan.steps, think=think, briefing=briefing, extra=plan)

    def accept_plan(self, plan: Plan, attempt: int, budget: int) -> str | None:
        if self.goals is None:
            return None
        parsed = plan.extra
        reason = self.goals.reject_reason(parsed.subgoal, parsed.recommit)
        if reason and attempt < budget:
            # The plan is valid; it just does not answer the question. Rejecting it is
            # the whole mechanism -- a review the agent may decline is the `[NOTE]`
            # channel it already had.
            logger.warning(f"[prolong] attempt {attempt}: subgoal review unanswered, "
                           f"rejecting the plan")
            self.goals.note_rejection()
            # The full reason goes to the model as the nudge; the log gets one short
            # line, since it is re-read in full every turn.
            self.log.add_note(
                f"REVIEW: attempt {attempt} rejected -- the plan did not "
                f"answer the subgoal review."
            )
            return reason
        if reason:
            # Never at the cost of the episode: a stuck review would return no actions
            # at all, which is worse than a badly answered one.
            logger.error("[prolong] subgoal review still unanswered after "
                         f"{self.analyzer_retries} attempts; accepting the plan")
            self.log.add_note(
                "REVIEW: not answered after "
                f"{self.analyzer_retries} attempts; the plan was accepted anyway."
            )
        elif self._review_pending:
            self.log.add_note(
                f"REVIEW: answered. subgoal is now {parsed.subgoal!r}"
                + (f"; recommitted because: {parsed.recommit}" if parsed.recommit else "")
            )
        self.goals.adopt(parsed.subgoal, parsed.recommit, self._obs.step, self._last_info)
        return None

    def adopt_plan(self, plan: Plan, result: dict[str, Any]) -> None:
        self.log.set_plan(plan.think, briefing=plan.briefing)
        logger.info(
            f"[prolong] step {self._obs.step}: queued {len(plan.entries)} entries "
            f"= {len(plan.steps)} steps (turn {self.codex.calls})"
        )

    def after_pop(self, item: dict[str, Any]) -> None:
        # Name the tick within its plan entry. Without this every drained tick logs
        # the whole entry ("... x10"), which reads as if ten times the movement was
        # issued each step -- misleading to the agent that reads this log back.
        self._last_desc = f'{describe_entry(item["entry"])} [tick {item["tick"]}/{item["entry"]["repeat"]}]'
        self._last_step = self._obs.step
        self._last_plan_step = (item["index"], item["total"])
        self._action_num += 1

    def on_no_plan(self, result: dict[str, Any]) -> None:
        logger.error(f"[prolong] analyzer produced nothing after {self.analyzer_retries} tries")

    # -- what the episode store records (the MFM arm) ---------------------------------

    def episode_state(self, obs: Observation) -> dict[str, Any]:
        info = obs.raw["info"] or {}
        pos = obs.state["pos"]
        here, before = _xz(pos), _xz(self._tick_prev_pos)
        moved = math.dist(here, before) if here and before else 0.0
        self._tick_prev_pos = pos
        stats = info.get("location_stats") or {}
        vitals: dict[str, Any] = {}
        for label, key, src in (("health", "health", info), ("food", "food_level", info),
                                ("light", "light_level", stats)):
            v = _num(src.get(key))
            if v is not None:
                vitals[label] = v
        if stats.get("can_see_sky") is not None:
            vitals["sky"] = str(stats["can_see_sky"]).lower() == "true"
        mobs = info.get("mobs")
        mob_counts = None
        if isinstance(mobs, list):
            mob_counts = dict(Counter(
                str((m.get("name") or m.get("type") or "?") if isinstance(m, dict) else m)
                for m in mobs))
        spec = info.get("milestone_spec")
        goals = None
        if isinstance(spec, list) and spec:
            todo = [m for m in spec if not m.get("done")]
            goals = {"done": [m["identity"] for m in spec if m.get("done")],
                     "next": todo[0]["identity"] if todo else None}
        return {
            "step": obs.step, "pos": pos, "moved": round(moved, 3),
            "inventory": _inventory_counts(info), "hotbar": _hotbar_slots(info),
            "gui_open": bool(info["isGuiOpen"]) if info.get("isGuiOpen") is not None else None,
            "mainhand": ((info.get("equipped_items") or {}).get("mainhand") or {}).get("type"),
            "vitals": vitals, "mobs": mob_counts, "goals": goals, "verified": self._verified,
        }

    def episode_action_kind(self, item: dict[str, Any]) -> str | None:
        act = item["entry"].get("action") or {}
        keys = [k for k, v in act.items() if v not in (0, [0, 0], [0.0, 0.0])]
        return "+".join(keys) or "noop"

    def episode_outcome(self, entry: Any, first: dict[str, Any], last: dict[str, Any],
                        notes: list[str], flushed: bool) -> tuple[dict[str, Any], list[str], str]:
        here, before = _xz(last.get("pos")), _xz(first.get("pos"))
        moved = math.dist(here, before) if here and before else 0.0
        y0 = _num((first.get("pos") or {}).get("y"))
        y1 = _num((last.get("pos") or {}).get("y"))
        descended = (y0 - y1) if y0 is not None and y1 is not None else 0.0
        inv0, inv1 = first.get("inventory") or {}, last.get("inventory") or {}
        delta = {k: inv1.get(k, 0) - inv0.get(k, 0) for k in sorted(set(inv0) | set(inv1))
                 if inv1.get(k, 0) != inv0.get(k, 0)}
        done0 = set((first.get("goals") or {}).get("done") or [])
        done1 = set((last.get("goals") or {}).get("done") or [])
        transition = sorted(done1 - done0) or None
        act = (entry or {}).get("action") or {}
        movement = bool({"forward", "back", "left", "right", "jump", "sprint"} & set(act))
        tags = []
        if transition:
            tags.append("milestone")
        if delta:
            tags.append("inventory_changed")
        if movement and moved < 0.5:
            tags.append("stuck")
        if last.get("gui_open"):
            tags.append("gui")
        h0, h1 = (first.get("vitals") or {}).get("health"), (last.get("vitals") or {}).get("health")
        if h0 is not None and h1 is not None and h1 < h0:
            tags.append("damage")
        summary = f"{describe_entry(entry)}: moved {moved:.1f}"
        if delta:
            summary += f", inv {delta}"
        if transition:
            summary += f", milestone {transition}"
        return ({"moved": round(moved, 2), "descended": round(descended, 2),
                 "inventory_delta": delta, "milestone_transition": transition,
                 "verified_after": last.get("verified")}, tags, summary)

    def episode_index_fields(self, first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
        pos = first.get("pos") or {}
        return {"x": pos.get("x"), "z": pos.get("z"), "gui_open": first.get("gui_open")}


def _verified_state(milestone_hint: str) -> str | None:
    """The environment's verification bit as the header prints it: "yes", "no", or
    None under the no-hint protocol (no line rendered, nothing to print)."""
    text = (milestone_hint or "").strip()
    if not text:
        return None
    return "yes" if "HAS verified" in text else "no"


def _png(frame: np.ndarray) -> bytes:
    # Native resolution for the MCU port. Upstream halves anything wider than 256 px so
    # this arm's one frame carries the same pixels as one of the direct agents' twenty.
    # On MCU the comparison partner attaches a single 640x360 frame and says why: an
    # inventory GUI is a thing the agent is meant to *read*, and an 18 px slot does not
    # survive being halved to 9 px.
    buf = io.BytesIO()
    img = Image.fromarray(np.asarray(frame).astype(np.uint8), "RGB")
    img.save(buf, format="PNG")
    return buf.getvalue()
