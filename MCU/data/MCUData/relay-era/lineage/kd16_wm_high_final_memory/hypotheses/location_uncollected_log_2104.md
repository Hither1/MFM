# location_uncollected_log_2104

- kind: location
- status: active
- confidence: 0.65
- created_step: 2400
- updated_step: 2400
- depends_on: resource_reset_three_logs

## Statement

A spruce-log item may remain near the step-2104 break around (-2999.36,65,-5568.29), but it was not collected by the immediate sweep and should receive at most one short recovery attempt before switching to a fresh trunk.

## Evidence

- mine_block spruce_log fired at 2104 from that pose; no later pickup event exists and collect_drops through 2176 found nothing.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
