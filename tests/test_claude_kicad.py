"""The KiCad arms on the Claude Code CLI (`run_eval.py --cli claude`).

Off, every arm is the codex arm it was. On: the prolong / mfm arms drive `claude -p`
through `prolong_search.claude_backend.ClaudeTurn` (CLAUDE.md, stream-json with the frame
after the text, Bash/Read/Write/Edit, a resumed session under our own uuid), the design
turn is its own Claude session at its own effort, and the direct arm runs with no tools.
`claude_sandbox.sh` keeps the model's reads inside the workspace and off the network.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "fake_claude.py"
WRAPPER = ROOT / "CUA-KiCad" / "prolong_search" / "claude_sandbox.sh"
sys.path.insert(0, str(ROOT / "CUA-KiCad"))
run_eval = pytest.importorskip("gym_codex.run_eval")

PNG = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes(32)
MODEL = "claude-opus-5"


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch):
    FAKE.chmod(FAKE.stat().st_mode | stat.S_IEXEC)
    script, calls = tmp_path / "fake_claude.jsonl", tmp_path / "fake_claude_calls.jsonl"
    script.write_text("")
    calls.write_text("")
    monkeypatch.setenv("CLAUDE_BIN", str(FAKE))
    monkeypatch.setenv("FAKE_CLAUDE_SCRIPT", str(script))
    monkeypatch.setenv("FAKE_CLAUDE_CALLS", str(calls))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "test-token")
    for k in ("CLAUDE_NATIVE_SANDBOX", "CLAUDE_AUTOCOMPACT", "CLAUDE_API_KEY_HELPER",
              "CLAUDE_SANDBOX_DENY_READ", "CLAUDE_SESSION_MAX_TURNS", "CLAUDE_MAX_CALLS"):
        monkeypatch.delenv(k, raising=False)

    class Handle:
        def reply(self, artifact=None, message="", error=None, files=None):
            with script.open("a") as f:
                f.write(json.dumps({"artifact": artifact, "message": message,
                                    "error": error, "files": files or {}}) + "\n")

        def recorded(self) -> list[dict]:
            return [json.loads(l) for l in calls.read_text().splitlines() if l.strip()]

    return Handle()


def _agent(tmp_path: Path, monkeypatch, kind: str, **kw):
    from gym_codex import memory_agents
    monkeypatch.setattr("time.sleep", lambda s: None)
    return memory_agents.make_agent(
        kind, workspace=tmp_path / "ws", model=MODEL, effort="low", max_steps=8,
        transcript_dir=tmp_path / "codex", codex_home=None, session_turns=None,
        base_url=None, cli="claude", **kw)


CLICK = {"actions": [{"action": "click", "coordinate": [500, 500]}]}


def test_prolong_logonly_runs_on_claude_code(tmp_path, fake_claude, monkeypatch):
    from prolong_search.claude_backend import ClaudeTurn
    agent = _agent(tmp_path, monkeypatch, "prolong-logonly")
    assert isinstance(agent.codex, ClaudeTurn)
    fake_claude.reply(CLICK, "Opening the editor.\n[PLAN]\nclick")
    fake_claude.reply({"terminate": {"status": "success"}}, "done")

    msg, calls, done = agent.predict("Draw an RC low-pass filter.", PNG, 0, 8)
    assert not done and calls[0]["function"]["name"] == "computer"
    msg, calls, done = agent.predict("Draw an RC low-pass filter.", PNG, 1, 8)
    assert done

    first, second = fake_claude.recorded()
    assert first["model"] == MODEL and first["effort"] == "low"
    assert first["tools"] == ["Bash", "Read", "Write", "Edit"]
    assert "--setting-sources" in first["argv"] and "project" in first["argv"]
    assert not first["resume"] and second["resume"] and second["session"] == first["session"]
    assert first["blocks"] == ["text", "image"], "the frame rides after the text block"
    assert first["cwd"] == second["cwd"] == str(agent.visible)
    assert first["env"]["MFM_IMAGE_TOOL"] == "Read"
    assert first["env"]["CLAUDE_CONFIG_DIR"].endswith("ws.claudehome")
    assert first["env"]["CLAUDECODE"] is None, "the launching session's identity is scrubbed"
    assert first["env"]["has_oauth_token"]
    deny = first["settings"]["permissions"]["deny"]
    assert any(d.startswith(f"Read({first['env']['CLAUDE_CONFIG_DIR']}") for d in deny)
    assert first["settings"]["autoCompactEnabled"] is False
    assert first["settings"]["autoMemoryEnabled"] is False

    claude_md = agent.visible / "CLAUDE.md"
    assert claude_md.exists(), "the log-only view keeps the system prompt file"
    text = claude_md.read_text()
    assert "view_image" not in text and "Read" in text
    assert not (agent.visible / "AGENTS.md").exists()

    audit = agent.audit()
    assert audit["cli"] == "claude" and audit["analyzer_turns"] == 2
    assert audit["sessions"] == 1 and audit["images_attached"] == 2
    assert audit["input_tokens"] > 0 and audit["cached_input_tokens"] > 0
    assert audit["log_only"] is True


def test_mfm_design_turn_runs_on_claude_code(tmp_path, fake_claude, monkeypatch):
    agent = _agent(tmp_path, monkeypatch, "mfm", design=True, design_effort="high",
                   conventions=True)
    intent = {"parts": [{"ref": "R1", "symbol": "Device:R", "value": "10k"}],
              "nets": [{"label": "GND", "pins": ["R1.2"]}]}
    fake_claude.reply(None, "Designed the filter.",
                      files={"design.md": "# Parts\nR1 Device:R 10k\n",
                             "intent.json": json.dumps(intent)})
    fake_claude.reply(CLICK, "Placing R1.\n[PLAN]\nclick")
    msg, calls, done = agent.predict("Design an RC low-pass filter.", PNG, 0, 8)
    assert calls[0]["function"]["name"] == "computer"

    design, act = fake_claude.recorded()
    assert design["effort"] == "high" and act["effort"] == "low"
    assert design["blocks"] == ["text"] and act["blocks"] == ["text", "image"]
    assert not design["resume"] and not act["resume"]
    assert design["session"] != act["session"], "the act thread does not resume the design's"
    assert "do not write ./actions.json" in design["prompt"]
    assert (agent.visible / "design.md").exists() and (agent.visible / "intent.json").exists()
    agent.finish(1.0, None)
    audit = agent.audit()
    assert audit["design"]["ok"] and audit["design"]["codex_calls"] == 1
    assert audit["design"]["parts"] == 1 and audit["design"]["effort"] == "high"
    assert audit["analyzer_turns"] == 1


def test_direct_arm_runs_on_claude_code_with_no_tools(tmp_path, fake_claude):
    from gym_codex.codex_gui_agent import CodexGuiAgent
    from prolong_search.codex_client import CodexClient
    agent = CodexGuiAgent(model=MODEL, effort="low", env_id="cua.bench.local.kicad",
                          transcript_dir=str(tmp_path / "codex"), timeout=60, cli="claude")
    assert type(agent.client).__name__ == "ClaudeClient"
    fake_claude.reply(None, 'Clicking.\n```json\n{"actions": [{"action": "click", '
                            '"coordinate": [10, 10]}]}\n```')
    reply, calls, done = agent.predict("Draw an RC filter.", PNG, 0, 5)
    assert calls[0]["function"]["name"] == "computer" and not done
    agent.predict("Draw an RC filter.", PNG, 1, 5)

    first, second = fake_claude.recorded()
    assert first["tools"] == [] and "--tools" in first["argv"]
    assert not second["resume"] and second["session"] != first["session"], "memoryless"
    # The same prompt text and attachments CodexClient renders for this turn.
    messages = [{"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": first["prompt"].split("[user]\n", 1)[1].split("\n\n[system]\nAttached")[0]}]
    d = tmp_path / "render"
    d.mkdir()
    ref = SimpleNamespace(_write_pil=CodexClient._write_pil, max_images=1)
    expected, paths = CodexClient._flatten(ref, messages, [PNG], d)
    assert first["prompt"] == expected
    assert first["blocks"] == ["text"] + ["image"] * len(paths)


def test_codex_stays_the_default(tmp_path, monkeypatch):
    from gym_codex import memory_agents
    from gym_codex.codex_gui_agent import CodexGuiAgent
    from prolong_search.codex_backend import CodexTurn
    monkeypatch.setattr("time.sleep", lambda s: None)
    agent = memory_agents.make_agent(
        "prolong-logonly", workspace=tmp_path / "ws", model="gpt-6-astra", effort="low",
        max_steps=8, transcript_dir=tmp_path / "codex", codex_home=str(tmp_path / "home"),
        session_turns=None, base_url=None)
    assert isinstance(agent.codex, CodexTurn) and agent.cli == "codex"
    assert type(CodexGuiAgent(model="gpt-6-astra").client).__name__ == "CodexClient"


def _args(**over):
    base = dict(agent="prolong-logonly", model=MODEL, effort="low", max_steps=200,
                codex_timeout=None, session_turns=None, codex_base_url=None,
                env_id="cua.bench.local.kicad")
    base.update(over)
    return SimpleNamespace(**base)


def test_cli_flag_reaches_the_agents_only_when_claude(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(run_eval, "make_agent", lambda kind, **kw: seen.update(kind=kind, **kw))
    run_eval._make_agent(_args(), tmp_path / "t")
    assert "cli" not in seen
    seen.clear()
    run_eval._make_agent(_args(cli="codex"), tmp_path / "t")
    assert "cli" not in seen
    seen.clear()
    run_eval._make_agent(_args(cli="claude", agent="mfm-carry"), tmp_path / "t")
    assert seen["cli"] == "claude"

    direct = {}
    monkeypatch.setattr(run_eval, "CodexGuiAgent", lambda **kw: direct.update(kw))
    run_eval._make_agent(_args(agent="direct"), tmp_path / "t")
    assert "cli" not in direct
    run_eval._make_agent(_args(agent="direct", cli="claude"), tmp_path / "t")
    assert direct["cli"] == "claude"

    assert run_eval._cli_error(_args()) is None
    assert run_eval._cli_error(_args(cli="claude")) is None
    assert run_eval._cli_error(_args(cli="claude", agent="vista")) is None   # mfm/vista/claude_runner.py
    assert "base-url" in run_eval._cli_error(_args(cli="claude", codex_base_url="http://x"))


def _bwrap_works() -> bool:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    return subprocess.run([bwrap, "--ro-bind", "/", "/", "true"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _bwrap_works(), reason="bwrap cannot create a namespace here")
def test_claude_sandbox_confines_reads_writes_and_network(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    secret = tmp_path / "reference.net"
    secret.write_text("SECRET-REFERENCE")
    lab_file = Path(__file__).resolve()      # on the lab filesystem, outside the workspace
    probe = (f"cat {secret} 2>&1; cat {lab_file} 2>&1 | head -1; "
             f"echo written > {ws}/inside.txt; echo nope > {tmp_path}/outside.txt 2>&1; "
             f"(exec 3<>/dev/tcp/1.1.1.1/80) 2>/dev/null && echo NET-OPEN || echo NET-CLOSED; "
             f"echo HOME=$HOME; echo TOKEN=${{CLAUDE_CODE_OAUTH_TOKEN:-unset}}")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env.update(CLAUDE_SANDBOX_EXEC="/bin/bash", CLAUDE_REAL_BIN="/bin/bash",
               CLAUDE_CODE_OAUTH_TOKEN="tok-123", CLAUDE_CONFIG_DIR=str(tmp_path / "ws.claudehome"))
    proc = subprocess.run([str(WRAPPER), "-c", probe], cwd=ws, env=env, capture_output=True,
                          text=True, timeout=60)
    out = proc.stdout
    assert "SECRET-REFERENCE" not in out
    assert "The KiCad arms on the Claude Code CLI" not in out and '"""' not in out.splitlines()[1:2]
    assert (ws / "inside.txt").read_text() == "written\n"
    assert not (tmp_path / "outside.txt").exists()
    assert "NET-CLOSED" in out
    assert f"HOME={tmp_path / 'ws.claudehome'}" in out
    # The credential survives --clearenv (a --setenv before it is wiped: "Not logged in").
    assert "TOKEN=tok-123" in out


def test_usage_limit_waits_and_resends_the_same_turn(tmp_path, fake_claude, monkeypatch):
    from prolong_search import claude_backend
    slept = []
    # subprocess polls with sub-second sleeps on the same module; keep the waits only.
    monkeypatch.setattr(claude_backend.time, "sleep", lambda s: s >= 1 and slept.append(s))
    monkeypatch.setenv("CLAUDE_QUOTA_WAIT", "600")
    (tmp_path / "ws").mkdir()
    turn = claude_backend.ClaudeTurn(tmp_path / "ws", model=MODEL)
    fake_claude.reply(error="You've reached your usage limit · resets 3am")
    fake_claude.reply(CLICK, "clicking")
    result = turn.run("go", images=())
    assert result["ok"] and json.loads(result["artifact"]) == CLICK
    assert slept == [600.0] and turn.calls == 1
    assert len(fake_claude.recorded()) == 2
    audit = turn.audit()
    assert audit["quota_hits"] == 1 and audit["quota_wait_s"] == 600


def test_usage_limit_gives_up_past_its_budget(tmp_path, fake_claude, monkeypatch):
    from prolong_search import claude_backend
    monkeypatch.setattr(claude_backend.time, "sleep", lambda s: None)
    monkeypatch.setenv("CLAUDE_QUOTA_WAIT", "600")
    monkeypatch.setenv("CLAUDE_QUOTA_WAIT_MAX", "1200")
    (tmp_path / "ws").mkdir()
    turn = claude_backend.ClaudeTurn(tmp_path / "ws", model=MODEL)
    fake_claude.reply(error="You've reached your usage limit")
    result = turn.run("go", images=())
    assert not result["ok"] and "usage limit" in result["error"]
    assert len(fake_claude.recorded()) == 3      # the first call and two waits' re-sends


@pytest.mark.parametrize("error", [
    "Not logged in · Please run /login",
    # the CLI's wording, missed by the pattern for 15 h of no-op turns.
    "Failed to authenticate. API Error: 401 OAuth access token has been revoked.",
])
def test_lost_credential_stops_the_run(tmp_path, fake_claude, monkeypatch, error):
    from prolong_search import claude_backend
    exits = []

    def fake_exit(code):
        exits.append(code)
        raise SystemExit(code)
    monkeypatch.setattr(claude_backend.os, "_exit", fake_exit)
    (tmp_path / "ws").mkdir()
    turn = claude_backend.ClaudeTurn(tmp_path / "ws", model=MODEL)
    fake_claude.reply(error="Not logged in · Please run /login")
    with pytest.raises(SystemExit):
        turn.run("go", images=())
    assert exits == [claude_backend.AUTH_EXIT_STATUS]
