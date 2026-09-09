#!/usr/bin/env python3
"""A coding-agent CLI stand-in for the arc tests: `codex exec --json` as the arc arm
spawns it, playing a script instead of a model.

FAKE_ARC_SCRIPT is JSONL, one line per SESSION the loop starts (the first with the task
prompt, the rest with the resume prompt): {"commands": [...], "message": "..."}. Each
command runs through the shell in the workspace the way the model's would -- `./act do`,
`grep`, `cat`, writing files -- and is emitted as the `command_execution` item codex
would report; a command `view <path>` stands in for the model's image tool and is
emitted as a `view_image` item. The session ends with an agent message and a
`turn.completed`, then exits 0 -- a model that stopped -- so the loop's resume runs.
Past the last line the fake holds (sleeps until killed), the way a session still
thinking would, so the harness's close is what ends it.

Every session's argv, prompt and each command's output go to FAKE_ARC_CALLS.
"""
import json
import os
import subprocess
import sys
import time

argv = sys.argv[1:]
prompt = argv[-1] if argv else ""
script = os.environ["FAKE_ARC_SCRIPT"]
calls = os.environ["FAKE_ARC_CALLS"]
idx_path = script + ".idx"
lines = [l for l in open(script, encoding="utf-8").read().splitlines() if l.strip()]
try:
    i = int(open(idx_path).read().strip() or 0)
except FileNotFoundError:
    i = 0
open(idx_path, "w").write(str(i + 1))


def emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


emit({"type": "thread.started", "thread_id": "0f0f0f0f-0000-4000-8000-%012d" % i})
record = {"session": i, "argv": argv, "prompt": prompt, "cwd": os.getcwd(), "results": []}
if i >= len(lines):
    record["held"] = True
    with open(calls, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    while True:  # script exhausted: hold until the harness closes the session
        time.sleep(0.5)

session = json.loads(lines[i])
for cmd in session.get("commands", []):
    if cmd.startswith("view "):
        # The path may be a shell expression (`view $(./act view)`): let the shell say.
        path = subprocess.run(f"printf %s {cmd[5:].strip()}", shell=True, cwd=os.getcwd(),
                              capture_output=True, text=True).stdout.strip()
        ok = os.path.exists(path)
        record["results"].append({"cmd": cmd, "rc": 0 if ok else 1, "out": "" if ok else "no such image"})
        emit({"type": "item.completed", "item": {"type": "view_image", "path": path}})
        continue
    p = subprocess.run(cmd, shell=True, cwd=os.getcwd(), capture_output=True, text=True)
    out = p.stdout + (("[stderr] " + p.stderr) if p.stderr else "")
    record["results"].append({"cmd": cmd, "rc": p.returncode, "out": out})
    emit({"type": "item.completed", "item": {"type": "command_execution", "command": cmd,
                                              "aggregated_output": out, "exit_code": p.returncode}})
emit({"type": "item.completed", "item": {"type": "agent_message", "text": session.get("message", "")}})
emit({"type": "turn.completed", "usage": {"input_tokens": 1000 * (i + 1), "cached_input_tokens": 0,
                                          "output_tokens": 50, "reasoning_output_tokens": 10}})
with open(calls, "a", encoding="utf-8") as f:
    f.write(json.dumps(record) + "\n")
