"""`CodexClient.generate_text` on the Claude Code CLI, for the direct (memoryless) arm.

One fresh session per call and no tools at all (`--tools ""`): the reply is the whole
output channel, which is what the codex client arrives at by switching off codex's shell,
plan and patch tools. The prompt is built by `CodexClient._flatten` itself, so both CLIs
are handed the same text and the same image files for the same turn.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from model_channel.claude_backend import ClaudeTurn
from model_channel.codex_client import CodexClient

logger = logging.getLogger("model_channel.claude_client")


class ClaudeClient:
    """Screenshot + messages in, the model's reply out, through `claude -p`."""

    # The codex client's prompt and image rendering, reused rather than re-typed.
    _write_pil = staticmethod(CodexClient._write_pil)
    _flatten = CodexClient._flatten

    def __init__(self, model_name: str, reasoning_effort: str = "low",
                 transcript_dir: Optional[str] = None, max_images: Optional[int] = None,
                 timeout: int = 360, base_url: Optional[str] = None,
                 claude_bin: Optional[str] = None) -> None:
        self.default_model = model_name
        self.max_images = max_images
        self.timeout = timeout
        self._calls = 0
        self.workdir = Path(tempfile.mkdtemp(prefix="claude-client-"))
        # session_max_turns=1: every call after the first cold-starts, so no reply is
        # conditioned on an earlier one -- the direct arm's defining property.
        self.turn = ClaudeTurn(
            self.workdir, model=model_name, reasoning_effort=reasoning_effort,
            base_url=base_url, claude_bin=claude_bin, timeout=timeout,
            transcript_dir=Path(transcript_dir) if transcript_dir else None,
            tools=(), session_max_turns=1)

    def generate_text(self, messages: list[dict[str, Any]],
                      images: Optional[list[Any]] = None) -> str:
        self._calls += 1
        call_dir = self.workdir / f"call_{self._calls:04d}"
        call_dir.mkdir()
        try:
            prompt, image_paths = self._flatten(messages, images, call_dir)
            result = self.turn.run(prompt, images=image_paths, expect_artifact=False,
                                   timeout=self.timeout)
        finally:
            shutil.rmtree(call_dir, ignore_errors=True)
        if not result.get("ok"):
            raise RuntimeError(f"claude produced no message: {result.get('error')}")
        return result["message"]

    def audit(self) -> dict[str, Any]:
        return self.turn.audit()
