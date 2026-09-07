"""The controller: what stands between the tools and the environment.

Ported from the upstream `GameController` with the ARC game replaced by a `Bridge`
the benchmark implements. The controller keeps what is benchmark-neutral: the play
validation budget (an invalid action is answered with an error and does not reach the
environment; past `max_invalid_retries` of them in a row the result says so), the
event record `history` reads, the checkpoint markers and the recovery snapshots, the
frame archive `inspect` reads, and the notes files' provenance.

The bridge (`mcu_worldmodel/vista.py`, `gym_codex/vista_agent.py`) implements:

    validate(arguments) -> Validation     the play's arguments, checked without the
                                          environment (shape, vocabulary)
    execute(parsed) -> Outcome            BLOCKS until the environment has run the
                                          action; the objective result, the resulting
                                          frame, whether the episode ended
    present() -> (metadata, png | None)   the current observation as the benchmark
                                          renders it, for the initial prompt and the
                                          recovery prompts
    terminal -> bool                      the episode is over

Everything the model reads about the environment comes back through `handle`: the
play result metadata (the bridge's outcome fields plus the turn, the applied flag and
the `visual` block that addresses the archived frames), the inspect / read_pixels
views, the history events.
"""
from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from mfm.vista.archive import FrameArchive
from mfm.vista.recovery import CompactRecovery, RuntimeRecovery
from mfm.vista.tools import MAX_GUIDE_CHARS, MAX_WORKING_CHARS


@dataclass(frozen=True)
class Validation:
    ok: bool
    error: str | None = None
    parsed: Any = None
    #: What `history` records as the action (the arguments as the model gave them,
    #: or a compact rendering).
    public: Any = None


@dataclass
class Outcome:
    """What the environment reports for one play."""
    applied: bool
    #: The fields of the play result the model reads (entry, ticks, state ...).
    result: dict[str, Any] = field(default_factory=dict)
    #: The compact record `history` keeps for this play.
    event: dict[str, Any] = field(default_factory=dict)
    #: The final frame, archived as the turn's last frame and steered into the thread.
    png: bytes | None = None
    error: str | None = None
    terminal: bool = False


class Bridge(Protocol):
    def validate(self, arguments: Any) -> Validation: ...
    def execute(self, parsed: Any) -> Outcome: ...
    def present(self) -> tuple[dict[str, Any], bytes | None]: ...
    @property
    def terminal(self) -> bool: ...


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, sort_keys=True, default=str) + "\n")


def atomic_write_text(path: Path, content: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.chmod(mode)
    tmp.replace(path)


#: Files in the codex home that carry the checkpoint protocol between the hook, the
#: tools and the segment loop (upstream names).
COMPACT_RESTORE_MARKER = "compact_restore.pending"
COMPACT_GUIDE_SNAPSHOT = "compact_guide.snapshot"
COMPACT_CHECKPOINT_MARKER = "compact_checkpoint.requested"
COMPACT_CHECKPOINT_READY = "compact_checkpoint.ready"

#: How many history events a recovery prompt carries (upstream carried the level's
#: attempt summary; there are no levels here, so the tail of the record stands in).
RECOVERY_HISTORY_EVENTS = 12


class VistaController:
    def __init__(self, *, bridge: Bridge, archive: FrameArchive, private_dir: Path,
                 codex_home: Path, guide_path: Path, working_path: Path,
                 max_invalid_retries: int = 15) -> None:
        self.bridge = bridge
        self.archive = archive
        self.private_dir = Path(private_dir)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.guide_path = Path(guide_path)
        self.working_path = Path(working_path)
        self.max_invalid_retries = max_invalid_retries
        home = Path(codex_home)
        self.compact_restore_marker = home / COMPACT_RESTORE_MARKER
        self.compact_guide_snapshot = home / COMPACT_GUIDE_SNAPSHOT
        self.compact_checkpoint_marker = home / COMPACT_CHECKPOINT_MARKER
        self.compact_checkpoint_ready = home / COMPACT_CHECKPOINT_READY
        self.working_provenance_path = self.private_dir / "working_memory_provenance.json"
        self.action_log_path = self.private_dir / "action_log.jsonl"
        self.error_log_path = self.private_dir / "controller_errors.jsonl"
        self.recovery_log_path = self.private_dir / "compact_recovery.jsonl"
        #: Applied plays so far; the turn a play result carries is this after it.
        self.turn = 0
        self.attempt_index = 0
        self.total_attempts = 0
        self.invalid_plays = 0
        self.forced_termination_reason: str | None = None
        self.checkpoint_reasons: list[str] = []
        self._events: list[dict[str, Any]] = []
        self._last_result: dict[str, Any] | None = None
        self._lock = threading.RLock()

    # -- state ------------------------------------------------------------------------

    @property
    def terminal(self) -> bool:
        return self.forced_termination_reason is not None or self.bridge.terminal

    @property
    def termination_reason(self) -> str | None:
        if self.forced_termination_reason:
            return self.forced_termination_reason
        return "environment_ended" if self.bridge.terminal else None

    def force_terminal(self, reason: str) -> None:
        with self._lock:
            if self.forced_termination_reason is None:
                self.forced_termination_reason = reason

    def _metadata(self, *, action_applied: bool, error: str | None = None,
                  invalid_action_limit: bool = False, result: dict[str, Any] | None = None,
                  present: dict[str, Any] | None = None) -> dict[str, Any]:
        if present is None:
            present, _ = self.bridge.present()
        metadata: dict[str, Any] = {"turn": self.turn, "action_applied": action_applied,
                                    "terminal": self.terminal}
        if self.termination_reason:
            metadata["termination_reason"] = self.termination_reason
        if error:
            metadata["error"] = error
        if invalid_action_limit:
            metadata["invalid_action_limit"] = True
        if result:
            metadata.update(result)
        metadata.update(present or {})
        visual = self.archive.visual(self.turn)
        if visual:
            metadata["visual"] = visual
        return metadata

    def initial_metadata(self) -> dict[str, Any]:
        with self._lock:
            return self._metadata(action_applied=False)

    def initial_image_paths(self) -> list[Path]:
        last = self.archive.last(self.turn)
        return [last] if last else []

    def _response(self, *, ok: bool, action_applied: bool, error: str | None = None,
                  include_image: bool = True, invalid_action_limit: bool = False,
                  result: dict[str, Any] | None = None,
                  present: dict[str, Any] | None = None) -> dict[str, Any]:
        response: dict[str, Any] = {
            "ok": ok,
            "metadata": self._metadata(action_applied=action_applied, error=error,
                                       invalid_action_limit=invalid_action_limit,
                                       result=result, present=present),
        }
        last = self.archive.last(self.turn)
        if include_image and last is not None:
            response["image"] = {"mime_type": "image/png", "detail": "original",
                                 "data": base64.b64encode(last.read_bytes()).decode("ascii")}
        return response

    # -- the tools --------------------------------------------------------------------

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        if method == "inspect":
            return self._inspect(request.get("arguments"))
        if method == "read_pixels":
            return self._read_pixels(request.get("arguments"))
        if method == "history":
            return self._history(request.get("arguments"))
        if method == "save_compact_checkpoint":
            return self._save_compact_checkpoint(request.get("arguments"))
        if method != "play":
            return self._response(ok=False, action_applied=False,
                                  error="Unknown controller method.", include_image=False)
        return self._play(request)

    def _play(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self.terminal:
                return self._response(ok=True, action_applied=False, include_image=False)
            if self.compact_restore_marker.exists():
                return self._response(ok=False, action_applied=False,
                                      error="Compact recovery has not been delivered yet.",
                                      include_image=False)
            if self.compact_checkpoint_marker.exists():
                return self._response(ok=False, action_applied=False,
                                      error="Save the compact checkpoint before playing.",
                                      include_image=False)
            arguments = request.get("arguments")
            retry = self.attempt_index
            self.total_attempts += 1
            validation = self.bridge.validate(arguments)
            log_entry: dict[str, Any] = {
                "protocol": "app-server-tool-loop", "turn": self.turn, "retry": retry,
                "tool_call_id": request.get("request_id"), "requested": arguments,
                "validation": {"ok": validation.ok, "error": validation.error},
            }
            if not validation.ok:
                self.attempt_index += 1
                self.invalid_plays += 1
                limit = retry >= self.max_invalid_retries
                if limit:
                    self.attempt_index = 0
                    log_entry["recovery_boundary"] = "invalid_action_limit"
                append_jsonl(self.action_log_path, log_entry)
                return self._response(ok=False, action_applied=False, error=validation.error,
                                      include_image=False, invalid_action_limit=limit)
        # Outside the lock: the environment runs the action now, which takes as long
        # as it takes (tens of ticks on MCU), and `present()` must stay callable.
        try:
            outcome = self.bridge.execute(validation.parsed)
        except Exception as exc:
            with self._lock:
                error = {"turn": self.turn, "error_type": type(exc).__name__, "error": str(exc)}
                append_jsonl(self.error_log_path, error)
                log_entry["controller_error"] = error
                append_jsonl(self.action_log_path, log_entry)
                if self.forced_termination_reason is None:
                    self.forced_termination_reason = "controller_error"
            raise
        with self._lock:
            if not outcome.applied:
                # A structurally valid play the environment could not run (a
                # procedure refused against the live state, a plan the governor
                # dropped): answered like an invalid action, but it is not one, so it
                # does not spend the invalid-action budget.
                log_entry["result"] = {"applied": False, "error": outcome.error}
                append_jsonl(self.action_log_path, log_entry)
                present = outcome.result.pop("present", None)
                if outcome.terminal:
                    return self._response(ok=True, action_applied=False, include_image=False,
                                          result=outcome.result, present=present)
                return self._response(ok=False, action_applied=False, error=outcome.error,
                                      include_image=False, result=outcome.result, present=present)
            self.turn += 1
            self.attempt_index = 0
            if outcome.png:
                self.archive.add(self.turn, outcome.png)
            present = outcome.result.pop("present", None)
            metadata = self._metadata(action_applied=True, result=outcome.result,
                                      present=present)
            log_entry["result"] = {k: v for k, v in metadata.items() if k != "visual"}
            event = {"turn": self.turn, "action": validation.public, "result": outcome.event}
            self._events.append(event)
            self._last_result = event
            append_jsonl(self.action_log_path, log_entry)
            response = {"ok": True, "metadata": metadata}
            last = self.archive.last(self.turn)
            if last is not None:
                response["image"] = {"mime_type": "image/png", "detail": "original",
                                     "data": base64.b64encode(last.read_bytes()).decode("ascii")}
            return response

    def _inspect(self, arguments: object) -> dict[str, Any]:
        try:
            views, images = self.archive.inspect(arguments)
        except ValueError as exc:
            return {"ok": False, "metadata": {"error": str(exc)}}
        return {"ok": True, "images": images,
                "metadata": {"visual_kind": "inspection", "current_state_unchanged": True,
                             "view_count": len(views), "views": views}}

    def _read_pixels(self, arguments: object) -> dict[str, Any]:
        try:
            metadata = self.archive.read_pixels(arguments)
        except ValueError as exc:
            return {"ok": False, "metadata": {"error": str(exc)}}
        return {"ok": True, "metadata": metadata}

    def _history(self, arguments: object) -> dict[str, Any]:
        if not isinstance(arguments, dict) or set(arguments) - {"view", "start_turn", "end_turn", "limit"}:
            return {"ok": False, "metadata": {"error": "Invalid arguments."}}
        if arguments.get("view") != "events":
            return {"ok": False, "metadata": {"error": "Invalid history view."}}
        limit = arguments.get("limit", 64)
        if type(limit) is not int or not 1 <= limit <= 128:
            return {"ok": False, "metadata": {"error": "Invalid history limit."}}
        start, end = arguments.get("start_turn"), arguments.get("end_turn")
        for name, v in (("start_turn", start), ("end_turn", end)):
            if v is not None and (type(v) is not int or not 0 <= v <= 999999):
                return {"ok": False, "metadata": {"error": f"Invalid {name}."}}
        if isinstance(start, int) and isinstance(end, int) and start > end:
            return {"ok": False, "metadata": {"error": "start_turn must not exceed end_turn."}}
        with self._lock:
            matching = [e for e in self._events
                        if (start is None or e["turn"] >= start) and (end is None or e["turn"] <= end)]
            selected = matching[-limit:] if start is None and end is None else matching[:limit]
            turns = [e["turn"] for e in self._events]
        return {"ok": True, "metadata": {
            "view": "events", "source": "environment action results", "events": selected,
            "available_turn_range": [turns[0], turns[-1]] if turns else None,
            "total_matching": len(matching), "truncated": len(matching) > len(selected)}}

    def recent_history(self) -> dict[str, Any]:
        with self._lock:
            return {"view": "events", "source": "environment action results",
                    "events": self._events[-RECOVERY_HISTORY_EVENTS:],
                    "total_events": len(self._events)}

    # -- checkpoints and recovery (upstream, minus RESET) ---------------------------------

    def request_compact_checkpoint(self, *, reason: str) -> bool:
        """Ask for an agent-authored checkpoint at the next opportunity. False when one
        is already pending or being delivered (nothing to do)."""
        with self._lock:
            if self.terminal:
                return False
            if self.compact_restore_marker.exists() or self.compact_checkpoint_marker.exists():
                return False
            if self.compact_checkpoint_ready.exists():
                return False
            self.compact_checkpoint_marker.parent.mkdir(parents=True, exist_ok=True)
            self.compact_checkpoint_marker.touch(mode=0o600, exist_ok=True)
            self.checkpoint_reasons.append(reason)
            append_jsonl(self.recovery_log_path, {"turn": self.turn, "action_applied": False,
                                                  "delivery": "checkpoint_requested",
                                                  "reason": reason})
            return True

    def checkpoint_pending(self) -> bool:
        return self.compact_checkpoint_marker.exists()

    def _save_compact_checkpoint(self, arguments: object) -> dict[str, Any]:
        with self._lock:
            if not self.compact_checkpoint_marker.exists():
                return {"ok": False, "metadata": {"error": "No compact checkpoint is pending."}}
            if self.compact_checkpoint_ready.exists():
                if not self.working_path.is_file():
                    return {"ok": False, "metadata": {"error": "Compact checkpoint is incomplete."}}
                return {"ok": True, "metadata": {"checkpoint_saved": True, "already_saved": True}}
            if not isinstance(arguments, dict) or set(arguments) != {"guide", "working_memory"}:
                return {"ok": False, "metadata": {"error": "Invalid arguments."}}
            guide, working = arguments.get("guide"), arguments.get("working_memory")
            if guide is not None and (not isinstance(guide, str) or not guide.strip()
                                      or len(guide) > MAX_GUIDE_CHARS):
                return {"ok": False, "metadata": {"error": "Invalid GUIDE.md content."}}
            if not isinstance(working, str) or not working.strip() or len(working) > MAX_WORKING_CHARS:
                return {"ok": False, "metadata": {"error": "Invalid WORKING.md content."}}
            try:
                if guide is not None:
                    atomic_write_text(self.guide_path, guide.strip() + "\n")
                self.working_provenance_path.unlink(missing_ok=True)
                atomic_write_text(self.working_path, working.strip() + "\n")
                self._record_working_provenance()
                self.compact_checkpoint_ready.parent.mkdir(parents=True, exist_ok=True)
                self.compact_checkpoint_ready.touch(mode=0o600)
            except OSError:
                return {"ok": False, "metadata": {"error": "Compact checkpoint could not be saved."}}
            return {"ok": True, "metadata": {
                "checkpoint_saved": True, "guide_updated": guide is not None,
                "guide_chars": len(guide.strip()) if guide is not None else 0,
                "working_chars": len(working.strip())}}

    def _notes(self) -> tuple[str | None, str | None]:
        guide = self.guide_path.read_text(encoding="utf-8", errors="replace") if self.guide_path.is_file() else None
        working = self.working_path.read_text(encoding="utf-8", errors="replace") if self.working_path.is_file() else None
        return guide, working

    def begin_compact_recovery(self) -> CompactRecovery:
        with self._lock:
            try:
                for p in (self.compact_checkpoint_marker, self.compact_checkpoint_ready,
                          self.working_path, self.guide_path):
                    if not p.is_file():
                        raise RuntimeError("Compact checkpoint data is incomplete.")
                guide, working = self._notes()
                if not (guide or "").strip() or not (working or "").strip():
                    raise RuntimeError("Compact checkpoint data is empty.")
                assert guide is not None and working is not None
                atomic_write_text(self.compact_guide_snapshot, guide)
                self.compact_restore_marker.parent.mkdir(parents=True, exist_ok=True)
                self.compact_restore_marker.touch(mode=0o600)
                present, _ = self.bridge.present()
                images = tuple(self.initial_image_paths())
                return CompactRecovery(
                    guide=guide, working_memory=working,
                    current_observation=self._metadata(action_applied=False, present=present),
                    last_action_result=dict(self._last_result) if self._last_result else None,
                    objective_history=self.recent_history(), image_paths=images,
                    reason=self.checkpoint_reasons[-1] if self.checkpoint_reasons else "")
            except (OSError, RuntimeError) as exc:
                self.forced_termination_reason = "compact_recovery_failed"
                append_jsonl(self.recovery_log_path, {"turn": self.turn, "action_applied": False,
                                                      "delivery": "prepare", "error": str(exc)})
                raise RuntimeError("Compact recovery data is unavailable.") from exc

    def complete_compact_recovery(self, recovery: CompactRecovery, *, delivery: str = "fresh_thread") -> None:
        with self._lock:
            try:
                if (not self.compact_restore_marker.is_file() or not self.compact_guide_snapshot.is_file()
                        or not self.working_path.is_file()):
                    raise RuntimeError("Compact recovery is no longer pending.")
                guide = self.compact_guide_snapshot.read_text(encoding="utf-8", errors="replace")
                working = self.working_path.read_text(encoding="utf-8", errors="replace")
                if guide != recovery.guide or working != recovery.working_memory:
                    raise RuntimeError("Compact recovery data changed before delivery.")
                append_jsonl(self.recovery_log_path, {
                    "turn": self.turn, "action_applied": False, "delivery": delivery,
                    "reason": recovery.reason, "guide_chars": len(guide), "working_chars": len(working)})
                self._clear_compact_recovery_files()
            except (OSError, RuntimeError) as exc:
                self.forced_termination_reason = "compact_recovery_failed"
                raise RuntimeError("Compact recovery could not be completed.") from exc

    def discard_compact_recovery(self) -> None:
        with self._lock:
            self._clear_compact_recovery_files()

    def _clear_compact_recovery_files(self) -> None:
        for p in (self.compact_guide_snapshot, self.compact_restore_marker,
                  self.compact_checkpoint_ready, self.compact_checkpoint_marker):
            p.unlink(missing_ok=True)

    def begin_runtime_recovery(self) -> RuntimeRecovery:
        with self._lock:
            if self.terminal:
                raise RuntimeError("Cannot recover a terminal episode.")
            guide, working = self._notes()
            present, _ = self.bridge.present()
            return RuntimeRecovery(
                boundary_turn=self.turn, guide=guide, working_memory=working,
                current_observation=self._metadata(action_applied=False, present=present),
                last_action_result=dict(self._last_result) if self._last_result else None,
                objective_history=self.recent_history(),
                image_paths=tuple(self.initial_image_paths()))

    def complete_runtime_recovery(self, recovery: RuntimeRecovery, *, delivery: str) -> None:
        with self._lock:
            if self.terminal or recovery.boundary_turn != self.turn:
                raise RuntimeError("Runtime recovery is no longer current.")
            append_jsonl(self.recovery_log_path, {"turn": self.turn, "action_applied": False,
                                                  "delivery": delivery})

    def record_working_write(self) -> None:
        with self._lock:
            self._record_working_provenance()

    def _record_working_provenance(self) -> None:
        atomic_write_text(self.working_provenance_path,
                          json.dumps({"turn": self.turn}, separators=(",", ":")) + "\n")

    def audit(self) -> dict[str, Any]:
        with self._lock:
            reasons: dict[str, int] = {}
            for r in self.checkpoint_reasons:
                reasons[r] = reasons.get(r, 0) + 1
            return {"turns": self.turn, "play_attempts": self.total_attempts,
                    "invalid_plays": self.invalid_plays, "events": len(self._events),
                    "checkpoints": len(self.checkpoint_reasons), "checkpoint_reasons": reasons,
                    "frames_archived": self.archive.frames_written,
                    "frames_bytes": self.archive.bytes_written,
                    "termination_reason": self.termination_reason}
