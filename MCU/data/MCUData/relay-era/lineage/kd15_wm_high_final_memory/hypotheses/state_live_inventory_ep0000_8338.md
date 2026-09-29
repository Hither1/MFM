# state_live_inventory_ep0000_8338

- kind: state
- status: stale
- confidence: 1.00
- created_step: 8338
- updated_step: 10138
- depends_on: goal_iron_ingot, goal_furnace, goal_iron_pickaxe

## Statement

The step-8338 full-inventory snapshot is stale; the furnace was placed, materials changed, and the live step-10138 inventory has the iron-pick ingredients plus one free slot.

## Evidence

- Magnified step_8338 hotbar shows all nine stacks and counts; event accounting after step 7092 contains no consumption of the ingot, ore, or furnace, while pillar events reconcile cobblestone to x46.
- Furnace placement at 8528 and event/inventory transitions through 10138 supersede this snapshot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
