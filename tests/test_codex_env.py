"""What the codex process is handed, 2026-09-09.

Measured on codex 0.153: the model's exec cells inherit codex's whole environment, and
`shell_environment_policy.exclude` does not remove anything; the shell snapshot codex writes
at thread start is `declare -x` of every variable and survives an unclean exit. So the
backend drops secret-named variables before spawning codex and turns the snapshot off.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

MCU = Path(os.environ.get("MFM_MCU_ROOT", Path(__file__).resolve().parents[1] / "MCU"))
if str(MCU) not in sys.path:
    sys.path.insert(0, str(MCU))

backend = pytest.importorskip("mcu_worldmodel.codex_backend")


def test_secret_named_variables_are_dropped():
    env = {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "x", "WANDB_API_KEY": "y", "HF_TOKEN": "z",
        "OPENAI_API_KEY": "k", "CLAUDE_CODE_MESSAGING_TOKEN": "t", "AWS_SECRET_ACCESS_KEY": "s",
        "DB_PASSWORD": "p", "MAX_THINKING_TOKENS": "1",
        "PATH": "/bin", "HOME": "/h", "TOKIO_WORKER_THREADS": "8",
        "LOCAL_API_KEY": "EMPTY", "CODEX_AUTO_COMPACT_TOKEN_LIMIT": "100000", "CODEX_HOME": "/c",
    }
    kept, dropped = backend.scrub_env(env)
    assert dropped == sorted([
        "AWS_SECRET_ACCESS_KEY", "CLAUDE_CODE_MESSAGING_TOKEN", "DB_PASSWORD",
        "GITHUB_PERSONAL_ACCESS_TOKEN", "HF_TOKEN", "MAX_THINKING_TOKENS", "OPENAI_API_KEY",
        "WANDB_API_KEY",
    ])
    # what codex itself reads stays
    assert set(kept) == {"PATH", "HOME", "TOKIO_WORKER_THREADS", "LOCAL_API_KEY",
                         "CODEX_AUTO_COMPACT_TOKEN_LIMIT", "CODEX_HOME"}
    assert kept["LOCAL_API_KEY"] == "EMPTY"


def test_snapshot_is_off_in_every_turn():
    flags = list(backend.SAFE_CODEX_FLAGS)
    assert "features.shell_snapshot=false" in flags
    args = backend.CodexTurn(Path("/tmp/x"), model="gpt-5.6-sol")._args()
    assert "features.shell_snapshot=false" in args
