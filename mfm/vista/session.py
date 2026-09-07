"""The segment loop (upstream `run_task_with_compact_checkpoints`), in a thread.

One episode is one session: the first segment starts the thread with the initial
observation; a checkpoint request (the PreCompact hook, or the wire-side budget) ends
the segment, the loop asks the model for the checkpoint on the same thread, then starts
a FRESH thread from the recovery prompt; a runtime failure resumes the thread with the
current observation; a turn that ends while the environment is still active is
continued. The loop runs in a background thread because the environment drives the
benchmark: the environment's step thread meets the model inside `play` through the
channel (see `channel.py`), and `close()` is how the episode's end reaches the loop.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from mfm.vista.controller import VistaController
from mfm.vista.recovery import CHECKPOINT_PROMPT, NONTERMINAL_CONTINUATION_PROMPT
from mfm.vista.runner import AppServerRunner, CodexResult

logger = logging.getLogger(__name__)

MAX_CHECKPOINT_ATTEMPTS = 2
MAX_COMPACT_CYCLES_WITHOUT_ACTION = 3
MAX_RUNTIME_RECOVERIES_PER_TURN = 8
#: Runtime failures at one turn before the thread is abandoned for a fresh one that
#: starts from the notes (upstream tries the fresh path last).
FRESH_AFTER_RUNTIME_FAILURES = 4


class VistaSession:
    def __init__(self, *, runner: AppServerRunner, controller: VistaController,
                 initial_prompt: str, initial_images: tuple[Path, ...]) -> None:
        self.runner = runner
        self.controller = controller
        self.initial_prompt = initial_prompt
        self.initial_images = tuple(initial_images)
        self.results: list[CodexResult] = []
        self.failure: BaseException | None = None
        self.checkpoints = 0
        self.runtime_recoveries = 0
        self.continuations = 0
        self._thread: threading.Thread | None = None
        self._done = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vista-session", daemon=True)
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def close(self, timeout: float = 120.0) -> None:
        """The episode is over: the controller is terminal (the bridge says so), the
        loop returns once the current segment ends. Waits for it, then makes sure no
        app-server is left behind."""
        if self._thread is None:
            return
        self._thread.join(timeout)
        if self._thread.is_alive():
            logger.warning("[vista] the session thread did not end within %.0fs; closing the "
                           "app-server", timeout)
            conn = self.runner._connection
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            self._thread.join(30)

    def _run(self) -> None:
        try:
            self._loop()
        except BaseException as exc:  # noqa: BLE001 -- recorded, reported by audit()
            self.failure = exc
            logger.exception("[vista] session loop failed")
            self.controller.force_terminal("session_failed")
        finally:
            self._done.set()

    def _loop(self) -> None:
        runner, controller = self.runner, self.controller
        results = self.results
        results.append(runner.run_task(self.initial_prompt, self.initial_images))
        session_id = results[-1].session_id
        last_checkpoint_turn: int | None = None
        cycles_without_action = 0
        recovery_turn: int | None = None
        recoveries_at_turn = 0
        continuation_scope: tuple[str, int] | None = None

        def record_runtime_failure() -> int:
            nonlocal recovery_turn, recoveries_at_turn
            if recovery_turn != controller.turn:
                recovery_turn, recoveries_at_turn = controller.turn, 0
            recoveries_at_turn += 1
            self.runtime_recoveries += 1
            if recoveries_at_turn > MAX_RUNTIME_RECOVERIES_PER_TURN:
                raise RuntimeError("Codex player runtime failed repeatedly at the same state; "
                                   f"last stderr: {results[-1].stderr_path}")
            return recoveries_at_turn

        while True:
            if controller.terminal:
                controller.discard_compact_recovery()
                return

            if controller.compact_checkpoint_marker.exists():
                if session_id is None:
                    raise RuntimeError("Codex stopped for compact without a resumable session id")
                if controller.turn == last_checkpoint_turn:
                    cycles_without_action += 1
                else:
                    last_checkpoint_turn, cycles_without_action = controller.turn, 1
                if cycles_without_action >= MAX_COMPACT_CYCLES_WITHOUT_ACTION:
                    raise RuntimeError("Compact checkpoint loop repeated without an environment action")
                if not controller.compact_checkpoint_ready.exists() or not runner.working_path.is_file():
                    checkpoint_turn, attempts = controller.turn, 0
                    while not controller.compact_checkpoint_ready.exists() or not runner.working_path.is_file():
                        if attempts >= MAX_CHECKPOINT_ATTEMPTS:
                            raise RuntimeError("Codex did not write the compact checkpoint")
                        checkpoint = runner.resume_checkpoint(session_id, CHECKPOINT_PROMPT)
                        results.append(checkpoint)
                        if checkpoint.session_id != session_id:
                            raise RuntimeError("Compact checkpoint did not resume the exact Codex session")
                        if controller.terminal:
                            break
                        if controller.turn != checkpoint_turn:
                            raise RuntimeError("Compact checkpoint turn applied an environment action")
                        if checkpoint.returncode != 0:
                            record_runtime_failure()
                            continue
                        attempts += 1
                    if controller.terminal:
                        continue
                self.checkpoints += 1
                previous = session_id
                recovery = controller.begin_compact_recovery()
                recovery_session: str | None = None
                while controller.compact_restore_marker.exists():
                    if recovery_session is None:
                        recovered = runner.run_recovery_task(recovery)
                    else:
                        recovered = runner.resume_recovery_task(recovery_session, recovery)
                    results.append(recovered)
                    if recovered.session_id is not None:
                        if recovery_session is None:
                            if recovered.session_id == previous:
                                raise RuntimeError("Compact recovery did not create its required fresh session")
                            recovery_session = recovered.session_id
                        elif recovered.session_id != recovery_session:
                            raise RuntimeError("Compact recovery did not resume the exact Codex session")
                    if recovered.returncode != 0:
                        record_runtime_failure()
                        if controller.terminal:
                            break
                        continue
                    if controller.compact_restore_marker.exists():
                        raise RuntimeError("Codex did not enter compact recovery")
                if controller.terminal:
                    continue
                if recovery_session is None:
                    raise RuntimeError("Compact recovery created no Codex session")
                session_id = recovery_session
                continue

            current = results[-1]
            if current.returncode != 0:
                if session_id is None:
                    if controller.turn != 0:
                        raise RuntimeError("Codex runtime failed after environment actions without a session id")
                    record_runtime_failure()
                    time.sleep(min(30, 5 * recoveries_at_turn))
                    results.append(runner.run_task(self.initial_prompt, self.initial_images))
                    session_id = results[-1].session_id
                    continue
                n = record_runtime_failure()
                time.sleep(min(60, 5 * n))
                recovery = controller.begin_runtime_recovery()
                if n >= FRESH_AFTER_RUNTIME_FAILURES:
                    # The thread itself may be what fails (a poisoned session): a fresh
                    # one from the notes and the present, like a compact recovery.
                    fresh = runner.run_fresh_runtime_recovery(recovery)
                    results.append(fresh)
                    if fresh.session_id is not None:
                        session_id = fresh.session_id
                    continue
                resumed = runner.resume_runtime_recovery(session_id, recovery)
                results.append(resumed)
                if resumed.session_id is not None and resumed.session_id != session_id:
                    raise RuntimeError("Runtime recovery did not resume the exact Codex session")
                continue

            if session_id is None:
                return
            scope = (session_id, controller.turn)
            if scope != continuation_scope:
                # The model ended its turn while the environment is still active: the
                # thread is continued once per (session, turn); a second silent end at
                # the same turn falls through to a fresh recovery below.
                continuation_scope = scope
                self.continuations += 1
                continued = runner.resume_nonterminal_task(session_id, NONTERMINAL_CONTINUATION_PROMPT)
                results.append(continued)
                if continued.session_id is not None and continued.session_id != session_id:
                    raise RuntimeError("Nonterminal continuation changed Codex session")
                session_id = continued.session_id or session_id
                continue
            recovery = controller.begin_runtime_recovery()
            fresh = runner.run_fresh_runtime_recovery(recovery)
            results.append(fresh)
            session_id = fresh.session_id or session_id
            continuation_scope = None

    def audit(self) -> dict[str, Any]:
        return {"segments": len(self.results), "checkpoints": self.checkpoints,
                "runtime_recoveries": self.runtime_recoveries, "continuations": self.continuations,
                "failure": f"{type(self.failure).__name__}: {self.failure}" if self.failure else None,
                "finished": self._done.is_set(), **self.runner.audit(), **self.controller.audit()}
