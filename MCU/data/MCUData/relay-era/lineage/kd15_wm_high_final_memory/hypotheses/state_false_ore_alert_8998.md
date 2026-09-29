# state_false_ore_alert_8998

- kind: state
- status: confirmed
- confidence: 0.98
- created_step: 9000
- updated_step: 9000
- depends_on: resource_diamond_pickup_slot_8979, goal_mine_diamond_ore

## Statement

The step-8998 iron-like-speckles alert is a false positive caused by the floating dropped dirt item, not an ore block face.

## Evidence

- A 4x crop around reported pixel (342,204) shows an orange-brown item sprite floating over plain grey shaft blocks; no mine_block event occurred after the alert.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
