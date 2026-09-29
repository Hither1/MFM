"""`transformers serve`, made tolerant of the extra fields the Codex CLI sends.

Recovered from MineExplorer commit dad01c4^ ("Retire the transformers-serve shim"),
which deleted it when that project moved to vLLM. Its removal note is worth repeating,
because it is why this file exists rather than being rewritten: "it still worked, and
code that still works is exactly what gets picked up by accident later." MCU cannot use
vLLM at all -- every CUDA-12 build needs a newer glibc than this cluster's RHEL8 (2.28)
and every build old enough for the OS is CUDA 13, which needs a newer driver than 575 --
so the path MineExplorer retired is the one left open here.

Verified against transformers 5.9.0: every patch target below still exists.

Three incompatibilities, each of which kills a run on turn one:

1. Codex posts `client_metadata` on every `/v1/responses` request. Transformers
   validates the body against the OpenAI params TypedDict and rejects *any* unrecognised
   key with a 422, so the request dies before the model is consulted:

       422 Unprocessable Entity: {"detail":"Unexpected fields in the request: {'client_metadata'}"}

   Transformers already has an "ignore, don't reject" path (`_unused_fields`), so
   tolerance is the maintainers' own intent for fields it does not implement -- the list
   simply predates this client. Rather than edit site-packages, drop unknown keys here
   and log each one, so anything Codex adds in future shows up in the server log instead
   of silently changing behaviour.

2. Qwen's chat template accepts only system/user/assistant/tool and raises
   `Unexpected message role.` on anything else. The Responses API uses `developer` where
   chat completions used `system`, and transformers passes item roles through verbatim.

3. Codex supplies both `instructions` (which transformers prepends as system) and a
   `developer` item, so aliasing alone leaves two system messages and the template then
   raises `System message must be at the beginning.` They have to be folded into one.

Usage is identical to the real CLI:

    python scripts/serve_qwen_for_codex.py serve <model> --host ... --port ...
"""

import os
import sys

from transformers.cli.serving.response import ResponseHandler
from transformers.cli.serving.utils import BaseHandler
from transformers.cli.transformers import main

_ROLE_ALIASES = {"developer": "system"}

# 4. Codex sends no output cap, and transformers floors the default at 1024:
#
#     utils.py:1160  if generation_config.max_new_tokens is None or ... < 1024:
#     utils.py:1161      generation_config.max_new_tokens = 1024
#
# 1024 tokens does not survive contact with a thinking model. Measured on the first
# Qwen3.8 attempt: every turn stopped at exactly 1024 output tokens, mid-deliberation,
# before it could emit the tool call that writes actions.json -- and the model diagnosed
# itself in its own reasoning channel ("The previous response was cut off midway",
# "I've been repeatedly failing to output a valid actions.json"). Seven turns, zero
# actions, and the run looked like a model that could not follow the contract when it
# was a server default truncating it.
#
# `max_output_tokens` is the Responses API's own field (response.py:757) and codex has
# no key to set it -- it ignores max_tokens by design -- so the server side is the only
# place this can be fixed, exactly as serve_vllm.sh had to pin it there too.
#
# 8192 rather than vLLM's 16384: this path decodes at roughly 5 tok/s (plain
# transformers generate, sdpa, no CUDA graphs), so the cap is also a per-turn time
# budget. 8192 bounds a runaway near 27 minutes while clearing the measured p90 of
# ~1933 tokens fourfold. Raise it with TF_MAX_OUTPUT_TOKENS if turns start truncating
# again -- the tell is output_tokens landing on the cap exactly.
_MAX_OUTPUT_TOKENS = int(os.environ.get("TF_MAX_OUTPUT_TOKENS", 8192))

_original_validate = BaseHandler._validate_request
_original_normalize = ResponseHandler._normalize_input
_reported: set[str] = set()


def _validate_leniently(self, body: dict) -> None:
    if body.get("max_output_tokens") is None:
        body["max_output_tokens"] = _MAX_OUTPUT_TOKENS
        if "max-output-tokens" not in _reported:
            _reported.add("max-output-tokens")
            print(f"[codex-shim] setting max_output_tokens={_MAX_OUTPUT_TOKENS} "
                  f"(server default floors at 1024, which truncates thinking)", flush=True)
    valid = getattr(self._valid_params_class, "__mutable_keys__", None)
    if valid:
        for key in set(body) - set(valid):
            body.pop(key, None)
            if key not in _reported:
                _reported.add(key)
                print(f"[codex-shim] dropping unsupported request field: {key!r}", flush=True)
    return _original_validate(self, body)


BaseHandler._validate_request = _validate_leniently


def _as_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict):
            parts.append(block.get("text") or block.get("content") or "")
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(p for p in parts if p)


def _normalize_input_with_role_aliases(body: dict) -> list:
    messages = _original_normalize(body)

    for msg in messages:
        role = msg.get("role")
        if role in _ROLE_ALIASES:
            msg["role"] = _ROLE_ALIASES[role]
            if role not in _reported:
                _reported.add(role)
                print(f"[codex-shim] mapping message role {role!r} -> {msg['role']!r}", flush=True)

    system_parts = [_as_text(m.get("content")) for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    if len(system_parts) > 1 and "merged-system" not in _reported:
        _reported.add("merged-system")
        print(f"[codex-shim] merging {len(system_parts)} system messages into one leader", flush=True)
    if system_parts:
        return [{"role": "system", "content": "\n\n".join(p for p in system_parts if p)}] + rest
    return rest


ResponseHandler._normalize_input = staticmethod(_normalize_input_with_role_aliases)

if __name__ == "__main__":
    sys.exit(main())
