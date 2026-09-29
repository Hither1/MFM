"""Stage 0: the measured cursor while a stack is HELD.

The s1 table craft banked nothing: the servo declared arrival 9 px left and 5 px below
the target slot with the crafting table riding the cursor. This drives cursor_to_slot
to a series of slots with and without a held stack and reports, per move, the servo
verdict counters (ok / unverified / gave up), the frame-measured position at the end
of the move and what `over=` says -- so the failure is measured, not guessed.
"""
from __future__ import annotations

from mcu_worldmodel import gui
from mcu_worldmodel.stages.rig import SPAWN, Rig, main_guard


def P(name: str, **args):
    return {"procedure": name, "args": args}


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.clear()
    rig.give("oak_planks", 8)
    rig.idle(10)
    rig.run([P("open_inventory")], label="open")

    def probe(tag: str, slots: list[int]) -> None:
        for s in slots:
            r = rig.run([P("cursor_to_slot", slot=s)], label=f"{tag} -> slot {s}")
            cx, cy = gui.centre(gui.slot_topleft(s))
            pos = rig.agent.cursor.pos
            off = ((pos[0] - cx) ** 2 + (pos[1] - cy) ** 2) ** 0.5 if pos else 99.0
            rig.frame(f"s0_{tag}_slot{s}")
            rig.log(f"   measured {pos} target ({cx:.0f},{cy:.0f}) off {off:.1f}px "
                    f"over={rig.agent.cursor.over()} stats={r['stats']}")
            rig.check(f"{tag}: slot {s} within 3px", off <= 3.0, f"{off:.1f}px {r['stats']}")

    probe("empty", [1, 5, 8, 20, 35, 2])
    r = rig.run([P("cursor_to_slot", slot=0), P("gui_click")], label="lift planks")
    rig.check("planks lifted (off-inventory)",
              rig.agent.cursor.off_inventory(rig.inv()).get("oak_planks", 0) == 8,
              rig.agent.cursor.line(rig.inv()))
    probe("held", [1, 5, 8, 20, 35, 2, 9])
    r = rig.run([P("gui_click")], label="bank at slot 9")
    rig.check("held stack banked in slot 9",
              not rig.agent.cursor.off_inventory(rig.inv()), rig.agent.cursor.line(rig.inv()))
    rig.run([P("close_inventory")], label="close")


if __name__ == "__main__":
    main_guard(stage)
