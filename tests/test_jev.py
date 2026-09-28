"""The JEV + Astra arm (2026-09-27): the two-tier loop of rmalde/minecraft-agent on the
gen-4 chassis under MFM_MCU_ROOT.

Nothing here touches the network. The two clients are injected (`jev_options`), which is
how the bridge is built to be driven: `decider` answers typed questions from a policy the
test writes, `planner` hands back a fixed objective. What is actually asserted is the
part that can be wrong without a model noticing -- that every option on the menu is one
the chassis would accept, that a refused or dropped entry cools its key down, that three
failures in a row call the planner, and that the arm ends the episode rather than
stepping blind when the account cannot spend.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from mfm.jev.decisions import (Decision, DecisionsBudgetExceeded, _parse_decision, choice,
                               noul, read_api_key)
from mfm.jev.menu import Candidate, CandidateMenu
from mfm.jev.planner import Plan, _parse_plan
from mfm.jev.session import JevSession, Trigger

from test_pins_chassis import _pov


# -- the fakes -------------------------------------------------------------------------

class FakeDecider:
    """Answers `next_action` with the first key `policy` likes, `replan` with `replan`."""

    # The real client's identity fields: the bridge's audit reads them off whatever is
    # injected, so a fake that lacks them would make the report look empty.
    model = "fake-jev"
    provider = "fake"

    def __init__(self, policy=None, replan: bool = False) -> None:
        self.policy = policy or (lambda keys, state: keys[0])
        self.replan = replan
        self.calls = 0
        self.seen: list[dict] = []
        self.menus: list[list[str]] = []
        self.menus_asked: list[list[str]] = []      # the question names of each call

    def decide(self, state, questions) -> Decision:
        self.calls += 1
        self.menus_asked.append(list(questions))
        self.seen.append(state)
        self.menus.append(list(questions["next_action"].criteria))
        answers = {}
        for name, q in questions.items():
            if q.kind == "choice":
                keys = list(q.criteria)
                pick = self.policy(keys, state)
                answers[name] = {"type": "choice", "choice": pick, "confidence": 0.7,
                                 "probabilities": {k: (0.7 if k == pick else 0.1)
                                                   for k in keys}}
            elif q.kind == "noul":
                answers[name] = {"type": "noul", "noul": 0.9 if self.replan else 0.05}
        return _parse_decision({"answers": answers, "model": "fake-jev",
                                "usage": {"input_tokens": 10, "output_tokens": 2}},
                               questions)

    def audit(self):
        return {"calls": self.calls, "model": self.model, "provider": self.provider}


class FakePlanner:
    model = "fake-astra"
    provider = "fake"

    def __init__(self, plan: Plan | None = None) -> None:
        self.plan_obj = plan or Plan(objective="get a log", targets=["oak_log"],
                                     reasoning="wood first")
        self.calls = 0
        self.triggers: list[str] = []
        self.images_sent = 0
        self.states: list[dict] = []

    def plan(self, *, task, state, trigger, frame_png=None):
        self.calls += 1
        self.triggers.append(trigger)
        self.states.append(state)
        if frame_png:
            self.images_sent += 1
        return Plan(**{**self.plan_obj.__dict__})

    def audit(self):
        return {"calls": self.calls, "model": self.model, "provider": self.provider}


def _session(**kw) -> tuple[JevSession, FakeDecider, FakePlanner]:
    decider, planner = kw.pop("decider", None) or FakeDecider(), kw.pop("planner", None) or FakePlanner()
    return JevSession(decider=decider, planner=planner, task="t", **kw), decider, planner


def _cands(*keys) -> list[Candidate]:
    return [Candidate(key=k, entry={"procedure": k, "args": {}}, description=f"do {k}",
                      ticks=4, atom=k) for k in keys]


# -- 1. the menu: cooldowns and the failure counter -------------------------------------

def test_a_failed_action_leaves_the_menu_and_comes_back():
    menu = CandidateMenu()
    cands = _cands("mine_ahead", "wait")
    assert [c.key for c in menu.offer(cands)] == ["mine_ahead", "wait"]
    menu.note_decision()
    menu.note_failure("mine_ahead")
    assert [c.key for c in menu.offer(cands)] == ["wait"]      # dropped, wait survives
    for _ in range(3):
        menu.note_decision()
    assert [c.key for c in menu.offer(cands)] == ["mine_ahead", "wait"]


def test_three_failures_in_a_row_are_a_replan_and_a_success_clears_them():
    menu = CandidateMenu()
    for key in ("a", "b", "c"):
        menu.note_decision()
        menu.note_failure(key)
    assert menu.replan_due and menu.errors == 3
    menu.note_success("a")
    assert not menu.replan_due and menu.errors == 0
    assert "a" not in menu.cooldown                            # success clears the cooldown


def test_the_planner_can_veto_a_key_or_a_whole_atom():
    menu = CandidateMenu()
    cands = _cands("mine_ahead", "eat", "wait")
    assert [c.key for c in menu.offer(cands, avoid=["eat"])] == ["mine_ahead", "wait"]
    assert [c.key for c in menu.offer(cands, avoid=["mine_ahead"])] == ["eat", "wait"]


def test_the_menu_is_capped_but_never_without_wait():
    menu = CandidateMenu(max_options=3)
    offered = menu.offer(_cands(*[f"k{i}" for i in range(10)], "wait"))
    assert len(offered) == 3 and offered[-1].key == "wait"


# -- 2. the two-tier loop ---------------------------------------------------------------

def test_the_first_decision_plans_and_the_second_does_not():
    session, decider, planner = _session()
    state = {"step": 1, "position": {"x": 0.0, "y": 64.0, "z": 0.0}, "inventory": {}}
    first = session.decide(state, _cands("mine_ahead", "wait"))
    assert first is not None and planner.calls == 1
    assert planner.triggers == [Trigger.NO_PLAN]
    session.decide(state, _cands("mine_ahead", "wait"))
    assert planner.calls == 1                                   # the cooldown holds


def test_three_failed_entries_call_the_planner_again():
    session, decider, planner = _session(plan_cooldown=0)
    state = {"step": 1, "inventory": {}}
    for _ in range(3):
        chosen = session.decide(state, _cands("mine_ahead", "wait"))
        session.record_outcome(chosen.candidate.key, ok=False)
    session.decide(state, _cands("mine_ahead", "wait"))
    assert planner.triggers[-1] == Trigger.ERRORS
    assert session.menu.errors == 0                             # the counter is reset


def test_reaching_the_waypoint_calls_the_planner():
    plan = Plan(objective="walk", waypoint={"x": 10.0, "y": 64.0, "z": 0.0, "why": "tree"})
    session, _, planner = _session(planner=FakePlanner(plan), plan_cooldown=0)
    far = {"step": 1, "position": {"x": 0.0, "y": 64.0, "z": 0.0}, "inventory": {}}
    session.decide(far, _cands("wait"))
    session.decide(far, _cands("wait"))
    assert planner.triggers == [Trigger.NO_PLAN]
    near = {"step": 2, "position": {"x": 9.0, "y": 64.0, "z": 0.0}, "inventory": {}}
    session.decide(near, _cands("wait"))
    assert planner.triggers[-1] == Trigger.WAYPOINT


def test_the_targets_being_in_hand_calls_the_planner():
    session, _, planner = _session(plan_cooldown=0)              # targets: oak_log
    session.decide({"step": 1, "inventory": {}}, _cands("wait"))
    session.decide({"step": 2, "inventory": {"oak_log": 1}}, _cands("wait"))
    assert planner.triggers[-1] == Trigger.TARGETS


def test_the_selector_can_ask_for_a_new_objective():
    session, _, planner = _session(decider=FakeDecider(replan=True), plan_cooldown=0)
    session.decide({"step": 1, "inventory": {}}, _cands("wait"))
    assert session.replans_asked == 1
    session.decide({"step": 2, "inventory": {}}, _cands("wait"))
    assert planner.triggers[-1] == Trigger.SELECTOR


def test_an_off_menu_answer_falls_back_to_wait_and_is_counted():
    decider = FakeDecider(policy=lambda keys, state: "fly_to_the_end")
    session, _, _ = _session(decider=decider)
    chosen = session.decide({"step": 1, "inventory": {}}, _cands("mine_ahead", "wait"))
    assert chosen.candidate.key == "wait" and session.invalid_choices == 1
    assert "off-menu" in chosen.fallback


def test_the_selector_never_sees_an_image_and_the_planner_does():
    session, decider, planner = _session()
    session.decide({"step": 1, "inventory": {}, "frame": "would be an image"},
                   _cands("wait"), frame_png=b"\x89PNG")
    assert planner.images_sent == 1
    assert "frame" not in decider.seen[0]
    assert decider.seen[0]["objective"] == "get a log"


def test_a_budget_403_is_not_swallowed():
    class Broke(FakeDecider):
        def decide(self, state, questions):
            raise DecisionsBudgetExceeded("Workspace lifetime budget of $5000.00 exceeded.")

    session, _, _ = _session(decider=Broke())
    with pytest.raises(DecisionsBudgetExceeded):
        session.decide({"step": 1, "inventory": {}}, _cands("wait"))


# -- 3. the wire shapes -----------------------------------------------------------------

def test_a_decisions_response_parses_the_way_the_reference_documents_it():
    questions = {"team": choice("which team", {"a": "x", "b": "y"}),
                 "is_bug": noul("a bug?", "yes", "no")}
    raw = {"id": "gen-dec-1", "model": "typesafe/jev-1.13-20260917", "provider": "TypeSafe",
           "answers": {"team": {"type": "choice", "choice": "b", "confidence": 0.75,
                                "probabilities": {"a": 0.16, "b": 0.84}},
                       "is_bug": {"type": "noul", "noul": 0.96}},
           "usage": {"input_tokens": 476, "output_tokens": 70, "cost": 0.000019992}}
    d = _parse_decision(raw, questions)
    assert d.get("team").value == "b" and d.get("team").probabilities["b"] == 0.84
    assert d.get("is_bug").is_true and d.input_tokens == 476


def test_a_plan_with_a_junk_waypoint_keeps_the_objective_and_drops_the_coordinate():
    content = json.dumps({"objective": "get wood", "targets": ["oak_log"],
                          "waypoint": {"x": "somewhere", "y": 64, "z": 0, "why": "?"},
                          "avoid": ["eat"], "reasoning": "no axe yet"})
    plan = _parse_plan({"choices": [{"message": {"content": content}}]})
    assert plan.objective == "get wood" and plan.waypoint is None and plan.avoid == ["eat"]


def test_the_key_is_read_from_a_file_and_never_from_thin_air(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    keyfile = tmp_path / "openrouter.env"
    keyfile.write_text("OTHER=1\nOPENROUTER_API_KEY=sk-or-v1-test\n")
    assert read_api_key(keyfile) == "sk-or-v1-test"
    with pytest.raises(Exception) as exc:
        read_api_key(tmp_path / "absent.env")
    assert "OpenRouter" in str(exc.value)


# -- 4. the arm on the chassis ----------------------------------------------------------

def drive_jev(root: Path, steps: int = 120, decider=None, planner=None, **kw):
    """`drive_chassis` for an arm whose model is not a codex turn: the clients are
    injected instead of `agent.codex` being replaced."""
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1}]
    options = {"decider": decider or FakeDecider(), "planner": planner or FakePlanner()}
    options.update(kw.pop("jev_options", {}))
    agent = WorldModelAgent(workspace=root / "ws", task_text="get a log and a table",
                            ledger=MilestoneLedger(cfg, "t"), step_cap=50,
                            memory_mode="jev", platform_prompt="HOST REFERENCE",
                            jev_options=options, **kw)
    info = fake_info(inventory={"oak_log": 1})
    info["pov"] = _pov(0)
    agent.start(info)
    for step in range(1, steps + 1):
        agent.next_action(info)
        info = fake_info(inventory={"oak_log": 2 if step > 8 else 1},
                         mine_block={"oak_log": 1} if step > 8 else {})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["location_stats"]["ypos"] = np.array(64.0 - (step // 20))
        info["pov"] = _pov(step)
        agent.observe(info, step)
    return agent


def test_every_option_offered_is_one_the_chassis_would_accept(tmp_path):
    """The menu's whole promise: JEV cannot be asked to pick an impossible action."""
    seen: list[tuple[str, dict]] = []

    def policy(keys, state):
        seen.append((tuple(keys), state))
        return "wait"

    agent = drive_jev(tmp_path, steps=40, decider=FakeDecider(policy=policy))
    bridge = agent.jev
    assert bridge.decisions >= 3, "the loop never reached a decision"
    from mcu_worldmodel.selftest import fake_info
    info = fake_info(inventory={"oak_log": 3, "crafting_table": 1})
    for cand in bridge._candidates(info):
        ticks, notes = bridge._dry_run(cand.entry, info)
        assert ticks > 0, f"{cand.key} is on the menu but expands to nothing: {notes}"
    keys = {k for menu, _ in seen for k in menu}
    assert "wait" in keys and "mine_ahead" in keys
    # The inventory has no bucket and no food, so those atoms are never offered.
    assert not {k for k in keys if k.startswith(("fill_bucket", "eat"))}


def test_the_arm_acts_plans_and_leaves_a_decision_log(tmp_path):
    agent = drive_jev(tmp_path, steps=60,
                      decider=FakeDecider(policy=lambda keys, s:
                                          "mine_ahead" if "mine_ahead" in keys else keys[0]))
    bridge = agent.jev
    assert bridge.plans >= 1 and bridge.entries_applied >= 1
    rows = [json.loads(l) for l in (bridge.events_path).read_text().splitlines()]
    kinds = {r["kind"] for r in rows}
    assert {"plan", "outcome"} <= kinds
    agent.jev.finish()
    rows = [json.loads(l) for l in (bridge.events_path).read_text().splitlines()]
    decisions = [r for r in rows if r["kind"] == "decision"]
    assert decisions and all("probability" in r and "options" in r for r in decisions)
    # The harness record every arm leaves is still written, with the objective in it.
    logs = (agent.memory.root / "logs.txt").read_text()
    assert "[OBJECTIVE] get a log" in logs and "[CHOICE] " in logs


def test_the_report_carries_the_arm_and_the_two_models(tmp_path):
    agent = drive_jev(tmp_path, steps=30)
    report = agent.report()
    assert report["memory_mode"] == "jev"
    jev = report["jev"]
    assert jev["selector_model"] and jev["planner_model"]
    assert jev["decisions"] >= 1 and "menu" in jev and "mean_menu_size" in jev
    assert "hypotheses" not in report               # the belief graph is not this arm's
    assert report["codex"]["calls"] == jev["decisions"] + jev["plans"]


def test_the_episode_ends_when_the_account_cannot_spend(tmp_path):
    class Broke(FakeDecider):
        def decide(self, state, questions):
            raise DecisionsBudgetExceeded("Workspace lifetime budget of $5000.00 exceeded.")

    agent = drive_jev(tmp_path, steps=12, decider=Broke())
    assert isinstance(agent.jev.session_failed, DecisionsBudgetExceeded)
    assert agent.jev.decisions == 0
    assert agent.report()["jev"]["ended_on"] == "DecisionsBudgetExceeded"


# -- 5. the two routes to each model ----------------------------------------------------

def test_the_selector_routes_to_typesafe_or_openrouter_by_which_key_is_there(tmp_path, monkeypatch):
    from mfm.jev.decisions import PROVIDERS, JevDecider
    for var in ("JEV_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MCU_JEV_ENV", str(tmp_path / "jev.env"))
    monkeypatch.setenv("MCU_OPENROUTER_ENV", str(tmp_path / "openrouter.env"))
    # Only an OpenRouter key: the resale route, its path and its prefixed model id.
    (tmp_path / "openrouter.env").write_text("OPENROUTER_API_KEY=sk-or-v1-x\n")
    d = JevDecider()
    assert (d.provider, d.path, d.model) == ("openrouter", "/alpha/decisions",
                                             "typesafe/jev-1.13")
    assert d.base_url == "https://openrouter.ai/api"
    # A Jev key as well: TypeSafe's own API wins, with the bare model id.
    (tmp_path / "jev.env").write_text("JEV_API_KEY=ts-test\n")
    d = JevDecider()
    assert (d.provider, d.path, d.model) == ("typesafe", "/v1/systemone", "jev-1.13.0")
    assert d.base_url == "https://api.typesafe.ai"
    # Named explicitly, the other route is still available.
    assert JevDecider(provider="openrouter").provider == "openrouter"
    assert set(PROVIDERS) == {"typesafe", "openrouter"}


def test_the_typesafe_body_carries_no_session_id_and_openrouters_does(monkeypatch):
    from mfm.jev.decisions import JevDecider
    sent = {}

    def fake_post(self, path, body):
        sent["path"], sent["body"] = path, body
        return ({"answers": {"q": {"type": "noul", "noul": 0.9}}, "model": "m",
                 "usage": {"input_tokens": 1, "output_tokens": 0}}, 7)

    monkeypatch.setattr(JevDecider, "_post", fake_post)
    q = {"q": noul("up?", "yes", "no")}
    JevDecider(provider="typesafe", api_key="k", session_id="arm1").decide({"a": 1}, q)
    assert sent["path"] == "/v1/systemone" and "session_id" not in sent["body"]
    JevDecider(provider="openrouter", api_key="k", session_id="arm1").decide({"a": 1}, q)
    assert sent["path"] == "/alpha/decisions" and sent["body"]["session_id"] == "arm1"


def test_a_state_over_the_provider_ceiling_is_trimmed_not_refused():
    from mfm.jev.decisions import _fit_state
    state = {"step": 5, "position": {"x": 1}, "recent_outcomes": [{"key": "k" * 400}] * 40,
             "map_from_own_positions": "m" * 4000, "milestones_detail": "d" * 4000}
    questions = {"next_action": choice("pick", {"a": "x"}).payload()}
    fitted, dropped = _fit_state(state, questions, 6000)
    assert len(json.dumps(fitted)) <= 6000
    assert "recent_outcomes" in dropped and fitted["step"] == 5   # the small facts survive
    assert "position" in fitted
    # A state that already fits is passed through untouched.
    small = {"step": 1}
    assert _fit_state(small, questions, 6000) == (small, [])


def test_the_planner_model_id_is_spelled_for_its_route(monkeypatch):
    from mfm.jev.planner import AstraPlanner, _spell_model
    assert _spell_model("gpt-6-astra", "openai") == "gpt-6-astra"
    assert _spell_model("openai/gpt-6-astra", "openai") == "gpt-6-astra"
    assert _spell_model("gpt-6-astra", "openrouter") == "openai/gpt-6-astra"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    p = AstraPlanner(provider="openai", model="gpt-6-astra")
    assert p.base_url == "https://api.openai.com" and p.model == "gpt-6-astra"


def test_the_bridge_reports_the_route_each_model_actually_took(tmp_path):
    agent = drive_jev(tmp_path, steps=20)
    jev = agent.report()["jev"]
    # The audit names the route each client reports, never one the bridge assumed.
    assert jev["selector_provider"] == "fake" and jev["planner_provider"] == "fake"
    assert jev["selector_model"] == "fake-jev" and jev["planner_model"] == "fake-astra"


# -- 6. the planner through codex (the route with credit) -------------------------------

class StubTurn:
    """A CodexTurn that answers with `reply` instead of running the CLI."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []
        self.images: list[list] = []
        self.system = ""
        self.calls = 0

    def write_system_prompt(self, text: str) -> None:
        self.system = text

    def run(self, prompt, images=(), *, expect_actions=True):
        assert expect_actions is False, "a planning turn writes no actions.json"
        self.calls += 1
        self.prompts.append(prompt)
        self.images.append(list(images))
        return {"ok": True, "message": self.reply, "actions_json": None, "error": ""}


def _codex_planner(tmp_path: Path, reply: str):
    from mcu_worldmodel.jev import CodexPlanner
    stub = StubTurn(reply)
    return CodexPlanner(root=tmp_path / "ws" / "memory", model="gpt-6-astra", effort="high",
                        timeout=480, turn=stub), stub


def test_the_codex_planner_reads_a_fenced_plan_and_sends_the_frame(tmp_path):
    reply = ('Here is my plan.\n```json\n{"objective": "chop a tree", '
             '"targets": ["oak_log"], "waypoint": null, "avoid": [], '
             '"reasoning": "no wood yet"}\n```\n')
    planner, stub = _codex_planner(tmp_path, reply)
    plan = planner.plan(task="get a log", state={"step": 3}, trigger="there is no plan yet",
                        frame_png=b"\x89PNG\r\n")
    assert plan.objective == "chop a tree" and plan.targets == ["oak_log"]
    assert planner.images_sent == 1 and stub.images[0][0].name == "view.png"
    # The system prompt is the planner's own, and the arm's workspace is not the cwd.
    assert stub.system.startswith("You are the PLANNER")
    assert planner.dir.name == "jev_planner" and "memory" not in planner.dir.name
    assert "WHY YOU WERE CALLED" in stub.prompts[0]


def test_the_codex_planner_takes_a_bare_plan_object_too(tmp_path):
    reply = '{"objective": "mine stone", "targets": [], "waypoint": null, "avoid": [], "reasoning": "r"}'
    planner, _ = _codex_planner(tmp_path, reply)
    assert planner.plan(task="t", state={}, trigger="x").objective == "mine stone"


def test_a_codex_turn_that_says_nothing_is_a_planner_error(tmp_path):
    from mfm.jev.planner import PlannerError
    planner, _ = _codex_planner(tmp_path, "   ")
    with pytest.raises(PlannerError):
        planner.plan(task="t", state={}, trigger="x")
    assert planner.failures == 1


def test_the_arm_runs_on_the_codex_planner(tmp_path):
    """The whole loop with the selector faked and the planner on the codex backend."""
    from mcu_worldmodel.jev import CodexPlanner
    reply = ('{"objective": "get a log", "targets": ["oak_log"], "waypoint": null, '
             '"avoid": [], "reasoning": "wood first"}')
    stub = StubTurn(reply)
    planner = CodexPlanner(root=tmp_path / "ws" / "memory", model="openai/gpt-6-astra",
                           effort="high", timeout=480, turn=stub)
    agent = drive_jev(tmp_path, steps=40, planner=planner)
    assert stub.calls >= 1 and agent.jev.plans == stub.calls
    jev = agent.report()["jev"]
    assert jev["planner_provider"] == "codex" and jev["planner_model"] == "gpt-6-astra"
    assert "[OBJECTIVE] get a log" in (agent.memory.root / "logs.txt").read_text()


# -- 7. the planner-free variant (--jev-no-planner) --------------------------------------

OBJECTIVES = [("mine_log", "mine block: oak_log"), ("crafting_table", "craft item: table"),
              ("explore", "nothing reachable: cover new ground")]


def test_with_no_planner_the_selector_sets_the_objective_in_the_same_call():
    picks = {"objective": "crafting_table"}
    decider = FakeDecider(policy=lambda keys, s: picks.get("objective") if "craft" in str(keys)
                          else keys[0])

    class Pick(FakeDecider):
        """Answers `objective` with a milestone and `next_action` with the first option."""

        def decide(self, state, questions):
            out = super().decide(state, questions)
            if "objective" in questions:
                out.answers["objective"] = _parse_decision(
                    {"answers": {"objective": {"type": "choice", "choice": "crafting_table",
                                               "confidence": 0.8,
                                               "probabilities": {"crafting_table": 0.8}}}},
                    {"objective": questions["objective"]}).answers["objective"]
            return out

    d = Pick()
    session = JevSession(decider=d, planner=None, task="t", no_planner=True)
    chosen = session.decide({"step": 1, "inventory": {}}, _cands("mine_ahead", "wait"),
                            objectives=OBJECTIVES)
    assert chosen is not None
    # The objective was asked in the decision call, and takes effect from the next one.
    assert "objective" in d.menus_asked[-1]
    assert session.plan is not None and session.plan.objective == "craft item: table"
    assert session.plans == 1
    # One model call, not two: the objective rode inside the decision.
    assert session.model_calls == 1
    # The next decision carries the objective and does not re-ask it.
    session.decide({"step": 2, "inventory": {}}, _cands("mine_ahead", "wait"),
                   objectives=OBJECTIVES)
    assert "objective" not in d.menus_asked[-1]
    assert d.seen[-1]["objective"] == "craft item: table"


def test_with_no_planner_nothing_calls_a_planner_and_the_audit_says_so():
    session = JevSession(decider=FakeDecider(), planner=None, task="t", no_planner=True)
    for step in range(4):
        session.decide({"step": step, "inventory": {}}, _cands("wait"), objectives=OBJECTIVES)
    audit = session.audit()
    assert audit["no_planner"] is True and audit["planner"] is None
    assert session.planner_failures == 0


def test_the_arm_runs_with_no_planner_at_all(tmp_path):
    agent = drive_jev(tmp_path, steps=40, planner=None, jev_options={"no_planner": True})
    bridge = agent.jev
    assert bridge.session.planner is None and bridge.decisions >= 2
    assert bridge.plans >= 1, "the selector never set itself an objective"
    # The objective options are the ledger's unscored milestones plus the fallback.
    keys = [k for k, _ in bridge._objectives()]
    assert "explore" in keys and "crafting_table" in keys
    assert "mine_log" not in keys, "a scored milestone is not an objective any more"
    report = agent.report()["jev"]
    assert report["no_planner"] is True and report["planner_model"] == ""
    assert report["codex_calls"] if "codex_calls" in report else True
    assert agent.report()["codex"]["calls"] == report["decisions"]
