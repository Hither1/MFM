"""Stage 26: the model's own reflex runs in the real loop (`--own-reflexes`).

mcu_worldmodel/own.py (2026-09-07): a script under mine/reflexes/ runs every 4 ticks on the
live state while a plan executes. Here the rig plays the model: `halt.py` fires once the
avatar has walked 2 blocks (+z) -- stop, a note, and a watch(8) of its own -- during a raw
80-tick forward walk on a lit platform, so the walk must end about 2-3 blocks out with the
[REFLEX halt] note ahead of the watch note; `boom.py` always fails and must be switched
off after three runs with one note; the turn message must list both.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import RAW, Rig, main_guard

X, Y, Z = -3000, 80, -5560

HALT = '''"""halt: stop the walk two blocks out."""
import json, sys
s = json.load(sys.stdin)
if s["pos"] and s["pos"]["z"] >= %s + 2.0 and s["queue_len"] > 0:
    print(json.dumps({"stop": True,
                      "note": "walked %%.1f blocks during %%s, health %%s" %% (
                          s["pos"]["z"] - %s, s["entry"], s["health"]),
                      "actions": [{"procedure": "watch", "args": {"n": 8}}]}))
'''

BOOM = '''"""boom: always fails."""
import sys
print("no such number", file=sys.stderr)
raise SystemExit(2)
'''


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    rig.fill(X - 10, Y - 6, Z - 10, X + 10, Y, Z + 10, "stone")      # the floor's top is at Y
    rig.fill(X - 10, Y + 1, Z - 10, X + 10, Y + 6, Z + 10, "air")
    for xx in range(X - 9, X + 10, 4):
        rig.fill(xx, Y + 4, Z - 9, xx, Y + 4, Z + 9, "glowstone")
    rig.tp(X + 0.5, Y + 1, Z - 6 + 0.5, yaw=0, pitch=0)     # facing +z, 15 blocks of floor ahead
    rig.clear()
    rig.idle(10)
    z0 = rig.pos()["z"]

    a = rig.agent
    a.own, a.own_reflexes = True, True
    a.memory.own = True
    d = a.memory.root / "mine" / "reflexes"
    d.mkdir(parents=True, exist_ok=True)
    (a.memory.root / "mine" / "procedures").mkdir(parents=True, exist_ok=True)
    (d / "halt.py").write_text(HALT % (repr(z0), repr(z0)), encoding="utf-8")
    (d / "boom.py").write_text(BOOM, encoding="utf-8")

    r = rig.run([RAW(80, forward=1)], label="80-tick walk with the halt reflex", max_ticks=200)
    p = rig.pos()
    notes = r["notes"]
    halt = [n for n in notes if n.startswith("[REFLEX halt]")]
    rig.check("the walk stopped 2-4 blocks out", 1.8 <= p["z"] - z0 <= 4.0, (z0, p))
    rig.check("one [REFLEX halt] note with the dropped count and its own actions",
              len(halt) == 1 and "dropped the rest of your plan" in halt[0]
              and "running the reflex's own actions" in halt[0], notes)
    watch = [i for i, n in enumerate(notes) if "watch(until=none): waited 8 tick(s)" in n]
    rig.check("the reflex's watch(8) ran after the note",
              bool(watch) and halt and notes.index(halt[0]) < watch[0], notes)
    boom = [n for n in notes if n.startswith("[REFLEX boom] switched OFF after 3 failures")]
    rig.check("boom switched OFF after three failures, one note",
              len(boom) == 1 and "no such number" in boom[0], notes)
    rig.check("stats: one fire, three failures",
              a.cursor_stats.get("own_reflex_fires") == 1
              and a.cursor_stats.get("own_reflex_failures") == 3, dict(a.cursor_stats))
    prompt = a._turn_prompt(rig.info)
    rig.check("the turn message lists both reflexes",
              "[OWN] your own reflexes" in prompt and "`halt` -- halt: stop the walk" in prompt
              and "[fired 1x]" in prompt and "`boom` -- switched OFF" in prompt,
              prompt[prompt.find("[OWN] your own reflexes"):][:400])
    rig.frame("s26_stopped")


if __name__ == "__main__":
    main_guard(stage)
