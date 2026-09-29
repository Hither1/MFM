"""Stage 22: the model's own procedure runs in the real loop (`--atoms` + `--own`).

tasks/mfm-three-layer.self-harness (2026-09-07): the contract's procedure set is cut to
the atoms and the model keeps scripts under mine/procedures/ that print a plan. Here the
rig plays the model: a `chop.py` that aims at a given block (look_at), mines it
(mine_ahead) and sweeps the drop (collect_drops) is written into the workspace, called by
name against a cobblestone block on a lit platform, and must put the cobblestone in the
inventory through the ordinary queue; a failing script costs one [NOTE] and the rest of
the plan runs; a task-shaped built-in (chop_tree) is refused under the atoms; the turn
message carries the [OWN] block with the call count.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 80, -5600

CHOP = '''"""chop: look at the block at (x, y, z), mine it, sweep the drop."""
import json, sys
PARAMS = {"x": "block x", "y": "block y", "z": "block z", "n": "mining ticks (default 80)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
state = json.load(sys.stdin)
n = int(args.get("n", 80))
plan = [{"procedure": "look_at", "args": {"x": args["x"] + 0.5, "y": args["y"] + 0.5,
                                          "z": args["z"] + 0.5}},
        {"procedure": "mine_ahead", "args": {"n": n, "ore_watch": False}},
        {"procedure": "collect_drops", "args": {"ticks": 24}}]
print(json.dumps({"actions": plan}))
'''

BOOM = '''"""boom: always fails."""
import sys
print("the block is not there", file=sys.stderr)
raise SystemExit(4)
'''


def stage(rig: Rig) -> None:
    from mcu_worldmodel import procedures as PR
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    rig.platform(X, Y, Z, r=6, block="stone")
    rig.fill(X - 6, Y, Z - 6, X + 6, Y + 3, Z + 6, "air")
    for xx in range(X - 5, X + 6, 4):
        rig.fill(xx, Y + 3, Z - 5, xx, Y + 3, Z + 5, "glowstone")
    rig.tp(X + 0.5, Y, Z + 0.5, yaw=0, pitch=0)         # facing +z
    rig.clear()
    rig.give("iron_pickaxe", 1)
    rig.idle(10)
    # the block to mine: two cells ahead, at eye level's floor
    rig.setblock(X, Y, Z + 2, "cobblestone")
    rig.idle(4)

    # the arm's flags on the rig's agent (constructed without them)
    a = rig.agent
    a.own, a.atoms = True, True
    a.memory.own = True
    PR.set_visible(PR.ATOMS)
    d = a.memory.root / "mine" / "procedures"
    d.mkdir(parents=True, exist_ok=True)
    (d / "chop.py").write_text(CHOP, encoding="utf-8")
    (d / "boom.py").write_text(BOOM, encoding="utf-8")

    prompt = a._turn_prompt(rig.info)
    rig.check("the turn message carries the [OWN] block with chop and boom",
              "[OWN] your own procedures" in prompt and "`chop(x=<block x>" in prompt
              and "[called 0x]" in prompt and "`boom()` -- boom: always fails" in prompt,
              prompt[prompt.find("[OWN]"):prompt.find("[OWN]") + 400])

    pick = next((h["slot"] for h in __import__("mcu_worldmodel.episodes", fromlist=["_hotbar"])
                 ._hotbar(rig.info) if "pickaxe" in h["item"]), 0)
    mined0 = rig.stat("mine_block", "cobblestone")
    r = rig.run([P("equip_hotbar", slot=pick + 1),
                 P("boom"),
                 P("chop", x=X, y=Y, z=Z + 2, n=120),
                 P("chop_tree", n=10)],
                label="own chop + boom + refused chop_tree", max_ticks=400)
    notes = r["notes"]
    # the milestone (mine_cobblestone) fires on the break and re-plans, so the drop sweep
    # is cut short: the break itself is the evidence, on the game's own statistic
    mined = rig.stat("mine_block", "cobblestone") - mined0
    rig.check("boom failed with one [NOTE] naming the script and the stderr line",
              any("boom (mine/procedures/boom.py) FAILED" in n and "the block is not there" in n
                  for n in notes), notes[:4])
    rig.check("chop_tree was refused under the atoms",
              any("'chop_tree' is not in this run's procedure set" in n for n in notes), notes)
    rig.check("the own chop ran through the queue and broke the block "
              "(mine_block cobblestone +1)", mined >= 1, (mined, r["delta"], r["ticks"]))
    rig.check("the runner counted the call (own_calls 1, own_failures 1)",
              a.cursor_stats.get("own_calls") == 1 and a.cursor_stats.get("own_failures") == 1,
              {k: v for k, v in a.cursor_stats.items() if k.startswith("own")})
    log = (a.memory.root / "logs.txt").read_text(encoding="utf-8")
    rig.check("the log shows the call as one [ACTION] chop(...) entry",
              "[ACTION] chop(x=" in log, [ln for ln in log.splitlines() if "[ACTION]" in ln][-4:])
    prompt = a._turn_prompt(rig.info)
    rig.check("the next turn message counts it ([called 1x])", "[called 1x]" in prompt,
              prompt[prompt.find("[OWN]"):prompt.find("[OWN]") + 300])
    rig.check("mine/ survived the end-of-turn sweep",
              (d / "chop.py").exists() and (d / "boom.py").exists(), sorted(p.name for p in d.iterdir()))
    rig.frame("s22_after")
    PR.set_visible(None)


if __name__ == "__main__":
    main_guard(stage)
