"""The exact argv the KiCad backend hands to `codex exec`, and the codex home policy,
for hosted and local models, on the first call and on a resumed one.
"""
from __future__ import annotations

import json
from pathlib import Path


from conftest import check_pin

LOCAL = "http://127.0.0.1:8000/v1"
SESSION = "0f0f0f0f-0000-4000-8000-000000000000"


def _kicad_turn(ws: Path, base_url):
    from prolong_search.codex_backend import CodexTurn
    return CodexTurn(ws, model="gpt-5.6-sol", base_url=base_url,
                     codex_home=ws.with_name(ws.name + ".home"))


def _snapshot(make, tmp_path: Path) -> str:
    rows = {}
    for label, base in (("hosted", None), ("local", LOCAL)):
        ws = tmp_path / f"ws_{label}"
        turn = make(ws, base)
        first = turn._args()
        turn.session_id = SESSION
        resumed = turn._args()
        norm = lambda a: [x.replace(str(tmp_path), "<tmp>") for x in a]
        rows[label] = {
            "first": norm(first), "resumed": norm(resumed),
            "codex_home": str(turn.codex_home).replace(str(tmp_path), "<tmp>")
                          if turn.codex_home else None,
            "codex_bin": turn.codex_bin,
            "timeout": turn.timeout,
            "session_max_turns": turn.session_max_turns,
            "context_window": turn.context_window,
        }
    return json.dumps(rows, indent=1)


def test_kicad_argv(tmp_path):
    check_pin("argv_kicad.json", _snapshot(_kicad_turn, tmp_path))

