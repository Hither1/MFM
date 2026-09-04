"""Test setup shared by the pin tests.

The two submodules are put on sys.path so both repos' modules import as they do in
their own launchers. Every codex-related environment variable is cleared *before* any
of those modules import, because several read the environment at import time
(AUTO_COMPACT_TOKEN_LIMIT, DEFAULT_CONTEXT_WINDOW, the session age cap).
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MCU = ROOT / "MCU"
KICAD = ROOT / "CUA-KiCad"
PINS = ROOT / "tests" / "pins"
FAKE_CODEX = ROOT / "tests" / "fake_codex.py"

for repo in (MCU, KICAD):
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

_CODEX_ENV = [k for k in os.environ if k.startswith(("CODEX_", "PROLONG_", "FAKE_CODEX_"))]
for _k in _CODEX_ENV:
    os.environ.pop(_k, None)
# The pins are recorded against a fixed home so a derived `<workspace>.codexhome`
# never looks for a personal auth.json.
os.environ["HOME"] = str(Path(os.environ.get("MFM_TEST_HOME", "/nonexistent-home")))


def record_pins() -> bool:
    return os.environ.get("MFM_RECORD_PINS") == "1"


def pin_path(name: str) -> Path:
    return PINS / name


def check_pin(name: str, actual: str) -> None:
    """Compare `actual` to the recorded pin, or record it under MFM_RECORD_PINS=1."""
    path = pin_path(name)
    if record_pins():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    if not path.exists():
        pytest.fail(f"no recorded pin at {path}; run with MFM_RECORD_PINS=1 against the "
                    f"baseline code first")
    expected = path.read_text(encoding="utf-8")
    if expected != actual:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), actual.splitlines(), f"pin:{name}", "actual", lineterm="", n=2))
        pytest.fail(f"pin {name} changed:\n{diff[:6000]}")


@pytest.fixture
def fake_codex(tmp_path: Path):
    """Point CODEX_BIN at the fake and return a handle that scripts its replies."""
    FAKE_CODEX.chmod(FAKE_CODEX.stat().st_mode | stat.S_IEXEC)
    script = tmp_path / "fake_codex.jsonl"
    calls = tmp_path / "fake_codex_calls.jsonl"
    script.write_text("")
    calls.write_text("")
    os.environ["CODEX_BIN"] = str(FAKE_CODEX)
    os.environ["FAKE_CODEX_SCRIPT"] = str(script)
    os.environ["FAKE_CODEX_CALLS"] = str(calls)

    class Handle:
        def __init__(self):
            self.script, self.calls = script, calls

        def reply(self, artifact=None, message="", error=None, files=None):
            import json
            with self.script.open("a") as f:
                f.write(json.dumps({"artifact": artifact, "message": message,
                                    "error": error, "files": files or {}}) + "\n")

        def recorded(self) -> list[dict]:
            import json
            return [json.loads(l) for l in self.calls.read_text().splitlines() if l.strip()]

    yield Handle()
    for k in ("CODEX_BIN", "FAKE_CODEX_SCRIPT", "FAKE_CODEX_CALLS"):
        os.environ.pop(k, None)
