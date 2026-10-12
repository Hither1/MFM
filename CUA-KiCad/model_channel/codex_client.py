"""The model channel of the KiCad direct arm: one call through the Codex CLI.

Each `generate_text` is a fresh `codex exec` without `resume`: the caller sends the whole
message list at every step, and nothing is kept between calls. The memory arm uses the
resumable `mfm.backend.codex_turn.CodexTurn` instead. Both paths run codex with the same
safety flags (`mfm/backend/codex_turn.py` `SAFE_CODEX_FLAGS`).

The inline notes record measurements taken while the channel was built, some of them on
a question-answering benchmark; treat them as provenance.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

from mfm.backend.codex_turn import (
    DEFAULT_CONTEXT_WINDOW,
    LocalServerGate,
    SAFE_CODEX_FLAGS,
    SandboxViolation,
    _metadata_args,
    effort_for,
    prepare_codex_home,
    request_stats,
    resolve_codex_bin,
)

logger = logging.getLogger(__name__)

_DATA_URI_RE = re.compile(r"^data:image/(\w+);base64,(.*)$", re.DOTALL)


class CodexClient(LocalServerGate):
    """The direct arm's model channel: `generate_text(messages, images=...)` is one
    `codex exec` that returns the model's reply.
    """

    def __init__(
        self,
        model_name: str = "gpt-5.6-sol",
        reasoning_effort: str = "xhigh",
        codex_bin: str | None = None,
        max_images: int | None = None,
        # A ceiling on one call, not a target. Measured stalls sat at exactly this
        # value, so the number decides what a stall costs.
        timeout: int = int(os.environ.get("CODEX_TIMEOUT", 900)),
        transcript_dir: str | None = None,
        base_url: str | None = None,
        codex_home: str | None = None,
        context_window: int | None = None,
    ) -> None:
        self.default_model = model_name
        self.reasoning_effort = reasoning_effort
        self.context_window = context_window or DEFAULT_CONTEXT_WINDOW
        # Resolved against the launch CWD, because generate_text runs codex from a
        # scratch dir where a relative path would stop existing.
        self.codex_bin = resolve_codex_bin(codex_bin or os.environ.get("CODEX_BIN", "codex"))
        self.max_images = max_images
        self.timeout = timeout
        # When set, codex is redirected at a local OpenAI-compatible server instead of
        # the account's hosted models, which is how a local model gets driven through the
        # same harness. The server must tolerate the Responses API's `developer` role and
        # codex's `client_metadata`.
        self.base_url = base_url
        self.codex_home = Path(codex_home) if codex_home else None
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        if self.transcript_dir:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self._calls = 0

        if shutil.which(self.codex_bin) is None and not Path(self.codex_bin).exists():
            raise RuntimeError(f"codex binary not found: {self.codex_bin}")

        logger.info(
            "[CodexClient] model=%s effort=%s max_images=%s bin=%s endpoint=%s",
            model_name, reasoning_effort, max_images, self.codex_bin,
            base_url or "hosted",
        )

    # -- prompt assembly -------------------------------------------------

    @staticmethod
    def _write_pil(img: Any, path: Path) -> bool:
        try:
            img.convert("RGB").save(path, format="PNG")
            return True
        except Exception as e:  # a client should not die on one unreadable image
            logger.debug("Skipping unwritable image: %s", e)
            return False

    def _flatten(
        self,
        messages: list[dict[str, Any]],
        images: Optional[Sequence[Any]],
        image_dir: Path,
    ) -> tuple[str, list[Path]]:
        """Render the message list as one prompt plus image files on disk.

        Images arrive two ways in this repository -- as a separate `images=` list of PIL
        objects and as `image_url` data-URI blocks inside the content
        (`_embed_images_in_messages`) -- so both are handled. They are numbered in order
        and referenced by filename in the prompt, so "Image 3" in the text still points
        at a specific attachment once the message structure is gone.
        """
        out: list[Path] = []
        for img in images or []:
            path = image_dir / f"image_{len(out) + 1:03d}.png"
            if self._write_pil(img, path):
                out.append(path)

        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(f"[{role}]\n{content}")
                continue
            chunk: list[str] = []
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    chunk.append(block.get("text", ""))
                elif block.get("type") == "image_url":
                    url = (block.get("image_url") or {}).get("url", "")
                    m = _DATA_URI_RE.match(url)
                    if not m:
                        continue
                    ext, payload = m.group(1), m.group(2)
                    path = image_dir / f"image_{len(out) + 1:03d}.{ext}"
                    try:
                        path.write_bytes(base64.b64decode(payload))
                    except Exception as e:
                        logger.debug("Skipping undecodable inline image: %s", e)
                        continue
                    out.append(path)
                    chunk.append(f"<attached image: {path.name}>")
            parts.append(f"[{role}]\n" + "\n".join(chunk))

        if out:
            names = ", ".join(p.name for p in out)
            parts.append(f"[system]\nAttached images, in order: {names}")
        # Keep the *last* N, so a truncation drops the oldest observation rather than the
        # current one.
        if self.max_images is not None and len(out) > self.max_images:
            logger.info("[CodexClient] truncating %d images to the last %d",
                        len(out), self.max_images)
            out = out[-self.max_images:]
        return "\n\n".join(parts), out

    # -- the ClientBase surface ------------------------------------------

    def generate_text(
        self,
        messages: list[dict[str, Any]],
        images: Optional[list[Any]] = None,
    ) -> str:
        """One call, behind the server gate; `_generate_once` is the call itself.

        Same contract as `CodexTurn.run`: with `CODEX_BASE_URL_FILE` set, a call that
        fails while the server is not answering waits for the file to name a live
        address, adopts it, and runs once more -- without spending the caller's retry
        budget. Without the gate the direct arm answered 69 questions in a row as
        index-0 defaults against a dead node (one run); the agent arms,
        which already had it, stopped cleanly and waited.
        """
        if self._address_file() is not None:
            self._adopt_published_address()
        try:
            return self._generate_once(messages, images)
        except Exception:
            if self._address_file() is None or self._server_answers(self.base_url):
                raise               # hosted, or the server is fine: the failure is the model's
            if not self._await_server():
                raise
            logger.warning("[CodexClient] re-running the call against the recovered server")
            return self._generate_once(messages, images)

    def _generate_once(
        self,
        messages: list[dict[str, Any]],
        images: Optional[list[Any]] = None,
    ) -> str:
        self._calls += 1
        workdir = Path(tempfile.mkdtemp(prefix="codex-client-"))
        throwaway: Path | None = None
        try:
            prompt, image_paths = self._flatten(messages, images, workdir)
            out_file = workdir / "last_message.txt"
            cmd = [
                self.codex_bin, "exec",
                "--json", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
            ]
            # -i is variadic, so it must be followed by a non-variadic flag, never by a
            # positional. See CodexTurn._args for the failure this ordering prevents.
            for image in image_paths:
                cmd += ["-i", str(image)]
            cmd += [
                "-m", self.default_model,
                "-c", f'model_reasoning_effort="{effort_for(self.base_url, self.reasoning_effort)}"',
                "-o", str(out_file),
                "-c", 'sandbox_mode="workspace-write"',
                # The same *external* tool surface as the memory arm's turns: the direct
                # arm may not see a web search or a connector the other arm cannot.
                *SAFE_CODEX_FLAGS,
                # But not the same *shell*. CodexTurn is an agent and its whole output is
                # what it writes to disk; this client is one prompt for one message, and
                # its caller parses that message (the action batch). Leave codex's exec
                # tools in its hands and the model does not answer, it *acts*: measured
                # on qwen3.8-27b, one question ran 66 shell commands in a single call --
                # dozens of `echo done`, then reading its own rollout out of $CODEX_HOME
                # and a `find / -xdev` sweep -- reaching 824,729 input tokens before the
                # timeout, and never producing the reply its caller was waiting for.
                # Disabling them turned the same prompt into 0 commands and exactly that
                # reply. The sandbox is not
                # what this protects: it held (nothing but the throwaway home and an
                # empty workspace was reachable). What it protects is the arm's meaning
                # -- a "direct, no memory" control that shells around for 400s is an
                # agent, and is not the control it is being averaged against.
                "-c", "features.shell_tool=false",
                "-c", "features.unified_exec=false",
                # And every other tool, for the same reason and by the same measurement:
                # this model reaches for whatever is left. With the shell gone it spent a
                # whole call on `update_plan` -- 221 todo-list updates, no answer. Closing
                # the plan tool and apply_patch leaves it nothing to do but reply.
                "-c", "features.plan_tool=false",
                "-c", "features.apply_patch=false",
            ]
            if self.base_url:
                cmd += [
                    "-c", "model_provider=local",
                    "-c", 'model_providers.local.name="local"',
                    "-c", f'model_providers.local.base_url="{self.base_url}"',
                    "-c", 'model_providers.local.wire_api="responses"',
                    "-c", 'model_providers.local.env_key="LOCAL_API_KEY"',
                ] + _metadata_args(self.context_window)
            cmd.append("-")

            env = os.environ.copy()
            if self.codex_home:
                env["CODEX_HOME"] = str(self.codex_home)
            elif not os.environ.get("CODEX_HOME"):
                # The bare-binary path with no home configured would fall back to
                # `~/.codex`: the personal AGENTS.md in every prompt, and the rollouts
                # written into the same sessions/ dir that an agent run under the same
                # default reads.
                # The wrapper already gives its stateless calls a throwaway home; this
                # is that rule applied when the wrapper is not in front. Removed in the
                # same `finally` as the workdir.
                throwaway = prepare_codex_home(
                    Path(tempfile.mkdtemp(prefix="codex-home-")),
                    hosted=self.base_url is None)
                env["CODEX_HOME"] = str(throwaway)
            env.setdefault("LOCAL_API_KEY", "EMPTY")
            self._sandbox_allow_env(env)
            # Every call is a fresh `codex exec` with nothing to resume, so the sandbox
            # wrapper gives it a throwaway CODEX_HOME (auth only, discarded with the call)
            # instead of a persistent per-episode one. See codex_sandbox.sh.
            env["CODEX_SANDBOX_STATELESS"] = "1"

            try:
                proc = subprocess.run(
                    cmd, cwd=workdir, input=prompt, env=env,
                    capture_output=True, text=True, timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as expired:
                # The one call worth reading is the one that hung, and it is the only one
                # with no transcript: events are written after `run` returns. Keep the
                # partial stream under its own name.
                if self.transcript_dir:
                    partial = expired.stdout or ""
                    if isinstance(partial, bytes):
                        partial = partial.decode(errors="replace")
                    stem = f"call_{self._calls:04d}.timeout"
                    (self.transcript_dir / f"{stem}.events.jsonl").write_text(
                        partial, encoding="utf-8")
                    (self.transcript_dir / f"{stem}.prompt.txt").write_text(
                        prompt, encoding="utf-8")
                    logger.error(
                        "[CodexClient] call %d timed out after %ds; %d events kept at "
                        "%s.events.jsonl", self._calls, self.timeout,
                        len(partial.splitlines()), stem,
                    )
                raise

            if self.transcript_dir:
                stem = self.transcript_dir / f"call_{self._calls:04d}"
                stem.with_suffix(".events.jsonl").write_text(proc.stdout, encoding="utf-8")
                stem.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
                if proc.stderr:
                    stem.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")

            stats = request_stats(proc.stdout)
            violated = {k: stats[k] for k in ("web_searches", "mcp_tool_calls", "subthreads") if stats[k]}
            if violated:
                raise SandboxViolation(
                    f"codex call {self._calls} used capabilities this channel must not have: "
                    f"{violated}; see {self.transcript_dir or 'the event stream'}."
                )

            if out_file.exists():
                reply = out_file.read_text(encoding="utf-8").strip()
                if reply:
                    return reply

            # No -o file means the turn failed; surface the CLI's own reason rather than
            # an empty string the caller would silently mis-parse. The evaluators retry
            # on an exception and record an empty response on a blank one, so raising is
            # what buys the retry.
            reasons = []
            for line in proc.stdout.splitlines():
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") in ("error", "turn.failed"):
                    raw = ev.get("message") or ev.get("error") or ""
                    reasons.append(raw.get("message", str(raw)) if isinstance(raw, dict) else str(raw))
            raise RuntimeError(
                f"codex exec produced no message (rc={proc.returncode}): "
                f"{reasons[-1] if reasons else proc.stderr[:300]}"
            )
        finally:
            # Always remove them: the prompt and events are already copied into
            # transcript_dir, and keeping the images (or the throwaway home) per call
            # would leave thousands of files in the node's tmpfs over a long run.
            shutil.rmtree(workdir, ignore_errors=True)
            if throwaway is not None:
                shutil.rmtree(throwaway, ignore_errors=True)
