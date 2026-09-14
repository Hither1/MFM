#!/usr/bin/env python3
"""A `claude -p` stand-in for the tests.

Plays FAKE_CLAUDE_SCRIPT (JSONL, one {"artifact","message","error","files"} per call) in
order, in cwd: writes `actions.json` and any files, prints the stream-json events the
backend parses (system/init echoing the session and the --tools in force, an assistant
text block, the closing result with usage), and records every invocation -- argv, cwd,
session, the prompt text, the order of the content blocks on stdin, and the relevant
environment -- to FAKE_CLAUDE_CALLS. Past the end of the script the last line repeats.
"""
import json
import os
import sys

argv = sys.argv[1:]


def opt(name):
    return argv[argv.index(name) + 1] if name in argv else None


raw = sys.stdin.read()
first = next((l for l in raw.splitlines() if l.strip()), "{}")
content = (json.loads(first).get("message") or {}).get("content") or []
prompt = "".join(b.get("text", "") for b in content if b.get("type") == "text")
blocks = [b.get("type") for b in content]
script = os.environ["FAKE_CLAUDE_SCRIPT"]
lines = [l for l in open(script).read().splitlines() if l.strip()]
idx_path = script + ".idx"
try:
    i = int(open(idx_path).read().strip() or 0)
except FileNotFoundError:
    i = 0
open(idx_path, "w").write(str(i + 1))
step = json.loads(lines[min(i, len(lines) - 1)]) if lines else {}
session = opt("--resume") or opt("--session-id")
tools = [t for t in (opt("--tools") or "").split(",") if t]
env = {k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIR", "MFM_IMAGE_TOOL", "CLAUDECODE")}
env["has_oauth_token"] = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as f:
    f.write(json.dumps({"i": i, "cwd": os.getcwd(), "argv": argv, "session": session,
                        "resume": opt("--resume") is not None, "tools": tools,
                        "effort": opt("--effort"), "model": opt("--model"),
                        "settings": json.loads(opt("--settings") or "{}"),
                        "prompt": prompt, "blocks": blocks, "env": env}) + "\n")
print(json.dumps({"type": "system", "subtype": "init", "session_id": session,
                  "model": opt("--model"), "tools": tools, "mcp_servers": []}))
if step.get("error"):
    print(json.dumps({"type": "result", "subtype": "error", "is_error": True,
                      "result": step["error"]}))
    sys.exit(1)
for rel, text in (step.get("files") or {}).items():
    os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
    open(rel, "w").write(text)
if step.get("artifact") is not None:
    art = step["artifact"]
    open("actions.json", "w").write(art if isinstance(art, str) else json.dumps(art))
message = step.get("message", "")
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": message}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": message,
                  "num_turns": 1, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 100, "cache_read_input_tokens": 900 * (i + 1),
                            "cache_creation_input_tokens": 10, "output_tokens": 50}}))
