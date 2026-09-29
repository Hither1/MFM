"""The two memory arms on a cua-lite GUI episode: PRO-LONG and the world model.

Both present the interface ``run_eval.py`` drives -- ``predict(instruction,
screenshot_png, step_idx, max_steps) -> (reply, tool_calls, done)``, ``add_feedback``,
``audit`` -- and both emit exactly the direct arm's tool calls through
``gym_codex.actions.parse_batch``. What differs is what the model remembers between
steps:

- ``CodexGuiAgent`` (direct): nothing but a text list of prior actions, resent each call.
- ``ProlongGuiAgent``: an append-only ``logs.txt`` (one section per turn: feedback,
  screenshot path, executed actions, the model's own plan), a persistent workspace,
  and a codex thread resumed across turns under an age cap.
- ``WorldModelGuiAgent``: the same log plus five compiled world-model documents, a
  belief graph under the evidence discipline, and induction passes every N act turns;
  every call a fresh conversation, the filesystem the only continuity.

An episode is one task (MineExplorer's scoping): the workspace lives
under the task's output directory and is created empty for it. The substrate is
``prolong_search`` / ``worldmodel_search`` unchanged; the KiCad grounding is in
``prompts_prolong.py`` / ``prompts_worldmodel.py``.

Failure semantics match the direct arm at the driver boundary: a turn that produced
no usable ``actions.json`` after the arm's own retries is a no-op step with feedback
(a model behaviour to measure), and a turn the infrastructure would not run at all
raises, so ``run_eval``'s backoff-then-force-terminate path applies identically. A
retried ``predict`` continues the turn it opened rather than logging a second one.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from gym_codex import backend_errors, prompts_prolong, prompts_worldmodel
from gym_codex.actions import ParsedBatch, parse_batch
from prolong_search.codex_backend import CodexTurn
from prolong_search.log import EpisodeLog, prepare_workspace
from worldmodel_search.discipline import Discipline
from worldmodel_search.hypotheses import HypothesisGraph
from worldmodel_search.memory import WorldModelWorkspace
from worldmodel_search.ops import apply_ops, read_ops

logger = logging.getLogger("gym_codex.memory")

# The PRO-LONG arm and everything the two arms share by value live in
# `gym_codex.prolong_agent`; imported here so `make_agent` and the selftest keep
# their names (`M.ProlongGuiAgent`, `M.RETRY_NUDGE`).
from gym_codex.prolong_agent import (  # noqa: E402
    DEFAULT_ACT_TIMEOUT, DEFAULT_ANALYZER_RETRIES, DEFAULT_FINAL_INDUCTION_MIN_TURNS,
    DEFAULT_INDUCTION_EVERY, DEFAULT_INDUCTION_TIMEOUT, DEFAULT_PER_DOC_CHARS,
    DEFAULT_SESSION_TURNS_PROLONG, NO_ARTIFACT_FEEDBACK, RETRY_NUDGE, ProlongGuiAgent,
    _briefing_and_plan, _load_artifact, _png_hash,
)


class _MemoryGuiAgent:
    """What the two arms share: the per-task workspace, the log, the turn protocol."""

    arm = "memory"

    def __init__(self, *, workspace: Path, model: str, effort: str, max_steps: int,
                 transcript_dir: Optional[Path] = None, codex_home: Optional[str] = None,
                 timeout: int = DEFAULT_ACT_TIMEOUT, session_turns: Optional[int] = None,
                 analyzer_retries: int = DEFAULT_ANALYZER_RETRIES,
                 base_url: Optional[str] = None) -> None:
        self.visible, record = prepare_workspace(Path(workspace), ablated=False)
        self.log = EpisodeLog(record, attachment_markers=("SCREEN",),
                              attachment_dirs=("frames",))
        self.max_steps = max_steps
        self.analyzer_retries = analyzer_retries
        self.codex = CodexTurn(
            self.visible, model=model, artifact_name="actions.json",
            reasoning_effort=effort, timeout=timeout,
            codex_home=Path(codex_home) if codex_home else None,
            transcript_dir=Path(transcript_dir) if transcript_dir else None,
            session_max_turns=session_turns,
            base_url=base_url,   # the induction sub-turns inherit it via main.base_url
        )
        self.turn = 0                 # 1-based once the first turn opens
        self.act_turns = 0
        self.parse_failures = 0
        self.no_op_turns = 0
        self._call_seq = 0
        self._pending_feedback: str | None = None
        # The turn the driver is currently asking about, once its section is written.
        # A `predict` retried by the driver after an infra failure re-enters here and
        # must not log a second section for the same step.
        self._open: dict[str, Any] | None = None
        self._task: str | None = None
        self._last_message = ""

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
        self._open_turn(instruction, screenshot_png, step_idx, max_steps)
        self._before_act()
        pb, message = self._act()
        self._close_turn(pb, message)
        return message, pb.calls, pb.done

    # -- the turn protocol ----------------------------------------------------

    def _tool_call(self, name: str, args: dict) -> dict:
        self._call_seq += 1
        return {"id": f"call_{self._call_seq:04d}", "type": "function",
                "function": {"name": name, "arguments": args}}

    def _open_turn(self, instruction: str, png: bytes, step_idx: int, max_steps: int) -> None:
        if self._open is not None:
            return                      # a driver retry of the same step
        self.max_steps = max_steps
        if self._task is None:
            self._task = instruction
            self.log.write_initial(
                "Turn 0 | EPISODE START",
                [f"[TASK] {instruction.strip()}",
                 f"Step budget: {max_steps}. One section per turn follows. No section "
                 f"carries a score: nothing tells you whether the task is going well."],
            )
            self._write_system_prompt()
        self.turn += 1
        step = step_idx + 1
        rel = self.log.save_attachment(f"frames/step_{step:04d}.png", png or b"")
        feedback = self._pending_feedback
        self._pending_feedback = None
        lines = []
        if feedback:
            lines.append(f"[FEEDBACK] {feedback}")
        lines.append(f"[SCREEN] {rel}")
        title = f"Turn {self.turn} | Step {step}/{max_steps}"
        self.log.write_section(title, lines)
        self._open = {"title": title, "step": step, "rel": rel, "feedback": feedback,
                      "abs": self.visible / rel, "png_hash": _png_hash(png)}

    def _close_turn(self, pb: ParsedBatch, message: str) -> None:
        assert self._open is not None
        self.act_turns += 1
        think = _briefing_and_plan(message)
        self.log.append_lines([f"[ACTIONS] {pb.log_line}"], plan=think,
                              title=self._open["title"])
        if pb.feedback:
            self.add_feedback(pb.feedback)
        self._open = None

    def _run_with_retries(self, base_prompt: str, images: list[Path],
                          fold: Any = None) -> dict[str, Any]:
        """One act turn's codex call under the memory arms' retry policy: a refusal
        or a capacity error extends the budget (the latter with backoff); anything
        else spends it. Returns the last result; `ok` False means the turn failed."""
        attempt, budget, refusals, capacity = 0, self.analyzer_retries, 0, 0
        result: dict[str, Any] = {"ok": False, "error": "not attempted", "artifact": None,
                                  "message": ""}
        while attempt < budget:
            attempt += 1
            prompt = base_prompt if attempt == 1 else f"{base_prompt}\n\n{RETRY_NUDGE}"
            result = self.codex.run(prompt, images=images)
            if fold is not None:
                fold()
            if result["ok"]:
                obj = _load_artifact(result["artifact"])
                if obj is not None:
                    result["obj"] = obj
                    return result
                result["ok"] = False
                result["error"] = "actions.json did not parse as a JSON object"
            err = result.get("error")
            if backend_errors.is_filter_refusal(err) and refusals < backend_errors.FILTER_RETRIES:
                refusals += 1
                budget += 1
            elif backend_errors.is_transient_infra(err) and capacity < backend_errors.CAPACITY_RETRIES:
                capacity += 1
                budget += 1
                time.sleep(min(2 ** capacity, 60))
            elif attempt < budget:
                time.sleep(min(2 ** attempt, 30))
            logger.warning("[%s] turn %d attempt %d/%d produced no actions.json (%s%s)",
                           self.arm, self.turn, attempt, budget,
                           "context overflow; " if result.get("overflow") else "", err)
        if backend_errors.is_transient_infra(result.get("error")):
            # The infrastructure's failure, not the model's: hand it to the driver's
            # own backoff rather than scoring it as a no-op step.
            raise RuntimeError(f"codex unavailable: {result.get('error')}")
        return result

    def _no_op(self, result: dict[str, Any]) -> tuple[ParsedBatch, str]:
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
        return pb, result.get("message") or ""

    # -- hooks --------------------------------------------------------------------

    def _write_system_prompt(self) -> None:
        raise NotImplementedError

    def _before_act(self) -> None:
        pass

    def _act(self) -> tuple[ParsedBatch, str]:
        raise NotImplementedError

    def audit(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            **self.codex.audit(),
            "turns": self.turn,
            "act_turns": self.act_turns,
            "parse_failures": self.parse_failures,
            "no_op_turns": self.no_op_turns,
            "workspace": str(self.visible),
        }


class CampaignWorldModel:
    """The world model that outlives a task: `<root>/world_model/*.md` plus a manifest
    of the tasks that compiled it, in order.

    Campaign scope is the arm's mechanism on a benchmark whose 25 tasks all live in one
    application: the recipes (add a symbol, set a value, wire, power symbol, save) are
    what transfers, and the v1 arm threw them away after every task -- on the one task
    it solved, the induction pass never even ran. Single-writer: kicad runs at
    concurrency 1, and `seed`/`publish` are called by consecutive tasks in order.
    Every publish also snapshots the documents under `history/`, so how the model
    evolved over the campaign stays auditable.
    """

    GOAL_CHECK_RE = re.compile(r"\n## Goal check\b.*\Z", re.DOTALL)

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.docs_dir = self.root / "world_model"
        self.manifest_path = self.root / "manifest.json"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def prior_tasks(self) -> list[str]:
        return [m["task_id"] for m in self.manifest()]

    def seed(self, world_model_dir: Path) -> int:
        """Copy the campaign's documents into a fresh episode workspace (before the
        workspace seeds its placeholders). The procedural goal check is the previous
        task's post-mortem and is dropped: the new task has not been evaluated yet."""
        n = 0
        for src in sorted(self.docs_dir.glob("*.md")):
            text = src.read_text(encoding="utf-8")
            if src.stem == "procedural":
                text = self.GOAL_CHECK_RE.sub("", text).rstrip() + (
                    "\n\n## Goal check\n(not yet evaluated for this task -- the "
                    "previous task's post-mortem was dropped here)\n")
            (world_model_dir / src.name).write_text(text, encoding="utf-8")
            n += 1
        return len(self.prior_tasks()) if n else 0

    def publish(self, world_model_dir: Path, task_id: str, info: dict[str, Any]) -> None:
        entry = {"task_id": task_id, "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 **info}
        manifest = self.manifest()
        snap = self.root / "history" / f"{len(manifest):02d}_{task_id}"
        snap.mkdir(parents=True, exist_ok=True)
        for src in sorted(world_model_dir.glob("*.md")):
            text = src.read_text(encoding="utf-8")
            (snap / src.name).write_text(text, encoding="utf-8")
            tmp = self.docs_dir / (src.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(self.docs_dir / src.name)
        manifest.append(entry)
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        tmp.replace(self.manifest_path)


class WorldModelGuiAgent(_MemoryGuiAgent):
    """The world-model arm: compiled documents + belief graph + induction passes.

    Defaults are the v1 arm (every call a fresh conversation, episode-scoped model,
    sequential induction, no verification). The v2 levers are opt-in and separately
    flagged so each can be ablated:

    - ``session_turns`` > 1: the thread is resumed across that many act turns (as
      prolong's is), and dropped after every induction pass so the recompiled
      documents are re-read rather than remembered.
    - ``parallel_induction``: the five document calls of a pass run concurrently, each
      on its own CodexTurn (its own `-o` file and transcript dir, the shared
      workspace); the ops call follows once they are all in.
    - ``campaign_dir``: campaign scope -- the documents are seeded from the campaign's
      store at episode start and published back at episode end (``finish``).
    - ``final_induction``: a document-only pass after the episode ends, when at least
      ``final_induction_min_turns`` act turns happened since the last pass. Only
      meaningful under campaign scope.
    - ``verify_before_terminate``: the episode's first terminate(success) is held for
      one verification call against the current screen; that call's batch is what
      executes.
    """

    arm = "worldmodel"
    _TREF_RE = re.compile(r"\bT(\d+)\b")

    def __init__(self, *, induction_every: int = DEFAULT_INDUCTION_EVERY,
                 per_doc_chars: int = DEFAULT_PER_DOC_CHARS,
                 induction_timeout: int = DEFAULT_INDUCTION_TIMEOUT,
                 session_turns: Optional[int] = None,
                 parallel_induction: bool = False,
                 campaign_dir: Optional[Path] = None,
                 final_induction: bool = False,
                 final_induction_min_turns: int = DEFAULT_FINAL_INDUCTION_MIN_TURNS,
                 verify_before_terminate: bool = False,
                 task_id: Optional[str] = None,
                 **kw: Any) -> None:
        # v1: a fresh conversation every call (the driver's --session-turns is
        # prolong's and is ignored here). v2 passes its own cadence explicitly.
        self.session_turns = session_turns if session_turns and session_turns > 1 else 1
        super().__init__(session_turns=self.session_turns, **kw)
        self.induction_every = induction_every
        self.per_doc_chars = per_doc_chars
        self.induction_timeout = induction_timeout
        self.parallel_induction = parallel_induction
        self.final_induction = final_induction
        self.final_induction_min_turns = final_induction_min_turns
        self.verify_before_terminate = verify_before_terminate
        self.task_id = task_id or self.visible.parent.name
        self.wm = WorldModelWorkspace(self.visible, docs=prompts_worldmodel.WORLD_MODEL_DOCS)
        # Campaign scope: the carried-over documents land before the placeholders,
        # which `seed_world_model` then skips.
        self.campaign = CampaignWorldModel(Path(campaign_dir)) if campaign_dir else None
        self.prior_tasks: Optional[int] = None
        if self.campaign is not None:
            self.prior_tasks = self.campaign.seed(self.wm.world_model_dir)
        self.wm.seed_world_model()
        self.graph = HypothesisGraph()
        self.discipline = Discipline(
            self.graph, ref_re=self._TREF_RE, unit="turns",
            same_source_note="two turns on one unchanged screen are one look, not two")
        self.induction_turns = 0
        self.induction_silent = 0
        self.induction_calls_silent = 0
        self.tampering = 0
        self._last_induction_at = 0
        self._last_step = 0
        self._doc_turns: dict[str, CodexTurn] = {}
        self._verified = False
        self.verify_outcome: Optional[str] = None
        self.final_induction_ran = False
        self.published = False
        self._finished = False

    def _write_system_prompt(self) -> None:
        self.codex.write_system_prompt(prompts_worldmodel.build_system_prompt(
            self.max_steps, resumed=self.session_turns > 1, prior_tasks=self.prior_tasks))

    # -- belief bookkeeping ----------------------------------------------------

    def _persist_graph(self) -> None:
        self.graph.save(self.wm.graph_path)
        self.graph.write_markdown(self.visible / "hypotheses")

    def _fold_ops(self) -> None:
        out = read_ops(self.visible)
        if out["error"]:
            self.log.add_note(out["error"])
        _, notes = apply_ops(self.graph, self.discipline, out["ops"], step=self.turn)
        for note in notes:
            self.log.add_note(note)
        self._persist_graph()

    def _check_integrity(self, before: dict[str, int], where: str) -> None:
        for t in self.wm.assert_harness_files_intact(before):
            self.tampering += 1
            self.log.add_note(f"harness-owned file was modified during {where} and is "
                              f"not yours to write: {t}")

    # -- turns -----------------------------------------------------------------

    def _open_turn(self, instruction: str, png: bytes, step_idx: int, max_steps: int) -> None:
        super()._open_turn(instruction, png, step_idx, max_steps)
        if self._open is not None:
            self._last_step = self._open["step"]     # the final pass's step, after close

    def _before_act(self) -> None:
        assert self._open is not None
        # One screenshot per turn is the frame set the independence rule keys on.
        self.discipline.frame_ids[self.turn] = frozenset({self._open["png_hash"]})
        if (self.induction_every > 0 and self.act_turns > 0
                and self.act_turns % self.induction_every == 0
                and not self._open.get("induced")):
            self._open["induced"] = True     # once per turn, even if the act retries
            self.run_induction()

    def _act(self) -> tuple[ParsedBatch, str]:
        assert self._open is not None
        seen = prompts_worldmodel.build_seen_before(self.discipline.seen_before(self.turn))
        prompt = prompts_worldmodel.build_act_prompt(
            turn=self.turn, step=self._open["step"], max_steps=self.max_steps,
            task=self._task or "", screen_path=self._open["rel"],
            feedback=self._open["feedback"],
            world_model=self.wm.world_model_summary(self.per_doc_chars),
            graph_summary=self.graph.to_prompt_summary(12, self.discipline.flags(self.turn)),
            discipline_summary=self.discipline.summary(),
            seen_before=seen, prior_tasks=self.prior_tasks,
        )
        before = self.wm.snapshot_harness_files()
        # Ops are folded after every attempt: a turn that reasoned but fumbled the
        # artifact still learned something, and the ops file is consumed either way.
        result = self._run_with_retries(prompt, [self._open["abs"]], fold=self._fold_ops)
        self._check_integrity(before, f"turn {self.turn}")
        if not result["ok"]:
            return self._no_op(result)
        pb = parse_batch(result["obj"], self._tool_call, no_json_feedback=NO_ARTIFACT_FEEDBACK)
        message = result.get("message") or ""
        if pb.done and self.verify_before_terminate and not self._verified \
                and _is_success_terminate(pb):
            return self._verify(pb, message)
        return pb, message

    def _verify(self, pb: ParsedBatch, message: str) -> tuple[ParsedBatch, str]:
        """Hold the episode's first terminate(success) for one check against the
        current screen; the check's own batch is what executes. Once per episode, so
        a model that terminates again after checking is not looped."""
        assert self._open is not None
        self._verified = True
        self.log.add_note(f"turn {self.turn}: terminate(success) held for a verification "
                          f"call against the current screen")
        prompt = prompts_worldmodel.build_verify_prompt(
            turn=self.turn, step=self._open["step"], max_steps=self.max_steps,
            screen_path=self._open["rel"])
        before = self.wm.snapshot_harness_files()
        result = self._run_with_retries(prompt, [self._open["abs"]], fold=self._fold_ops)
        self._check_integrity(before, f"verification at turn {self.turn}")
        if not result["ok"]:
            self.verify_outcome = "unusable; original terminate executed"
            self.log.add_note("the verification call produced no usable ./actions.json; "
                              "the terminate stood")
            return pb, message
        pb2 = parse_batch(result["obj"], self._tool_call, no_json_feedback=NO_ARTIFACT_FEEDBACK)
        self.verify_outcome = "terminated" if pb2.done else f"continued: {pb2.log_line}"
        logger.info("[worldmodel] verification at turn %d: %s", self.turn, self.verify_outcome)
        return pb2, result.get("message") or ""

    # -- induction --------------------------------------------------------------

    def _doc_turn(self, doc: str) -> CodexTurn:
        """A CodexTurn of the parallel pass's own for one document: same workspace and
        home, its own closing-message file and transcript dir, never resumed."""
        turn = self._doc_turns.get(doc)
        if turn is None:
            main = self.codex
            turn = CodexTurn(
                self.visible, model=main.model, artifact_name=f".induction_{doc}.unused",
                message_name=f".induction_{doc}.msg", reasoning_effort=main.reasoning_effort,
                base_url=main.base_url, codex_bin=main.codex_bin, codex_home=main.codex_home,
                timeout=self.induction_timeout,
                transcript_dir=(main.transcript_dir / f"induction_{doc}"
                                if main.transcript_dir else None),
                session_max_turns=1,
            )
            self._doc_turns[doc] = turn
        return turn

    def _induction_call(self, turn: CodexTurn, prompt: str, what: str) -> dict[str, Any]:
        result: dict[str, Any] = {"ok": False, "message": "", "error": "not attempted"}
        for attempt in range(1 + backend_errors.FILTER_RETRIES):
            result = turn.run(prompt, images=(), expect_artifact=False,
                              timeout=self.induction_timeout)
            if result["ok"] or not backend_errors.is_filter_refusal(result.get("error")):
                break
            logger.warning("[worldmodel] induction call %s declined (attempt %d)",
                           what, attempt + 1)
        return result

    def run_induction(self, final: bool = False) -> None:
        """Recompile the world model: one act-sized call per document (sequential on
        the shared turn, or concurrent on per-document turns), then -- unless the
        episode has ended -- the belief-ops call. Consumes no environment step.
        Silent calls (a document the call did not rewrite) are counted, logged and
        not retried; refusals are."""
        self.induction_turns += 1
        self._last_induction_at = self.act_turns
        step = self._open["step"] if self._open else self._last_step
        logger.info("[worldmodel] %sinduction pass %d after %d act turns (step %d)%s",
                    "final " if final else "", self.induction_turns, self.act_turns, step,
                    " [parallel]" if self.parallel_induction else "")
        pass_stamps = self.wm.doc_stamps()
        before = self.wm.snapshot_harness_files()
        silent: list[str] = []
        summary = ""
        t0 = time.time()

        def doc_prompt(doc: str) -> str:
            return prompts_worldmodel.build_induction_doc_prompt(
                doc=doc, turns=self.turn - (0 if final else 1), step=step,
                max_steps=self.max_steps, per_doc_chars=self.per_doc_chars,
                final=final, prior_tasks=self.prior_tasks, task_id=self.task_id)

        def record(doc: str, call_stamps: dict, result: dict[str, Any]) -> None:
            if self.wm.docs_touched(call_stamps) == 0:
                silent.append(doc)
                self.induction_calls_silent += 1
                logger.warning("[worldmodel] induction call %s of pass %d rewrote nothing (%s)",
                               doc, self.induction_turns,
                               result.get("error") or "call completed without writing")

        docs = prompts_worldmodel.INDUCTION_DOC_ORDER
        if self.parallel_induction:
            stamps = {doc: self.wm.doc_stamps() for doc in docs}
            with ThreadPoolExecutor(max_workers=len(docs)) as pool:
                futures = {doc: pool.submit(self._induction_call, self._doc_turn(doc),
                                            doc_prompt(doc), doc) for doc in docs}
                results = {doc: f.result() for doc, f in futures.items()}
            for doc in docs:
                record(doc, stamps[doc], results[doc])
            self._fold_ops()
        else:
            for doc in docs:
                call_stamps = self.wm.doc_stamps()
                result = self._induction_call(self.codex, doc_prompt(doc), doc)
                self._fold_ops()
                record(doc, call_stamps, result)
        if not final:
            prompt = prompts_worldmodel.build_induction_ops_prompt(
                turns=self.turn - 1, step=step, max_steps=self.max_steps)
            result = self._induction_call(self.codex, prompt, "belief-ops")
            self._fold_ops()
            summary = (result.get("message") or "").strip()
        self._check_integrity(before, f"induction {self.induction_turns}")
        touched = self.wm.docs_touched(pass_stamps)
        if not touched:
            self.induction_silent += 1
        # The pass is recorded as its own section, then the open turn's section is
        # re-headed so the act call still finds the current turn last in the log.
        self.log.write_section(
            f"Induction {self.induction_turns} | after {self.act_turns} act turns, step {step}"
            + (" | after the episode ended" if final else ""),
            [f"[INDUCTION] {touched} document(s) rewritten"
             + (f"; nothing landed for: {', '.join(silent)}" if silent else "")
             + f" ({time.time() - t0:.0f}s)",
             *([f"[INDUCTION] {summary[:1200]}"] if summary else [])],
        )
        if self._open is not None:
            o = self._open
            lines = ([f"[FEEDBACK] {o['feedback']}"] if o["feedback"] else []) + \
                    [f"[SCREEN] {o['rel']}"]
            self.log.write_section(o["title"] + " (continued after induction)", lines)
        (self.visible / "actions.json").unlink(missing_ok=True)
        if self.codex.session_id:
            # The recompiled documents are the memory; a thread that remembers the
            # pre-induction state would keep acting on it.
            self.codex._discard_session("world model recompiled; the next act turn "
                                        "re-reads it", "age_resets")

    # -- episode end ----------------------------------------------------------------

    def finish(self, reward: Optional[float] = None, error: Optional[str] = None) -> None:
        """Called by the driver once the episode is over (any way it ended). Under
        campaign scope: a final document-only pass when enough act turns happened
        since the last one, then the documents are published for the next task."""
        if self._finished:
            return
        self._finished = True
        if self.campaign is None:
            return
        new_turns = self.act_turns - self._last_induction_at
        if self.final_induction and new_turns >= self.final_induction_min_turns:
            try:
                self.run_induction(final=True)
                self.final_induction_ran = True
            except Exception:  # noqa: BLE001 -- publish what exists regardless
                logger.exception("[worldmodel] final induction failed; publishing as is")
        else:
            logger.info("[worldmodel] no final induction (%d act turn(s) since the last "
                        "pass, threshold %d)", new_turns, self.final_induction_min_turns)
        self.campaign.publish(self.wm.world_model_dir, self.task_id, {
            "reward": reward, "error": error, "act_turns": self.act_turns,
            "induction_turns": self.induction_turns,
            "final_induction": self.final_induction_ran,
            "doc_sizes": self.wm.doc_sizes(),
        })
        self.published = True

    def audit(self) -> dict[str, Any]:
        induction_codex = {}
        for doc, turn in self._doc_turns.items():
            a = turn.audit()
            induction_codex[doc] = {k: a.get(k) for k in (
                "analyzer_turns", "timeout_resets", "empty_resets", "input_tokens",
                "output_tokens", "cached_input_tokens", "total_tokens") if k in a}
        return {
            **super().audit(),
            "induction_turns": self.induction_turns,
            "induction_silent": self.induction_silent,
            "induction_calls_silent": self.induction_calls_silent,
            "induction_every": self.induction_every,
            "per_doc_chars": self.per_doc_chars,
            "harness_files_tampered": self.tampering,
            "hypotheses": {
                "n": len(self.graph.nodes),
                "by_kind": self.graph.counts_by_kind(),
                "by_status": self.graph.counts_by_status(),
                "noop_updates": self.graph.noop_updates,
            },
            "discipline": dict(self.discipline.counters),
            **self.wm.audit(),
            # v2 levers, each recorded so a row says which arm variant produced it.
            "wm_session_turns": self.session_turns,
            "wm_parallel_induction": self.parallel_induction,
            "wm_scope": "campaign" if self.campaign is not None else "episode",
            "wm_prior_tasks": self.prior_tasks,
            "wm_final_induction": self.final_induction_ran,
            "wm_published": self.published,
            "wm_verify_before_terminate": self.verify_before_terminate,
            "wm_verify_outcome": self.verify_outcome,
            "induction_codex": induction_codex or None,
        }


# -- helpers ------------------------------------------------------------------------

def _is_success_terminate(pb: ParsedBatch) -> bool:
    if not pb.done or not pb.calls:
        return False
    fn = pb.calls[0].get("function", {})
    return fn.get("name") == "terminate" and \
        (fn.get("arguments") or {}).get("status") == "success"


def make_agent(kind: str, **kw: Any):
    if kind == "prolong":
        return ProlongGuiAgent(**kw)
    if kind == "mfm":
        # PRO-LONG plus the episode store and the plan queue (PLAN_episodic_memory.md).
        return ProlongGuiAgent(episodes=True, plan_queue=True, recall=True, **kw)
    if kind == "prolong-logonly":
        # PRO-LONG with the log as its only persistent memory: the model's own files
        # are taken back every turn (EpisodeLog log_only).
        return ProlongGuiAgent(log_only=True, **kw)
    if kind == "prolong-carry":
        # The carry rung's control: PRO-LONG with the finished tasks' logs, frames
        # and a persistent notes/ in its workspace (mfm/memory/carry.py).
        return ProlongGuiAgent(**kw)
    if kind == "mfm-carry":
        return ProlongGuiAgent(episodes=True, plan_queue=True, recall=True, **kw)
    if kind == "worldmodel":
        return WorldModelGuiAgent(**kw)
    if kind == "vista":
        from gym_codex.vista_agent import VistaGuiAgent
        return VistaGuiAgent(**kw)
    raise ValueError(f"unknown memory arm {kind!r}")
