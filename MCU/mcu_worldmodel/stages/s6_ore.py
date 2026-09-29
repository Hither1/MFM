"""Stage 6: the ore sentinel against real ore faces in a torch-lit tunnel.

A stone tunnel at y=12 with a diamond ore (then an iron ore) set in the end wall a few
blocks ahead: `strip_mine` must stop with the sentinel's [NOTE] naming the KIND, the
flag-time frame saved; `aim_at_ore` then centres the crosshair and `mine_ahead` breaks
the block the note pointed at (mine_block.diamond_ore / iron_ore from the statistics).
The bands were measured on this engine's frames (probe_diamond2, 2026-09-03); this is
the loop that has to convert them.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 12, -5600


def tunnel(rig: Rig, ore: str, at: int) -> None:
    """Fresh stone around, a 3x3 tunnel 12 long along +z, torches on the floor, the
    ore at eye level in the end wall `at` blocks ahead of the avatar."""
    rig.fill(X - 4, Y - 3, Z - 4, X + 4, Y + 6, Z + 16, "stone")
    rig.fill(X - 1, Y, Z, X + 1, Y + 2, Z + 12, "air")
    rig.fill(X - 1, Y, Z + at, X + 1, Y + 2, Z + at, "stone")
    rig.setblock(X, Y + 1, Z + at, ore)
    for tz in (Z + 1, Z + at - 1):
        rig.setblock(X - 1, Y, tz, "torch")
        rig.setblock(X + 1, Y, tz, "torch")
    rig.tp(X + 0.5, Y, Z + 0.5, yaw=0, pitch=0)
    rig.idle(10)


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 6000")
    rig.cmd("/gamemode survival")
    rig.clear()
    rig.give("iron_pickaxe", 1)
    rig.give("torch", 16)
    rig.run([P("equip_hotbar", slot=1)], label="equip")
    for ore, at in (("diamond_ore", 5), ("iron_ore", 5)):
        kind = ore.split("_")[0]
        tunnel(rig, ore, at)
        rig.frame(f"s6_{kind}_before")
        cs0 = dict(rig.agent.cursor_stats)
        r = rig.run([P("strip_mine", length=40)], label=f"strip_mine toward {ore}",
                    max_ticks=400)
        flagged = rig.agent.cursor_stats.get("ore_flagged", 0) - cs0.get("ore_flagged", 0)
        rig.check(f"{kind}: strip_mine stops on the sighting (ore_flagged +1)",
                  flagged == 1, f"flagged={flagged} ticks={r['ticks']}")
        rig.check(f"{kind}: the [NOTE] names the kind",
                  any(f"{kind}-ore-like speckles" in n for n in r["notes"]), r["notes"][-2:])
        if kind == "diamond":
            rig.check("diamond: counted in ore_flagged_diamond",
                      rig.agent.cursor_stats.get("ore_flagged_diamond", 0) == 1,
                      rig.agent.cursor_stats.get("ore_flagged_diamond"))
        rig.frame(f"s6_{kind}_flag")
        r2 = rig.run([P("aim_at_ore", ticks=40)], label="aim_at_ore", max_ticks=60)
        rig.check(f"{kind}: aim_at_ore walks up to the face and hands over aimed",
                  any(("walked" in n) and ("mine_ahead" in n) for n in r2["notes"]),
                  r2["notes"])
        rig.frame(f"s6_{kind}_aimed")
        s0 = rig.stats()
        r3 = rig.run([P("mine_ahead", n=120)], label="mine_ahead", max_ticks=200)
        d = rig.stat_delta(s0, rig.stats())
        rig.check(f"{kind}: mine_ahead breaks the ore (mine_block.{ore} +1)",
                  d.get(f"mine_block.{ore}") == 1.0, d)
        rig.frame(f"s6_{kind}_after")
    rig.ensure_closed()


if __name__ == "__main__":
    main_guard(stage)
