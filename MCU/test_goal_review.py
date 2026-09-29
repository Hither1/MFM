"""The subgoal-review layer, driven through ProlongAgent with a stubbed analyzer.

Reproduces the shape of the dragon run's failure -- an analyzer that re-submits the
same subgoal turn after turn while the environment verifies nothing -- and checks the
three properties the layer is supposed to have:

  * off by default, and with it off nothing about the ported arm changes;
  * on, a subgoal that overruns its budget is put to the model as a review and a plan
    that ignores the review is rejected rather than merely warned about;
  * a stated re-commitment is accepted but re-arms the budget, so one "yes" does not
    license the remaining episode -- which is exactly what 132 consecutive agreeing
    turns did.

Run it directly: `python test_goal_review.py`. It needs no simulator and no model.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mc_agent.prolong_agent as pa
from mc_agent.action_space import DefaultActionSpace

PLAN = json.dumps({"subgoal": "climb back to the surface",
                   "actions": [{"action": {"jump": 1, "use": 1}, "repeat": 20}]})
PLAN_RECOMMIT = json.dumps({"subgoal": "climb back up to the surface",
                            "recommit": "the ceiling is one block away",
                            "actions": [{"action": {"jump": 1}, "repeat": 20}]})

class StubCodex:
    """Always re-submits the same subgoal, the way the real run did for 132 turns."""
    calls = 0
    def __init__(self, *a, **k):
        self.replies = []
        self.prompts = []
    def write_system_prompt(self, text): self.system = text
    def run(self, prompt, images=None):
        self.prompts.append(prompt)
        StubCodex.calls += 1
        reply = self.replies.pop(0) if self.replies else PLAN
        return {"ok": True, "actions_json": reply, "message": "briefing\n[PLAN]\ndig up"}
    @staticmethod
    def split_briefing(msg): return ("briefing", "dig up")

pa.CodexTurn = StubCodex

SPEC = [{"identity": "mine_log", "event": "craft", "objects": ["log"], "done": True},
        {"identity": "diamond", "event": "mine", "objects": ["diamond"], "done": False}]

def info(step):
    return {"player_pos": {"x": 1.0, "y": 5.0 + step / 89.0, "z": 1.0, "pitch": 0, "yaw": 0},
            "inventory": {"0": {"type": "cobblestone", "quantity": 64}},
            "milestone_spec": SPEC}

def run(budget, n_steps, retries=3):
    ws = Path(tempfile.mkdtemp()) / "ep"
    agent = pa.ProlongAgent(action_space=DefaultActionSpace(), provider=None,
                            workspace=ws, milestone_hint=True, analyzer_retries=retries,
                            goal_budget_steps=budget, step_cap=20, repeat_cap=20)
    agent.load_system_prompt("mine a diamond from scratch")
    stub = agent.codex
    for step in range(n_steps):
        agent.get_action([], [], [], step, milestone_hint="1/2 milestones verified so far",
                         info=info(step))
    return agent, stub, ws

# 1. off by default -> untouched port
agent, stub, ws = run(budget=0, n_steps=60)
log = (ws / "logs.txt").read_text()
assert agent.goals is None
assert "Subgoal:" not in log and "REVIEW" not in log
assert "SUBGOAL REVIEW" not in agent.codex.system
print("off:  no subgoal field, no review, prompt unchanged")

# 2. on -> header carries the subgoal, review fires, plan rejected, retried
StubCodex.calls = 0
agent, stub, ws = run(budget=40, n_steps=200)
log = (ws / "logs.txt").read_text()
headers = [l for l in log.splitlines() if l.startswith("Action ") and "Subgoal" in l]
assert headers, "no subgoal in any header"
reviews = [l for l in log.splitlines() if "REVIEW" in l]
rejections = [l for l in reviews if "rejected --" in l]
review_prompts = [p for p in stub.prompts if "SUBGOAL REVIEW" in p]
assert review_prompts, "review never reached the analyzer"
assert rejections, "re-submitting the same subgoal was not rejected"
print(f"on:   {len(headers)} headers carry the subgoal, "
      f"{len(review_prompts)} review turns, {len(rejections)} plans rejected")
print("      audit:", json.dumps(agent.goals.audit(), separators=(",", ":"))[:220])
print("      review reached the model:")
print("      | " + "\n      | ".join(review_prompts[0].splitlines()[:6]))

# 3. a recommit is accepted and re-arms the budget rather than closing the question
StubCodex.calls = 0
ws = Path(tempfile.mkdtemp()) / "ep"
agent = pa.ProlongAgent(action_space=DefaultActionSpace(), provider=None, workspace=ws,
                        milestone_hint=True, analyzer_retries=3, goal_budget_steps=40,
                        step_cap=20, repeat_cap=20)
agent.load_system_prompt("mine a diamond from scratch")
agent.codex.replies = [PLAN] * 3 + [PLAN_RECOMMIT] * 40
for step in range(200):
    agent.get_action([], [], [], step, milestone_hint="1/2 verified", info=info(step))
a = agent.goals.audit()
assert a["subgoal_recommits"] >= 1, a
assert a["subgoal_reviews"] >= 2, a  # re-armed: asked again a budget later
print(f"recommit: accepted {a['subgoal_recommits']}x, still reviewed "
      f"{a['subgoal_reviews']}x -- one 'yes' does not buy the rest of the episode")
print("\nALL PASS")
