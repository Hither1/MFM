#!/usr/bin/env python3
"""A `codex app-server --stdio` stand-in for the VISTA tests.

Speaks the subset of the app-server protocol `mfm.vista.runner` uses, and plays a script
(FAKE_APPSERVER_SCRIPT, JSONL) in which each line is what "the model" does in one turn:

    {"message": "I expect ...", "calls": [{"tool": "play", "arguments": {...}},
                                          {"tool": "write_guide", "arguments": {...}}]}

A `turn/start` consumes the next line: the message is emitted as an agentMessage, then
each tool call is issued as an `item/tool/call` request and its response awaited (with
`turn/steer` answered in between), then the turn completes. A turn whose prompt asks for
the compact checkpoint (the harness's CHECKPOINT_PROMPT) consumes no line: the fake calls
`save_compact_checkpoint` with canned notes and completes. A `turn/interrupt` completes
the active turn as interrupted and drops the rest of its calls (an inspect's images come
back as a new turn, which consumes the next line). When the script is exhausted the fake
holds the turn open until stdin closes, the way a model that never answers would.

Every request received and every tool response text (images reduced to their size) is
appended to FAKE_APPSERVER_CALLS so a test can pin what the model was handed.
"""
from __future__ import annotations

import json
import os
import sys
import threading

script_path = os.environ["FAKE_APPSERVER_SCRIPT"]
calls_path = os.environ["FAKE_APPSERVER_CALLS"]
idx_path = script_path + ".idx"
home = os.environ.get("CODEX_HOME", "")

_out_lock = threading.Lock()
_threads = 0
_turns = 0
_calls = 0


def record(kind: str, payload: dict) -> None:
    with open(calls_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, **payload}, sort_keys=True, default=str) + "\n")


def send(msg: dict) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def shrink(value):
    if isinstance(value, dict):
        return {k: shrink(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shrink(v) for v in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        return f"<image {len(value)} b64 chars>"
    return value


def next_line():
    lines = [l for l in open(script_path, encoding="utf-8").read().splitlines() if l.strip()]
    try:
        i = int(open(idx_path).read().strip() or 0)
    except FileNotFoundError:
        i = 0
    if i >= len(lines):
        return None
    open(idx_path, "w").write(str(i + 1))
    return json.loads(lines[i])


def read_message():
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    return json.loads(line) if line else {}


class Server:
    def __init__(self) -> None:
        self.thread_id = None
        self.turn_id = None
        self.interrupted = False
        self.hooks_trusted = False
        self.rpc = 100

    def hooks(self, cwd):
        path = os.path.join(home, "hooks.json")
        if not os.path.exists(path):
            return []
        return [{"key": f"{path}:pre_compact:0:0", "eventName": "preCompact", "handlerType": "command",
                 "command": "sh .codex/pre_compact_checkpoint.sh", "enabled": True,
                 "sourcePath": path, "currentHash": "sha256:fake",
                 "trustStatus": "trusted" if self.hooks_trusted else "untrusted"}]

    def handle_request(self, msg):
        """A client request: answered here. Returns True when the loop should stop."""
        global _threads, _turns
        rid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        record("request", {"method": method, "params": shrink(params)})
        if method == "initialize":
            send({"id": rid, "result": {"userAgent": "fake/0.0", "codexHome": home}})
        elif method == "hooks/list":
            send({"id": rid, "result": {"data": [{"cwd": c, "hooks": self.hooks(c), "warnings": [], "errors": []}
                                                 for c in params.get("cwds", [])]}})
        elif method == "config/batchWrite":
            self.hooks_trusted = True
            send({"id": rid, "result": {"status": "ok"}})
        elif method == "thread/start":
            # Numbered across processes: every segment is a new app-server, and a
            # fresh thread must not reuse an old id (the runner checks it does not).
            counter = script_path + ".threads"
            try:
                _threads = int(open(counter).read().strip() or 0)
            except FileNotFoundError:
                _threads = 0
            _threads += 1
            open(counter, "w").write(str(_threads))
            self.thread_id = f"thread-{_threads}"
            send({"id": rid, "result": {"thread": {"id": self.thread_id}}})
        elif method == "thread/resume":
            self.thread_id = params["threadId"]
            send({"id": rid, "result": {"thread": {"id": self.thread_id}}})
        elif method == "turn/start":
            _turns += 1
            self.turn_id = f"turn-{_turns}"
            self.interrupted = False
            send({"id": rid, "result": {"turn": {"id": self.turn_id}}})
            send({"method": "turn/started", "params": {"threadId": self.thread_id, "turn": {"id": self.turn_id}}})
            text = " ".join(i.get("text", "") for i in params.get("input", []) if i.get("type") == "text")
            images = sum(1 for i in params.get("input", []) if i.get("type") == "image")
            record("turn", {"turn": self.turn_id, "thread": self.thread_id, "images": images, "text": text})
            return self.run_turn(text)
        elif method == "turn/steer":
            record("steer", {"turn": params.get("expectedTurnId"),
                             "input": shrink(params.get("input"))})
            send({"id": rid, "result": {"turnId": params.get("expectedTurnId")}})
        elif method == "turn/interrupt":
            send({"id": rid, "result": {}})
            self.interrupted = True
            send({"method": "turn/completed", "params": {"threadId": self.thread_id,
                                                          "turn": {"id": params.get("turnId"), "status": "interrupted"}}})
        else:
            send({"id": rid, "error": {"code": -32601, "message": f"unsupported {method}"}})
        return False

    def call_tool(self, tool, arguments):
        """Issue one tool call and wait for its response, serving requests meanwhile.
        Returns the response, or None when the turn was interrupted first."""
        global _calls
        _calls += 1
        call_id = f"call-{_calls}"
        self.rpc += 1
        rid = self.rpc
        send({"id": rid, "method": "item/tool/call",
              "params": {"threadId": self.thread_id, "turnId": self.turn_id, "callId": call_id,
                         "namespace": "game", "tool": tool, "arguments": arguments}})
        while True:
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("id") == rid and "method" not in msg:
                result = msg.get("result") or {}
                text = "".join(c.get("text", "") for c in result.get("contentItems", []))
                record("tool_response", {"tool": tool, "call_id": call_id, "success": result.get("success"),
                                         "text": text})
                send({"method": "item/completed", "params": {"threadId": self.thread_id, "turnId": self.turn_id,
                                                              "item": {"type": "dynamicToolCall", "id": call_id}}})
                return msg
            if msg.get("method"):
                self.handle_request(msg)
                if self.interrupted:
                    return None

    def run_turn(self, prompt: str) -> bool:
        if "save_compact_checkpoint" in prompt and "Call save_compact_checkpoint" in prompt:
            line = {"message": "checkpointing",
                    "calls": [{"tool": "save_compact_checkpoint",
                               "arguments": {"guide": "GUIDE after checkpoint: the world so far.",
                                             "working_memory": "WORKING: continue the plan."}}]}
        else:
            line = next_line()
        if line is None:
            # Script exhausted: hold the turn open until the client goes away.
            while read_message() is not None:
                pass
            sys.exit(0)
        if line.get("message"):
            send({"method": "item/completed", "params": {"threadId": self.thread_id, "turnId": self.turn_id,
                                                          "item": {"type": "agentMessage", "id": f"msg-{_turns}",
                                                                   "text": line["message"]}}})
        for call in line.get("calls", []):
            resp = self.call_tool(call["tool"], call.get("arguments", {}))
            if resp is None or self.interrupted:
                return False
            # An inspect's images arrive as a fresh turn started by the client; the
            # client interrupts this one first, which the loop above sees.
            if call["tool"] == "inspect":
                while not self.interrupted:
                    msg = read_message()
                    if msg is None:
                        sys.exit(0)
                    if msg.get("method"):
                        self.handle_request(msg)
                return False
        send({"method": "thread/tokenUsage/updated",
              "params": {"threadId": self.thread_id, "turnId": self.turn_id,
                         "tokenUsage": {"last": {"inputTokens": 1000 * _turns, "cachedInputTokens": 0,
                                                 "outputTokens": 50, "reasoningOutputTokens": 10}}}})
        send({"method": "turn/completed", "params": {"threadId": self.thread_id,
                                                      "turn": {"id": self.turn_id, "status": "completed"}}})
        return False

    def serve(self) -> None:
        while True:
            msg = read_message()
            if msg is None:
                return
            if msg.get("method"):
                self.handle_request(msg)


if __name__ == "__main__":
    Server().serve()
