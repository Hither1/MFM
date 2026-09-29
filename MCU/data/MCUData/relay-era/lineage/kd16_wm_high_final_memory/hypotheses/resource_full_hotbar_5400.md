# resource_full_hotbar_5400

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 5400
- updated_step: 6600
- depends_on: state_inventory_5400, goal_mine_iron_ore, state_inventory_route_6000

## Statement

The former full-hotbar blocker is resolved: placing the furnace at step 6473 emptied zero-based slot 6 before the visible iron is mined.

## Evidence

- All nine hotbar slots are visibly occupied, while slots 3 and 6 contain placeable portable workstations and no inventory event records iron or another free player slot.
- Frame 6000 visibly fills every hotbar slot, while slots 3 and 6 contain placeable workstations.
- furnace -1 and use_item furnace at step 6473 agree with the empty seventh hotbar slot in frame 6600.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
