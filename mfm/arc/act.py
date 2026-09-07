#!/usr/bin/env python3
"""`act`, as the agent sees it -- the one way it touches the environment.

A stdlib-only shim copied into the workspace (upstream: rig/client.py). Every command
is a request file under `.act/`; the harness answers with a response file, and what
came back is printed. `do` blocks for as long as the batch takes to play -- an entry is
tens to hundreds of ticks -- so a batch is one call, the way upstream's is one HTTP
request.

    ./act do ENTRY [ENTRY ...] [--plan "..."]     play entries in order until a milestone verifies
    ./act do --file plan.json [--plan "..."]      the same batch from a file: {"actions": [...]}
    ./act status                                  where you are: budget, milestones, inventory
    ./act view                                    the path of the current view (a PNG)

An ENTRY is a procedure call, `name(key=value, ...)`, or a JSON object -- either
{"procedure": "name", "args": {...}} or a raw action {"action": {...}, "repeat": N}.
Values in the call form are parsed as JSON where they can be (numbers, true/false,
quoted strings) and taken as plain strings otherwise, so `craft(item=stick)` and
`craft(item="stick")` are the same entry.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

MAILBOX = ".act"
POLL = 0.2
TIMEOUT = float(os.environ.get("ACT_TIMEOUT", "3600"))

_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", re.S)


class ActError(SystemExit):
    """Loud, non-zero exit. The message is the agent's feedback channel."""

    def __init__(self, message: str) -> None:
        super().__init__(f"act: {message}")


def _value(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        return text


def _split_args(body: str) -> list[str]:
    """Split `a=1, b="x, y", c=[1,2]` on the commas that separate arguments."""
    parts, depth, quote, cur = [], 0, None, []
    for ch in body:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def parse_entry(token: str) -> dict:
    """One ENTRY token -> the entry object the harness executes."""
    text = token.strip()
    if text.startswith("{"):
        try:
            entry = json.loads(text)
        except ValueError as exc:
            raise ActError(f"could not read {token!r} as JSON: {exc}") from None
        if not isinstance(entry, dict):
            raise ActError(f"{token!r} is not an entry object")
        return entry
    m = _CALL.match(text)
    if not m:
        raise ActError(f"{token!r} is neither `name(key=value, ...)` nor a JSON object")
    name, body = m.group(1), m.group(2)
    args = {}
    for part in _split_args(body):
        if "=" not in part:
            raise ActError(f"argument {part.strip()!r} in {token!r} needs `key=value`")
        key, val = part.split("=", 1)
        args[key.strip()] = _value(val)
    return {"procedure": name, "args": args}


def parse_do(argv: list[str]) -> dict:
    plan = None
    file = None
    tokens: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--plan":
            if i + 1 >= len(argv):
                raise ActError("--plan needs text")
            plan = argv[i + 1]
            i += 2
        elif a == "--file":
            if i + 1 >= len(argv):
                raise ActError("--file needs a path")
            file = argv[i + 1]
            i += 2
        else:
            tokens.append(a)
            i += 1
    entries = [parse_entry(t) for t in tokens]
    if file:
        try:
            data = json.loads(open(file, encoding="utf-8").read())
        except OSError as exc:
            raise ActError(f"could not read {file}: {exc}") from None
        except ValueError as exc:
            raise ActError(f"{file} is not JSON: {exc}") from None
        batch = data.get("actions") if isinstance(data, dict) else data
        if not isinstance(batch, list) or not all(isinstance(e, dict) for e in batch):
            raise ActError(f'{file} must hold {{"actions": [entry, ...]}}')
        entries = batch + entries
    if not entries:
        raise ActError("no entries given")
    return {"actions": entries, "plan": plan}


def call(request: dict) -> dict:
    os.makedirs(MAILBOX, exist_ok=True)
    rid = f"{time.time_ns()}-{os.getpid()}"
    request = {"id": rid, "argv": sys.argv[1:], **request}
    tmp = os.path.join(MAILBOX, f"req-{rid}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(request, f)
    os.replace(tmp, os.path.join(MAILBOX, f"req-{rid}.json"))
    res = os.path.join(MAILBOX, f"res-{rid}.json")
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if os.path.exists(res):
            with open(res, encoding="utf-8") as f:
                reply = json.load(f)
            os.unlink(res)
            return reply
        time.sleep(POLL)
    raise ActError(f"no answer from the harness in {TIMEOUT:.0f}s -- is the episode over?")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "do":
        request = {"cmd": "do", **parse_do(rest)}
    elif cmd in ("status", "view"):
        if rest:
            raise ActError(f"{cmd} takes no arguments")
        request = {"cmd": cmd}
    else:
        raise ActError(f"unknown command {cmd!r} -- do, status or view")
    reply = call(request)
    sys.stdout.write(reply.get("stdout", ""))
    err = reply.get("stderr", "")
    if err:
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    return int(reply.get("rc", 0))


if __name__ == "__main__":
    sys.exit(main())
