#!/usr/bin/env python3
"""The VISTA tools as an MCP server for the Claude Code player (stdlib only).

Claude Code spawns this script (`--mcp-config`) and speaks MCP to it over stdio; every
`tools/call` is forwarded, one line of JSON, to the runner's unix socket
(`mfm/vista/claude_runner.py`), which executes it against the controller and answers
with the MCP content blocks -- the play result text, then the resulting frame as an
image block, which Claude Code shows the model directly (measured on 2.1.257:
the model read a 120x80 red frame back from a tool result), so none of the
steer / interrupt choreography the codex app-server needs. The tool list itself comes
from the runner at startup: this file knows nothing about the benchmark.

    python3 mcp_bridge.py /path/to/runner.sock

It runs wherever the CLI starts it -- inside claude_sandbox.sh that is a cleared
environment with the system Python -- so it imports nothing from `mfm`.
"""
from __future__ import annotations

import json
import socket
import sys
import threading

PROTOCOL_VERSION = "2025-06-18"


class RunnerLink:
    """One line-delimited JSON request/response channel to the runner, serialised:
    Claude Code may issue tool calls concurrently and the runner answers one at a time."""

    def __init__(self, path: str) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(path)
        self._reader = self._sock.makefile("r", encoding="utf-8")
        self._lock = threading.Lock()

    def request(self, message: dict) -> dict:
        with self._lock:
            self._sock.sendall((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
            line = self._reader.readline()
        if not line:
            raise RuntimeError("the runner closed the tool socket")
        return json.loads(line)


_out_lock = threading.Lock()


def _write(message: dict) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def _reply(request_id, result: dict) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: mcp_bridge.py <runner socket>\n")
        return 2
    link = RunnerLink(argv[1])
    tools = link.request({"op": "list"}).get("tools", [])

    def serve_call(request_id, params: dict) -> None:
        name, arguments = params.get("name"), params.get("arguments")
        try:
            answer = link.request({"op": "call", "id": str(request_id), "tool": name,
                                   "arguments": arguments if arguments is not None else {}})
            result = {"content": answer.get("content") or [{"type": "text", "text": ""}],
                      "isError": bool(answer.get("isError"))}
        except Exception as exc:  # noqa: BLE001 -- the model must hear about it
            result = {"content": [{"type": "text", "text": f"Tool call failed: {exc}"}], "isError": True}
        _reply(request_id, result)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        request_id, method = message.get("id"), message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            _reply(request_id, {"protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                                "capabilities": {"tools": {}},
                                "serverInfo": {"name": "game", "version": "1.0.0"}})
        elif method == "tools/list":
            _reply(request_id, {"tools": tools})
        elif method == "tools/call":
            threading.Thread(target=serve_call, args=(request_id, params), daemon=True).start()
        elif method == "ping":
            _reply(request_id, {})
        elif request_id is not None:
            _error(request_id, -32601, f"Unsupported method {method}")
        # notifications (initialized, cancelled, ...) take no answer
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
