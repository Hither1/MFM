# resource_free_iron_slot_5508

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 5508
- updated_step: 6000
- depends_on: goal_mine_iron_ore

## Statement

The dirt x14 stack was deliberately dropped at y57 at step 5520, freeing an inventory slot; the wooden pick was later recovered during descent.

## Evidence

- The step-5508 state reports 0 slots free and dirt x14 in hotbar slot 2; guarded force-close is documented to drop the cursor-held stack.
- INV dirt -14 and forced-close note occur at 5517/5520; pickup wooden_pickaxe occurs at 5701.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
