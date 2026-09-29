# state_cursor_planks_1800

- kind: state
- status: refuted
- confidence: 1.00
- created_step: 1800
- updated_step: 1800
- depends_on: goal_wooden_pickaxe

## Statement

Refuted for this reset's step 1800: no GUI is open and no planks are on the cursor; the player is attacking a spruce log with an empty selected slot.

## Evidence

- craft_item spruce_planks +4 fired at step 1799; step_1800.png shows an empty 2x2 grid and the plank stack attached to the pointer over hotbar slot 3.
- Verified stick craft at step 1842 and wooden-pickaxe craft at step 1956 account for the plank output; current spruce_planks x3 are banked in hotbar slot 0.
- Frame 1800 shows the world view and empty selected slot; events have no plank craft after step 1391.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
