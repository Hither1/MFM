#!/usr/bin/env python3
"""A `codex exec` stand-in for the pin tests.

Plays FAKE_CODEX_SCRIPT (JSONL, one {"artifact","message","error","files"} per call) in
order, in cwd, the way the real binary would: writes `actions.json` (or nothing), writes
the `-o` message file, emits the `--json` event lines the backends parse, and records
every invocation -- argv, cwd, attached images, resume, the prompt on stdin, and the
codex-relevant environment -- to FAKE_CODEX_CALLS so a test can pin what the model was
handed. Past the end of the script the last line repeats.
"""
import json
import os
import sys

argv = sys.argv[1:]
prompt = sys.stdin.read()
out = argv[argv.index("-o") + 1] if "-o" in argv else None
images = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
resume = "resume" in argv
script = os.environ["FAKE_CODEX_SCRIPT"]
lines = [l for l in open(script).read().splitlines() if l.strip()]
idx_path = script + ".idx"
try:
    i = int(open(idx_path).read().strip() or 0)
except FileNotFoundError:
    i = 0
open(idx_path, "w").write(str(i + 1))
step = json.loads(lines[min(i, len(lines) - 1)]) if lines else {}
env = {k: os.environ.get(k) for k in ("CODEX_HOME", "LOCAL_API_KEY", "CODEX_SANDBOX_ALLOW")}
with open(os.environ["FAKE_CODEX_CALLS"], "a") as f:
    f.write(json.dumps({"i": i, "cwd": os.getcwd(), "argv": argv, "images": images,
                        "resume": resume, "prompt": prompt, "env": env}) + "\n")
print(json.dumps({"type": "thread.started",
                  "thread_id": "0f0f0f0f-0000-4000-8000-%012d" % (i // 1000)}))
if step.get("error"):
    print(json.dumps({"type": "error", "message": step["error"]}))
    sys.exit(1)
for rel, text in (step.get("files") or {}).items():
    os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
    open(rel, "w").write(text)
if step.get("artifact") is not None:
    art = step["artifact"]
    open("actions.json", "w").write(art if isinstance(art, str) else json.dumps(art))
if out:
    open(out, "w").write(step.get("message", ""))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}))
print(json.dumps({"type": "turn.completed",
                  "usage": {"input_tokens": 1000 * (i + 1), "cached_input_tokens": 0,
                            "output_tokens": 50}}))
