"""The direct arm: a cua-lite gym agent that thinks with `codex exec`.

The model channel is ``model_channel.codex_client.CodexClient``, one Codex call per step
with the safety flags of the memory arm. The model replies with a JSON action batch,
which is parsed and clamped here and handed to ``env.step`` as canonical cua-lite tool
calls (``LiteDesktopActionSpace``).

Memoryless on purpose: each turn resends the instruction, a text log of every prior
action, and ONLY the current screenshot (no image history -- one screenshot per call
keeps the cost linear in steps). Nothing is carried as codex conversation state.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("gym_codex.agent")

from model_channel.codex_client import CodexClient

from gym_codex.actions import (
    ACTION_REFERENCE, GENERAL_RULES, TERMINATE_REFERENCE,
    last_json_block, parse_batch,
)

# The vocabulary, the action reference and the parser live in gym_codex/actions.py,
# shared with the memory arm.
SYSTEM_PROMPT = """You are operating a real Linux desktop through a GUI to complete a task. Each turn you receive the current screenshot; reply with the next action batch as JSON.

""" + ACTION_REFERENCE + """

""" + TERMINATE_REFERENCE + """

Reply format: first think briefly in plain text (1-3 sentences), then give EXACTLY ONE fenced json block:
```json
{"actions": [ ... ]}
```
or the terminate form. Keep batches short (1-3 actions) so you can see the result before continuing.

""" + GENERAL_RULES + """{desktop_notes}"""

# Per-environment addenda appended to the system prompt via {desktop_notes}.
DESKTOP_NOTES = {
    "cua.bench.local.kicad": """

This desktop is XFCE with KiCad installed. Work inside KiCad's own editors (schematic editor etc.); use its menus and keyboard shortcuts (e.g. 'a' to add a symbol, 'w' to wire, ctrl+s to save). Save the project before terminating — scoring compares the resulting netlist.""",
}


class CodexGuiAgent:
    """Screenshot in, LiteDesktopActionSpace tool calls out, through `codex exec`.

    ``predict(instruction, screenshot_png) -> (reply_text, tool_calls, done)`` where
    ``tool_calls`` is ready for ``env.step`` and ``done`` marks a terminate/response
    turn. Parse failures return a no-op with corrective feedback queued for the next
    turn rather than raising: a malformed reply is a model behaviour to measure, not a
    harness crash.
    """

    def __init__(self, model: str = "gpt-5.6-sol", effort: str = "low",
                 codex_bin: str | None = None, transcript_dir: str | None = None,
                 timeout: int | None = None, env_id: str | None = None,
                 base_url: str | None = None, cli: str = "codex") -> None:
        # Literal-brace-safe substitution (the prompt is full of JSON examples).
        self.system_prompt = SYSTEM_PROMPT.replace(
            "{desktop_notes}", DESKTOP_NOTES.get(env_id or "", ""))
        kwargs: dict[str, Any] = dict(
            model_name=model, reasoning_effort=effort,
            codex_bin=codex_bin, transcript_dir=transcript_dir,
            max_images=1,
            # An OpenAI-compatible endpoint instead of the account's hosted models
            # (OpenRouter, a local server); None keeps the ChatGPT-auth path.
            base_url=base_url,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        if cli == "claude":
            # Anthropic models through Claude Code, with no tools at all
            # (model_channel/claude_client.py); the prompt is CodexClient's own rendering.
            from model_channel.claude_client import ClaudeClient
            kwargs.pop("codex_bin")
            self.client = ClaudeClient(**kwargs)
        elif cli == "codex":
            self.client = CodexClient(**kwargs)
        else:
            raise ValueError(f"unknown cli {cli!r} (codex|claude)")
        self.action_log: list[str] = []   # one compact line per turn, resent as text
        self._pending_feedback: str | None = None
        self._call_seq = 0

    def reset(self) -> None:
        self.action_log = []
        self._pending_feedback = None

    def add_feedback(self, msg: str) -> None:
        """Queue env-side feedback (action errors, tool text) for the next turn."""
        msg = msg.strip()
        if not msg:
            return
        self._pending_feedback = (
            f"{self._pending_feedback} | {msg}" if self._pending_feedback else msg)[:1500]

    # -- turn ----------------------------------------------------------------------

    def predict(self, instruction: str, screenshot_png: bytes,
                step_idx: int, max_steps: int) -> tuple[str, list[dict], bool]:
        user_lines = [f"TASK: {instruction}", f"STEP: {step_idx + 1} of at most {max_steps}"]
        if self.action_log:
            user_lines.append("PREVIOUS ACTIONS (oldest first):")
            user_lines.extend(f"  {i + 1}. {a}" for i, a in enumerate(self.action_log))
        else:
            user_lines.append("This is the first step; the screenshot shows the initial state.")
        if self._pending_feedback:
            user_lines.append(f"FEEDBACK ON YOUR LAST REPLY: {self._pending_feedback}")
            self._pending_feedback = None
        user_lines.append("Current screenshot attached. What next?")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n".join(user_lines)},
        ]
        reply = self.client.generate_text(messages, images=[screenshot_png])
        return (reply, *self._parse(reply))

    # -- parsing -------------------------------------------------------------------

    def _tool_call(self, name: str, args: dict) -> dict:
        self._call_seq += 1
        return {
            "id": f"call_{self._call_seq:04d}",
            "type": "function",
            "function": {"name": name, "arguments": args},
        }

    def _parse(self, reply: str) -> tuple[list[dict], bool]:
        pb = parse_batch(last_json_block(reply), self._tool_call)
        if pb.feedback:
            self._pending_feedback = pb.feedback
        self.action_log.append(pb.log_line)
        return pb.calls, pb.done
