# state_inventory_0600

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 600
- updated_step: 600
- depends_on: resource_reset_three_logs, goal_mine_log

## Statement

At live step 600 the GUI is closed; the player is at (-3004.79,68.00,-5566.27), holds exactly one spruce log in zero-based hotbar slot 0, and has full health and hunger.

## Evidence

- Step-600 frame shows empty hotbar and full bars; events.jsonl has no pickup entries.
- Step-600 frame plus step-593 INV and step-597 GRID/CURSOR resolve the live contents; current events contain no plank craft.
- Current events record pickup spruce_log +1 at step 375 and no later inventory event; the attached step-600 frame shows the closed world view, one log in the first hotbar slot, and full bars; the latest map row gives the pose.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
