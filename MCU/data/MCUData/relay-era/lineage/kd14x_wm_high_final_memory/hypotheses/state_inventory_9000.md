# state_inventory_9000

- kind: state
- status: refuted
- confidence: 1.00
- created_step: 9000
- updated_step: 9000
- depends_on: goal_iron_pickaxe

## Statement

The prior step-9000 inventory claim (stone pick 46 uses, coal, torches, no iron) is incompatible with this live run and must not guide actions; at step 9000 the verified iron pick has just been crafted and remains on the open-table cursor.

## Evidence

- Step-9000 hotbar and HUD show all stacks and two blanks; events count 85 stone-pick uses since craft and contain no iron/diamond events.
- events verify iron_pickaxe craft at 8998, 96 stone-pick uses imply 35/131 uses remaining, and the live GUI/frame do not support the claimed coal/torch inventory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
