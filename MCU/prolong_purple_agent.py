"""PRO-LONG as an MCU purple agent.

Wraps MineExplorer's `ProlongAgent` -- an append-only `logs.txt` the model greps, a
persistent Codex workspace, and a plan queue so one analysis covers many steps -- in the
A2A protocol the MCU green agent speaks. The agent's decision logic is untouched and its
module is vendored byte-identical; everything here is the adapter between two interfaces:

    MCU `init` ->  a fresh episode: new workspace, new ProlongAgent, system prompt written
    MCU `obs`  ->  ProlongAgent.get_action(frame, info) -> one env-format action

Three seams needed adapting, and each one is marked below:

  * MCU sends the observation as a JPEG plus the human-parity `info` slice (pose,
    inventory, cumulative statistics). ProlongAgent reads exactly `info["player_pos"]`,
    so it is forwarded unchanged; the milestone bits the wire used to carry are now
    derived here -- a ledger applies the public task config's rules to the statistics --
    and become the verification sentence `_verified_state` keys on.
  * A Codex turn takes far longer than a frame, so `get_action` runs in a worker thread
    and the evaluation is run with a raised `step_timeout`.
  * MineStudio has no ESC button, so an ESC request cannot end an MCU episode. It is
    reported back through `on_esc_rejected`, which is what that hook is for.
"""
import argparse
import base64
import json
import os
from collections import deque
from pathlib import Path

import asyncio
import cv2
import numpy as np
import uvicorn
from loguru import logger

from dotenv import load_dotenv

load_dotenv()

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from mc_agent.action_space import MinerRLActionSpace
from mc_agent.prolong_agent import ProlongAgent
from camera_contract import with_camera_truth
from models import AckPayload, ActionPayload
# Adapter-level, not agent-level: the vendored PRO-LONG module stays byte-identical.
# The green agent no longer publishes milestone bits or the scoring spec, so this
# adapter derives both from the repo's public task config + the human-parity statistics
# (the same rules the scorer applies) and injects them in the wire shapes the agent's
# log already renders -- keeping every arm's milestone knowledge identical.
from mcu_worldmodel.milestones import MilestoneLedger
from task_milestones import (load_milestone_cfg, load_reveal_mode,
                             synthesize_milestone_info)

# Verbatim from MineExplorer's eval_benchmark.py. The exact wording matters:
# `prolong_agent._verified_state` decides the header's verification bit by looking for
# "HAS verified", and a paraphrase would silently read as "not verified" forever.
MILESTONE_VERIFIED = (
    "The environment HAS verified the task as complete. "
    "You may now end the episode by setting ESC=1."
)
MILESTONE_PENDING = (
    "The environment has NOT verified the task as complete yet. "
    "Do not end the episode (ESC) until it is."
)


def prepare_agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Solves MCU benchmark tasks with PRO-LONG's programmatic memory",
        tags=["benchmark", "mcu", "prolong"],
        examples=[],
    )
    return AgentCard(
        name="prolong_agent",
        description="PRO-LONG Minecraft agent for MCU benchmark evaluation",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )


class ProlongExecutor(AgentExecutor):
    """One episode at a time, the way the green agent drives a purple agent."""

    def __init__(
        self,
        workspace_root: Path,
        model: str,
        codex_home: Path | None,
        reasoning_effort: str = "low",
        base_url: str | None = None,
        action_cap: int = 15,
        repeat_cap: int = 20,
        step_cap: int = 40,
        analyzer_retries: int = 5,
        task: str = "mine_diamond_from_scratch",
        goal_budget_steps: int = 0,
        mfm: bool = False,
        session_max_turns: int = 1,
        session_max_bytes: int = 0,
        codex_timeout: int = 480,
        max_steps: int = 12000,
        report_every: int = 200,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.codex_home = Path(codex_home).resolve() if codex_home else None
        self.reasoning_effort = reasoning_effort
        self.base_url = base_url
        self.action_cap = action_cap
        self.repeat_cap = repeat_cap
        self.step_cap = step_cap
        self.analyzer_retries = analyzer_retries
        self.task = task
        self.milestone_cfg = load_milestone_cfg(task)
        self._ledger: MilestoneLedger | None = None
        self.goal_budget_steps = goal_budget_steps
        self.session_max_turns = session_max_turns
        self.session_max_bytes = session_max_bytes
        self.codex_timeout = codex_timeout
        # The episode's step budget and the audit cadence. There is no end-of-episode
        # message in this protocol, so the audit is written every `report_every` steps
        # and the episode is closed (the last open episode in the store, the final
        # audit) on the observation for the last step. Before this the audit was
        # written only from `save_state`, which nothing called: no run of this arm
        # left a `prolong_vision_audit.json`, and its last episode never closed.
        self.max_steps = int(max_steps)
        self.report_every = int(report_every)
        self._workspace: Path | None = None
        # The MFM arm: PRO-LONG plus the episode store and its query tool.
        self.mfm = mfm

        self.action_space = MinerRLActionSpace()
        self._agent: ProlongAgent | None = None
        # One observation at a time. `asyncio.to_thread` cannot be cancelled, so a
        # green-side step timeout leaves the worker thread running inside Codex; without
        # this the next observation would start a second `execute()` over the same
        # episode state (`_step`, the plan queue, the agent's log).
        self._lock = asyncio.Lock()
        self._episode = 0
        self._step = 0
        # ProlongAgent reads only the newest frame -- it keeps its history in logs.txt
        # and frames/, not in a resent buffer -- so one slot is the whole buffer.
        self._frames: deque = deque(maxlen=1)
        # Which milestones the ledger has verified from the statistics. Only used to log
        # the transitions: MilestoneTrackerCallback writes its JSON at `before_close`, so
        # a long episode that is killed leaves no record of how far it got.
        self._done: set = set()

    # -- episode lifecycle ------------------------------------------------

    def _start_episode(self, task_text: str, platform_prompt: str = "") -> Path:
        if self._agent is not None:
            # MCU episodes end on step count with no final call into the agent, so the
            # previous episode's memory is closed here, on the next init.
            self._agent.finish()
        self._episode += 1
        self._step = 0
        self._frames.clear()
        self._done.clear()
        # Fresh per episode; armed (baselined) on the first observation. Empty cfg means
        # a task with no milestone list, which is the pre-existing no-hint protocol.
        self._ledger = (MilestoneLedger(self.milestone_cfg, task_name=self.task,
                                        reveal=load_reveal_mode(self.task))
                        if self.milestone_cfg else None)
        self._ledger_armed = False
        workspace = self.workspace_root / f"episode_{self._episode:03d}"
        agent = ProlongAgent(
            action_space=self.action_space,
            provider=None,  # unused: Codex is the model channel
            model=self.model,
            workspace=workspace,
            transcript_dir=workspace / "transcripts",
            reasoning_effort=self.reasoning_effort,
            base_url=self.base_url,
            codex_home=self.codex_home,
            action_cap=self.action_cap,
            repeat_cap=self.repeat_cap,
            step_cap=self.step_cap,
            analyzer_retries=self.analyzer_retries,
            # MCU reports per-milestone completion bits, so the verification line is
            # available and the system prompt should document the marker.
            milestone_hint=True,
            goal_budget_steps=self.goal_budget_steps,
            episodes=self.mfm,
            session_max_turns=self.session_max_turns,
            session_max_bytes=self.session_max_bytes,
            timeout=self.codex_timeout,
        )
        agent.load_system_prompt(task_text, platform_prompt)
        self._agent = agent
        self._workspace = workspace
        logger.info(f"[adapter] episode {self._episode} workspace={workspace} platform_prompt={len(platform_prompt)} chars")
        return workspace

    # -- A2A surface ------------------------------------------------------

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        ctx_id = context.context_id
        try:
            payload = json.loads(context.get_user_input())
        except Exception as exc:
            await self._send(event_queue, ctx_id, AckPayload(success=False, message=f"bad JSON: {exc}"))
            return

        kind = payload.get("type")
        if kind == "init":
            async with self._lock:
                await self._handle_init(payload, event_queue, ctx_id)
        elif kind == "obs":
            async with self._lock:
                await self._handle_obs(payload, event_queue, ctx_id)
        else:
            await self._send(event_queue, ctx_id, AckPayload(success=False, message=f"unknown type: {kind}"))

    async def _handle_init(self, payload: dict, event_queue: EventQueue, ctx_id: str) -> None:
        task_text = payload.get("text", "")
        # `prompt` is the host benchmark's own control reference, sent to every purple
        # agent (`src/prompt.txt` via `InitPayload.prompt`). This adapter used to drop it,
        # which left the arm documented by upstream MineExplorer's action reference rather
        # than by the environment it is actually being scored in.
        platform_prompt = payload.get("prompt", "") or ""
        # The host's camera section describes a continuous angle the encoder cannot
        # deliver (see camera_contract). Both arms get the same correction, because
        # the alternative is measuring how each copes with wrong documentation.
        platform_prompt = with_camera_truth(platform_prompt)
        try:
            # Codex writes AGENTS.md here, so it touches the filesystem; off the loop.
            workspace = await asyncio.to_thread(
                self._start_episode, task_text, platform_prompt)
        except Exception as exc:
            logger.exception("[adapter] episode start failed")
            await self._send(event_queue, ctx_id, AckPayload(success=False, message=str(exc)))
            return
        await self._send(
            event_queue, ctx_id,
            AckPayload(success=True, message=f"prolong episode {self._episode} at {workspace}"),
        )

    async def _handle_obs(self, payload: dict, event_queue: EventQueue, ctx_id: str) -> None:
        if self._agent is None:
            await self._send(event_queue, ctx_id, AckPayload(success=False, message="no episode; send init first"))
            return

        encoded = payload.get("obs")
        if not encoded:
            await self._send(event_queue, ctx_id, AckPayload(success=False, message="no observation provided"))
            return

        try:
            self._frames.append(self._decode_image(encoded))
        except Exception:
            # An exception escaping `execute` reaches the green agent as a failed task,
            # and its step loop only handles `asyncio.TimeoutError` -- so one corrupt
            # payload would end a 12,000-step episode instead of costing it one frame.
            # ProlongAgent reads the newest frame it has; reusing the previous one is a
            # stale view for a tick, which the next observation corrects.
            logger.exception("[adapter] frame decode failed; reusing the previous frame")

        info = dict(payload.get("info") or {})
        # Milestone knowledge is agent-side now: the ledger applies the public config's
        # rules to the human-parity statistics, and the result is injected in the wire
        # shapes the vendored agent's log already renders ([GOALS], [MILESTONES]). The
        # step passed is the green agent's own index, same fallback as `wire_step` below.
        if self._ledger is not None:
            wire_step = payload.get("step")
            step_no = int(wire_step) if isinstance(wire_step, int) else self._step + 1
            if not self._ledger_armed:
                self._ledger.reset(info)
                self._ledger_armed = True
            self._ledger.update(info, step_no)
            info.update(synthesize_milestone_info(self._ledger.cfg,
                                                  self._ledger.achieved,
                                                  self._ledger.revealed()))
        milestones = info.get("milestones") or {}
        if self._step == 0:
            # Says once per episode whether the green agent is sending the extended
            # observation. Without it a silently missing `info` looks the same as an
            # agent that simply never moved.
            logger.info(
                f"[adapter] episode {self._episode} first obs: info keys={sorted(info)} "
                f"pos={'yes' if info.get('player_pos') else 'no'} milestones={len(milestones)}"
            )
        done = {k for k, v in milestones.items() if int(v) == 1}
        if done != self._done:
            gained = sorted(done - self._done)
            logger.success(
                f"[adapter] step {self._step}: milestone(s) {gained} verified "
                f"({len(done)}/{len(milestones)})"
            )
            self._done = done
        verified = bool(milestones) and all(int(v) == 1 for v in milestones.values())
        # No milestones defined for this task -> no verification line at all, which is
        # the no-hint protocol `_verified_state` already handles by returning None.
        hint = ""
        if milestones:
            if verified:
                hint = MILESTONE_VERIFIED
            else:
                # Names which milestones have fired. `_milestone_note` only writes when
                # the hint changes, so the original constant sentence produced exactly one
                # [MILESTONE] line per episode: an agent that reached `mine_log` at step
                # 175 was never told it had. The ordered checklist itself lives in the log
                # (`[MILESTONES]` once, `[GOALS]` per section); this is the transition
                # marker. It must not contain the literal "HAS verified", which is what
                # `_verified_state` keys the header bit on.
                got = ", ".join(sorted(done)) if done else "none yet"
                hint = (f"{len(done)}/{len(milestones)} milestones verified so far "
                        f"({got}). {MILESTONE_PENDING}")

        # The green agent's own step index, not a local count: `Messenger` gives up on a
        # slow step and moves on, so a local counter drifts from the number the milestone
        # log, the frame files and the recording are indexed by -- and PRO-LONG's log is
        # meant to be read back against them. Falls back if the field is ever absent.
        wire_step = payload.get("step")
        self._step = int(wire_step) if isinstance(wire_step, int) else self._step + 1
        wire = None
        try:
            # A Codex turn on the step where the plan queue drains takes minutes, and it
            # is synchronous; keep the event loop free so the card endpoint still answers.
            _, wire, _ = await asyncio.to_thread(
                self._agent.get_action,
                list(self._frames),
                [],  # thought_history: ProlongAgent keeps its history in logs.txt
                [],  # action_history: idem
                self._step,
                milestone_hint=hint,
                info=info,
            )
        except Exception:
            logger.exception(f"[adapter] get_action failed at step {self._step}")

        try:
            if wire is None:
                # The analyzer produced nothing usable; ProlongAgent has already logged it.
                _, wire = self._agent.get_default_action()

            wire = dict(wire)
            if int(wire.get("ESC", 0)) == 1:
                # MineStudio has no ESC button and MCU episodes end on step count, not on
                # agent request. Tell the agent the episode is still running so it does not
                # spend the remaining steps pressing a key that does nothing.
                wire["ESC"] = 0
                if verified:
                    # `on_esc_rejected` writes "the environment has not verified the task",
                    # which would be false here. Nothing truthful is available to say
                    # through that hook, so this is logged rather than fed back.
                    logger.info(f"[adapter] step {self._step}: ESC after full verification; "
                                f"MCU episodes end on step count, so the run continues")
                else:
                    self._agent.on_esc_rejected(self._step)
            payload_out = ActionPayload(action_type="env", action=self._jsonable(wire))
        except Exception:
            logger.exception("[adapter] action failed validation; sending a no-op")
            # `ActionPayload` fills in every missing env key with 0, so a bare camera is a
            # complete no-op and cannot itself fail validation.
            payload_out = ActionPayload(action_type="env", action={"camera": [0.0, 0.0]})

        await self._send(event_queue, ctx_id, payload_out)
        self._flush_audit()

    def _flush_audit(self) -> None:
        """Periodic audit, and the episode's close on its last step (the green agent
        sends steps 0..max_steps-1 and no final message)."""
        if self._agent is None or self._workspace is None:
            return
        last = self._step >= self.max_steps - 1
        if not last and not (self.report_every and self._step
                             and self._step % self.report_every == 0):
            return
        try:
            if last:
                self._agent.save_state(self._workspace)
                logger.info(f"[adapter] step {self._step}: last step, episode closed "
                            f"and audit written to {self._workspace}")
            else:
                self._agent.write_audit(self._workspace)
            if self._ledger is not None:
                (self._workspace / "prolong_milestones.json").write_text(
                    json.dumps({"steps": self._step,
                                "milestones": self._ledger.summary()}, indent=2),
                    encoding="utf-8")
        except Exception as exc:  # never let bookkeeping kill an episode
            logger.warning(f"[adapter] audit flush failed at step {self._step}: {exc}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError

    # -- helpers ----------------------------------------------------------

    @staticmethod
    async def _send(event_queue: EventQueue, ctx_id: str, payload) -> None:
        await event_queue.enqueue_event(
            new_agent_text_message(payload.model_dump_json(), context_id=ctx_id)
        )

    @staticmethod
    def _jsonable(wire: dict) -> dict:
        """Plain JSON types. `camera` stays a 2-list; every button is an int."""
        out: dict = {}
        for key, value in wire.items():
            if key == "camera":
                out[key] = [float(value[0]), float(value[1])]
            else:
                out[key] = int(value)
        return out

    @staticmethod
    def _decode_image(encoded: str) -> np.ndarray:
        """Decode to an RGB array, which is what ProlongAgent's `_png` expects.

        The green agent encodes the simulator's RGB frame with `cv2.imencode`, which
        treats its input as BGR; decoding it back with `cv2.imdecode` applies the same
        swap a second time, so the array that comes out is the original RGB order.
        """
        buffer = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image decoding failed.")
        return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PRO-LONG purple agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9019)
    parser.add_argument("--card-url", type=str, help="External URL for the agent card")
    parser.add_argument("--workspace", type=str, default="output/prolong_workspaces",
                        help="Root for per-episode Codex workspaces")
    parser.add_argument("--model", type=str, default="gpt-5.6-sol")
    parser.add_argument("--codex-home", type=str, default=os.path.expanduser("~/.codex-eval"))
    parser.add_argument("--base-url", type=str, default=None,
                        help="OpenAI-compatible endpoint, for a locally served model")
    parser.add_argument("--reasoning-effort", type=str, default="medium",
                        help="Matched to mcu_worldmodel's runner default, so the "
                             "arms differ in memory mechanism and not in compute")
    # Matched to the worldmodel arm's CLI defaults (entries 40 / repeat 200 / step 400),
    # so the alignment holds by default instead of depending on launcher flags. The
    # vendored module's own 15/20/40 defaults are upstream MineExplorer's and stay.
    # 40 comes from the wm arms' trajectories (plans entry-clipped at 20 with tick
    # budget to spare); for this arm it is pure headroom -- its median plan is 2 entries.
    # The Codex channel's lifecycle, as explicit arguments rather than environment
    # defaults: the measured arms ran 1-turn sessions and a 480 s ceiling (below the
    # green agent's 600 s step_timeout, so a stalled turn returns a default action
    # instead of failing the step). A launcher that forgot CODEX_SESSION_MAX_TURNS got
    # the backend's 0 (never drop the session) and 1800 s, and its rounds 12-18+ took
    # 600 s each on a thread that resumed forever.
    parser.add_argument("--max-steps", type=int, default=12000,
                        help="the episode's step budget; the audit is finalised on the "
                             "last step (run-arm.sh passes its --steps)")
    parser.add_argument("--report-every", type=int, default=200,
                        help="write prolong_vision_audit.json every N steps")
    parser.add_argument("--session-turns", type=int, default=1,
                        help="drop the codex session after this many turns (0 = never)")
    # The persistent-session policy (run-arm.sh, 2026-09-09): --session-turns 0 with a
    # byte budget, so one thread carries across turns and hands off to a fresh one
    # only when the next frame would push its re-sent payload past the wall.
    parser.add_argument("--session-bytes", type=int, default=0,
                        help="cold-start the codex session before its attached frames "
                             "exceed this many base64 bytes on the wire (0 = no budget)")
    parser.add_argument("--codex-timeout", type=int, default=480,
                        help="seconds one codex turn may take")
    parser.add_argument("--action-cap", type=int, default=40)
    parser.add_argument("--repeat-cap", type=int, default=200)
    parser.add_argument("--step-cap", type=int, default=400)
    parser.add_argument("--task", type=str, default="mine_diamond_from_scratch",
                        help="task_category being evaluated; names the public task "
                             "config the milestone checklist is loaded from now that "
                             "the wire no longer carries the scoring spec")
    parser.add_argument(
        "--goal-budget-steps", type=int, default=0,
        help="Enable the subgoal-review layer (prolong_mc/goals.py) and force a "
             "re-derivation whenever one subgoal has cost this many environment steps, "
             "or 3x that many steps have passed with no milestone verified. 0 (the "
             "default) is the ported arm, with no layer above the plan.")
    parser.add_argument(
        "--mfm", action="store_true",
        help="The MFM arm: PRO-LONG plus the episode store (episodes/, index.jsonl, "
             "tools/episodes.py) and one paragraph in AGENTS.md naming it. Everything "
             "else -- prompts, caps, the log, the codex policy -- is the prolong arm's.")
    args = parser.parse_args()

    executor = ProlongExecutor(
        workspace_root=Path(args.workspace),
        model=args.model,
        codex_home=Path(args.codex_home) if args.codex_home else None,
        reasoning_effort=args.reasoning_effort,
        base_url=args.base_url,
        action_cap=args.action_cap,
        repeat_cap=args.repeat_cap,
        step_cap=args.step_cap,
        task=args.task,
        goal_budget_steps=args.goal_budget_steps,
        mfm=args.mfm,
        session_max_turns=args.session_turns,
        session_max_bytes=args.session_bytes,
        codex_timeout=args.codex_timeout,
        max_steps=args.max_steps,
        report_every=args.report_every,
    )

    card = prepare_agent_card(args.card_url or f"http://{args.host}:{args.port}/")
    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        ),
    )
    logger.info(f"PRO-LONG purple agent: model={args.model} codex_home={args.codex_home} "
                f"goal_budget_steps={args.goal_budget_steps or 'off (ported arm)'} "
                f"mfm={'on' if args.mfm else 'off'}")
    uvicorn.run(app.build(), host=args.host, port=args.port, timeout_keep_alive=600)


if __name__ == "__main__":
    main()
