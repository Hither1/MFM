"""VISTA on Claude Code: the app-server runner's surface on `claude -p` and MCP tools.

The codex runner (`runner.py`) drives one app-server thread whose dynamic tools are the
VISTA contract; frames reach the thread as steered images and inspection views as a
fresh turn, because a codex tool result cannot carry an image. Claude Code's MCP tool
results can (measured on 2.1.257, 2026-09-15), so this twin is simpler where the
protocol is concerned: the tools are an MCP server (`mcp_bridge.py`, spawned by the CLI,
forwarding every call to this runner over a unix socket), a play's result text and the
resulting frame go back in the same tool result, and an `inspect` returns its views the
same way.

What is kept one-for-one with the codex runner, so `session.py` runs unchanged:

  * one CLI process per segment: a fresh session (`--session-id <uuid>`) for a task or a
    compact / fresh recovery, `--resume <id>` for a checkpoint, a runtime recovery or a
    nonterminal continuation; the segment ends when the model ends its turn (the
    `result` event) or when this runner ends it (below);
  * the checkpoint handoff: past `thread_bytes_budget` of image bytes sent into the
    session, or past `context_token_limit` of context on the last model call (the twin
    of codex's auto-compact limit; Claude Code's own auto-compaction is off), a play
    result asks for the checkpoint (`controller.request_compact_checkpoint`) and the turn
    is interrupted right after it; the loop then resumes the session for the checkpoint
    and starts a fresh one from it. A saved checkpoint also interrupts the turn, so the
    handoff never waits for the model to stop talking;
  * `CodexResult` / `CodexUsage` / `audit()` shapes, `last_agent_message`, the
    per-segment transcript files (events, requests, prompt, stderr, command).

Isolation is the Claude Code arms' (prolong_search/claude_backend.py + claude_sandbox.sh):
a per-episode CLAUDE_CONFIG_DIR holding only the credential, a scrubbed environment (no
CLAUDE_* of the launching session, nothing that looks like a secret), `--tools ""` (no
built-in tool at all: the model has no shell and no filesystem, VISTA's premise),
`--strict-mcp-config` (only our server), `--setting-sources ""` + `--system-prompt` (no
CLAUDE.md, settings or skills of any account), auto-memory and auto-compaction off, and
the init event audited: the tool surface must be exactly our MCP tools and nothing else,
or the segment fails as a sandbox violation. Under the wrapper the CLI and the bridge run
in bwrap with the workspace and the config dir as the only writable paths and Anthropic
as the only route out; the runner's socket directory is bound in through
CLAUDE_SANDBOX_RW_BINDS.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from mfm.vista.controller import write_json
from mfm.vista.dispatcher import GameToolDispatcher, ToolExecution
from mfm.vista.recovery import (CompactRecovery, RuntimeRecovery, compact_recovery_prompt,
                                fresh_runtime_recovery_prompt, runtime_recovery_prompt)
from mfm.vista.runner import (DEFAULT_IDLE_TIMEOUT, DEFAULT_THREAD_BYTES_BUDGET,
                              PLAYER_TOOL_NAMESPACE, CodexResult, CodexUsage)

logger = logging.getLogger(__name__)

#: The MCP server name: the tools reach the model as `mcp__game__<name>`.
MCP_SERVER_NAME = PLAYER_TOOL_NAMESPACE
BRIDGE_SOURCE = Path(__file__).with_name("mcp_bridge.py")
WRAPPER_NAME = "claude_sandbox.sh"
#: Context tokens on the last model call past which the next play asks for the
#: checkpoint. Claude Code reports the call's input (fresh + cache) in every assistant
#: event; 160k leaves the checkpoint turn room under any window the Opus models have.
DEFAULT_CONTEXT_TOKEN_LIMIT = 160_000
#: Seconds to wait for the `result` after an interrupt before the process is closed.
INTERRUPT_GRACE = 120.0
_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
#: Environment names that look like credentials are not handed to the CLI (the one
#: credential it signs with is kept) -- claude_backend.py's rule.
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSW|CREDENTIAL", re.I)
ENV_KEEP = frozenset({"CLAUDE_CODE_OAUTH_TOKEN"})
_QUOTA_RE = re.compile(r"usage limit|out of (?:extra )?usage", re.I)
_AUTH_RE = re.compile(r"Not logged in|Please run /login|OAuth (?:access )?token (?:has )?expired|"
                      r"authentication_error|Invalid (?:API key|bearer token)|"
                      r"OAuth (?:access )?token has been revoked", re.I)
AUTH_EXIT_STATUS = 75


class SandboxViolation(RuntimeError):
    """The CLI ran with a tool surface other than the one this arm is defined by."""


def scrubbed_env() -> dict[str, str]:
    """claude_backend.scrubbed_env: no CLAUDE_* of the launching session, no secrets."""
    drop_exact = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CLAUDE_PID", "CLAUDE_EFFORT",
                  "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"}
    env = {k: v for k, v in os.environ.items()
           if k in ENV_KEEP or not (k in drop_exact or k.startswith("CLAUDE_CODE_"))}
    return {k: v for k, v in env.items() if k in ENV_KEEP or not SECRET_NAME.search(k)}


def default_claude_bin() -> str:
    for cand in (os.environ.get("CLAUDE_BIN"), shutil.which("claude")):
        if cand and os.access(cand, os.X_OK):
            return cand
    raise RuntimeError("no runnable claude binary: set CLAUDE_BIN")


def prepare_claude_home(home: Path, *, wrapped: bool) -> Path:
    """The episode's CLAUDE_CONFIG_DIR: the credential and nothing else. Unwrapped, the
    eval account's .credentials.json is linked in (never copied: the CLI refreshes it in
    place); under the wrapper the sandbox binds it itself. A `claude setup-token` token
    in CLAUDE_CODE_OAUTH_TOKEN needs no file."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    if wrapped or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return home
    target = home / ".credentials.json"
    if not (target.exists() or target.is_symlink()):
        auth = Path(os.environ.get("CLAUDE_EVAL_AUTH")
                    or os.path.expanduser("~/.claude-eval/.credentials.json"))
        if auth.exists():
            target.symlink_to(auth.resolve())
    return home


def _looks_like_base64(value: str) -> bool:
    return len(value) > 4096 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", value[:512]) is not None


def _sanitize(value: Any) -> Any:
    """Image payloads out of the transcripts: a sha256 and a byte count instead."""
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str) and _looks_like_base64(value):
        try:
            raw = base64.b64decode(value, validate=True)
        except ValueError:
            return value
        return f"<base64;bytes={len(raw)};sha256={hashlib.sha256(raw).hexdigest()}>"
    return value


class _ToolServer:
    """The runner's end of the bridge: a unix socket, one line of JSON per request."""

    def __init__(self, runner: "ClaudeCodeRunner") -> None:
        self.runner = runner
        # Short, because a unix socket path is capped near 108 bytes; /tmp is a tmpfs
        # inside the sandbox, so the wrapper binds this directory in (CLAUDE_SANDBOX_RW_BINDS).
        self.dir = Path(tempfile.mkdtemp(prefix="vista-mcp-", dir="/tmp"))
        os.chmod(self.dir, 0o700)
        self.path = self.dir / "s"
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self.path))
        self._sock.listen(8)
        self._closed = False
        threading.Thread(target=self._accept, name="vista-tools", daemon=True).start()

    def _accept(self) -> None:
        while not self._closed:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        reader = conn.makefile("r", encoding="utf-8")
        try:
            for line in reader:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if request.get("op") == "list":
                    answer: dict[str, Any] = {"tools": self.runner.mcp_tools()}
                elif request.get("op") == "call":
                    answer = self.runner.handle_tool_call(request.get("tool"), request.get("arguments"),
                                                          str(request.get("id")))
                else:
                    answer = {"content": [{"type": "text", "text": "Unknown request."}], "isError": True}
                conn.sendall((json.dumps(answer, separators=(",", ":")) + "\n").encode("utf-8"))
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def close(self) -> None:
        self._closed = True
        try:
            self._sock.close()
        except OSError:
            pass
        shutil.rmtree(self.dir, ignore_errors=True)


class _ClaudeProcess:
    """One `claude -p` process: stdin for our messages, stdout events on a queue,
    stderr copied to a file. Like the codex runner's connection, with the CLI's own
    quirks: the process runs in its own session so the wrapper's whole group dies with it."""

    def __init__(self, argv: list[str], *, cwd: Path, env: dict[str, str], events_path: Path,
                 stderr_path: Path, requests_path: Path) -> None:
        self.process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        bufsize=1, start_new_session=True)
        assert self.process.stdin and self.process.stdout and self.process.stderr
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._requests = requests_path.open("a", encoding="utf-8")
        self._stdin_lock = threading.Lock()
        threading.Thread(target=self._read_stdout, args=(self.process.stdout, events_path), daemon=True).start()
        threading.Thread(target=self._copy, args=(self.process.stderr, stderr_path), daemon=True).start()

    def _read_stdout(self, stream: Any, path: Path) -> None:
        with path.open("a", encoding="utf-8") as sink:
            for line in stream:
                if '"stream_event"' not in line:
                    try:
                        sink.write(json.dumps(_sanitize(json.loads(line)), separators=(",", ":")) + "\n")
                    except (json.JSONDecodeError, TypeError):
                        sink.write(line)
                    sink.flush()
                self._queue.put(line)
        self._queue.put(None)

    @staticmethod
    def _copy(stream: Any, path: Path) -> None:
        with path.open("a", encoding="utf-8") as sink:
            for line in stream:
                sink.write(line)
                sink.flush()

    def send(self, message: dict[str, Any]) -> None:
        text = json.dumps(message, separators=(",", ":"))
        with self._stdin_lock:
            self._requests.write(json.dumps(_sanitize(message), separators=(",", ":")) + "\n")
            self._requests.flush()
            assert self.process.stdin is not None
            self.process.stdin.write(text + "\n")
            self.process.stdin.flush()

    def receive(self, deadline: float, idle_timeout: float | None) -> dict[str, Any] | None:
        """The next event, None when the process ended, TimeoutError on silence."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Claude Code turn timed out")
            wait = remaining if idle_timeout is None else min(remaining, idle_timeout)
            try:
                line = self._queue.get(timeout=wait)
            except queue.Empty as exc:
                if idle_timeout is not None and remaining > idle_timeout:
                    raise TimeoutError(f"Claude Code was silent for {idle_timeout:.0f}s") from exc
                raise TimeoutError("Claude Code turn timed out") from exc
            if line is None:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                return message

    def close(self) -> int:
        try:
            if self.process.stdin is not None:
                with self._stdin_lock:
                    self.process.stdin.close()
        except OSError:
            pass
        try:
            return self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                return self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return self.process.wait()
        finally:
            self._requests.close()


class ClaudeCodeRunner:
    def __init__(self, *, workspace: Path, config_dir: Path, io_dir: Path, controller: Any,
                 tools: tuple[dict[str, Any], ...], base_instructions: str,
                 developer_instructions: str, model: str | None, reasoning_effort: str | None,
                 claude_bin: str | None = None, task_timeout: float = 3 * 24 * 3600,
                 idle_timeout: float | None = DEFAULT_IDLE_TIMEOUT,
                 thread_bytes_budget: int | None = DEFAULT_THREAD_BYTES_BUDGET,
                 context_token_limit: int | None = None,
                 objective: str = "Continue the task.") -> None:
        self.workspace = Path(workspace).resolve()
        self.guide_path = self.workspace / "GUIDE.md"
        self.working_path = self.workspace / "WORKING.md"
        self.claude_bin = claude_bin or default_claude_bin()
        self.wrapped = Path(self.claude_bin).name == WRAPPER_NAME
        self.config_dir = prepare_claude_home(Path(config_dir).resolve(), wrapped=self.wrapped)
        #: The codex runner's name for the markers' directory, for callers that read it.
        self.codex_home = self.config_dir
        self.io_dir = Path(io_dir).resolve()
        self.io_dir.mkdir(parents=True, exist_ok=True)
        self.controller = controller
        self.tools = tuple(tools)
        self.model = model or "claude-opus-5"
        if reasoning_effort and reasoning_effort not in _EFFORTS:
            logger.info("[vista/claude] effort %r is not in the CLI's vocabulary; sending 'low'",
                        reasoning_effort)
        self.reasoning_effort = reasoning_effort if reasoning_effort in _EFFORTS else "low"
        self.system_prompt = "\n\n".join([base_instructions.strip(), developer_instructions.strip(), (
            f"Your tools are served by the MCP server `{MCP_SERVER_NAME}` (`mcp__{MCP_SERVER_NAME}__play` "
            "is `play`, and so on). You have no other tool: no shell, no file access.")])
        self.task_timeout = task_timeout
        self.idle_timeout = idle_timeout
        self.thread_bytes_budget = thread_bytes_budget
        self.context_token_limit = context_token_limit or int(
            os.environ.get("CLAUDE_VISTA_CONTEXT_LIMIT", DEFAULT_CONTEXT_TOKEN_LIMIT))
        self.objective = objective
        self.dispatcher = GameToolDispatcher(controller=controller, guide_path=self.guide_path,
                                             working_path=self.working_path)
        # The bridge script travels in the config dir: inside the sandbox that is one of
        # the two paths that exist besides the system.
        self.bridge_path = self.config_dir / "mcp_bridge.py"
        shutil.copyfile(BRIDGE_SOURCE, self.bridge_path)
        self.bridge_path.chmod(0o500)
        self.tool_server = _ToolServer(self)
        self._lock = threading.RLock()
        self._segment_index = 0
        self._connection: _ClaudeProcess | None = None
        self._result: dict[str, Any] | None = None
        self._final_message = ""
        self._segment_usage: CodexUsage | None = None
        self._context_tokens = 0
        self._paused = False
        self._interrupt_at: float | None = None
        self._session_seen: str | None = None
        self._violation: str | None = None
        self.last_agent_message = ""
        self.thread_bytes: dict[str, int] = {}
        self.peak_thread_bytes = 0
        self.peak_context_tokens = 0
        self.wire_checkpoints = 0
        self.context_checkpoints = 0
        self.images_sent = 0
        self.tool_errors = 0
        self.quota_hits = 0
        self.quota_wait_s = 0.0
        self.cost_usd = 0.0
        self.api_turns = 0
        self.resolved_model: str | None = None
        self.session_ids: list[str] = []
        self.segments: list[CodexResult] = []

    # -- what the bridge asks for ----------------------------------------------------------

    def mcp_tools(self) -> list[dict[str, Any]]:
        return [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"],
                 **({"annotations": t["annotations"]} if t.get("annotations") else {})}
                for t in self.tools]

    def expected_tool_names(self) -> frozenset[str]:
        return frozenset(f"mcp__{MCP_SERVER_NAME}__{t['name']}" for t in self.tools)

    def handle_tool_call(self, tool: Any, arguments: Any, call_id: str) -> dict[str, Any]:
        """A tool call from the model, executed against the controller; the MCP content
        blocks go back to the bridge, and the turn is interrupted after a checkpoint
        boundary (the codex runner's `_handle_tool_call`, without the steering)."""
        if not isinstance(tool, str) or tool not in {t["name"] for t in self.tools}:
            execution = ToolExecution("Invalid tool request.", False)
        else:
            execution = self.dispatcher.execute(tool, arguments, call_id)
        content: list[dict[str, Any]] = [{"type": "text", "text": execution.text}]
        for image in execution.images:
            data, steer_text = image.get("data"), image.get("steer_text")
            if not isinstance(data, str) or not isinstance(steer_text, str):
                content = [{"type": "text", "text": json.dumps({"error": "The resulting visual could not be delivered."})}]
                execution.success = False
                break
            self._count_bytes(data)
            content.append({"type": "text", "text": steer_text})
            content.append({"type": "image", "data": data, "mimeType": image.get("mime_type", "image/png")})
        if not execution.success:
            self.tool_errors += 1
        with self._lock:
            if tool == "play" and execution.images and not self._paused:
                reason = None
                session = self._session_seen
                if (self.thread_bytes_budget and session
                        and self.thread_bytes.get(session, 0) > self.thread_bytes_budget):
                    reason = "thread_bytes"
                elif self.context_token_limit and self._context_tokens > self.context_token_limit:
                    reason = "context_tokens"
                if reason and self.controller.request_compact_checkpoint(reason=reason):
                    if reason == "thread_bytes":
                        self.wire_checkpoints += 1
                    else:
                        self.context_checkpoints += 1
                    execution.interrupt_after = True
                    execution.boundary_reason = reason
                    content.append({"type": "text", "text": (
                        "<checkpoint_requested>The conversation is full: your next and only action "
                        "is save_compact_checkpoint.</checkpoint_requested>")})
            if (tool == "save_compact_checkpoint" and execution.success
                    and self.controller.compact_checkpoint_ready.exists()):
                execution.interrupt_after = True
                execution.boundary_reason = "checkpoint_saved"
        answer = {"content": content, "isError": not execution.success}
        if execution.interrupt_after:
            # The result is written to the bridge by the caller right after this
            # returns; the interrupt goes out on a timer so it lands after it.
            threading.Timer(0.5, self._interrupt, kwargs={"reason": execution.boundary_reason or ""}).start()
        return answer

    def _count_bytes(self, data_b64: str) -> None:
        with self._lock:
            self.images_sent += 1
            session = self._session_seen
            if session is not None:
                total = self.thread_bytes.get(session, 0) + len(data_b64)
                self.thread_bytes[session] = total
                self.peak_thread_bytes = max(self.peak_thread_bytes, total)

    def _interrupt(self, *, reason: str) -> None:
        with self._lock:
            if self._paused or self._connection is None:
                return
            self._paused = True
            self._interrupt_at = time.monotonic()
            connection = self._connection
        try:
            connection.send({"type": "control_request", "request_id": str(uuid.uuid4()),
                             "request": {"subtype": "interrupt"}})
        except (OSError, ValueError) as exc:
            logger.warning("[vista/claude] interrupt (%s) could not be sent: %s", reason, exc)

    # -- segments --------------------------------------------------------------------------

    def run_task(self, prompt: str, images: tuple[Path, ...]) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=None, initial_images=images, kind="task")

    def run_recovery_task(self, recovery: CompactRecovery) -> CodexResult:
        return self._run_segment(prompt=compact_recovery_prompt(recovery, self.objective), session_id=None,
                                 initial_images=recovery.image_paths, recovery=recovery,
                                 kind="compact_recovery")

    def resume_recovery_task(self, session_id: str, recovery: CompactRecovery) -> CodexResult:
        return self._run_segment(prompt=compact_recovery_prompt(recovery, self.objective),
                                 session_id=session_id, initial_images=recovery.image_paths,
                                 recovery=recovery, kind="compact_recovery_resumed")

    def resume_runtime_recovery(self, session_id: str, recovery: RuntimeRecovery) -> CodexResult:
        return self._run_segment(prompt=runtime_recovery_prompt(recovery, self.objective),
                                 session_id=session_id, initial_images=recovery.image_paths,
                                 runtime_recovery=recovery, kind="runtime_recovery")

    def run_fresh_runtime_recovery(self, recovery: RuntimeRecovery) -> CodexResult:
        return self._run_segment(prompt=fresh_runtime_recovery_prompt(recovery, self.objective),
                                 session_id=None, initial_images=recovery.image_paths,
                                 runtime_recovery=recovery, fresh_delivery=True,
                                 kind="fresh_runtime_recovery")

    def resume_checkpoint(self, session_id: str, prompt: str) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=session_id, initial_images=(), kind="checkpoint")

    def resume_nonterminal_task(self, session_id: str, prompt: str) -> CodexResult:
        return self._run_segment(prompt=prompt, session_id=session_id, initial_images=(),
                                 kind="continuation")

    def _argv(self, session_id: str | None) -> tuple[list[str], str]:
        settings = json.dumps({"autoCompactEnabled": False, "autoMemoryEnabled": False,
                               "includeCoAuthoredBy": False})
        python = "python3" if self.wrapped else sys.executable
        mcp = json.dumps({"mcpServers": {MCP_SERVER_NAME: {
            "type": "stdio", "command": python, "args": [str(self.bridge_path), str(self.tool_server.path)]}}})
        argv = [self.claude_bin, "-p", "--model", self.model, "--effort", self.reasoning_effort,
                "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--include-partial-messages",
                "--tools", "", "--mcp-config", mcp, "--strict-mcp-config",
                "--disable-slash-commands", "--setting-sources", "",
                "--system-prompt", self.system_prompt, "--settings", settings,
                "--permission-mode", "bypassPermissions"]
        if session_id:
            argv += ["--resume", session_id]
            resolved = session_id
        else:
            resolved = str(uuid.uuid4())
            argv += ["--session-id", resolved]
        return argv, resolved

    def _env(self) -> dict[str, str]:
        env = scrubbed_env()
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        env["DISABLE_AUTOUPDATER"] = "1"
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        env["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"] = "1"
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        env["CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING"] = "1"
        # The wrapper binds this directory in, so the bridge inside can reach the socket.
        env["CLAUDE_SANDBOX_RW_BINDS"] = str(self.tool_server.dir)
        return env

    @staticmethod
    def _user_message(prompt: str, images: tuple[Path, ...]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in images:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/png",
                "data": base64.b64encode(Path(path).read_bytes()).decode("ascii")}})
        return {"type": "user", "message": {"role": "user", "content": content}}

    def _run_segment(self, *, prompt: str, session_id: str | None, initial_images: Any,
                     recovery: CompactRecovery | None = None,
                     runtime_recovery: RuntimeRecovery | None = None,
                     fresh_delivery: bool = False, kind: str) -> CodexResult:
        self._segment_index += 1
        segment = self._segment_index
        stem = f"segment_{segment:03d}"
        events_path = self.io_dir / f"{stem}.stdout.jsonl"
        stderr_path = self.io_dir / f"{stem}.stderr.txt"
        requests_path = self.io_dir / f"{stem}.requests.jsonl"
        (self.io_dir / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
        argv, resolved = self._argv(session_id)
        write_json(self.io_dir / f"{stem}.command.json",
                   {"argv": [a if len(a) < 4000 else a[:200] + "..." for a in argv], "kind": kind,
                    "session_id": resolved, "cli": "claude"})
        with self._lock:
            self._result = None
            self._final_message = ""
            self._segment_usage = None
            self._paused = False
            self._interrupt_at = None
            self._session_seen = resolved
            self._violation = None
            self.thread_bytes.setdefault(resolved, 0)
            if resolved not in self.session_ids:
                self.session_ids.append(resolved)
        returncode, error_text = 0, ""
        process: _ClaudeProcess | None = None
        try:
            process = _ClaudeProcess(argv, cwd=self.workspace, env=self._env(), events_path=events_path,
                                     stderr_path=stderr_path, requests_path=requests_path)
        except Exception as exc:
            stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            result = CodexResult(segment, 125, "", resolved if session_id else None, events_path,
                                 stderr_path, requests_path, None, kind)
            self.segments.append(result)
            return result
        with self._lock:
            self._connection = process
        deadline = time.monotonic() + self.task_timeout
        logger.info("[vista/claude] segment %d (%s) model=%s resume=%s images=%d", segment, kind,
                    self.model, "yes" if session_id else "no", len(tuple(initial_images)))
        try:
            message = self._user_message(prompt, tuple(Path(p) for p in initial_images))
            for image in message["message"]["content"][1:]:
                self._count_bytes(image["source"]["data"])
            process.send(message)
            if recovery is not None:
                self.controller.complete_compact_recovery(recovery)
            if runtime_recovery is not None:
                self.controller.complete_runtime_recovery(
                    runtime_recovery,
                    delivery="fresh_runtime_thread" if fresh_delivery else "resumed_runtime_thread")
            while self._result is None:
                with self._lock:
                    interrupted_at = self._interrupt_at
                if interrupted_at is not None and time.monotonic() - interrupted_at > INTERRUPT_GRACE:
                    break
                event = process.receive(deadline, self.idle_timeout if interrupted_at is None
                                        else min(self.idle_timeout or 30.0, 30.0))
                if event is None:
                    break
                self._observe(event)
                if self._violation:
                    raise SandboxViolation(self._violation)
            paused = self.controller.compact_checkpoint_marker.exists() and self._paused
            if self._result is None:
                if not paused:
                    returncode = 1
                    error_text = "Claude Code ended without a result event"
            elif self._result.get("is_error") and not paused:
                returncode = 1
                error_text = str(self._result.get("result") or self._result.get("subtype") or "error")
        except TimeoutError as exc:
            returncode, error_text = 124, str(exc)
        except SandboxViolation:
            raise
        except Exception as exc:
            returncode, error_text = 1, f"{type(exc).__name__}: {exc}"
        finally:
            rc = process.close()
            with self._lock:
                self._connection = None
            if returncode == 0 and rc not in (0, None) and self._result is None and not self._paused:
                returncode = rc
                error_text = error_text or f"claude exited rc={rc}"
            if error_text:
                with stderr_path.open("a", encoding="utf-8") as f:
                    f.write(error_text + "\n")
                logger.warning("[vista/claude] segment %d (%s) ended: %s", segment, kind, error_text)
        if error_text and _AUTH_RE.search(error_text):
            self._auth_lost(error_text)
        if error_text and _QUOTA_RE.search(error_text):
            # A usage limit resets on a clock: wait it out before the loop retries.
            self.quota_hits += 1
            pause = float(os.environ.get("CLAUDE_QUOTA_WAIT", "600"))
            logger.warning("[vista/claude] usage limit (%s); waiting %.0fs", error_text[:120], pause)
            time.sleep(pause)
            self.quota_wait_s += pause
        # A fresh session that never answered may not exist: no id to resume into.
        session_out: str | None = resolved
        if session_id is None and not (self._result is not None or self._paused):
            session_out = None
        result = CodexResult(segment, returncode, self._final_message, session_out, events_path,
                             stderr_path, requests_path, self._segment_usage, kind)
        self.segments.append(result)
        return result

    def _auth_lost(self, error: str) -> None:
        logger.critical("[vista/claude] no working credential (%s); stopping the run (exit %d)",
                        error[:200], AUTH_EXIT_STATUS)
        if os.environ.get("CLAUDE_AUTH_FATAL", "1") == "0":
            raise RuntimeError(f"claude: not authenticated: {error[:200]}")
        logging.shutdown()
        os._exit(AUTH_EXIT_STATUS)

    def _observe(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            seen = event.get("session_id")
            with self._lock:
                if isinstance(seen, str) and seen != self._session_seen:
                    logger.warning("[vista/claude] session drift: asked %s, got %s", self._session_seen, seen)
                    previous = self._session_seen
                    self.thread_bytes[seen] = (self.thread_bytes.pop(previous, 0)
                                               if previous is not None else 0)
                    self._session_seen = seen
                    if seen not in self.session_ids:
                        self.session_ids.append(seen)
            self.resolved_model = event.get("model") or self.resolved_model
            tools = set(event.get("tools") or [])
            expected = self.expected_tool_names()
            problems: dict[str, Any] = {}
            if tools != expected:
                problems["tool_surface"] = sorted(tools ^ expected)
            servers = [s for s in (event.get("mcp_servers") or []) if isinstance(s, dict)]
            if [s.get("name") for s in servers] != [MCP_SERVER_NAME]:
                problems["mcp_servers"] = servers
            elif servers[0].get("status") != "connected":
                problems["mcp_status"] = servers[0].get("status")
            for surface in ("skills", "slash_commands", "plugins"):
                if event.get(surface):
                    problems[surface] = event[surface]
            if problems:
                self._violation = (f"the CLI ran with a surface this arm must not have: {problems} "
                                   f"(expected exactly {sorted(expected)})")
        elif kind == "assistant":
            message = event.get("message") or {}
            for block in message.get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    self._final_message = block["text"]
                    self.last_agent_message = block["text"]
            usage = message.get("usage") or {}
            if usage:
                context = sum(int(usage.get(k) or 0) for k in
                              ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                with self._lock:
                    self._context_tokens = context
                    self.peak_context_tokens = max(self.peak_context_tokens, context)
        elif kind == "result":
            usage = event.get("usage") or {}
            self._segment_usage = CodexUsage(int(usage.get("input_tokens") or 0),
                                             int(usage.get("cache_read_input_tokens") or 0)
                                             + int(usage.get("cache_creation_input_tokens") or 0),
                                             int(usage.get("output_tokens") or 0), 0)
            cost = event.get("total_cost_usd")
            if isinstance(cost, (int, float)):
                self.cost_usd += cost
            self.api_turns += int(event.get("num_turns") or 0)
            if not event.get("is_error") and event.get("result"):
                self._final_message = str(event["result"])
                self.last_agent_message = self._final_message
            self._result = event

    def close(self) -> None:
        with self._lock:
            connection = self._connection
        if connection is not None:
            connection.close()
        self.tool_server.close()

    def audit(self) -> dict[str, Any]:
        usage = CodexUsage()
        for s in self.segments:
            if s.usage:
                usage = CodexUsage(usage.input_tokens + s.usage.input_tokens,
                                   usage.cached_input_tokens + s.usage.cached_input_tokens,
                                   usage.output_tokens + s.usage.output_tokens, 0)
        kinds: dict[str, int] = {}
        for s in self.segments:
            kinds[s.kind] = kinds.get(s.kind, 0) + 1
        return {"cli": "claude", "codex_bin": self.claude_bin, "base_url": None, "model": self.model,
                "resolved_model": self.resolved_model, "effort": self.reasoning_effort,
                "wrapped": self.wrapped, "config_dir": str(self.config_dir),
                "compact_thresholds": {"context_token_limit": self.context_token_limit,
                                       "source": "claude-vista-default"},
                "thread_bytes_budget": self.thread_bytes_budget,
                "segments": len(self.segments), "segments_by_kind": kinds,
                "segments_failed": sum(1 for s in self.segments if s.returncode != 0),
                "threads": len(self.thread_bytes), "peak_thread_bytes": self.peak_thread_bytes,
                "peak_context_tokens": self.peak_context_tokens,
                "images_sent": self.images_sent, "wire_checkpoints": self.wire_checkpoints,
                "context_checkpoints": self.context_checkpoints,
                "tool_calls": dict(self.dispatcher.calls), "tool_errors": self.tool_errors,
                "api_turns": self.api_turns, "cost_usd": round(self.cost_usd, 4),
                "quota_hits": self.quota_hits, "quota_wait_s": self.quota_wait_s,
                "usage": usage.__dict__}
