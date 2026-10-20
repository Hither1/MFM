"""One codex app-server thread driving the tools (upstream `DockerCodexRunner`).

The model runs in `codex app-server --stdio`, one long thread, with the game tools as
dynamic tools and nothing else -- no shell, no code mode, no apps, no web -- which is
VISTA's memory claim made operational: the conversation, the frame archive behind
`inspect`, and two notes files are all the model has. Frames reach the thread as
images steered into the running turn (`turn/steer`) right after the tool's text
response, and `inspect` results as a fresh user turn after the current one is
interrupted, exactly as upstream does it, because a tool result cannot carry an image.

Differences from upstream: the codex binary is local (`$CODEX_BIN`, or `codex` on PATH;
the bubblewrap wrapper of either benchmark works too, since it passes its arguments
through), the codex home is the arm's own, and the runner counts the image bytes it
has sent into the current thread: past `thread_bytes_budget` it requests the same
checkpoint handoff the PreCompact hook requests (see the package docstring).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mfm.backend.codex_turn import resolve_codex_bin
from mfm.vista.controller import write_json
from mfm.vista.dispatcher import GameToolDispatcher, ToolExecution
from mfm.vista.recovery import (CompactRecovery, RuntimeRecovery, compact_recovery_prompt,
                                fresh_runtime_recovery_prompt, runtime_recovery_prompt)

logger = logging.getLogger(__name__)

APP_SERVER_CLIENT_NAME = "mfm_vista"
PLAYER_TOOL_NAMESPACE = "game"
COMPACT_HOOK_EVENTS = frozenset({"preCompact"})
#: The context window codex believes gpt-5.x has (upstream's default) and where the
#: checkpoint is asked for relative to it: a hard reserve for the checkpoint turn, and
#: headroom before that for the normal auto-compact limit.
DEFAULT_MODEL_CONTEXT_WINDOW = 272_000
FALLBACK_MODEL_CONTEXT_WINDOW = 128_000
DEFAULT_CONTEXT_MODEL_PREFIXES = ("gpt-5.4", "gpt-5.5", "gpt-5.6", "gpt-6")
CHECKPOINT_HARD_CONTEXT_RESERVE = 32_000
CHECKPOINT_TURN_HEADROOM = 40_000
MIN_NORMAL_AUTO_COMPACT_LIMIT = 16_000
#: Base64 bytes of images sent into one thread before the wire-side checkpoint (see the
#: package docstring). 4 MB: the stall was measured between 5.15 and 6.15 MB.
DEFAULT_THREAD_BYTES_BUDGET = 4_000_000
#: Seconds of app-server silence (no message at all) before a segment is abandoned and
#: the thread resumed. The model's own turn is silent while it reasons; 900 s is what
#: the KiCad memory arms give one codex call.
DEFAULT_IDLE_TIMEOUT = 900


@dataclass
class CodexUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0

    def add(self, raw: dict[str, Any]) -> "CodexUsage":
        return CodexUsage(
            self.input_tokens + int(raw.get("inputTokens", 0)),
            self.cached_input_tokens + int(raw.get("cachedInputTokens", 0)),
            self.output_tokens + int(raw.get("outputTokens", 0)),
            self.reasoning_output_tokens + int(raw.get("reasoningOutputTokens", 0)))


@dataclass(frozen=True)
class CompactThresholds:
    model_context_window: int
    normal_auto_compact_limit: int
    checkpoint_auto_compact_limit: int
    source: str


def compact_thresholds_for_context(context_window: int, *, source: str) -> CompactThresholds:
    checkpoint_limit = context_window - CHECKPOINT_HARD_CONTEXT_RESERVE
    normal_limit = checkpoint_limit - CHECKPOINT_TURN_HEADROOM
    if normal_limit < MIN_NORMAL_AUTO_COMPACT_LIMIT:
        raise ValueError(f"Model context window {context_window} is too small for compact checkpointing")
    return CompactThresholds(context_window, normal_limit, checkpoint_limit, source)


def resolve_compact_thresholds(model: str | None, *, codex_home: Path | None = None) -> CompactThresholds:
    catalog = (codex_home or Path.home() / ".codex") / "models_cache.json"
    if model:
        try:
            models = json.loads(catalog.read_text(encoding="utf-8")).get("models", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            models = []
        for entry in models:
            if isinstance(entry, dict) and entry.get("slug") == model:
                window = entry.get("context_window")
                if isinstance(window, int) and not isinstance(window, bool):
                    return compact_thresholds_for_context(window, source="codex-model-catalog")
        if model.startswith(DEFAULT_CONTEXT_MODEL_PREFIXES):
            return compact_thresholds_for_context(DEFAULT_MODEL_CONTEXT_WINDOW, source="known-model-family")
    return compact_thresholds_for_context(FALLBACK_MODEL_CONTEXT_WINDOW, source="conservative-fallback")


@dataclass(frozen=True)
class CodexResult:
    segment: int
    returncode: int
    final_message: str
    session_id: str | None
    stdout_path: Path
    stderr_path: Path
    requests_path: Path
    usage: CodexUsage | None
    kind: str


def prepare_codex_home(home: Path) -> Path:
    """The arm's codex home: sessions and the system-skills marker (no skills injected),
    like the benchmarks' wrappers seed theirs. Auth is the launcher's business."""
    from mfm.backend.codex_turn import ensure_system_skills_marker

    home = Path(home)
    (home / "sessions").mkdir(parents=True, exist_ok=True)
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    # Shared with the backend: the launcher may already have put a FILE at
    # skills/.system, and mkdir on a file is what took one run down.
    ensure_system_skills_marker(home)
    return home


def provider_config(base_url: str | None) -> tuple[list[str], list[str]]:
    """The --base-url provider for the app-server thread: (top-level lines, tables).

    The twin of codex_backend's `-c` set on the exec arms (MCU mcu_worldmodel/codex_backend.py:
    model_provider=local, name/base_url/wire_api="responses", provider_auth_args,
    _metadata_args), written into config.toml because app-server takes no -c. The key
    travels as codex's `auth.command` from CODEX_LOCAL_AUTH_COMMAND (a JSON list), so it
    is never in any process's environment; without it, `env_key` LOCAL_API_KEY as on a
    local server. CODEX_MODEL_CONTEXT_WINDOW names the window of a model codex has never
    heard of. The auto-compaction limit stays the runner's own: unlike the exec arms,
    this arm WANTS compaction -- the PreCompact hook is its checkpoint handoff.
    Without a base_url nothing is added, byte for byte."""
    if not base_url:
        return [], []
    top = ['model_provider = "local"']
    window = os.environ.get("CODEX_MODEL_CONTEXT_WINDOW", "").strip()
    if window:
        top.append(f"model_context_window = {int(window)}")
    tables = ["[model_providers.local]", 'name = "local"', f'base_url = "{base_url}"',
              'wire_api = "responses"']
    raw = os.environ.get("CODEX_LOCAL_AUTH_COMMAND", "").strip()
    if raw:
        cmd = json.loads(raw)
        if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
            raise ValueError("CODEX_LOCAL_AUTH_COMMAND must be a JSON list of strings")
        tables += ["", "[model_providers.local.auth]", f"command = {json.dumps(cmd[0])}",
                   f"args = {json.dumps(cmd[1:])}"]
    else:
        tables.append('env_key = "LOCAL_API_KEY"')
    return top, tables + [""]


def write_codex_config(codex_home: Path, workspace: Path, normal_auto_compact_limit: int,
                       base_instructions: str, base_url: str | None = None) -> Path:
    """The complete player-local codex configuration (upstream's, with the paths ours).

    Every generic capability is off: the model's tool list is the dynamic namespace and
    nothing else. `hooks = true` is what makes the PreCompact hook run."""
    instructions = codex_home / "player_instructions.md"
    instructions.write_text(base_instructions, encoding="utf-8")
    provider_top, provider_tables = provider_config(base_url)
    config = codex_home / "config.toml"
    config.write_text("\n".join([
        f'model_instructions_file = "{instructions}"',
        f"model_auto_compact_token_limit = {normal_auto_compact_limit}",
        'model_auto_compact_token_limit_scope = "total"',
        'personality = "none"',
        'web_search = "disabled"',
        *provider_top,
        "",
        f'[projects."{workspace}"]',
        'trust_level = "trusted"',
        "",
        "[agents]",
        "interrupt_message = false",
        "",
        "[skills]",
        "include_instructions = false",
        "",
        "[skills.bundled]",
        "enabled = false",
        "",
        "[features]",
        "apps = false",
        "browser_use = false",
        "computer_use = false",
        "code_mode_host = true",
        "goals = false",
        "hooks = true",
        "image_generation = false",
        "multi_agent = false",
        "plugins = false",
        "remote_plugin = false",
        "shell_snapshot = false",
        "shell_tool = false",
        "tool_suggest = false",
        "unified_exec = false",
        "",
        "[features.code_mode]",
        "enabled = false",
        f'direct_only_tool_namespaces = ["{PLAYER_TOOL_NAMESPACE}"]',
        "",
        *provider_tables,
    ]), encoding="utf-8")
    return config


def write_compact_hook(workspace: Path, codex_home: Path) -> None:
    """The PreCompact hook: touch the checkpoint marker and stop the turn, so the
    segment loop asks for the checkpoint and hands off to a fresh thread."""
    codex_dir = workspace / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    write_json(codex_home / "hooks.json", {"hooks": {"PreCompact": [{
        "matcher": "auto|manual",
        "hooks": [{"type": "command", "command": "sh .codex/pre_compact_checkpoint.sh",
                   "statusMessage": "Saving checkpoint"}]}]}})
    script = codex_dir / "pre_compact_checkpoint.sh"
    script.write_text("\n".join([
        "#!/bin/sh", "set -eu", "umask 077", "cat >/dev/null",
        'request="$CODEX_HOME/compact_checkpoint.requested"',
        ': > "$request"',
        "printf '%s\\n' '{\"continue\":false,\"stopReason\":\"Save the compact checkpoint before continuing.\"}'",
        "",
    ]), encoding="utf-8")
    script.chmod(0o555)


class _AppServerConnection:
    def __init__(self, process: subprocess.Popen, *, stdout_path: Path, stderr_path: Path,
                 requests_path: Path) -> None:
        self.process = process
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("app-server pipes are unavailable")
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._requests = requests_path.open("a", encoding="utf-8")
        threading.Thread(target=self._read_stdout, args=(process.stdout, stdout_path), daemon=True).start()
        threading.Thread(target=self._copy_stream, args=(process.stderr, stderr_path), daemon=True).start()

    def _read_stdout(self, stream: Any, path: Path) -> None:
        with path.open("a", encoding="utf-8") as sink:
            for line in stream:
                sink.write(_sanitize(line) if "data:image/" in line else line)
                sink.flush()
                self._queue.put(line)
        self._queue.put(None)

    @staticmethod
    def _copy_stream(stream: Any, path: Path) -> None:
        with path.open("a", encoding="utf-8") as sink:
            for line in stream:
                sink.write(line)
                sink.flush()

    def send(self, message: dict[str, Any]) -> None:
        text = json.dumps(message, separators=(",", ":"))
        self._requests.write(json.dumps(_sanitize_message(message), separators=(",", ":")) + "\n")
        self._requests.flush()
        assert self.process.stdin is not None
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def receive(self, deadline: float, idle_timeout: float | None) -> dict[str, Any]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex app-server turn timed out")
            wait = remaining if idle_timeout is None else min(remaining, idle_timeout)
            try:
                line = self._queue.get(timeout=wait)
            except queue.Empty as exc:
                if idle_timeout is not None and remaining > idle_timeout:
                    raise TimeoutError(f"Codex app-server was silent for {idle_timeout:.0f}s") from exc
                raise TimeoutError("Codex app-server turn timed out") from exc
            if line is None:
                raise RuntimeError(f"Codex app-server exited before the turn completed "
                                   f"(returncode={self.process.poll()})")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Codex app-server emitted invalid JSON") from exc
            if not isinstance(message, dict):
                raise RuntimeError("Codex app-server emitted a non-object message")
            return message

    def close(self) -> int:
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except OSError:
            pass
        try:
            return self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                return self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                return self.process.wait()
        finally:
            self._requests.close()


def _sanitize(line: str) -> str:
    try:
        return json.dumps(_sanitize_message(json.loads(line)), separators=(",", ":")) + "\n"
    except (json.JSONDecodeError, TypeError):
        return line


def _sanitize_message(value: Any) -> Any:
    """Image payloads out of the transcripts: a sha256 and a byte count instead."""
    if isinstance(value, dict):
        return {k: _sanitize_message(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_message(v) for v in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        header, sep, payload = value.partition(",")
        if sep:
            try:
                raw = base64.b64decode(payload, validate=True)
            except ValueError:
                raw = payload.encode("ascii", errors="replace")
            return f"<{header};bytes={len(raw)};sha256={hashlib.sha256(raw).hexdigest()}>"
    return value


class AppServerRunner:
    def __init__(self, *, workspace: Path, codex_home: Path, io_dir: Path, controller: Any,
                 tools: tuple[dict[str, Any], ...], base_instructions: str,
                 developer_instructions: str, model: str | None,
                 reasoning_effort: str | None, codex_bin: str | None = None,
                 base_url: str | None = None,
                 compact_thresholds: CompactThresholds | None = None,
                 task_timeout: float = 3 * 24 * 3600,
                 idle_timeout: float | None = DEFAULT_IDLE_TIMEOUT,
                 thread_bytes_budget: int | None = DEFAULT_THREAD_BYTES_BUDGET,
                 objective: str = "Continue the task.",
                 model_step_limit: int | None = None,
                 play_limit: int | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.guide_path = self.workspace / "GUIDE.md"
        self.working_path = self.workspace / "WORKING.md"
        self.codex_home = Path(codex_home).resolve()
        self.io_dir = Path(io_dir).resolve()
        self.io_dir.mkdir(parents=True, exist_ok=True)
        self.controller = controller
        self.tools = tuple(tools)
        self.base_instructions = base_instructions
        self.developer_instructions = developer_instructions
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.codex_bin = resolve_codex_bin(codex_bin or os.environ.get("CODEX_BIN", "codex"))
        self.base_url = base_url or None
        self.compact_thresholds = compact_thresholds or resolve_compact_thresholds(
            model, codex_home=self.codex_home)
        self.task_timeout = task_timeout
        self.idle_timeout = idle_timeout
        self.thread_bytes_budget = thread_bytes_budget
        self.objective = objective
        self.dispatcher = GameToolDispatcher(controller=controller, guide_path=self.guide_path,
                                             working_path=self.working_path)
        prepare_codex_home(self.codex_home)
        write_codex_config(self.codex_home, self.workspace,
                           self.compact_thresholds.normal_auto_compact_limit, base_instructions,
                           base_url=self.base_url)
        write_compact_hook(self.workspace, self.codex_home)
        self._segment_index = 0
        self._rpc_id = 0
        self._connection: _AppServerConnection | None = None
        self._pending: dict[Any, dict[str, Any]] = {}
        self._active_thread_id: str | None = None
        self._active_turn_id: str | None = None
        self._completed_turn: dict[str, Any] | None = None
        self._awaited_tool_call: str | None = None
        self._completed_tool_call: str | None = None
        self._final_message = ""
        self._segment_usage: CodexUsage | None = None
        #: The last agent message seen in the thread (the model's stated expectation
        #: before a play, its reading after one); the benchmark logs it as the briefing.
        self.last_agent_message = ""
        self.thread_bytes: dict[str, int] = {}
        self.peak_thread_bytes = 0
        self.wire_checkpoints = 0
        #: `model_steps()`: turns that ended in the model's answer (an interrupted turn
        #: ended after a tool call, which is counted already), and the cap past which a
        #: tool call is refused and the episode goes on without the model.
        self.turns_answered = 0
        self.model_step_limit = model_step_limit
        #: `--turn-budget`: plays (the vista arm's turns) past which a play is refused.
        self.play_limit = play_limit
        self.images_sent = 0
        self.segments: list[CodexResult] = []

    # -- segments -------------------------------------------------------------------

    def run_task(self, prompt: str, images: tuple[Path, ...]) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=None,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=images, kind="task")

    def run_recovery_task(self, recovery: CompactRecovery) -> CodexResult:
        return self._run_segment(prompt=compact_recovery_prompt(recovery, self.objective),
                                 session_id=None,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=recovery.image_paths, recovery=recovery,
                                 kind="compact_recovery")

    def resume_recovery_task(self, session_id: str, recovery: CompactRecovery) -> CodexResult:
        return self._run_segment(prompt=compact_recovery_prompt(recovery, self.objective),
                                 session_id=session_id,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=recovery.image_paths, recovery=recovery,
                                 kind="compact_recovery_resumed")

    def resume_runtime_recovery(self, session_id: str, recovery: RuntimeRecovery) -> CodexResult:
        return self._run_segment(prompt=runtime_recovery_prompt(recovery, self.objective),
                                 session_id=session_id,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=recovery.image_paths, runtime_recovery=recovery,
                                 kind="runtime_recovery")

    def run_fresh_runtime_recovery(self, recovery: RuntimeRecovery) -> CodexResult:
        return self._run_segment(prompt=fresh_runtime_recovery_prompt(recovery, self.objective),
                                 session_id=None,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=recovery.image_paths, runtime_recovery=recovery,
                                 fresh_delivery=True, kind="fresh_runtime_recovery")

    def resume_checkpoint(self, session_id: str, prompt: str) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=session_id,
                                 compact_limit=self.compact_thresholds.checkpoint_auto_compact_limit,
                                 initial_images=(), kind="checkpoint")

    def resume_nonterminal_task(self, session_id: str, prompt: str) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=session_id,
                                 compact_limit=self.compact_thresholds.normal_auto_compact_limit,
                                 initial_images=(), kind="continuation")

    def _next_segment(self) -> int:
        self._segment_index += 1
        return self._segment_index

    def _command(self) -> list[str]:
        return [self.codex_bin, "app-server", "--stdio", "--strict-config"]

    def _run_segment(self, *, prompt: str, session_id: str | None, compact_limit: int,
                     initial_images: Any, recovery: CompactRecovery | None = None,
                     runtime_recovery: RuntimeRecovery | None = None,
                     fresh_delivery: bool = False, kind: str) -> CodexResult:
        segment = self._next_segment()
        stem = f"segment_{segment:03d}"
        stdout_path = self.io_dir / f"{stem}.stdout.jsonl"
        stderr_path = self.io_dir / f"{stem}.stderr.txt"
        requests_path = self.io_dir / f"{stem}.requests.jsonl"
        (self.io_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
        write_codex_config(self.codex_home, self.workspace, compact_limit, self.base_instructions,
                           base_url=self.base_url)
        command = self._command()
        write_json(self.io_dir / f"{stem}.command.json", {"argv": command, "kind": kind,
                                                            "session_id": session_id})
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)
        env.setdefault("LOCAL_API_KEY", "EMPTY")
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(command, cwd=self.workspace, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       bufsize=1)
            connection = _AppServerConnection(process, stdout_path=stdout_path,
                                              stderr_path=stderr_path, requests_path=requests_path)
        except Exception as exc:
            if process is not None:
                process.kill()
            stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            result = CodexResult(segment, 125, "", session_id, stdout_path, stderr_path,
                                 requests_path, None, kind)
            self.segments.append(result)
            return result
        self._connection = connection
        self._pending = {}
        self._active_thread_id = None
        self._active_turn_id = None
        self._completed_turn = None
        self._awaited_tool_call = None
        self._completed_tool_call = None
        self._final_message = ""
        self._segment_usage = None
        deadline = time.monotonic() + self.task_timeout
        returncode, error_text, resolved = 0, "", session_id
        try:
            self._rpc("initialize", {"clientInfo": {"name": APP_SERVER_CLIENT_NAME,
                                                    "title": "MFM VISTA harness", "version": "1.0.0"},
                                     "capabilities": {"experimentalApi": True}}, deadline)
            connection.send({"method": "initialized", "params": {}})
            self._ensure_compact_hooks_trusted(deadline)
            common = self._thread_parameters(compact_limit)
            if session_id is None:
                common["environments"] = []
                common["dynamicTools"] = self._dynamic_tools()
                thread_result = self._rpc("thread/start", common, deadline)
            else:
                thread_result = self._rpc("thread/resume", {"threadId": session_id, "excludeTurns": True,
                                                            **common}, deadline)
            thread = thread_result.get("thread")
            if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
                raise RuntimeError("app-server returned no thread id")
            self._active_thread_id = thread["id"]
            resolved = self._active_thread_id
            self.thread_bytes.setdefault(self._active_thread_id, 0)
            turn_input: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for image_path in initial_images:
                turn_input.append(self._image_input(Path(image_path).read_bytes()))
            turn_params: dict[str, Any] = {"threadId": self._active_thread_id, "input": turn_input}
            if self.model:
                turn_params["model"] = self.model
            if self.reasoning_effort:
                turn_params["effort"] = self.reasoning_effort
            turn = self._rpc("turn/start", turn_params, deadline).get("turn")
            if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
                raise RuntimeError("app-server returned no turn id")
            self._active_turn_id = turn["id"]
            if recovery is not None:
                self.controller.complete_compact_recovery(recovery)
            if runtime_recovery is not None:
                self.controller.complete_runtime_recovery(
                    runtime_recovery,
                    delivery="fresh_runtime_thread" if fresh_delivery else "resumed_runtime_thread")
            while self._completed_turn is None:
                self._dispatch(connection.receive(deadline, self.idle_timeout), deadline)
            status = self._completed_turn.get("status")
            paused = self.controller.compact_checkpoint_marker.exists()
            # A turn the API refused (rate limit, capacity) is a runtime failure even while
            # a checkpoint is pending: counted as a checkpoint attempt, four refusals in a
            # row ended a life ("Codex did not write the compact checkpoint", all 429s).
            api_error = (status == "failed" and isinstance(self._completed_turn.get("error"), dict)
                         and bool(self._completed_turn["error"].get("codexErrorInfo")))
            if status not in {"completed", "interrupted"} and (not paused or api_error):
                returncode = 1
                error_text = f"Turn ended with status {status}: {self._completed_turn.get('error')}"
        except TimeoutError as exc:
            returncode, error_text = 124, str(exc)
        except Exception as exc:
            returncode, error_text = 1, f"{type(exc).__name__}: {exc}"
        finally:
            rc = connection.close()
            self._connection = None
            if returncode == 0 and rc not in (0, None):
                returncode = rc
            if error_text:
                with stderr_path.open("a", encoding="utf-8") as f:
                    f.write(error_text + "\n")
                logger.warning("[vista] segment %d (%s) ended: %s", segment, kind, error_text)
        result = CodexResult(segment, returncode, self._final_message, resolved, stdout_path,
                             stderr_path, requests_path, self._segment_usage, kind)
        self.segments.append(result)
        return result

    def _thread_parameters(self, compact_limit: int) -> dict[str, Any]:
        config: dict[str, Any] = {"model_auto_compact_token_limit": compact_limit}
        if self.reasoning_effort:
            config["model_reasoning_effort"] = self.reasoning_effort
        common: dict[str, Any] = {
            "cwd": str(self.workspace), "approvalPolicy": "never", "sandbox": "workspace-write",
            "baseInstructions": self.base_instructions,
            "developerInstructions": self.developer_instructions,
            "personality": "none", "config": config}
        if self.model:
            common["model"] = self.model
        return common

    def _dynamic_tools(self) -> list[dict[str, Any]]:
        return [{"type": "namespace", "name": PLAYER_TOOL_NAMESPACE,
                 "description": "Environment tools.",
                 "tools": [{"type": "function", "name": t["name"], "description": t["description"],
                            "inputSchema": t["inputSchema"]} for t in self.tools]}]

    # -- the hook trust dance (upstream) ------------------------------------------------

    def _ensure_compact_hooks_trusted(self, deadline: float) -> None:
        hooks = self._compact_hooks(self._rpc("hooks/list", {"cwds": [str(self.workspace)]}, deadline))
        untrusted = {h["key"]: {"trusted_hash": h["currentHash"]} for h in hooks.values()
                     if h.get("trustStatus") not in {"trusted", "managed"}}
        if untrusted:
            self._rpc("config/batchWrite", {"edits": [{"keyPath": "hooks.state", "value": untrusted,
                                                        "mergeStrategy": "upsert"}],
                                             "reloadUserConfig": True}, deadline)
            hooks = self._compact_hooks(self._rpc("hooks/list", {"cwds": [str(self.workspace)]}, deadline))
        invalid = {e: h.get("trustStatus") for e, h in hooks.items()
                   if not h.get("enabled") or h.get("trustStatus") not in {"trusted", "managed"}}
        if invalid:
            raise RuntimeError(f"Compact hooks are not trusted and enabled: {invalid}")

    def _compact_hooks(self, result: dict[str, Any]) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        source = str(self.codex_home / "hooks.json")
        for entry in result.get("data") or []:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks") or []:
                if (isinstance(hook, dict) and hook.get("eventName") in COMPACT_HOOK_EVENTS
                        and hook.get("sourcePath") == source and isinstance(hook.get("key"), str)
                        and isinstance(hook.get("currentHash"), str)):
                    found[hook["eventName"]] = hook
        missing = COMPACT_HOOK_EVENTS.difference(found)
        if missing:
            raise RuntimeError(f"Required compact hooks were not discovered: {sorted(missing)}")
        return found

    # -- the wire ----------------------------------------------------------------------

    def _next_rpc_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _rpc(self, method: str, params: dict[str, Any], deadline: float) -> dict[str, Any]:
        if self._connection is None:
            raise RuntimeError("app-server is not running")
        request_id = self._next_rpc_id()
        self._connection.send({"id": request_id, "method": method, "params": params})
        while request_id not in self._pending:
            self._dispatch(self._connection.receive(deadline, self.idle_timeout), deadline)
        response = self._pending.pop(request_id)
        if "error" in response:
            raise RuntimeError(f"{method} failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"{method} returned no result object")
        return result

    def _dispatch(self, message: dict[str, Any], deadline: float) -> None:
        method, request_id = message.get("method"), message.get("id")
        if isinstance(method, str) and request_id is not None:
            if method == "item/tool/call":
                self._handle_tool_call(message, deadline)
            elif self._connection is not None:
                self._connection.send({"id": request_id,
                                       "error": {"code": -32601, "message": "Unsupported request"}})
            return
        if method is None and request_id is not None:
            self._pending[request_id] = message
            return
        if isinstance(method, str):
            self._observe(method, message.get("params"))

    def _observe(self, method: str, params: Any) -> None:
        if not isinstance(params, dict):
            return
        if method == "turn/started":
            turn = params.get("turn")
            if (self._active_turn_id is None and params.get("threadId") == self._active_thread_id
                    and isinstance(turn, dict) and isinstance(turn.get("id"), str)):
                self._active_turn_id = turn["id"]
        elif method == "turn/completed":
            turn = params.get("turn")
            if isinstance(turn, dict) and turn.get("id") == self._active_turn_id:
                self._completed_turn = turn
                if turn.get("status") == "completed":
                    self.turns_answered += 1
        elif method == "item/completed":
            item = params.get("item")
            if isinstance(item, dict):
                if item.get("type") == "dynamicToolCall":
                    if item.get("id") == self._awaited_tool_call:
                        self._completed_tool_call = item.get("id")
                elif item.get("type") == "agentMessage" and isinstance(item.get("text"), str):
                    self._final_message = item["text"]
                    self.last_agent_message = item["text"]
        elif method == "thread/tokenUsage/updated":
            usage = params.get("tokenUsage")
            if (params.get("turnId") == self._active_turn_id and isinstance(usage, dict)
                    and isinstance(usage.get("last"), dict)):
                self._segment_usage = (self._segment_usage or CodexUsage()).add(usage["last"])

    def _handle_tool_call(self, message: dict[str, Any], deadline: float) -> None:
        if self._connection is None:
            raise RuntimeError("app-server is not running")
        request_id, params = message.get("id"), message.get("params")
        if not isinstance(params, dict):
            self._connection.send(self._tool_response(request_id, ToolExecution("Invalid tool request.", False)))
            return
        tool, namespace, call_id, arguments = (params.get("tool"), params.get("namespace"),
                                               params.get("callId"), params.get("arguments"))
        if namespace != PLAYER_TOOL_NAMESPACE or not isinstance(tool, str) or not isinstance(call_id, str):
            execution = ToolExecution("Invalid tool request.", False)
        elif self._spent_budget(tool) is not None:
            # A budget is spent: no further tool runs, and the episode is over for the
            # model (the chassis plays the rest of it idle).
            name, cap = self._spent_budget(tool)
            self.controller.force_terminal(name)
            execution = ToolExecution(
                f"The {name.replace('_', ' ')} ({cap}) is spent: this call was not run, and the "
                f"rest of the life goes on without you.", False,
                interrupt_after=True, boundary_reason=name)
        else:
            execution = self.dispatcher.execute(tool, arguments, call_id)
        if tool == "inspect" and execution.images:
            # The views go out as a fresh user turn once this turn is interrupted.
            self._awaited_tool_call = call_id
            self._connection.send(self._tool_response(request_id, execution))
            self._wait_for_tool_completion(call_id, deadline)
            self._start_inspection_turn(execution.images, deadline)
            return
        if execution.images:
            try:
                for index, image in enumerate(execution.images):
                    self._steer_visual(image, f"{call_id}-{index + 1}", deadline)
            except Exception:
                execution = ToolExecution("The resulting visual could not be delivered.", False)
            else:
                if (tool == "play" and self.thread_bytes_budget and self._active_thread_id
                        and self.thread_bytes.get(self._active_thread_id, 0) > self.thread_bytes_budget
                        and self.controller.request_compact_checkpoint(reason="thread_bytes")):
                    # The wire-side handoff: the same marker the hook touches, then
                    # the turn ends right after this response.
                    self.wire_checkpoints += 1
                    execution.interrupt_after = True
                    execution.boundary_reason = "thread_bytes"
        self._connection.send(self._tool_response(request_id, execution))
        if execution.interrupt_after:
            self._finish_turn_boundary(deadline)

    def _spent_budget(self, tool: str) -> tuple[str, int] | None:
        """The budget this call would overrun, as (name, cap), or None."""
        if self.model_step_limit is not None and self.model_steps() >= self.model_step_limit:
            return "model_step_budget", self.model_step_limit
        if (self.play_limit is not None and tool == "play"
                and self.dispatcher.calls.get("play", 0) >= self.play_limit):
            return "turn_budget", self.play_limit
        return None

    def model_steps(self) -> int:
        """Model steps spent: every tool call the model made and every turn it ended with
        its answer -- the unit `--model-step-budget` counts in every arm."""
        return sum(self.dispatcher.calls.values()) + self.turns_answered

    @staticmethod
    def _tool_response(request_id: Any, execution: ToolExecution) -> dict[str, Any]:
        return {"id": request_id, "result": {"contentItems": [{"type": "inputText", "text": execution.text}],
                                             "success": execution.success}}

    def _finish_turn_boundary(self, deadline: float) -> None:
        if self._active_thread_id is None or self._active_turn_id is None:
            raise RuntimeError("No active turn to interrupt")
        turn_id = self._active_turn_id
        try:
            self._rpc("turn/interrupt", {"threadId": self._active_thread_id, "turnId": turn_id}, deadline)
        except RuntimeError as exc:
            if "no active turn to interrupt" not in str(exc):
                raise
        self._wait_for_turn_completion(turn_id, deadline)

    def _wait_for_turn_completion(self, turn_id: str, deadline: float) -> None:
        if self._connection is None:
            raise RuntimeError("app-server is not running")
        while not isinstance(self._completed_turn, dict) or self._completed_turn.get("id") != turn_id:
            self._dispatch(self._connection.receive(deadline, self.idle_timeout), deadline)

    def _wait_for_tool_completion(self, call_id: str, deadline: float) -> None:
        if self._connection is None:
            raise RuntimeError("app-server is not running")
        while self._completed_tool_call != call_id:
            self._dispatch(self._connection.receive(deadline, self.idle_timeout), deadline)
        self._awaited_tool_call = None
        self._completed_tool_call = None

    def _count_bytes(self, data_b64: str) -> None:
        self.images_sent += 1
        if self._active_thread_id is not None:
            total = self.thread_bytes.get(self._active_thread_id, 0) + len(data_b64)
            self.thread_bytes[self._active_thread_id] = total
            self.peak_thread_bytes = max(self.peak_thread_bytes, total)

    def _image_input(self, png: bytes) -> dict[str, Any]:
        data = base64.b64encode(png).decode("ascii")
        self._count_bytes(data)
        return {"type": "image", "url": f"data:image/png;base64,{data}", "detail": "original"}

    def _start_inspection_turn(self, images: tuple[dict[str, Any], ...], deadline: float) -> None:
        if self._active_thread_id is None or self._active_turn_id is None:
            raise RuntimeError("No active turn for inspection")
        previous = self._active_turn_id
        self._rpc("turn/interrupt", {"threadId": self._active_thread_id, "turnId": previous}, deadline)
        while not isinstance(self._completed_turn, dict) or self._completed_turn.get("id") != previous:
            if self._connection is None:
                raise RuntimeError("app-server is not running")
            self._dispatch(self._connection.receive(deadline, self.idle_timeout), deadline)
        if self._completed_turn.get("status") not in {"interrupted", "completed"}:
            raise RuntimeError("Inspection turn boundary was not completed")
        turn_input: list[dict[str, Any]] = [{"type": "text", "text": (
            f'<inspection_visuals count="{len(images)}">Results of the completed inspect call '
            "follow in request order; the current state is unchanged.</inspection_visuals>")}]
        for image in images:
            data, steer_text = image.get("data"), image.get("steer_text")
            if not isinstance(data, str) or not isinstance(steer_text, str):
                raise RuntimeError("Controller returned incomplete inspection visual")
            self._count_bytes(data)
            turn_input.extend([{"type": "text", "text": steer_text},
                               {"type": "image", "url": f"data:{image.get('mime_type', 'image/png')};base64,{data}",
                                "detail": image.get("detail", "original")}])
        self._completed_turn = None
        self._active_turn_id = None
        self._final_message = ""
        turn_params: dict[str, Any] = {"threadId": self._active_thread_id, "input": turn_input}
        if self.model:
            turn_params["model"] = self.model
        if self.reasoning_effort:
            turn_params["effort"] = self.reasoning_effort
        turn = self._rpc("turn/start", turn_params, deadline).get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise RuntimeError("app-server returned no inspection turn id")
        self._active_turn_id = turn["id"]

    def _steer_visual(self, image: dict[str, Any], call_id: str, deadline: float) -> None:
        if self._active_thread_id is None or self._active_turn_id is None:
            raise RuntimeError("No active turn for the resulting visual")
        data, steer_text = image.get("data"), image.get("steer_text")
        if not isinstance(data, str):
            raise RuntimeError("Controller returned no visual data")
        if not isinstance(steer_text, str) or not steer_text:
            raise RuntimeError("Controller returned no visual identity")
        self._count_bytes(data)
        self._rpc("turn/steer", {
            "threadId": self._active_thread_id, "expectedTurnId": self._active_turn_id,
            "clientUserMessageId": f"visual-{call_id}",
            "input": [{"type": "text", "text": steer_text},
                      {"type": "image", "url": f"data:{image.get('mime_type', 'image/png')};base64,{data}",
                       "detail": image.get("detail", "original")}]}, deadline)

    def audit(self) -> dict[str, Any]:
        usage = CodexUsage()
        for s in self.segments:
            if s.usage:
                usage = CodexUsage(usage.input_tokens + s.usage.input_tokens,
                                   usage.cached_input_tokens + s.usage.cached_input_tokens,
                                   usage.output_tokens + s.usage.output_tokens,
                                   usage.reasoning_output_tokens + s.usage.reasoning_output_tokens)
        kinds: dict[str, int] = {}
        for s in self.segments:
            kinds[s.kind] = kinds.get(s.kind, 0) + 1
        return {"codex_bin": self.codex_bin, "base_url": self.base_url, "model": self.model,
                "effort": self.reasoning_effort,
                "compact_thresholds": self.compact_thresholds.__dict__,
                "thread_bytes_budget": self.thread_bytes_budget,
                "segments": len(self.segments), "segments_by_kind": kinds,
                "segments_failed": sum(1 for s in self.segments if s.returncode != 0),
                "threads": len(self.thread_bytes), "peak_thread_bytes": self.peak_thread_bytes,
                "images_sent": self.images_sent, "wire_checkpoints": self.wire_checkpoints,
                "tool_calls": dict(self.dispatcher.calls),
                "usage": usage.__dict__}
