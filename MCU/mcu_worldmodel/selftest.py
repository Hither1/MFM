"""Offline validation: the whole loop, with the simulator and Codex both faked.

Neither dependency is available to a quick check -- the simulator needs Java, a GPU node
and a 466 MB engine jar, and Codex needs a network round trip per turn -- so both are
replaced by scripted stand-ins and everything between them is exercised for real. What
this covers is the part most likely to be wrong: the bookkeeping. The filesystem layout,
the ground-truth channel, the milestone deltas, the belief graph, and above all the
discipline rules, which are the ones that only fire when the agent misbehaves and would
otherwise go untested until an agent misbehaved at step 4,000 of a real run.

    python -m mcu_worldmodel.selftest
"""
from __future__ import annotations

import json
import math
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

import mcu_worldmodel.agent as _agent_mod
_agent_mod.RETRY_SLEEP = lambda _s: None   # scripted failures must not wait out real backoff

from mcu_worldmodel import camera as _camera
from mcu_worldmodel.actions import parse_actions
from mcu_worldmodel.discipline import UNVERIFIED_MARK, Discipline
from mcu_worldmodel.hypotheses import CycleError, HypothesisGraph
from mcu_worldmodel.memory import MultimodalMemory
from mcu_worldmodel.milestones import (
    MilestoneLedger, hotbar_line, inventory_counts, location, nearby_mobs, vitals,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILURES.append(name)


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


# -- 1. the memory filesystem -------------------------------------------

def test_memory(root: Path) -> None:
    print("\n[memory] layout, the ground-truth channel, and who may write what")
    mem = MultimodalMemory(root / "mem")
    mem.seed_world_model("test task")
    for d in ("entities", "locations", "maps", "events", "procedures",
              "hypotheses", "world_model"):
        check(f"{d}/ exists", (mem.root / d).is_dir())
    check("six world-model docs seeded",
          len(list((mem.root / "world_model").glob("*.md"))) == 6
          and (mem.root / "world_model" / "rules.md").exists())

    mem.write_initial("test task", {"x": 0, "y": 64, "z": 0}, "f0.png")
    mem.set_plan("go north", "briefing text")
    mem.add_note("a harness note")
    mem.write_action(action_num=1, step=1, entry_desc="[ACTION] fwd x10",
                     pos={"x": 3, "y": 64, "z": 4}, prev_pos={"x": 0, "y": 64, "z": 0},
                     frame="f1.png", plan_step="1/1", verified="0/10 verified")
    log = mem.logs_path.read_text()
    check("log records the briefing once", log.count("briefing text") == 1)
    check("log records the plan", "go north" in log)
    check("log records the note", "a harness note" in log)
    check("moved is computed from position", "moved=5.00" in log,
          [l for l in log.splitlines() if "moved" in l])

    mem.append_events(5, [{"kind": "milestone", "identity": "mine_log"}])
    check("events.jsonl is append-only jsonl", len(mem.read_events()) == 1)

    before = mem.snapshot_harness_files()
    check("intact when untouched", mem.assert_harness_files_intact(before) == [])
    mem.logs_path.write_text("truncated")
    check("a shrunk harness file is detected",
          mem.assert_harness_files_intact(before) != [])

    # Per-document truncation, which is what keeps one grown document from evicting the
    # other four out of the act turn's prompt. The budget is chosen above the seeded
    # length so that only the oversized document is the one that gets cut.
    (mem.root / "world_model" / "causal.md").write_text("# Causal model\n" + "C" * 5000)
    summ = mem.world_model_summary(per_doc_chars=400)
    check("only the oversized doc is truncated", summ.count("truncated") == 1,
          summ.count("truncated"))
    check("all five docs survive an oversized one",
          all(n in summ for n in ("Spatial", "Semantic", "Dynamics",
                                  "Procedural", "Causal")), summ[:200])


# -- 2. milestones ------------------------------------------------------

def test_milestones() -> None:
    print("\n[milestones] delta rule, ordering, and the ground-truth views")
    cfg = [
        {"event": "mine_block", "identity": "mine_log",
         "objects": ["oak_log", "birch_log"], "reward": 1.0, "max_reward_times": 1},
        {"event": "craft_item", "identity": "crafting_table",
         "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1},
        {"event": "kill_entity", "identity": "kill_ender_dragon",
         "objects": ["ender_dragon"], "reward": 1.0, "max_reward_times": 1},
    ]
    led = MilestoneLedger(cfg, "t")
    led.reset(fake_info())
    check("nothing verified at reset", len(led.achieved) == 0)
    check("next target is the first rule", led.next_target()["identity"] == "mine_log")

    fired = led.update(fake_info(mine_block={"oak_log": 1}), 10)
    check("a delta fires the milestone", [f["identity"] for f in fired] == ["mine_log"])
    check("achievement records the step", led.achieved["mine_log"] == 10)

    # a second-half start: the kit holds the items, the scorer credits nothing for them
    # (measured 2026-09-07: 4/24 for a run that never rebuilt), so they stay open
    given = MilestoneLedger(cfg, "t", given=["mine_log", "not_a_rule"])
    given.reset(fake_info())
    check("given milestones are NOT credited at reset", given.achieved == {})
    check("unknown given names are ignored", given.given == ["mine_log"])
    check("the next target is the given one (still open)", given.next_target()["identity"] == "mine_log")
    check("the checklist says the kit holds it and the scorer wants it done",
          "[ ] mine_log" in given.progress_block() and "the kit HOLDS this item" in given.progress_block())
    fired = given.update(fake_info(mine_block={"oak_log": 3}), 5)
    check("a given milestone fires when it happens", [f["identity"] for f in fired] == ["mine_log"]
          and given.achieved["mine_log"] == 5)
    check("the summary lists the given ones", given.summary()["given"] == ["mine_log"])
    given.reset(fake_info())
    check("a second reset keeps the credit", given.achieved == {"mine_log": 0})
    from task_milestones import load_given_milestones, load_milestone_cfg
    half = load_milestone_cfg("ender_dragon_half"); full = load_milestone_cfg("ender_dragon")
    check("the half task carries the full task's 24 rules verbatim", half == full and len(full) == 24)
    hg = load_given_milestones("ender_dragon_half")
    check("the half task credits the first ten rules",
          hg == [c["identity"] for c in full[:10]] and hg[-1] == "mine_diamond_ore", hg)
    portal = load_milestone_cfg("ender_dragon_portal")
    check("the portal task carries the full task's 24 rules verbatim", portal == full)
    pg = load_given_milestones("ender_dragon_portal")
    check("the portal task credits the first ten rules plus obsidian and the flint and steel",
          pg == hg + ["mine_obsidian", "flint_and_steel"], pg)
    check("the from-scratch tasks credit nothing",
          load_given_milestones("ender_dragon") == [] and load_given_milestones("mine_diamond_from_scratch") == [])
    # The same absolute value at the next step must NOT re-fire -- an absolute test here
    # would make "9/10" meaningless the moment the agent mined a second log.
    fired = led.update(fake_info(mine_block={"oak_log": 1}), 11)
    check("an unchanged statistic does not re-fire", fired == [])
    fired = led.update(fake_info(mine_block={"oak_log": 7}), 12)
    check("mining more does not re-fire an achieved milestone", fired == [])

    check("next target advances", led.next_target()["identity"] == "crafting_table")
    led.update(fake_info(mine_block={"oak_log": 7},
                         kill_entity={"ender_dragon": 1}), 20)
    check("out-of-order achievement is still recorded",
          led.is_verified("kill_ender_dragon"))
    check("next target skips to the first *gap*",
          led.next_target()["identity"] == "crafting_table")
    check("not all done with a gap", not led.all_done())
    check("progress line counts correctly", "2/3" in led.progress_line(),
          led.progress_line())
    check("checklist marks both states",
          led.progress_block().count("[x]") == 2
          and led.progress_block().count("[ ]") == 1)

    inv = inventory_counts(fake_info(inventory={"oak_log": 3, "dirt": 0}))
    check("slot-keyed inventory aggregates to items, dropping air and zeros",
          inv == {"oak_log": 3}, inv)
    # The same item spread over two slots must total, which is the case the old
    # item-keyed reading silently got wrong.
    split = fake_info()
    split["inventory"][0] = {"type": "oak_log", "quantity": np.array(3)}
    split["inventory"][20] = {"type": "oak_log", "quantity": np.array(5)}
    split["inventory"][4] = {"type": "stone_pickaxe", "quantity": np.array(1)}
    check("one item across two slots is summed",
          inventory_counts(split) == {"oak_log": 8, "stone_pickaxe": 1},
          inventory_counts(split))
    check("the hotbar reports slot numbers, not just items",
          "hotbar.1=oak_logx3" in hotbar_line(split)
          and "hotbar.5=stone_pickaxex1" in hotbar_line(split), hotbar_line(split))
    check("hotbar ignores slots past the ninth",
          "oak_logx5" not in hotbar_line(split), hotbar_line(split))
    check("vitals render", vitals(fake_info()) == "health=20/20 food=20/20",
          vitals(fake_info()))
    check("mobs degrade gracefully when absent",
          nearby_mobs(fake_info()) == "none reported")
    loc = location(fake_info())
    check("location maps xpos->x", loc and loc["x"] == 1.0 and loc["y"] == 64.0, loc)


# -- 3. the belief graph ------------------------------------------------

def test_graph() -> None:
    print("\n[hypotheses] the DAG, and the no-op accounting the prompt promises")
    g = HypothesisGraph()
    g.add_or_update(id="h1", statement="there is iron below y=40", confidence=0.4,
                    kind="location", step=1)
    g.add_or_update(id="h2", statement="mine iron ore", kind="goal", step=1)
    g.add_dependency("h2", "h1", step=1)
    check("dependency recorded", g.nodes["h2"].depends_on == ["h1"])
    try:
        g.add_dependency("h1", "h2", step=2)
        check("a cycle is refused", False)
    except CycleError:
        check("a cycle is refused", True)

    # A re-send that changes nothing must not look fresh: `updated_step` drives both the
    # frontier tie-break and which nodes hold the prompt's remaining slots.
    before = g.nodes["h1"].updated_step
    g.add_or_update(id="h1", statement="there is iron below y=40", confidence=0.4, step=9)
    check("a no-op op does not refresh updated_step",
          g.nodes["h1"].updated_step == before)
    check("no-op ops are counted", g.noop_updates == 1)
    g.add_or_update(id="h1", confidence=0.8, step=10)
    check("a real change does refresh", g.nodes["h1"].updated_step == 10)

    g.add_or_update(id="h3", statement="x", status="locked", step=1)
    check("an unrecognised status is dropped", g.nodes["h3"].status == "active")

    for i in range(30):
        g.add_or_update(id=f"m{i}", statement=f"mech {i}", kind="mechanism", step=i)
    view = g.to_prompt_summary(max_items=12)
    check("the view is bounded", len([l for l in view.splitlines()
                                      if l.startswith("- [")]) <= 12)
    check("mechanisms are capped in the view",
          sum(1 for l in view.splitlines() if "(mechanism," in l) <= 4)
    check("the view says it is a view", "not shown" in view)

    ev = ["e"] * 20
    g.add_or_update(id="h1", evidence=ev, step=11)
    check("evidence is bounded and deduplicated", len(g.nodes["h1"].evidence) <= 8)


# -- 4. discipline ------------------------------------------------------

def test_discipline(root: Path) -> None:
    print("\n[discipline] the rules that only fire when the agent misbehaves")
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1}]
    led = MilestoneLedger(cfg, "t")
    led.reset(fake_info())
    g = HypothesisGraph()
    d = Discipline(g, led)

    # The core rule: the model confirms its own goal, the environment has not.
    g.add_or_update(id="mine_log", statement="I have mined a log", kind="goal",
                    status="confirmed", confidence=0.99, step=5)
    d.enforce(["mine_log"], 5)
    n = g.nodes["mine_log"]
    check("a self-confirmed goal is reverted to active", n.status == "active")
    check("its confidence drops to the reverted band", n.confidence <= 0.6, n.confidence)
    check("its STATEMENT is marked, not just its status",
          n.statement.startswith(UNVERIFIED_MARK), n.statement)
    check("the revert is counted", d.counters["goal_confirm_reverted"] == 1)

    # ... and once the environment agrees, the mark comes off.
    led.update(fake_info(mine_block={"oak_log": 1}), 6)
    d.enforce([], 6)
    check("verification clears the unverified mark",
          not g.nodes["mine_log"].statement.startswith(UNVERIFIED_MARK))

    # An unverified goal cannot sit above the ceiling the prompt states.
    g.add_or_update(id="crafting_table", statement="table made", kind="goal",
                    confidence=0.99, step=7)
    d.enforce([], 7)
    check("an unverified goal is held to the ceiling",
          g.nodes["crafting_table"].confidence <= 0.9)

    # The claim gate: what replaces ESC-gating, since MCU has no ESC.
    note = d.check_claim({"completed": ["crafting_table"]}, 8)
    check("a false completion claim is rejected", note is not None)
    check("the claimed goal is locked", "crafting_table" in d.locked)
    check("a locked goal is capped at 0.5",
          g.nodes["crafting_table"].confidence <= 0.5)
    check("locked goals appear in the prompt flags",
          d.flags(8).get("crafting_table") == "locked")
    check("a true claim is not rejected", d.check_claim({"completed": ["mine_log"]}, 9)
          is None)

    # The test budget.
    g.add_or_update(id="h9", statement="stuck belief", confidence=0.5, kind="location",
                    step=10)
    check("first sighting starts the clock", d.track_testing("h9", 10) is None)
    check("still inside the budget", d.track_testing("h9", 100) is None)
    note = d.track_testing("h9", 10 + 121)
    check("the budget retires a motionless test", note is not None)
    check("it is marked stale", g.nodes["h9"].status == "stale")

    summ = d.summary()
    check("the summary reports what fired",
          "reverted" in summ and "claim" in summ.lower(), summ)


# -- 4b. GUI geometry and recipe-driven crafting -------------------------

def test_gui() -> None:
    print("\n[gui] slot geometry and inventory-aware crafting")
    from mcu_worldmodel import gui

    # The MineRL slot numbering is the opposite vertical order to the drawn layout:
    # 0-8 is the HOTBAR (drawn at the bottom, y=142), 9-35 the main rows (y=84..).
    # Getting this backwards puts every click one region away and looks like a
    # calibration error.
    check("hotbar slot 0 is on the bottom row",
          gui.centre(gui.slot_topleft(0)) == (16.0, 150.0))
    check("main-inventory slot 9 is the top-left of the upper block",
          gui.centre(gui.slot_topleft(9)) == (16.0, 92.0))
    check("slot 35 is the bottom-right of the main block",
          gui.centre(gui.slot_topleft(35)) == (160.0, 128.0))
    check("hotbar sits below the main inventory",
          gui.centre(gui.slot_topleft(0))[1] > gui.centre(gui.slot_topleft(35))[1])
    try:
        gui.slot_topleft(36)
        check("an out-of-range slot is refused", False)
    except ValueError:
        check("an out-of-range slot is refused", True)

    check("cursor opens at the container-space screen centre",
          gui.cursor_home() == (88.0, 83.0))
    # Pinned because it was measured the hard way: MOUSE_MULTIPLIER=0.1 implies 10 px per
    # degree and that is wrong for cursor motion inside a GUI. locate_cursor.py tracked the
    # cursor by frame-diff centroid and fitted 4.17. Reverting to 10 makes every absolute
    # move overshoot by ~2.4x.
    check("px-per-degree is the measured value, not the derived one",
          abs(gui.PX_PER_DEGREE - 4.17) < 0.01, gui.PX_PER_DEGREE)
    from mcu_worldmodel.procedures import CURSOR_DEG_PER_SLOT
    check("the agent's slot unit agrees with the measured scale",
          abs(CURSOR_DEG_PER_SLOT - gui.SLOT_PITCH / gui.PX_PER_DEGREE) < 0.05,
          (CURSOR_DEG_PER_SLOT, gui.SLOT_PITCH / gui.PX_PER_DEGREE))

    inv = {i: {"type": "air", "quantity": np.array(0)} for i in range(36)}
    inv[0] = {"type": "oak_planks", "quantity": np.array(8)}
    info = {"inventory": inv}
    ok, why = gui.can_craft(info, "crafting_table")
    check("a craft with ingredients is allowed", ok, why)
    ok, why = gui.can_craft(info, "stone_pickaxe")
    check("a craft without ingredients is refused with the shortfall",
          not ok and "cobblestone" in why, why)
    check("an unknown recipe is refused",
          not gui.can_craft(info, "elytra")[0])

    acts, why = gui.craft_actions(info, "crafting_table")
    check("crafting emits a bounded action sequence", 20 < len(acts) < 200, len(acts))
    check("it moves the camera (the cursor)",
          any(a["camera"] != [0.0, 0.0] for a in acts))
    check("it both right-clicks (place) and left-clicks (take)",
          any(a["use"] for a in acts) and any(a["attack"] for a in acts))
    # Every camera delta must be one the simulator can actually deliver. This check has
    # been wrong twice by naming a number instead of the property: first `<= 8 degrees`,
    # which the bin set rounds *up* to 10, then membership in that bin set, which stopped
    # being the constraint when the green agent moved to `action_type="env"`. `camera`
    # owns the answer for whichever encoder is in the path, so ask it.
    check("every camera delta is one the simulator can deliver",
          all(_camera.deliverable(v) for a in acts for v in a["camera"]),
          sorted({round(v, 4) for a in acts for v in a["camera"]
                  if not _camera.deliverable(v)}))

    # Two cells needing the same ingredient must not both draw from a one-item stack.
    inv2 = {i: {"type": "air", "quantity": np.array(0)} for i in range(36)}
    inv2[0] = {"type": "oak_planks", "quantity": np.array(1)}
    inv2[1] = {"type": "oak_planks", "quantity": np.array(1)}
    ok, why = gui.can_craft({"inventory": inv2}, "crafting_table")
    check("a split stock that is still short is refused", not ok, why)
    inv2[2] = {"type": "oak_planks", "quantity": np.array(2)}
    acts2, why2 = gui.craft_actions({"inventory": inv2}, "crafting_table")
    check("ingredients spread across stacks are usable", bool(acts2), why2)

    # A category ingredient accepts any member.
    inv3 = {i: {"type": "air", "quantity": np.array(0)} for i in range(36)}
    inv3[5] = {"type": "spruce_planks", "quantity": np.array(4)}
    check("any plank satisfies a plank recipe",
          gui.can_craft({"inventory": inv3}, "crafting_table")[0])


# -- 5. the action contract ---------------------------------------------

def test_actions() -> None:
    print("\n[actions] the plan contract, including keys MCU does not have")
    plan = parse_actions(json.dumps({"actions": [
        {"action": {"forward": 1, "sprint": 1}, "repeat": 30},
        {"procedure": "dig_down", "args": {"n": 10}},
        {"action": {"ESC": 1}},
        {"action": {"forward": 1, "back": 1}},
        {"action": {"hotbar.1": 1, "hotbar.2": 1}},
        {"action": {"camera": [200, 270]}},
        {"bogus": True},
    ]}))
    check("raw and procedure entries both run", len(plan.entries) >= 5)

    # `craft` is registered again (macros_gui.py), closed loop this time. Called with
    # no screen open it must cost a note that says what to open, never a silent no-op
    # or a blind click sequence.
    from mcu_worldmodel import procedures as _P
    check("the closed-loop craft macro is offered", "craft" in _P.REGISTRY)
    shut = parse_actions(json.dumps({"actions": [
        {"procedure": "craft", "args": {"item": "crafting_table"}}]}),
        info=fake_info(inventory={"oak_planks": 8}))
    check("craft with no screen open yields a note, not actions",
          not shut.steps and any("no screen is open" in n for n in shut.notes),
          shut.notes)
    from mcu_worldmodel.cursor import CursorState as _CS
    _cur = _CS(); _cur.opened({"oak_planks": 8})
    laid = parse_actions(json.dumps({"actions": [
        {"procedure": "craft", "args": {"item": "crafting_table"}}]}),
        info=fake_info(inventory={"oak_planks": 8}), cursor=_cur)
    kinds = [next(k for k in s if k != "_cost") for s in laid.steps if isinstance(s, dict)]
    check("craft on an open screen is a gate, servos, clicks and a check",
          kinds[:1] == ["_screen_need"] and kinds[-1] == "_craftcheck"
          and kinds.count("_servo") >= 6 and kinds.count("_click") >= 6, kinds)
    from mcu_worldmodel import macros_gui as _MG
    spelt = parse_actions(json.dumps({"actions": [
        {"procedure": "craft", "args": {"item": "sticks"}}]}),
        info=fake_info(inventory={"oak_planks": 8}), cursor=_cur)
    check("craft takes a model's spelling of a recipe: sticks, minecraft:stick, "
          "oak_planks, eye_of_ender",
          spelt.steps and not any("no recipe" in n for n in spelt.notes)
          and _MG.recipe_name("minecraft:stick") == "stick"
          and _MG.recipe_name("oak_planks") == "planks"
          and _MG.recipe_name("eye_of_ender") == "ender_eye"
          and _MG.recipe_name("Sticks") == "stick"
          and _MG.recipe_name("nonsense") == "nonsense", spelt.notes)
    # Deferred expansion: a refused craft that is NOT the plan's first entry waits for
    # its turn (the entries before it may supply the screen or the ingredients).
    _cur2 = _CS(); _cur2.opened({})
    chained = parse_actions(json.dumps({"actions": [
        {"procedure": "collect_drops", "args": {"ticks": 48}},
        {"procedure": "craft", "args": {"item": "planks"}}]}),
        info=fake_info(inventory={}), cursor=_cur2)
    later = [st for st in chained.steps if isinstance(st, dict) and "_later" in st]
    check("a craft refused at parse time behind another entry is queued as _later, "
          "not dropped, and the note says so",
          len(later) == 1 and later[0]["_later"]["name"] == "craft"
          and any("will expand when its turn comes" in n for n in chained.notes),
          f"{[list(st)[0] for st in chained.steps]} {chained.notes}")
    _cur3 = _CS(); _cur3.opened({})
    alone = parse_actions(json.dumps({"actions": [
        {"procedure": "craft", "args": {"item": "planks"}}]}),
        info=fake_info(inventory={}), cursor=_cur3)
    check("the same craft as the plan's FIRST entry is refused outright",
          not alone.steps and any("need" in n and "have 0" in n for n in alone.notes), alone.notes)
    _cur4 = _CS(); _cur4.opened({"oak_log": 2})
    part = parse_actions(json.dumps({"actions": [
        {"procedure": "craft", "args": {"item": "planks", "count": 3}}]}),
        info=fake_info(inventory={"oak_log": 2}), cursor=_cur4)
    check("a craft asked for more than the ingredients allow makes what it can and says so",
          part.steps and any("crafting 2x planks" in n and "only 2 of the 3 asked" in n
                             for n in part.notes)
          and not any("need" in n and "have 2" in n for n in part.notes), part.notes)
    check("a 3x3 recipe short of ingredients is refused with the shortfall",
          not parse_actions(json.dumps({"actions": [
              {"procedure": "craft", "args": {"item": "stone_pickaxe"}}]}),
              info=fake_info(inventory={"cobblestone": 1}), cursor=_cur).steps)
    check("the GUI primitives it needs are still offered",
          all(k in _P.REGISTRY for k in
              ("open_inventory", "close_inventory", "cursor_to",
               "gui_click", "gui_right_click")))
    check("ESC is dropped with a note",
          any("ESC" in n for n in plan.notes), plan.notes)
    check("forward+back is cancelled",
          any("cancel" in n for n in plan.notes))
    check("multiple hotbars are reduced to one",
          any("hotbar" in n for n in plan.notes))
    check("an entry with neither key is skipped",
          any("neither" in n for n in plan.notes))
    # Closed-loop markers (`_chop`, `_dig`, `_servo`) carry no camera key; only the raw
    # env-action steps do.
    cam = [s for s in plan.steps if "camera" in s and s["camera"] != [0.0, 0.0]]
    check("pitch is clamped to 90", all(abs(s["camera"][0]) <= 90 for s in cam))
    check("yaw 270 normalises to -90", any(s["camera"][1] == -90.0 for s in cam),
          [s["camera"] for s in cam][:5])

    deep = parse_actions(json.dumps({"actions": [
        {"procedure": "dig_down", "args": {"n": 390, "until_y": 12}}]}))
    dig = next((st for st in deep.steps if "_dig" in st), None)
    check("actions: an over-budget dig_down is shrunk to fit, not dropped",
          dig is not None and dig["_dig"]["remaining"] == 360 and dig["_cost"] == 360
          and dig["_dig"]["until_y"] == 12.0
          and any("shrunk to fit" in n for n in deep.notes), str(deep.notes))
    stair = parse_actions(json.dumps({"actions": [
        {"procedure": "stair_down", "args": {"depth": 30}}]}))
    mf = next((st for st in stair.steps if "_mfwd" in st), None)
    check("actions: an over-budget stair_down is shrunk to the cap",
          mf is not None and mf["_cost"] == 400 and mf["_mfwd"]["budget"] == 400
          and sum(int(st.get("_cost", 1)) for st in stair.steps) <= 400, str(stair.notes)[:200])
    ahead = parse_actions(json.dumps({"actions": [
        {"action": {"forward": 1}, "repeat": 50},
        {"procedure": "mine_ahead", "args": {"n": 500}}]}))
    seq = next((st for st in ahead.steps if "_seq" in st), None)
    check("actions: an over-budget mine_ahead keeps its first ticks",
          seq is not None and seq["_cost"] == 350 and len(seq["_seq"]["steps"]) == 350,
          str(ahead.notes)[:200])
    capped = parse_actions(json.dumps({"actions": [
        {"action": {"forward": 1}, "repeat": 5000}]}), step_cap=100)
    check("the step cap is enforced", len(capped) == 100, len(capped))
    check("malformed json yields an empty plan and a note",
          not parse_actions("{not json").steps)


# -- 6. the loop, with both dependencies faked ---------------------------

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
        # let turn 2's claim.json be re-read on turns 3..N and make this test pass or
        # fail for reasons the real backend never has.
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


def test_cursor() -> None:
    """The harness-held cursor: does an absolute address actually land on the slot?

    This is the claim the whole module rests on. If the tracked position drifts, an
    absolute address is worse than the relative nudging it replaced, because the agent is
    told the position is exact and will stop checking.
    """
    import math

    from mcu_worldmodel import gui as G
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.cursor import CursorState

    print("\n[cursor] the harness-held GUI cursor")

    worst = 0.0
    for slot in range(36):
        cur = CursorState()
        cur.opened({})
        acts, note = P.cursor_to_slot(cur, slot)
        worst = max(worst, math.dist(cur.pos, G.centre(G.slot_topleft(slot))))
    # Slot boxes are 16 px; landing inside means the click hits. Half a box is the
    # tolerance, not the expectation -- the measured worst case is ~1.6 px.
    check("every player slot is reachable from a cold open", worst < 8.0, f"{worst:.2f}px")

    # The failure the absolute form exists to remove: error accumulating across a chain.
    cur = CursorState()
    cur.opened({})
    chain = [("slot", 3), ("cell", 0), ("cell", 1), ("cell", 2), ("cell", 4),
             ("cell", 7), ("slot", 3), ("cell", "out"), ("slot", 12), ("cell", 3)]
    for kind, v in chain:
        if kind == "slot":
            P.cursor_to_slot(cur, v)
        else:
            P.cursor_to_cell(cur, "3x3", v)
    end = math.dist(cur.pos, G.centre(G.TABLE_CRAFT_IN[3]))
    check("a ten-move chain does not accumulate error", end < 8.0, f"{end:.2f}px")
    check("the cursor knows which cell it is over", "3x3 cell 3" in cur.over(), cur.over())

    # An absolute address must parse whatever the projection believes about the screen:
    # a runtime-refused close leaves reality open where the projection says closed, and
    # the recovery entries after it (re-address, put back, close) must not be dropped at
    # parse. The runner stops the servo with a [NOTE] if no screen is truly open.
    cur = CursorState()
    acts, note = P.cursor_to_slot(cur, 3)
    check("an absolute address parses even while the projection thinks it is closed",
          len(acts) == 1 and "_servo" in acts[0] and note == "", f"{acts} {note!r}")

    # Items that have left the player inventory are in the cursor or in a grid. The
    # harness cannot tell those apart and does not claim to; what it reports is that they
    # are not anywhere safe, which is what closing the screen turns into dropped items.
    cur = CursorState()
    cur.opened({})
    cur.anchor(G.centre(G.FURNACE_FUEL))
    check("the furnace fuel slot is addressable and reported",
          "furnace fuel" in cur.over(), cur.over())
    acts, _ = P.cursor_to_cell(cur, "furnace", 0)
    check("cursor_to_cell knows the furnace grid",
          acts and acts[0]["_servo"]["tx"] == G.centre(G.FURNACE_IN)[0], str(acts))

    cur = CursorState()
    cur.opened({"cobblestone": 3, "stick": 2})
    check("off-inventory is measured against the screen opening",
          cur.off_inventory({"stick": 2}) == {"cobblestone": 3})
    _, note = P.close_screen(cur)
    check("closing with items off-inventory warns", "cobblestonex3" in note, note)
    check("closing with everything stowed is silent",
          P.close_screen(CursorState()) [1] == "")

    # A plan is parsed against a projection, so a later absolute address sees where the
    # earlier entries left the cursor -- including a raw camera entry in between.
    cur = CursorState()
    plan = parse_actions(json.dumps({"actions": [
        {"procedure": "open_inventory"},
        {"procedure": "cursor_to_slot", "args": {"slot": 0}},
        {"action": {"camera": [3.215, 3.215]}, "repeat": 2},
        {"procedure": "cursor_to_slot", "args": {"slot": 0}},
    ]}), cursor=cur)
    check("the projection survives a raw camera entry mid-plan",
          math.dist(cur.pos, G.centre(G.slot_topleft(0))) < 8.0,
          f"{math.dist(cur.pos, G.centre(G.slot_topleft(0))):.2f}px")
    check("a whole-recipe plan fits under the entry cap",
          len(parse_actions(json.dumps({"actions":
              [{"procedure": "open_inventory"}]
              + [{"procedure": "cursor_to_cell", "args": {"grid": "3x3", "cell": c}}
                 for c in range(9)]
              + [{"procedure": "gui_right_click"} for _ in range(9)]
              + [{"procedure": "close_inventory"}]}), cursor=CursorState()).entries) == 20)


def test_gui_feedback(root: Path) -> None:
    """[INV] and [GUI] must reach logs.txt.

    `write_action` has always accepted both and `_log_entry_done` passed neither, so the
    diamond run's log carried 0 [INV] lines across 194 entries while the prompt told the
    agent [INV] was the ground truth for what a click did. The regression is silent -- the
    log looks fine, it just cannot answer the one question GUI work asks of it -- so it is
    pinned here rather than left to a reviewer noticing an absent line.
    """
    print("\n[gui-feedback] the closed loop's evidence channel")
    from mcu_worldmodel.agent import WorldModelAgent

    led = MilestoneLedger([{"event": "craft_item", "identity": "crafting_table",
                            "objects": ["crafting_table"], "reward": 1.0,
                            "max_reward_times": 1}], "t")
    agent = WorldModelAgent(workspace=root / "gws", task_text="craft a table",
                            ledger=led, induction_every=0, step_cap=50)
    agent.codex = FakeCodex(agent.memory.root, [
        {"actions": {"actions": [{"procedure": "open_inventory"},
                                 {"procedure": "cursor_to_slot", "args": {"slot": 0}},
                                 {"procedure": "gui_click"}]},
         "message": "[PLAN]\npick the planks up"},
        {"actions": {"actions": [{"procedure": "close_inventory"}]},
         "message": "[PLAN]\nclose"},
    ] + [{"actions": {"actions": [{"action": {"forward": 1}, "repeat": 3}]},
          "message": "[PLAN]\nwalk"} for _ in range(6)])

    # Four planks, then the screen opens, then the stack leaves the slot (it is in the
    # cursor), then the screen closes with it still there. The planks do not come back:
    # they are an item entity on the floor now, which is the failure being detected.
    def info_at(step: int) -> dict:
        i = fake_info(inventory={"oak_planks": 4} if step < 4 else {})
        i["isGuiOpen"] = 2 <= step <= 12
        return i

    info = info_at(0)
    agent.start(info)
    for step in range(1, 20):
        agent.next_action(info)
        info = info_at(step)
        agent.observe(info, step)

    log = agent.memory.logs_path.read_text()
    check("[INV] reaches logs.txt", "[INV]" in log,
          "write_action supports it; _log_entry_done must pass it")
    check("[INV] is signed and names the item", "oak_planks -4" in log,
          [ln for ln in log.splitlines() if ln.startswith("[INV]")])
    check("[GUI] reaches logs.txt", "[GUI] open=True" in log)
    check("closing with the stack still held is warned about",
          "not in any inventory slot" in log,
          [ln for ln in log.splitlines() if ln.startswith("[NOTE]")])
    check("the turn prompt carries the [CURSOR] line",
          any("[CURSOR]" in p for p in agent.codex.prompts),
          agent.codex.prompts[:1])


def test_loop(root: Path) -> None:
    print("\n[loop] act turns, the queue, induction, and end-to-end bookkeeping")
    from mcu_worldmodel.agent import WorldModelAgent

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1}]
    led = MilestoneLedger(cfg, "t")
    agent = WorldModelAgent(workspace=root / "ws", task_text="get a log",
                            ledger=led, induction_every=10, step_cap=50)
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "briefing one\n[PLAN]\nwalk to the trees",
         "files": {"hypotheses_ops.json": {
             "hypotheses": [{"id": "mine_log", "statement": "a log is gettable",
                             "kind": "goal", "confidence": 0.3},
                            {"id": "trees_north", "statement": "trees to the north",
                             "kind": "location", "confidence": 0.5,
                             "depends_on": ["mine_log"]}],
             "testing": "trees_north"}}},
        {"actions": {"actions": [{"procedure": "chop_tree", "args": {"n": 5}}]},
         "message": "briefing two\n[PLAN]\nchop",
         "files": {"claim.json": {"completed": ["crafting_table"]}}},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 5}]},
          "message": "[PLAN]\nkeep going"} for _ in range(12)]
    agent.codex = FakeCodex(agent.memory.root, script)

    info = fake_info()
    agent.start(info)
    check("AGENTS.md written once", (agent.memory.root / "AGENTS.md").exists())

    # Positions advance so that the log's `moved` is measurable rather than always 0.
    for step in range(1, 31):
        agent.next_action(info)
        if step == 12:
            info = fake_info(mine_block={"oak_log": 1})
        else:
            info = fake_info() if step != 12 else info
        info["location_stats"]["xpos"] = np.array(float(step))
        agent.observe(info, step)

    check("act turns fired only when the queue ran dry",
          2 <= agent.turns["act"] <= 8, agent.turns)
    check("induction turns fired on schedule", agent.turns["induction"] >= 2,
          agent.turns)
    check("the milestone was picked up from info", led.is_verified("mine_log"))
    check("the graph persisted to disk", (agent.memory.graph_path).exists())
    check("one .md per belief was projected",
          len(list((agent.memory.root / "hypotheses").glob("*.md"))) >= 2)
    check("dependencies survived the round trip",
          agent.graph.nodes["trees_north"].depends_on == ["mine_log"])

    # The claim in turn 2 named a milestone the environment never verified.
    check("the false claim was rejected", agent.discipline.counters["claim_rejected"] == 1)
    log = agent.memory.logs_path.read_text()
    check("the rejection reached the log as a NOTE", "[NOTE]" in log and "claimed" in log)
    check("the briefing reached the log", "briefing one" in log)
    check("milestone events reached the log", "MILESTONE mine_log" in log)

    # An induction turn must not leave an executable actions.json behind.
    check("induction leaves no stale actions.json",
          not (agent.memory.root / "actions.json").exists())

    # The bug this guards: logging at planning time used the same position for `pos` and
    # `prev_pos`, so every [STATE] line read moved=0.00 -- the one number the prompt tells
    # the agent to trust over its own read of a frame.
    moved = [l for l in log.splitlines() if "moved=" in l]
    check("log sections report real movement, not moved=0.00 everywhere",
          any(not l.endswith("moved=0.00") for l in moved),
          moved[:4])
    # `>= turns - 1`, not `>= turns`: a section is written when an entry *finishes*, so the
    # plan still in flight when the loop stops has none yet. The property under test is that
    # logging is per entry rather than per turn, which a per-turn regression would break by
    # an order of magnitude, not by one.
    check("one log section per plan entry, not per turn",
          log.count("[ACTION]") >= agent.turns["act"] - 1,
          (log.count("[ACTION]"), agent.turns["act"]))

    rep = agent.report()
    check("the report carries milestones, beliefs and discipline",
          rep["milestones"]["milestones_achieved"] == 1
          and rep["hypotheses"]["n"] >= 2 and "claim_rejected" in rep["discipline"], rep)


def test_closed_loop(root: Path) -> None:
    """The measured cursor, end to end: a synthetic screen whose pointer moves at a
    deliberately wrong scale (5.0 px/degree against the assumed 4.17) and in integer
    pixels, rendered with the real sprite so `vision.find_cursor` is in the loop. What
    open-loop expansion could never survive -- and dm4_wmv2 did not -- the servo must."""
    print("\n[closed-loop] the measured cursor: servo, chop early-stop, close guard")
    from mcu_worldmodel import gui, vision
    from mcu_worldmodel.agent import WorldModelAgent

    def render(cx: float, cy: float) -> np.ndarray:
        f = np.full((360, 640, 3), 197, dtype=np.uint8)
        for pts, val in ((vision.BLACK, 0), (vision.WHITE, 255)):
            for dy, dx in pts:
                y, x = int(cy) + dy, int(cx) + dx
                if 0 <= y < 360 and 0 <= x < 640:
                    f[y, x] = val
        return f

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "cl", task_text="t",
                            ledger=MilestoneLedger(cfg, "t"),
                            induction_every=0, step_cap=400)
    agent.codex = FakeCodex(agent.memory.root, [
        {"actions": {"actions": [
            {"procedure": "open_inventory"},
            {"procedure": "cursor_to_slot", "args": {"slot": 0}},
            {"procedure": "gui_click"},
            {"procedure": "cursor_to_cell", "args": {"grid": "2x2", "cell": 0}},
            {"procedure": "close_inventory"},                  # refused: stack in hand
            {"procedure": "cursor_to_slot", "args": {"slot": 0}},
            {"procedure": "gui_click"},                        # put it back
            {"procedure": "close_inventory"},                  # passes
        ]}, "message": "[PLAN]\npick up, be refused, stow, close"},
        {"actions": {"actions": [
            {"procedure": "chop_tree", "args": {"n": 50}},
            {"procedure": "dig_down", "args": {"n": 200, "until_y": 60}},
        ]}, "message": "[PLAN]\nchop with early stop, then dig to depth"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])

    TRUE_SCALE = 5.0
    st = {"gui": False, "cur": (320.0, 180.0), "logs": 3, "held": 0,
          "prev_attack": 0, "chop_ticks": 0, "mined": 0, "y": 64.0, "dig_ticks": 0}

    def info_now() -> dict:
        inv = {"spruce_log": st["logs"]} if st["logs"] else None
        i = fake_info(inventory=inv)
        i["isGuiOpen"] = st["gui"]
        i["location_stats"]["ypos"] = np.array(st["y"])
        if st["mined"]:
            i["mine_block"]["spruce_log"] = np.array(float(st["mined"]))
        i["pov"] = (render(*st["cur"]) if st["gui"]
                    else np.full((360, 640, 3), 120, dtype=np.uint8))
        return i

    agent.start(info_now())
    for step in range(1, 180):
        a = agent.next_action(info_now())
        if a.get("inventory"):
            st["gui"] = not st["gui"]
            st["cur"] = (320.0, 180.0)
        cam = a.get("camera") or [0.0, 0.0]
        if st["gui"] and (cam[0] or cam[1]):
            st["cur"] = (min(639.0, max(0.0, round(st["cur"][0] + cam[1] * TRUE_SCALE))),
                         min(359.0, max(0.0, round(st["cur"][1] + cam[0] * TRUE_SCALE))))
        rising = a.get("attack") and not st["prev_attack"]
        st["prev_attack"] = a.get("attack", 0)
        if st["gui"] and rising:
            ox, oy = gui.container_origin()
            cont = (st["cur"][0] - ox, st["cur"][1] - oy)
            tl = gui.slot_topleft(0)
            if tl[0] <= cont[0] < tl[0] + 16 and tl[1] <= cont[1] < tl[1] + 16:
                if st["held"] == 0 and st["logs"]:
                    st["held"], st["logs"] = st["logs"], 0
                elif st["held"]:
                    st["logs"], st["held"] = st["held"], 0
        if not st["gui"] and a.get("attack"):
            if not st["mined"]:
                st["chop_ticks"] += 1
                if st["chop_ticks"] == 7:
                    st["logs"] += 1
                    st["mined"] += 1
            else:                              # attacks after the chop stopped = the dig
                st["dig_ticks"] += 1
                if st["dig_ticks"] % 8 == 0:   # eight ticks a block, roughly stone speed
                    st["y"] -= 1.0
        agent.observe(info_now(), step)
    cs = agent.cursor_stats
    check("servo moves arrived (measured, wrong scale, integer px)",
          cs["servo_ok"] >= 3 and cs["servo_gave_up"] == 0, str(cs))
    check("anchoring corrected real drift", cs["drift_max"] > 0.5, str(cs))
    check("the pickup click landed on slot 0 and the stack came back",
          st["logs"] == 4 and st["held"] == 0, str(st))
    check("the dropping close was refused, the stowed close passed",
          cs["close_blocked"] == 1 and st["gui"] is False, str(cs))
    log_text = (agent.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("the refusal reached the log as a NOTE", "close refused" in log_text)
    check("[CURSOR] lines reach logs.txt now", "[CURSOR]" in log_text)
    check("chop stopped when the block broke, not at its 50-tick budget",
          cs["chop_early_stops"] == 1 and st["chop_ticks"] < 15, str(st))
    check("dig stopped at its target depth, not at its 200-tick budget",
          cs.get("dig_reached_depth") == 1 and st["y"] <= 60.5
          and st["dig_ticks"] < 60, str(st))
    check("stat events reached events.jsonl",
          '"kind":"stat"' in (agent.memory.root / "events"
                              / "events.jsonl").read_text(encoding="utf-8"))
    # look_at: pure trigonometry against [STATE] ground truth. The oracle is live data:
    # the wmv3 agent measured "yaw about -15" for spawn -> first trunk, and MC's yaw
    # convention (0 = +z, positive clockwise) must reproduce it.
    from mcu_worldmodel import procedures as P2
    la_info = fake_info()
    la_info["location_stats"].update(
        {"xpos": np.array(-3009.5), "ypos": np.array(71.0), "zpos": np.array(-5572.5),
         "pitch": np.array(0.0), "yaw": np.array(0.0)})
    la_acts, la_note = P2.look_at(la_info, x=-3008.72, y=73.0, z=-5569.58)
    la_yaw = sum(a["camera"][1] for a in la_acts)
    la_pitch = sum(a["camera"][0] for a in la_acts)
    check("look_at reproduces the live-measured heading to the first trunk",
          abs(la_yaw - (-15.0)) < 2.0 and -15.0 < la_pitch < 0.0,
          f"yaw {la_yaw:.1f} pitch {la_pitch:.1f} {la_note}")

    # use_until_gui: the screen opens on the second press; the marker must stop there.
    agent2 = WorldModelAgent(workspace=root / "ug", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"),
                             induction_every=0, step_cap=400)
    agent2.codex = FakeCodex(agent2.memory.root, [
        {"actions": {"actions": [{"procedure": "use_until_gui", "args": {"n": 5}}]},
         "message": "[PLAN]\nopen the table"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])
    ug = {"gui": False, "presses": 0}
    def ug_info():
        i = fake_info()
        i["isGuiOpen"] = ug["gui"]
        i["pov"] = np.full((360, 640, 3), 120, dtype=np.uint8)
        return i
    agent2.start(ug_info())
    for step in range(1, 25):
        a = agent2.next_action(ug_info())
        if a.get("use"):
            ug["presses"] += 1
            if ug["presses"] == 2:
                ug["gui"] = True
        agent2.observe(ug_info(), step)
    check("use_until_gui stops the moment the screen opens",
          ug["presses"] == 2
          and agent2.cursor_stats.get("use_gui_opened") == 1, str(ug))
    # The screen the last press opened shows up 12 ticks later (server lag, kd41z_lb
    # step 11775): still a success, counted as late; never opening is the failure
    # note only after the 20-tick grace.
    for late, opens in ((12, True), (99, False)):
        agent3 = WorldModelAgent(workspace=root / f"ug{late}", task_text="t",
                                 ledger=MilestoneLedger(cfg, "t"),
                                 induction_every=0, step_cap=400)
        agent3.codex = FakeCodex(agent3.memory.root, [
            {"actions": {"actions": [{"procedure": "use_until_gui", "args": {"n": 2}}]},
             "message": "[PLAN]\nopen the furnace"},
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
        ])
        ug = {"gui": False, "presses": 0, "since": None}
        ticks_to_end = None
        for step in range(1, 60):
            a = agent3.next_action(ug_info())
            if a.get("use"):
                ug["presses"] += 1
                if ug["presses"] == 2:
                    ug["since"] = 0
            elif ug["since"] is not None:
                ug["since"] += 1
                if ug["since"] == late:
                    ug["gui"] = True
            agent3.observe(ug_info(), step)
            if ticks_to_end is None and not agent3.queue and ug["presses"] == 2:
                ticks_to_end = step
        notes = " | ".join(agent3.memory._pending_notes) + agent3.memory.logs_path.read_text()
        if opens:
            check("a screen reported 12 ticks after the last press is a late success",
                  ug["presses"] == 2 and agent3.cursor_stats.get("use_gui_opened") == 1
                  and agent3.cursor_stats.get("use_gui_late_open") == 1
                  and "no screen opened" not in notes, f"{ug} {agent3.cursor_stats}")
        else:
            check("no screen at all: the failure note comes after the 20-tick grace",
                  ug["presses"] == 2 and "no screen opened" in notes
                  and not agent3.cursor_stats.get("use_gui_opened")
                  and ticks_to_end is not None and ticks_to_end >= 24,
                  f"{ug} end={ticks_to_end} {agent3.cursor_stats}")

    # Miss-fast chop: the env breaks leaves, never wood; the macro must name the wrong
    # target and stop within a few ticks instead of running its 120-tick budget.
    agent_m = WorldModelAgent(workspace=root / "mf", task_text="t",
                              ledger=MilestoneLedger(cfg, "t"),
                              induction_every=0, step_cap=400)
    agent_m.codex = FakeCodex(agent_m.memory.root, [
        {"actions": {"actions": [{"procedure": "chop_tree", "args": {"n": 120}}]},
         "message": "[PLAN]\nchop at leaves by mistake"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])
    mf = {"attacks": 0}
    def mf_info():
        i = fake_info()
        if mf["attacks"] >= 3:
            i["mine_block"]["spruce_leaves"] = np.array(float(min(2, mf["attacks"] - 2)))
        i["pov"] = np.full((360, 640, 3), 120, dtype=np.uint8)
        return i
    agent_m.start(mf_info())
    for step in range(1, 30):
        a = agent_m.next_action(mf_info())
        if a.get("attack"):
            mf["attacks"] += 1
        agent_m.observe(mf_info(), step)
    log_m = (agent_m.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("a chop breaking the wrong block stops fast and names it",
          agent_m.cursor_stats.get("chop_wrong_target") == 1 and mf["attacks"] < 12
          and "breaking spruce_leaves" in log_m, str(mf))

    # Ore sighting: a strip mine whose 30th tick brings iron-ore texture on screen must
    # stop there with a naming [NOTE], not tunnel past it.
    from mcu_worldmodel import vision as _V
    tex = np.zeros((16, 16, 3), np.uint8)
    tex[:] = (136, 131, 127)
    for yy in range(3, 13, 3):
        for xx in range(3, 13, 3):
            tex[yy:yy + 2, xx:xx + 2] = (196, 160, 133)
    ore_face = np.kron(tex, np.ones((2, 2, 1))).astype(np.uint8)
    agent_o = WorldModelAgent(workspace=root / "ore", task_text="t",
                              ledger=MilestoneLedger(cfg, "t"),
                              induction_every=0, step_cap=400)
    agent_o.codex = FakeCodex(agent_o.memory.root, [
        {"actions": {"actions": [{"procedure": "strip_mine", "args": {"length": 160}},
                                 {"procedure": "travel", "args": {"n": 40}}]},
         "message": "[PLAN]\ntunnel, then walk on"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])
    ore = {"ticks": 0}
    def ore_info():
        i = fake_info()
        f = np.full((360, 640, 3), 110, np.uint8)
        if ore["ticks"] >= 30:
            f[160:192, 300:332] = ore_face
        i["pov"] = f
        return i
    agent_o.start(ore_info())
    for step in range(1, 70):
        a = agent_o.next_action(ore_info())
        if a.get("attack") or a.get("forward"):
            ore["ticks"] += 1
        agent_o.observe(ore_info(), step)
    log_o = (agent_o.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("a mining macro stops on an iron-ore sighting and says where",
          agent_o.cursor_stats.get("ore_flagged") == 1 and ore["ticks"] < 50
          and "iron-ore-like speckles" in log_o,
          f"{ore} {agent_o.cursor_stats.get('ore_flagged')}")
    # The same sentinel, a diamond-ore face (cyan dots on grey) at the 30th tick.
    tex_d = np.zeros((16, 16, 3), np.uint8)
    tex_d[:] = (110, 110, 108)
    for yy in range(3, 13, 3):
        for xx in range(3, 13, 3):
            tex_d[yy:yy + 2, xx:xx + 2] = (87, 191, 182)
    dia_face = np.kron(tex_d, np.ones((2, 2, 1))).astype(np.uint8)
    agent_d = WorldModelAgent(workspace=root / "ore_d", task_text="t",
                              ledger=MilestoneLedger(cfg, "t"),
                              induction_every=0, step_cap=400)
    agent_d.codex = FakeCodex(agent_d.memory.root, [
        {"actions": {"actions": [{"procedure": "strip_mine", "args": {"length": 160}}]},
         "message": "[PLAN]\ntunnel"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])
    ore_d = {"ticks": 0}
    def ore_d_info():
        i = fake_info()
        f = np.full((360, 640, 3), 110, np.uint8)
        if ore_d["ticks"] >= 30:
            f[160:192, 300:332] = dia_face
        i["pov"] = f
        return i
    agent_d.start(ore_d_info())
    for step in range(1, 70):
        a = agent_d.next_action(ore_d_info())
        if a.get("attack") or a.get("forward"):
            ore_d["ticks"] += 1
        agent_d.observe(ore_d_info(), step)
    log_d = (agent_d.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("a mining macro stops on a diamond-ore sighting, names the kind and counts it",
          agent_d.cursor_stats.get("ore_flagged") == 1
          and agent_d.cursor_stats.get("ore_flagged_diamond") == 1 and ore_d["ticks"] < 50
          and "diamond-ore-like speckles" in log_d,
          f"{ore_d} {agent_d.cursor_stats}")
    # The flag must also flush the QUEUED remainder of the plan (the travel entry) --
    # ked3's sighting was walked off-screen by exactly such an entry -- and persist the
    # flag-time frame under a name the [NOTE] hands to zoom.
    ore_frames = list(agent_o.memory.frames_dir.glob("*_ore.png"))
    check("an ore flag drops the queued rest of the plan",
          agent_o.cursor_stats.get("ore_flush_dropped") == 1,
          str(agent_o.cursor_stats.get("ore_flush_dropped")))
    check("the flag-time frame is saved and the [NOTE] names it",
          len(ore_frames) == 1 and ore_frames[0].name in log_o,
          f"{[f.name for f in ore_frames]}")

    # go_to: closed-loop walk. The env moves the player 0.2 blocks per forward tick
    # along the facing and applies camera yaw exactly; starting 40 degrees off-heading,
    # the walker must turn first, then walk, and stop within reach of the target.
    agent3 = WorldModelAgent(workspace=root / "gt", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"),
                             induction_every=0, step_cap=400)
    agent3.codex = FakeCodex(agent3.memory.root, [
        {"actions": {"actions": [{"procedure": "go_to",
                                  "args": {"x": 6.0, "z": 10.0, "n": 100}}]},
         "message": "[PLAN]\nwalk there"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"},
    ])
    import math as _m
    gt = {"x": 1.0, "z": 2.0, "yaw": 40.0, "walk": 0}
    def gt_info():
        i = fake_info()
        i["location_stats"].update({"xpos": np.array(gt["x"]), "zpos": np.array(gt["z"]),
                                    "yaw": np.array(gt["yaw"])})
        i["pov"] = np.full((360, 640, 3), 120, dtype=np.uint8)
        return i
    agent3.start(gt_info())
    for step in range(1, 120):
        a = agent3.next_action(gt_info())
        cam = a.get("camera") or [0.0, 0.0]
        gt["yaw"] = ((gt["yaw"] + cam[1] + 180.0) % 360.0) - 180.0
        if a.get("forward"):
            gt["walk"] += 1
            r = _m.radians(gt["yaw"])
            gt["x"] += -_m.sin(r) * 0.2
            gt["z"] += _m.cos(r) * 0.2
        agent3.observe(gt_info(), step)
    dist = _m.hypot(gt["x"] - 6.0, gt["z"] - 10.0)
    check("go_to turns, walks and arrives within reach",
          agent3.cursor_stats.get("goto_arrived") == 1 and dist < 1.6
          and gt["walk"] < 80, f"dist {dist:.2f} {gt}")

    # Grid occupancy against the run that motivated it: dm4_wmv8 step 4200 has three
    # items stuck in the survival 2x2 (cells 1,2,3) and an empty 3x3 -- when those
    # archived frames are present, the reading must reproduce that.
    from pathlib import Path as _P
    real = _P("output/dm4_wmv8/episode_001/memory/episodes/ep_0000/frames/step_4200.png")
    if real.exists():
        from PIL import Image as _Img
        fr = np.array(_Img.open(real).convert("RGB"))
        ox2, oy2 = gui.container_origin()
        occ2 = [vision.slot_occupied(fr, int(ox2 + tl[0]), int(oy2 + tl[1]))
                for tl in gui.SURVIVAL_CRAFT_IN]
        occ3 = [vision.slot_occupied(fr, int(ox2 + tl[0]), int(oy2 + tl[1]))
                for tl in gui.TABLE_CRAFT_IN]
        check("grid occupancy reproduces the wmv8 stuck-ingredient frame",
              occ2 == [False, True, True, True] and not any(occ3),
              f"2x2={occ2} 3x3={occ3}")
    fgrid = np.full((360, 640, 3), 139, np.uint8)
    ox2, oy2 = gui.container_origin()
    tlx, tly = gui.TABLE_CRAFT_IN[4]
    fgrid[int(oy2 + tly):int(oy2 + tly) + 16,
          int(ox2 + tlx):int(ox2 + tlx) + 16] = ore_face[:16, :16]
    check("a textured icon reads occupied, flat grey reads empty",
          vision.slot_occupied(fgrid, int(ox2 + tlx), int(oy2 + tly))
          and not vision.slot_occupied(fgrid, int(ox2 + gui.TABLE_CRAFT_IN[0][0]),
                                       int(oy2 + gui.TABLE_CRAFT_IN[0][1])))

    # Death detection: a >15-block teleport with full health voids the plan and writes
    # the death coordinates; a 4-heart drop interrupts with a damage note.
    agent_d = WorldModelAgent(workspace=root / "dd", task_text="t",
                              ledger=MilestoneLedger(cfg, "t"),
                              induction_every=0, step_cap=400)
    agent_d.codex = FakeCodex(agent_d.memory.root, [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 30}]},
         "message": "[PLAN]\nwalk"},
    ] + [{"actions": {"actions": [{"action": {}, "repeat": 1}]},
          "message": "[PLAN]\n-"} for _ in range(8)])
    dd = {"x": -3007.0, "y": 16.0, "z": -5569.0, "hp": 20.0}
    def dd_info():
        i = fake_info()
        i["location_stats"].update({"xpos": np.array(dd["x"]), "ypos": np.array(dd["y"]),
                                    "zpos": np.array(dd["z"])})
        i["health"] = np.array(dd["hp"])
        i["pov"] = np.full((360, 640, 3), 120, dtype=np.uint8)
        return i
    agent_d.start(dd_info())
    for step in range(1, 12):
        agent_d.next_action(dd_info())
        if step == 4:
            dd["hp"] = 12.0                    # fall damage
        if step == 8:                          # death: teleport to spawn, full health
            dd.update({"x": -3009.5, "y": 71.0, "z": -5572.5, "hp": 20.0})
        agent_d.observe(dd_info(), step)
    log_d = (agent_d.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("a big health drop interrupts the plan with a damage note",
          agent_d.cursor_stats.get("damage_interrupts") == 1
          and "took 8 damage" in log_d, str(agent_d.cursor_stats))
    check("a death is detected and located in the log",
          agent_d.cursor_stats.get("deaths") == 1 and "YOU DIED at (-3007, 16" in log_d,
          str(agent_d.cursor_stats))

    zoom = agent.memory.root / "tools" / "zoom.py"
    frame = agent.memory.root / "episodes" / "ep_0000" / "frames" / "step_0000.png"
    ran = __import__("subprocess").run(
        [sys.executable, str(zoom), str(frame), "10", "10", "20", "15"],
        cwd=agent.memory.root, capture_output=True)
    check("tools/zoom.py exists and magnifies a frame region",
          ran.returncode == 0 and (agent.memory.root / "zoom.png").exists(),
          ran.stderr.decode()[:200])




def test_logbook(root: Path) -> None:
    """The claim-M control arm: PRO-LONG's memory protocol on the shared substrate.

    Two properties carry the comparison. (1) The shared surfaces -- action reference,
    procedures, perception guidance, strategy knowledge -- must be IDENTICAL across the
    two memory modes: any drift there is a confound, not a finding. (2) The memory
    surfaces must be fully absent: a logbook arm whose workspace still grows a belief
    graph, an events channel or compiled documents is quietly running the other arm's
    design, and its score would be unreadable.
    """
    print("\n[logbook] PRO-LONG's memory protocol on the worldmodel chassis")
    from mcu_worldmodel import prompts
    from mcu_worldmodel.agent import WorldModelAgent

    # -- (1) the prompts: shared segments byte-equal, memory segments swapped --------
    kw = dict(task_text="get a log", progress_block="0/2", graph_summary="",
              plan_summary="", discipline_summary="", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE")
    wm_p = prompts.act_prompt(**kw)
    lb_p = prompts.act_prompt(**kw, memory_mode="logbook")
    for marker in ("hypothes", "world_model/", "events.jsonl", "claim.json",
                   "zoom", "frames/", "view_image", "any file you save"):
        check(f"logbook prompt has no {marker!r}", marker not in lb_p)
    for marker in ("hypotheses_ops.json", "world_model/", "events/events.jsonl",
                   "zoom.py"):
        check(f"worldmodel prompt keeps {marker!r}", marker in wm_p)
    for marker in ("stair_down", "cursor_to_slot", "append-only", "[EVENT]",
                   "HOST REFERENCE", "is removed when", "ONLY thing"):
        check(f"logbook prompt carries {marker!r}", marker in lb_p)
    if prompts.strategy_enabled():
        check("strategy knowledge is shared verbatim",
              prompts._STRATEGY_BULLETS in wm_p and prompts._STRATEGY_BULLETS in lb_p)
    seg = lambda s, a, b=None: s[s.index(a):(s.index(b) if b else len(s))]
    check("cursor mechanics identical across modes",
          seg(wm_p, "**The harness measures", "3. ")
          == seg(lb_p, "**The harness measures", "3. "))
    check("movement..platform tail identical across modes",
          seg(wm_p, "**Movement**") == seg(lb_p, "**Movement**"))

    # -- (2) the loop: no structured surfaces, belief ops ignored, induction off -----
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "lb", task_text="get a log",
                            ledger=MilestoneLedger(cfg, "t"),
                            induction_every=10, step_cap=50, memory_mode="logbook")
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "briefing lb\n[PLAN]\nwalk",
         "files": {"hypotheses_ops.json": {"hypotheses": [
             {"id": "h1", "statement": "x", "kind": "goal", "confidence": 0.3}]},
             "claim.json": {"completed": ["mine_log"]},
             # A notes file the model tried to keep: swept when the turn ends.
             "crafting_notes.md": {"table": "slot 4"}}},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 5}]},
          "message": "[PLAN]\nchop"} for _ in range(8)]
    agent.codex = FakeCodex(agent.memory.root, script)

    info = fake_info()
    agent.start(info)
    for step in range(1, 26):
        agent.next_action(info)
        info = fake_info(mine_block={"oak_log": 1}) if step == 8 else fake_info()
        info["location_stats"]["xpos"] = np.array(float(step))
        agent.observe(info, step)

    ws = agent.memory.root
    for absent in ("world_model", "hypotheses", "events", "maps", "entities",
                   "locations", "procedures", "notes", "tools", "episodes"):
        check(f"no {absent}/ in the logbook workspace", not (ws / absent).exists())
    check("the logbook workspace is the log, the system prompt and nothing else",
          {p.name for p in ws.iterdir()} <= {"AGENTS.md", "logs.txt", "actions.json",
                                              "last_message.txt"},
          str(sorted(p.name for p in ws.iterdir())))
    check("the model's own notes file was swept at the end of its turn",
          not (ws / "crafting_notes.md").exists() and agent.memory.swept >= 1,
          str(agent.memory.swept))
    check("the current view is attached from OUTSIDE the workspace",
          agent.memory.attach_dir.exists() and agent.memory.attach_dir.parent == ws.parent
          and not str(agent.memory.attach_dir).startswith(str(ws) + "/"))
    check("belief ops were ignored (graph empty, nothing persisted)",
          not agent.graph.nodes and not agent.memory.graph_path.exists())
    check("the false claim did not reach discipline",
          agent.discipline.counters.get("claim_rejected", 0) == 0)
    check("induction never fires in logbook mode",
          agent.induction_every == 0 and agent.turns["induction"] == 0)
    check("the milestone still verifies from the ledger",
          agent.ledger.is_verified("mine_log"))
    log = (ws / "logs.txt").read_text()
    check("events reach the log as [EVENT]/MILESTONE lines",
          "MILESTONE mine_log" in log and "[EVENT]" in log)
    check("the briefing reaches the log", "briefing lb" in log)
    check("no [FRAME] pointers in the logbook log (no archive to point at)",
          "[FRAME]" not in log)
    turn1 = agent.codex.prompts[0]
    check("turn prompt serves the present, points the past at grep",
          "[STATE]" in turn1 and "grep" in turn1
          and "compiled world model" not in turn1
          and "hypothesis graph" not in turn1)
    check("AGENTS.md was rendered in logbook mode",
          "append-only log" in (ws / "AGENTS.md").read_text()
          and "hypothes" not in (ws / "AGENTS.md").read_text()
          and "zoom" not in (ws / "AGENTS.md").read_text())
    rep = agent.report()
    check("the report names the arm", rep["memory_mode"] == "logbook", rep.get("memory_mode"))


def test_wmlite(root: Path) -> None:
    """The simplification arm: one compiled document on the logbook substrate.

    Three properties carry it. (1) Shared chassis segments stay byte-equal to both
    existing arms. (2) The full arm's structured surfaces (graph, ops files, events
    channel, five documents) are absent. (3) What remains of the treatment -- the
    induction pass and one world.md read every act turn -- actually runs."""
    print("\n[wmlite] one compiled document on the logbook substrate")
    from mcu_worldmodel import prompts
    from mcu_worldmodel.agent import WorldModelAgent

    kw = dict(task_text="get a log", progress_block="0/2", graph_summary="",
              plan_summary="", discipline_summary="", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE")
    wm_p = prompts.act_prompt(**kw)
    lb_p = prompts.act_prompt(**kw, memory_mode="logbook")
    lt_p = prompts.act_prompt(**kw, memory_mode="wmlite")
    for marker in ("hypothes", "events.jsonl", "claim.json", "spatial.md",
                   "procedural.md"):
        check(f"wmlite prompt has no {marker!r}", marker not in lt_p)
    check("wmlite prompt keeps world.md", "world_model/world.md" in lt_p)
    for marker in ("stair_down", "cursor_to_slot", "append-only",
                   "[EVENT]", "HOST REFERENCE", "stow_items", "collect_drops"):
        check(f"wmlite prompt carries shared {marker!r}", marker in lt_p)
    check("wmlite prompt has no zoom/frames (the logbook substrate keeps none)",
          "zoom" not in lt_p and "frames/" not in lt_p)
    seg = lambda s, a, b=None: s[s.index(a):(s.index(b) if b else len(s))]
    check("wmlite action tail identical to logbook's",
          seg(lt_p, "**Movement**") == seg(lb_p, "**Movement**"))
    check("wmlite cursor mechanics identical to worldmodel's",
          seg(lt_p, "**The harness measures", "3. ")
          == seg(wm_p, "**The harness measures", "3. "))
    check("wmlite ground-truth bullet is the logbook's, same object",
          prompts._GROUND_TRUTH_BULLET["wmlite"]
          is prompts._GROUND_TRUTH_BULLET["logbook"])

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "lt", task_text="get a log",
                         ledger=MilestoneLedger(cfg, "t"),
                         induction_every=10, step_cap=50, memory_mode="wmlite")
    check("wmlite keeps induction on", ag.induction_every == 10,
          str(ag.induction_every))
    check("wmlite is not structured", not ag.structured and ag.lite, "")
    wm_dir = ag.memory.root / "world_model"
    check("world.md seeded", (wm_dir / "world.md").exists(),
          str(sorted(p.name for p in wm_dir.glob('*'))))
    check("no five-document seeding", not (wm_dir / "spatial.md").exists(), "")
    for absent in ("events", "hypotheses", "maps", "procedures", "entities", "tools",
                   "episodes"):
        check(f"no {absent}/ directory", not (ag.memory.root / absent).exists(), "")
    (wm_dir / "world.md").write_text("# World model\n\nIron at (10, 40, -3).\n")
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "-"}] * 4)
    ag.start(fake_info())
    tp = ag._turn_prompt(fake_info())
    check("turn prompt reads world.md", "Iron at (10, 40, -3)" in tp, tp[-400:])
    check("turn prompt has no graph section", "hypothesis graph" not in tp, "")
    ip = prompts.wmlite_induction_prompt(task_text="t", progress_block="p",
                                         per_doc_chars=prompts.WMLITE_DOC_CHARS)
    check("wmlite induction rewrites ONE document",
          "world.md" in ip and "spatial.md" not in ip
          and "hypotheses_ops" not in ip, "")
    check("wmlite induction keeps the goal check", "## Goal check" in ip, "")


def test_direct(root: Path) -> None:
    """The no-memory baseline on the shared substrate. Three properties carry it. (1)
    The shared surfaces must stay identical to the memory arms', or the baseline delta
    is a prompt confound. (2) Every memory surface must be absent -- no log, no tools,
    no files, no resumed thread, no window, no feedback from the last batch, and no
    prompt text about memory at all: each turn is the present alone, served exactly as
    the memory arms see it. (3) The reply is the whole output channel: fenced JSON in,
    a reply without one retried with a nudge."""
    print("\n[direct] the no-memory baseline on the worldmodel chassis")
    from mcu_worldmodel import prompts
    from mcu_worldmodel.agent import WorldModelAgent, extract_actions_block
    from mcu_worldmodel.codex_backend import CodexTurn

    # -- (1)+(2a) the prompts ---------------------------------------------------------
    kw = dict(task_text="get a log", progress_block="0/2", graph_summary="",
              plan_summary="", discipline_summary="", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE")
    wm_p = prompts.act_prompt(**kw)
    dr_p = prompts.act_prompt(**kw, memory_mode="direct")
    for marker in ("logs.txt", "hypothes", "world_model/", "events.jsonl",
                   "claim.json", "zoom", "grep", "actions.json", "Bash",
                   "recent replies", "window", "memory", "persist", "remember",
                   "[NOTE]/[INV]", "Since your last plan"):
        check(f"direct prompt has no {marker!r}", marker not in dr_p)
    for marker in ("stair_down", "cursor_to_slot", "HOST REFERENCE", "fenced",
                   "Address slots and cells by number"):
        check(f"direct prompt carries {marker!r}", marker in dr_p)
    if prompts.strategy_enabled():
        check("strategy knowledge is shared verbatim",
              prompts._STRATEGY_BULLETS in dr_p)
    seg = lambda s, a, b=None: s[s.index(a):(s.index(b) if b else len(s))]
    check("cursor mechanics identical to the worldmodel arm's",
          seg(wm_p, "**The harness measures", "3. ")
          == seg(dr_p, "**The harness measures", "3. "))
    check("movement..strategy tail identical across modes",
          seg(wm_p, "**Movement**", "# The benchmark's own control reference")
          == seg(dr_p, "**Movement**", "# The benchmark's own control reference"))
    check("the platform wrapper names each arm's output channel",
          "ONE entry of your actions JSON" in dr_p
          and "ONE entry of your `actions.json`" in wm_p)
    # -- (2b)+(3) the loop ------------------------------------------------------------
    fence = lambda payload: "```json\n" + json.dumps(payload) + "\n```"
    # Two milestones, one forever unmet: with the full set verified the chassis would
    # (correctly) stop firing turns, and this scenario is about the turns.
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "mine_block", "identity": "mine_cobblestone",
            "objects": ["cobblestone"], "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "dr", task_text="get a log",
                            ledger=MilestoneLedger(cfg, "t"),
                            induction_every=10, step_cap=50, memory_mode="direct")
    check("direct forces 1-turn codex sessions",
          agent.codex.session_max_turns == 1, str(agent.codex.session_max_turns))
    check("direct codex runs read-only",
          agent.codex.sandbox_mode == "read-only", agent.codex.sandbox_mode)
    script = ([{"message": "brief A\n[PLAN]\nwalk\n"
                           + fence({"actions": [{"action": {"forward": 1}, "repeat": 5}]})},
               {"message": "no block in this reply"}]     # parse failure -> retried
              + [{"message": f"brief {i}\n[PLAN]\nchop\n"
                             + fence({"actions": [{"action": {"attack": 1}, "repeat": 5}]})}
                 for i in range(9)])
    agent.codex = FakeCodex(agent.memory.root, script)

    info = fake_info()
    agent.start(info)
    for step in range(1, 26):
        agent.next_action(info)
        info = fake_info(mine_block={"oak_log": 1}) if step == 8 else fake_info()
        info["location_stats"]["xpos"] = np.array(float(step))
        agent.observe(info, step)

    ws = agent.memory.root
    check("direct workspace is the system prompt and nothing else",
          sorted(p.name for p in ws.iterdir()) == ["AGENTS.md"],
          str(sorted(p.name for p in ws.iterdir())))
    check("induction never fires in direct mode",
          agent.induction_every == 0 and agent.turns["induction"] == 0)
    check("the milestone still verifies from the ledger",
          agent.ledger.is_verified("mine_log"))
    check("the direct turn message is the memory arms' present block, verbatim",
          "Act turns since anything" in agent.codex.prompts[0]
          and "[STATE]" in agent.codex.prompts[0] and "Milestones:" in agent.codex.prompts[0]
          and agent.codex.prompts[0].startswith("Step "))
    check("parse failure retries with the full prompt plus the nudge",
          agent.codex.prompts[2].startswith(agent.codex.prompts[1])
          and "fenced" in agent.codex.prompts[2][len(agent.codex.prompts[1]):]
          and agent.direct_stats["reply_parse_failures"] == 1)
    check("no turn message carries earlier turns, replies or batch feedback",
          not any("recent turns" in p or "[your reply]" in p or "brief A" in p
                  or "Since your last plan" in p or "[NOTE]" in p or "[INV]" in p
                  or "MILESTONE mine_log verified" in p
                  for p in agent.codex.prompts[1:]),
          agent.codex.prompts[3][:300])
    check("every turn message after the first differs only in the present",
          agent.codex.prompts[3].count("Step ") == agent.codex.prompts[0].count("Step "))
    rep = agent.report()
    check("the report names the arm, no window",
          rep["memory_mode"] == "direct" and "window" not in rep
          and rep["direct"]["reply_parse_failures"] == 1, str(rep.get("direct")))

    # -- (3b) the extraction contract, alone ------------------------------------------
    two = ("x\n" + fence({"actions": []}) + "\ny\n"
           + fence({"actions": [{"action": {"jump": 1}, "repeat": 1}]}))
    check("extraction takes the LAST valid fenced actions block",
          json.loads(extract_actions_block(two) or "{}").get("actions")
          == [{"action": {"jump": 1}, "repeat": 1}])
    check("prose and non-actions blocks are not plans",
          extract_actions_block("no fence here") is None
          and extract_actions_block("```json\n{\"x\": 1}\n```") is None)

    # -- the codex posture, alone ------------------------------------------------------
    cx_args = CodexTurn(root / "dr-cx", model="gpt-5.6-sol",
                        sandbox_mode="read-only")._args()
    check("direct codex turn asks for the read-only sandbox",
          'sandbox_mode="read-only"' in cx_args)
    cx_default = CodexTurn(root / "dr-cx2", model="gpt-5.6-sol")._args()
    check("the memory arms keep workspace-write",
          'sandbox_mode="workspace-write"' in cx_default)

    # -- the account's usage limit stops the calls instead of retrying for an episode --
    from mcu_worldmodel.codex_backend import (QUOTA_RETRY_AFTER, QUOTA_STREAK_STOP,
                                              _QUOTA_RE)
    check("the refusal codex reports for an exhausted account is recognised",
          bool(_QUOTA_RE.search(
              "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/"
              "usage to purchase more credits or try again at Sep 7th, 2026 10:25 AM.")))
    check("an ordinary turn error is not read as a usage limit",
          not _QUOTA_RE.search("stream disconnected before completion"))
    cx_q = CodexTurn(root / "dr-cx3", model="gpt-5.6-sol")
    check("a fresh backend blocks nothing", not cx_q._quota_blocked())
    cx_q.quota_streak = QUOTA_STREAK_STOP - 1
    check("a short streak still calls the model", not cx_q._quota_blocked())
    cx_q.quota_streak = QUOTA_STREAK_STOP
    blocked = [cx_q._quota_blocked() for _ in range(QUOTA_RETRY_AFTER * 2)]
    check(f"the streak stops the calls and probes every {QUOTA_RETRY_AFTER}th",
          all(blocked[: QUOTA_RETRY_AFTER - 1]) and blocked[QUOTA_RETRY_AFTER - 1] is False
          and blocked[-1] is False and sum(1 for b in blocked if not b) == 2,
          str(blocked.count(False)))


def test_stow_and_sweep(root: Path) -> None:
    """The GUI item-lifecycle package: stow_items, collect_drops, probe clicks,
    the plan-repetition streak, and the slots-free line."""
    print("\n[stow] stow_items / collect_drops / probe clicks / plan streak")
    from mcu_worldmodel.agent import WorldModelAgent, _empty_slot_count
    from mcu_worldmodel.cursor import CursorState
    from mcu_worldmodel.procedures import REGISTRY, act, click, expand

    # -- stow expansion: cursor deposit first, then lift+bank per cell
    def open_cur():
        c = CursorState()
        c.opened({"stick": 2})
        return c

    full_info = fake_info(inventory={"stick": 2})           # slot 0 held, 35 empty
    acts, note = expand("stow_items", info=full_info, cursor=open_cur(),
                        grid="3x3", cells=[0, 4])
    kinds = [next((k for k in a if k.startswith("_")), "env") for a in acts]
    check("stow(2 cells) = 5 servo+click pairs, silent",
          kinds == ["_servo", "_click"] * 5 and note == "", f"{kinds} {note!r}")
    check("stow clicks are probe clicks",
          all(a["_click"]["probe"] for a in acts if "_click" in a), str(acts[1]))
    check("stow servo targets: slot then cell then slot",
          "slot" in acts[0]["_servo"]["label"] and "cell" in acts[2]["_servo"]["label"]
          and "slot" in acts[4]["_servo"]["label"],
          str([a["_servo"]["label"] for a in acts if "_servo" in a]))

    acts, note = expand("stow_items", info=full_info, cursor=open_cur(),
                        grid="furnace")
    check("stow refuses the furnace, naming why",
          acts == [] and "KEEPS" in note, note)
    acts, note = expand("stow_items", info=full_info, cursor=open_cur(),
                        grid="3x3", cells=[9])
    check("stow rejects an out-of-range cell", acts == [] and "cells 0-8" in note, note)

    crammed = fake_info(inventory={f"item{i}": 1 for i in range(35)})   # 1 slot free
    acts, note = expand("stow_items", info=crammed, cursor=open_cur(),
                        grid="3x3", cells=[0, 4])
    check("stow with 1 free slot: cursor only, says what is left",
          len(acts) == 2 and "left 2" in note, f"{len(acts)} {note!r}")
    stuffed = fake_info(inventory={f"item{i}": 1 for i in range(36)})   # 0 free
    acts, note = expand("stow_items", info=stuffed, cursor=open_cur(),
                        grid="3x3", cells=[0])
    check("stow with 0 free slots refuses, names force",
          acts == [] and "force=true" in note, note)
    check("stow is in the prompt reference",
          "stow_items" in REGISTRY and "furnace keeps" in
          REGISTRY["stow_items"].preconditions.lower(),
          REGISTRY["stow_items"].preconditions)

    # -- probe clicks never arm the lifted-nothing judgment
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]

    def mk(tag: str) -> WorldModelAgent:
        ag = WorldModelAgent(workspace=root / f"sw_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"),
                             induction_every=0, step_cap=400)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "-"}
        ] * 8)
        ag.start(fake_info())
        return ag

    ag = mk("probe")
    ag.cursor.opened({})
    from mcu_worldmodel import gui as _gui
    ag.cursor.pos = _gui.centre(_gui.slot_topleft(12))      # over an empty slot
    ag.queue.extend([(c, 0) for c in click("attack", probe=True)])
    ag.next_action(fake_info())
    check("probe click over an empty slot arms no judgment",
          ag._pending_click is None, str(ag._pending_click))
    ag2 = mk("lift")
    ag2.cursor.opened({})
    ag2.cursor.pos = _gui.centre(_gui.slot_topleft(12))
    ag2.queue.extend([(c, 0) for c in click("attack")])
    ag2.next_action(fake_info())
    check("plain click over a slot still arms it",
          ag2._pending_click is not None, str(ag2._pending_click))

    # -- collect_drops: stops on pickup, reports an empty sweep
    ag3 = mk("sweep")
    acts, _ = expand("collect_drops", ticks=48)
    ag3.queue.extend([(acts[0], 0)])
    a = ag3.next_action(fake_info())
    check("sweep emits movement", any(a.get(k) for k in
          ("forward", "back", "left", "right")), str(a))
    ag3._cur_inv = {"spruce_log": 1}                        # the pickup lands
    ag3.next_action(fake_info(inventory={"spruce_log": 1}))
    notes = " | ".join(ag3.memory._pending_notes)
    check("sweep stops on the inventory rising, and says so",
          "inventory rose by 1" in notes, notes)
    check("sweep_collected counted", ag3.cursor_stats.get("sweep_collected") == 1,
          str(ag3.cursor_stats.get("sweep_collected")))
    ag4 = mk("dry")
    ag4.queue.extend([(expand("collect_drops", ticks=24)[0][0], 0)])
    for _ in range(30):
        ag4.next_action(fake_info())
        if not ag4.queue:
            break
    notes = " | ".join(ag4.memory._pending_notes)
    check("an empty sweep ends early with the picked-up-by-themselves fact",
          "picked up nothing" in notes and "by themselves" in notes, notes)
    ag4b = mk("dry_long")
    ag4b.queue.extend([(expand("collect_drops", ticks=120)[0][0], 0)])
    n4 = 0
    for _ in range(140):
        ag4b.next_action(fake_info())
        n4 += 1
        if not ag4b.queue:
            break
    check("a 120-tick sweep that finds nothing stops at the 24-tick cap",
          n4 <= 26 and ag4b.cursor_stats.get("sweep_empty") == 1, f"ticks={n4}")
    ag4c = mk("dry_shape")
    ag4c.queue.extend([(expand("collect_drops", ticks=120)[0][0], 0)])
    keys = []
    for _ in range(30):
        a = ag4c.next_action(fake_info())
        keys.append(next((k for k in ("forward", "back", "left", "right") if a.get(k)), None))
        if not ag4c.queue:
            break
    check("an empty sweep's 24 ticks go 12 forward (toward the drops) and 12 back "
          "to where they began, not 8 out and 16 past the start",
          keys[:24] == ["forward"] * 12 + ["back"] * 12, str(keys[:26]))

    # -- a deferred macro (parse-time refusal behind another entry) expands at run time
    from mcu_worldmodel.actions import parse_actions as _pa
    from mcu_worldmodel.cursor import CursorState as _CS2
    _c = _CS2(); _c.opened({})
    chained = _pa(json.dumps({"actions": [
        {"procedure": "collect_drops", "args": {}},
        {"procedure": "craft", "args": {"item": "planks"}}]}),
        info=fake_info(inventory={}), cursor=_c)        # no logs yet -> deferred
    later = [st for st in chained.steps if isinstance(st, dict) and "_later" in st]
    check("a craft short of ingredients behind a gatherer is deferred", len(later) == 1,
          [list(st)[0] for st in chained.steps if st])
    agl = mk("later")
    agl._gui_open, agl._screen = True, "inventory"
    agl._cur_info = fake_info(inventory={"oak_log": 3})
    agl.cursor.opened({"oak_log": 3})
    agl.queue.append((later[0], 3))
    agl.queue.append(({}, 4))
    agl.next_action(agl._cur_info)
    kinds_l = [next(k for k in st if k != "_cost") for st, _ in list(agl.queue)
               if isinstance(st, dict) and st]
    check("at run time the deferred craft expands in place, under its own entry index "
          "(the zero-cost screen gate is consumed in the same tick)",
          agl.cursor_stats.get("deferred_expanded") == 1 and "_click" in kinds_l
          and "_craftcheck" in kinds_l and all(i == 3 for _, i in list(agl.queue)[:-1]),
          f"{kinds_l[:6]} deferred={agl.cursor_stats.get('deferred_expanded')}")
    agr = mk("later_refused")
    agr._gui_open, agr._screen = False, None
    agr._cur_info = fake_info(inventory={"oak_log": 3})
    agr.queue.append((later[0], 5))
    agr.next_action(agr._cur_info)
    check("a deferred craft still impossible at its turn is refused with the live note",
          agr.cursor_stats.get("deferred_refused") == 1
          and any("no screen is open" in n for n in agr.memory._pending_notes),
          f"{agr.cursor_stats} {agr.memory._pending_notes[-1:]}")

    # -- a craft whose product never appears banks its cells back by itself
    from mcu_worldmodel import macros as _M
    agc = mk("craft_fail")
    agc._gui_open, agc._screen = True, "inventory"
    agc._cur_info = fake_info(inventory={"oak_planks": 6})
    agc.cursor.opened({"oak_planks": 6})
    agc.queue.append((_M.marker("_craftcheck", {"item": "stick", "product": "stick",
                                                "count": 1, "out": 4, "base": 0.0,
                                                "grid": "2x2", "cells": [0, 1], "t": 0}, 4), 2))
    agc.queue.append(({}, 3))
    for _ in range(6):
        agc.next_action(agc._cur_info)
        if agc.cursor_stats.get("craft_failed"):
            break
    kinds_c = [next(k for k in st if k != "_cost") for st, _ in list(agc.queue)
               if isinstance(st, dict) and st]
    # -- a placed block is remembered; use_until_gui(item=) aims at it before pressing
    from mcu_worldmodel import macros_gui as _MGp
    from mcu_worldmodel.procedures import use_until_gui as _uug
    est = (_MGp.placed_block({"x": 0.0, "y": 64.0, "z": 0.0, "yaw": 0.0, "pitch": 55.0}),
           _MGp.placed_block({"x": 0.0, "y": 64.0, "z": 0.0, "yaw": 90.0, "pitch": 55.0}),
           _MGp.placed_block(None))
    check("placed_block: 1.13 blocks ahead at feet level, in look_at's yaw convention",
          est == ((0, 64, 1), (-2, 64, 0), None), str(est))
    agp = mk("reopen")
    agp._placed["crafting_table"] = (2, 64, 0)               # two blocks to the right
    agp._cur_info = {"location_stats": {"xpos": 0.0, "ypos": 64.0, "zpos": 0.0,
                                        "pitch": 0.0, "yaw": 0.0}}
    agp.queue.append((_uug(3, item="crafting_table")[0], 1))
    seq = []
    for _ in range(40):
        a = agp.next_action(agp._cur_info)
        seq.append("cam" if a.get("camera") is not None and any(abs(v) > 0.01 for v in a["camera"])
                   else "use" if a.get("use") else "-")
        if not agp.queue:
            break
    check("use_until_gui(item=) turns toward the remembered block before the first press",
          "cam" in seq and "use" in seq and seq.index("cam") < seq.index("use")
          and agp.cursor_stats.get("use_gui_aimed") == 1, str(seq))
    agf = mk("reopen_far")
    agf._placed["crafting_table"] = (14, 64, 0)              # fourteen blocks away
    agf._cur_info = agp._cur_info
    agf._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    agf.queue.append((_uug(3, item="crafting_table")[0], 1))
    pressed = False
    for _ in range(40):
        a = agf.next_action(agf._cur_info)
        pressed = pressed or bool(a.get("use"))
        if not agf.queue:
            break
    check("use_until_gui(item=) with the remembered block out of reach says walk, and "
          "does not press",
          not pressed and agf.cursor_stats.get("use_gui_far") == 1
          and any("out of reach (max 4.4). go_to(14, 0, within=2)" in n
                  for n in agf.memory._pending_notes),
          f"pressed={pressed} far={agf.cursor_stats.get('use_gui_far')} "
          f"{agf.memory._pending_notes[-1:]}")
    agn = mk("reopen_none")
    agn._cur_info = agp._cur_info
    agn.queue.append((_uug(2, item="furnace")[0], 1))
    for _ in range(12):
        agn.next_action(agn._cur_info)
        if not agn.queue:
            break
    check("use_until_gui(item=) with nothing remembered says so and still presses",
          any("no remembered spot" in n for n in agn.memory._pending_notes), str(agn.memory._pending_notes[-1:]))
    check("a failed craft flushes the plan tail and splices a stow of its own cells",
          agc.cursor_stats.get("craft_failed") == 1 and agc.cursor_stats.get("craft_cleanup") == 1
          and "_servo" in kinds_c and "_click" in kinds_c
          and all(i == 2 for _, i in list(agc.queue))
          and any("banking the 2 cells" in n for n in agc.memory._pending_notes),
          f"{kinds_c[:8]} {agc.cursor_stats} {agc.memory._pending_notes[-1:]}")
    ag5 = mk("gui")
    ag5._gui_open = True
    ag5.queue.extend([(expand("collect_drops")[0][0], 0)])
    ag5.next_action(fake_info())
    check("sweep stops at once under an open screen",
          ag5.cursor_stats.get("sweep_gui_stops") == 1
          and "SCREEN is open" in " | ".join(ag5.memory._pending_notes),
          str(ag5.cursor_stats))

    # -- the plan-repetition streak and its notice
    ag6 = mk("streak")
    ag6._update_plan_streak("Collect the nearby log drops, testing the drop "
                            "column. Once inventory confirms wood, craft planks "
                            "and the crafting table.")
    ag6._update_plan_streak("Collect the nearby log drops, testing the drop "
                            "column. Once inventory confirms wood, craft planks "
                            "and the crafting table.")
    ag6._update_plan_streak("Collect the nearby log drops, sweeping the drop "
                            "column. Once inventory confirms wood, craft planks "
                            "and the crafting table.")
    check("three near-identical plans -> streak 2", ag6._plan_repeat == 2,
          str(ag6._plan_repeat))
    ag6._stall_turns = 3
    check("stalled streak renders the notice",
          "near-identical" in ag6._notices(), ag6._notices())
    ag6._update_plan_streak("Dig a staircase down to stone and mine cobblestone")
    check("a new plan resets the streak", ag6._plan_repeat == 0,
          str(ag6._plan_repeat))
    ag6._stall_turns = 3
    check("no streak, no notice", "near-identical" not in ag6._notices(),
          ag6._notices())

    # -- the post-completion hold: every milestone verified -> no more model turns
    agH = mk("hold")
    base = agH.codex.calls
    for rule in agH.ledger.cfg:
        agH.ledger.achieved.setdefault(rule["identity"], 0)
    agH.next_action(fake_info())
    check("all-verified -> the chassis coasts on a no-op",
          agH.cursor_stats.get("completion_hold", 0) == 1,
          str(agH.cursor_stats.get("completion_hold")))
    check("...without spending a model turn", agH.codex.calls == base,
          f"calls {base} -> {agH.codex.calls}")

    # -- the close refusal now teaches stow_items and the furnace fact
    ag7 = mk("close")
    ag7.cursor.opened({"stick": 2})
    ag7.cursor.off_inventory({})                            # 2 sticks off-inventory
    ag7._cur_inv = {}
    refused = ag7._guard_close({"inventory": 1}, lambda: {})
    notes = " | ".join(ag7.memory._pending_notes)
    check("close refusal names stow_items and the furnace",
          refused == {} and "stow_items" in notes and "FURNACE keeps" in notes,
          notes)

    # -- screen kind: the furnace's contents are not "on the floor"
    from mcu_worldmodel import gui as _gui, vision as _vis

    def screen_frame(kind: str, bevel: bool = True) -> np.ndarray:
        fr = np.full((360, 640, 3), 60, dtype=np.uint8)
        ox, oy = (int(v) for v in _gui.container_origin())
        fr[oy:oy + _gui.CONTAINER_H, ox:ox + _gui.CONTAINER_W] = 198
        if bevel:
            fr[oy + 2, ox + 2] = 254
            fr[oy + 163, ox + 173] = 85
        cell = {"inventory": 20, "table": 139, "furnace": 198}[kind]
        for cx0, cy0, cx1, cy1 in _vis._SCREEN_CELLS:
            fr[oy + cy0:oy + cy1, ox + cx0:ox + cx1] = cell
        return fr

    kinds = [_vis.screen_kind(screen_frame(k)) for k in ("inventory", "table", "furnace")]
    check("vision: the three container screens are told apart by their cell-0/6 patch",
          kinds == ["inventory", "table", "furnace"], str(kinds))
    check("vision: no container bevel -> no screen (a flat world frame is not a GUI)",
          _vis.screen_kind(screen_frame("furnace", bevel=False)) is None
          and _vis.screen_kind(np.full((360, 640, 3), 197, dtype=np.uint8)) is None)
    ag8 = mk("furnace_close")
    ag8.cursor.opened({"iron_ore": 2})
    ag8.cursor.off_inventory({})
    ag8._cur_inv = {}
    ag8._screen = "furnace"
    allowed = ag8._guard_close({"inventory": 1}, lambda: {})
    ag8._screen = "table"
    refused2 = ag8._guard_close({"inventory": 1}, lambda: {})
    check("close guard: a furnace screen closes freely, a table screen is still refused",
          allowed == {"inventory": 1} and refused2 == {}
          and ag8.cursor_stats.get("furnace_close_ok") == 1,
          f"allowed={allowed} refused={refused2} {ag8.cursor_stats.get('furnace_close_ok')}")
    ag9 = mk("furnace_fall")
    ag9._last_pov = screen_frame("furnace")
    ag9._sync_cursor({"isGuiOpen": True})
    ag9._cur_inv = {}
    ag9.cursor.opened({"iron_ore": 2})
    ag9._gui_open = True
    ag9._sync_cursor({"isGuiOpen": False})
    notes9 = " | ".join(ag9.memory._pending_notes)
    check("falling edge on a furnace screen: the note says the furnace keeps the ore, "
          "no floor recheck is armed",
          "in the furnace" in notes9 and "not in any inventory slot" not in notes9
          and ag9._close_recheck is None and ag9._screen is None, notes9[:160])

    # -- a craft output writes its ingredients off the baseline
    ag10 = mk("crafted")
    ag10.cursor.opened({"spruce_log": 4, "stick": 2})
    ag10._cur_inv = {"spruce_log": 3}                       # one log lifted into the grid
    before = ag10.cursor.off_inventory(ag10._cur_inv)
    gone = ag10.cursor.crafted("planks", 4)
    ag10._cur_inv = {"spruce_log": 3, "spruce_planks": 4}   # the output was taken
    after = ag10.cursor.off_inventory(ag10._cur_inv)
    check("cursor: crafting planks writes the log off the baseline (no stale off-inventory)",
          before == {"spruce_log": 1, "stick": 2} and gone == {"spruce_log": 1}
          and after.get("spruce_log", 0) == 0 and after.get("stick", 0) == 2,
          f"before={before} gone={gone} after={after}")
    allowed10 = ag10._guard_close({"inventory": 1}, lambda: {})
    check("cursor: ...but the sticks still off-inventory keep the close refused",
          allowed10 == {}, str(allowed10))

    # -- the slots-free count
    check("_empty_slot_count: 33 free with 3 held",
          _empty_slot_count(fake_info(inventory={"a": 1, "b": 1, "c": 1})) == 33,
          str(_empty_slot_count(fake_info(inventory={"a": 1, "b": 1, "c": 1}))))
    check("Inventory line carries the count",
          "slots free)" in mk("prompt")._turn_prompt(fake_info()), "")


def test_task_knowledge() -> None:
    """Milestone knowledge after the wire leak removal: loaded from the public task
    configs, verified from stat deltas, synthesized back into the wire shapes the
    prolong log renders. Every arm reads the same rules from the same files."""
    print("\n[task-knowledge] agent-side milestone config + synthesis")
    import task_milestones as tk
    from prolong_mc.log import milestone_checklist

    dia = tk.load_milestone_cfg("mine_diamond_from_scratch")
    drg = tk.load_milestone_cfg("ender_dragon")
    check("diamond config has the 10 rules", len(dia) == 10, str(len(dia)))
    check("dragon config loads a full progression", len(drg) >= 20, str(len(drg)))
    check("unknown task -> empty config", tk.load_milestone_cfg("no_such_task") == [])
    check("rules keep full object lists (no [:4] wire truncation)",
          any(len(r.get("objects") or []) > 4 for r in drg))

    led = MilestoneLedger(dia, "diamond")
    led.reset(fake_info())
    fired = led.update(fake_info(mine_block={"oak_log": 1}), step=7)
    check("stat-delta path verifies without wire bits",
          [f["identity"] for f in fired] == ["mine_log"] and led.is_verified("mine_log"))

    syn = tk.synthesize_milestone_info(dia, led.achieved)
    check("synthesized bits flip only the achieved milestone",
          syn["milestones"]["mine_log"] == 1
          and sum(syn["milestones"].values()) == 1)
    spec = syn["milestone_spec"]
    check("synthesized spec carries done bits in the wire shape",
          spec[0]["identity"] == "mine_log" and spec[0]["done"] == 1
          and spec[1]["done"] == 0 and spec[1]["objects"])
    check("the prolong checklist renders from the synthesized spec",
          "mine_log" in milestone_checklist(spec))

    check("absent mobs channel reads as unreported, not as empty",
          nearby_mobs({}) == "not reported -- read the frame"
          and nearby_mobs({"mobs": []}) == "none reported")


def test_systemics(root: Path) -> None:
    """P12: durability surfacing, step budget, absolute look, attack-hold refund."""
    print("systemics:")
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import held_line
    from mcu_worldmodel.procedures import (act, look_abs, mine_forward, stair_down,
                                           strip_mine)

    # -- held_line reads equipped_items durability off the wire shape
    i = fake_info()
    i["equipped_items"] = {"mainhand": {"type": "wooden_pickaxe",
                                        "damage": np.array(12),
                                        "maxDamage": np.array(59)}}
    check("held: uses left", held_line(i) == "wooden_pickaxe (47/59 uses left)",
          held_line(i))
    i["equipped_items"]["mainhand"]["damage"] = np.array(50)
    check("held: near-broken warning", "NEARLY BROKEN" in held_line(i), held_line(i))
    check("held: empty hand",
          held_line({"equipped_items": {"mainhand": {"type": "air"}}}) == "empty hand",
          held_line({"equipped_items": {"mainhand": {"type": "air"}}}))
    check("held: missing key", held_line({}) == "unknown", held_line({}))

    # -- the turn prompt carries the budget header and the held line
    led = MilestoneLedger([{"identity": "mine_log", "event": "mine_block",
                            "objects": ["log"], "max_reward_times": 1}], task_name="t")
    ag = WorldModelAgent(workspace=root / "sy", task_text="t", ledger=led,
                         induction_every=0, step_cap=50, max_steps=6000)
    ag.step = 5200
    p = ag._turn_prompt(i)
    check("prompt: budget header", "Step 5200/6000 -- 800 steps remain" in p,
          p.splitlines()[0])
    check("prompt: held line", "Held: wooden_pickaxe" in p, "")

    # -- look_abs converges from pitch 90 to 38, closed loop against fake truth
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 90.0, "yaw": 0.0}
    la = look_abs(pitch=38.0, ticks=20)[0]["_lookabs"]
    ticks = 0
    while ticks < 25:
        a = ag._lookabs_tick(la, act)
        if a is None:
            break
        ticks += 1
        ag._cur_pos["pitch"] += a["camera"][0]
    check("look_abs converged", abs(ag._cur_pos["pitch"] - 38.0) <= 2.0,
          f"pitch={ag._cur_pos['pitch']:.1f} after {ticks} ticks")
    check("look_abs tick count sane", ticks <= 4, str(ticks))

    # -- stair_down is now one displacement-verified cycle entry
    sd = stair_down(3)
    check("stair_down is a displacement cycle",
          "_mfwd" in sd[0] and sd[0]["_mfwd"]["down_by"] == 3.0
          and sd[0]["_mfwd"]["jump"] is False, str(sd[0])[:90])

    # -- mine_forward: the displacement cycle closes on the face, breaks foot+eye and
    # walks in. Fake world: camera moves pitch instantly, a block breaks after 3 attack
    # ticks, forward gains 0.35 blocks per tick up to the face (a wall 1 block ahead
    # that recedes by one cell after each foot+eye pair).
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    ag._log_breaks = 0.0
    ag._other_breaks = 0.0
    mf = mine_forward(60)[0]["_mfwd"]
    swing = 0
    ticks = 0
    wall = 1.0
    first_phases = []
    while ticks < 70:
        a = ag._mfwd_tick(mf, act)
        if a is None:
            break
        ticks += 1
        if len(first_phases) < 6:
            first_phases.append((mf["phase"], bool(a.get("forward")), bool(a.get("attack"))))
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        if a.get("attack"):
            swing += 1
            if swing >= 3:
                ag._log_breaks += 1.0
                swing = 0
                if ag._log_breaks % 2 == 0:
                    wall += 1.0
        if a.get("forward"):
            ag._cur_pos["x"] = min(ag._cur_pos["x"] + 0.35, wall - 0.3)
    log_mf = "\n".join(ag.memory._pending_notes)
    check("mine_forward cycle advances (not digging in place)",
          mf["advanced"] >= 1.8 and mf["broken"] >= 4,
          f"advanced={mf['advanced']:.2f} broken={mf['broken']} ticks={ticks}")
    check("the cycle walks up to the face before the foot carve (close first, no swing)",
          first_phases[0][0] == "close" and first_phases[0][1] and not first_phases[0][2]
          and any(p == "foot" for p, _, _ in first_phases),
          f"{first_phases} x={ag._cur_pos['x']:.2f} wall={wall}")
    check("mine_forward reports broke/advanced in a [NOTE]",
          "mine_forward: broke" in log_mf and "advanced" in log_mf, log_mf[-200:])

    # -- a stair whose cycles advance without descending steepens its carve
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    from mcu_worldmodel.procedures import stair_down
    st = stair_down(20)[0]["_mfwd"]
    atk = 0
    for _ in range(90):
        a = ag._mfwd_tick(st, act)
        if a is None:
            break
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        if a.get("attack"):
            atk += 1
            if atk % 2 == 0:
                ag._other_breaks += 1          # soft ground: fast breaks
        if a.get("forward"):
            ag._cur_pos["x"] += 0.35           # walks in... but y never drops
        if st.get("p_lo_bump", 0.0) >= 10.0:
            break
    check("no-descent cycles steepen the foot carve (+5 each)",
          st.get("p_lo_bump", 0.0) >= 10.0
          and ag.cursor_stats.get("stair_steepened", 0) >= 2,
          f"bump={st.get('p_lo_bump')} stat={ag.cursor_stats.get('stair_steepened')}")
    y_bump = st["p_lo"] + st["p_lo_bump"]
    for _ in range(30):                        # now the steeper carve works: y drops
        a = ag._mfwd_tick(st, act)
        if a is None:
            break
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        if a.get("attack"):
            atk += 1
            if atk % 2 == 0:
                ag._other_breaks += 1
        if a.get("forward"):
            ag._cur_pos["x"] += 0.35
            ag._cur_pos["y"] -= 0.34
    check("a descending cycle keeps the bump that worked",
          st.get("p_lo_bump", 0.0) >= 10.0, f"bump={st.get('p_lo_bump')}")
    check("foot target had steepened before the reset", y_bump >= 58.0,
          f"target={y_bump}")

    # -- slow-cycle stair (real-world timing): a failing carve cycle runs ~97
    # ticks, so the 96-tick no-depth checkpoint fires first. It must steepen
    # and continue the entry, not kill it: dm9/kd9 ended with min_y>=50 and
    # stair_steepened=0 on all six arms because the abort preempted the ladder.
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    ag.cursor_stats.pop("stair_steepened", None)
    ag.memory._pending_notes.clear()
    st2 = stair_down(12)[0]["_mfwd"]
    survived_97 = False
    for t in range(1, 130):
        a = ag._mfwd_tick(st2, act)
        if a is None:
            break
        if t >= 97:
            survived_97 = True
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        # no breaks, no forward motion, y never drops: nothing completes a
        # cycle, so only the checkpoint path can steepen
    ck_notes = "\n".join(ag.memory._pending_notes)
    check("no-depth checkpoint steepens and continues (not a kill)",
          survived_97 and st2.get("p_lo_bump", 0.0) == 5.0
          and ag.cursor_stats.get("stair_steepened", 0) == 1,
          f"survived={survived_97} bump={st2.get('p_lo_bump')} "
          f"stat={ag.cursor_stats.get('stair_steepened')}")
    check("checkpoint steepen note names the new angle",
          "steepening the cut to 53 deg and continuing" in ck_notes,
          ck_notes[-200:])

    # -- same world with the bump already maxed: now the checkpoint may abort,
    # and the diagnosis says the steepest cut was already tried
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    ag.memory._pending_notes.clear()
    st3 = stair_down(12)[0]["_mfwd"]
    st3["p_lo_bump"] = 14.0
    ended_at = None
    for t in range(1, 130):
        a = ag._mfwd_tick(st3, act)
        if a is None:
            ended_at = t
            break
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
    ck3 = "\n".join(ag.memory._pending_notes)
    check("maxed-bump checkpoint stops the entry at ~97 ticks",
          ended_at is not None and ended_at <= 100, f"ended_at={ended_at}")
    check("terminal note says the steepest cut was tried",
          "even at the steepest cut (62 deg)" in ck3
          and "different footing" in ck3, ck3[-220:])

    # -- an unbreakable face stops the entry early with a diagnosis, not at budget
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    mfb = strip_mine(400)[0]["_mfwd"]
    ticks_b = 0
    while ticks_b < 500:
        a = ag._mfwd_tick(mfb, act)
        if a is None:
            break
        ticks_b += 1
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
    log_mfb = "\n".join(ag.memory._pending_notes)
    check("a zero-break stall stops early and says the swings hit nothing",
          ticks_b < 250 and ag.cursor_stats.get("mine_stall_stops") == 1
          and "hitting nothing breakable" in log_mfb,
          f"ticks={ticks_b} stats={ag.cursor_stats.get('mine_stall_stops')}")

    # -- breaks-but-no-advance is the other stall flavour, and it flushes the queued
    # rest of the plan (dm4_wmv22 ran three identical doomed stair_downs back to back)
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    mfc_entry = strip_mine(400)[0]
    ag.queue.clear()
    ag.queue.append((mfc_entry, 41))
    for _ in range(6):
        ag.queue.append((act(attack=1), 42))
    mfc = mfc_entry["_mfwd"]
    swing = 0
    ticks_c2 = 0
    while ticks_c2 < 500:
        a = ag._mfwd_tick(mfc, act)
        if a is None:
            break
        ticks_c2 += 1
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        if a.get("attack"):
            swing += 1
            if swing >= 3:
                ag._log_breaks += 1.0
                swing = 0
    log_mfc = "\n".join(ag.memory._pending_notes)
    check("a breaks-but-stuck stall names the unopened passage and flushes the plan",
          "passage is not opening" in log_mfc
          and ag.cursor_stats.get("stall_flush_dropped") == 1
          and len(ag.queue) == 1,
          f"queue={len(ag.queue)} dropped={ag.cursor_stats.get('stall_flush_dropped')}")
    ag.queue.clear()

    # -- a mining entry under an open screen stops on its first tick with the reason
    ag._gui_open = True
    mfg = mine_forward(60)[0]["_mfwd"]
    check("mining under an open screen stops at once",
          ag._mfwd_tick(mfg, act) is None
          and ag.cursor_stats.get("mine_gui_stops") == 1
          and "SCREEN is open" in "\n".join(ag.memory._pending_notes),
          str(ag.cursor_stats.get("mine_gui_stops")))
    ag._gui_open = False

    # -- mine_ahead reports what its swings produced when the sequence completes
    from mcu_worldmodel.procedures import mine_ahead
    sqa = mine_ahead(4)[0]["_seq"]
    for _ in range(3):
        ag._seq_tick(sqa, act)
    ag._log_breaks += 1.0
    while ag._seq_tick(sqa, act) is not None:
        pass
    check("mine_ahead reports its break count at the end",
          "mine_ahead: finished 4 ticks, broke 1 block" in
          "\n".join(ag.memory._pending_notes),
          "\n".join(ag.memory._pending_notes)[-160:])

    # -- stair_down's cycle stops at the target depth and reports the descent
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 0.0, "yaw": 0.0}
    ag._log_breaks = 0.0
    sdm = stair_down(3)[0]["_mfwd"]
    swing = 0
    ticks_c = 0
    while ticks_c < 200:
        a = ag._mfwd_tick(sdm, act)
        if a is None:
            break
        ticks_c += 1
        if a.get("camera"):
            ag._cur_pos["pitch"] += a["camera"][0]
        if a.get("attack"):
            swing += 1
            if swing >= 3:
                ag._log_breaks += 1.0
                swing = 0
        if a.get("forward"):
            ag._cur_pos["x"] += 0.35
            ag._cur_pos["y"] -= 0.4
    log_sd = "\n".join(ag.memory._pending_notes)
    check("stair_down cycle stops at depth",
          ag.cursor_stats.get("mine_reached_depth") == 1 and "descended" in log_sd,
          f"y={ag._cur_pos['y']:.1f} ticks={ticks_c}")

    # -- a within-inventory cursor drop is invisible at close time (the item never
    # leaves the inventory count while riding the cursor -- how ked3 lost its stone
    # pickaxe, silently) and must be caught by the one-tick recheck.
    led_d = MilestoneLedger([{"identity": "mine_log", "event": "mine_block",
                              "objects": ["log"], "max_reward_times": 1}], task_name="t")
    agd = WorldModelAgent(workspace=root / "drop", task_text="t", ledger=led_d,
                          induction_every=0, step_cap=400)
    i_open = fake_info(inventory={"stone_pickaxe": 1})
    i_open["isGuiOpen"] = True
    agd.observe(i_open, 1)
    agd.observe(fake_info(inventory={"stone_pickaxe": 1}), 2)   # close: diff is zero
    agd.observe(fake_info(), 3)                                  # the drop lands now
    log_d = "\n".join(agd.memory._pending_notes)
    check("silent cursor drop caught one tick after the close",
          "never made it back" in log_d and "stone_pickaxe" in log_d, log_d[-300:])
    i_open2 = fake_info(inventory={"spruce_log": 1})
    i_open2["isGuiOpen"] = True
    agd.observe(i_open2, 4)
    agd.observe(fake_info(inventory={"spruce_log": 1}), 5)
    agd.observe(fake_info(inventory={"spruce_planks": 4}), 6)    # crafted, not dropped
    log_d2 = "\n".join(agd.memory._pending_notes)
    check("a craft conversion does not false-alarm the drop recheck",
          log_d2.count("never made it back") == 1,
          f"count={log_d2.count('never made it back')}")

    # -- a raw attack-hold is refunded when the stat stream reports a break
    led2 = MilestoneLedger([{"identity": "mine_log", "event": "mine_block",
                             "objects": ["log"], "max_reward_times": 1}], task_name="t")
    ag2 = WorldModelAgent(workspace=root / "sy2", task_text="t", ledger=led2,
                          induction_every=0, step_cap=400)
    ag2.queue.extend([(act(attack=1), 3)] * 60)
    ag2.queue.append((act(forward=1), 4))
    a = ag2.next_action(fake_info())
    check("hold: first tick attacks", a.get("attack") == 1, str(a))
    check("hold: queue drains one", len(ag2.queue) == 60, str(len(ag2.queue)))
    ag2._other_breaks += 1.0            # the block broke, per the stat stream
    a = ag2.next_action(fake_info())
    check("hold: refunded to next entry", a.get("forward") == 1, str(a))
    check("hold: queue emptied", len(ag2.queue) == 0, str(len(ag2.queue)))
    check("hold: stat counted", ag2.cursor_stats.get("attack_holds_cut") == 1,
          str(ag2.cursor_stats.get("attack_holds_cut")))
    check("hold: note pending for the next log section",
          any("attack-hold entry cut short" in n for n in ag2.memory._pending_notes),
          str(ag2.memory._pending_notes))

    # -- aim_at_ore: vision-servo converges onto a synthetic speckle cluster
    from mcu_worldmodel.procedures import aim_at_ore
    from mcu_worldmodel import vision as _V

    def ore_frame(cx: int, cy: int) -> np.ndarray:
        fr = np.full((360, 640, 3), 110, dtype=np.uint8)   # plain stone grey
        fr[..., 2] = 108
        # several small speckle blobs (the detector requires intra-block texture,
        # not one solid mass -- a solid mass is a dirt clump)
        for dx, dy in ((0, 0), (5, 2), (10, -1), (2, 7), (8, 6), (-4, 4), (-2, -5)):
            x, y = cx + dx, cy + dy
            fr[max(0, y - 1):y + 1, max(0, x - 1):x + 1] = (190, 158, 129)
        return fr

    hit = _V.find_iron_ore(ore_frame(420, 130))
    check("aim: synthetic cluster detected", hit is not None
          and abs(hit[0] - 420) < 8 and abs(hit[1] - 130) < 8, str(hit))

    def dia_frame(cx: int, cy: int, col=(87, 191, 182), solid: bool = False) -> np.ndarray:
        fr = np.full((360, 640, 3), 110, dtype=np.uint8)
        fr[..., 2] = 108
        if solid:
            fr[cy - 16:cy + 16, cx - 16:cx + 16] = col
            return fr
        for dx, dy in ((0, 0), (5, 2), (10, -1), (2, 7), (8, 6), (-4, 4), (-2, -5)):
            x, y = cx + dx, cy + dy
            fr[max(0, y - 1):y + 1, max(0, x - 1):x + 1] = col
        return fr

    dh = _V.find_diamond_ore(dia_frame(420, 130))
    check("diamond: cyan speckles on grey are found by the diamond band and by no other "
          "(the tan cluster is not diamond, the cyan one is not iron)",
          dh is not None and abs(dh[0] - 420) < 8 and abs(dh[1] - 130) < 8
          and _V.find_iron_ore(dia_frame(420, 130)) is None
          and _V.find_diamond_ore(ore_frame(420, 130)) is None, str(dh))
    check("diamond: a solid cyan mass (diamond block, wool) is not speckle",
          _V.find_diamond_ore(dia_frame(420, 130, solid=True)) is None, "fired")
    check("diamond: lapis-blue and water-blue dots fail the blue-green cap",
          _V.find_diamond_ore(dia_frame(420, 130, col=(16, 53, 125))) is None
          and _V.find_diamond_ore(dia_frame(420, 130, col=(41, 68, 124))) is None, "fired")
    fo_d, fo_i = _V.find_ore(dia_frame(420, 130)), _V.find_ore(ore_frame(420, 130))
    check("find_ore names the kind", fo_d is not None and fo_d[0] == "diamond"
          and fo_i is not None and fo_i[0] == "iron", f"{fo_d} {fo_i}")

    ax, ay = 430.0, 120.0          # cluster starts right-and-above centre
    ag._last_pov = ore_frame(int(ax), int(ay))
    ao = aim_at_ore(30)[0]["_aimore"]
    ticks = 0
    while ticks < 30:
        a = ag._aimore_tick(ao, act)
        if a is None:
            break
        ticks += 1
        dp, dy = a["camera"]
        check("aim: turns toward cluster", (dy > 0) == (ax > 320) and
              (dp > 0) == (ay > 180) or (abs(ax - 320) < 12 or abs(ay - 180) < 12),
              f"cam=({dp:.1f},{dy:.1f}) at ({ax:.0f},{ay:.0f})")
        ax -= dy / 0.14            # the world turns under the camera
        ay -= dp / 0.19
        ag._last_pov = ore_frame(int(round(ax)), int(round(ay)))
    check("aim: centred", abs(ax - 320) <= 12 and abs(ay - 180) <= 12,
          f"({ax:.0f},{ay:.0f}) after {ticks} ticks")
    check("aim: done note queued",
          any("crosshair centred" in n for n in ag.memory._pending_notes),
          str(ag.memory._pending_notes[-2:]))

    # -- and stops fast when the cluster is gone
    ag._last_pov = np.full((360, 640, 3), 110, dtype=np.uint8)
    ao2 = aim_at_ore(30)[0]["_aimore"]
    ticks = 0
    while ticks < 30 and ag._aimore_tick(ao2, act) is not None:
        ticks += 1
    check("aim: miss-stops fast", ticks == 5, str(ticks))   # 6th call returns None

    # -- aim_at_tree: the wood-phase servo converges onto a synthetic trunk
    from mcu_worldmodel.procedures import aim_at_tree

    def tree_frame(tx: int) -> np.ndarray:
        fr = np.empty((360, 640, 3), dtype=np.uint8)
        fr[:] = (120, 170, 235)                   # sky
        fr[260:] = (70, 120, 60)                  # grass (green context)
        x0 = max(0, tx - 20)
        fr[40:256, x0:tx + 20] = (109, 85, 50)    # oak-bark column, 40px wide
        return fr

    t_hit = _V.find_tree_trunk(tree_frame(200))
    check("tree: synthetic trunk detected", t_hit is not None
          and abs(t_hit[0] - 200) < 8 and 150 <= t_hit[1] <= 210, str(t_hit))
    tx = 200.0                                   # trunk starts left of centre
    ag._last_pov = tree_frame(int(tx))
    at = aim_at_tree(30)[0]["_aimtree"]
    ticks = 0
    while ticks < 30:
        a = ag._aimtree_tick(at, act)
        if a is None:
            break
        ticks += 1
        dp, dyw = a["camera"]
        tx -= dyw / 0.14                         # the world turns under the camera
        ag._last_pov = tree_frame(int(round(tx)))
    check("tree: centred on the trunk", abs(tx - 320) <= 14,
          f"tx={tx:.0f} after {ticks} ticks")
    check("tree: done note queued",
          any("centred on the trunk" in n for n in ag.memory._pending_notes),
          str(ag.memory._pending_notes[-2:]))
    ag._last_pov = np.full((360, 640, 3), (120, 170, 235), dtype=np.uint8)
    at2 = aim_at_tree(30)[0]["_aimtree"]
    ticks = 0
    while ticks < 30 and ag._aimtree_tick(at2, act) is not None:
        ticks += 1
    check("tree: miss-stops fast", ticks == 5, str(ticks))

    # -- the strategy-knowledge gate: advice out, constants and mechanics stay
    import os as _os
    from mcu_worldmodel import prompts as _pr
    _prev = _os.environ.get("MCU_WM_STRATEGY")
    try:
        _os.environ["MCU_WM_STRATEGY"] = "0"
        p_off = _pr.act_prompt(task_text="t", progress_block="pb", graph_summary="",
                               plan_summary="", discipline_summary="",
                               entry_cap=20, step_cap=400)
        check("ablation: strategy stripped",
              "Plan your stone trip" not in p_off and "VERTICAL shaft" not in p_off
              and "Bank the endgame" not in p_off, "")
        check("ablation: constants kept",
              "mine_cobblestone" in p_off and "Tools wear out" in p_off
              and "Smelting" in p_off, "")
        check("ablation: progress_line neutral",
              "bank whichever" not in led.progress_line(), led.progress_line())
        _os.environ["MCU_WM_STRATEGY"] = "1"
        p_on = _pr.act_prompt(task_text="t", progress_block="pb", graph_summary="",
                              plan_summary="", discipline_summary="",
                              entry_cap=20, step_cap=400)
        check("ablation: default ships strategy",
              "Plan your stone trip" in p_on and "opens under your feet" in p_on
              and "bank whichever" in led.progress_line(), "")
    finally:
        if _prev is None:
            _os.environ.pop("MCU_WM_STRATEGY", None)
        else:
            _os.environ["MCU_WM_STRATEGY"] = _prev

    # -- short bursts (strip_mine shape) are NOT cut
    ag2.queue.extend([(act(attack=1), 9)] * 6)
    ag2.queue.append((act(forward=1), 10))
    ag2.next_action(fake_info())
    ag2._other_breaks += 1.0
    ag2.next_action(fake_info())
    check("hold: short burst untouched",
          ag2.cursor_stats.get("attack_holds_cut") == 1, str(ag2.cursor_stats))





def test_entities(root: Path) -> None:
    """Entity vision (motion + colour), the entity macros' plan-time compilation, and
    the fight loop run to a kill against a scripted world."""
    print("\n[entities] find_moving_blob / entity_hint / face_entity / fight / boats")
    from mcu_worldmodel import macros
    from mcu_worldmodel import macros_entity as ME
    from mcu_worldmodel import vision
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    def scene(fill=120):
        return np.full((360, 640, 3), fill, dtype=np.uint8)

    # -- motion ------------------------------------------------------------------
    a = scene()
    b = a.copy()
    b[120:200, 280:330] = 30                       # something moved into view
    hit = vision.find_moving_blob(a, b)
    check("find_moving_blob: the changed rectangle, centred on its middle",
          hit is not None and abs(hit[0] - 304) <= 3 and abs(hit[1] - 159) <= 3
          and hit[3] >= 40 and hit[4] >= 70, hit)
    check("find_moving_blob: identical frames -> nothing", vision.find_moving_blob(a, a) is None)
    hud = a.copy()
    hud[300:355, 200:440] = 250                    # the hotbar repainting
    check("find_moving_blob: a HUD-only change is ignored",
          vision.find_moving_blob(a, hud) is None, vision.find_moving_blob(a, hud))
    hand = a.copy()
    hand[240:290, 540:630] = 40                    # the held item swinging
    check("find_moving_blob: the held-item corner is ignored",
          vision.find_moving_blob(a, hand) is None, vision.find_moving_blob(a, hand))
    thin = a.copy()
    thin[100:140, 300:301] = 0                     # a one-pixel chat stroke
    check("find_moving_blob: a one-pixel-wide change is eroded away",
          vision.find_moving_blob(a, thin) is None, vision.find_moving_blob(a, thin))
    faint = a.copy()
    faint[120:200, 280:330] = 132                  # 12/255 -- water animation, not a mob
    check("find_moving_blob: a change below the threshold is ignored",
          vision.find_moving_blob(a, faint) is None, vision.find_moving_blob(a, faint))
    whole = np.full((360, 640, 3), 220, dtype=np.uint8)
    check("find_moving_blob: the whole view changing means the camera moved, not a mob",
          vision.find_moving_blob(a, whole) is None)

    # -- colour ------------------------------------------------------------------
    def mob(colour, box=(110, 210, 300, 350), fill=120):
        f = scene(fill)
        y0, y1, x0, x1 = box
        f[y0:y1, x0:x1] = colour
        return f
    # The colours the stage-s4 corpus MEASURED off each mob, not the texture files:
    # a zombie is identified by its cyan shirt, a cow by an olive-brown hide.
    cases = {"pig": (176, 100, 100), "zombie": (0, 130, 130), "creeper": (13, 167, 11),
             "blaze": (246, 178, 1), "phantom": (100, 140, 200), "cow": (52, 36, 20),
             "witch": (30, 5, 60)}
    got = {k: (vision.entity_hint(mob(v)) or ("none",))[0] for k, v in cases.items()}
    check("entity_hint: each mob's own colour gets its own label",
          all(got[k] == k for k in cases), got)
    check("entity_hint: an empty grey scene is not a mob", vision.entity_hint(scene()) is None)
    check("entity_hint: the sky is not a mob", vision.entity_hint(scene(205)) is None)
    check("entity_hint(want=): the asked mob is found and a wrong ask is not",
          (vision.entity_hint(mob(cases["pig"]), want="pig") or ("none",))[0] == "pig"
          and vision.entity_hint(mob(cases["pig"]), want="zombie") is None)
    hint = vision.entity_hint(mob(cases["zombie"]))
    check("entity_hint: returns the blob centroid in full-frame coordinates",
          hint is not None and abs(hint[1] - 324) <= 3 and abs(hint[2] - 159) <= 3, hint)

    # -- plan-time compilation ------------------------------------------------------
    inv = fake_info(inventory={"diamond_sword": 1, "bow": 1, "arrow": 8, "shears": 1})
    acts, note = ME.face_entity(CursorState(), inv, ticks=40, label="zombie")
    check("face_entity compiles to one _face marker carrying the label",
          len(acts) == 1 and acts[0]["_face"]["label"] == "zombie"
          and acts[0]["_cost"] == 40, (acts, note))
    acts, note = ME.fight(CursorState(), inv)
    ft = next(a["_fight"] for a in acts if "_fight" in a)
    check("fight picks the best sword carried and equips it first",
          ft["weapon"] == "diamond_sword" and any(a.get("hotbar.1") for a in acts
                                                  if "_fight" not in a), (ft, note))
    acts, note = ME.fight(CursorState(), fake_info(inventory={"stone_axe": 1}))
    check("fight falls back to an axe when no sword is carried",
          next(a["_fight"] for a in acts if "_fight" in a)["weapon"] == "stone_axe", note)
    acts, note = ME.fight(CursorState(), fake_info())
    check("fight with nothing carried still fights bare-handed",
          next(a["_fight"] for a in acts if "_fight" in a)["weapon"] is None, note)
    acts, note = ME.fight(CursorState(), inv, weapon="netherite_sword")
    check("fight refuses a weapon that is not carried", not acts and "carry no" in note, note)
    acts, note = ME.shoot_bow(CursorState(), inv, shots=3)
    check("shoot_bow compiles with a draw of at least 25 ticks",
          next(a["_shoot"] for a in acts if "_shoot" in a)["draw"] >= 25
          and next(a["_shoot"] for a in acts if "_shoot" in a)["shots"] == 3, note)
    acts, note = ME.shoot_bow(CursorState(), fake_info(inventory={"bow": 1}))
    check("shoot_bow refuses a bow with no arrows", not acts and "no arrows" in note, note)
    acts, note = ME.block_with_shield(CursorState(), inv)
    check("block_with_shield refuses without a shield", not acts and "carry no" in note, note)
    acts, note = ME.block_with_shield(CursorState(), fake_info(inventory={"shield": 1}))
    check("block_with_shield compiles to equip + one _shield marker",
          sum(1 for a in acts if "_shield" in a) == 1, note)
    acts, note = ME.use_on_entity(CursorState(), inv, item="shears")
    check("use_on_entity equips the item and compiles one _useent marker",
          next(a["_useent"] for a in acts if "_useent" in a)["item"] == "shears", note)
    acts, note = ME.use_on_entity(CursorState(), fake_info(), item="oak_boat")
    check("use_on_entity(oak_boat) with no boat carried clicks the FLOATING boat",
          next(a["_useent"] for a in acts if "_useent" in a)["item"] is None, note)
    acts, note = ME.use_on_entity(CursorState(), fake_info(), item="shears")
    check("use_on_entity refuses an item that is not carried", not acts and "carry no" in note,
          note)
    acts, note = ME.boat_forward(CursorState(), fake_info(), ticks=40, yaw=90)
    check("boat_forward compiles with the heading it was given",
          next(a["_boatfwd"] for a in acts if "_boatfwd" in a)["yaw"] == 90.0, note)
    check("leave_boat compiles to one _leaveboat marker",
          len(ME.leave_boat()) == 1 and "_leaveboat" in ME.leave_boat()[0])
    check("the fight markers are registered as combat (the hit reflex leaves them alone) "
          "and fight/boat_forward as moving",
          {"_fight", "_face", "_shoot", "_shield", "_useent"} <= macros.COMBAT
          and {"_fight", "_boatfwd"} <= macros.MOVING)
    from mcu_worldmodel import procedures as P
    trimmed = P.shrink_marker(next(a for a in acts if "_boatfwd" in a), 25)
    check("an entity marker is shrinkable to fit a step cap",
          trimmed is not None and trimmed["_boatfwd"]["ticks"] == 25
          and trimmed["_cost"] == 25, trimmed)
    docs = P.reference()
    check("docs: the entity macros are offered",
          all(k in docs for k in ("face_entity(", "fight(", "shoot_bow(",
                                  "block_with_shield(", "use_on_entity(",
                                  "boat_forward(", "leave_boat(")))

    # -- the fight loop against a scripted world -------------------------------------
    # A milestone the scripted world never reaches: a ledger that COMPLETES makes the
    # runner coast on no-ops to the episode end, which would end the fight before its
    # own note was written (and is the right behaviour -- just not the one under test).
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]

    class MobWorld:
        """One mob at a fixed bearing. The frame draws it where the current camera
        would see it, so the aim loop closes; a pulsed attack within tolerance and in
        reach takes 5 hp off it, and the fourth hit kills it."""

        def __init__(self, bearing_yaw=25.0, bearing_pitch=8.0, hp=20.0, reach=True):
            self.pitch, self.yaw = 0.0, 0.0
            self.byaw, self.bpitch, self.mob_hp = bearing_yaw, bearing_pitch, hp
            self.reach = reach
            self.stats = {"kill_entity": {}, "use_item": {}, "custom": {}}
            self.swings, self.landed = 0, 0
            self.x, self.z = 1.5, 2.5

        def pos(self):
            return {"x": self.x, "y": 64.0, "z": self.z,
                    "pitch": self.pitch, "yaw": self.yaw}

        def pov(self):
            f = np.full((360, 640, 3), 120, dtype=np.uint8)
            if self.mob_hp <= 0:
                return f
            cx = 320 + (self.byaw - self.yaw) * 6.3
            cy = 180 + (self.bpitch - self.pitch) * 5.26
            x0, y0 = int(cx - 26), int(cy - 52)
            x1, y1 = max(x0 + 1, int(cx + 26)), max(y0 + 1, int(cy + 52))
            x0, x1 = max(0, min(639, x0)), max(1, min(640, x1))
            y0, y1 = max(0, min(294, y0)), max(1, min(295, y1))
            f[y0:y1, x0:x1] = (0, 130, 130)          # a zombie's cyan shirt
            return f

        def info(self):
            i = fake_info(inventory={"diamond_sword": 1})
            i["location_stats"].update(
                {"xpos": np.array(self.x), "ypos": np.array(64.0),
                 "zpos": np.array(self.z), "pitch": np.array(self.pitch),
                 "yaw": np.array(self.yaw)})
            for k, bucket in self.stats.items():
                i[k] = {n: np.array(float(v)) for n, v in bucket.items()}
            i["pov"] = self.pov()
            return i

        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch = max(-90.0, min(90.0, self.pitch + float(cam[0])))
            self.yaw += float(cam[1])
            if a.get("forward"):
                self.reach = True
            if a.get("attack") and self.mob_hp > 0:
                self.swings += 1
                # The hit window is the mob's HITBOX: a 0.6-block-wide body at the
                # 3-block melee reach subtends 5.7 degrees either side, which is 27 px
                # in this frame. A window narrower than the aim tolerance would be a
                # fake world stricter than the engine.
                on = (abs(self.yaw - self.byaw) * 6.3 <= 30
                      and abs(self.pitch - self.bpitch) * 5.26 <= 26)
                if on and self.reach:
                    self.landed += 1
                    self.mob_hp -= 5.0
                    d = self.stats["custom"]
                    d["damage_dealt"] = d.get("damage_dealt", 0) + 50
                    u = self.stats["use_item"]
                    u["diamond_sword"] = u.get("diamond_sword", 0) + 1
                    if self.mob_hp <= 0:
                        self.stats["kill_entity"]["zombie"] = 1

    def drive(tag, plan, world, steps=600):
        ag = WorldModelAgent(workspace=root / f"ent_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"), induction_every=0,
                             step_cap=400)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": plan}, "message": "[PLAN]\nentity"},
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
        seen: list[str] = []
        _add = ag.memory.add_note
        ag.memory.add_note = lambda n: (seen.append(n), _add(n))[1]
        ag.start(world.info())
        for step in range(1, steps):
            a = ag.next_action(world.info())
            world.apply(a)
            ag.observe(world.info(), step)
            if ag.codex.calls >= 2 and not ag.queue:
                break
        return ag, " | ".join(seen)

    w = MobWorld()
    ag, notes = drive("face", [{"procedure": "face_entity",
                                "args": {"ticks": 60, "label": "zombie"}}], w)
    check("face_entity turns onto the mob's bearing and says it is centred",
          abs(w.yaw - w.byaw) <= 3.0 and abs(w.pitch - w.bpitch) <= 3.0
          and "crosshair centred" in notes and ag.cursor_stats.get("face_entity_ok") == 1,
          (w.yaw, w.pitch, notes[-260:]))
    w = MobWorld()
    ag, notes = drive("fight", [{"procedure": "fight", "args": {"ticks": 300}},
                                {"procedure": "travel", "args": {"n": 10}}], w)
    check("fight aims, pulses attack and stops the moment the kill registers",
          w.stats["kill_entity"].get("zombie") == 1 and "KILLED zombie" in notes
          and w.landed == 4 and "4 landed" in notes, (w.swings, w.landed, notes[-320:]))
    check("fight reports the damage dealt from custom.damage_dealt (tenths of hp)",
          "20.0 hp of damage dealt" in notes, notes[-320:])
    w = MobWorld(reach=False)
    ag, notes = drive("fight_far", [{"procedure": "fight", "args": {"ticks": 300}}], w)
    check("fight walks in when its swings land nothing, then kills",
          w.stats["kill_entity"].get("zombie") == 1 and "walked" in notes,
          (w.swings, w.landed, notes[-320:]))
    w = MobWorld(bearing_yaw=25.0)
    w.mob_hp = 0.0                                    # nothing in view at all
    ag, notes = drive("fight_none", [{"procedure": "fight", "args": {"ticks": 200}}], w)
    check("fight with nothing in view says so instead of swinging at air",
          "nothing to fight" in notes and w.swings == 0, notes[-320:])

    class HurtWorld(MobWorld):
        """The mob hits back: four hp every twenty ticks, the way a real swing lands
        (a 3+ hp drop in one tick is exactly what arms the runner's hit reflex)."""

        def __init__(self):
            super().__init__(hp=400.0)          # it outlives the fight's budget
            self.hp, self.t = 20.0, 0

        def info(self):
            i = super().info()
            i["health"] = np.array(self.hp)
            return i

        def apply(self, a):
            super().apply(a)
            self.t += 1
            if self.t % 20 == 0:
                self.hp = max(0.0, self.hp - 4.0)

    hw = HurtWorld()
    ag, notes = drive("retreat", [{"procedure": "fight",
                                   "args": {"ticks": 300, "retreat_hp": 12}}], hw)
    check("fight breaks off at retreat_hp and backs away instead of dying on the spot",
          "BROKE OFF" in notes and hw.hp <= 12.0, (hw.hp, notes[-320:]))
    check("real 4 hp hits arrive during the fight (so the reflex rule is exercised)",
          hw.hp <= 12.0 and ag.cursor_stats.get("damage_repeats", 0) >= 1,
          (hw.hp, ag.cursor_stats))
    check("the hit reflex does NOT clear the plan or spin the avatar away while a "
          "fight marker is the queue head",
          ag.cursor_stats.get("damage_interrupts", 0) == 0
          and abs(hw.yaw - hw.byaw) <= 25.0, (ag.cursor_stats, hw.yaw))


def test_harness_guards(root: Path) -> None:
    """The dm5 guards: click verification, closed-screen flush, dig/stair stalls, yaw."""
    print("\n[guards] GUI click verification, dig/stair stall stops, yaw display")
    from mcu_worldmodel import gui
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.memory import norm_yaw, state_line
    from mcu_worldmodel.procedures import act, click, dig_down, stair_down

    # -- click() is now a marker, at the unchanged 3-tick cost
    c = click("attack")
    check("click is a _click marker, cost 3",
          len(c) == 1 and "_click" in c[0] and c[0]["_cost"] == 3, str(c))

    # -- yaw is displayed as an angle, not a turn count
    check("norm_yaw(-571) == 149", norm_yaw(-571) == 149.0, str(norm_yaw(-571)))
    sl = state_line({"x": 1.0, "y": 2.0, "z": 3.0, "pitch": 0.0, "yaw": -898.0}, None)
    check("state_line yaw normalised (-898 -> -178)", "yaw=-178" in sl, sl)

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]

    def mk(tag: str) -> WorldModelAgent:
        ag = WorldModelAgent(workspace=root / f"gd_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"),
                             induction_every=0, step_cap=400)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "-"}
        ] * 6)
        ag.start(fake_info())
        return ag

    # -- A0: a WORLD click (place_block) runs with no screen open, unguarded
    from mcu_worldmodel.procedures import place_block
    ag0 = mk("world")
    steps = place_block(45.0)
    check("place_block's click is gui=False",
          steps[-1]["_click"]["gui"] is False, str(steps[-1]))
    ag0.queue.extend([(steps[-1], 0)])
    a = ag0.next_action(fake_info())
    check("world click emits use with the screen closed",
          a.get("use") == 1 and not ag0.cursor_stats.get("gui_closed_flush"),
          f"{a} {ag0.cursor_stats}")

    # -- A: a GUI click against a closed screen drops the plan's tail
    ag = mk("closed")
    ag.queue.extend([(click("attack")[0], 0), (act(), 1), (act(), 2)])
    ag.next_action(fake_info())
    check("closed-screen click flushed the plan",
          ag.cursor_stats.get("gui_closed_flush") == 1, str(ag.cursor_stats))
    notes = " | ".join(ag.memory._pending_notes)
    check("...and said which entries were dropped",
          "the screen is closed" in notes and "was dropped" in notes, notes)

    # -- B: a click whose pointer moved since the servo landed is aborted
    ag = mk("moved")
    ag.cursor.opened({})
    ag.cursor.anchor((125.0, 152.0), 1)
    ag._servo_landed = (125.0, 152.0)
    ag.cursor.anchor((88.0, 83.0), 2)          # the game snapped the pointer away
    ag.queue.extend([(click("attack")[0], 0), (act(), 1)])
    ag.next_action(fake_info())
    check("moved-pointer click aborted",
          ag.cursor_stats.get("click_pos_mismatch") == 1, str(ag.cursor_stats))
    check("...naming both positions",
          "click aborted" in " | ".join(ag.memory._pending_notes),
          " | ".join(ag.memory._pending_notes))

    # -- C: a lift that changes nothing is called out one tick after the click
    ag = mk("lift")
    tl = gui.slot_topleft(6)
    on6 = (tl[0] + 8.0, tl[1] + 8.0)
    ag._cur_inv = {"cobblestone": 17}
    ag.cursor.opened({"cobblestone": 17})
    ag.cursor.anchor(on6, 1)
    ag._servo_landed = on6
    ag.queue.extend([(click("attack")[0], 0), (act(), 1), (act(), 2)])
    for _ in range(7):
        ag.next_action(fake_info())            # inventory never changes
    check("empty lift detected", ag.cursor_stats.get("click_lifted_nothing") == 1,
          str(ag.cursor_stats))
    check("...with the slot named", "lifted nothing" in
          (ag.memory.logs_path.read_text(encoding="utf-8")
           + " | ".join(ag.memory._pending_notes)))

    # -- D: dig_down that breaks nothing stops at 60 ticks, not its budget
    ag = mk("dig")
    ag._gui_open = False
    ag._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 60.0, "yaw": 0.0}
    dg = dig_down(300)[-1]["_dig"]
    ticks = 0
    while ag._dig_tick(dg, act) is not None:
        ticks += 1
        if ticks > 200:
            break
    check("dig stall stops at 60 ticks", ticks == 60 and
          ag.cursor_stats.get("dig_stall_stops") == 1,
          f"ticks={ticks} {ag.cursor_stats}")
    check("...saying nothing broke", "nothing broke" in
          " | ".join(ag.memory._pending_notes), " | ".join(ag.memory._pending_notes))

    # -- E: a dig that works reports what it did when its budget ends
    ag2 = mk("dig2")
    ag2._gui_open = False
    ag2._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 60.0, "yaw": 0.0}
    dg = dig_down(8)[-1]["_dig"]
    ticks = 0
    while ag2._dig_tick(dg, act) is not None:
        ticks += 1
        ag2._other_breaks += 0.5               # blocks are breaking
        ag2._cur_pos["y"] -= 0.2               # and y is dropping
    check("dig end-of-budget summary written",
          any("dig_down: broke" in n for n in ag2.memory._pending_notes),
          " | ".join(ag2.memory._pending_notes))

    # -- E2: a dig that breaks blocks but never descends stops at the 96-tick
    # window with a carving-a-wall diagnosis (kd10rec: "broke 4, descended 0.0
    # in 390 ticks" burned the whole budget silently)
    ag2b = mk("dig3")
    ag2b._gui_open = False
    ag2b._cur_pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 90.0, "yaw": 0.0}
    dgb = dig_down(300)[-1]["_dig"]
    ticks_b = 0
    while ag2b._dig_tick(dgb, act) is not None and ticks_b < 200:
        ticks_b += 1
        if ticks_b % 40 == 0:
            ag2b._other_breaks += 1.0          # slow breaks, wall not column
        # y never moves
    notes_b = " | ".join(ag2b.memory._pending_notes)
    check("dig no-descent window stops early (not at budget)",
          96 <= ticks_b <= 110, f"ticks={ticks_b}")
    check("...with the carving-a-wall diagnosis",
          "carving a wall" in notes_b and "pitch=90" in notes_b, notes_b[-200:])

    # -- F: a staircase that breaks and advances but never descends is stopped
    ag3 = mk("stair")
    ag3._gui_open = False
    pos = {"x": 0.0, "y": 64.0, "z": 0.0, "pitch": 48.0, "yaw": 0.0}
    ag3._cur_pos = pos
    mf = stair_down(depth=10)[0]["_mfwd"]
    phase_attacks = 0
    # Parallel ifs, not elif: attack/forward actions carry camera=[0,0], which
    # is truthy, so an elif chain starves the world of breaks and advance.
    for _ in range(400):
        a = ag3._mfwd_tick(mf, act)
        if a is None:
            break
        if a.get("camera"):
            pos["pitch"] += max(-20.0, min(20.0, a["camera"][0]))
        if a.get("attack"):
            phase_attacks += 1
            if phase_attacks >= 2:             # the carve breaks blocks...
                ag3._other_breaks += 1.0
                phase_attacks = 0
        if a.get("forward"):
            pos["x"] += 1.0                    # ...and the walk-in advances
        # but y never moves: the staircase is not going down
    check("no-descent staircase stopped (after the ladder maxed)",
          ag3.cursor_stats.get("stair_no_descent_stops") == 1
          and mf.get("p_lo_bump", 0.0) == 14.0,
          f"stats={ag3.cursor_stats} bump={mf.get('p_lo_bump')}")
    check("...naming the steepest cut tried", any(
          "even at the steepest cut" in n for n in ag3.memory._pending_notes),
          " | ".join(ag3.memory._pending_notes))




def test_escalation(root: Path) -> None:
    """G1/G2/G3: failure streaks, stall visibility, staleness, crisis induction."""
    print("\n[escalation] failure streaks, stall header, staleness, crisis induction")
    from mcu_worldmodel import prompts
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.hypotheses import HypothesisGraph

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "esc", task_text="t",
                         ledger=MilestoneLedger(cfg, "t"),
                         induction_every=600, step_cap=400)
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "-"}
    ] * 4)
    ag.start(fake_info())

    # -- G2a: the shared header names the stall counter, in both memory modes
    ag._stall_turns = 7
    p_wm = ag._turn_prompt(fake_info())
    check("header carries the stall counter",
          "Act turns since anything verifiably changed (milestone or inventory): 7."
          in p_wm, p_wm.splitlines()[1])
    ag.structured = False
    check("...identically in the logbook arm",
          "Act turns since anything verifiably changed" in ag._turn_prompt(fake_info()))
    ag.structured = True

    # -- G1: two guard-stops become a notice; a mechanism hypothesis absorbs it
    ag._note_failure("dig_down")
    ag._note_failure("dig_down")
    n = ag._notices()
    check("streak of 2 renders a notice", "`dig_down` has been guard-stopped 2 times"
          in n, n)
    check("...flagging the missing mechanism hypothesis",
          "no mechanism hypothesis mentions it" in n, n)
    ag.graph.add_or_update(id="mech_dig", statement="dig ticks break nothing on gravel",
                           confidence=0.4, status="active", kind="mechanism", step=5)
    n = ag._notices()
    check("a mechanism hypothesis absorbs the flag",
          "no mechanism hypothesis mentions it" not in n, n)

    # -- G1: verified progress clears the streaks (the act turn's marker moved)
    ag._cur_inv = {"spruce_log": 2}
    ag.next_action(fake_info())
    check("progress clears the streaks", not ag._proc_fails, str(ag._proc_fails))

    # -- G2b: stale active nodes say how stale they are
    g = HypothesisGraph()
    g.add_or_update(id="goal_x", statement="s", confidence=0.8, status="active",
                    kind="goal", step=100)
    view = g.to_prompt_summary(12, None, now_step=5000)
    check("stale node dated", "updated 4900 steps ago" in view, view)
    check("fresh node undated",
          "updated" not in g.to_prompt_summary(12, None, now_step=250))

    # -- G3: the stall trigger remembers why it fired and picks the focused prompt
    ag._stall_turns, ag._last_induction = 12, ag.step - 250
    check("stall trigger fires", ag._due_for_induction() is True)
    check("...and is remembered as a stall", ag._induction_stalled is True)
    ag._stall_turns, ag._last_induction = 0, ag.step - 601
    check("periodic trigger fires", ag._due_for_induction() is True)
    check("...and is not a stall", ag._induction_stalled is False)
    sp = prompts.induction_stall_prompt(
        task_text="t", progress_block="p", per_doc_chars=2000,
        stall_turns=13, failure_lines="- `dig_down`: 3 consecutive guard-stops")
    check("stall prompt is the diagnosis prompt",
          "called EARLY" in sp and "not a housekeeping turn" in sp
          and "Re-price" in sp)
    check("stall prompt carries the streaks", "3 consecutive guard-stops" in sp)


def test_seed_memory(root: Path) -> None:
    """--seed-memory: knowledge carries across runs, the episodic record does not."""
    print("\n[seed-memory] inherited knowledge vs episodic record")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from worldmodel_purple_agent import seed_memory_dir, SEED_SKIP

    seed = root / "seed_src"
    for d in ("world_model", "hypotheses", "tools", "entities", "maps", "episodes", "events"):
        (seed / d).mkdir(parents=True)
    (seed / "world_model" / "terrain.md").write_text("iron seam at (-3010, 55, -5590)")
    (seed / "hypotheses" / "h1.json").write_text("{}")
    (seed / "tools" / "probe.py").write_text("# tool")
    (seed / "maps" / "visited.csv").write_text("x,z\n")
    (seed / "logs.txt").write_text("Action 1 | Step 10 ...")
    (seed / "episodes" / "junk.png").write_text("x")
    (seed / "events" / "events.jsonl").write_text("{}")
    (seed / "actions.json").write_text("{}")
    (seed / "AGENTS.md").write_text("old contract")

    dest = root / "seed_dst"
    copied = seed_memory_dir(seed, dest)
    check("seed: knowledge dirs copied",
          (dest / "world_model" / "terrain.md").exists()
          and (dest / "hypotheses" / "h1.json").exists()
          and (dest / "tools" / "probe.py").exists()
          and (dest / "maps" / "visited.csv").exists(), str(copied))
    check("seed: episodic record left behind",
          not (dest / "logs.txt").exists() and not (dest / "episodes").exists()
          and not (dest / "events").exists() and not (dest / "AGENTS.md").exists(),
          str(sorted(x.name for x in dest.iterdir())))
    check("seed: skip set names what it skips",
          {"logs.txt", "episodes", "events", "AGENTS.md"} <= SEED_SKIP, str(SEED_SKIP))
    # existing files in dest are never clobbered
    (dest / "world_model" / "terrain.md").write_text("newer truth")
    copied2 = seed_memory_dir(seed, dest)
    check("seed: existing files win over the seed",
          (dest / "world_model" / "terrain.md").read_text() == "newer truth"
          and "world_model" not in copied2, f"copied2={copied2}")
    # the memory module seeds around the inherited docs instead of overwriting
    from mcu_worldmodel.memory import MultimodalMemory
    mem = MultimodalMemory(dest, structured=True)
    mem.seed_world_model("task text")
    check("seed: seed_world_model keeps the inherited doc",
          (dest / "world_model" / "terrain.md").read_text() == "newer truth", "")



def test_governor(root: Path) -> None:
    """Null-entry governor: nudge on the second no-change entry, refuse the third,
    aspiration on world movement, and the ledger line in the notices."""
    print("\n[governor] null-entry tabu across turns")
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.governor import Governor

    g = Governor()
    cell = (0, 8, 0)
    base = dict(cell=cell, events=0, moved=0.0, descended=0.0,
                inv_changed=False, item_types={"log"}, milestones=0)
    n1 = g.note_entry(label="look_abs", step=100, **base)
    n2 = g.note_entry(label="look_abs", step=140, **base)
    check("governor: first null silent, second nudges",
          n1 is None and n2 is not None and "will be refused" in n2, str(n2))
    check("governor: third is vetoed at zero cost",
          (g.check("look_abs", cell, 150) or "").startswith("governor: REFUSED"),
          str(g.check("look_abs", cell, 150)))
    check("governor: other cell unaffected",
          g.check("look_abs", (1, 8, 0), 150) is None, "")
    g2 = Governor()
    for st in (100, 140, 180):
        g2.note_entry(label="dig_down", step=st, **base)
        g2.note_entry(label="raw", step=st, **base)
        g2.note_entry(label="cursor_to_slot", step=st, **base)
    check("governor: descents, raw and GUI micro-ops are never vetoed",
          g2.check("dig_down", cell, 200) is None
          and g2.check("raw", cell, 200) is None
          and g2.check("cursor_to_slot", cell, 200) is None, "")
    g.note_entry(label="look_abs", step=200, cell=cell, events=0, moved=0.0,
                 descended=0.0, inv_changed=False,
                 item_types={"log", "cobblestone"}, milestones=0)
    check("governor: a new item type lifts every ban (aspiration)",
          g.check("look_abs", cell, 210) is None, "")
    g3 = Governor()
    g3.note_entry(label="equip_hotbar", step=100, **base)
    g3.note_entry(label="equip_hotbar", step=140, **base)
    g3.note_entry(label="equip_hotbar", step=180, cell=cell, events=2, moved=0.0,
                  descended=0.0, inv_changed=True, item_types={"log"}, milestones=0)
    check("governor: a productive entry clears the streak",
          g3.check("equip_hotbar", cell, 200) is None, "")
    g4 = Governor()
    g4.note_entry(label="look_at", step=100, **base)
    g4.note_entry(label="look_at", step=140, **base)
    check("governor: tenure expires a stale ban",
          g4.check("look_at", cell, 141) is not None
          and g4.check("look_at", cell, 140 + 1501) is None, "")
    line = g.summary(step=300, y=64.0, budget=12000)
    check("governor: ledger line carries counts, y and budget",
          "changed nothing" in line and "y=64" in line and "of 12000" in line, line)

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "gov", task_text="t",
                         ledger=MilestoneLedger(cfg, "t"),
                         induction_every=0, step_cap=400)
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [{"procedure": "look_abs",
                                  "args": {"pitch": 30, "ticks": 8}}]},
         "message": "[PLAN]\nlook once"},
        {"actions": {"actions": [{"procedure": "look_abs",
                                  "args": {"pitch": 30, "ticks": 8}}]},
         "message": "[PLAN]\nlook again"},
        {"actions": {"actions": [{"procedure": "look_abs",
                                  "args": {"pitch": 30, "ticks": 8}}]},
         "message": "[PLAN]\nlook a third time, alone"},
        {"actions": {"actions": [{"procedure": "look_abs",
                                  "args": {"pitch": 30, "ticks": 8}},
                                 {"procedure": "chop_tree", "args": {"n": 10}}]},
         "message": "[PLAN]\nlook then chop"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]},
         "message": "[PLAN]\n-"},
    ])
    gov = {"attacks": 0}
    def gov_info():
        i = fake_info()
        i["pov"] = np.full((360, 640, 3), 120, dtype=np.uint8)
        return i
    ag.start(gov_info())
    for step in range(1, 61):
        a = ag.next_action(gov_info())
        if a.get("attack"):
            gov["attacks"] += 1
        ag.observe(gov_info(), step)
    log_g = (ag.memory.root / "logs.txt").read_text(encoding="utf-8")
    check("governor wired: nudge lands in the log after the second null look",
          "governor: `look_abs`" in log_g and "will be refused" in log_g, "")
    check("governor wired: an all-null plan is dropped whole, with a no-op",
          ag.cursor_stats.get("governor_plan_drops", 0) >= 1
          and "REFUSED this whole plan" in log_g, str(ag.cursor_stats))
    check("governor wired: a mixed plan runs intact, banned preamble included",
          gov["attacks"] > 0, str(gov))
    check("governor wired: ledger line reaches the notices",
          "changed nothing" in ag._notices(), ag._notices())


def test_playbook(root: Path) -> None:
    """Playbook branching: logs.txt -> turn groups -> shadow backend -> handover."""
    print("\n[playbook] replay a recorded prefix, then hand over")
    from mcu_worldmodel.playbook import PlaybookCodex, extract_playbook

    log = root / "pb_logs.txt"
    log.write_text(
        "=" * 80 + "\n"
        "Action 0 | Step 0 | INITIAL STATE\n\n[STATE] pos=(0, 64, 0)\n"
        + "=" * 80 + "\n"
        "Action 1 | Step 10 | Plan Step 1/2 | 0/10 verified\n\n"
        "[ACTION] look_abs(pitch=-90,yaw=None,ticks=40) -> 40 ticks\n"
        + "=" * 80 + "\n"
        "Action 2 | Step 50 | Plan Step 2/2 | 0/10 verified\n\n"
        "[ACTION] cursor_to_cell(grid=2x2,cell=out) -> 16 ticks\n"
        + "=" * 80 + "\n"
        "Action 3 | Step 60 | Plan Step 1/1 | 0/10 verified\n\n"
        "[ACTION] stow_items(grid=2x2,cells=[0,1]) -> 57 ticks\n"
        + "=" * 80 + "\n"
        "Action 4 | Step 60 | Plan Step 1/1 | 0/10 verified\n\n"
        '[ACTION] {"forward":1} x10\n'
        + "=" * 80 + "\n"
        "Action 4 | Step 900 | Plan Step 1/1 | 1/10 verified\n\n"
        "[ACTION] dig_down(n=40, until_y=57) -> 40 ticks\n"
        "[EVENT] MILESTONE mine_log verified\n",
        encoding="utf-8")
    turns = extract_playbook(log, until_step=100)
    check("playbook: turn grouping from Plan Step indices",
          len(turns) == 3 and len(turns[0]["actions"]) == 2
          and len(turns[1]["actions"]) == 1
          and len(turns[2]["actions"]) == 1, str(turns))
    a0 = turns[0]["actions"][0]
    check("playbook: args parse with None and negatives",
          a0["procedure"] == "look_abs"
          and a0["args"] == {"pitch": -90, "yaw": None, "ticks": 40}, str(a0))
    check("playbook: non-literal args stay strings",
          turns[0]["actions"][1]["args"] == {"grid": "2x2", "cell": "out"},
          str(turns[0]["actions"][1]))
    check("playbook: a list argument survives the comma split",
          turns[1]["actions"][0]["args"] == {"grid": "2x2", "cells": [0, 1]},
          str(turns[1]["actions"][0]))
    check("playbook: raw entries round-trip",
          turns[2]["actions"][0] == {"action": {"forward": 1}, "repeat": 10},
          str(turns[2]))
    check("playbook: entries past until_step are dropped",
          all("dig_down" != a.get("procedure")
              for t in turns for a in t["actions"]), "")

    fired = {"n": 0}
    real = FakeCodex(root / "pb_ws", [
        {"actions": {"actions": [{"action": {}, "repeat": 1}]},
         "message": "[PLAN]\nlive"}])
    (root / "pb_ws").mkdir(exist_ok=True)
    pc = PlaybookCodex(real, turns, on_exhausted=lambda: fired.__setitem__("n", fired["n"] + 1))
    r1 = pc.run("p1")
    check("playbook: replay turn is served free",
          r1["ok"] and "look_abs" in r1["actions_json"] and real.calls == 0, str(r1))
    check("playbook: outputs are empty during replay",
          pc.read_outputs() == {"hypotheses_ops": None, "claim": None, "errors": []}, "")
    pc.run("p2")
    pc.run("p3")
    r3 = pc.run("p4")
    check("playbook: handover fires once and delegates",
          fired["n"] == 1 and real.calls == 1 and "repeat" in r3["actions_json"],
          f"fired={fired} calls={real.calls}")
    pc.run("p5")
    check("playbook: stays delegated after handover",
          fired["n"] == 1 and real.calls == 2, f"fired={fired} calls={real.calls}")

    from mcu_worldmodel.playbook import extract_milestone_schedule
    sched = extract_milestone_schedule(log)
    check("playbook: milestone schedule reads step and count",
          sched == [(900, 1)], str(sched))
    real2 = FakeCodex(root / "pb_ws", [
        {"actions": {"actions": [{"action": {}, "repeat": 1}]},
         "message": "[PLAN]\nlive"}])
    fired2 = {"n": 0}
    pc2 = PlaybookCodex(real2, list(turns),
                        on_exhausted=lambda: fired2.__setitem__("n", fired2["n"] + 1),
                        schedule=[(100, 1)], progress=lambda: (2000, 0),
                        grace_steps=800)
    r = pc2.run("p1")
    check("playbook: divergence aborts replay and hands over",
          fired2["n"] == 1 and pc2.aborted_at == 2000 and real2.calls == 1
          and "repeat" in r["actions_json"], f"abort={pc2.aborted_at}")
    pc3 = PlaybookCodex(real2, list(turns), schedule=[(100, 1)],
                        progress=lambda: (2000, 1), grace_steps=800)
    r = pc3.run("p1")
    check("playbook: on-schedule replay keeps serving",
          pc3.aborted_at is None and "look_abs" in r["actions_json"], str(r)[:80])

def test_inventory_encoding() -> None:
    """The live engine reports an empty slot as `{"type": "none", "quantity": 0}`; the
    fake above (taken from a compute-node `sim.reset()`) says "air". Every reader must
    treat both as empty: with the "air"-only predicate the Inventory line read "0 slots
    free" on the first turn of every live arm and stow_items refused every call."""
    print("\n[inventory-encoding] 'none' and zero-quantity slots are empty everywhere")
    from mcu_worldmodel.agent import _empty_slot_count, _first_empty_slot
    from mcu_worldmodel.cursor import CursorState
    from mcu_worldmodel.milestones import slot_is_empty
    from mcu_worldmodel.procedures import _empty_slots, discard_stack, stow_items

    live = fake_info()
    live["inventory"] = {i: {"type": "none", "quantity": 0} for i in range(36)}
    live["inventory"][0] = {"type": "stone_pickaxe", "quantity": 1}
    live["inventory"][9] = {"type": "cobblestone", "quantity": 12}
    check("'none' slot is empty", slot_is_empty({"type": "none", "quantity": 0}))
    check("zero-quantity slot is empty whatever its type",
          slot_is_empty({"type": "dirt", "quantity": 0}))
    check("a held stack is not empty", not slot_is_empty({"type": "dirt", "quantity": 3}))
    check("live encoding: 34 of 36 slots free", _empty_slot_count(live) == 34,
          _empty_slot_count(live))
    check("live encoding: first empty main-row slot is 10", _first_empty_slot(live) == 10,
          _first_empty_slot(live))
    check("live encoding: stow targets found", _empty_slots(live, 3) == [10, 11, 12],
          _empty_slots(live, 3))
    check("live encoding: hotbar and counts read through",
          hotbar_line(live) == "hotbar.1=stone_pickaxex1"
          and inventory_counts(live) == {"stone_pickaxe": 1, "cobblestone": 12},
          (hotbar_line(live), inventory_counts(live)))
    cur = CursorState()
    cur.apply({"inventory": 1})
    acts, note = stow_items(cur, live, grid="2x2", cells=[0])
    check("stow_items no longer refuses a mostly-empty inventory", bool(acts) and not note,
          note)
    full = fake_info()
    full["inventory"] = {i: {"type": "dirt", "quantity": 1} for i in range(36)}
    check("a genuinely full inventory still reads 0 free", _empty_slot_count(full) == 0)
    acts, note = discard_stack(CursorState(), live, slot=9)
    check("discard_stack: open, lift, forced close, step back",
          any("_closegui" in a and a["_closegui"].get("force") for a in acts)
          and any(a.get("back") == 1 for a in acts)
          and sum(1 for a in acts if "_click" in a) == 1 and not note, note)
    acts, note = discard_stack(CursorState(), live, slot=20)
    check("discard_stack refuses an empty slot", not acts and "already empty" in note, note)


def test_lava_guard(root: Path) -> None:
    """Lava in the lower view while moving below y 40 drops the plan, saves a _lava
    frame, writes the note and (structured) a hazard node; a torch flame or a table
    top does not read as lava; standing still, the surface and the rate limit are
    all quiet."""
    print("\n[lava-guard] colour band, motion gate, y gate, rate limit, hazard node")
    from mcu_worldmodel import vision
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.procedures import act

    def frame(kind):
        fr = np.full((360, 640, 3), 80, dtype=np.uint8)
        if kind == "lava":
            fr[240:320, 100:500] = (200, 85, 15)
        elif kind == "torch":
            fr[240:320, 100:500] = (220, 95, 0)
        elif kind == "table":
            fr[240:320, 100:500] = (113, 55, 30)
        return fr

    check("vision: a lava band reads well above the floor",
          vision.lava_fraction(frame("lava")) >= 0.05, str(vision.lava_fraction(frame("lava"))))
    check("vision: torch flame and table top read as nothing",
          vision.lava_fraction(frame("torch")) < 0.002
          and vision.lava_fraction(frame("table")) < 0.002)
    cfg = [{"event": "mine_block", "identity": "mine_iron_ore", "objects": ["iron_ore"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "lava", task_text="iron",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=100000,
                            step_cap=50)
    agent.codex = FakeCodex(agent.memory.root, [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "[PLAN]\nwalk"} for _ in range(6)])

    def obs(x, y, z, kind):
        i = fake_info()
        i["location_stats"].update({"xpos": np.array(float(x)), "ypos": np.array(float(y)),
                                    "zpos": np.array(float(z)), "yaw": np.array(0.0)})
        i["pov"] = frame(kind)
        return i

    agent.start(obs(0, 12, 0, "stone"))
    agent.queue.extend([(act(forward=1), 5)] * 30)
    agent.observe(obs(0.0, 12, 0.0, "lava"), 4)          # no motion yet: quiet
    check("lava: quiet without motion", len(agent.queue) == 30)
    agent._reflex = agent._arm_flee(agent._cur_pos)      # a sprint in progress
    agent.observe(obs(0.5, 12, 0.0, "lava"), 8)          # moved 0.5 blocks toward it
    notes = "\n".join(agent.memory._pending_notes) + agent.memory.logs_path.read_text()
    check("lava: moving toward it drops the plan, saves the frame, notes it",
          not agent.queue and agent.cursor_stats.get("lava_flagged") == 1
          and "LAVA AHEAD" in notes and "_lava.png" in notes
          and any((agent.memory.root / "episodes").rglob("*_lava.png")),
          f"queue={len(agent.queue)} flagged={agent.cursor_stats.get('lava_flagged')}")
    check("lava: a running flee is cancelled with its own note",
          agent._reflex is None and "but lava ahead" in notes, notes[-300:])
    # ...and a flee already 8 blocks along is told to find another way, never "sprint on"
    rf = agent._arm_flee(agent._cur_pos)
    rf["x0"] -= 8.0
    n0 = len(agent.memory._pending_notes)
    agent._finish_flee(rf, "lava ahead")
    late = " | ".join(agent.memory._pending_notes[n0:])
    check("lava: a flee cancelled after 8 blocks gets the find-another-way note",
          "but lava ahead after 8 blocks" in late and "sprint on" not in late, late)
    check("lava: hazard node in the graph",
          any(n.id.startswith("hazard_lava_") and "LAVA in view" in n.statement
              for n in agent.graph.nodes.values()))
    agent.queue.extend([(act(forward=1), 6)] * 10)
    agent.observe(obs(1.0, 12, 0.0, "lava"), 12)
    check("lava: rate-limited right after a flag", len(agent.queue) == 10)
    agent.observe(obs(1.5, 12, 0.0, "torch"), 200)     # past the rate limit
    agent.observe(obs(2.0, 12, 0.0, "torch"), 204)
    check("lava: a torch while moving is not an alarm", len(agent.queue) == 10)
    agent_s = WorldModelAgent(workspace=root / "lava_s", task_text="iron",
                              ledger=MilestoneLedger(cfg, "t"), induction_every=100000,
                              step_cap=50)
    agent_s.codex = FakeCodex(agent_s.memory.root, [])
    agent_s.start(obs(5.0, 70, 0.0, "stone"))
    agent_s.queue.extend([(act(forward=1), 5)] * 10)
    agent_s.observe(obs(5.0, 70, 0.0, "lava"), 4)
    agent_s.observe(obs(5.5, 70, 0.0, "lava"), 8)
    check("lava: the surface is never an alarm",
          len(agent_s.queue) == 10 and not agent_s.cursor_stats.get("lava_flagged"))
    docs = (agent.memory.root / "AGENTS.md").read_text()
    check("docs: the lava watcher is taught", "LAVA AHEAD" in docs)

    # -- the same sighting, reframed when the bucket is carried and obsidian is open ----
    ocfg = [{"event": "mine_block", "identity": "mine_obsidian", "objects": ["obsidian"],
             "reward": 1.0, "max_reward_times": 1}]

    def lava_agent(tag, inv):
        ag = WorldModelAgent(workspace=root / tag, task_text="dragon",
                             ledger=MilestoneLedger(ocfg, "t"), induction_every=100000,
                             step_cap=50)
        ag.codex = FakeCodex(ag.memory.root, [])
        seen: list[str] = []
        _a = ag.memory.add_note
        ag.memory.add_note = lambda n: (seen.append(n), _a(n))

        def o(x, kind, pitch=25.0):
            i = fake_info(inventory=inv)
            i["location_stats"].update({"xpos": np.array(float(x)), "ypos": np.array(11.0),
                                        "zpos": np.array(0.0), "yaw": np.array(0.0),
                                        "pitch": np.array(pitch)})
            i["pov"] = frame(kind)
            return i
        ag.start(o(0, "stone"))
        ag.queue.extend([(act(forward=1), 5)] * 10)
        ag.observe(o(0.0, "lava"), 4)
        ag.observe(o(0.6, "lava"), 8)
        return ag, " | ".join(seen)

    ag_b, notes_b = lava_agent("lava_bucket", {"water_bucket": 1, "diamond_pickaxe": 1})
    check("lava with the bucket and obsidian unmet: the note reframes it as the ingredient "
          "and names the make_obsidian call",
          "THIS IS THE LAVA THE OBSIDIAN NEEDS" in notes_b and "make_obsidian(" in notes_b
          and "the RIM block to pour from" in notes_b
          and "Do not re-issue the same walk" not in notes_b, notes_b[-400:])
    check("lava with the bucket: the hazard sentence stays", "lava ends a run in seconds"
          in notes_b and "Do not walk into it" in notes_b, notes_b[-300:])
    ag_n, notes_n = lava_agent("lava_nobucket", {"diamond_pickaxe": 1})
    check("lava without a bucket keeps the old avoid-it text",
          "Do not re-issue the same walk" in notes_n
          and "THIS IS THE LAVA" not in notes_n, notes_n[-300:])
    ag_d, _ = lava_agent("lava_done", {"water_bucket": 1})
    ag_d.ledger.achieved["mine_obsidian"] = 1
    check("the obsidian milestone is read from the ledger", not ag_d._obsidian_unmet()
          and ag_b._obsidian_unmet())


def test_find_lava(root: Path) -> None:
    """lava_view's geometry, lava_cells' cells, and find_lava's search against a scripted
    world: the walk stops short of the pool naming the rim, an empty leg turns 90 degrees,
    the budget stop says what to do next."""
    print("\n[find-lava] lava_view / lava_cells / find_lava walk, turn, budget")
    from mcu_worldmodel import macros, vision
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel import macros_world as MW
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    LAVA_RGB = (207, 92, 16)          # inside the measured band: g/r 0.44, b/r 0.08

    # -- the reading -------------------------------------------------------------------
    fr = np.full((360, 640, 3), 100, dtype=np.uint8)
    fr[200:260, 120:280] = LAVA_RGB          # left of the held-item cut (cols 60%+)
    frac, cx, bottom, top = vision.lava_view(fr)
    check("lava_view: the mass's centre column, its bottom and top rows",
          frac > 0.02 and abs(cx - (200 / 640 - 0.5)) < 0.01
          and abs(bottom - 259 / 360) < 0.01 and abs(top - 200 / 360) < 0.01,
          (frac, cx, bottom, top))
    clip = np.full((360, 640, 3), 100, dtype=np.uint8)
    clip[300:360, 120:280] = LAVA_RGB        # runs into the hotbar cut at 86%
    check("lava_view: a mass at the frame's lower edge reads clipped (bottom 0.86)",
          abs(vision.lava_view(clip)[2] - 0.86) < 0.01, vision.lava_view(clip))
    check("lava_view: the fraction is lava_fraction's, and an empty frame reads zero",
          abs(frac - vision.lava_fraction(fr)) < 1e-9
          and vision.lava_view(np.full((360, 640, 3), 100, np.uint8)) == (0.0, 0.0, 0.0, 0.0))

    # -- the cells, from angles alone --------------------------------------------------
    TV = math.tan(math.radians(MN.LAVA_VFOV / 2.0))
    TH = math.tan(math.radians(MN.LAVA_HFOV / 2.0))

    def row_of(dist, pitch, drop=0.0):
        """The frame row (0..1) the near edge of a pool `dist` blocks off falls on: the
        projection is rectilinear, so the row is linear in the tangent of the angle."""
        dep = math.degrees(math.atan2(MW.EYE + drop, dist))
        return 0.5 + math.tan(math.radians(dep - pitch)) / (2.0 * TV)

    pos = {"x": 0.5, "y": 11.0, "z": 0.5, "pitch": 12.0, "yaw": 0.0}
    errs = []
    for d in (3.0, 4.0, 6.0, 8.0, 12.0):
        c = MN.lava_cells(pos, 0.0, row_of(d, 12.0))
        errs.append(abs(c["dist"] - d))
        check(f"lava_cells: a pool {d:.0f} blocks dead ahead lands within 1.5 blocks",
              abs(c["dist"] - d) <= 1.5 and c["pool"] == (0, 10, int(0.5 + d))
              and c["rim"] == (0, 10, int(0.5 + d) - 1) and c["drop"] == 0,
              (c["dist"], c["pool"], c["rim"]))
    b_ray, dep_ray = MN.lava_ray(0.0, 30.0, 0.2, 0.5)
    check("lava_ray: a column a fifth of the width right of the crosshair is atan(2 * 0.2 "
          "* tan(51)) off the heading -- 26.4 degrees, not the linear model's 20.4",
          abs(MW.norm_yaw_delta(b_ray, 30.0)
              - math.degrees(math.atan(2 * 0.2 * TH))) < 1e-6 and abs(dep_ray) < 1e-9,
          (b_ray, math.degrees(math.atan(2 * 0.2 * TH))))
    check("lava_ray: down the centre column it is the plain pitch + (row - 0.5) * fov "
          "arithmetic, to a degree",
          abs(MN.lava_ray(12.0, 0.0, 0.0, 0.6)[1] - (12.0 + 0.1 * MN.LAVA_VFOV)) < 1.0,
          MN.lava_ray(12.0, 0.0, 0.0, 0.6))
    off = dict(pos, yaw=30.0)
    c = MN.lava_cells(off, 0.2, row_of(6.0, 12.0))
    dx, dz = MW.facing(c["bearing"])
    check("lava_cells: a mass off the crosshair is placed on its ray's bearing",
          abs(MW.norm_yaw_delta(c["bearing"], MN.lava_ray(12.0, 30.0, 0.2,
                                                          row_of(6.0, 12.0))[0])) < 1e-9
          and abs(c["dist"] - 6.0) <= 1.5
          and c["pool"] == (math.floor(0.5 + c["dist"] * dx), 10,
                            math.floor(0.5 + c["dist"] * dz)),
          (c["bearing"], c["dist"], c["pool"]))
    # A pit: its lip occludes the lava's true near edge, so the reading is the LIP's
    # distance whatever the depth -- which is where the rim block to pour from is.
    c = MN.lava_cells(pos, 0.0, row_of(6.0, 12.0), min_dist=MN.FIND_MIN_DIST)
    check("lava_cells: a pool sunk below the feet reads its lip, so the rim is still named "
          "within 1.5 blocks", abs(c["dist"] - 6.0) <= 1.5 and c["rim"] == (0, 10, 5),
          (c["dist"], c["rim"]))
    # Standing at the edge of a lake below the floor: too steep for a pool at our level.
    c = MN.lava_cells(dict(pos, pitch=50.0), 0.0, 0.60, min_dist=2.0)
    check("lava_cells: a mass too steep to be at our own level is reported BELOW us",
          c["drop"] >= 1 and c["dist"] >= 2.0 and c["pool"][1] == 10 - c["drop"], c)
    check("lava_cells: a mass at or above the horizon has no ground distance",
          MN.lava_cells(dict(pos, pitch=0.0), 0.0, 0.40) is None)
    sen = MN.lava_sentence(MN.lava_cells(pos, 0.0, row_of(6.0, 12.0)))
    check("lava_sentence names the rim and the exact call",
          "make_obsidian(0, 10, 5)" in sen and "RIM" in sen, sen)

    # -- plan-time compilation ----------------------------------------------------------
    inv = fake_info(inventory={"diamond_pickaxe": 1, "water_bucket": 1})
    acts, note = MN.find_lava(CursorState(), inv, n=400)
    st = next(a["_findlava"] for a in acts if "_findlava" in a)
    check("find_lava compiles: the pickaxe is selected, no staircase from y 64... ",
          st["n"] == 400 and st["leg"] == MN.FIND_LEG and st["bucket"]
          and any(a.get("hotbar.1") for a in acts if "_findlava" not in a), (st, note))
    deep = fake_info(inventory={"stone_pickaxe": 1})
    deep["location_stats"]["ypos"] = np.array(64.0)
    acts, note = MN.find_lava(CursorState(), deep, n=300)
    mf = [a["_mfwd"] for a in acts if "_mfwd" in a]
    check("find_lava from y 64: a 20-block staircase down comes first, and the note says so",
          len(mf) == 1 and mf[0]["down_by"] == 20.0 and "staircase down" in note
          and "no water_bucket" in note, (mf, note))
    shallow = fake_info(inventory={"stone_pickaxe": 1})
    shallow["location_stats"]["ypos"] = np.array(11.4)
    acts, _ = MN.find_lava(CursorState(), shallow)
    check("find_lava at y 11 digs no staircase", not any("_mfwd" in a for a in acts))
    acts, note = MN.find_lava(CursorState(), fake_info(inventory={"cobblestone": 4}))
    check("find_lava without a pickaxe is refused", not acts and "no pickaxe" in note, note)
    check("find_lava's marker is registered as moving and shrinkable",
          "_findlava" in macros.MOVING and macros.SHRINK.get("_findlava") == "n")
    from mcu_worldmodel import procedures as P
    check("docs: find_lava is offered", "find_lava(" in P.reference())

    # -- the search against a scripted world -------------------------------------------
    class LavaWorld:
        """A 1-wide stone tunnel at y 11 with a `w`-wide lava pool whose near edge is
        `pool_z` blocks along +z, its surface `drop` blocks below the feet. The frame
        paints the pool where the geometry puts it: the near edge at the depression of
        the ray grazing the pool's lip (atan(1.62 / L), the same whatever the depth,
        because the lip occludes everything steeper) and the far edge at its own level.
        A `wall` of stone blocks at `wall_z` stops the walk until 6 attack ticks break
        each one."""

        def __init__(self, pool_z=10.0, drop=0.0, w=3.0, d=3.0, wall=0, wall_z=4.0,
                     yaw=0.0, lava=True):
            self.x, self.z, self.y = 0.5, 0.5, 11.0
            self.yaw, self.pitch = yaw, 0.0
            self.pool_z, self.drop, self.hw, self.d = pool_z, drop, w / 2.0, d
            self.wall, self.wall_z, self.lava = wall, wall_z, lava
            self.hits, self.broken = 0, 0
            self.inv = {"diamond_pickaxe": 1, "water_bucket": 1}

        def err(self):
            yt = math.degrees(math.atan2(-(0.5 - self.x), self.pool_z - self.z))
            return ((yt - self.yaw + 180.0) % 360.0) - 180.0

        def frame(self):
            f = np.full((360, 640, 3), 90, dtype=np.uint8)
            L = self.pool_z - self.z
            if not self.lava or L <= 0.2:
                return f
            e = self.err()
            if abs(e) >= 51:
                return f

            def row(dep):                      # rectilinear: rows are linear in tan
                t = math.tan(math.radians(max(-80.0, min(80.0, dep - self.pitch))))
                return max(0, min(359, int(round(180 + 180 * t / TV))))
            r0 = row(math.degrees(math.atan2(MW.EYE + self.drop, L + self.d)))
            r1 = row(math.degrees(math.atan2(MW.EYE, L)))
            if r1 <= r0:
                return f
            half = int(320 * (self.hw / max(L, 0.5)) / TH)
            c = int(round(320 + 320 * math.tan(math.radians(e)) / TH))
            f[r0:r1, max(0, c - half):min(640, c + half)] = LAVA_RGB
            return f

        def info(self):
            i = fake_info(inventory=self.inv, mine_block={"stone": self.broken})
            i["location_stats"].update({"xpos": np.array(self.x), "ypos": np.array(self.y),
                                        "zpos": np.array(self.z), "pitch": np.array(self.pitch),
                                        "yaw": np.array(self.yaw)})
            i["pov"] = self.frame()
            return i

        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch = max(-90.0, min(90.0, self.pitch + float(cam[0])))
            self.yaw += float(cam[1])
            at_wall = (self.wall > 0 and self.wall_z - 0.3 <= self.z < self.wall_z + 0.3
                       and abs(self.err()) < 40.0)
            if a.get("attack") and at_wall and self.pitch > 5.0:
                self.hits += 1
                if self.hits >= 6:
                    self.hits, self.wall, self.broken = 0, self.wall - 1, self.broken + 1
            sp = 0.28 if a.get("sprint") else 0.2
            for key, ang in (("forward", 0.0), ("back", 180.0)):
                if a.get(key):
                    if key == "forward" and at_wall:
                        continue
                    h = math.radians(self.yaw + ang)
                    self.x, self.z = self.x - sp * math.sin(h), self.z + sp * math.cos(h)

    cfg = [{"event": "mine_block", "identity": "mine_obsidian", "objects": ["obsidian"],
            "reward": 1.0, "max_reward_times": 1}]

    def drive(tag, args, world, steps=900, prefix=None):
        ag = WorldModelAgent(workspace=root / f"findlava_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"), induction_every=0,
                             step_cap=1600)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": list(prefix or []) + [{"procedure": "find_lava", "args": args}]},
             "message": "[PLAN]\nsearch"},
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
        seen: list[str] = []
        _a = ag.memory.add_note
        ag.memory.add_note = lambda n: (seen.append(n), _a(n))
        ag.start(world.info())
        for step in range(1, steps):
            a = ag.next_action(world.info())
            world.apply(a)
            ag.observe(world.info(), step)
            if ag.codex.calls >= 2 and not ag.queue:
                break
        return ag, " | ".join(seen)

    w = LavaWorld(pool_z=10.0, wall=1, wall_z=4.0)
    ag, notes = drive("found", {"n": 700}, w)
    call = re.search(r"make_obsidian\((-?\d+), (-?\d+), (-?\d+)\)", notes)
    rim = tuple(int(g) for g in call.groups()) if call else None
    true_rim = (0, 10, int(w.pool_z) - 1)
    check("find_lava: the walk stops SHORT of the pool (never inside it, 2+ blocks off)",
          "LAVA FOUND" in notes and w.z <= w.pool_z - 2.0, (w.z, notes[-400:]))
    check("find_lava: the note names a rim cell within 1.5 blocks of the pool's true rim "
          "and the exact make_obsidian call",
          rim is not None and math.dist(rim, true_rim) <= 1.5, (rim, true_rim, notes[-400:]))
    check("find_lava: the sighting tunnelled the wall, saved a frame and counted itself",
          w.broken == 1 and ag.cursor_stats.get("findlava_seen") == 1
          and "_lava.png" in notes and "blocks of tunnel" in notes,
          (w.broken, ag.cursor_stats, notes[-300:]))
    check("find_lava: the sighting says the bucket is in hand and warns off the pool",
          "water_bucket, so the pour can happen now" in notes
          and "Do NOT walk any closer" in notes, notes[-400:])

    w2 = LavaWorld(pool_z=6.0, drop=1.0, w=5.0, d=5.0)
    ag2, notes2 = drive("pit", {"n": 700}, w2)
    call2 = re.search(r"make_obsidian\((-?\d+), (-?\d+), (-?\d+)\)", notes2)
    rim2 = tuple(int(g) for g in call2.groups()) if call2 else None
    check("find_lava: a pool sunk one block below the floor is still named within 1.5 "
          "blocks (its lip is what the ray meets)",
          rim2 is not None and math.dist(rim2, (0, 10, 5)) <= 1.5 and w2.z <= 4.0,
          (rim2, w2.z, notes2[-400:]))

    w3 = LavaWorld(lava=False)
    ag3, notes3 = drive("turn", {"n": 260, "leg": 8}, w3, steps=400)
    check("find_lava: an empty leg turns 90 degrees and keeps searching",
          ag3.cursor_stats.get("findlava_turns", 0) >= 1
          and abs(MW.norm_yaw_delta(90.0 * ag3.cursor_stats["findlava_turns"], w3.yaw)) < 15.0,
          (ag3.cursor_stats, w3.yaw, w3.z))
    check("find_lava: the budget stop says how far it searched and what to do next",
          "No lava came into view" in notes3 and "move 30+ blocks" in notes3.lower()
          and "blocks of tunnel" in notes3, notes3[-400:])
    # On the shrunk tail of a plan (seven 200-tick raw entries under the 1600 cap leave
    # 200) the search does not start and says so; a small model-chosen n is raised.
    w4 = LavaWorld(lava=False)
    ag4, notes4 = drive("shrunk", {}, w4, steps=1700, prefix=[{"action": {}, "repeat": 200}] * 7)
    import re as _re
    m4s = _re.search(r"shrunk to fit the step cap: 600 -> (\d+) ticks", notes4)
    m4r = _re.search(r"NOT STARTED: only (\d+) ticks were available", notes4)
    check("find_lava on the shrunk tail of a plan does not start and says to lead the next plan with it",
          m4s is not None and m4r is not None and m4s.group(1) == m4r.group(1)
          and int(m4r.group(1)) < 250 and "0 blocks of tunnel" in notes4
          and "put find_lava FIRST" in notes4 and ag4.cursor_stats.get("findlava_not_started") == 1,
          (w4.z, m4s and m4s.group(0), m4r and m4r.group(0), notes4[-300:]))
    w5 = LavaWorld(lava=False)
    ag5, notes5 = drive("smalln", {"n": 150, "leg": 8}, w5, steps=400)
    check("find_lava with n=150 is raised to 250 and runs (no refusal)",
          "NOT STARTED" not in notes5 and "up to 250 ticks" in notes5
          and ag5.cursor_stats.get("findlava_not_started", 0) == 0, notes5[-300:])


def test_harvest(root: Path) -> None:
    """harvest_tree against a synthetic world: a trunk 5 blocks ahead, the avatar
    walks until blocked, chops (60 attack ticks in reach break a log), sweeps the
    drop, repeats to the target; leaves in the way are cleared; an unreachable trunk
    ends after two empty chops; a treeless view ends at once. Then the agent's
    marker dispatch runs the same loop."""
    print("\n[harvest] closed-loop wood: approach, chop, collect, give-up rules")
    import math

    from mcu_worldmodel import harvest
    from mcu_worldmodel.procedures import harvest_tree

    def tree_frame(tx: int, width: int = 40) -> np.ndarray:
        fr = np.empty((360, 640, 3), dtype=np.uint8)
        fr[:] = (120, 170, 235)
        fr[260:] = (70, 120, 60)
        if -width <= tx <= 640 + width:
            x0, x1 = max(0, tx - width // 2), min(640, tx + width // 2)
            fr[40:256, x0:x1] = (109, 85, 50)
        return fr

    class World:
        """A trunk 5 blocks ahead: levels 0 (foot) .. height-1. The crosshair's block
        follows the real geometry the macro relies on: eye level at pitch ~0, the foot
        block at ~54 down, the blocks above at -48/-67/-74 from outside, and every
        remaining block straight overhead once the avatar stands in the column. The
        bark column's width follows the distance (a one-block trunk across a ~102-degree
        view, times the ~0.55 recall of the bark mask measured on sim frames), so the
        arrival test reads bark in the face only when the avatar really is at the
        trunk. `ledge_at`: a one-block step at that distance, climbed by a jump."""

        def __init__(self, wall_at=None, leaves=0, foot_wood=True, height=5, terrace=False,
                     ledge_at=None, step2_at=None):
            self.x, self.z, self.yaw, self.pitch = 0.0, 0.0, 25.0, 0.0
            self.ground_y, self.y = 64.0, 64.0
            self.tx, self.tz = 0.0, 5.0
            self.logs, self.other, self.inv = 0.0, 0.0, 0
            # wall_at: a distance the walk cannot cross (or a list: each ground break
            # under a foot probe removes the nearest, the last one stays).
            self.walls = list(wall_at) if isinstance(wall_at, (list, tuple)) else [wall_at]
            self.att, self.leaves, self.drop_in = 0, leaves, None
            self.foot_wood, self.height, self.gone = foot_wood, height, set()
            self.terrace = terrace                    # foot is earth and cannot be entered
            self.ledge, self.climb, self.climbed = ledge_at, 0, False
            self.air, self.climbing = 0, False        # a jump: 12 airborne ticks, or a climb
            # step2_at: a two-block earth step at that distance -- no jump climbs it;
            # the walk passes once its foot AND its upper block are broken.
            self.step2, self.step2_foot, self.step2_open = step2_at, False, False

        def dist(self):
            return math.hypot(self.tx - self.x, self.tz - self.z)

        @property
        def wall(self):
            return self.walls[0]

        def err(self):
            yt = math.degrees(math.atan2(-(self.tx - self.x), self.tz - self.z))
            return ((yt - self.yaw + 180.0) % 360.0) - 180.0

        def frame(self):
            e = self.err()
            if abs(e) >= 50:
                return tree_frame(-999)
            width = int(0.55 * 640 * 2 * math.atan(0.5 / max(self.dist(), 0.45))
                        / math.radians(102))
            return tree_frame(int(round(320 + e * 6.3)), width)

        def level(self):
            d = self.dist()
            if d < 0.5:                                   # inside the column
                if self.pitch < -60:
                    return next((k for k in range(2, self.height) if k not in self.gone), None)
                return None
            p = self.pitch
            if abs(self.err()) < 12 and 1.3 <= d < 2.5 and 40 <= p <= 70:
                return "ground"                       # earth ahead, short of the trunk
            if (abs(self.err()) < 12 and 1.3 <= d < 2.5 and -15 <= p <= 15
                    and self.step2 is not None and self.step2_foot and not self.step2_open):
                return "upper"                        # the step's upper block
            if abs(self.err()) >= 12 or d >= 1.3:
                return None
            for lo, hi, lvl in ((-15, 15, 1), (40, 70, 0), (-55, -40, 2), (-72, -60, 3),
                                (-80, -72, 4)):
                if lo <= p <= hi:
                    return lvl
            return None

        def apply(self, a):
            if "camera" in a:
                self.pitch = max(-90.0, min(90.0, self.pitch + float(a["camera"][0])))
                self.yaw += float(a["camera"][1])
            nx = self.x - math.sin(math.radians(self.yaw)) * 0.28
            nz = self.z + math.cos(math.radians(self.yaw)) * 0.28
            nd = math.hypot(self.tx - nx, self.tz - nz)
            at_ledge = (self.ledge is not None and not self.climbed
                        and nd < self.ledge <= self.dist())
            if a.get("jump") and self.air == 0 and not self.climbing:
                if at_ledge and a.get("forward"):
                    self.climbing, self.climb = True, 0
                else:
                    self.air = 12                     # up and back down, x/z as blocked
            if self.climbing:                         # x/z static, y rising, then free
                self.climb += 1
                self.y = self.ground_y + 0.25 * self.climb
                if self.climb >= 4:
                    self.climbing, self.climbed = False, True
                    self.ground_y = self.y
            else:
                if self.air > 0:
                    self.air -= 1
                self.y = self.ground_y + (1.0 if self.air > 0 else 0.0)
                if a.get("forward") and not at_ledge:
                    enterable = (({1, 2} <= self.gone) if self.terrace
                                 else ({0, 1} <= self.gone))
                    floor = 0.1 if enterable else 0.8
                    shut = (self.step2 is not None and not self.step2_open
                            and nd < self.step2 <= self.dist() + 1e-9)
                    if nd >= floor and (self.wall is None or nd >= self.wall) and not shut:
                        self.x, self.z = nx, nz
            lvl = self.level() if a.get("attack") else None
            if lvl is None or lvl in self.gone or (isinstance(lvl, int) and lvl >= self.height):
                self.att = 0
            elif lvl == "ground":
                self.att += 1
                if self.att >= 15:                    # grass/dirt by hand
                    self.other += 1
                    self.att = 0
                    self.step2_foot = True
                    if len(self.walls) > 1:
                        self.walls.pop(0)             # that step is gone: one wall less
            elif lvl == "upper":
                self.att += 1
                if self.att >= 15:
                    self.other += 1
                    self.att = 0
                    self.step2_open = True
            else:
                self.att += 1
                if lvl == 0 and (not self.foot_wood or self.terrace):
                    if self.att >= 4:                      # dirt breaks fast
                        self.other += 1
                        self.gone.add(0)
                        self.att = 0
                elif lvl == 1 and self.leaves > 0:
                    if self.att % 4 == 0:
                        self.other += 1
                        if self.other % 2 == 0:
                            self.leaves -= 1
                            self.att = 0
                elif self.att >= 60:
                    self.logs += 1
                    self.gone.add(lvl)
                    self.att = 0
                    self.drop_in = 2
            if self.drop_in is not None:
                self.drop_in -= 1
                if self.drop_in <= 0:
                    self.inv += 1
                    self.drop_in = None

    def run(world, logs=3, budget=500):
        hv = harvest.new_state(logs, budget)
        notes, ticks = [], 0
        while ticks < budget + 5:
            a, note = harvest.tick(hv, world.frame(), {"x": world.x, "z": world.z,
                                                       "y": world.y, "pitch": world.pitch,
                                                       "yaw": world.yaw},
                                   world.logs, world.other, world.inv)
            if note:
                notes.append(note)
            if a is None:
                break
            world.apply(a)
            ticks += 1
        return hv, notes, ticks

    w = World()
    hv, notes, ticks = run(w, logs=4)
    check("harvest: four logs from one trunk without taking a step (foot, eye, 2 above)",
          w.inv == 4 and w.gone >= {0, 1, 2, 3} and w.dist() >= 0.8,
          f"inv={w.inv} gone={sorted(w.gone)} dist={w.dist():.2f}")
    check("harvest: within budget, one probe of each kind at the trunk",
          ticks < 420 and hv["empties"] == 0 and hv["probes"] == 0 and not hv["blocked"],
          f"ticks={ticks} empties={hv['empties']} probes={hv['probes']} "
          f"approaches={hv['approaches']}")
    check("harvest: summary note", bool(notes) and "4 log(s) collected" in notes[-1],
          str(notes[-1:]))
    w5 = World(foot_wood=False, height=4)
    hv5, notes5, ticks5 = run(w5, logs=3)
    check("harvest: earth under the trunk, then the blocks above from outside",
          w5.inv == 3 and w5.gone >= {0, 1, 2, 3},
          f"inv={w5.inv} gone={sorted(w5.gone)} ticks={ticks5}")
    w8 = World(terrace=True, height=5)
    hv8, notes8, ticks8 = run(w8, logs=4)
    check("harvest: trunk on a terrace -> the three blocks above from outside",
          w8.inv == 4 and w8.gone >= {1, 2, 3, 4},
          f"inv={w8.inv} gone={sorted(w8.gone)} ticks={ticks8}")
    w9 = World(ledge_at=3.0)
    hv9, notes9, ticks9 = run(w9, logs=4)
    check("harvest: a ledge on the way is climbed by the jump probe, not chopped at",
          w9.inv == 4 and w9.climbed and hv9["probes"] == 0 and hv9["chops"] == 4
          and hv9["empties"] == 0 and hv9["approaches"] == 1,
          f"inv={w9.inv} climbed={w9.climbed} probes={hv9['probes']} "
          f"chops={hv9['chops']} empties={hv9['empties']} ticks={ticks9}")
    w10 = World(wall_at=1.8)
    hv10, notes10, ticks10 = run(w10, logs=2)
    check("harvest: a fence short of the trunk: ground probe, same spot again -> eye "
          "chops from here, then give up",
          w10.inv == 0 and hv10["probes"] == 1 and not hv10["blocked"] and notes10
          and "broke nothing" in notes10[-1] and ticks10 < 300,
          f"inv={w10.inv} probes={hv10['probes']} blocked={hv10['blocked']} "
          f"ticks={ticks10} {notes10[-1:]}")
    far = harvest.far_ladder(115)
    near = harvest.far_ladder(250)
    check("harvest: a 115-px trunk (~3 blocks off) gets the eye then three blocks above "
          "at that distance's angles, no foot; a wide one gets the touching ladder",
          [k for _, _, k in far] == ["eye", "up", "up", "up"]
          and -20 < far[1][1] < -10 and -36 < far[2][1] < -26 and -48 < far[3][1] < -38
          and [k for _, _, k in near] == ["eye", "foot", "up", "up", "up"]
          and near[2][1] == harvest.OUTSIDE_LADDER[0],
          f"far={[(k, round(p, 1)) for _, p, k in far]} near={[k for _, _, k in near]}")
    hvr = harvest.new_state(4, 400)
    hvr["far"], hvr["used"] = True, 400 - harvest.SWEEP_RESERVE + 1
    hvr["ladder"] = [("pitch", -48.0, "up")]
    harvest._next(hvr, 0)
    hvn = harvest.new_state(4, 400)
    hvn["far"], hvn["used"], hvn["ladder"] = True, 100, [("pitch", -48.0, "up")]
    harvest._next(hvn, 0)
    hvt = harvest.new_state(4, 400)
    hvt["far"], hvt["used"] = False, 400 - harvest.SWEEP_RESERVE + 1
    hvt["ladder"] = [("pitch", -48.0, "up")]
    harvest._next(hvt, 0)
    check("harvest: a far ladder keeps the budget for its sweep -- with less than "
          "SWEEP_RESERVE ticks left it sweeps instead of chopping again; with room, "
          "and at a touching trunk, the ladder goes on",
          hvr["state"] == "sweep" and hvn["state"] == "pitch" and hvt["state"] == "pitch"
          and 140 <= harvest.SWEEP_RESERVE <= 160,
          f"far/short={hvr['state']} far/room={hvn['state']} near/short={hvt['state']} "
          f"reserve={harvest.SWEEP_RESERVE}")
    w12 = World(step2_at=2.0)
    hv12, notes12, ticks12 = run(w12, logs=4)
    check("harvest: a two-block earth step is tunnelled (foot probe, then the eye probe) "
          "and the walk goes on to the trunk",
          w12.inv == 4 and w12.step2_open and hv12["probes"] == 1 and not hv12["blocked"],
          f"inv={w12.inv} open={w12.step2_open} probes={hv12['probes']} "
          f"blocked={hv12['blocked']} ticks={ticks12}")
    w11 = World(wall_at=[2.4, 1.8, 1.3, 1.3])
    hv11, notes11, ticks11 = run(w11, logs=2)
    check("harvest: terrain that keeps breaking under the foot probe: three probes, "
          "then an honest chop from where it stands",
          w11.inv == 0 and hv11["blocked"] and hv11["probes"] == 3 and notes11
          and "stopped short" in notes11[-1] and "broke nothing" in notes11[-1],
          f"inv={w11.inv} probes={hv11['probes']} blocked={hv11['blocked']} "
          f"ticks={ticks11} {notes11[-1:]}")
    w7 = World(height=3)
    hv7, notes7, ticks7 = run(w7, logs=4)
    check("harvest: short trunk ends with what it had",
          w7.inv == 3 and notes7 and "used up" in notes7[-1],
          f"inv={w7.inv} ticks={ticks7} {notes7[-1:]}")
    w2 = World(leaves=1)
    hv2, notes2, ticks2 = run(w2, logs=2)
    check("harvest: leaves at eye level cleared then wood", w2.inv == 2 and hv2["clears"] == 1,
          f"inv={w2.inv} clears={hv2['clears']} ticks={ticks2}")
    w3 = World(wall_at=3.0)
    hv3, notes3, ticks3 = run(w3, logs=1)
    check("harvest: unreachable trunk gives up after two empty eye chops",
          w3.inv == 0 and hv3["empties"] == 2 and "broke nothing" in notes3[-1]
          and not hv3["blocked"],
          f"empties={hv3['empties']} probes={hv3['probes']} ticks={ticks3} "
          f"{notes3[-1:]}")
    hv4 = harvest.new_state(1, 100)
    ticks4 = 0
    while ticks4 < 20:
        a, note = harvest.tick(hv4, tree_frame(-999), {"x": 0.0, "z": 0.0, "y": 64.0},
                               0.0, 0.0, 0)
        if a is None:
            break
        ticks4 += 1
    check("harvest: treeless view stops fast", ticks4 <= 6 and note
          and "no trunk detected" in note, f"ticks={ticks4} {note!r}")
    a5, note5 = harvest.tick(harvest.new_state(1, 100), tree_frame(320), None, 0.0, 0.0,
                             0, gui_open=True)
    check("harvest: refuses with a screen open", a5 is None and "SCREEN" in (note5 or ""),
          str(note5))
    # the agent's marker dispatch runs the same loop, JSON-serialisable state and all
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.procedures import act
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "hv", task_text="wood",
                         ledger=MilestoneLedger(cfg, "t"), induction_every=100000,
                         step_cap=50)
    marker = harvest_tree(1, 120)[0]
    json.dumps(marker)                                   # the queue must stay serialisable
    w6 = World()
    hv6 = marker["_harvest"]
    out, n6 = None, 0
    while n6 < 130:
        ag._last_pov = w6.frame()
        ag._cur_pos = {"x": w6.x, "y": 64.0, "z": w6.z, "pitch": w6.pitch, "yaw": w6.yaw}
        ag._log_breaks, ag._other_breaks = w6.logs, w6.other
        ag._cur_inv = {"oak_log": w6.inv} if w6.inv else {}
        out = ag._harvest_tick(hv6, act)
        if out is None:
            break
        w6.apply(out)
        n6 += 1
    check("harvest: agent dispatch collects a log", out is None and w6.inv == 1,
          f"inv={w6.inv} ticks={n6}")
    check("harvest: agent note + stats",
          any("harvest_tree: 1 log(s) collected" in n for n in ag.memory._pending_notes)
          and ag.cursor_stats.get("harvest_runs") == 1, str(ag.memory._pending_notes[-1:]))
    # the mine_log milestone fires on the macro's FIRST log; it must not drop the macro
    ag.queue.clear()
    ag.queue.append((harvest_tree(4, 300)[0], 7))
    ag.queue.append((act(forward=1), 8))
    ag.observe(fake_info(mine_block={"oak_log": 1.0}), 900)
    check("harvest: milestone mid-harvest keeps the queue", len(ag.queue) == 2,
          f"queue={len(ag.queue)}")
    from mcu_worldmodel.procedures import chop_tree as _chop
    ag.queue.clear()
    ag.queue.append((_chop(80, 1)[0], 9))
    ag.ledger = MilestoneLedger(cfg, "t")
    ag.observe(fake_info(mine_block={"oak_log": 2.0}), 901)
    check("harvest: milestone still drops a plain plan", len(ag.queue) == 0,
          f"queue={len(ag.queue)}")


def test_hit_reflex(root: Path) -> None:
    """A hit empties the plan, turns the player to face where it came from before any
    model turn, and the next act turn carries the hit frame beside the current view.
    Slow loss (1 hp at a time) interrupts once per 100 ticks. The shared docs carry one
    depth policy and the charcoal/discard knowledge every arm reads."""
    print("\n[hit-reflex] interrupt, turn around, attach the hit frame; slow damage; docs")
    from mcu_worldmodel.agent import WorldModelAgent

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "hit", task_text="survive",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=100000,
                            step_cap=50)
    script = [{"actions": {"actions": [{"action": {"forward": 1}, "repeat": 40}]},
               "message": "[PLAN]\nwalk"} for _ in range(8)]
    agent.codex = FakeCodex(agent.memory.root, script)
    pov = np.zeros((360, 640, 3), dtype=np.uint8)

    def obs(step, hp, yaw=0.0):
        i = fake_info()
        i["health"] = np.array(float(hp))
        i["location_stats"]["yaw"] = np.array(float(yaw))
        i["pov"] = pov
        return i

    agent.start(obs(0, 20))
    docs = (agent.memory.root / "AGENTS.md").read_text()
    check("docs: one depth policy (y 11-12), the shallow one gone",
          "y 11-12" in docs and "y 45-55" not in docs and "y 12-20 only" not in docs)
    check("docs: charcoal torches, discard_stack, the hit reflex are taught",
          "charcoal" in docs and "discard_stack" in docs
          and "turns you 180 degrees" in docs)
    agent.next_action(obs(1, 20))
    calls0 = agent.codex.calls
    for step in range(1, 4):
        agent.observe(obs(step, 20), step)
        agent.next_action(obs(step, 20))
    check("plan in flight before the hit", bool(agent.queue))
    agent.observe(obs(4, 16), 4)
    check("the hit emptied the plan queue", not agent.queue)
    check("the reflex is armed toward yaw 180",
          agent._reflex is not None
          and abs((agent._reflex["yaw"] - 180.0 + 180.0) % 360.0 - 180.0) < 1e-6,
          str(agent._reflex))
    log = agent.memory.logs_path.read_text()
    check("the note names the damage and the hit frame",
          "took 4 damage" in log and "_hit.png" in log and "turning you 180" in log)
    a = agent.next_action(obs(4, 16))
    check("the reflex tick is a camera turn, no model call",
          a.get("camera") in ([0.0, 30.0], [0.0, -30.0]) and agent.codex.calls == calls0,
          str(a))
    agent.observe(obs(5, 16, yaw=180.0), 5)
    agent.next_action(obs(5, 16, yaw=180.0))
    check("facing the hit, the act turn fired with ONLY the current view attached",
          agent.codex.calls == calls0 + 1 and agent.codex.images_attached == 2
          and "Also attached" not in agent.codex.prompts[-1],
          (agent.codex.calls - calls0, agent.codex.images_attached))
    # A second hit 8 ticks later (lava, fire, a mob still swinging): the escape plan
    # keeps running, no new 180-degree turn, a "still taking damage" note instead.
    from mcu_worldmodel.procedures import act as _act
    agent.queue.clear()
    agent.queue.extend([(_act(left=1, jump=1), 99)] * 20)
    agent.observe(obs(12, 12, yaw=180.0), 12)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("repeat hit keeps the plan and does not turn",
          len(agent.queue) == 20 and agent._reflex is None
          and agent.cursor_stats.get("damage_repeats") == 1
          and "still taking damage -- health 12/20" in log,
          f"queue={len(agent.queue)} reflex={agent._reflex} "
          f"repeats={agent.cursor_stats.get('damage_repeats')}")
    agent.queue.clear()
    # The same repeat hit while the plan stands still (a dig): interrupted like a
    # first hit -- kr30_lb went 16 -> 14 -> 2 -> dead inside one stair_down.
    from mcu_worldmodel.procedures import stair_down as _stair_down
    agent.queue.extend([(_stair_down(7)[-1], 98)])           # an _mfwd cycle head
    agent.observe(obs(20, 9, yaw=180.0), 20)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("repeat hit with a digging head interrupts the plan and says so",
          not agent.queue and agent._reflex is not None
          and agent.cursor_stats.get("damage_repeat_interrupts") == 1
          and "STILL under attack" in log and "stood still" in log,
          f"queue={len(agent.queue)} reflex={agent._reflex} "
          f"{agent.cursor_stats.get('damage_repeat_interrupts')}")
    agent._reflex = None
    agent.queue.clear()
    agent.queue.extend([(_act(left=1, jump=1), 97)] * 10)
    agent.observe(obs(28, 5, yaw=180.0), 28)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("repeat hit at critical health interrupts even an escape plan",
          not agent.queue and "CRITICAL" in log and "pillar up" in log,
          f"queue={len(agent.queue)}")
    agent._reflex = None
    agent.queue.clear()
    # With a placeable block in the HOTBAR, critical health arms the pillar reflex
    # instead of the turn: equip, look straight down, jump-and-place until two blocks
    # are under the feet, each one counted from the measured y. kd34z_wm at 4/20 read
    # the "pillar up" advice and fought the zombie with a stone pickaxe instead.
    def obs_c(step, hp, y=64.0, pitch=0.0):
        i = fake_info(inventory={"cobblestone": 20})
        i["health"] = np.array(float(hp))
        i["location_stats"]["ypos"] = np.array(float(y))
        i["location_stats"]["pitch"] = np.array(float(pitch))
        i["pov"] = pov
        return i
    agent.queue.extend([(_act(left=1, jump=1), 96)] * 10)
    agent.observe(obs_c(36, 2), 36)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("critical hit with cobblestone in the hotbar arms the pillar reflex",
          not agent.queue and agent._reflex is not None
          and agent._reflex.get("kind") == "pillar" and agent._reflex["slot"] == 1
          and "pillaring you up two blocks on cobblestone (hotbar 1)" in log,
          str(agent._reflex))
    a = agent.next_action(obs_c(36, 2))
    check("pillar tick 1 equips the block", a.get("hotbar.1") == 1, str(a))
    a = agent.next_action(obs_c(36, 2))
    check("pillar tick 2 turns the camera down", a.get("camera") == [30.0, 0.0], str(a))
    agent.observe(obs_c(37, 2, pitch=90.0), 37)
    a = agent.next_action(obs_c(37, 2, pitch=90.0))
    check("looking down, the jump starts without use", a.get("jump") == 1 and a.get("use") == 0,
          str(a))
    for _ in range(9):
        a = agent.next_action(obs_c(37, 2, pitch=90.0))
    check("use is held from the third jump tick", a.get("jump") == 1 and a.get("use") == 1,
          str(a))
    for _ in range(6):
        a = agent.next_action(obs_c(37, 2, pitch=90.0))
    check("then it waits to land", a.get("jump") == 0 and a.get("use") == 0, str(a))
    agent.observe(obs_c(38, 2, y=65.0, pitch=90.0), 38)
    agent.next_action(obs_c(38, 2, y=65.0, pitch=90.0))
    check("one block counted from the measured y",
          agent._reflex is not None and agent._reflex["placed"] == 1, str(agent._reflex))
    for _ in range(16):
        agent.next_action(obs_c(38, 2, y=65.0, pitch=90.0))
    agent.observe(obs_c(39, 2, y=66.0, pitch=90.0), 39)
    calls_before = agent.codex.calls
    agent.next_action(obs_c(39, 2, y=66.0, pitch=90.0))
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("two blocks up ends the reflex with the note and hands over the turn",
          agent._reflex is None and "pillared you up 2 block(s) on cobblestone to y 66" in log
          and agent.cursor_stats.get("pillar_reflexes") == 1
          and agent.cursor_stats.get("pillar_blocks") == 2
          and agent.codex.calls == calls_before + 1,
          f"reflex={agent._reflex} calls={agent.codex.calls - calls_before}")
    # A hit while the pillar runs must not replace it with a turn.
    agent._reflex = {"kind": "pillar", "slot": 1, "item": "cobblestone", "phase": "jump",
                     "t": 2, "placed": 0, "target": 2, "tries": 0, "remaining": 60,
                     "y0": 66.0, "y_jump": 66.0}
    agent.queue.clear()
    agent.observe(obs_c(41, 1, y=66.0, pitch=90.0), 41)
    check("a hit during the pillar keeps the pillar reflex",
          agent._reflex is not None and agent._reflex.get("kind") == "pillar"
          and agent._reflex["t"] == 2, str(agent._reflex))
    agent._reflex = None
    agent.queue.clear()
    # Slow loss: 1 hp at a time, three within 100 ticks, well after the hit's window.
    for step, hp in ((110, 16), (130, 15), (150, 14), (170, 13)):
        agent.observe(obs(step, hp), step)

    def alltext():
        return agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    log = alltext()
    check("gradual loss interrupts once with its own wording",
          log.count("lost 3 health over the last 100 ticks") == 1, log[-600:])
    agent.observe(obs(180, 12), 180)
    check("...and not again inside the same 100-tick window",
          log.count("lost") == alltext().count("lost"))
    # Drowning: a gradual loss with water seen lately within reach (the guard's reading,
    # hd13z's hit frames showed only the shaft's dirt) arms the swim-up, not the turn.
    # A fractional y alone (a jump arc, a slab) is not evidence (audit pass 17).
    agent._reflex = None
    agent.queue.clear()

    def obs_w(step, hp, y, frame=None):
        i = obs(step, hp)
        i["location_stats"]["ypos"] = np.array(float(y))
        if frame is not None:
            i["pov"] = frame
        return i
    water_pov0 = np.zeros((360, 640, 3), dtype=np.uint8)
    water_pov0[:] = (62, 84, 130)
    for step, hp in ((300, 12), (320, 12), (340, 12), (360, 12)):
        agent.observe(obs_w(step, hp, 42.85), step)
    check("a fractional y with no water seen is not drowning (a jump arc, a slab): no reflex",
          agent._reflex is None and agent.cursor_stats.get("drown_reflexes", 0) == 0
          and agent._last_water_seen is None, f"{agent._reflex} {agent._last_water_seen}")
    agent.observe(obs_w(396, 12, 60.0, frame=water_pov0), 396)   # the guard runs on step % 4
    agent.observe(obs_w(400, 12, 60.0, frame=water_pov0), 400)
    check("the water guard remembers the reading (step, x, z)",
          agent._last_water_seen is not None and agent._last_water_seen[0] == 400,
          str(agent._last_water_seen))
    for step, hp in ((520, 12), (540, 11), (560, 10), (580, 9)):
        agent.observe(obs_w(step, hp, 60.0), step)
    log = alltext()
    check("a gradual loss with water seen 180 ticks ago within reach arms the DROWN reflex with its own wording",
          agent._reflex is not None and agent._reflex.get("kind") == "drown"
          and "you are DROWNING" in log and "water was within reach 180 ticks ago" in log
          and agent.cursor_stats.get("drown_reflexes") == 1, f"{agent._reflex} {log[-300:]}")
    jumps, y = 0, 60.0
    for k in range(110):
        o = obs_w(581 + k, 9, y)
        agent.observe(o, 581 + k)
        a = agent.next_action(o)
        if a.get("jump") == 1:
            jumps += 1
            y = min(63.0, y + 0.06)      # the surface is 3 blocks up: the rise stops there at tick 50
        if agent._reflex is None:
            break
    log = alltext()
    check("the drown reflex holds jump for 40+ ticks, ends once 12 ticks gain under 0.3 blocks, and the note explains the flooded shaft",
          50 <= jumps <= 64 and agent._reflex is None and "swam you UP 3.0" in log
          and "6+ blocks from any water" in log, (jumps, y, agent._reflex, log[-300:]))
    # On dry land (a false positive) the jump arc repeats every ~12 ticks: the reflex ends
    # at DROWN_TICKS, not at DROWN_MAX (audit pass 18: the still-tick rule never fired).
    agent._reflex = None
    agent.queue.clear()
    agent._reflex = agent._arm_drown({"x": 10.5, "y": 60.0, "z": 20.5, "yaw": 0.0, "pitch": 0.0}, 9.0, 0.0)
    jumps2, y2, vy = 0, 60.0, 0.0
    for k in range(110):
        o = obs_w(700 + k, 9, y2)
        agent.observe(o, 700 + k)
        a = agent.next_action(o)
        if agent._reflex is None:
            break
        if a.get("jump") == 1:
            jumps2 += 1
        if y2 <= 60.0 and a.get("jump") == 1:
            vy = 0.42
        y2 = max(60.0, y2 + vy)
        vy = (vy - 0.08) * 0.98
    check("a drown reflex on dry land (jump arcs, no net rise) ends at DROWN_TICKS, not DROWN_MAX",
          40 <= jumps2 <= 48 and agent._reflex is None, (jumps2, y2, agent._reflex))
    agent._last_water_seen = None
    # Underground with a pickaxe AND a block in the hotbar, a hit at 10 hp or less
    # arms the BUNKER instead of the pillar: kd40z_wm (twice) and kd41z_lb died at
    # y 14-28 on 2026-09-03 after "tried to pillar you up ... but the block did not
    # place" -- a jump under a two-high tunnel ceiling never gains the block of
    # height a pillar needs. Dig two down, cap the cell the feet started in.

    def obs_u(step, hp, y=16.0, pitch=0.0, yaw=0.0, use_cob=0.0):
        i = fake_info(inventory={"stone_pickaxe": 1, "cobblestone": 20},
                      use_item={"cobblestone": use_cob})
        i["health"] = np.array(float(hp))
        i["location_stats"].update({"xpos": np.array(10.5), "ypos": np.array(float(y)),
                                    "zpos": np.array(20.5), "pitch": np.array(float(pitch)),
                                    "yaw": np.array(float(yaw))})
        i["pov"] = pov
        return i
    agent.observe(obs_u(200, 20), 200)                       # a healed baseline
    agent.queue.extend([(_stair_down(7)[-1], 95)])          # a digging head
    agent.observe(obs_u(201, 9), 201)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a hit to 9 hp at y 16 with pickaxe + cobblestone in the hotbar arms the bunker",
          not agent.queue and agent._reflex is not None
          and agent._reflex.get("kind") == "bunker" and agent._reflex["pick"] == 1
          and agent._reflex["slot"] == 2 and agent._reflex["cell"] == [10, 16, 20]
          and agent._reflex["faces"][:2] == ["west", "east"]
          and "BUNKERING you: digging two blocks straight down with the stone_pickaxe "
              "(hotbar 1) and capping the hole with cobblestone (hotbar 2)" in log
          and agent.cursor_stats.get("bunker_reflexes") == 1,
          f"reflex={agent._reflex} log={log[-400:]}")
    a = agent.next_action(obs_u(201, 9))
    check("bunker tick 1 equips the pickaxe", a.get("hotbar.1") == 1, str(a))
    a = agent.next_action(obs_u(201, 9))
    check("bunker tick 2 turns the camera down", a.get("camera") == [30.0, 0.0], str(a))
    agent.observe(obs_u(202, 9, pitch=90.0), 202)
    a = agent.next_action(obs_u(202, 9, pitch=90.0))
    check("looking down, attack is held", a.get("attack") == 1 and not a.get("use"), str(a))
    agent.observe(obs_u(203, 9, y=15.0, pitch=90.0), 203)
    a = agent.next_action(obs_u(203, 9, y=15.0, pitch=90.0))
    check("one block down, attack continues", a.get("attack") == 1, str(a))
    acts = []
    for st in (204, 205, 206):
        agent.observe(obs_u(st, 9, y=14.0, pitch=90.0), st)
        acts.append(agent.next_action(obs_u(st, 9, y=14.0, pitch=90.0)))
    check("two blocks down and steady: attack stops, the block is equipped",
          not acts[0].get("attack") and not acts[1].get("attack")
          and acts[2].get("hotbar.2") == 1 and agent._reflex["phase"] == "equip_block",
          f"{acts} phase={agent._reflex.get('phase') if agent._reflex else None}")
    agent.observe(obs_u(207, 9, y=14.0, pitch=90.0), 207)
    a = agent.next_action(obs_u(207, 9, y=14.0, pitch=90.0))
    cam = a.get("camera") or [0.0, 0.0]
    check("the cap aims up at the west wall of the start cell (pitch up, yaw toward +x)",
          agent._reflex is not None and agent._reflex["phase"] == "cap"
          and cam[0] < -20.0 and cam[1] > 20.0
          and agent._reflex["cap"]["target"] == [10, 16, 20]
          and agent._reflex["cap"]["face"] == "west", f"{a} {agent._reflex}")
    used = False
    steps = 0
    calls_before = agent.codex.calls
    last_acts = []
    while agent._reflex is not None and steps < 40:
        steps += 1
        o = obs_u(207 + steps, 9, y=14.0, pitch=-60.4, yaw=90.0, use_cob=1.0 if used else 0.0)
        agent.observe(o, 207 + steps)
        a = agent.next_action(o)
        last_acts.append(a)
        if a.get("use") == 1:
            used = True
    check("after the cap the pickaxe is re-equipped (the last reflex tick is hotbar 1)",
          len(last_acts) >= 2 and last_acts[-2].get("hotbar.1") == 1, str(last_acts[-3:]))
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("aimed, it clicks use once and the use_item stat closes the reflex with the note",
          used and agent._reflex is None and steps < 40
          and "BUNKERED you: dug 2 blocks down to y 14 and capped the hole with "
              "cobblestone at (10, 16, 20)" in log
          and "look_abs(pitch=-90) + mine_ahead(n=60)" in log
          and "stone_pickaxe is back in your hand" in log
          and agent.cursor_stats.get("bunker_capped") == 1
          and agent.cursor_stats.get("bunker_blocks") == 2
          and agent.codex.calls == calls_before + 1,
          f"used={used} steps={steps} reflex={agent._reflex} "
          f"stats={ {k: v for k, v in agent.cursor_stats.items() if 'bunker' in k} } "
          f"calls={agent.codex.calls - calls_before} log={log[-500:]}")
    # No pickaxe in the hotbar: the bunker cannot dig, so the pillar rule applies as
    # before (here at 9 hp: the 180-degree turn).
    agent.queue.clear()
    agent.queue.extend([(_stair_down(7)[-1], 94)])
    o = obs_u(300, 20)
    agent.observe(o, 300)
    o = obs_u(301, 9)
    o["inventory"][0] = {"type": "air", "quantity": np.array(0)}
    agent.observe(o, 301)
    check("without a pickaxe in the hotbar the hit falls back to the turn",
          agent._reflex is not None and agent._reflex.get("kind") is None
          and agent.cursor_stats.get("bunker_reflexes") == 1, str(agent._reflex))
    agent._reflex = None
    agent.queue.clear()
    # One cap block is enough for the bunker (the pillar still wants two). (40 ticks
    # after the last hit: 10 would read as a melee mob's second swing -> the flee.)
    agent.queue.extend([(_stair_down(7)[-1], 92)])
    o = obs_u(340, 20)
    agent.observe(o, 340)
    o = obs_u(341, 9)
    o["inventory"][1]["quantity"] = np.array(1)
    agent.observe(o, 341)
    check("a single cobblestone in the hotbar still arms the bunker",
          agent._reflex is not None and agent._reflex.get("kind") == "bunker"
          and agent.cursor_stats.get("bunker_reflexes") == 2, str(agent._reflex))
    agent._reflex = None
    agent.queue.clear()
    # Melee: a combat head at critical health FLEES (turn 180, sprint-jump 60 ticks)
    # instead of bunkering -- dm26z_lb fought a zombie from 16 hp and died inside the
    # bunker's dig at 4; a zombie adjacent to the hole cannot be out-dug (s8 run 4).
    agent.queue.clear()
    flee0 = agent.cursor_stats.get("flee_reflexes", 0)     # earlier surface hits without a block ran too
    agent.queue.extend([({"_fight": {"label": "zombie", "budget": 100}}, 91)])
    agent.observe(obs_u(400, 20, yaw=0.0), 400)
    agent.observe(obs_u(401, 5, yaw=0.0), 401)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a combat head hit to 5 hp underground arms the flee, not the bunker",
          not agent.queue and agent._reflex is not None and agent._reflex.get("kind") == "flee"
          and abs(abs(agent._reflex["yaw"]) - 180.0) < 1e-6
          and "SPRINTING you away" in log and agent.cursor_stats.get("flee_reflexes") == flee0 + 1
          and agent.cursor_stats.get("bunker_reflexes") == 2,
          f"{agent._reflex} stats={ {k: v for k, v in agent.cursor_stats.items() if 'flee' in k or 'bunker' in k} } "
          f"log={log[-400:]}")
    a = agent.next_action(obs_u(401, 5, yaw=0.0))
    check("flee tick 1 turns the camera (yaw +30 toward 180)",
          a.get("camera") is not None and abs(a["camera"][1]) == 30.0, str(a))
    agent.observe(obs_u(402, 5, yaw=180.0), 402)
    acts = [agent.next_action(obs_u(402, 5, yaw=180.0)) for _ in range(3)]
    check("facing away, it sprint-jumps forward",
          all(x.get("forward") == 1 and x.get("sprint") == 1 and x.get("jump") == 1 for x in acts),
          str(acts[0]))
    # the avatar moves ~0.35 blocks a tick along +z (yaw 180 faces -z: facing(180) = (0, -1))
    calls_before = agent.codex.calls
    steps = 0
    while agent._reflex is not None and steps < 90:
        steps += 1
        o = obs_u(402 + steps, 5, yaw=180.0)
        o["location_stats"]["zpos"] = np.array(20.5 - 0.35 * steps)
        agent.observe(o, 402 + steps)
        agent.next_action(o)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("after 60 run ticks the flee ends with the distance and hands over the turn",
          agent._reflex is None and 55 <= steps <= 70
          and "turned you around and sprinted 2" in log
          and agent.cursor_stats.get("flee_blocks", 0) >= 18
          and agent.codex.calls == calls_before + 1,
          f"steps={steps} stats={ {k: v for k, v in agent.cursor_stats.items() if 'flee' in k} } "
          f"log={log[-300:]}")
    # A mining head with hits 20 ticks apart: the second hit inside MELEE_CADENCE at
    # or below BUNKER_HP reads as a melee mob at arm's length -> the FLEE, along the
    # knockback (the plan stood still, the avatar was shoved +x -> run toward yaw -90).
    # hd9z_wm (2026-09-04) armed the bunker at 8 hp under 4-damage hits 27 ticks apart
    # and died with the hole one block deep.
    agent.queue.clear()
    agent.queue.extend([(_stair_down(7)[-1], 89)])
    agent.observe(obs_u(500, 20), 500)
    agent.observe(obs_u(520, 17), 520)          # the first hit: 17 > BUNKER_HP, the turn
    check("the first hit (17 hp) is the turn, not a bunker or a flee",
          agent._reflex is not None and agent._reflex.get("kind") is None
          and agent.cursor_stats.get("bunker_reflexes") == 2,
          f"{agent._reflex} stats={ {k: v for k, v in agent.cursor_stats.items() if 'flee' in k or 'bunker' in k} }")
    agent._reflex = None
    agent.queue.extend([(_stair_down(7)[-1], 89)]) if not agent.queue else None
    from mcu_worldmodel import macros_world as MW
    o = obs_u(540, 14)
    o["location_stats"]["xpos"] = np.array(11.0)    # shoved +0.5 x by the swing
    agent.observe(o, 540)
    check("the second hit 20 ticks later at 14 hp arms the FLEE away from the shove (yaw -90), not the bunker",
          agent._reflex is not None and agent._reflex.get("kind") == "flee"
          and abs(MW.norm_yaw_delta(-90.0, float(agent._reflex["yaw"]))) < 1e-6
          and agent.cursor_stats.get("flee_reflexes") == flee0 + 2
          and agent.cursor_stats.get("bunker_reflexes") == 2
          and "a melee mob is at arm's length" in alltext()
          and "away from the shove" in alltext(),
          f"{agent._reflex} stats={ {k: v for k, v in agent.cursor_stats.items() if 'flee' in k or 'bunker' in k} } {alltext()[-300:]}")
    agent._reflex = None
    agent.queue.clear()
    # A melee hit while the bunker is still digging ends the bunker and flees.
    agent.queue.extend([(_stair_down(7)[-1], 89)])
    agent.observe(obs_u(580, 20), 580)
    o = obs_u(581, 13); o["location_stats"]["xpos"] = np.array(10.5)
    agent.observe(o, 581)
    check("a lone hit to 13 hp at y 16 arms the bunker (BUNKER_HP 14)",
          agent._reflex is not None and agent._reflex.get("kind") == "bunker"
          and agent.cursor_stats.get("bunker_reflexes") == 3, str(agent._reflex))
    agent.next_action(o)
    o = obs_u(596, 9); o["location_stats"]["xpos"] = np.array(10.5)
    agent.observe(o, 596)
    log = alltext()
    check("a second hit 15 ticks into the dig ends the bunker ('kept hitting into the dig') and arms the flee",
          agent._reflex is not None and agent._reflex.get("kind") == "flee"
          and "a melee attacker kept hitting into the dig" in log
          and agent.cursor_stats.get("flee_reflexes") == flee0 + 3, f"{agent._reflex} {log[-300:]}")
    agent._reflex = None
    agent.queue.clear()
    # A flee whose run gains no ground (a dead end) ends early with the other note.
    agent.queue.extend([({"_fight": {"label": "zombie", "budget": 100}}, 88)])
    agent.observe(obs_u(600, 20, yaw=0.0), 600)
    agent.observe(obs_u(601, 4, yaw=0.0), 601)
    check("a combat head hit to 4 hp arms the flee again",
          agent._reflex is not None and agent._reflex.get("kind") == "flee"
          and agent.cursor_stats.get("flee_reflexes") == flee0 + 4, str(agent._reflex))
    agent.observe(obs_u(602, 4, yaw=180.0), 602)
    steps = 0
    while agent._reflex is not None and steps < 90:
        steps += 1
        o = obs_u(602 + steps, 4, yaw=180.0)          # never moves
        agent.observe(o, 602 + steps)
        agent.next_action(o)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a flee that gains no ground in 20 ticks stops with 'the way is blocked'",
          agent._reflex is None and steps < 30 and "the way is blocked" in log
          and "find another way out NOW" in log, f"steps={steps} {log[-200:]}")
    agent._reflex = None
    agent.queue.clear()
    # On the surface (y 64) the same hit keeps the pillar / turn rule.
    agent.queue.extend([(_stair_down(7)[-1], 93)])
    agent.observe(obs_u(700, 20, y=64.0), 700)
    agent.observe(obs_u(701, 9, y=64.0), 701)
    check("at y 64 a hit to 9 hp does not bunker",
          agent._reflex is not None and agent._reflex.get("kind") is None
          and agent.cursor_stats.get("bunker_reflexes") == 3, str(agent._reflex))
    agent._reflex = None
    agent.queue.clear()
    # With a sword in the hotbar the melee cadence underground is answered by FIGHTING
    # BACK, facing the shove's origin, not by the sprint (hd21z_wm died running up its
    # own staircase with a diamond sword in hand); the run takes over at CRITICAL_HP.
    def obs_s(step, hp, x=10.5):
        o = obs_u(step, hp)
        o["inventory"][3] = {"type": "diamond_sword", "quantity": np.array(1)}
        o["location_stats"]["xpos"] = np.array(float(x))
        return o
    agent.queue.extend([(_stair_down(7)[-1], 87)])
    agent.observe(obs_s(800, 20), 800)
    agent.observe(obs_s(801, 13), 801)
    check("with a sword in the hotbar the FIRST hit to 13 hp still bunkers (the attacker is unknown)",
          agent._reflex is not None and agent._reflex.get("kind") == "bunker", str(agent._reflex))
    agent.next_action(obs_s(801, 13))
    agent.observe(obs_s(816, 9, x=11.0), 816)              # shoved +0.5 x by the swing
    log = alltext()
    check("the second hit 15 ticks later arms the FIGHTBACK facing the shove's origin (yaw 90), ending the bunker",
          agent._reflex is not None and agent._reflex.get("kind") == "fightback"
          and abs(MW.norm_yaw_delta(90.0, float(agent._reflex["yaw"]))) < 1e-6
          and agent._reflex["item"] == "diamond_sword" and agent._reflex["slot"] == 4
          and "FIGHTING BACK" in log and "diamond_sword (hotbar 4)" in log
          and "where the shove came from" in log
          and "a melee attacker kept hitting into the dig" in log
          and agent.cursor_stats.get("fightback_reflexes") == 1,
          f"{agent._reflex} {log[-400:]}")
    a1 = agent.next_action(obs_s(816, 9, x=11.0))
    check("fightback tick 1 equips the sword (hotbar 4)", a1.get("hotbar.4") == 1, str(a1))
    a2 = agent.next_action(obs_s(816, 9, x=11.0))
    check("fightback tick 2 turns toward yaw 90 (camera +30)",
          a2.get("camera") is not None and a2["camera"][1] == 30.0, str(a2))
    o = obs_s(817, 9, x=11.0); o["location_stats"]["yaw"] = np.array(90.0)
    agent.observe(o, 817)
    acts = [agent.next_action(o) for _ in range(18)]
    check("facing it, the fightback swings (one attack tick per 9: the fight macro's charge cadence) and steps in at the start",
          sum(1 for x in acts if x.get("attack") == 1) == 2
          and any(x.get("forward") == 1 for x in acts)
          and agent._reflex is not None and agent._reflex.get("phase") == "fight", str(acts))
    o = obs_s(830, 4, x=11.5); o["location_stats"]["yaw"] = np.array(90.0)
    agent.observe(o, 830)                                    # a third hit, to critical
    log = alltext()
    check("a hit to 4 hp during the fightback ends it ('health critical') and the FLEE takes over",
          agent._reflex is not None and agent._reflex.get("kind") == "flee"
          and "fought back with the diamond_sword" in log and "health critical" in log,
          f"{agent._reflex} {log[-300:]}")
    agent._reflex = None
    agent.queue.clear()
    # The End: no run, no bunker, no pillar -- the island's edge is the void (stage s10
    # on the merged tree, 2026-09-04: the flee sprinted the avatar to y -272). The runner
    # only turns to face the hit, and says so.
    agent.queue.clear()
    agent.observe(obs_u(800, 20, y=64.0), 800)
    agent._dimension = "the End"
    f0 = agent.cursor_stats.get("flee_reflexes", 0); b0 = agent.cursor_stats.get("bunker_reflexes", 0)
    p0 = agent.cursor_stats.get("pillar_reflexes", 0)
    agent.queue.extend([({"_fight": {"label": "dragon", "budget": 100}}, 91)])
    agent.observe(obs_u(801, 5, y=64.0), 801)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("in the End a combat head hit to 5 hp only turns the avatar (no flee/bunker/pillar)",
          not agent.queue and agent._reflex is not None and "kind" not in agent._reflex
          and agent._reflex.get("remaining") == 16
          and agent.cursor_stats.get("flee_reflexes", 0) == f0
          and agent.cursor_stats.get("bunker_reflexes", 0) == b0
          and agent.cursor_stats.get("pillar_reflexes", 0) == p0
          and "in the End it never sprints or pillars you" in log,
          f"{agent._reflex} log={log[-300:]}")
    agent._reflex = None
    o = obs_u(802, 20, y=64.0)
    o["location_stats"]["xpos"] = np.array(float(o["location_stats"]["xpos"]) + 300.0)
    agent.observe(o, 802)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a death (coordinate jump at full health) puts the dimension back to the Overworld",
          agent._dimension == "the Overworld" and "YOU DIED" in log, f"{agent._dimension} {log[-200:]}")
    agent._reflex = None
    agent.queue.clear()

    # Lava: a hit while lava fills the lower view is the lava, not a mob -- douse with
    # the hotbar water bucket, step back, level the view (hd5z_wm, 2026-09-04).
    from mcu_worldmodel import vision
    lava_pov = np.zeros((360, 640, 3), dtype=np.uint8)
    lava_pov[:] = (60, 60, 60)
    lava_pov[150:, :] = (220, 90, 20)                   # r 220, g/r 0.41, b/r 0.09: the band
    check("the synthetic lava frame reads as lava in the lower view",
          vision.lava_fraction(lava_pov) >= 0.3, vision.lava_fraction(lava_pov))
    fire_pov = np.zeros((360, 640, 3), dtype=np.uint8)
    fire_pov[:] = (60, 60, 60)
    fire_pov[240:, :] = (250, 150, 30)                  # flames: r 250, g/r 0.6, b/r 0.12
    check("the synthetic burning frame reads as fire, not as lava",
          vision.fire_fraction(fire_pov) >= 0.3 and vision.lava_fraction(fire_pov) < 0.06,
          (vision.fire_fraction(fire_pov), vision.lava_fraction(fire_pov)))
    check("an ordinary grey frame reads as neither",
          vision.fire_fraction(np.full((360, 640, 3), 60, np.uint8)) == 0.0)
    def obs_l(step, hp, bucket=True, poured=False, z=20.5, frame=None):
        o = obs_u(step, hp, y=12.0)
        o["location_stats"]["zpos"] = np.array(float(z))
        if frame is not None:
            o["pov"] = frame
        if bucket:
            o["inventory"][8] = {"type": "water_bucket", "quantity": 1}
        if poured:
            o["inventory"][8] = {"type": "bucket", "quantity": 1}
            o["use_item"]["water_bucket"] = np.array(1.0)
        return o
    agent.observe(obs_l(900, 20), 900)
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    l0 = agent.cursor_stats.get("lava_reflexes", 0)
    agent.observe(obs_l(901, 16, frame=lava_pov), 901)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a 4-damage hit with lava in the lower view arms the lava reflex with the hotbar water bucket",
          not agent.queue and agent._reflex is not None and agent._reflex.get("kind") == "lava"
          and agent._reflex.get("wb") == 9 and agent.cursor_stats.get("lava_reflexes") == l0 + 1
          and "the damage is the LAVA" in log and "DOUSING you" in log,
          f"{agent._reflex} log={log[-300:]}")
    a = agent.next_action(obs_l(901, 16))
    check("lava tick 1 selects the water bucket (hotbar 9)", a.get("hotbar.9") == 1, str(a))
    acts = []
    for k in range(3):
        acts.append(agent.next_action(obs_l(902 + k, 16, z=20.5)))
    check("then the camera pitches down by 30 a tick",
          all(x.get("camera") is not None and x["camera"][0] == 30.0 for x in acts), str(acts))
    o = obs_l(905, 16); o["location_stats"]["pitch"] = np.array(90.0)
    agent.observe(o, 905)
    a = agent.next_action(o)
    check("looking down, it pours (use)", a.get("use") == 1, str(a))
    backs = 0
    z = 20.5
    for k in range(40):
        o = obs_l(906 + k, 16, poured=True, z=z); o["location_stats"]["pitch"] = np.array(90.0 if k < 20 else 10.0)
        agent.observe(o, 906 + k)
        a = agent.next_action(o)
        if a.get("back") == 1 and a.get("jump") == 1:
            backs += 1
            z -= 0.2
        if agent._reflex is None:
            break
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("it steps back 14 ticks with jump and ends with the DOUSED note and the counters",
          backs == 14 and agent._reflex is None and "DOUSED you" in log
          and "health 16/20. If you are still burning" in log
          and "never from inside it" in log
          and agent.cursor_stats.get("lava_doused") == 1
          and agent.cursor_stats.get("lava_escape_blocks", 0) >= 2,
          f"backs={backs} stats={ {k: v for k, v in agent.cursor_stats.items() if 'lava' in k} } log={log[-300:]}")
    # without a bucket: the step back only, and the note says so
    agent.queue.clear(); agent._reflex = None
    agent.observe(obs_l(960, 16, bucket=False), 960)
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    agent.observe(obs_l(961, 12, bucket=False, frame=lava_pov), 961)
    check("without a water bucket the lava reflex arms in the step-back phase",
          agent._reflex is not None and agent._reflex.get("kind") == "lava"
          and agent._reflex.get("wb") is None and agent._reflex.get("phase") == "out", str(agent._reflex))
    a = agent.next_action(obs_l(961, 12, bucket=False))
    check("its first tick already steps back", a.get("back") == 1 and a.get("jump") == 1, str(a))
    z = 20.5
    for k in range(70):
        o = obs_l(962 + k, 12, bucket=False, z=z); agent.observe(o, 962 + k)
        a = agent.next_action(o)
        if a.get("back") == 1:
            z -= 0.05                                   # crawling in lava: 20 ticks per block
        if agent._reflex is None:
            break
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("the no-bucket escape says so in its note", "had no water bucket in your hotbar" in log, log[-250:])
    # in the Nether water evaporates: the bucket is not used even when carried
    agent.queue.clear(); agent._reflex = None
    agent.observe(obs_l(990, 16), 990)
    agent._dimension = "the Nether"
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    agent.observe(obs_l(991, 12, frame=fire_pov), 991)   # flames only: the fire trigger
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("a burning frame (no lava in view) arms the lava reflex too, and in the Nether it skips the bucket",
          agent._reflex is not None and agent._reflex.get("kind") == "lava" and agent._reflex.get("wb") is None
          and "you are BURNING" in log, f"{agent._reflex} {log[-200:]}")
    for k in range(60):
        o = obs_l(992 + k, 12); agent.observe(o, 992 + k)
        agent.next_action(o)
        if agent._reflex is None:
            break
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("the Nether note says the bucket was skipped for the evaporation, not missing",
          agent._reflex is None and "water evaporates in the Nether" in log
          and "had no water bucket" not in log[-600:], log[-300:])
    # a lake ahead (the bridge level) is not the trigger: a hit there is a mob's
    lake_pov = np.zeros((360, 640, 3), dtype=np.uint8)
    lake_pov[:] = (60, 60, 60)
    lake_pov[205:225, :] = (220, 90, 20)
    lk = vision.lava_fraction(lake_pov)
    lf = vision.fire_fraction(lake_pov)
    agent._dimension = "the Overworld"
    agent._reflex = None
    agent.queue.clear()
    agent.observe(obs_l(1060, 16), 1060)
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    agent.observe(obs_l(1061, 12, frame=lake_pov), 1061)
    check("a hit with a lake ahead (lava 0.05-0.15 of the view, flames below 0.16) does not arm the lava escape",
          0.05 <= lk < agent.LAVA_ESCAPE_FRAC and lf < vision.FIRE_FRAC_MIN
          and (agent._reflex is None or agent._reflex.get("kind") != "lava"),
          f"lava={lk:.3f} fire={lf:.3f} reflex={agent._reflex}")
    # in the End the frames are never read for lava (no lava there; the void is behind)
    agent._reflex = None
    agent.queue.clear()
    agent.observe(obs_l(1070, 16), 1070)
    agent._dimension = "the End"
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    agent.observe(obs_l(1071, 12, frame=lava_pov), 1071)
    check("in the End a lava-coloured frame does not arm the lava escape (the turn instead)",
          agent._reflex is not None and agent._reflex.get("kind") != "lava"
          and agent.cursor_stats.get("end_turns", 0) >= 1, str(agent._reflex))
    agent._dimension = "the Overworld"
    # dig_down beside water seen lately is refused (hd13z's flooded shaft)
    agent._reflex = None
    agent.queue.clear()
    water_pov = np.zeros((360, 640, 3), dtype=np.uint8)
    water_pov[:] = (62, 84, 130)
    agent.observe(obs_l(1100, 20, frame=water_pov), 1100)
    check("the water guard remembers the pond frame (step 1100, this position)",
          agent._last_water_seen is not None and agent._last_water_seen[0] == 1100,
          str(agent._last_water_seen))
    agent.queue.append(({"_dig": {"remaining": 40, "until_y": None}, "_cost": 40}, 96))
    a = agent.next_action(obs_l(1101, 20))
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("dig_down within 6 blocks of water seen in the last 200 ticks is refused with the flood note",
          not agent.queue and "dig_down REFUSED" in log and "FLOODS" in log
          and agent.cursor_stats.get("dig_water_refusals") == 1, f"{a} {log[-300:]}")
    agent._last_water_seen = None
    # the lava preempts a bunker in progress: the dig opened into lava (40+ ticks after
    # the lake block's hit: a hit inside MELEE_CADENCE of it would be the flee)
    agent._reflex = None
    agent.queue.clear()
    agent.observe(obs_l(1140, 20), 1140)
    agent.queue.extend([(_stair_down(7)[-1], 95)])
    agent.observe(obs_l(1141, 9), 1141)
    check("a hit to 9 hp at y 12 (no lava in view) arms the bunker",
          agent._reflex is not None and agent._reflex.get("kind") == "bunker", str(agent._reflex))
    agent.next_action(obs_l(1141, 9))
    agent.observe(obs_l(1142, 5, frame=lava_pov), 1142)
    log = agent.memory.logs_path.read_text() + "\n".join(agent.memory._pending_notes)
    check("the next hit with lava in the view ends the bunker and arms the lava escape",
          agent._reflex is not None and agent._reflex.get("kind") == "lava"
          and "the dig met lava" in log and "the damage is the LAVA" in log,
          f"{agent._reflex} {log[-300:]}")
    agent._reflex = None
    agent.queue.clear()


def test_dark_tunnel(root: Path) -> None:
    """The ore watch measures the view's brightness; a mining macro that ran in the
    dark says so in its finish note; mining coal without torches draws one nudge."""
    print("\n[dark-tunnel] brightness sampling, the blind-mining line, the torch nudge")
    from mcu_worldmodel.agent import WorldModelAgent
    cfg = [{"event": "mine_block", "identity": "mine_iron_ore", "objects": ["iron_ore"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "dark", task_text="iron",
                            ledger=MilestoneLedger(cfg, "iron"),
                            induction_every=0, step_cap=400)
    agent.codex = FakeCodex(agent.memory.root, [])
    dark = np.full((360, 640, 3), 14, dtype=np.uint8)
    lit = np.full((360, 640, 3), 70, dtype=np.uint8)
    i = fake_info()
    i["pov"] = dark
    agent.start(i)
    agent._last_pov = dark                  # observe() sets it; start() does not
    marker: dict = {}
    for _ in range(24):
        agent._ore_flag(marker)
    check("the ore watch samples brightness every 8th tick",
          marker.get("lum_n") == 3 and abs(marker["lum_sum"] / 3 - 14.0) < 0.5, str(marker))
    line = agent._dark_line(marker)
    check("a dark run gets the blind-mining line and the mine_dark stat",
          "DARK throughout (mean brightness 14/255)" in line and "1 coal + 1 stick" in line
          and agent.cursor_stats.get("mine_dark") == 1, line)
    agent._last_pov = lit
    marker2: dict = {}
    for _ in range(24):
        agent._ore_flag(marker2)
    check("a lit run gets no line", agent._dark_line(marker2) == ""
          and marker2.get("lum_n") == 3, str(marker2))
    check("fewer than three samples: no verdict", agent._dark_line({"lum_sum": 10.0, "lum_n": 2}) == "")
    # the coal nudge: once, only without torches, not again within 3000 steps
    def obs(step, coal, torch=0):
        j = fake_info(inventory={"torch": torch} if torch else None, mine_block={"coal_ore": coal})
        j["pov"] = lit
        return j
    agent.observe(obs(10, 0), 10)
    agent.observe(obs(11, 1), 11)
    notes = " | ".join(agent.memory._pending_notes)
    check("mining coal with no torch carried draws the torch nudge",
          "coal in hand and no torches" in notes and agent.cursor_stats.get("torch_nudges") == 1,
          notes[-200:])
    agent.observe(obs(12, 2), 12)
    check("a second coal within 3000 steps does not repeat it",
          agent.cursor_stats.get("torch_nudges") == 1)
    agent.observe(obs(4000, 3, torch=4), 4000)
    check("with torches carried the nudge stays quiet",
          agent.cursor_stats.get("torch_nudges") == 1)
    agent.observe(obs(4001, 4), 4001)
    check("3000 steps later, coal without torches nudges again",
          agent.cursor_stats.get("torch_nudges") == 2)
    j = fake_info(craft_item={"stone_pickaxe": 1})
    j["pov"] = lit
    agent.observe(j, 4002)
    notes = " | ".join(agent.memory._pending_notes)
    from mcu_worldmodel.macros_gui import torch_recipe as _torch_recipe
    check("craft(torch) with charcoal and no coal in hand uses the charcoal recipe",
          _torch_recipe("torch", fake_info(inventory={"charcoal": 3, "stick": 4})) == "charcoal_torch"
          and _torch_recipe("torch", fake_info(inventory={"coal": 1, "charcoal": 3})) == "torch"
          and _torch_recipe("torch", fake_info(inventory={"stick": 4})) == "torch"
          and _torch_recipe("planks", fake_info(inventory={"charcoal": 3})) == "planks")
    from mcu_worldmodel.cursor import CursorState as _CS
    cs = _CS()
    cs.opened({"charcoal": 2, "stick": 3})
    gone = cs.crafted("torch", 4)
    cs2 = _CS()
    cs2.opened({"coal": 2, "charcoal": 2, "stick": 3})
    gone2 = cs2.crafted("torch", 4)
    cs3 = _CS()
    cs3.opened({"charcoal": 2})                # the sticks were made in this session
    gone3 = cs3.crafted("torch", 4)
    check("a torch craft writes off charcoal when no coal was on the baseline (and coal "
          "when it was; and with the sticks made in-session)",
          gone == {"charcoal": 1, "stick": 1} and gone2 == {"coal": 1, "stick": 1}
          and gone3 == {"charcoal": 1},
          f"{gone} {gone2} {gone3}")
    check("a stone pickaxe crafted with no sword carried draws the sword nudge once",
          "stone sword is 2 cobblestone + 1 stick" in notes
          and agent.cursor_stats.get("sword_nudges") == 1, notes[-160:])
    agent.observe(j, 4003)
    check("...and not twice", agent.cursor_stats.get("sword_nudges") == 1)
    j2 = fake_info(inventory={"stone_sword": 1}, craft_item={"stone_pickaxe": 1})
    j2["pov"] = lit
    agent2 = WorldModelAgent(workspace=root / "dark2", task_text="iron",
                             ledger=MilestoneLedger(cfg, "iron"),
                             induction_every=0, step_cap=400)
    agent2.codex = FakeCodex(agent2.memory.root, [])
    agent2.start(fake_info())
    agent2.observe(j2, 5)
    check("with a sword carried there is no nudge", not agent2.cursor_stats.get("sword_nudges"))


def test_harness_nodes(root: Path) -> None:
    """Harness-generated beliefs: placed sites (merged when re-placed, retired when
    picked up), hazards (hits merged by place and time, deaths), coverage since the
    last ore, location verification by standing there, and the approach verdict pin."""
    print("\n[harness-nodes] sites, hazards, coverage, visits, approach verdict")
    from mcu_worldmodel import prompts, sites
    from mcu_worldmodel.agent import WorldModelAgent

    cfg = [{"event": "mine_block", "identity": "mine_iron_ore", "objects": ["iron_ore"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "hn", task_text="iron",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=100000,
                            step_cap=50)
    agent.codex = FakeCodex(agent.memory.root, [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "[PLAN]\nwalk"} for _ in range(6)])
    pov = np.zeros((360, 640, 3), dtype=np.uint8)

    def obs(x, y, z, hp=20.0, **stats):
        i = fake_info(**stats)
        i["location_stats"].update({"xpos": np.array(float(x)), "ypos": np.array(float(y)),
                                    "zpos": np.array(float(z)), "yaw": np.array(90.0)})
        i["health"] = np.array(float(hp))
        i["pov"] = pov
        return i

    agent.start(obs(0, 64, 0))
    agent.observe(obs(0, 64, 0, use_item={"furnace": 1}), 10)
    n = agent.graph.nodes.get("site_furnace_10")
    check("a placed furnace becomes a location node with its coordinates",
          n is not None and n.kind == "location" and "(0, 64, 0)" in n.statement
          and n.confidence == 0.9, str(n))
    agent.observe(obs(1, 64, 1, use_item={"furnace": 2}), 20)
    check("re-placing within 4 blocks merges into the same site",
          "site_furnace_20" not in agent.graph.nodes
          and "placed 2 times" in agent.graph.nodes["site_furnace_10"].statement)
    agent.observe(obs(30, 64, 0, use_item={"furnace": 3}), 30)
    check("a placement 30 blocks away is a new site", "site_furnace_30" in agent.graph.nodes)
    agent.observe(obs(30, 64, 0, use_item={"furnace": 3}, mine_block={"furnace": 1}), 40)
    n2 = agent.graph.nodes["site_furnace_30"]
    check("mining the furnace retires the nearest site", n2.status == "stale"
          and "PICKED UP" in n2.statement, str(n2))
    # Coverage: two strips at y12, then an iron ore resets it.
    agent.observe(obs(30, 12, 0, use_item={"furnace": 3}, mine_block={"furnace": 1}), 50)
    agent._record_coverage("strip_mine", (30.0, 12.0, 0.0), 40, 14.0, 250)
    agent._record_coverage("strip_mine", (44.0, 12.0, 0.0), 35, 12.0, 250)
    cov = agent.graph.nodes["coverage_since_ore"]
    check("coverage node sums the finished macros",
          "2 mining macro(s), 75 blocks broken, 26 blocks advanced" in cov.statement
          and "y12 x2" in cov.statement and "no iron ore mined yet" in cov.statement,
          cov.statement)
    agent.observe(obs(56, 12, 0, use_item={"furnace": 3}, mine_block={"furnace": 1,
                                                                    "iron_ore": 1}), 60)
    cov = agent.graph.nodes["coverage_since_ore"]
    check("an iron ore mined resets coverage", "since the last iron ore (step 60)"
          in cov.statement and "no mining macro" in cov.statement, cov.statement)
    vein = agent.graph.nodes.get("vein_iron_ore_60")
    check("an ore block mined is a confirmed vein node at the position",
          vein is not None and vein.kind == "location" and vein.status == "confirmed"
          and "(56, 12, 0)" in vein.statement, str(vein))
    agent.observe(obs(58, 12, 1, use_item={"furnace": 3},
                      mine_block={"furnace": 1, "iron_ore": 2}), 65)
    check("a second ore block within 4 blocks merges into the vein (2 blocks here)",
          "vein_iron_ore_65" not in agent.graph.nodes
          and "2 blocks here so far" in agent.graph.nodes["vein_iron_ore_60"].statement)
    # Hazards: two hits at one spot merge; a death is its own confirmed node.
    hp = 20.0
    agent.observe(obs(56, 12, 0, hp=16.0, use_item={"furnace": 3},
                      mine_block={"furnace": 1, "iron_ore": 1}), 70)
    agent._reflex = None
    agent.observe(obs(57, 12, 0, hp=12.0, use_item={"furnace": 3},
                      mine_block={"furnace": 1, "iron_ore": 1}), 200)
    hits = [n for n in agent.graph.nodes.values() if n.id.startswith("hazard_hit_")]
    check("two hits near one spot within 400 steps are one hazard",
          len(hits) == 1 and "2 times" in hits[0].statement and "8 hp" in hits[0].statement,
          [h.statement for h in hits])
    agent.observe(obs(-3009.5, 71, -5572.5, hp=20.0, use_item={"furnace": 3},
                      mine_block={"furnace": 1, "iron_ore": 1}), 210)
    check("a death is a confirmed hazard node at the death point",
          "hazard_death_210" in agent.graph.nodes
          and "(57, 12, 0)" in agent.graph.nodes["hazard_death_210"].statement
          and agent.graph.nodes["hazard_death_210"].status == "confirmed")
    # Visits: a model-written place is marked when the player stands there.
    agent.graph.add_or_update(id="vein_east", kind="location", confidence=0.6,
                              statement="an iron vein at (100, 12, 200)", step=210)
    agent.observe(obs(101, 12, 201, hp=20.0, use_item={"furnace": 3},
                      mine_block={"furnace": 1, "iron_ore": 1}), 220)
    flags = agent.discipline.flags(220)
    check("standing at the coordinates marks the node visited",
          flags.get("vein_east") == "visited at step 220", str(flags))
    view = agent.graph.to_prompt_summary(12, flags, now_step=220)
    check("the view renders the visit", "visited at step 220" in view)
    block = sites.render_block(agent.graph, {"x": 101.0, "y": 12.0, "z": 201.0}, 220,
                               agent.discipline.visits)
    check("the harness block lists the live site, hazards and coverage",
          "a furnace was placed" in block and "DIED" in block
          and "Harness coverage" in block and "PICKED UP" not in block
          and "52 above you" in block, block)
    check("site and hit nodes carry frame pointers the block renders",
          any(e.startswith("frame: ") and e.endswith("_site.png")
              for e in agent.graph.nodes["site_furnace_10"].evidence)
          and any(e.startswith("frame: ") and e.endswith("_hit.png")
                  for e in hits[0].evidence)
          and "frame: episodes/" in block, block)
    check("the frame index tool is installed in the worldmodel workspace",
          (agent.memory.root / "tools" / "frames.py").exists())
    import subprocess
    # visited.csv has the observed positions; the tool joins them to the frames.
    res = subprocess.run([sys.executable, "tools/frames.py", "--near", "0", "0",
                          "--radius", "3", "--sheet", "sheet.png"],
                         cwd=agent.memory.root, capture_output=True, text=True)
    check("frames.py lists the frames saved at a place and tiles them",
          res.returncode == 0 and "step_0010_site.png" in res.stdout
          and (agent.memory.root / "sheet.png").exists(),
          res.stdout[-300:] + res.stderr[-300:])
    # Approach verdict pinned from rules.md.
    (agent.memory.root / "world_model" / "rules.md").write_text(
        "APPROACH: KEEP strip-mining y12 heading 90; switch if no sighting by step 900.\n"
        "- never dig straight down [x2]\n", encoding="utf-8")
    prompt = agent._turn_prompt(obs(101, 12, 201))
    check("the act prompt pins the approach verdict and the harness facts",
          "Approach verdict from your last induction: APPROACH: KEEP" in prompt
          and "Harness facts in your graph" in prompt, prompt[-1500:])
    ind = prompts.induction_prompt(task_text="t", progress_block="", per_doc_chars=2000)
    check("the induction pass is asked for approach, sunk cost, alternatives, verdict",
          "SUNK COST" in ind and "Alternatives:" in ind and "`APPROACH:`" in ind)


def test_relay_semantics(root: Path) -> None:
    """An inherited graph is repriced by node type at episode start: built sites go
    stale, veins stay confirmed and say the ore is back, hits go stale, deaths keep the
    terrain, coverage is dropped."""
    print("\n[relay] inherited harness nodes are repriced by type")
    from mcu_worldmodel.agent import WorldModelAgent

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ws = root / "relay"
    parent = WorldModelAgent(workspace=ws, task_text="t", ledger=MilestoneLedger(cfg, "t"),
                             induction_every=0)
    g = parent.graph
    g.add_or_update(id="site_furnace_10", kind="location", confidence=0.9,
                    statement="Harness: a furnace was placed at step 10 within ~2 blocks of (0, 64, 0).",
                    step=10)
    g.add_or_update(id="vein_iron_ore_20", kind="location", confidence=0.95,
                    status="confirmed",
                    statement="Harness: iron ore mined at step 20 within ~3 blocks of (5, 12, 5) (3 blocks here so far).",
                    step=20)
    g.add_or_update(id="hazard_hit_30", kind="location", confidence=0.8,
                    statement="Harness: took 4 damage at (6, 12, 5) at step 30.", step=30)
    g.add_or_update(id="hazard_death_40", kind="location", confidence=1.0, status="confirmed",
                    statement="Harness: you DIED at (7, 12, 5) at step 40.", step=40)
    g.add_or_update(id="coverage_since_ore", kind="state", confidence=1.0,
                    statement="Harness coverage ...", step=40)
    g.add_or_update(id="my_belief", kind="location", confidence=0.6,
                    statement="trees at (50, 64, 50)", step=40)
    parent._persist()

    child = WorldModelAgent(workspace=ws, task_text="t", ledger=MilestoneLedger(cfg, "t"),
                            induction_every=0)
    child.codex = FakeCodex(child.memory.root, [])
    check("the child loads the inherited graph", child._inherited_graph
          and len(child.graph.nodes) == 6)
    child.start(fake_info())
    n = child.graph.nodes
    check("built site goes stale and says so",
          n["site_furnace_10"].status == "stale" and "NOT there now" in n["site_furnace_10"].statement)
    check("vein stays confirmed and says the ore is back",
          n["vein_iron_ore_20"].status == "confirmed" and "BACK in place" in n["vein_iron_ore_20"].statement)
    check("hit goes stale, death keeps the terrain",
          n["hazard_hit_30"].status == "stale" and n["hazard_death_40"].status == "confirmed"
          and "terrain" in n["hazard_death_40"].statement)
    check("coverage is dropped, the model's own node untouched",
          "coverage_since_ore" not in n and n["my_belief"].statement == "trees at (50, 64, 50)")
    check("repricing happens once", child._inherited_graph is False
          and n["vein_iron_ore_20"].statement.count("PREVIOUS run") == 1)


def test_world(root: Path) -> None:
    """World macros: aim-by-coordinate geometry, plan-time compilation, and the place /
    build / pillar / hold / scan machines run against a scripted world."""
    print("\n[world] place_at / use_at / build / pillar_up / use_held / scan_around")
    import math
    from mcu_worldmodel import macros_world as MW
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    fx, fz = MW.facing(0.0)
    check("facing: yaw 0 -> +z, yaw 90 -> -x, yaw -90 -> +x",
          abs(fx) < 1e-9 and fz > 0.99 and MW.axis_facing(90.0) == (-1, 0)
          and MW.axis_facing(-90.0) == (1, 0) and MW.axis_facing(200.0) == (0, -1))
    check("aim point: inside the target, just short of the face toward the support",
          math.dist(MW.aim_point((0, 0, 0), "below"), (0.5, 0.05, 0.5)) < 1e-9
          and math.dist(MW.aim_point((0, 0, 0), "south"), (0.5, 0.5, 0.95)) < 1e-9)
    pos = {"x": 0.5, "y": 0.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    pitch, yaw, dist = MW.angles_to(pos, MW.aim_point((0, 0, 2), "below"))
    check("angles: the ground block 2 ahead is ~40 deg down, dead ahead, in reach",
          30 < pitch < 50 and abs(yaw) < 1e-6 and 2.0 < dist < 3.0, (pitch, yaw, dist))
    check("overlap: own cell yes, the cell ahead no",
          MW.overlaps_player((0, 0, 0), pos) and not MW.overlaps_player((0, 0, 2), pos))
    check("candidate faces: the asked face first, then the side facing the avatar",
          MW.candidate_faces((0, 0, 2), pos, "below")[:2] == ["below", "north"])

    info = fake_info(inventory={"cobblestone": 8, "torch": 4})
    acts, note = MW.place_at(CursorState(), info, x=1, y=64, z=4, item="cobblestone")
    check("place_at compiles to equip + one _useat marker",
          sum(1 for a in acts if "_useat" in a) == 1
          and any(a.get("hotbar.1") for a in acts if "_useat" not in a), note)
    acts, note = MW.place_at(CursorState(), info, x=1, y=64, z=4, item="diamond")
    check("place_at refuses an item not carried", not acts and "carry no" in note, note)
    acts, note = MW.place_at(CursorState(), fake_info(inventory={"stone_pickaxe": 1}),
                             x=1, y=64, z=4, item="stone_pickaxe")
    check("place_at refuses a tool", not acts and "not a block" in note, note)
    acts, note = MW.use_at(CursorState(), info, x=1, y=65, z=3, item="torch", face="south")
    check("use_at with a face compiles", any("_useat" in a for a in acts) and "south" in note, note)
    acts, note = MW.use_at(CursorState(), info, x=1, y=64, z=4, item="torch", face="sideways")
    check("use_at rejects a bad face name", not acts and "face must be" in note, note)

    # A stack in the main rows goes through the hotbar first.
    deep = fake_info()
    deep["inventory"][20] = {"type": "cobblestone", "quantity": np.array(9)}
    acts, note = MW.place_at(CursorState(), deep, x=1, y=64, z=4, item="cobblestone")
    check("place_at moves a main-row stack into the hotbar first (one GUI trip)",
          any("_opengui" in a for a in acts) and any("_closegui" in a for a in acts)
          and any("_useat" in a for a in acts), note)

    info2 = fake_info(inventory={"cobblestone": 64})
    acts, note = MW.build_wall(CursorState(), info2, item="cobblestone", length=5, height=2)
    tg = [t for a in acts if "_build" in a for t in a["_build"]["targets"]]
    xs = sorted({t[0] for t in tg})
    check("build_wall: 10 targets in a line 2 ahead across the facing, two high, row 1 "
          "from one block up",
          len(tg) == 10 and {t[2] for t in tg} == {4} and xs == [-1, 0, 1, 2, 3]
          and {t[1] for t in tg} == {64, 65} and tg[0][0] == 1
          and sum(1 for a in acts if "_pillar" in a) == 1, tg)
    acts, note = MW.build_wall(CursorState(), info2, item="cobblestone", length=12, height=6)
    check("build_wall refuses more than carried", not acts and "needed" in note, note)
    acts, note = MW.bridge_forward(CursorState(), info2, n=3)
    bd = next(a["_build"] for a in acts if "_build" in a)
    check("bridge_forward: floor-level targets ahead, clicked on the face toward us, sneaking",
          [tuple(t) for t in bd["targets"]] == [(1, 63, 3, "north"), (1, 63, 4, "north"),
                                                (1, 63, 5, "north")] and bd["sneak"]
          and abs(bd["spots"][0][1] - 3.2) < 1e-9, bd)
    acts, note = MW.build_row(CursorState(), info2, item="cobblestone", length=3)
    bd = next(a["_build"] for a in acts if "_build" in a)
    check("build_row: three cells ahead at feet level, far one first, from where we stand",
          [tuple(t[:3]) for t in bd["targets"]] == [(1, 64, 5), (1, 64, 4), (1, 64, 3)]
          and bd["spots"] == [[1.5, 2.5]] * 3, bd)
    acts, note = MW.build_row(CursorState(), info2, item="cobblestone", length=5)
    bd = next(a["_build"] for a in acts if "_build" in a)
    check("build_row: a 5-long row is two segments, the far one built first from 3 ahead",
          [t[2] for t in bd["targets"]] == [7, 6, 5, 4, 3]
          and bd["spots"][0] == [1.5, 5.5] and bd["spots"][-1] == [1.5, 2.5], bd)

    # -- the place machine in a scripted world ------------------------------------------
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]

    class World:
        """Position fixed; the camera follows the deltas; a `use` press that is aimed
        within 2 degrees of a target's aim point places a block there."""

        def __init__(self, targets, inv, y=64.0):
            self.pitch, self.yaw, self.y = 0.0, 0.0, y
            self.targets = list(targets)
            self.inv = dict(inv)
            self.uses = {}
            self.jumping = 0
            self.pov = np.full((360, 640, 3), 120, dtype=np.uint8)

        def pos(self):
            return {"x": 1.5, "y": self.y, "z": 2.5, "pitch": self.pitch, "yaw": self.yaw}

        def info(self):
            i = fake_info(inventory=self.inv or None)
            i["location_stats"].update({"xpos": np.array(1.5), "ypos": np.array(self.y),
                                        "zpos": np.array(2.5), "pitch": np.array(self.pitch),
                                        "yaw": np.array(self.yaw)})
            i["use_item"] = {k: np.array(float(v)) for k, v in self.uses.items()}
            i["pov"] = self.pov
            return i

        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch = max(-90.0, min(90.0, self.pitch + float(cam[0])))
            self.yaw += float(cam[1])
            if a.get("use"):
                sel = next((k for k, v in self.inv.items() if v > 0), None)
                for t in list(self.targets):
                    p, yw, _ = MW.angles_to(self.pos(), MW.aim_point(t[:3], t[3]))
                    if (abs(p - self.pitch) < 2.0
                            and abs(MW.norm_yaw_delta(yw, self.yaw)) < 2.0 and sel):
                        self.uses[sel] = self.uses.get(sel, 0) + 1
                        self.inv[sel] -= 1
                        self.targets.remove(t)
                        break
                if a.get("jump") and self.pitch > 85 and sel and not self.jumping:
                    self.uses[sel] = self.uses.get(sel, 0) + 1
                    self.inv[sel] -= 1
                    self.jumping = 12
            if self.jumping:
                self.jumping -= 1
                if self.jumping == 0:
                    self.y += 1.0

    def drive(tag, plan, world, steps=260):
        ag = WorldModelAgent(workspace=root / f"world_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"), induction_every=0,
                             step_cap=400)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": plan}, "message": "[PLAN]\nworld"},
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
        seen: list[str] = []
        images: list[str] = []
        _add, _run = ag.memory.add_note, ag.codex.run

        def _cap(note):
            seen.append(note)
            _add(note)

        def _runcap(prompt, imgs=(), **kw):
            images.extend(str(i) for i in imgs)
            return _run(prompt, imgs, **kw)
        ag.memory.add_note = _cap
        ag.codex.run = _runcap
        ag.start(world.info())
        for step in range(1, steps):
            a = ag.next_action(world.info())
            world.apply(a)
            ag.observe(world.info(), step)
            if ag.codex.calls >= 2 and not ag.queue:
                break
        ag._test_images = images
        return ag, " | ".join(seen)

    w = World([(1, 64, 4, "below")], {"cobblestone": 8})
    ag, notes = drive("place", [{"procedure": "place_at",
                                 "args": {"x": 1, "y": 64, "z": 4, "item": "cobblestone"}}], w)
    check("place_at places the block and says so",
          w.uses.get("cobblestone") == 1 and "placed at (1, 64, 4)" in notes
          and ag.cursor_stats.get("useat_ok") == 1, notes[-300:])
    w = World([], {"cobblestone": 8})            # nothing ever registers
    ag, notes = drive("place_fail", [{"procedure": "place_at",
                                      "args": {"x": 1, "y": 64, "z": 4, "item": "cobblestone"}},
                                     {"procedure": "travel", "args": {"n": 20}}], w)
    check("a refused placement tries other faces, then names the failure and drops the plan",
          "did not go down" in notes and ag.cursor_stats.get("useat_failed_flush") == 1
          and w.uses == {}, notes[-300:])
    w = World([(1, 64, 4, "below"), (1, 65, 4, "below"), (1, 66, 4, "below")], {"cobblestone": 8})
    ag, notes = drive("column", [{"procedure": "build_column",
                                  "args": {"item": "cobblestone", "height": 3, "dist": 2}}], w, 400)
    check("build_column of 3: one from the ground, then one block up per row",
          w.uses.get("cobblestone") == 5 and notes.count("placed 1 of 1") == 3
          and notes.count("pillar_up: 1 of 1") == 2, notes[-400:])
    w = World([], {"cobblestone": 8})
    ag, notes = drive("pillar", [{"procedure": "pillar_up", "args": {"n": 3}}], w, 400)
    check("pillar_up: three blocks under the feet, y +3",
          w.y == 67.0 and "3 of 3" in notes, (w.y, notes[-200:]))
    w = World([], {"bow": 1, "arrow": 4})
    # the world: a bow held >= 25 ticks then released fires one arrow
    class BowWorld(World):
        def __init__(self):
            super().__init__([], {"bow": 1, "arrow": 4})
            self.held = 0
        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch += float(cam[0]); self.yaw += float(cam[1])
            if a.get("use"):
                self.held += 1
            else:
                if self.held >= 25:
                    self.uses["bow"] = self.uses.get("bow", 0) + 1
                    self.inv["arrow"] -= 1
                self.held = 0
    bw = BowWorld()
    ag, notes = drive("bow", [{"procedure": "use_held", "args": {"item": "bow", "hold": 28}}], bw)
    check("use_held draws and releases the bow (use_item.bow +1, arrow -1)",
          bw.uses.get("bow") == 1 and bw.inv["arrow"] == 3 and "use_item +1" in notes,
          notes[-200:])
    ag, notes = drive("throw", [{"procedure": "throw", "args": {"item": "snowball", "n": 2}}],
                      World([], {"cobblestone": 5}))
    check("throw without the item carried is refused with a note", "carry no" in notes, notes[-200:])

    # fill_bucket: the world has still water under a pitch-35 / yaw+20 aim only
    class BucketWorld(World):
        def __init__(self, water=True):
            super().__init__([], {"bucket": 1, "cobblestone": 5})
            self.water = water
            self.taps = 0
        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch += float(cam[0]); self.yaw += float(cam[1])
            if a.get("use"):
                self.taps += 1
                if (self.water and self.inv.get("bucket", 0) == 1
                        and abs(self.pitch - 35.0) <= 3.0 and abs(self.yaw - 20.0) <= 3.0):
                    self.inv["bucket"] = 0
                    self.inv["water_bucket"] = 1
                    self.uses["bucket"] = self.uses.get("bucket", 0) + 1
    bw = BucketWorld()
    ag, notes = drive("fillb", [{"procedure": "fill_bucket", "args": {}}], bw)
    check("fill_bucket sweeps until the bucket fills and names water_bucket",
          bw.inv.get("water_bucket") == 1 and "the bucket filled -- water_bucket +1" in notes
          and ag.cursor_stats.get("fillb_ok") == 1, (bw.taps, bw.pitch, bw.yaw, notes[-300:]))
    check("fill_bucket stops at the aim that filled it (pitch 35, yaw 20 = aim 12: every pitch at one heading first)",
          "aim 12 of 25" in notes and abs(bw.pitch - 35.0) <= 3.0 and abs(bw.yaw - 20.0) <= 3.0,
          (bw.taps, bw.pitch, bw.yaw, notes[-300:]))
    bw = BucketWorld(water=False)
    ag, notes = drive("fillb_dry", [{"procedure": "fill_bucket", "args": {}}], bw)
    check("fill_bucket without water tries all 25 aims and says how to stand",
          bw.taps == 50 and "nothing filled in 25 aims" in notes and "SOURCE block" in notes
          and "pressed use at pitch/yaw 25/0, 35/0, 45/0, 60/0, 18/0, 25/-20" in notes,
          (bw.taps, notes[-300:]))
    ag, notes = drive("fillb_none", [{"procedure": "fill_bucket", "args": {}}],
                      World([], {"cobblestone": 5}))
    check("fill_bucket without a bucket carried is refused with a note", "carry no" in notes,
          notes[-200:])

    class FetchWorld:
        """A 3-wide pool `pool_z` blocks north of the start and a two-high leaf hedge at
        `hedge_z` the walk cannot cross until its eye-level block is broken (attack at
        pitch <= 12 from within 1.5 blocks, 6 ticks); the one-high rest is hopped. The
        frame paints the pool where the geometry puts it (70-degree vertical, ~102-degree
        horizontal view, the eye 1.62 up), all blue once the feet are in it. A `use` at
        that puts the crosshair's ground point (1.62 / tan(pitch) ahead) in the pool
        fills the bucket, from 5 blocks at most."""

        def __init__(self, pool_z=12.0, hedge_z=5.0, yaw=0.0, water=True, width=3.0, depth=3.0):
            self.x, self.z, self.yaw, self.pitch, self.y = 0.0, 0.0, yaw, 0.0, 64.0
            self.pool_z, self.hedge_z, self.water = pool_z, hedge_z, water
            self.hw, self.hd = width / 2.0, depth / 2.0
            self.hedge_open, self.att, self.taps = False, 0, 0
            self.inv = {"bucket": 1, "cobblestone": 5}
            self.uses: dict[str, int] = {}

        def dist(self):
            return math.hypot(0.0 - self.x, self.pool_z - self.z)

        def err(self):
            yt = math.degrees(math.atan2(-(0.0 - self.x), self.pool_z - self.z))
            return ((yt - self.yaw + 180.0) % 360.0) - 180.0

        def frame(self):
            f = np.full((360, 640, 3), 120, dtype=np.uint8)
            if not self.water:
                return f
            if self.z >= self.pool_z - self.hd:
                f[:] = (62, 84, 130)
                return f
            e = self.err()
            if abs(e) >= 51:
                return f
            d = self.dist()

            def row(dd):
                dep = math.degrees(math.atan2(1.62, dd))
                return max(0, min(359, int(round(180 + (dep - self.pitch) * 360 / 70))))
            r0, r1 = row(d + self.hd), row(max(d - self.hd, 0.3))
            if r1 <= r0:
                return f
            half = int(640 * math.degrees(math.atan2(self.hw, max(d, 0.5))) / 102)
            c = int(round(320 + e * 640 / 102))
            f[r0:r1, max(0, c - half):min(640, c + half)] = (62, 84, 130)
            return f

        def pos(self):
            return {"x": self.x, "y": self.y, "z": self.z, "pitch": self.pitch, "yaw": self.yaw}

        def info(self):
            i = fake_info(inventory=self.inv or None)
            i["location_stats"].update({"xpos": np.array(self.x), "ypos": np.array(self.y),
                                        "zpos": np.array(self.z), "pitch": np.array(self.pitch),
                                        "yaw": np.array(self.yaw)})
            i["use_item"] = {k: np.array(float(v)) for k, v in self.uses.items()}
            i["pov"] = self.frame()
            return i

        def _move(self, ang, sp):
            nx = self.x - sp * math.sin(math.radians(ang))
            nz = self.z + sp * math.cos(math.radians(ang))
            if not self.hedge_open and self.z <= self.hedge_z - 0.3 <= nz:
                nz = self.hedge_z - 0.3
            self.x, self.z = nx, nz

        def apply(self, a):
            cam = a.get("camera") or [0.0, 0.0]
            self.pitch = max(-90.0, min(90.0, self.pitch + float(cam[0])))
            self.yaw += float(cam[1])
            if (a.get("attack") and self.pitch <= 12.0 and abs(self.err()) < 30.0
                    and self.hedge_z - 1.5 <= self.z < self.hedge_z):
                self.att += 1
                if self.att >= 6:
                    self.hedge_open = True
            sp = 0.28 if a.get("sprint") else 0.2
            if a.get("forward"):
                self._move(self.yaw, sp)
            if a.get("back"):
                self._move(self.yaw + 180.0, 0.2)
            if a.get("left"):
                self._move(self.yaw - 90.0, 0.2)
            if a.get("right"):
                self._move(self.yaw + 90.0, 0.2)
            self.y = 63.4 if self.z >= self.pool_z - self.hd else 64.0
            if a.get("use"):
                self.taps += 1
                # the crosshair's ground point: 1.62 / tan(pitch) ahead along the yaw
                reach = 1.62 / math.tan(math.radians(max(self.pitch, 5.0)))
                gx = self.x - reach * math.sin(math.radians(self.yaw))
                gz = self.z + reach * math.cos(math.radians(self.yaw))
                if (self.water and self.inv.get("bucket", 0) == 1 and reach <= 5.0
                        and abs(gx) <= self.hw and abs(gz - self.pool_z) <= self.hd):
                    self.inv["bucket"] = 0
                    self.inv["water_bucket"] = 1
                    self.uses["bucket"] = self.uses.get("bucket", 0) + 1

    fw = FetchWorld()
    ag, notes = drive("fetchw", [{"procedure": "fetch_water", "args": {}}], fw, steps=700)
    check("fetch_water (water in view): walks to the pool, breaks the hedge, stops on the shore, and the sweep fills",
          fw.inv.get("water_bucket") == 1 and fw.hedge_open and 6.0 <= fw.z < fw.pool_z - 1.5
          and "fetch_water: water reached" in notes and "1 block(s) broken on the way" in notes
          and "The bucket sweep (fill_bucket) runs next" in notes
          and "the bucket filled -- water_bucket +1" in notes
          and ag.cursor_stats.get("fetchw_ok") == 1 and ag.cursor_stats.get("fetchw_blocks", 0) >= 6,
          (fw.z, fw.hedge_open, fw.att, fw.taps, {k: v for k, v in ag.cursor_stats.items() if "fetch" in k}, notes[-400:]))
    fw = FetchWorld(yaw=180.0)
    ag, notes = drive("fetchw_scan", [{"procedure": "fetch_water", "args": {}}], fw, steps=900)
    check("fetch_water (facing away): the 12-heading scan finds the pool, the walk turns onto it and fills",
          fw.inv.get("water_bucket") == 1 and abs(MW.norm_yaw_delta(0.0, fw.yaw)) <= 12.0
          and "fetch_water: water reached" in notes and "the bucket filled -- water_bucket +1" in notes,
          (fw.z, fw.yaw, fw.hedge_open, notes[-300:]))
    fw = FetchWorld(pool_z=35.0, yaw=180.0, width=12.0, depth=12.0)
    ag, notes = drive("fetchw_far", [{"procedure": "fetch_water", "args": {}}], fw, steps=1200)
    check("fetch_water (a 12x12 lake 35 blocks off, found by the scan): the walk keeps the heading through the blind stretch and fills",
          fw.inv.get("water_bucket") == 1 and fw.z >= 24.0 and "fetch_water: water reached" in notes
          and "lost sight" not in notes, (fw.z, fw.yaw, notes[-300:]))
    fw = FetchWorld()
    ag, notes = drive("fetchw_short", [{"action": {}, "repeat": 250},
                                       {"procedure": "fetch_water", "args": {}}], fw, steps=400)
    import re as _re
    m_shr = _re.search(r"shrunk to fit the step cap: 600 -> (\d+) ticks", notes)
    m_ref = _re.search(r"NOT STARTED: only (\d+) ticks were available", notes)
    check("fetch_water shrunk to the tail of a plan (400-tick cap, a raw entry ahead of it) does not start and says so",
          m_shr is not None and m_ref is not None and m_shr.group(1) == m_ref.group(1)
          and int(m_ref.group(1)) < 250
          and "Put fetch_water FIRST in the next plan" in notes and abs(fw.z) < 0.5
          and fw.inv.get("water_bucket") is None
          and ag.cursor_stats.get("fetchw_not_started") == 1,
          (fw.z, m_shr and m_shr.group(0), m_ref and m_ref.group(0), notes[-200:]))
    fw = FetchWorld()
    ag, notes = drive("fetchw_smalln", [{"procedure": "fetch_water", "args": {"n": 150}}], fw, steps=700)
    check("a model-chosen n of 150 is raised to 250, not refused: the walk runs and fills",
          fw.inv.get("water_bucket") == 1 and "NOT STARTED" not in notes
          and "up to 250 ticks" in notes, (fw.z, notes[-300:]))
    fw = FetchWorld(water=False)
    ag, notes = drive("fetchw_dry", [{"procedure": "fetch_water", "args": {}}], fw, steps=400)
    check("fetch_water with no water anywhere scans 12 headings and says so",
          "no still water in view from here in 12 headings" in notes
          and fw.inv.get("water_bucket") is None and abs(fw.z) < 0.5, (fw.z, notes[-300:]))
    ag, notes = drive("fetchw_none", [{"procedure": "fetch_water", "args": {}}],
                      World([], {"cobblestone": 5}))
    check("fetch_water without a bucket carried is refused with a note",
          "carry no empty bucket" in notes, notes[-200:])
    w = World([], {"cobblestone": 4})
    ag, notes = drive("scan", [{"procedure": "scan_around", "args": {"steps": 4}}], w)
    frames = sorted((ag.memory.root / "episodes").rglob("*_scan*.png"))
    check("scan_around saves a frame per heading plus a contact sheet it names, attaching nothing",
          len([f for f in frames if "scansheet" not in f.name]) == 4
          and any("scansheet" in f.name for f in frames) and "4 views" in notes
          and "tiled into" in notes
          and not any("scansheet" in f for f in ag._test_images),
          (len(frames), ag._test_images, notes[-200:]))
    check("scan_around ends near the starting yaw", abs(MW.norm_yaw_delta(0.0, w.yaw)) <= 4.0, w.yaw)
    from mcu_worldmodel import procedures as P
    docs = P.reference()
    check("docs: the world macros are offered",
          all(k in docs for k in ("place_at(", "use_at(", "build_wall(", "bridge_forward(",
                                  "pillar_up(", "scan_around(", "sleep_in_bed(",
                                  "fill_bucket(", "fetch_water(")))


def test_nether(root: Path) -> None:
    """Nether macros: frame geometry, refusals, the dimension check on a scripted biome."""
    print("\n[nether] make_obsidian / build_portal_frame / light_portal / enter_portal")
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    pos = {"x": 1.5, "y": 64.0, "z": 2.5, "pitch": 0.0, "yaw": 0.0}
    cells, (dx, dz), (px, pz) = MN._frame_cells(pos, 2)
    xs = {c[0] for c in cells}
    check("frame: 14 cells, 4 wide x 5 high, in the plane 2 ahead",
          len(cells) == 14 and {c[2] for c in cells} == {4} and xs == {0, 1, 2, 3}
          and {c[1] for c in cells} == {64, 65, 66, 67, 68}, cells)
    check("frame: the interior 2x3 is left empty",
          not any((c[0] in (1, 2) and c[1] in (65, 66, 67)) for c in cells))
    check("frame: the top row's inner blocks are placed against their nearest corner",
          cells[-2][3] == "west" and cells[-1][3] == "east" and cells[-2][:3] == (1, 68, 4),
          cells[-2:])
    info = fake_info(inventory={"obsidian": 14, "flint_and_steel": 1, "cobblestone": 8})
    acts, note = MN.build_portal_frame(CursorState(), info, dist=2)
    bd = [a["_build"] for a in acts if "_build" in a]
    pil = [a["_pillar"] for a in acts if "_pillar" in a]
    check("build_portal_frame with 14 obsidian: row 0 from the ground, one block up per row",
          len(bd) == 5 and [len(b["targets"]) for b in bd] == [4, 2, 2, 2, 4]
          and [p["target"] for p in pil] == [1, 1, 1, 1] and pil[0]["item"] == "cobblestone",
          note)
    acts, note = MN.build_portal_frame(CursorState(),
                                       fake_info(inventory={"obsidian": 14}), dist=2)
    check("build_portal_frame asks for a hotbar filler to stand on when none is carried",
          not acts and "HOTBAR" in note, note)
    acts, note = MN.build_portal_frame(CursorState(), fake_info(inventory={"obsidian": 6}))
    check("build_portal_frame refuses fewer than 10", not acts and "needs 10" in note, note)
    short = fake_info(inventory={"obsidian": 10, "cobblestone": 8})
    acts, note = MN.build_portal_frame(CursorState(), short, dist=2)
    bd = [a["_build"] for a in acts if "_build" in a]
    check("10 obsidian + cobblestone in the hotbar: corners from cobblestone, 10 obsidian",
          len(bd) == 7 and bd[0]["item"] == "cobblestone" and bd[1]["item"] == "obsidian"
          and sum(len(b["targets"]) for b in bd) == 14
          and sum(len(b["targets"]) for b in bd if b["item"] == "obsidian") == 10
          and sum(1 for a in acts if "_pillar" in a) == 4, note)
    acts, note = MN.light_portal(CursorState(), info, dist=2)
    check("light_portal compiles to a use_at on the inside bottom block plus a check",
          any("_useat" in a for a in acts) and any("_portalcheck" in a for a in acts)
          and "(1, 64, 4)" in note, note)
    acts, note = MN.make_obsidian(CursorState(), fake_info(inventory={"bucket": 1}), 0, 63, 3)
    check("make_obsidian needs a water bucket", not acts and "water_bucket" in note, note)
    acts, note = MN.make_obsidian(CursorState(), fake_info(inventory={"water_bucket": 1}),
                                  0, 63, 3)
    kinds = [next(k for k in a if k != "_cost") for a in acts if isinstance(a, dict)
             and any(k.startswith("_") and k != "_cost" for k in a)]
    check("make_obsidian: pour, wait, scoop back, check",
          kinds.count("_useat") == 2 and "_wait" in kinds and kinds[-1] == "_obsidiancheck",
          kinds)
    acts, note = MN.mine_obsidian(CursorState(), fake_info(inventory={"iron_pickaxe": 1}),
                                  0, 63, 3)
    check("mine_obsidian insists on a diamond pickaxe", not acts and "DIAMOND" in note, note)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[100:200, 250:400] = (120, 30, 200)
    check("portal_fraction reads the purple and ignores stone",
          MN.portal_fraction(frame) > MN.PORTAL_FRAC_MIN
          and MN.portal_fraction(np.full((360, 640, 3), 128, np.uint8)) == 0.0)
    check("dimension_of maps the biome ids",
          MN.dimension_of(8) == "the Nether" and MN.dimension_of(9) == "the End"
          and MN.dimension_of(1) == "the Overworld")

    # enter_portal against a scripted world whose biome flips after 60 ticks in the cell
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "nether", task_text="t",
                         ledger=MilestoneLedger(cfg, "t"), induction_every=0, step_cap=400)
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [{"procedure": "enter_portal", "args": {"x": 1.5, "z": 4.5}}]},
         "message": "[PLAN]\nin"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
    st = {"x": 1.5, "z": 2.5, "yaw": 0.0, "biome": 1, "in": 0}
    seen: list[str] = []
    _add = ag.memory.add_note
    ag.memory.add_note = lambda n: (seen.append(n), _add(n))

    def info_now():
        i = fake_info()
        i["location_stats"].update({"xpos": np.array(st["x"]), "zpos": np.array(st["z"]),
                                    "yaw": np.array(st["yaw"]), "biome_id": np.array(st["biome"])})
        i["pov"] = np.zeros((360, 640, 3), dtype=np.uint8)
        return i
    ag.start(info_now())
    for step in range(1, 300):
        a = ag.next_action(info_now())
        cam = a.get("camera") or [0.0, 0.0]
        st["yaw"] += float(cam[1])
        if a.get("forward"):
            st["z"] += 0.2 * math.cos(math.radians(st["yaw"]))
            st["x"] -= 0.2 * math.sin(math.radians(st["yaw"]))
        if abs(st["z"] - 4.5) < 0.75 and abs(st["x"] - 1.5) < 0.75:
            st["in"] += 1
            if st["in"] >= 60:
                st["biome"], st["x"], st["z"] = 8, st["x"] / 8, st["z"] / 8
        ag.observe(info_now(), step)
        if ag.codex.calls >= 2 and not ag.queue:
            break
    check("enter_portal walks in, waits, and reports the Nether",
          any("in the Nether" in n for n in seen) and ag.cursor_stats.get("portal_trips") == 1,
          seen[-2:])
    from mcu_worldmodel import procedures as P
    docs = P.reference()
    check("docs: the nether macros are offered",
          all(k in docs for k in ("make_obsidian(", "build_portal_frame(", "light_portal(",
                                  "enter_portal(", "mine_obsidian(")))


def test_nether2(root: Path) -> None:
    """The Nether leg: the fortress and blaze detectors, explore_nether's compile and
    its walk/tunnel/stop loop against a scripted world, fight_blaze, enderman_pit."""
    print("\n[nether2] fortress_in_view / blaze_hint / explore_nether / fight_blaze / enderman_pit")
    from mcu_worldmodel import macros, vision
    from mcu_worldmodel import macros_entity as ME
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel import vision_nether as VN
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    # -- detectors on synthetic frames --------------------------------------------
    rack = np.zeros((360, 640, 3), dtype=np.uint8)
    rack[:] = (97, 38, 38)                          # netherrack everywhere
    check("fortress_in_view: netherrack alone is not a fortress",
          VN.fortress_in_view(rack) is None, VN.fortress_fraction(rack))
    wall = rack.copy()
    wall[90:250, 380:620] = (44, 22, 26)            # a nether-brick mass, right of centre
    fv = VN.fortress_in_view(wall)
    check("fortress_in_view: a nether-brick mass is found with a rightward yaw offset",
          fv is not None and fv[0] > 0.05 and 25.0 < fv[1] < 45.0, fv)
    shade = rack.copy()
    shade[90:250, 380:620] = (50, 20, 20)           # shaded netherrack: b == g
    check("fortress_in_view: shaded netherrack (blue == green) is not nether brick",
          VN.fortress_in_view(shade) is None, VN.fortress_fraction(shade))
    stem = rack.copy()
    stem[60:300, 300:312] = (44, 22, 26)            # a thin column in the band
    check("fortress_in_view: a thin column in the band is too small to be a fortress",
          VN.fortress_in_view(stem) is None, VN.fortress_fraction(stem))
    grey = np.full((360, 640, 3), 120, dtype=np.uint8)
    blaze = grey.copy()
    blaze[120:220, 280:340] = (246, 178, 1)         # the yellow body
    blaze[120:220, 302:316] = (50, 50, 50)          # its grey rods down the middle
    bh = VN.blaze_hint(blaze)
    check("blaze_hint: a yellow blob with grey rods inside is a blaze, centred on it",
          bh is not None and bh[0] == "blaze" and abs(bh[1] - 310) <= 6
          and abs(bh[2] - 170) <= 6, bh)
    lava = rack.copy()
    lava[200:290, 100:500] = (246, 178, 1)          # a lava pool: no grey in its box
    check("blaze_hint: lava (the same yellow, no rods) is not a blaze",
          VN.blaze_hint(lava) is None, VN.blaze_hint(lava))
    bluish = grey.copy()
    bluish[120:220, 280:340] = (200, 120, 48)       # lava's yellow: a quarter blue
    bluish[150:180, 280:340] = (50, 50, 50)
    check("blaze_hint: the blue in lava's yellow (b/r 0.24) is refused even with grey inside",
          VN.blaze_hint(bluish) is None, VN.blaze_hint(bluish))
    check("the blaze detector is registered for fight(detect='blaze')",
          ME.DETECTORS.get("blaze") is VN.blaze_hint)
    sky = np.zeros((360, 640, 3), dtype=np.uint8)
    sky[:] = (150, 190, 250)
    ender = sky.copy()
    ender[100:250, 300:340] = (20, 20, 20)          # a tall black body against the sky
    eh = VN.enderman_hint(ender)
    check("enderman_hint: a tall black blob against the SKY is an enderman (the plain "
          "band rejects sky-ringed blobs as clouds; from a pit every mob is sky-ringed)",
          eh is not None and eh[0] == "enderman" and abs(eh[1] - 319) <= 4
          and abs(eh[2] - 174) <= 4, (eh, vision.entity_hint(ender, want="enderman")))
    wide = sky.copy()
    wide[150:190, 200:440] = (20, 20, 20)           # a flat dark band: not a mob
    check("enderman_hint: a wide flat dark band is not an enderman",
          VN.enderman_hint(wide) is None, VN.enderman_hint(wide))
    check("the enderman detector is registered, so fight(label='enderman') uses it first",
          ME.DETECTORS.get("enderman") is VN.enderman_hint)

    # -- plan-time compilation -------------------------------------------------------
    inv = fake_info(inventory={"diamond_pickaxe": 1, "cobblestone": 12, "diamond_sword": 1})
    acts, note = MN.explore_nether(CursorState(), inv, axis="x", sign=-1, length=50)
    st = next(a["_nexplore"] for a in acts if "_nexplore" in a)
    check("explore_nether compiles: heading for x- is yaw 90, the pickaxe selected, "
          "cobblestone chosen for bridging",
          st["yaw_t"] == 90.0 and (st["ax"], st["az"]) == (-1, 0) and st["length"] == 50
          and st["pick"] == "diamond_pickaxe" and st["block"] == "cobblestone"
          and any(a.get("hotbar.1") for a in acts if "_nexplore" not in a), (st, note))
    acts, note = MN.explore_nether(CursorState(), inv, axis="y", sign=1)
    check("explore_nether refuses an axis that is not x or z", not acts and "axis" in note, note)
    acts, note = MN.explore_nether(CursorState(), fake_info(inventory={"stone_pickaxe": 1}),
                                   axis="z", sign=1, length=20)
    st = next(a["_nexplore"] for a in acts if "_nexplore" in a)
    check("explore_nether with no blocks compiles but says it cannot bridge",
          st["block"] is None and "NO blocks" in note, (st, note))
    check("explore_nether's marker is registered as moving (survives the repeat-hit rule)",
          "_nexplore" in macros.MOVING)
    acts, note = MN.fight_blaze(CursorState(), inv)
    ft = next(a["_fight"] for a in acts if "_fight" in a)
    check("fight_blaze is fight with label=blaze and the blaze detector",
          ft["label"] == "blaze" and ft["detect"] == "blaze" and ft["weapon"] == "diamond_sword"
          and "hovers" in note, (ft, note))
    acts, note = MN.fight_blaze(CursorState(), fake_info(inventory={"cobblestone": 1}))
    ft = next(a["_fight"] for a in acts if "_fight" in a)
    check("fight_blaze without a sword still compiles (bare hands)", ft["weapon"] is None, note)
    acts, note = MN.enderman_pit(CursorState(), inv)
    dg = next(a["_dig"] for a in acts if "_dig" in a)
    check("enderman_pit: a dig_down to y-2 with the pickaxe, then a look up, then a check",
          dg["until_y"] == 62.0 and any("_lookabs" in a for a in acts)
          and any("_pitcheck" in a for a in acts) and "2 blocks" in note, (dg, note))
    from mcu_worldmodel import procedures as P
    docs = P.reference()
    check("docs: explore_nether, fight_blaze and enderman_pit are offered",
          all(k in docs for k in ("explore_nether(", "fight_blaze(", "enderman_pit(")))

    # -- the walk against a scripted world: open ground, a wall, then a fortress -------
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "nether2", task_text="t",
                         ledger=MilestoneLedger(cfg, "t"), induction_every=0, step_cap=400)
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [
            {"procedure": "explore_nether", "args": {"axis": "z", "sign": 1, "length": 24}},
            {"procedure": "look", "args": {"pitch": 0, "yaw": 90}}]},
         "message": "[PLAN]\nwalk"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
    world = {"x": 1.5, "z": 2.5, "yaw": 0.0, "pitch": 0.0, "wall": 2, "hits": 0,
             "broken": 0}
    seen: list[str] = []
    _add = ag.memory.add_note
    ag.memory.add_note = lambda n: (seen.append(n), _add(n))
    WALL_Z, FORT_Z = 8.0, 20.0

    def info_now():
        i = fake_info(inventory={"diamond_pickaxe": 1, "cobblestone": 12},
                      mine_block={"netherrack": world["broken"]})
        i["location_stats"].update({"xpos": np.array(world["x"]), "zpos": np.array(world["z"]),
                                    "yaw": np.array(world["yaw"]),
                                    "pitch": np.array(world["pitch"])})
        f = rack.copy()
        if world["z"] >= FORT_Z - 8.0:               # the fortress comes into view
            f[80:260, 200:440] = (44, 22, 26)
        i["pov"] = f
        return i
    ag.start(info_now())
    for step in range(1, 900):
        a = ag.next_action(info_now())
        cam = a.get("camera") or [0.0, 0.0]
        world["pitch"] = max(-90.0, min(90.0, world["pitch"] + float(cam[0])))
        world["yaw"] += float(cam[1])
        at_wall = WALL_Z - 0.3 <= world["z"] < WALL_Z + 0.3 and world["wall"] > 0
        if a.get("forward") and not at_wall:
            world["z"] += 0.2 * math.cos(math.radians(world["yaw"]))
            world["x"] -= 0.2 * math.sin(math.radians(world["yaw"]))
        if a.get("attack") and at_wall and world["pitch"] > 5.0:
            world["hits"] += 1
            if world["hits"] >= 6:                   # a netherrack block breaks
                world["hits"], world["wall"] = 0, world["wall"] - 1
                world["broken"] += 1
        ag.observe(info_now(), step)
        if ag.codex.calls >= 2 and not ag.queue:
            break
    fort = [n for n in seen if "FORTRESS IN VIEW" in n]
    check("explore_nether: walked, tunnelled the wall (2 blocks broken) and stopped on "
          "the fortress with the bearing", len(fort) == 1 and "broke 2 block" in fort[0]
          and "bearing yaw" in fort[0] and world["z"] >= FORT_Z - 8.0,
          (fort[-1:] if fort else seen[-3:], world))
    check("explore_nether: the fortress stop dropped the rest of the plan",
          any("was dropped" in n for n in fort), fort)
    check("explore_nether: the stop is counted (fortress_seen, explore_blocks)",
          ag.cursor_stats.get("fortress_seen") == 1
          and ag.cursor_stats.get("explore_blocks", 0) >= 8, ag.cursor_stats)


def test_end(root: Path) -> None:
    """End macros: ring geometry, refusals, the bearing arithmetic, the End check on a
    scripted teleport, the crystal / dragon detectors on synthetic frames."""
    print("\n[end] throw_eye / travel_bearing / fill_end_portal / enter_end / dragon")
    from mcu_worldmodel import macros_end as ME_
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState

    frames = ME_.portal_frames(10, 40, -20)
    cells = {f["cell"] for f in frames}
    check("portal ring: 12 frames on the sides of a 5x5 square, no corners",
          len(cells) == 12 and all(max(abs(c[0] - 10), abs(c[2] + 20)) == 2 for c in cells)
          and not any(abs(c[0] - 10) == 2 and abs(c[2] + 20) == 2 for c in cells)
          and all(c[1] == 40 for c in cells), sorted(cells))
    outer_ok = all(
        (f["face"] == "west" and f["cell"][0] == 8) or (f["face"] == "east" and f["cell"][0] == 12)
        or (f["face"] == "north" and f["cell"][2] == -22) or (f["face"] == "south" and f["cell"][2] == -18)
        for f in frames)
    spots_ok = all(max(abs(f["spot"][0] - 10.5), abs(f["spot"][1] + 19.5)) == 3.0 for f in frames)
    check("portal ring: each frame's face points away from the pit and its spot is one "
          "block outside it", outer_ok and spots_ok, frames[:2])
    acts, note = ME_.fill_end_portal(CursorState(), fake_info(inventory={"cobblestone": 4}),
                                     10, 40, -20)
    check("fill_end_portal refuses without eyes", not acts and "no ender_eye" in note, note)
    info = fake_info(inventory={"ender_eye": 12, "cobblestone": 8})
    ME_.LAST_PORTAL.clear()
    acts, note = ME_.fill_end_portal(CursorState(), info, 10, 40, -20)
    fp = [a["_fillportal"] for a in acts if "_fillportal" in a]
    check("fill_end_portal compiles one resumable marker over the 12 frames",
          len(fp) == 1 and len(fp[0]["frames"]) == 12 and "12 frames" in note, note)
    ME_.LAST_PORTAL["filled"] = [list(f["cell"]) for f in frames]
    acts, note = ME_.fill_end_portal(CursorState(), info, 10, 40, -20)
    check("fill_end_portal after every frame is done says so and points to enter_end",
          not acts and "enter_end" in note, note)
    ME_.LAST_PORTAL.clear()
    check("bearing_of_pixel: the centre column is the facing, 55 px right is +11.6 degrees",
          abs(ME_.bearing_of_pixel(320, 640, 30.0) - 30.0) < 0.01
          and abs(ME_.bearing_of_pixel(375, 640, 0.0) - 11.6) < 0.2)
    b = ME_.bearing_from_samples([(15, 383, 260), (21, 375, 188), (27, 371, 145), (30, 370, 135)],
                                 640, -170.0)
    check("bearing_from_samples: median column -> bearing wraps, the y slope reads the climb",
          b is not None and abs(b[0] - (-170.0 + 11.9)) < 1.5 and b[2] < -ME_.EYE_DOWN_SLOPE, b)
    b2 = ME_.bearing_from_samples([(15, 320, 100), (21, 320, 140), (27, 320, 180)], 640, 0.0)
    check("bearing_from_samples: a falling eye has a positive slope",
          b2 is not None and b2[2] > ME_.EYE_DOWN_SLOPE, b2)
    acts, note = ME_.throw_eye(CursorState(), fake_info(inventory={"cobblestone": 4}))
    check("throw_eye refuses without an eye", not acts and "no ender_eye" in note, note)
    acts, note = ME_.throw_eye(CursorState(), fake_info(inventory={"ender_eye": 3}))
    kinds = [next(k for k in a if k != "_cost") for a in acts if isinstance(a, dict)
             and any(k.startswith("_") and k != "_cost" for k in a)]
    check("throw_eye: look level, throw+watch; no fetch by default (the eye never drops back)",
          kinds[-2:] == ["_lookabs", "_eyetrack"] and "_eyefetch" not in kinds, kinds)
    acts, note = ME_.throw_eye(CursorState(), fake_info(inventory={"ender_eye": 3}), fetch=True)
    check("throw_eye(fetch=true) appends the walk-out",
          any("_eyefetch" in a for a in acts), note)
    acts, note = ME_.travel_bearing(CursorState(), fake_info(), yaw=90, blocks=50)
    gts = [a["_goto"] for a in acts if "_goto" in a]
    check("travel_bearing: 50 blocks toward yaw 90 (-x) is three legs ending 50 blocks west",
          len(gts) == 3 and abs(gts[-1]["x"] - (1.0 - 50.0)) < 0.01 and abs(gts[-1]["z"] - 2.0) < 0.01
          and any("_bearingreport" in a for a in acts), (gts, note))
    acts, note = ME_.mine_end_stone(CursorState(), fake_info(inventory={"cobblestone": 4}))
    check("mine_end_stone refuses without a pickaxe", not acts and "no pickaxe" in note, note)
    acts, note = ME_.mine_end_stone(CursorState(), fake_info(inventory={"iron_pickaxe": 1}))
    seqs = [a["_seq"] for a in acts if "_seq" in a]
    check("mine_end_stone: pickaxe, aim toward the island, mine until end_stone, check",
          seqs and seqs[0].get("until_item") == "end_stone"
          and any("_endstonecheck" in a for a in acts), (note, [list(a)[0] for a in acts]))
    frame = np.full((360, 640, 3), 22, np.uint8)          # the End sky
    frame[120:180, 300:340] = (210, 60, 200)               # a crystal
    c = ME_.crystal_blob(frame)
    check("crystal_blob finds the magenta cube on the End sky and nothing on the sky alone",
          c is not None and abs(c[0] - 320) < 3 and ME_.crystal_blob(np.full((360, 640, 3), 22, np.uint8)) is None, c)
    frame = np.full((360, 640, 3), 22, np.uint8)
    frame[100:220, 200:420] = 6                            # the dragon
    dgn = ME_.dragon_blob(frame)
    check("dragon_blob finds the black mass on the not-quite-black sky, none on the sky alone",
          dgn is not None and abs(dgn[0] - 310) < 3 and ME_.dragon_blob(np.full((360, 640, 3), 22, np.uint8)) is None, dgn)
    check("in_the_end: the spawn platform, not the overworld",
          ME_.in_the_end({"x": 100.5, "z": -0.5}) and not ME_.in_the_end({"x": -3009.5, "z": -5572.5}))
    socket = np.full((360, 640, 3), 25, np.uint8)             # the empty frame's dark socket
    eye = socket.copy()
    eye[170:191, 310:331] = (70, 105, 85)                     # the iris seen from one block
    check("frame_has_eye: the dark socket is empty, the green iris is an eye",
          ME_.frame_has_eye(socket) is False and ME_.frame_has_eye(eye) is True,
          (ME_.frame_top_reading(socket), ME_.frame_top_reading(eye)))

    # enter_end against a scripted world that teleports after 30 ticks in the pit
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]
    ag = WorldModelAgent(workspace=root / "end", task_text="t",
                         ledger=MilestoneLedger(cfg, "t"), induction_every=0, step_cap=400)
    ag.codex = FakeCodex(ag.memory.root, [
        {"actions": {"actions": [{"procedure": "enter_end", "args": {"x": 1, "y": 63, "z": 6}}]},
         "message": "[PLAN]\nin"},
        {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "[PLAN]\n-"}])
    st = {"x": 1.5, "z": 2.5, "yaw": 0.0, "in": 0}
    seen: list[str] = []
    _add = ag.memory.add_note
    ag.memory.add_note = lambda n: (seen.append(n), _add(n))

    def info_now():
        i = fake_info()
        i["location_stats"].update({"xpos": np.array(st["x"]), "zpos": np.array(st["z"]),
                                    "yaw": np.array(st["yaw"])})
        i["pov"] = np.zeros((360, 640, 3), dtype=np.uint8)
        return i
    ag.start(info_now())
    for step in range(1, 300):
        a = ag.next_action(info_now())
        cam = a.get("camera") or [0.0, 0.0]
        st["yaw"] += float(cam[1])
        if a.get("forward"):
            st["z"] += 0.2 * math.cos(math.radians(st["yaw"]))
            st["x"] -= 0.2 * math.sin(math.radians(st["yaw"]))
        if abs(st["z"] - 6.5) < 0.75 and abs(st["x"] - 1.5) < 0.75:
            st["in"] += 1
            if st["in"] >= 30:
                st["x"], st["z"] = 100.5, 0.5
        ag.observe(info_now(), step)
        if ag.codex.calls >= 2 and not ag.queue:
            break
    check("enter_end walks into the pit, waits, and reports THE END on the spawn platform",
          any("THE END" in n and "spawn platform" in n for n in seen)
          and ag.cursor_stats.get("end_trips") == 1, seen[-2:])
    from mcu_worldmodel import procedures as P
    docs = P.reference()
    check("docs: the End macros are offered",
          all(k in docs for k in ("throw_eye(", "travel_bearing(", "fill_end_portal(",
                                  "enter_end(", "mine_end_stone(", "break_crystal(",
                                  "attack_dragon(")))


def test_containers(root: Path) -> None:
    """The container screens beyond the table and the furnace: recognition, geometry,
    the [GRID] rows, and the six macros in macros_container.py."""
    print("\n[containers] chest / double chest / brewing / enchanting / stonecutter")
    from mcu_worldmodel import gui as _gui, macros as _macros, vision as _vis
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.cursor import CursorState
    from mcu_worldmodel.procedures import REGISTRY, expand

    # -- synthetic screens ----------------------------------------------------
    # Drawn the way the engine draws them: the container is CENTRED (so its top row is
    # (360 - backgroundHeight)/2, which is what screen_kind reads the height from), one
    # dark border row and two near-white bevel rows above the body, and each slot is a
    # dark top/left, white bottom/right ring around a grey 16x16 item area.
    def slot(fr, sx, sy, pad=0, full=False):
        t, l = sy - 1 - pad, sx - 1 - pad
        b, r = sy + 16 + pad, sx + 16 + pad
        fr[t, l:r + 1] = 55
        fr[t:b + 1, l] = 55
        fr[b, l:r + 1] = 255
        fr[t:b + 1, r] = 255
        fr[sy:sy + 16, sx:sx + 16] = 139
        if full:                                    # an item icon is texture, not flat
            rng = np.random.RandomState(sx * 31 + sy)
            fr[sy + 1:sy + 15, sx + 1:sx + 15] = rng.randint(0, 255, (14, 14, 3))

    def cells_of(kind):
        """(container-coordinate top-left, pad) of every slot the screen draws."""
        std = [(_gui.player_slot_topleft(s), 0) for s in range(36)]
        if kind in ("chest", "chest2"):
            return ([(tl, 0) for tl in _gui.chest_cells(kind)]
                    + [(_gui.player_slot_topleft(s, kind), 0) for s in range(36)])
        if kind == "brewing":
            return [(_gui.BREW_FUEL, 0), (_gui.BREW_INGREDIENT, 0)] + [
                (tl, 0) for tl in _gui.BREW_BOTTLES] + std
        if kind == "enchanting":
            return [(_gui.ENCHANT_ITEM, 0), (_gui.ENCHANT_LAPIS, 0)] + std
        if kind == "stonecutter":
            return [(_gui.CUT_IN, 0), (_gui.CUT_OUT, 4)] + std
        if kind == "anvil":
            return [(_gui.ANVIL_IN, 0), (_gui.ANVIL_ADD, 0), (_gui.ANVIL_OUT, 0)] + std
        return [(_gui.FURNACE_IN, 0), (_gui.FURNACE_FUEL, 0), (_gui.FURNACE_OUT, 4)] + std

    def container_frame(kind, full=()):
        h = _gui.SCREEN_H[kind]
        top = (360 - h) // 2
        ox, oy = (int(v) for v in _gui.container_origin())   # the FIXED 176x166 frame
        fr = np.full((360, 640, 3), 60, dtype=np.uint8)
        fr[top:top + h, ox:ox + _gui.CONTAINER_W] = 198
        fr[top, ox:ox + _gui.CONTAINER_W] = 0
        fr[top + 1:top + 3, ox:ox + _gui.CONTAINER_W] = 255
        fr[oy + 163, ox + 173] = 85                          # the legacy dark bevel probe
        for i, (tl, pad) in enumerate(cells_of(kind)):
            slot(fr, ox + int(tl[0]), oy + int(tl[1]), pad, full=i in full)
        return fr

    kinds = ("chest", "chest2", "brewing", "enchanting", "stonecutter", "anvil",
             "furnace")
    got = [_vis.screen_kind(container_frame(k)) for k in kinds]
    check("vision: the six new container screens are told apart by their slot layout",
          got == list(kinds), f"{got} != {list(kinds)}")
    check("vision: the three pinned kinds still come from the cell probes, and a "
          "non-GUI frame is still None",
          _vis.screen_kind(np.full((360, 640, 3), 197, dtype=np.uint8)) is None
          and _vis.screen_kind(None) is None)
    check("vision: screen_kind reads a chest with items in it the same as an empty one",
          _vis.screen_kind(container_frame("chest", full=(0, 4, 13))) == "chest")
    check("gui: a 3-row chest keeps the standard player rows, a double chest moves them",
          _gui.player_slot_topleft(0, "chest") == _gui.slot_topleft(0)
          and _gui.player_slot_topleft(0, "chest2") == (8, 169)
          and len(_gui.chest_cells("chest2")) == 54,
          str(_gui.player_slot_topleft(0, "chest2")))

    # -- the cursor names the new cells ---------------------------------------
    cur = CursorState()
    cur.opened({})
    for target, want in ((_gui.centre(_gui.chest_cells("chest")[12]), "chest cell 12"),
                         (_gui.centre(_gui.BREW_BOTTLES[1]), "brewing bottle 1"),
                         (_gui.centre(_gui.ENCHANT_LAPIS), "enchant lapis"),
                         (_gui.enchant_button_centre(1), "enchant option 2"),
                         (_gui.centre(_gui.CUT_OUT), "stonecutter output"),
                         (_gui.centre(_gui.ANVIL_OUT), "anvil result"),
                         (_gui.centre(_gui.player_slot_topleft(0, "chest2")),
                          "hotbar slot 0 (double chest screen)")):
        cur.pos = target
        check(f"cursor.over names {want!r}", want in cur.over(), cur.over())

    # -- told which screen is open, the line drops the readings that cannot apply ------
    # Measured in rp02 (2026-09-03, real green): with no screen passed, every GUI turn
    # of a from-scratch run carried "hotbar slot 1 / inventory slot 28 (double chest
    # screen)" and worse -- three of four readings for screens the episode never opens.
    cur.pos = _gui.centre(_gui.slot_topleft(1))
    plain = cur.over()
    check("unfiltered, a player slot is also read as a double chest's row",
          "hotbar slot 1" in plain and "double chest screen" in plain, plain)
    inv = cur.over("inventory")
    check("on the survival screen only the standard row is named",
          inv == "hotbar slot 1", inv)
    cur.pos = _gui.centre(_gui.player_slot_topleft(1, "chest2"))
    ch2 = cur.over("chest2")
    check("on a double chest only the shifted row is named",
          "double chest screen" in ch2 and " / " not in ch2, ch2)
    cur.pos = _gui.centre(_gui.SURVIVAL_CRAFT_IN[0])
    craft2 = cur.over("inventory")
    check("a 2x2 cell keeps its own screen's reading",
          craft2 == "2x2 cell 0 (survival screen)", craft2)
    check("an unknown screen kind still reports every reading",
          cur.over("mystery") == cur.over(), cur.over("mystery"))

    # -- the macros compile ---------------------------------------------------
    def open_cur():
        c = CursorState()
        c.opened({})
        return c

    def marks(acts):
        return [next((k for k in a if k.startswith("_")), "env") for a in acts]

    chest_inv = fake_info(inventory={"cobblestone": 64, "iron_pickaxe": 1})
    chest_inv["isGuiOpen"] = True
    acts, note = expand("container_take", info=chest_inv, cursor=open_cur())
    check("container_take is a gate plus one frame-reading marker",
          marks(acts) == ["_cscreen", "_ctake"] and "emptying" in note, f"{marks(acts)}")
    acts, _ = expand("container_put", info=chest_inv, cursor=open_cur(),
                     item="cobblestone")
    check("container_put is a gate plus one marker",
          marks(acts) == ["_cscreen", "_cput"], str(marks(acts)))
    brew_inv = fake_info(inventory={"nether_wart": 2, "blaze_powder": 1, "potion": 1})
    brew_inv["isGuiOpen"] = True
    acts, note = expand("brew", info=brew_inv, cursor=open_cur())
    check("brew quick-moves fuel, bottles and the ingredient, then checks",
          marks(acts) == ["_cscreen"] + ["_servo", "_click"] * 3 + ["_servo",
                                                                    "_brewcheck"]
          and all(a["_click"]["shift"] for a in acts if "_click" in a)
          and "400 ticks" in note, f"{marks(acts)} {note!r}")
    acts, _ = expand("brew_take", info=brew_inv, cursor=open_cur())
    check("brew_take quick-moves the three bottle cells, then parks off them",
          marks(acts) == ["_cscreen"] + ["_servo", "_click"] * 3 + ["_servo", "_ccheck"]
          and acts[-2]["_servo"]["label"] == "clear of the cells", str(marks(acts)))
    ench_inv = fake_info(inventory={"diamond_sword": 1, "lapis_lazuli": 3})
    ench_inv["isGuiOpen"] = True
    acts, note = expand("enchant", info=ench_inv, cursor=open_cur(), option=2)
    labels = [a["_servo"]["label"] for a in acts if "_servo" in a]
    check("enchant: item in, lapis in, option button, then both cells emptied again",
          marks(acts)[0] == "_cscreen" and marks(acts)[-1] == "_enchcheck"
          and "enchant option 2" in labels and labels[-3:] == [
              "enchant item cell", "enchant lapis cell",
              "clear of the cells"], str(labels))
    cut_inv = fake_info(inventory={"stone": 16})
    cut_inv["isGuiOpen"] = True
    acts, note = expand("stonecut", info=cut_inv, cursor=open_cur(),
                        output="stone_bricks")
    check("stonecut searching loads nothing up front (one item per attempt)",
          marks(acts) == ["_cscreen", "_cutpick"] and "one item each" in note,
          f"{marks(acts)} {note!r}")
    acts, note = expand("stonecut", info=cut_inv, cursor=open_cur(), button=2)
    check("stonecut with a known button quick-moves the whole stack in first",
          marks(acts) == ["_cscreen", "_servo", "_click", "_cutpick"]
          and "whole stack" in note, f"{marks(acts)} {note!r}")

    # -- refusals -------------------------------------------------------------
    shut = fake_info()
    for name, kw, info, want in (
            ("container_take", {}, shut, "no screen is open"),
            ("brew", {}, brew_inv, None),
            ("brew", {"ingredient": "ghast_tear"}, brew_inv, "you carry no ghast_tear"),
            ("enchant", {"option": 3},
             dict(ench_inv, inventory=fake_info(inventory={"diamond_sword": 1,
                                                           "lapis_lazuli": 2})["inventory"]),
             "costs 3 lapis_lazuli and you carry 2"),
            ("stonecut", {"item": "granite"}, cut_inv, "you carry no granite"),
            ("container_put", {"item": "emerald"}, chest_inv, "you carry no emerald")):
        if want is None:
            continue
        c = open_cur() if info.get("isGuiOpen") else CursorState()
        acts, note = expand(name, info=info, cursor=c, **kw)
        check(f"{name} refuses cleanly: {want!r}", acts == [] and want in note, note)

    # -- the run-time splice: which cells to empty is read from the frame ------
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1}]

    def mk(tag):
        ag = WorldModelAgent(workspace=root / f"ct_{tag}", task_text="t",
                             ledger=MilestoneLedger(cfg, "t"), induction_every=0,
                             step_cap=400)
        ag.codex = FakeCodex(ag.memory.root, [
            {"actions": {"actions": [{"action": {}, "repeat": 1}]}, "message": "-"}] * 8)
        ag.start(fake_info())
        return ag

    ag = mk("take")
    frame = container_frame("chest", full=(0, 4, 13))
    ag._last_pov = frame
    ag._gui_open = True
    ag._screen = "chest"
    ag.cursor.opened({})
    ag.ledger._prev = fake_info(inventory={"iron_pickaxe": 1})
    acts, _ = expand("container_take", info=chest_inv, cursor=open_cur())
    ag.queue.extend([(acts[1], 0)])
    ag.next_action(fake_info())
    queued = marks([e for e, _ in ag.queue])
    check("_ctake queues one servo+click pair per FULL cell, then parks and checks",
          queued == ["_servo", "_click"] * 3 + ["_servo", "_ccheck"], str(queued))
    check("...aimed at the cells the frame showed full, then off them",
          [e["_servo"]["label"] for e, _ in ag.queue if "_servo" in e]
          == ["chest cell 0", "chest cell 4", "chest cell 13", "clear of the cells"],
          str([e["_servo"]["label"] for e, _ in ag.queue if "_servo" in e]))
    # The bug this pins (stage s3, run 1): a run-time splice that wrote its target into
    # the REAL cursor made every single-cell macro's servo declare arrival on tick one
    # without moving, and the click then landed wherever the pointer actually was.
    first = _gui.centre(_gui.chest_cells("chest")[0])
    check("...and the spliced entries do NOT rewrite the real cursor position, so the "
          "first servo is still steering toward its cell",
          "_servo" in ag.queue[0][0]
          and ag.queue[0][0]["_servo"]["label"] == "chest cell 0"
          and abs(ag.cursor.pos[0] - first[0]) > 2.0,
          f"{ag.cursor.pos} vs {first}")
    check("gui.cursor_park lands on body, not on a slot, for every container",
          all(not any(_vis._is_slot(container_frame(k).astype(np.float32).mean(-1),
                                    int(232 + _gui.cursor_park(k)[0] + dx),
                                    int(97 + _gui.cursor_park(k)[1] + dy))
                      for dx in (-8, 0) for dy in (-8, 0))
              for k in ("chest", "chest2", "brewing", "enchanting", "stonecutter")),
          str({k: _gui.cursor_park(k) for k in _gui.SCREEN_H}))
    check("...with quick-move clicks, so nothing rides the cursor",
          all(e["_click"]["shift"] for e, _ in ag.queue if "_click" in e))

    ag2 = mk("empty")
    ag2._last_pov = container_frame("chest")
    ag2._gui_open = True
    ag2._screen = "chest"
    ag2.cursor.opened({})
    ag2.ledger._prev = fake_info(inventory={"iron_pickaxe": 1})
    ag2.queue.extend([(expand("container_take", info=chest_inv,
                              cursor=open_cur())[0][1], 0)])
    ag2.next_action(fake_info())
    notes2 = " | ".join(ag2.memory._pending_notes)
    check("an empty chest is reported as empty and nothing is clicked",
          not ag2.queue and "is EMPTY" in notes2, f"{len(ag2.queue)} {notes2}")

    ag3 = mk("wrong")
    ag3._last_pov = container_frame("brewing")
    ag3._gui_open = True
    ag3._screen = "brewing"
    ag3.cursor.opened({})
    ag3.queue.extend([(e, 0) for e in expand("container_take", info=chest_inv,
                                             cursor=open_cur())[0]])
    ag3.next_action(fake_info())
    notes3 = " | ".join(ag3.memory._pending_notes)
    check("a chest macro on the brewing screen is refused, naming both screens",
          "needs the chest or the chest2 screen" in notes3 and "brewing" in notes3,
          notes3)

    ag4 = mk("full")
    ag4._last_pov = container_frame("chest", full=(0, 1, 2))
    ag4._gui_open = True
    ag4._screen = "chest"
    ag4.cursor.opened({})
    ag4.ledger._prev = fake_info(inventory={f"item_{i}": 1 for i in range(36)})
    ag4.queue.extend([(expand("container_take", info=chest_inv,
                              cursor=open_cur())[0][1], 0)])
    ag4.next_action(fake_info())
    notes4 = " | ".join(ag4.memory._pending_notes)
    check("a full inventory stops the take and says so",
          "inventory is FULL" in notes4, notes4)

    # -- the [GRID] rows ------------------------------------------------------
    ag5 = mk("grid")
    ag5._gui_open = True
    ag5._last_pov = container_frame("chest", full=(0, 4, 26))
    ag5._screen = "chest"
    line = ag5._grid_line()
    check("[GRID] names the full chest cells and the total",
          "chest cells [0,4,26]" in line and "3 of 27" in line, line)
    ag5._last_pov = container_frame("brewing", full=(0, 2))
    ag5._screen = "brewing"
    line = ag5._grid_line()
    check("[GRID] names the brewing cells that hold something",
          "brewing [fuel,bottle0]" in line, line)
    ag5._last_pov = container_frame("stonecutter", full=(0,))
    ag5._screen = "stonecutter"
    line = ag5._grid_line()
    check("[GRID] reports the stonecutter input and the recipe buttons drawn",
          "stonecutter [in]" in line and "recipe button" in line, line)

    # -- close semantics ------------------------------------------------------
    check("chest, double chest and brewing keep their contents across a close; the "
          "enchanting table and the stonecutter do not",
          {"chest", "chest2", "brewing", "furnace"} <= _macros.KEEPS_CONTENTS
          and not ({"enchanting", "stonecutter", "anvil"} & _macros.KEEPS_CONTENTS),
          str(sorted(_macros.KEEPS_CONTENTS)))
    ag6 = mk("close")
    ag6.cursor.opened({"coal": 30})
    ag6.cursor.off_inventory({})
    ag6._cur_inv = {}
    ag6._screen = "chest"
    allowed = ag6._guard_close({"inventory": 1}, lambda: {})
    check("closing a chest with items in it is allowed, not refused",
          allowed == {"inventory": 1}, str(allowed))

    # -- the model-facing documentation ---------------------------------------
    for name in ("container_take", "container_put", "brew", "brew_take", "enchant",
                 "stonecut"):
        p = REGISTRY.get(name)
        check(f"docs: {name} is offered with preconditions",
              p is not None and len(p.doc) > 40 and "use_until_gui" in p.preconditions,
              name)
    check("docs: no anvil macro is registered (renaming needs a keyboard)",
          "anvil" not in REGISTRY)

def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_memory(root)
        test_milestones()
        test_graph()
        test_discipline(root)
        test_gui()
        test_actions()
        test_cursor()
        test_gui_feedback(root)
        test_loop(root)
        test_closed_loop(root)
        test_logbook(root)
        test_harness_guards(root)
        test_escalation(root)
        test_stow_and_sweep(root)
        test_wmlite(root)
        test_direct(root)
        test_task_knowledge()
        test_systemics(root)
        test_seed_memory(root)
        test_governor(root)
        test_playbook(root)
        test_inventory_encoding()
        test_hit_reflex(root)
        test_dark_tunnel(root)
        test_harness_nodes(root)
        test_relay_semantics(root)
        test_harvest(root)
        test_lava_guard(root)
        test_find_lava(root)
        test_world(root)
        test_nether(root)
        test_nether2(root)
        test_end(root)
        test_containers(root)
        test_entities(root)
    print(f"\n{'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all checks passed'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
