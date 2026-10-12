"""Give MinecraftSim a real crafting action.

`HumanSurvival.create_actionables()` installs keyboard, camera, chat, voxel and mob
handlers -- and nothing else. The `CraftAction`, `CraftNearbyAction`, `SmeltItemNearby`,
`EquipAction` and `PlaceBlock` handlers exist in the tree, fully implemented on the Python
side, and are simply never wired in. So `MinecraftSim` cannot craft, which caps both
long-horizon tasks near their second milestone: 5 of the diamond task's 10 milestones and
9 of the dragon's 24 are `craft_item`.

This module adds them back.

**Crafting cannot be fixed this way, and this module is the evidence.** Installing the
handlers works on the Python side -- the action space gains `craft`/`nearbyCraft`/
`nearbySmelt`/`place`/`equip` -- but the first step then fails, because the engine has no
such command. `com.minerl.multiagent.env.EnvServer` is the dispatcher, and its complete
verb vocabulary is:

    attack back camera chat drop dwheel equip forward hotbar
    inventory jump left pickItem right sneak sprint swapHands use ESC

`craft`, `nearbyCraft`, `nearbySmelt` and `place` are absent. Sending one produces

    [EnvServerSocketHandler/ERROR]: Error while processing commands
    java.lang.NumberFormatException: For input string: "none"

-- the engine parsing the item name as a number -- and the step returns nothing, so the
Python side dies in `struct.unpack` on a None reply. The Malmo `Schemas` classes in the jar
(including a `NearbyCraftCommand` enum containing `craftNearby`) are generated XML bindings
with no implementation behind them; the jar has no `MissionHandlers` package at all, not
even for the commands that do work.

So **crafting has to go through the inventory GUI**, which is what `procedures.py` is for,
and which is confirmed working: a run reached the `crafting_table` milestone at step 514
using `cursor_to` / `gui_click` / `craft_2x2`.

What this module *does* deliver is the four verbs the engine implements and the spec simply
never installs -- `equip` above all, which lets a tool be selected by name instead of by
hunting hotbar slots. `probe()` measures each one against a live engine rather than assuming.

Run `python -m mcu_worldmodel.craft_env` on a compute node.
"""
from __future__ import annotations

import os

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

from loguru import logger  # noqa: E402

# `equip` is the one item-list handler the engine implements. The list is kept to what the
# two tasks need rather than all 976 items: the handler builds an Enum space and mission XML
# enumerating every entry. 'none' and 'other' are required by ItemListAction.
EQUIP_ITEMS = [
    "none", "other",
    "wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "diamond_pickaxe",
    "wooden_axe", "stone_axe", "iron_axe", "diamond_axe",
    "wooden_sword", "stone_sword", "iron_sword", "diamond_sword",
    "wooden_shovel", "stone_shovel", "iron_shovel", "diamond_shovel",
    "crafting_table", "furnace", "torch", "flint_and_steel", "bucket",
    "cobblestone", "dirt", "oak_planks", "coal", "iron_ore", "diamond",
    "bow", "arrow", "ender_eye", "obsidian",
]

#: Keyboard verbs the engine implements that `HumanSurvival` does not install. Adding them
#: is free -- they are the same `KeybasedCommandAction` mechanism as `forward` and `attack`,
#: and the engine already has a branch for each.
#:
#: `drop` and `swapHands` matter for inventory work; `pickItem` less so. `ESC` is
#: deliberately NOT added: the harness, not the agent, decides when an episode ends, and
#: an agent that can end its own episode will end it early. Here the episode ends on the
#: step budget and the score is milestone depth, so handing the agent a quit button can
#: only lose milestones.
#: Only `drop`. `pickItem` is already installed by the base spec (it is in
#: SIMPLE_KEYBOARD_ACTION), and adding it again trips env_spec.reset's duplicate-name
#: assertion; `swapHands` and `ESC` have no INVERSE_KEYMAP entry, so there is no key to
#: bind even though the engine implements the verbs.
EXTRA_KEYBOARD = {"drop": None}

#: Action keys added, with the value each takes when idle. Every one must be sent on every
#: step: MineRL builds its action space from the installed actionables, and a missing key is
#: a KeyError inside `env.step`, not a defaulted no-op.
ADDED_ACTION_KEYS = {"drop": 0}

#: Already in the real action space, though `entry.py`'s hardcoded `action_type="env"`
#: dict does not advertise them. `chat` is deliberately never surfaced to the agent: it
#: would let a from-scratch run `/give` itself the entire tech tree.
ALREADY_PRESENT_UNADVERTISED = ("pickItem", "chat", "mobs", "voxels")

#: Verbs the engine does NOT implement. Listed so nothing tries to add them again.
UNSUPPORTED_BY_ENGINE = ("craft", "nearbyCraft", "nearbySmelt", "place")

#: Implemented by the engine but NOT usable through MineRL's handlers: the engine parses
#: this command's argument as a number, while `EquipAction` sends an item name. Installing
#: it makes `reset()` throw, because `MinecraftSim.reset` sends a full `no_op()` (carrying
#: `equip none`) for its empty frames. Selecting a tool therefore stays a `hotbar.N` press.
NUMERIC_ARG_ONLY = ("equip",)


def extended_human_survival():
    """`HumanSurvival` plus the verbs the engine supports and the spec leaves out."""
    from minestudio.simulator.minerl.herobraine.env_specs.human_survival_specs import (
        HumanSurvival,
    )
    from minestudio.simulator.minerl.herobraine.hero import handlers as H
    from minestudio.simulator.minerl.herobraine.hero.mc import INVERSE_KEYMAP

    class ExtendedHumanSurvival(HumanSurvival):
        """Subclassed rather than edited in place, so anything else constructing a plain
        `HumanSurvival` -- MCU's own `run_task.py`, and the VPT/STEVE-1 baselines whose
        action space must not change or the comparison stops being one -- is untouched."""

        def create_actionables(self):
            actionables = super().create_actionables()
            # EquipAction is NOT installed. The engine has an `equip` branch, but it
            # parses the argument as a number, so the item name `none` that
            # `env.action_space.no_op()` supplies throws
            # `NumberFormatException: For input string: "none"` on the very first step --
            # and `MinecraftSim.reset()` sends a full no_op for its empty frames, so the
            # env cannot even reset. Measured twice; see the module docstring.
            existing = {a.to_string() for a in actionables}
            for verb in EXTRA_KEYBOARD:
                if verb in existing:
                    # env_spec.reset asserts actionable names are unique, and the failure
                    # is a bare AssertionError with no indication of which name collided.
                    logger.info(f"[craft_env] {verb!r} already installed; skipping")
                    continue
                key = INVERSE_KEYMAP.get(verb)
                if key is None:
                    logger.warning(f"[craft_env] no keymap entry for {verb!r}; skipped")
                    continue
                actionables.append(H.KeybasedCommandAction(verb, key))
            return actionables

    return ExtendedHumanSurvival


def patch_minecraft_sim() -> None:
    """Point `MinecraftSim` at the crafting-enabled spec.

    Monkeypatching the name `entry.HumanSurvival` rather than editing entry.py: the
    constructor looks the class up in its own module globals, so rebinding it there is
    enough, and it leaves the vendored file untouched.
    """
    from minestudio.simulator import entry

    if getattr(entry, "_mcu_worldmodel_extended_patched", False):
        return
    entry.HumanSurvival = extended_human_survival()
    entry._mcu_worldmodel_extended_patched = True
    logger.info("[craft_env] MinecraftSim patched: %s" % ", ".join(ADDED_ACTION_KEYS))


def probe(steps_per_phase: int = 10) -> dict:
    """Does the engine honour the added verbs?

    Measured, not assumed. `equip` is checked against `info['equipped_items']['mainhand']`,
    which is the game's own report of what is in hand -- not the inventory, and not the
    frame. A control craft attempt is included so the negative result stays on the record
    next to the positive one.
    """
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim

    result: dict = {"mission_started": False, "drop_worked": None, "error": None}
    sim = None
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360), callbacks=[])
        keys = set(sim.env.action_space.spaces.keys())
        result["action_space_added"] = sorted(keys & set(ADDED_ACTION_KEYS))
        result["craft_absent_as_expected"] = not (keys & set(UNSUPPORTED_BY_ENGINE))

        obs, info = sim.reset()
        result["mission_started"] = True

        def noop():
            # A *minimal* dict, not `env.action_space.no_op()`. `_process_action` skips
            # keys that are absent, so omitting `equip` keeps `equip none` off the wire --
            # which is exactly what put `craft none` in front of the engine's number parser
            # on every tick of the previous probe.
            return {"attack": 0, "forward": 0, "camera": [0.0, 0.0]}

        # Two distinguishable tools, so "equip changed the mainhand" cannot be confused
        # with "the mainhand happened to already hold it".
        sim.env.execute_cmd("/give @p minecraft:iron_pickaxe 1")
        sim.env.execute_cmd("/give @p minecraft:diamond_sword 1")
        for _ in range(steps_per_phase):
            obs, _, _, _, info = sim.step(noop())

        def mainhand():
            eq = info.get("equipped_items") or {}
            mh = eq.get("mainhand")
            if isinstance(mh, dict):
                return str(mh.get("type", "?"))
            return str(mh)

        # `drop` is the one verb this patch adds. Held for a few ticks, then checked
        # against the inventory: the engine reports what actually left the player's hands.
        def count(item):
            n = 0
            for slot in (info.get("inventory") or {}).values():
                if isinstance(slot, dict) and slot.get("type") == item:
                    n += int(slot.get("quantity", 0))
            return n

        # Put the sword in hand first. `/give` fills the first free inventory slot, which
        # is a hotbar slot on an empty inventory, but nothing is *selected* until a hotbar
        # key is pressed -- and `drop` drops the held item, so without this the probe
        # measures dropping air. (The first attempt did exactly that: mainhand="air",
        # sword count unchanged, which reads as a failure and was not one.)
        sel = noop(); sel["hotbar.1"] = 1
        obs, _, _, _, info = sim.step(sel)
        for _ in range(4):
            obs, _, _, _, info = sim.step(noop())
        result["mainhand_before_drop"] = mainhand()

        # Count the item that is actually HELD, not a fixed name. `/give` fills slots in
        # its own order, so hardcoding `diamond_sword` measured an item sitting in slot 2
        # that `drop` was never going to touch -- and reported a working drop as a failure.
        held = mainhand()
        before = count(held)
        act = noop()
        act["drop"] = 1
        obs, _, _, _, info = sim.step(act)
        for _ in range(steps_per_phase):
            obs, _, _, _, info = sim.step(noop())
        after = count(held)
        result.update(held_item=held, held_before=before, held_after=after,
                      mainhand_after=mainhand(),
                      drop_worked=(after < before or mainhand() != held))
    except Exception as e:      # a probe reports, it does not raise
        logger.exception("[craft_env] probe failed")
        result["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass
    return result


if __name__ == "__main__":
    import json

    out = probe()
    print("\n=== ACTION-SPACE PROBE ===")
    print(json.dumps(out, indent=2, default=str))
    print("\nmission started :", out.get("mission_started"))
    print("equip honoured  :", out.get("equip_worked"),
          f"({out.get('mainhand_before')} -> {out.get('mainhand_after')})")
    print("craft/smelt/place: not offered -- the engine has no such command "
          "(see the module docstring)")
