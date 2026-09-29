# resource_diamond_capacity_coal_10634

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 10634
- updated_step: 10658
- depends_on: resource_diamond_capacity_andesite_10157

## Statement

Coal x3 was force-dropped behind the westward route at step 10652, restoring the pickup slot needed for a diamond drop; do not backtrack east across the dropped coal.

## Evidence

- Step 10634 reports [INV] coal +3, STATE Inventory (0 slots free), and hotbar.2=coalx3 after 9.2 blocks of westward advance.
- The step-10652 runner note states that coal x3 left the cursor and became a floor item entity; step 10658 still holds position while facing west, so westward continuation moves away from it.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
