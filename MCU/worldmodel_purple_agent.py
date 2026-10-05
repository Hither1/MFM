"""The memory arms as an MCU purple agent.

Wraps the chassis (`mcu_worldmodel.agent.WorldModelAgent`) in the A2A protocol the MCU
green agent speaks: it is handed `InitPayload.prompt` and one `ObservationPayload` per
step and answers each with an env action. `--memory` picks the arm
(`mcu_worldmodel/arms.py`): direct, logbook (PRO-LONG), vista or mfm. Everything else --
executor, perception, caps, the milestone ledger -- is the same for all four.

Three seams between the chassis and the wire, each marked below:

  * `WorldModelAgent` reads its frame from `info['pov']`, which does not survive the wire.
    MCU sends the frame as a base64 JPEG, so it is decoded and put back under that key.
  * The agent owns a `MilestoneLedger` built from the repo's public task config
    (`task_milestones.py`) -- the wire carries no milestone definitions or bits.
    Construction is deferred to the first `obs`, because `start()` wants a real
    info dict for the ledger baseline and the initial frame.
  * Over A2A each observation carries the state *after* the previous action, so the
    order per message is `observe(info)` then `next_action(info)`.
"""
import argparse
import asyncio
import base64
import json
import os
import shutil
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from loguru import logger

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from mcu_worldmodel.agent import WorldModelAgent
from mcu_worldmodel.arms import ARMS, MEMORY_MODE, SESSION_TURNS
from mcu_worldmodel.milestones import MilestoneLedger
from camera_contract import with_camera_truth
from models import AckPayload, ActionPayload
from task_milestones import load_given_milestones, load_milestone_cfg


def prepare_agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Solves MCU benchmark tasks with a filesystem memory",
        tags=["benchmark", "mcu", "memory"],
        examples=[],
    )
    return AgentCard(
        name="mfm_agent",
        description="Minecraft agent with filesystem memory for MCU benchmark evaluation",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )


class WorldModelExecutor(AgentExecutor):
    """One episode at a time, the way the green agent drives a purple agent."""

    def __init__(
        self,
        workspace_root: Path,
        model: str,
        codex_home: Path | None,
        cli: str = "codex",
        reasoning_effort: str = "medium",
        base_url: str | None = None,
        entry_cap: int = 40,
        repeat_cap: int = 200,
        step_cap: int = 400,
        report_every: int = 200,
        max_steps: int = 6000,
        memory_mode: str = "mfm",
        task: str = "mine_diamond_from_scratch",
        seed_memory: list[str] | None = None,
        seed_log: str | None = None,
        carried_world: str = "same",
        install_carried: bool = False,
        install_scripts: list[str] | None = None,
        grant: list[str] | None = None,
        withhold: list[str] | None = None,
        endgame_recipes: bool = False,
        start_dimension: str | None = None,
        own_live: bool = False,
        near_deaths: bool = False,
        session_max_turns: int = 1,
        codex_timeout: int = 480,
        vista_options: dict | None = None,
        frame_size: tuple[int, int] = (320, 180),
        hires_every: int = 1,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.frame_size = tuple(frame_size)
        # Every Nth observation's wire JPEG, kept whole for the record (0 = off).
        self.hires_every = max(0, int(hires_every))
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.codex_home = Path(codex_home).resolve() if codex_home else None
        self.cli = cli
        self.reasoning_effort = reasoning_effort
        self.base_url = base_url
        self.seed_memory = seed_memory
        self.seed_log = seed_log
        self.carried_world = carried_world
        self.install_carried = install_carried
        self.install_scripts = install_scripts
        self.grant, self.withhold = list(grant or []), list(withhold or [])
        self.endgame_recipes, self.start_dimension = bool(endgame_recipes), start_dimension
        self.own_live = bool(own_live)
        self.near_deaths = bool(near_deaths)
        self.session_max_turns = session_max_turns
        self.codex_timeout = codex_timeout
        self.vista_options = vista_options
        self.entry_cap = entry_cap
        self.repeat_cap = repeat_cap
        self.step_cap = step_cap
        self.report_every = report_every
        self.max_steps = max_steps
        # The arm (mcu_worldmodel/arms.py). Same chassis every way -- execution engine,
        # perception, caps -- so the mode is the memory and nothing else.
        if memory_mode not in ARMS:
            raise ValueError(f"unknown arm: {memory_mode!r}")
        self.arm = memory_mode
        self.memory_mode = MEMORY_MODE[memory_mode]
        # Which benchmark task this arm is being evaluated on. The milestone checklist
        # comes from the repo's public task config (task_milestones.py) now that the
        # wire no longer carries the scoring spec; the operator names the task the same
        # way they name it in the evaluation TOML.
        self.task = task
        self.milestone_cfg = load_milestone_cfg(task)

        self._agent: WorldModelAgent | None = None
        # One observation at a time. `asyncio.to_thread` cannot be cancelled, so a
        # green-side step timeout leaves the worker thread running inside Codex; without
        # this the next observation would start a second `execute()` over the same
        # episode state (`_step`, the plan queue, the agent's log).
        self._lock = asyncio.Lock()
        self._episode = 0
        self._step = 0
        self._task_text = ""
        self._platform_prompt = ""
        self._workspace: Path | None = None
        self._hires_dir: Path | None = None
        self._hires_failed = False

    # -- episode lifecycle ------------------------------------------------

    def _build_agent(self, info: dict) -> None:
        """Deferred to the first observation: `WorldModelAgent.start` wants a real info
        dict for the ledger baseline and the initial frame.

        The milestone definitions come from the repo's public task config, not the wire:
        the green agent no longer publishes `milestone_spec` (scoring config) or the live
        `milestones` bits (the scorer's private verdict), so the ledger recomputes
        completion from deltas on the cumulative statistics -- the same rules, applied
        agent-side to human-visible numbers."""
        cfg = self.milestone_cfg
        workspace = self.workspace_root / f"episode_{self._episode:03d}"
        # The full-resolution record of the life, for a video of it: every observation's
        # frame exactly as the green agent sent it (640x360 JPEG, the render size), named
        # by the green agent's step. It lives beside memory/, not in it -- memory/ is the
        # model's working directory and the only tree any prompt, tool or skill names --
        # so the model never sees these files, and the carry (previous/) never links them.
        self._hires_dir = workspace / "hires" if self.hires_every else None
        if self._hires_dir is not None:
            self._hires_dir.mkdir(parents=True, exist_ok=True)
        # What an earlier life hands over. mfm: its record whole, under previous/
        # (mcu_worldmodel/previous.py), for the model to read. logbook: its log, as one
        # text file beside this life's.
        previous_lives = list(self.seed_memory or []) if self.memory_mode == "mfm" else []
        seeded_log = False
        if self.seed_log:
            prev = workspace / "memory" / "previous_expedition_log.txt"
            if not prev.exists():
                prev.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(self.seed_log), prev)
                seeded_log = True
            logger.info(f"[adapter] episode {self._episode} log inherited from {self.seed_log}")
        self._agent = WorldModelAgent(
            workspace=workspace / "memory",
            task_text=self._task_text,
            ledger=MilestoneLedger(cfg, task_name=self.task,
                                   given=load_given_milestones(self.task)),
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            base_url=self.base_url,
            codex_home=self.codex_home,
            cli=self.cli,
            transcript_dir=workspace / "codex_turns",
            entry_cap=self.entry_cap,
            repeat_cap=self.repeat_cap,
            step_cap=self.step_cap,
            max_steps=self.max_steps,
            # False, not run.py's True: `extended_actions` marks that
            # `craft_env.patch_minecraft_sim()` has added `drop` to the action space, and
            # the green agent builds its simulator without that patch. Claiming otherwise
            # would let `drop` through to a handler that is not installed, where
            # `_process_action` silently skips it -- an action that reads as issued and
            # does nothing.
            extended_actions=False,
            platform_prompt=self._platform_prompt,
            memory_mode=self.memory_mode,
            session_max_turns=self.session_max_turns,
            codex_timeout=self.codex_timeout,
            vista_options=self.vista_options,
            previous_lives=previous_lives,
            carried_world=self.carried_world,
            # only passed when on, so an arm without it calls the agent as before
            **({"install_carried": True} if self.install_carried else {}),
            **({"install_scripts": list(self.install_scripts)} if self.install_scripts else {}),
            # the endgame skill probes' row options, only passed when set
            **({"grant": list(self.grant)} if self.grant else {}),
            **({"withhold": list(self.withhold)} if self.withhold else {}),
            **({"endgame_recipes": True} if self.endgame_recipes else {}),
            **({"start_dimension": self.start_dimension} if self.start_dimension else {}),
            **({"own_live": True} if self.own_live else {}),
            **({"near_deaths": True} if self.near_deaths else {}),
            frame_size=self.frame_size,
            **ARMS[self.arm],
        )
        if previous_lives:
            prev = self._agent.episodes.previous
            audit = prev.audit()
            logger.info(f"[adapter] episode {self._episode}: {audit['lives']} previous "
                        f"life/lives carried from {previous_lives}: "
                        f"{audit['files_linked']} files linked")
        if seeded_log:
            self._agent.memory.add_note(
                "Memory inherited from a previous expedition in this world: "
                "previous_expedition_log.txt is that expedition's complete "
                "append-only log, and any notes files are its distillations. The "
                "terrain and coordinates in them are still valid; your position, "
                "inventory, and step count have reset to the spawn, and every "
                "step number in the old log belongs to the OLD run, not this "
                "one. The world has reset too: every ore or resource site the "
                "old run verified -- including any it later called exhausted, "
                "looted, or retired -- is FULL again; exhaustion never survives "
                "a reset. The same reset erases what that run BUILT or LEFT: "
                "dug shafts are refilled, placed tables and furnaces are gone, "
                "dropped item caches no longer exist -- only natural terrain "
                "and ore stand as it first found them. Before searching "
                "anywhere blind, grep the old log for what it proved, walk to "
                "the nearest proven site, and mine it again, verifying arrival "
                "against your live position. If the task differs from the one "
                "it pursued, keep the world facts and re-derive the goals from "
                "the current milestone list.")
        self._workspace = workspace
        logger.info(
            f"[adapter] episode {self._episode} workspace={workspace} "
            f"arm={self.arm} milestones={len(cfg)} "
            f"platform_prompt={len(self._platform_prompt)} chars"
        )

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
        self._episode += 1
        self._step = 0
        self._agent = None
        self._task_text = payload.get("text", "")
        # The host's control reference; without it the arm would be documented by its
        # own action reference alone.
        self._platform_prompt = payload.get("prompt", "") or ""
        # The host's camera section describes a continuous angle the encoder cannot
        # deliver (see camera_contract). Both arms get the same correction, because
        # the alternative is measuring how each copes with wrong documentation.
        self._platform_prompt = with_camera_truth(self._platform_prompt)
        await self._send(
            event_queue, ctx_id,
            AckPayload(success=True, message=f"{self.arm} episode {self._episode} armed"),
        )

    async def _handle_obs(self, payload: dict, event_queue: EventQueue, ctx_id: str) -> None:
        from mcu_worldmodel.procedures import noop

        encoded = payload.get("obs")
        if not encoded:
            await self._send(event_queue, ctx_id, AckPayload(success=False, message="no observation provided"))
            return
        if not self._task_text and self._episode == 0:
            await self._send(event_queue, ctx_id,
                             AckPayload(success=False, message="no episode; send init first"))
            return

        # The green agent's own step index, not a local count: `Messenger` gives up on a
        # slow step and moves on, so a local counter drifts from the number the milestone
        # log and the recording are indexed by. Falls back if the field is ever absent.
        step = payload.get("step")
        self._step = int(step) if isinstance(step, int) else self._step + 1

        action = None
        try:
            info = dict(payload.get("info") or {})
            # `_save_frame` reads `info['pov']` at the native render size, which is where
            # the inventory GUI is legible. MCU sends that frame as a JPEG instead, so it
            # goes back under the key the agent already looks for. Inside the try: a
            # corrupt payload raises, and an exception that escapes `execute` reaches the
            # green agent as a failed task, which ends the episode rather than costing it
            # one step.
            info["pov"] = self._decode_image(encoded)
            if self._hires_dir is not None and self._step % self.hires_every == 0:
                self._keep_hires(encoded)

            if self._agent is None:
                try:
                    await asyncio.to_thread(self._build_agent, info)
                    await asyncio.to_thread(self._agent.start, info)
                except Exception:
                    # `_build_agent` has already assigned `self._agent`, so leaving it in
                    # place would send every later observation down the `observe` path with
                    # no ledger reset and no initial log entry -- an episode that is quietly
                    # broken for its whole length. Drop it and build again next observation.
                    self._agent = None
                    raise
                logger.info(
                    f"[adapter] episode {self._episode} first obs: keys={sorted(k for k in info if k != 'pov')}"
                )
            else:
                await asyncio.to_thread(self._agent.observe, info, self._step)

            # An act turn runs inside here and takes minutes; keep the event loop free
            # so the card endpoint still answers.
            action = await asyncio.to_thread(self._agent.next_action, info)
        except Exception:
            logger.exception(f"[adapter] step {self._step} failed")
        if action is None:
            action = noop()

        # A dead session means the episode is over whatever the step budget says. The
        # bridge already stops waiting (see VistaBridge.session_failed), which turns the
        # remaining steps into fast noops rather than turn-ceiling stalls -- but noops
        # for 11,000 steps are still hours of a node producing a run that cannot score.
        # End it here, with the report written first so the partial progress survives.
        # Only this arm has a session that can die this way; every other arm is
        # untouched, and nothing any model is shown changes.
        failure = getattr(getattr(self._agent, "vista", None), "session_failed", None)
        if failure is not None:
            try:
                self._agent.vista.finish()
                if self._agent.episodes is not None:
                    self._agent.episodes.finish()
                self._agent.step = self._step
                self._agent.save_report(self._workspace / "worldmodel_report.json")
            except Exception as exc:  # the abort must not be lost to bookkeeping
                logger.warning(f"[adapter] report flush during abort failed: {exc}")
            logger.error(f"[adapter] step {self._step}: vista session is dead "
                         f"({type(failure).__name__}: {failure}); ending the episode")
            raise RuntimeError(f"vista session failed: {failure}") from failure

        last = self._step >= self.max_steps - 1
        if last or (self.report_every and self._step and self._step % self.report_every == 0):
            # There is no end-of-episode message in this protocol, so the report is
            # flushed periodically: a run stopped by a deadline still has one. On the
            # last step the MFM arm's open episode is closed first, so its store and
            # index are complete.
            try:
                if last and self._agent.episodes is not None:
                    self._agent.episodes.finish()
                if last and getattr(self._agent, "vista", None) is not None:
                    # A play waiting in the thread gets a terminal result; the
                    # app-server is closed.
                    self._agent.vista.finish()
                self._agent.step = self._step
                self._agent.save_report(self._workspace / "worldmodel_report.json")
                logger.info(f"[adapter] step {self._step}: {self._agent.ledger.progress_line()}")
            except Exception as exc:  # never let bookkeeping kill an episode
                logger.warning(f"[adapter] report flush failed: {exc}")

        try:
            payload_out = ActionPayload(action_type="env", action=self._jsonable(action))
        except Exception:
            logger.exception("[adapter] action failed validation; sending a no-op")
            payload_out = ActionPayload(action_type="env", action=self._jsonable(noop()))
        await self._send(event_queue, ctx_id, payload_out)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError

    # -- helpers ----------------------------------------------------------

    @staticmethod
    async def _send(event_queue: EventQueue, ctx_id: str, payload) -> None:
        await event_queue.enqueue_event(
            new_agent_text_message(payload.model_dump_json(), context_id=ctx_id)
        )

    @staticmethod
    def _jsonable(action: dict) -> dict:
        """Plain JSON types. `camera` stays a 2-list; every button is an int."""
        out: dict = {}
        for key, value in action.items():
            if key == "camera":
                out[key] = [float(value[0]), float(value[1])]
            else:
                out[key] = int(value)
        return out

    def _keep_hires(self, encoded: str) -> None:
        """Write this step's frame, as received, under hires/. Never lets a disk problem
        cost the episode a step: the first failure is logged and the record stops."""
        if self._hires_failed:
            return
        try:
            data, ext = self.wire_frame_bytes(encoded)
            (self._hires_dir / f"{self._step:07d}{ext}").write_bytes(data)
        except Exception as exc:
            self._hires_failed = True
            logger.warning(f"[adapter] hires frame at step {self._step} not kept ({exc}); "
                           f"the hires record stops here")

    @staticmethod
    def wire_frame_bytes(encoded: str) -> tuple[bytes, str]:
        """The frame's bytes as they came over the wire, and the extension its magic
        number says they are (the green agent encodes JPEG; PNG is accepted too)."""
        data = base64.b64decode(encoded)
        if data[:3] == b"\xff\xd8\xff":
            return data, ".jpg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return data, ".png"
        raise ValueError(f"not a JPEG or PNG frame ({data[:4]!r})")

    @staticmethod
    def _decode_image(encoded: str) -> np.ndarray:
        """Decode to an RGB array, which is what `Image.fromarray` in `_save_frame` wants.

        The green agent encodes the simulator's RGB frame with `cv2.imencode`, which treats
        its input as BGR; decoding it back with `cv2.imdecode` applies the same swap a
        second time, so the array that comes out is the original RGB order.
        """
        buffer = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image decoding failed.")
        return image


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one memory arm as an MCU purple agent.")
    parser.add_argument("--memory", type=str, default="mfm", choices=sorted(ARMS),
                        help="the arm: direct (no persistent memory), logbook (PRO-LONG: "
                             "an append-only logs.txt the model greps), vista (VISTA: one "
                             "thread calling `play`, the frame archive behind `inspect`, "
                             "GUIDE.md/WORKING.md), mfm-matched (Multimodal Filesystem "
                             "Memory on the baselines' contract) or "
                             "mfm (the same memory; the agent writes its own procedures "
                             "and reflexes). Settings: mcu_worldmodel/arms.py")
    parser.add_argument("--task", type=str, default="mine_diamond_from_scratch",
                        help="task_category being evaluated; names the public task "
                             "config the milestone checklist is loaded from")
    parser.add_argument("--max-steps", type=int, default=12000,
                        help="the episode's step budget, shown to the agent every turn "
                             "(the paper: 12000 for the diamond, 36000 for the dragon)")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9021)
    parser.add_argument("--card-url", type=str, help="External URL for the agent card")
    parser.add_argument("--workspace", type=str, default="output/workspaces")

    model = parser.add_argument_group("model channel")
    model.add_argument("--cli", type=str, default="codex", choices=["codex", "claude"],
                       help="which CLI carries the model: codex (GPT through the Codex "
                            "CLI) or claude (Anthropic models through Claude Code; "
                            "--base-url is then ANTHROPIC_BASE_URL)")
    model.add_argument("--model", type=str, default="gpt-6-astra")
    model.add_argument("--reasoning-effort", type=str, default="high")
    model.add_argument("--base-url", type=str, default=None,
                       help="an OpenAI-compatible endpoint instead of the account's "
                            "hosted models")
    model.add_argument("--codex-home", type=str, default=os.path.expanduser("~/.codex-eval"),
                       help="isolated home for the chosen CLI (CODEX_HOME, or "
                            "CLAUDE_CONFIG_DIR under --cli claude)")
    model.add_argument("--session-turns", type=int, default=None,
                       help="drop the model session after this many turns (0 = never: one "
                            "thread for the life, compacted by the CLI). Default: 1 for "
                            "direct, 0 for the memory arms")
    model.add_argument("--codex-timeout", type=int, default=480,
                       help="seconds one model turn may take (under the green agent's "
                            "600 s step timeout)")

    plan = parser.add_argument_group("plan size")
    plan.add_argument("--entry-cap", type=int, default=40, help="entries in one plan")
    plan.add_argument("--repeat-cap", type=int, default=200, help="repeats of a raw action")
    plan.add_argument("--step-cap", type=int, default=400, help="ticks one plan may run")

    frames = parser.add_argument_group("frames")
    frames.add_argument("--frame-size", type=str, default="320x180",
                        help="WxH of the frames attached to the model (the render is "
                             "640x360)")
    frames.add_argument("--hires-every", type=int, default=1,
                        help="keep every Nth observation's frame as sent by the green agent "
                             "(640x360 JPEG) under episode_NNN/hires/, outside the model's "
                             "working directory, for a video of the life; 0 = off")

    carry = parser.add_argument_group("an earlier life")
    carry.add_argument("--seed-memory", type=str, action="append", default=None,
                       help="mfm: the memory dir of an earlier life in this world; its "
                            "record (logs.txt, episodes/, index.jsonl, grid.jsonl, mine/) is "
                            "carried under previous/ for the model to read. Repeat the flag "
                            "to carry several lives, oldest first")
    carry.add_argument("--carried-world", choices=("same", "other"), default="same",
                       help="mfm with --seed-memory: where the carried lives were played. "
                            "same (default): this world, so their places hold. other: "
                            "another world and another task; the contract says so and "
                            "tells the model to take from them how to act, not where")
    carry.add_argument("--install-carried", action="store_true",
                       help="mfm with --seed-memory: install the scripts the carried lives "
                            "wrote (or edited from an example) into this life's mine/, armed "
                            "and callable, and say so in the contract. Off (default): they "
                            "stay in previous/ for the model to copy")
    carry.add_argument("--install-scripts", type=str, action="append", default=None,
                       help="mfm WITHOUT --seed-memory: the memory dir of an earlier life (and "
                            "the lives it carried); only the scripts those lives wrote are "
                            "installed into this life's mine/. No log, notes or episodes of "
                            "theirs are carried: the skills-only arm")
    carry.add_argument("--seed-log", type=str, default=None,
                       help="logbook: the logs.txt of an earlier life; copied beside this "
                            "life's log as previous_expedition_log.txt")

    probe = parser.add_argument_group("the endgame skill probes (slurm/skill_reuse3.sbatch)")
    probe.add_argument("--grant", type=str, action="append", default=None,
                       help="procedure names, comma-separated (repeatable), ADDED to the arm's "
                            "set: a row is the shipped arm (the atoms) plus these macros")
    probe.add_argument("--withhold", type=str, action="append", default=None,
                       help="procedure names taken OUT of the arm's set; a call answers with "
                            "a note")
    probe.add_argument("--endgame-recipes", action="store_true",
                       help="write the chain's doctrine past the iron pickaxe (blazes, "
                            "endermen, the eye, the stronghold, the End, the dragon) as "
                            "references/endgame.md, headed by which macros it names are "
                            "built in for this row")
    probe.add_argument("--start-dimension", choices=("overworld", "nether", "end"), default=None,
                       help="where the task config puts the avatar at reset (the engine's "
                            "biome id cannot tell); end_stone_tail and dragon_tail start "
                            "in the End")

    live = parser.add_argument_group("the model's own scripts")
    live.add_argument("--own-live", action="store_true",
                      help="mfm: a script under mine/procedures/ that declares LOOP = True is "
                           "a closed loop -- run during the plan, each time the actions it "
                           "returned have finished, on the live state and a PNG of the live "
                           "view -- and the model's reflexes get that PNG too. Off (default): "
                           "its scripts see the numbers of the turn only")

    live.add_argument("--near-deaths", action="store_true",
                      help="name a death whose respawn is close to where it happened: the "
                           "YOU DIED note is otherwise written only for a respawn 15+ blocks "
                           "away, and a death at the spawn (a fight there, a fall onto it) "
                           "passes unnamed with the plan still running. Any memory mode. "
                           "Off (default): the shipped rule")

    vista = parser.add_argument_group("vista")
    vista.add_argument("--vista-thread-bytes", type=int, default=None,
                       help="base64 image bytes one thread may carry before the "
                            "checkpoint handoff (default 4,000,000; 0 = off)")
    vista.add_argument("--vista-frame-every", type=int, default=None,
                       help="ticks between archived intermediate frames of a running entry")
    vista.add_argument("--vista-idle-timeout", type=float, default=None,
                       help="seconds of app-server silence before the thread is resumed")
    args = parser.parse_args()

    mode = MEMORY_MODE[args.memory]
    if args.seed_memory and mode != "mfm":
        parser.error("--seed-memory carries an earlier life's record: it needs an mfm arm")
    if args.carried_world == "other" and not (args.seed_memory and args.memory == "mfm"):
        parser.error("--carried-world other describes carried lives: it needs --memory mfm "
                     "and --seed-memory")
    if args.install_carried and not (args.seed_memory and args.memory == "mfm"):
        parser.error("--install-carried installs carried lives' scripts: it needs --memory mfm "
                     "and --seed-memory")
    if args.install_scripts and (args.seed_memory or args.memory != "mfm"):
        parser.error("--install-scripts installs scripts without carrying the lives: it needs "
                     "--memory mfm and no --seed-memory (with one, use --install-carried)")
    if args.own_live and args.memory != "mfm":
        parser.error("--own-live gives the model's own scripts the live view: it needs "
                     "--memory mfm")
    if args.seed_log and mode != "logbook":
        parser.error("--seed-log carries an earlier life's log: it needs --memory logbook")
    vista_options = {k: v for k, v in (("thread_bytes", args.vista_thread_bytes),
                                       ("frame_every", args.vista_frame_every),
                                       ("idle_timeout", args.vista_idle_timeout)) if v is not None}
    if vista_options and mode != "vista":
        parser.error("--vista-* options need --memory vista")
    try:
        fw, fh = (int(v) for v in args.frame_size.lower().split("x"))
    except ValueError:
        parser.error("--frame-size must be WxH, e.g. 640x360 or 320x180")
    session_turns = (SESSION_TURNS[args.memory] if args.session_turns is None
                     else args.session_turns)

    names = lambda vals: [n.strip() for v in (vals or []) for n in v.split(",") if n.strip()]  # noqa: E731
    executor = WorldModelExecutor(
        workspace_root=Path(args.workspace),
        model=args.model,
        codex_home=Path(args.codex_home) if args.codex_home else None,
        cli=args.cli,
        reasoning_effort=args.reasoning_effort,
        base_url=args.base_url,
        entry_cap=args.entry_cap,
        repeat_cap=args.repeat_cap,
        step_cap=args.step_cap,
        max_steps=args.max_steps,
        memory_mode=args.memory,
        task=args.task,
        seed_memory=args.seed_memory, seed_log=args.seed_log,
        carried_world=args.carried_world,
        install_carried=args.install_carried,
        install_scripts=args.install_scripts,
        grant=names(args.grant) or None, withhold=names(args.withhold) or None,
        endgame_recipes=args.endgame_recipes, start_dimension=args.start_dimension,
        own_live=args.own_live, near_deaths=args.near_deaths,
        session_max_turns=session_turns,
        codex_timeout=args.codex_timeout,
        vista_options=vista_options or None,
        frame_size=(fw, fh),
        hires_every=args.hires_every,
    )
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    card = prepare_agent_card(args.card_url or f"http://{args.host}:{args.port}/")
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    logger.info(f"{args.memory} purple agent on {args.host}:{args.port} "
                f"(model={args.model} effort={args.reasoning_effort} cli={args.cli} "
                f"task={args.task} max_steps={args.max_steps} session_turns={session_turns})")
    uvicorn.run(app.build(), host=args.host, port=args.port, timeout_keep_alive=600)


if __name__ == "__main__":
    main()
