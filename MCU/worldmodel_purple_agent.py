"""The world-model agent as an MCU purple agent.

Companion to `prolong_purple_agent.py`. Both wrap a Codex-driven agent in the A2A protocol
the MCU green agent speaks, both are handed the same `InitPayload.prompt` and the same
`ObservationPayload`, and both answer with an env action. The only thing that differs is
what the agent does with its history:

    PRO-LONG      an append-only logs.txt it greps, and nothing else
    world model   the same log, plus documents it periodically recompiles from it and a
                  typed graph of beliefs the harness polices

That is the arm axis. Everything else is held constant on purpose, which is why this file
exists at all -- `mcu_worldmodel.run` builds its own simulator in-process and never sees
the host's control reference, so a number produced by it is not comparable to one produced
through the benchmark.

Three seams needed adapting, each marked below:

  * `WorldModelAgent` reads its frame from `info['pov']`, which does not survive the wire.
    MCU sends the frame as a base64 JPEG, so it is decoded and put back under that key.
  * The agent owns a `MilestoneLedger` built from the repo's public task config
    (`task_milestones.py`) -- the wire no longer carries milestone definitions or bits.
    Construction is still deferred to the first `obs`, because `start()` wants a real
    info dict for the ledger baseline and the initial frame.
  * `run.py` drives `next_action` -> `sim.step` -> `observe`. Over A2A each observation
    carries the state *after* the previous action, so the order per message is
    `observe(info)` then `next_action(info)` -- the same two calls against the same state.
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
from mcu_worldmodel.milestones import MilestoneLedger
from camera_contract import with_camera_truth
from models import AckPayload, ActionPayload
from task_milestones import load_given_milestones, load_milestone_cfg


def prepare_agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Solves MCU benchmark tasks with a filesystem world model",
        tags=["benchmark", "mcu", "worldmodel"],
        examples=[],
    )
    return AgentCard(
        name="worldmodel_agent",
        description="World-model Minecraft agent for MCU benchmark evaluation",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )


# What an inherited memory keeps and what it leaves behind: the world and its
# coordinates persist across runs on this deterministic seed, so the distilled
# knowledge (world_model docs, hypothesis graph, tools, entities, visited map)
# carries; the episodic record (logs, frames, events, step-stamped artifacts)
# does not -- a fresh episode starts its own, and stale step numbers would only
# mislead. AGENTS.md stays behind too: the running version seeds its own contract.
SEED_SKIP = {"logs.txt", "episodes", "events", "actions.json",
             "last_message.txt", "frames", "AGENTS.md"}


def seed_memory_dir(seed: Path, dest: Path) -> list[str]:
    """Copy a previous run's distilled memory into a fresh episode memory dir."""
    copied: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    for entry in sorted(Path(seed).iterdir()):
        if entry.name in SEED_SKIP or entry.name.startswith("."):
            continue
        target = dest / entry.name
        if target.exists():
            continue
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
        copied.append(entry.name)
    return copied


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
        induction_every: int = 600,
        report_every: int = 200,
        max_steps: int = 6000,
        memory_mode: str = "worldmodel",
        task: str = "mine_diamond_from_scratch",
        seed_memory: str | None = None,
        seed_log: str | None = None,
        playbook: str | None = None,
        playbook_until: int = 0,
        session_max_turns: int = 1,
        codex_timeout: int = 480,
        retrieval: bool = False,
        refusal: bool = False,
        vista_options: dict | None = None,
        expect: bool = False,
        frames: bool = False,
        corridors: bool = False,
        sites: bool = False,
        thin: bool = False,
        atoms: bool = False,
        own: bool = False,
        visual_only: bool = False,
        human_play: bool = False,
        frame_size: tuple[int, int] = (640, 360),
        hires_every: int = 1,
        own_reflexes: bool = False,
        harness_reflexes: bool = True,
        skills: bool = False,
        minimal: bool = False,
        seed_mine: str | None = None,
        event_sheet: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.expect, self.frames, self.corridors = bool(expect), bool(frames), bool(corridors)
        self.sites = bool(sites)
        self.thin = bool(thin)
        self.atoms, self.own = bool(atoms), bool(own)
        self.visual_only = bool(visual_only)
        self.human_play = bool(human_play)
        self.own_reflexes = bool(own_reflexes)
        self.harness_reflexes = bool(harness_reflexes)
        self.skills = bool(skills)
        self.minimal = bool(minimal)
        self.seed_mine = seed_mine
        self.event_sheet = bool(event_sheet)
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
        self.playbook = playbook
        self.playbook_until = int(playbook_until)
        self.session_max_turns = session_max_turns
        self.codex_timeout = codex_timeout
        # mfm only: the harness-computed [RECALL] block in the turn prompt.
        self.retrieval = bool(retrieval)
        self.refusal = bool(refusal)
        self.vista_options = vista_options
        self.entry_cap = entry_cap
        self.repeat_cap = repeat_cap
        self.step_cap = step_cap
        self.induction_every = induction_every
        self.report_every = report_every
        self.max_steps = max_steps
        # "worldmodel", "logbook", "wmlite", "direct" or "mfm". Same chassis every way --
        # execution engine, perception, caps, knowledge -- so the flag *is* the
        # claim-M arm axis.
        self.memory_mode = memory_mode
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
        seeded: list[str] = []
        seeds = ([self.seed_memory] if isinstance(self.seed_memory, str)
                 else list(self.seed_memory or []))
        previous_lives: list[str] = []
        if seeds and self.memory_mode == "mfm":
            # The mfm arm carries the seeds' records whole (mcu_worldmodel/previous.py):
            # nothing is copied into the live memory dir, so `seeded` stays empty and
            # neither inherited-memory note below applies.
            previous_lives = seeds
        elif seeds and not (workspace / "memory").exists():
            if len(seeds) > 1:
                logger.warning(f"[adapter] --seed-memory given {len(seeds)} times; the "
                               f"{self.memory_mode} arm inherits the first only")
            seeded = seed_memory_dir(Path(seeds[0]), workspace / "memory")
        if self.seed_mine:
            # `--seed-mine`: what the distiller pass (mcu_worldmodel/distill.py) wrote from
            # the previous lives -- GUIDE.md, kept scripts, candidate reflexes, the frame
            # index -- copied into this life's mine/ before the agent starts. The model's
            # own writing, not the harness's: the carry-only protocol holds.
            dst = workspace / "memory" / "mine"
            dst.mkdir(parents=True, exist_ok=True)
            n = 0
            for src in sorted(Path(self.seed_mine).rglob("*")):
                if not src.is_file():
                    continue
                rel = src.relative_to(self.seed_mine)
                tgt = dst / rel
                if tgt.exists():
                    continue
                tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tgt)
                n += 1
            logger.info(f"[adapter] episode {self._episode} mine/ seeded from {self.seed_mine}: "
                        f"{n} file(s)")
        if self.seed_log:
            prev = workspace / "memory" / "previous_expedition_log.txt"
            if not prev.exists():
                prev.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(self.seed_log), prev)
                seeded.append("previous_expedition_log.txt")
            logger.info(
                f"[adapter] episode {self._episode} memory inherited from "
                f"{self.seed_memory}: {', '.join(seeded) or 'nothing'}")
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
            induction_every=self.induction_every,
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
            retrieval=self.retrieval,
            refusal=self.refusal,
            vista_options=self.vista_options,
            previous_lives=previous_lives,
            expect=self.expect, frames=self.frames, corridors=self.corridors,
            sites=self.sites, thin=self.thin, frame_size=self.frame_size,
            atoms=self.atoms, own=self.own, visual_only=self.visual_only,
            human_play=self.human_play, own_reflexes=self.own_reflexes,
            harness_reflexes=self.harness_reflexes, skills=self.skills,
            minimal=self.minimal, event_sheet=self.event_sheet,
        )
        if previous_lives:
            prev = self._agent.episodes.previous
            logger.info(f"[adapter] episode {self._episode}: {prev.audit()['lives']} previous "
                        f"life/lives carried from {seeds}: {prev.audit()['kinds']}")
        if seeded and self.memory_mode == "logbook":
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
        elif seeded:
            self._agent.memory.add_note(
                "Memory inherited from a previous expedition in this world. The "
                "terrain, coordinates, and facts in your documents are still valid; "
                "your position, inventory, and step count have reset to the spawn. "
                "The world has reset with you: every ore or resource site any "
                "previous run verified -- including any your documents call "
                "exhausted, looted, or retired -- is FULL again; exhaustion never "
                "survives a reset. The same reset erases what previous runs "
                "BUILT or LEFT: dug shafts are refilled, placed tables and "
                "furnaces are gone, dropped item caches no longer exist -- only "
                "natural terrain and ore stand as the first run found them. "
                "Before searching anywhere blind, walk to the nearest "
                "previously-verified site (locations/ore_registry.md and "
                "spatial.md hold the coordinates) and mine it again, verifying "
                "arrival against your live position. "
                "If the task differs from the one those documents pursued, keep the "
                "world facts and re-derive the goals from the current milestone "
                "list -- a stale Goal check is the first thing to rewrite.")
        if self.playbook and self.playbook_until > 0:
            from mcu_worldmodel.playbook import (PlaybookCodex, extract_playbook,
                                                 extract_milestone_schedule)
            turns = extract_playbook(Path(self.playbook), self.playbook_until)
            schedule = [(st, c) for st, c in
                        extract_milestone_schedule(Path(self.playbook))
                        if st <= self.playbook_until]
            if turns:
                agent = self._agent
                orig_induction = agent.induction_every
                agent.induction_every = 0

                def _handover() -> None:
                    agent.induction_every = orig_induction
                    aborted = getattr(agent.codex, "aborted_at", None)
                    if aborted is not None:
                        agent.memory.add_note(
                            f"Replay ABORTED at step {aborted}: the world forked "
                            f"from the recording (a milestone the recorded route "
                            f"had banked by now has not fired here), so the rest "
                            f"of the route was discarded. From this step on every "
                            f"decision is yours -- trust this run's [EVENT]/[INV] "
                            f"lines over any memory of what you 'should' have.")
                    else:
                        agent.memory.add_note(
                            "Replay of the previous expedition's route ends here; "
                            "from this step on, every decision is yours. The "
                            "history above is real: those entries executed in "
                            "this world this run.")
                    logger.info(
                        f"[adapter] playbook handover after "
                        f"{agent.codex.replayed} turns"
                        + (f" (ABORTED at step {aborted})" if aborted is not None
                           else " (exhausted)"))

                agent.codex = PlaybookCodex(
                    agent.codex, turns, on_exhausted=_handover,
                    schedule=schedule,
                    progress=lambda: (agent.step, len(agent.ledger.achieved)))
                logger.info(
                    f"[adapter] playbook: {len(turns)} turns extracted from "
                    f"{self.playbook} (until step {self.playbook_until}); "
                    f"induction suppressed during replay")
        self._workspace = workspace
        logger.info(
            f"[adapter] episode {self._episode} workspace={workspace} "
            f"memory={self.memory_mode} milestones={len(cfg)} "
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
        # The host's control reference. `mcu_worldmodel.run` has no equivalent, so without
        # this the arm would be documented by its own action reference alone.
        self._platform_prompt = payload.get("prompt", "") or ""
        # The host's camera section describes a continuous angle the encoder cannot
        # deliver (see camera_contract). Both arms get the same correction, because
        # the alternative is measuring how each copes with wrong documentation.
        self._platform_prompt = with_camera_truth(self._platform_prompt)
        await self._send(
            event_queue, ctx_id,
            AckPayload(success=True, message=f"worldmodel episode {self._episode} armed"),
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
                await asyncio.to_thread(self._build_agent, info)
                try:
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

            # An act turn -- or, every `induction_every` steps, an induction turn -- runs
            # inside here and takes minutes; keep the event loop free so the card endpoint
            # still answers.
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
    parser = argparse.ArgumentParser(description="Run the world-model purple agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9021)
    parser.add_argument("--card-url", type=str, help="External URL for the agent card")
    parser.add_argument("--workspace", type=str, default="output/worldmodel_workspaces")
    parser.add_argument("--model", type=str, default="gpt-5.6-sol")
    parser.add_argument("--codex-home", type=str, default=os.path.expanduser("~/.codex-eval"),
                        help="isolated home for the chosen CLI (CODEX_HOME, or "
                             "CLAUDE_CONFIG_DIR under --cli claude)")
    parser.add_argument("--cli", type=str, default="codex", choices=["codex", "claude"],
                        help="which CLI carries the model: codex (GPT through the Codex "
                             "CLI) or claude (Anthropic models through Claude Code; "
                             "--base-url is then ANTHROPIC_BASE_URL)")
    parser.add_argument("--base-url", type=str, default=None,
                        help="OpenAI-compatible endpoint, for a locally served model")
    parser.add_argument("--reasoning-effort", type=str, default="medium")
    # 40, raised from 20 on trajectory evidence (dm4_final1-3, wmv22, ked_final1): the
    # entry cap was the binding constraint -- 8-15% of plans were clipped at exactly 20
    # entries while using only ~65% of the 400-tick budget (act-turn step gaps p90
    # 273-337, cap hits <=2%). With the cap at 40 the binding budget is ticks, which is
    # the resource-meaningful one. Same value for both arms; the flush guards
    # (milestone / ore / damage) still cut a stale plan the tick the world moves.
    # The Codex channel's lifecycle, as explicit arguments rather than environment
    # defaults (see prolong_purple_agent.py for the failure this prevents). The measured
    # arms ran 1-turn sessions -- every turn a fresh conversation, the filesystem the
    # only continuity -- and a 480 s ceiling under the green agent's 600 s step_timeout.
    parser.add_argument("--session-turns", type=int, default=1,
                        help="drop the codex session after this many turns (0 = never)")
    parser.add_argument("--codex-timeout", type=int, default=480,
                        help="seconds one codex turn may take")
    parser.add_argument("--entry-cap", type=int, default=40)
    parser.add_argument("--repeat-cap", type=int, default=200)
    parser.add_argument("--step-cap", type=int, default=400)
    parser.add_argument("--induction-every", type=int, default=600)
    parser.add_argument("--max-steps", type=int, default=6000,
                        help="the episode's step budget, shown to the agent every turn")
    parser.add_argument("--memory", type=str, default="worldmodel",
                        choices=["worldmodel", "logbook", "wmlite", "direct", "mfm", "vista"],
                        help="the claim-M arm axis: 'worldmodel' is the full structured "
                             "memory; 'logbook' is PRO-LONG's protocol (append-only "
                             "logs.txt + grep) on the identical substrate; 'wmlite' is "
                             "the simplification arm -- the logbook substrate plus one "
                             "induction-maintained world_model/world.md, no belief "
                             "graph, no five-document taxonomy; 'direct' is the "
                             "no-memory baseline -- no filesystem, read-only codex, "
                             "no window: each turn is the present alone 'mfm' is the logbook arm plus the Multimodal Filesystem Memory beside the log: one episode directory per plan entry (image, state, action, outcome) and tools/episodes.py to query them; 'vista' is VISTA's protocol on the same chassis -- one codex thread calling `play` one entry at a time, the frame archive behind `inspect`, GUIDE.md/WORKING.md, a checkpoint handoff when the context fills (mcu_worldmodel/vista.py).")
    parser.add_argument("--vista-thread-bytes", type=int, default=None,
                        help="vista only: base64 image bytes one codex thread may carry "
                             "before the checkpoint handoff (mfm/vista/runner.py default)")
    parser.add_argument("--vista-frame-every", type=int, default=None,
                        help="vista only: ticks between archived intermediate frames of "
                             "a running entry (mcu_worldmodel/vista.py default)")
    parser.add_argument("--vista-idle-timeout", type=float, default=None,
                        help="vista only: seconds of app-server silence before the thread "
                             "is abandoned and resumed (mfm/vista/runner.py default)")
    parser.add_argument("--retrieval", action="store_true",
                        help="mfm only: put a harness-computed [RECALL] block in the "
                             "turn prompt -- actions that changed nothing in their last "
                             "calls, what happened at this spot before, the entries "
                             "that scored each milestone (mfm.memory.retrieve)")
    parser.add_argument("--refuse", action="store_true",
                        help="mfm only: veto a plan from the episode record -- an action "
                             "that changed nothing in its last 5 calls anywhere, or a "
                             "descent away from the placed crafting table -- unless the "
                             "entry says `why` / `leave_table` (mcu_worldmodel/episodes.py)")
    parser.add_argument("--expect", action="store_true",
                        help="mfm only: the prediction protocol -- the briefing ends with "
                             "an EXPECT line, echoed next turn against the harness record")
    parser.add_argument("--frames", action="store_true",
                        help="mfm only: tools/zoom.py in the workspace (and, with --sites, "
                             "frame= pointers on the [KNOWN SITES] lines)")
    parser.add_argument("--no-event-sheet", action="store_true",
                        help="mfm only: do not attach the 2x2 sheet of this turn's event frames "
                             "(the current view alone; the frames stay on disk in episodes/)")
    parser.add_argument("--sites", action="store_true",
                        help="mfm only: push the carried lives' verified places (water, "
                             "lava, ore, deaths) into the turn prompt as [KNOWN SITES]. NOT "
                             "the MFM protocol -- the carry alone leaves previous/ for the "
                             "model to read; this reproduces the ob1..obf3 chain")
    parser.add_argument("--corridors", action="store_true",
                        help="mfm only, with --sites: the earlier lives' dry corridors "
                             "(tunnels dug at y<=14 without incident) in [KNOWN SITES]")
    parser.add_argument("--thin", action="store_true",
                        help="any memory mode: a one-page contract (task, memory protocol, "
                             "response format, action schema, procedure index); the GUI, "
                             "skills, survival and control sections go to references/ in "
                             "the workspace, read on demand (dropped for --memory direct)")
    parser.add_argument("--atoms", action="store_true",
                        help="any memory mode: the procedure set is procedures.ATOMS (the "
                             "closed-loop primitives, the GUI and the one-call craft); the "
                             "task-shaped macros are refused with a note")
    parser.add_argument("--own", action="store_true",
                        help="mfm only: mine/ persists across turns and is carried to the "
                             "next life; mine/procedures/<name>.py scripts are procedures "
                             "(mcu_worldmodel/own.py)")
    parser.add_argument("--own-reflexes", action="store_true",
                        help="mfm + --own (or --human-play): mine/reflexes/<name>.py scripts "
                             "run every 4 ticks on the live state and may stop the plan, "
                             "note and act (mcu_worldmodel/own.py); the contract names "
                             "what to write first")
    parser.add_argument("--no-harness-reflexes", action="store_true",
                        help="mfm + --own-reflexes: the runner's guards, escapes, governor "
                             "and nudges are off (as in --human-play); the model's own "
                             "reflexes are the tick layer")
    parser.add_argument("--skills", action="store_true",
                        help="mfm + thin + --own: the meta-level skill package "
                             "(skills/<name>/SKILL.md + scripts; mcu_worldmodel/skills.py) "
                             "with the reflex examples under skills/reflexes/scripts/ (nothing "
                             "is installed under mine/reflexes/: the model copies what it wants)")
    parser.add_argument("--minimal", action="store_true",
                        help="the short contract (prompts.MINIMAL_CONTRACT): task, loop, tools, "
                             "memory, one safety line, the procedure index; every rule in "
                             "references/, the meta layer in skills/ (needs --skills)")
    parser.add_argument("--seed-mine", type=str, default=None,
                        help="a mine/ directory written by the distiller pass "
                             "(scripts/distill.py) -- copied into this life's mine/ before start")
    parser.add_argument("--visual-only", action="store_true",
                        help="mfm + thin only: the model is served the frame alone -- no "
                             "state/inventory/map text, no retrieval block, no event sheet; "
                             "coordinate-free atoms; notes scrubbed of coordinates "
                             "(mcu_worldmodel/visual.py)")
    parser.add_argument("--human-play", action="store_true",
                        help="mfm only: play like a person -- the memory mechanism, the frame "
                             "and the state text, no built-in skills beyond the GUI cursor and "
                             "watch, no advice, no reflexes; the model writes its own scripts "
                             "(implies --own; mcu_worldmodel/human.py)")
    parser.add_argument("--frame-size", type=str, default="640x360",
                        help="WxH of the frames attached to the model (the render is "
                             "640x360; smaller frames make longer sessions affordable)")
    parser.add_argument("--hires-every", type=int, default=1,
                        help="keep every Nth observation's frame as sent by the green agent "
                             "(640x360 JPEG) under episode_NNN/hires/, outside the model's "
                             "working directory, for a video of the life; 0 = off")
    parser.add_argument("--task", type=str, default="mine_diamond_from_scratch",
                        help="task_category being evaluated; names the public task "
                             "config the milestone checklist is loaded from now that "
                             "the wire no longer carries the scoring spec")
    parser.add_argument("--no-strategy-knowledge", action="store_true",
                        help="ablation: drop the run-distilled strategy bullets from the "
                             "prompts, keeping game constants and harness mechanics")
    parser.add_argument("--seed-log", type=str, default=None,
                        help="path to a previous run's logs.txt; copied into this "
                             "episode's memory as previous_expedition_log.txt so an "
                             "append-only-log protocol can inherit its own record")
    parser.add_argument("--seed-memory", type=str, action="append", default=None,
                        help="path to a previous run's episode memory dir; its "
                             "distilled knowledge (docs, hypotheses, tools, maps) is "
                             "copied into each fresh episode before the agent starts. "
                             "With --memory mfm the seed's RECORD (logs.txt, episodes/, "
                             "index.jsonl) is carried under previous/ instead and the "
                             "sites its log verified are pushed into the turn prompt; "
                             "repeat the flag to carry several lives (oldest first)")
    parser.add_argument("--playbook", type=str, default=None,
                        help="path to a previous run's logs.txt; its executed entries "
                             "are replayed at sim speed with zero model calls, then "
                             "the model takes over (DIAGNOSTIC runs only, scores are "
                             "not comparable to from-scratch runs)")
    parser.add_argument("--playbook-until", type=int, default=0,
                        help="replay entries logged at or before this step")
    args = parser.parse_args()

    if args.memory == "direct" and (args.seed_log or args.seed_memory or args.playbook):
        # The no-memory baseline has no memory to seed and no log to replay from; a
        # seeded direct arm would be a different (undefined) arm, not this one.
        parser.error("--memory direct cannot be combined with --seed-log, "
                     "--seed-memory or --playbook")
    if (args.retrieval or args.refuse) and args.memory != "mfm":
        parser.error("--retrieval/--refuse need --memory mfm (both are computed from the store)")
    vista_options = {k: v for k, v in (("thread_bytes", args.vista_thread_bytes),
                                       ("frame_every", args.vista_frame_every),
                                       ("idle_timeout", args.vista_idle_timeout)) if v is not None}
    if vista_options and args.memory != "vista":
        parser.error("--vista-* options need --memory vista")
    if (args.expect or args.frames or args.corridors or args.sites) and args.memory != "mfm":
        parser.error("--expect/--frames/--corridors/--sites need --memory mfm")
    if args.corridors and not args.sites:
        parser.error("--corridors needs --sites")
    if args.no_event_sheet and args.memory != "mfm":
        parser.error("--no-event-sheet needs --memory mfm")
    if args.own and args.memory != "mfm":
        parser.error("--own needs --memory mfm")
    if args.visual_only and (args.memory != "mfm" or not args.thin):
        parser.error("--visual-only needs --memory mfm and --thin")
    if args.human_play and args.memory != "mfm":
        parser.error("--human-play needs --memory mfm")
    if args.own_reflexes and not (args.own or args.human_play):
        parser.error("--own-reflexes needs --own (or --human-play)")
    if args.no_harness_reflexes and not args.own_reflexes:
        parser.error("--no-harness-reflexes needs --own-reflexes")
    if args.skills and not (args.thin and args.own):
        parser.error("--skills needs --thin and --own")
    if args.minimal and not args.skills:
        parser.error("--minimal needs --skills (the meta layer the short contract points at)")
    if args.seed_mine and args.memory != "mfm":
        parser.error("--seed-mine needs --memory mfm")
    try:
        fw, fh = (int(v) for v in args.frame_size.lower().split("x"))
    except ValueError:
        parser.error("--frame-size must be WxH, e.g. 640x360 or 320x180")

    if args.no_strategy_knowledge:
        os.environ["MCU_WM_STRATEGY"] = "0"

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
        induction_every=args.induction_every,
        max_steps=args.max_steps,
        memory_mode=args.memory,
        task=args.task,
        seed_memory=args.seed_memory, seed_log=args.seed_log,
        playbook=args.playbook,
        playbook_until=args.playbook_until,
        session_max_turns=args.session_turns,
        codex_timeout=args.codex_timeout,
        retrieval=args.retrieval,
        refusal=args.refuse,
        expect=args.expect, frames=args.frames, corridors=args.corridors,
        sites=args.sites, thin=args.thin, frame_size=(fw, fh),
        hires_every=args.hires_every,
        atoms=args.atoms, own=args.own, visual_only=args.visual_only,
        human_play=args.human_play, own_reflexes=args.own_reflexes,
        harness_reflexes=not args.no_harness_reflexes, skills=args.skills,
        minimal=args.minimal, seed_mine=args.seed_mine,
        event_sheet=not args.no_event_sheet,
        vista_options=vista_options or None,
    )

    card = prepare_agent_card(args.card_url or f"http://{args.host}:{args.port}/")
    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        ),
    )
    logger.info(f"World-model purple agent: model={args.model} memory={args.memory} "
                f"retrieval={args.retrieval} refuse={args.refuse} "
                f"expect={args.expect} frames={args.frames} corridors={args.corridors} "
                f"sites={args.sites} thin={args.thin} "
                f"atoms={args.atoms} own={args.own} own_reflexes={args.own_reflexes} "
                f"harness_reflexes={not args.no_harness_reflexes} skills={args.skills} "
                f"minimal={args.minimal} seed_mine={args.seed_mine} "
                f"visual_only={args.visual_only} human_play={args.human_play} "
                f"frame_size={fw}x{fh} "
                f"codex_home={args.codex_home}")
    uvicorn.run(app.build(), host=args.host, port=args.port, timeout_keep_alive=600)


if __name__ == "__main__":
    main()
