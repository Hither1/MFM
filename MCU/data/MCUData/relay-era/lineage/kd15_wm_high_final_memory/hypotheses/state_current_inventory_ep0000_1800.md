# state_current_inventory_ep0000_1800

- kind: state
- status: active
- confidence: 1.00
- created_step: 1800
- updated_step: 1800
- depends_on: goal_wooden_pickaxe, goal_crafting_table

## Statement

At step 1800 the live hotbar contains crafting_table x1 in slot 0 and spruce_log x1 in slot 1; slot 2 is selected and empty, GUI closed, with no tools or mined materials.

## Evidence

- The live frame shows dirt x4, sticks x2, and the selected wooden pick. Events verify exactly four pick uses after its craft and contain no stone/cobblestone event through step 1800.
- At step 2400 the frame and event accounting show dirt x1, cobblestone x6, sticks x2, wooden pickaxe with 41 uses left, and granite x4.
- Frame 1800 visibly shows the two stacks; current events account for the table craft/banking and the log pickup, and contain no tool, stone, or cobblestone event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
