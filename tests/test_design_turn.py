"""The KiCad design turn (`--design-turn`) and the conventions paragraph
(`--conventions`): off, the arm is the baseline; on, one design call at its own effort
precedes the first action turn and the prompt carries the notes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KICAD = Path(__file__).resolve().parents[1] / "CUA-KiCad"
sys.path.insert(0, str(KICAD))

run_eval = pytest.importorskip("gym_codex.run_eval")

PNG = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes(32)


def _agent(tmp_path: Path, monkeypatch, kind: str = "mfm", **kw):
    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    return memory_agents.make_agent(
        kind, workspace=tmp_path / "ws", model="gpt-6-astra", effort="low", max_steps=8,
        transcript_dir=tmp_path / "codex", codex_home=str(tmp_path / "home"),
        session_turns=None, base_url=None, **kw)


def test_notes_only_reach_the_prompt_when_the_flags_are_on():
    from gym_codex.mfm_prompts import CONVENTIONS_NOTE, DESIGN_NOTE
    from gym_codex.prolong_agent import ProlongGuiAgent

    def prompt(**kw):
        a = ProlongGuiAgent.__new__(ProlongGuiAgent)
        a.max_steps, a.log_only, a.netlist, a.netlist_verify = 200, False, False, False
        for k, v in kw.items():
            setattr(a, k, v)
        return a.system_prompt()

    # The designator rule must name KiCad's own prefixes and confine the task's
    # ordering to the NUMBER. An earlier wording ("the first resistor the task names is
    # R1 ... for every prefix") had the model designate a trim potentiometer `R1` where
    # the reference has `RV1`; the grader keys components on the prefix and nets on
    # (ref, pin), so one wrong prefix cost both checks on ba34f1c3 in the design pilot.
    assert "RV a potentiometer" in CONVENTIONS_NOTE
    assert "Only the NUMBER within a prefix" in CONVENTIONS_NOTE
    # The rail clause must not contradict "a label only where the task asks": reading a
    # regulator's own output as a supply rail put a `+3.3V` label on c4baee36's feedback
    # node, where the reference keeps KiCad's `Net-(U1-FB)` -- the pilot's second
    # self-inflicted regression.
    assert "regulator or converter is not one of" in CONVENTIONS_NOTE

    base = prompt()
    assert CONVENTIONS_NOTE not in base and DESIGN_NOTE not in base
    assert CONVENTIONS_NOTE in prompt(conventions=True)
    assert DESIGN_NOTE not in prompt(conventions=True)
    both = prompt(conventions=True, design=True)
    assert CONVENTIONS_NOTE in both and DESIGN_NOTE in both
    assert both.index(CONVENTIONS_NOTE) < both.index(DESIGN_NOTE)


def test_design_turn_runs_once_before_the_first_act(tmp_path, fake_codex, monkeypatch):
    agent = _agent(tmp_path, monkeypatch, design=True, design_effort="high", conventions=True)
    intent = {"parts": [{"ref": "R1", "symbol": "Device:R", "value": "10k"},
                        {"ref": "C1", "symbol": "Device:C", "value": "100n"}],
              "nets": [{"label": "GND", "pins": ["R1.2", "C1.2"]},
                       {"label": None, "pins": ["R1.1", "C1.1"]}]}
    # Call 1: the design turn (no actions.json; two files). Calls 2-3: action turns.
    fake_codex.reply(None, "Designed the RC filter.",
                     files={"design.md": "# Parts\nR1 Device:R 10k\n",
                            "intent.json": json.dumps(intent)})
    fake_codex.reply({"actions": [{"action": "click", "coordinate": [500, 500]}]},
                     "Opening the editor.\n[PLAN]\nclick")
    fake_codex.reply({"terminate": {"status": "success"}}, "done")

    msg, calls, done = agent.predict("Design an RC low-pass filter.", PNG, 0, 8)
    assert not done and calls[0]["function"]["name"] == "computer"
    rec = fake_codex.recorded()
    assert len(rec) == 2, "the design call precedes the first act call"
    design, act = rec
    assert 'model_reasoning_effort="high"' in design["argv"]
    assert 'model_reasoning_effort="low"' in act["argv"]
    assert "-i" not in design["argv"] and act["images"], "design is text-only, acts see the screen"
    assert not design["resume"] and not act["resume"], "the act thread starts cold"
    assert "[TASK] Design an RC low-pass filter." in design["prompt"]
    assert "do not write ./actions.json" in design["prompt"]
    assert design["cwd"] == act["cwd"] == str(agent.visible)
    assert (agent.visible / "design.md").exists() and (agent.visible / "intent.json").exists()
    log = (agent.record_dir / "logs.txt").read_text()
    assert "design turn (reasoning effort high" in log and "2 parts, 2 nets" in log
    assert log.index("design turn") < log.index("[ACTIONS] click(500,500)")
    agents_md = (agent.visible / "AGENTS.md").read_text()
    from gym_codex.mfm_prompts import CONVENTIONS_NOTE, DESIGN_NOTE
    assert CONVENTIONS_NOTE in agents_md and DESIGN_NOTE in agents_md

    msg, calls, done = agent.predict("Design an RC low-pass filter.", PNG, 1, 8)
    assert done and len(fake_codex.recorded()) == 3, "no second design call"
    agent.finish(1.0, None)
    audit = agent.audit()
    assert audit["design"]["ok"] and audit["design"]["parts"] == 2 and audit["design"]["nets"] == 2
    assert audit["design"]["effort"] == "high" and audit["design"]["codex_calls"] == 1
    assert audit["conventions"] is True
    assert audit["analyzer_turns"] == 2, "the act thread's own count excludes the design call"


def test_design_turn_without_files_is_noted_not_fatal(tmp_path, fake_codex, monkeypatch):
    agent = _agent(tmp_path, monkeypatch, design=True)
    fake_codex.reply(None, "I could not decide.")          # design call: no files
    fake_codex.reply({"terminate": {"status": "failure", "reason": "x"}}, "giving up")
    msg, calls, done = agent.predict("Design something.", PNG, 0, 8)
    assert done
    log = (agent.record_dir / "logs.txt").read_text()
    assert "produced no ./design.md" in log
    audit = agent.audit()
    assert audit["design"]["design_md"] is False and audit["design"]["intent_json"] is False


def test_baseline_arm_makes_no_design_call(tmp_path, fake_codex, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    fake_codex.reply({"terminate": {"status": "success"}}, "done")
    agent.predict("Design something.", PNG, 0, 8)
    rec = fake_codex.recorded()
    assert len(rec) == 1 and 'model_reasoning_effort="low"' in rec[0]["argv"]
    assert not (agent.visible / "design.md").exists()
    assert "design" not in agent.audit() and "conventions" not in agent.audit()


def _args(**over):
    base = dict(agent="mfm", model="gpt-6-astra", effort="low", max_steps=200,
                codex_timeout=None, session_turns=None, codex_base_url=None,
                netlist_readback=False, netlist_verify=False, carry_outcomes=False,
                design_turn=False, design_effort="high", conventions=False,
                env_id="cua.bench.local.kicad")
    base.update(over)
    return SimpleNamespace(**base)


def test_flags_reach_the_agent_only_when_on(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(run_eval, "make_agent", lambda kind, **kw: seen.update(kind=kind, **kw))
    run_eval._make_agent(_args(), tmp_path / "t")
    assert "design" not in seen and "conventions" not in seen and "design_effort" not in seen
    seen.clear()
    run_eval._make_agent(_args(design_turn=True, design_effort="medium", conventions=True),
                         tmp_path / "t")
    assert seen["design"] is True and seen["design_effort"] == "medium"
    assert seen["conventions"] is True
    seen.clear()
    run_eval._make_agent(_args(agent="prolong", conventions=True), tmp_path / "t")
    assert seen["conventions"] is True and "design" not in seen


NET = """(export (version "E")
  (design (source "x.kicad_sch"))
  (components
    (comp (ref "R1") (value "10k") (datasheet "~")
      (libsource (lib "Device") (part "R_US") (description "Resistor, US symbol")))
    (comp (ref "Q1") (value "2N3904")
      (libsource (lib "Transistor_BJT") (part "2N3904") (description "npn"))))
  (libparts (libpart (lib "Device") (part "R_US")))
  (nets
    (net (code "1") (name "GND") (class "Default")
      (node (ref "Q1") (pin "3") (pinfunction "E") (pintype "passive")))
    (net (code "2") (name "Net-(Q1-B)") (class "Default")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "Q1") (pin "1") (pinfunction "B") (pintype "input")))))
"""


def test_netlist_summary_is_parts_and_nets():
    from gym_codex.prolong_agent import netlist_summary
    assert netlist_summary(NET) == (
        "Existing parts (2):\n"
        "  R1  Device:R_US  10k\n"
        "  Q1  Transistor_BJT:2N3904  2N3904\n"
        "Existing nets (2):\n"
        "  GND: Q1.3(E)\n"
        "  Net-(Q1-B): R1.2 Q1.1(B)")
    assert netlist_summary("") is None
    assert netlist_summary("(export (version \"E\") (components))") is None
    assert netlist_summary("(export (components (comp (ref \"R1\")") is not None, \
        "an unbalanced export still yields the parts it holds"


def test_design_turn_sees_the_existing_project_only_when_seeded(tmp_path, fake_codex,
                                                                 monkeypatch):
    from gym_codex.mfm_prompts import DESIGN_EXISTING
    agent = _agent(tmp_path, monkeypatch, design=True)
    assert agent.seed_design(NET) is True
    fake_codex.reply(None, "Designed.", files={"design.md": "# Parts\n"})
    fake_codex.reply({"terminate": {"status": "success"}}, "done")
    agent.predict("Add a 10k pull-down to Q1's base.", PNG, 0, 8)
    design = fake_codex.recorded()[0]["prompt"]
    assert "[TASK] Add a 10k pull-down to Q1's base.\n" in design
    assert "The project already holds a schematic" in design
    assert "  R1  Device:R_US  10k" in design and "  Net-(Q1-B): R1.2 Q1.1(B)" in design
    assert "even where existing parts use a variant such as `Device:R_US`" in DESIGN_EXISTING
    assert design.index("already holds") < design.index("Design the circuit completely")
    log = (agent.record_dir / "logs.txt").read_text()
    assert "given the existing schematic" in log
    agent.finish(1.0, None)
    assert agent.audit()["design"]["existing"] is True

    # Not seeded (a from-scratch task, or an empty project): the pilot's prompt, byte
    # for byte -- the slot collapses to the blank line between the task and the brief.
    agent2 = _agent(tmp_path / "b", monkeypatch, design=True)
    assert agent2.seed_design("(export (components))") is False
    fake_codex.reply(None, "Designed.", files={"design.md": "# Parts\n"})
    fake_codex.reply({"terminate": {"status": "success"}}, "done")
    agent2.predict("Design an RC filter.", PNG, 0, 8)
    design2 = fake_codex.recorded()[2]["prompt"]
    assert "already holds" not in design2
    assert "[TASK] Design an RC filter.\n\nDesign the circuit completely" in design2
    agent2.finish(1.0, None)
    assert agent2.audit()["design"]["existing"] is False
