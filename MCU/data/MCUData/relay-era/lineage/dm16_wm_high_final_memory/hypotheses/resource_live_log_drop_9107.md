# resource_live_log_drop_9107

- kind: resource
- status: refuted
- confidence: 0.05
- created_step: 9167
- updated_step: 9312
- depends_on: location_live_fuel_spruce_8970

## Statement

The item from the step-9107 log break is no longer a viable resource: two directed sweeps after freeing inventory capacity and revisiting within about 0.5 block produced no spruce-log pickup, so it should be retired in favor of fresh harvesting.

## Evidence

- The block break is event-verified only 60 ticks ago, no pickup event followed, and prior live ingot recovery established that freeing a unique-stack slot before revisiting a fresh drop enables pickup.
- No pickup event follows the break; steps 9175-9200 consume the last dirt, approach the block column, and end at (-3000.11,67,-5570.60) without inventory gain.
- No spruce_log pickup follows the verified step-9107 break through step 9312. Steps 9172-9252 freed capacity, returned to the exact column, and swept for 72 ticks without pickup; the later sweep only recovered dirt.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
