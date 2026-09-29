# resource_wooden_pickaxe_secure

- kind: resource
- status: confirmed
- confidence: 0.98
- created_step: 1175
- updated_step: 1800
- depends_on: goal_wooden_pickaxe

## Statement

The live wooden pickaxe is secured in zero-based hotbar slot 1 with about 35 of 59 uses remaining at step 1800.

## Evidence

- 29 uses at 2245 followed by two coal breaks and no break event.
- events.jsonl contains 44 use_item wooden_pickaxe events and no break_item event through step 3000.
- Four use_item events at 3053, 3082, 3212, and 3241 raise the verified count from 44 to 48; no break_item event exists.
- Current events contain no wooden_pickaxe craft and frame 600 shows only logs and table.
- The step-781 craft event proves creation, the active recipe grid cleared, and the frame visibly shows the pickaxe at the cursor over empty hotbar slot 1; this turn tests the deposit via an inventory delta.
- Authoritative STATE at step 1016 lists wooden_pickaxe x1, Held wooden_pickaxe (55/59 uses left), and the GUI is closed.
- Held state reported 55/59 at step 1016; seven later stone-use events occurred through 1194 with no break_item event; frame 1200 shows the selected tool.
- Step 1649 reported 36 uses; one later stone break occurred at 1699 and no break_item event exists. Frame 1800 shows the tool.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
