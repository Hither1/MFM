"""What the codex process is handed.

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

MCU = Path(__file__).resolve().parents[1] / "MCU"
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


def test_provider_auth_is_a_command_when_asked(monkeypatch):
    import json
    monkeypatch.delenv("CODEX_LOCAL_AUTH_COMMAND", raising=False)
    assert backend.provider_auth_args() == ["-c", 'model_providers.local.env_key="LOCAL_API_KEY"']
    cmd = ["sed", "-n", "s/^OPENROUTER_API_KEY=//p", "/abs/openrouter.env"]
    monkeypatch.setenv("CODEX_LOCAL_AUTH_COMMAND", json.dumps(cmd))
    got = backend.provider_auth_args()
    assert got[1] == 'model_providers.local.auth.command="sed"'
    assert json.loads(got[3].split("=", 1)[1]) == cmd[1:]
    args = backend.CodexTurn(Path("/tmp/x"), model="openai/gpt-6-astra",
                             base_url="https://openrouter.ai/api/v1")._args()
    assert not any("env_key" in a for a in args)
    assert any("auth.command" in a for a in args)
    with pytest.raises(ValueError):
        monkeypatch.setenv("CODEX_LOCAL_AUTH_COMMAND", '"not a list"')
        backend.provider_auth_args()


def test_codex_home_without_auth(tmp_path):
    import subprocess
    out = subprocess.run(
        ["bash", str(MCU / "scripts" / "codex-home.sh"), "t_none"],
        env={**os.environ, "MCU_CODEX_ROOT": str(tmp_path), "MCU_CODEX_AUTH": "none"},
        capture_output=True, text=True, check=True,
    ).stdout
    home = tmp_path / "t_none"
    assert "CODEX_RUNTIME_HOME=" in out and not (home / "auth.json").exists()
