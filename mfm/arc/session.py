"""One coding-agent session in the workspace, and the loop that keeps one alive.

Upstream's run.py starts `claude -p` or `codex exec --json` once per game with the task
prompt, records the event stream verbatim, and folds it into a report (rig/agents.py:
turns, tool calls, compactions, tokens). A session that dies is resumed by hand with
`--resume`, whose prompt tells a fresh agent to recover from notes.md and logs.txt.
Here the episode is driven by the benchmark's clock, so the resume is automatic: when
a session exits before the episode is over, the loop starts another with the resume
prompt, up to `max_sessions`. The workspace is the memory either way.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

#: How to run each CLI headlessly. Codex: upstream's flags plus the ones the benchmark
#: passes in (`extra_args`: the sandbox mode and the feature switches every codex arm
#: here runs under). Claude Code: upstream's six pre-approved tools.
CLAUDE_ALLOWED_TOOLS = "Bash,Read,Write,Edit,Grep,Glob"


def codex_argv(*, codex_bin: str, model: str, effort: str, prompt: str,
               extra_args: tuple[str, ...] = ()) -> list[str]:
    return [codex_bin, "exec", "--json", "--skip-git-repo-check", "--ignore-user-config",
            "-m", model, "-c", f'model_reasoning_effort="{effort}"', *extra_args, prompt]


def claude_argv(*, claude_bin: str, model: str, effort: str | None, prompt: str) -> list[str]:
    argv = [claude_bin, "-p", prompt, "--model", model, "--output-format", "stream-json",
            "--verbose", "--allowedTools", CLAUDE_ALLOWED_TOOLS]
    if effort:
        argv += ["--effort", effort]
    return argv


def child_env(base: dict[str, str], *, codex_home: Path | None, kind: str) -> dict[str, str]:
    """Upstream's child_env: a session of its own, not a continuation of the one that
    launched it (the CLAUDE_* variables identify *this* session), and no key it does
    not need."""
    env = {k: v for k, v in base.items()
           if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "CLAUDE_"))}
    env.pop("OPENAI_API_KEY", None)      # the account's login, never the key (every arm here)
    if kind == "claude":
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    env.setdefault("TOKIO_WORKER_THREADS", "8")
    return env


class StreamStats:
    """What rig/agents.py reads off a session's event stream, for either CLI."""

    def __init__(self) -> None:
        self.turns = 0
        self.tool_calls = 0
        self.commands = 0
        self.image_views = 0
        self.file_changes = 0
        self.agent_messages = 0
        self.compactions = 0
        self.input_tokens = 0
        self.cached_input_tokens = 0
        self.output_tokens = 0
        self.last_message = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "last_message"}

    def absorb(self, kind: str, event: dict) -> None:
        if kind == "codex":
            self._absorb_codex(event)
        else:
            self._absorb_claude(event)

    def _absorb_codex(self, event: dict) -> None:
        t = event.get("type")
        item = event.get("item") or {}
        if t == "item.completed":
            it = item.get("type")
            if it == "agent_message":
                self.agent_messages += 1
                self.last_message = str(item.get("text") or "")
            elif it == "command_execution":
                self.tool_calls += 1
                self.commands += 1
            elif it == "view_image":
                self.tool_calls += 1
                self.image_views += 1
            elif it in ("file_change", "patch_apply"):
                self.tool_calls += 1
                self.file_changes += 1
        elif t == "turn.completed":
            self.turns += 1
            usage = event.get("usage") or {}
            # Cumulative over the thread: keep the maximum, not the sum.
            self.input_tokens = max(self.input_tokens, int(usage.get("input_tokens") or 0))
            self.cached_input_tokens = max(self.cached_input_tokens,
                                           int(usage.get("cached_input_tokens") or 0))
            self.output_tokens = max(self.output_tokens, int(usage.get("output_tokens") or 0)
                                     + int(usage.get("reasoning_output_tokens") or 0))
        elif t in ("thread.compacted", "compaction") or "compact" in str(t or ""):
            self.compactions += 1

    def _absorb_claude(self, event: dict) -> None:
        t = event.get("type")
        if t == "assistant":
            self.turns += 1
            for block in (event.get("message") or {}).get("content", []):
                if block.get("type") == "tool_use":
                    self.tool_calls += 1
                    name = block.get("name", "")
                    got = block.get("input") or {}
                    if name == "Bash":
                        self.commands += 1
                    elif name == "Read" and str(got.get("file_path", "")).lower().endswith(
                            (".png", ".jpg", ".jpeg")):
                        self.image_views += 1
                    elif name in ("Write", "Edit"):
                        self.file_changes += 1
                elif block.get("type") == "text":
                    self.agent_messages += 1
                    self.last_message = str(block.get("text") or "")
        elif t == "system" and event.get("subtype") == "compact_boundary":
            self.compactions += 1
        elif t == "result":
            usage = event.get("usage") or {}
            self.input_tokens = int(usage.get("input_tokens") or 0)
            self.cached_input_tokens = int(usage.get("cache_read_input_tokens") or 0)
            self.output_tokens = int(usage.get("output_tokens") or 0)


class AgentSession:
    """One headless CLI session: spawned in the workspace, its stdout recorded line by
    line to `stream_path` and folded into `stats` as it arrives."""

    def __init__(self, argv: list[str], *, workspace: Path, env: dict[str, str],
                 stream_path: Path, stderr_path: Path, kind: str) -> None:
        self.argv = argv
        self.workspace = Path(workspace)
        self.env = env
        self.stream_path = Path(stream_path)
        self.stderr_path = Path(stderr_path)
        self.kind = kind
        self.stats = StreamStats()
        self.proc: subprocess.Popen | None = None
        self.started = 0.0
        self.seconds = 0.0
        self.returncode: int | None = None

    def run(self, stop: threading.Event) -> int:
        self.started = time.monotonic()
        with self.stderr_path.open("ab") as err:
            self.proc = subprocess.Popen(
                self.argv, cwd=str(self.workspace), env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=err, start_new_session=True)
        assert self.proc.stdout is not None
        with self.stream_path.open("a", encoding="utf-8", buffering=1) as stream:
            for raw in self.proc.stdout:
                line = raw.decode("utf-8", errors="replace")
                stream.write(line)
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    self.stats.absorb(self.kind, event)
                if stop.is_set():
                    break
        if stop.is_set():
            self.kill()
        self.returncode = self.proc.wait()
        self.seconds = time.monotonic() - self.started
        return self.returncode

    def kill(self, grace: float = 5.0) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.proc.pid, sig)
            except ProcessLookupError:
                return
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    return
                time.sleep(0.1)


class SessionLoop:
    """Keep a coding agent playing until the episode ends.

    `make_argv(prompt)` builds the CLI command; `first_prompt` starts the run and
    `resume_prompt` every later session. A session that ends while `episode_over()` is
    false is replaced after `relaunch_delay` seconds, up to `max_sessions`; the loop
    then leaves the environment to run out on no-ops, the way upstream's launcher
    leaves a game whose agent stopped.
    """

    def __init__(self, *, make_argv: Callable[[str], list[str]], workspace: Path,
                 env: dict[str, str], io_dir: Path, kind: str, first_prompt: str,
                 resume_prompt: str, episode_over: Callable[[], bool],
                 max_sessions: int = 25, relaunch_delay: float = 5.0,
                 quick_failure_seconds: float = 20.0) -> None:
        self.make_argv = make_argv
        self.workspace = Path(workspace)
        self.env = env
        self.io_dir = Path(io_dir)
        self.kind = kind
        self.first_prompt = first_prompt
        self.resume_prompt = resume_prompt
        self.episode_over = episode_over
        self.max_sessions = max_sessions
        self.relaunch_delay = relaunch_delay
        self.quick_failure_seconds = quick_failure_seconds
        self.quick_failures = 0
        self.sessions: list[AgentSession] = []
        self.exhausted = False
        self.failure: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="arc-session", daemon=True)
        self._current: AgentSession | None = None

    def start(self) -> None:
        self.io_dir.mkdir(parents=True, exist_ok=True)
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def close(self, timeout: float = 30.0) -> None:
        self._stop.set()
        cur = self._current
        if cur is not None:
            cur.kill()
        self._thread.join(timeout)

    def _run(self) -> None:
        try:
            n = 0
            while not self._stop.is_set() and not self.episode_over():
                if n >= self.max_sessions:
                    self.exhausted = True
                    return
                n += 1
                prompt = self.first_prompt if n == 1 else self.resume_prompt
                argv = self.make_argv(prompt)
                (self.io_dir / f"session_{n:03d}.command.json").write_text(
                    json.dumps({"argv": argv, "prompt": prompt, "kind": self.kind}, indent=1),
                    encoding="utf-8")
                session = AgentSession(argv, workspace=self.workspace, env=self.env,
                                       stream_path=self.io_dir / f"session_{n:03d}.stream.jsonl",
                                       stderr_path=self.io_dir / f"session_{n:03d}.stderr.txt",
                                       kind=self.kind)
                self.sessions.append(session)
                self._current = session
                rc = session.run(self._stop)
                self._current = None
                (self.io_dir / f"session_{n:03d}.result.json").write_text(
                    json.dumps({"returncode": rc, "seconds": round(session.seconds, 1),
                                **session.stats.as_dict()}, indent=1), encoding="utf-8")
                if self._stop.is_set() or self.episode_over():
                    return
                # Ended with budget left: the resume, after a pause. A CLI that dies at
                # once and non-zero is not a model that stopped -- it is an outage or a
                # spent quota, which cannot clear in seconds -- so those back off. 25
                # restarts at a flat 5 s would spend the session budget in two minutes
                # and leave the episode coasting on no-ops for the rest of its walltime.
                if rc != 0 and session.seconds < self.quick_failure_seconds:
                    self.quick_failures += 1
                else:
                    self.quick_failures = 0
                self._stop.wait(self.relaunch_delay * 2 ** min(self.quick_failures, 6))
        except Exception as exc:  # noqa: BLE001
            self.failure = f"{type(exc).__name__}: {exc}"

    def audit(self) -> dict[str, Any]:
        total = StreamStats()
        for s in self.sessions:
            for k, v in s.stats.as_dict().items():
                setattr(total, k, getattr(total, k) + v)
        return {
            "sessions": len(self.sessions),
            "session_exits": [s.returncode for s in self.sessions],
            "session_seconds": [round(s.seconds, 1) for s in self.sessions],
            "sessions_exhausted": self.exhausted,
            "quick_failures": self.quick_failures,
            "failure": self.failure,
            "stream": total.as_dict(),
        }
