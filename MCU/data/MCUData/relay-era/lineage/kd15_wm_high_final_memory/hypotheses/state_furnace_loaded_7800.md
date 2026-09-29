# state_furnace_loaded_7800

- kind: state
- status: stale
- confidence: 1.00
- created_step: 7800
- updated_step: 4800
- depends_on: location_furnace_worksite_4390, resource_live_iron_vein_6296, goal_mine_iron_ore, goal_furnace

## Statement

The loaded-furnace state belongs to another trajectory; no furnace has been crafted or placed in the live reset through step 4800.

## Evidence

- Logs 7765-7781 record iron_ore -3, input placement, spruce_planks -3 then +3; GRID has input and frame 7800 shows active flames with empty output.
- Steps 8001-8007 right-clicked two planks into furnace fuel and step 8012 banked the one-plank remainder. The force-close warning aggregates furnace-contained input/fuel, which persist across closing; the attached step-8062 frame shows the furnace still burning.
- GRID showed furnace [in,fuel,out] at 8263, inventory gained iron_ingot at 8284, and about 396 ticks have elapsed since two planks were loaded around step 8004.
- Current inventory is iron_ingot x1. The 8269 output click produced no cursor item or inventory delta; step 8275 instead removed the existing inventory ingot, and 8284 restored it elsewhere. Smelting has had over 400 additional ticks.
- Current events contain no craft_item furnace, use_item furnace, or iron-ingot pickup.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
