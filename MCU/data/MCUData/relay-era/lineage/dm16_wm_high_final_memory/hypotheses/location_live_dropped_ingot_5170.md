# location_live_dropped_ingot_5170

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 5200
- updated_step: 5211
- depends_on: goal_mine_iron_ore, goal_furnace

## Statement

The furnace-side ingot dropped at step 5170 was successfully recollected at the same pose after freeing a slot, satisfying iron_ingot at step 5211; no dropped ingot remains to recover.

## Evidence

- craft_item iron_ingot fired at 5160; INV iron_ingot +1 at 5164 and -1 at 5167; force-close at 5170; no pickup event through 5200; STATE reports 0 slots free.
- The step-5211 milestone and pickup event occurred without movement from (-2993.30,54.00,-5564.70), and STATE now includes iron_ingot x1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
