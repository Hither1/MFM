# state_live_inventory_ep0000_7800

- kind: state
- status: stale
- confidence: 1.00
- created_step: 7800
- updated_step: 8400
- depends_on: state_current_furnace_smelt_ep0000_7070, goal_iron_ingot, resource_current_wood_fuel_ep0000_6000, state_inventory_8400

## Statement

The step-7800 inventory snapshot is historical and superseded by the iron-pick craft/bank plus three later diorite breaks; use state_inventory_8400 for the live inventory.

## Evidence

- Event and inventory deltas from the verified step-7200 snapshot reconcile with pickup dirt +1/iron_ingot +1 at 7354 and the later lift/rebank at 7744/7795; step-7800 hotbar and furnace crops agree.
- events verify iron_pickaxe at 7905 and diorite breaks at 8100/8118/8136; frame step_8400 is newer.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
