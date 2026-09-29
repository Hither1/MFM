# resource_current_lighting_kit

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 4800
- updated_step: 10800
- depends_on: resource_early_logs, goal_furnace, goal_stone_pickaxe, resource_surface_wood_after_furnace

## Statement

The former coal/torch kit was dropped in lava at death and no longer exists in live inventory.

## Evidence

- Frame 8400 shows torches x7, no use_item torch occurs after step 3925, and craft_item iron_pickaxe at 8008 accounts for the two sticks.
- Frame 9000 shows torches x7; no use_item torch occurs after 3925; coal pickups fire at 8850 and 8871; iron-pick crafting consumed the last two sticks.
- Frame 9000 showed seven torches; use_item torch fired at steps 9114 and 9488; the frame-9600 hotbar visibly shows torch x5.
- Step-9890 events record use_item torch +1, and step-9894 STATE reports torch x4 and coal x2.
- Frame/STATE at 9894 reports torch x4 and coal x2; events through 10200 contain no later torch use or stick acquisition.
- Step-10594 STATE explicitly reports torch x2 and coal x2, with no sticks. Events at 10424/10426 record two torch uses, but one torch was picked back up at 10460 after the support was mined.
- Authoritative step-10604 STATE reports torch x1 and zero free slots; events record use_item torch at 10602 and 10604.
- Step-10624 deltas remove coal x2 and every stack; frame 10800 has an empty hotbar.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
