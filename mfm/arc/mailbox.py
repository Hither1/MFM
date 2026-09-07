"""The actuator's transport: request files in, response files out.

Upstream's agent reached its broker over HTTP. Here the coding agent's commands run in
its CLI's sandbox, which gives them the workspace to write in and no network, so the
shim (`act.py`) drops a request file under `<workspace>/.act/` and the harness answers
beside it. One thread here watches the directory and serves one request at a time,
in arrival order, through a handler the benchmark's bridge supplies -- and blocks in
it for as long as the batch takes to play, the way the model thread blocks inside
VISTA's `play`. Every request and its answer are appended to `.act/calls.jsonl`, the
record of what the model asked the actuator for.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class MailboxServer:
    def __init__(self, directory: Path, handler: Handler, poll: float = 0.2) -> None:
        self.dir = Path(directory)
        self.handler = handler
        self.poll = poll
        self.served = 0
        self.by_command: dict[str, int] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="arc-mailbox", daemon=True)

    def start(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def _pending(self) -> list[Path]:
        try:
            names = [p for p in self.dir.iterdir()
                     if p.name.startswith("req-") and p.name.endswith(".json")]
        except OSError:
            return []
        # The id is `<time_ns>-<pid>`: arrival order is name order.
        return sorted(names, key=lambda p: p.name)

    def _run(self) -> None:
        while not self._stop.is_set():
            pending = self._pending()
            if not pending:
                time.sleep(self.poll)
                continue
            for path in pending:
                if self._stop.is_set():
                    return
                self._serve(path)

    def _serve(self, path: Path) -> None:
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            request = {"id": path.name[4:-5], "cmd": "?", "error": str(exc)}
        rid = str(request.get("id") or path.name[4:-5])
        started = time.time()
        try:
            reply = self.handler(request)
        except Exception as exc:  # the handler's failure is the agent's error text
            reply = {"stdout": "", "stderr": f"act: harness error: {exc}", "rc": 3}
        reply = {"stdout": str(reply.get("stdout", "")), "stderr": str(reply.get("stderr", "")),
                 "rc": int(reply.get("rc", 0))}
        tmp = self.dir / f"res-{rid}.tmp"
        tmp.write_text(json.dumps(reply), encoding="utf-8")
        os.replace(tmp, self.dir / f"res-{rid}.json")
        try:
            path.unlink()
        except OSError:
            pass
        self.served += 1
        cmd = str(request.get("cmd", "?"))
        self.by_command[cmd] = self.by_command.get(cmd, 0) + 1
        with (self.dir / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": rid, "at": started, "seconds": round(time.time() - started, 2),
                                "request": request, "reply": reply}) + "\n")
