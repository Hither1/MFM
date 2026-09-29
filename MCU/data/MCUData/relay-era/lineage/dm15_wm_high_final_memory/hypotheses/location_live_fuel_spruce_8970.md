# location_live_fuel_spruce_8970

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 8970
- updated_step: 9200
- depends_on: resource_emergency_spruce_10794

## Statement

Natural spruce block centre (-3000.5,67.5,-5570.5) is current-prefix verified by the step-9107 break; the block site is permanent, while its uncollected drop is this-run-only.

## Evidence

- The natural block and approach geometry were independently verified in the same seed; current-prefix spruce-log breaks are limited to the pond-side tree and the separate grove tree near x=-3008, so this x=-3000.5 trunk has no live break event.
- events/events.jsonl records mine_block spruce_log at step 9107 from the exact targeted face. The following 60-tick sweep produced no pickup, while authoritative STATE reports zero free slots and a disposable dirt x1 stack.
- events/events.jsonl line 474 records mine_block spruce_log at step 9107 from the targeted face; no pickup follows through 9200. This removes the stale future-trajectory dependency.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
