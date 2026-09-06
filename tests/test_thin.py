"""`--thin` (a one-page contract with the long sections in references/) and `watch`."""
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_thin_contract_and_references(tmp_path: Path):
    from test_pins_chassis import drive_chassis

    agent, _ = drive_chassis(tmp_path, "mfm", thin=True)
    ws = agent.memory.root
    short = (ws / "AGENTS.md").read_text()
    assert "**Procedures**" in short and "**Response format**" in short
    assert "**Loop.** Every turn: observe, plan, act, verify." in short
    assert short.index("**Task**") < short.index("**Loop.**") < short.index("**Procedures**")
    assert "**References.**" in short and "`references/skills.md`" in short
    assert "**Skills by situation" not in short and "Crafting is ONE call" not in short
    assert "**Survival**" not in short and "control reference" not in short.split("**References.**")[0]
    refs = ws / "references"
    assert "**Skills by situation" in (refs / "skills.md").read_text()
    assert "Crafting is ONE call" in (refs / "gui.md").read_text()
    assert "**Survival**" in (refs / "survival.md").read_text()
    assert (refs / "control.md").read_text().startswith("# The benchmark's own control reference")
    assert "- `watch(" in short and "`references/procedures.md`" in short
    assert "**Procedures**" in (refs / "procedures.md").read_text()
    assert "[Aim first" in (refs / "procedures.md").read_text() or "preconditions" in short
    assert len(short.split()) < 0.3 * sum(len(t.split()) for t in
                                          [short] + [p.read_text() for p in refs.iterdir()])
    assert agent.report()["thin"] is True
    assert refs.exists()          # the end-of-turn sweep keeps references/


def test_thin_split_is_a_partition():
    from mcu_worldmodel import prompts

    full = ("**Task**: x\n\nbody\n\n**Procedures** (prefer these):\n- a\n\n"
            "**Crafting is ONE call.** c\n\n**Skills by situation**\ns\n\n"
            "**Oddity**: o\n\n# The benchmark's own control reference\nctl\n")
    short, refs = prompts.thin_split(full)
    assert short.startswith("**Task**") and "**Procedures**" in short and "**References.**" in short
    assert "**Loop.**" in short
    assert set(refs) == {"procedures.md", "gui.md", "skills.md", "more.md", "control.md"}
    assert refs["control.md"].startswith("# The benchmark's own control reference")
    assert refs["more.md"].startswith("**Oddity**")
    moved = "".join("".join(t.split()) for f, t in refs.items() if f != "procedures.md")
    assert "".join(full.split()).endswith(moved)          # the moved tail, in order, nothing lost
    assert refs["procedures.md"].startswith("**Procedures**")
    short2, refs2 = prompts.thin_split(full, tools=False)
    assert refs2 == {} and "Kept short" in short2
    untouched = "**Task**: x\nno moved headings\n"
    assert prompts.thin_split(untouched) == (untouched, {})


def _stub(pos, inv, notes, health=20, gui=False):
    return SimpleNamespace(_cur_pos=pos, _cur_inv=inv, _cur_info={"health": health},
                           _gui_open=gui, cursor_stats={},
                           memory=SimpleNamespace(add_note=notes.append))


def test_watch_ends_on_the_condition_or_the_budget():
    from mcu_worldmodel import macros_world as MW
    from mcu_worldmodel import procedures as P

    mk = lambda: {"camera": [0.0, 0.0]}      # noqa: E731
    notes: list[str] = []
    wt = MW.watch(until="inventory", n=10)[0]["_watch"]
    ag = _stub({"x": 0.0, "y": 64.0, "z": 0.0}, {"cobblestone": 3}, notes)
    assert MW._watch_tick(ag, wt, mk) is not None
    ag._cur_inv = {"cobblestone": 4}
    assert MW._watch_tick(ag, wt, mk) is None
    assert "cobblestone +1" in notes[-1] and "after 2 tick" in notes[-1]
    assert ag.cursor_stats["watch_met"] == 1

    wt = MW.watch(until="y_below:60", n=10)[0]["_watch"]
    ag = _stub({"x": 0.0, "y": 64.0, "z": 0.0}, {}, notes)
    for y in (63.0, 61.0):
        ag._cur_pos = {"x": 0.0, "y": y, "z": 0.0}
        assert MW._watch_tick(ag, wt, mk) is not None
    ag._cur_pos = {"x": 0.0, "y": 59.5, "z": 0.0}
    assert MW._watch_tick(ag, wt, mk) is None and "y 59.5" in notes[-1]

    wt = MW.watch(until="damage", n=10)[0]["_watch"]
    ag = _stub({"x": 0.0, "y": 64.0, "z": 0.0}, {}, notes, health=20)
    assert MW._watch_tick(ag, wt, mk) is not None
    ag._cur_info = {"health": 17}
    assert MW._watch_tick(ag, wt, mk) is None and "health 20 -> 17" in notes[-1]

    wt = MW.watch(until="none", n=3)[0]["_watch"]
    ag = _stub({"x": 0.0, "y": 64.0, "z": 0.0}, {}, notes)
    assert MW._watch_tick(ag, wt, mk) is not None and MW._watch_tick(ag, wt, mk) is not None
    assert MW._watch_tick(ag, wt, mk) is None
    assert "waited 3 tick" in notes[-1] and ag.cursor_stats["watch_timeouts"] == 1

    with pytest.raises(ValueError):
        MW.watch(until="lava")
    with pytest.raises(ValueError):
        MW.watch(until="moved")
    acts, note = P.expand("watch", until="moved:3", n=20)
    assert acts and "_watch" in acts[0] and acts[0]["_cost"] == 20
