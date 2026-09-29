"""Stand-ins for the simulator and the model channel, for offline tests.

The simulator needs Java, a GPU node and the engine jar, and the model needs a network
round trip per turn; with both replaced by scripted stand-ins, everything between them
-- the loop, the workspace, the episode store, the contract -- runs for real.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import mcu_worldmodel.agent as _agent_mod
_agent_mod.RETRY_SLEEP = lambda _s: None   # scripted failures must not wait out real backoff


def fake_info(inventory=None, **stats) -> dict:
    """An info dict shaped like the real one.

    The shapes here were taken from an actual `sim.reset()` on a compute node, not from
    reading the handler source, because two of them are not what the source suggests:
    `inventory` is keyed by **slot index** (`{slot: {"type", "quantity"}}`) rather than by
    item name, and the statistic buckets are `defaultdict`s of 0-d numpy arrays. A fake
    built on the wrong shape would have validated the aggregation bug rather than caught it.
    """
    info = {
        "mine_block": {}, "craft_item": {}, "pickup": {}, "kill_entity": {},
        "inventory": {i: {"type": "air", "quantity": np.array(0)} for i in range(36)},
        "health": np.array(20.0), "food_level": np.array(20.0), "mobs": [],
        "location_stats": {"xpos": np.array(1.0), "ypos": np.array(64.0),
                           "zpos": np.array(2.0), "pitch": np.array(0.0),
                           "yaw": np.array(0.0)},
        "isGuiOpen": False,
    }
    if inventory:
        for slot, (name, qty) in enumerate(inventory.items()):
            info["inventory"][slot] = {"type": name, "quantity": np.array(qty)}
    for key, payload in stats.items():
        info.setdefault(key, {})
        for k, v in payload.items():
            info[key][k] = np.array(v)
    return info


class FakeCodex:
    """Stands in for CodexTurn. Scripted turns, and it records what it was asked."""

    def __init__(self, workspace, script):
        self.workspace = Path(workspace)
        self.script = list(script)
        self.calls = 0
        self.prompts: list[str] = []
        self.images_attached = 0

    def write_system_prompt(self, text):
        (self.workspace / "AGENTS.md").write_text(text, encoding="utf-8")

    def run(self, prompt, images=(), *, expect_actions=True):
        self.calls += 1
        self.prompts.append(prompt)
        self.images_attached += len(images)
        # The real CodexTurn clears these before every turn; a fake that does not would
        # let one turn's files be re-read on the next and make a test pass or fail for
        # reasons the real backend never has.
        from mcu_worldmodel.codex_backend import TURN_ARTEFACTS
        for stale in TURN_ARTEFACTS:
            (self.workspace / stale).unlink(missing_ok=True)
        turn = self.script.pop(0) if self.script else {}
        for name, payload in turn.get("files", {}).items():
            (self.workspace / name).write_text(json.dumps(payload), encoding="utf-8")
        return {"actions_json": json.dumps(turn["actions"]) if "actions" in turn else None,
                "message": turn.get("message", ""), "ok": "actions" in turn,
                "error": None, "overflow": False}

    def read_outputs(self):
        out = {"hypotheses_ops": None, "claim": None, "errors": []}
        for key, name in (("hypotheses_ops", "hypotheses_ops.json"), ("claim", "claim.json")):
            p = self.workspace / name
            if p.exists():
                out[key] = json.loads(p.read_text())
                p.unlink()          # consumed on read, as the real backend does
        return out

    @staticmethod
    def split_briefing(message):
        from mcu_worldmodel.codex_backend import CodexTurn
        return CodexTurn.split_briefing(message)

    def vision_audit(self):
        return {"frames_attached": self.images_attached, "view_image_calls": 0,
                "image_attach_failures": 0, "vision_audit_source": None}
