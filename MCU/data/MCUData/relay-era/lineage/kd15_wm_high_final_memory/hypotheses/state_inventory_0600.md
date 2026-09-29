# state_inventory_0600

- kind: state
- status: refuted
- confidence: 1.00
- created_step: 600
- updated_step: 1200
- depends_on: resource_reset_three_logs

## Statement

The prior claim that the step-600 GUI held logs and a full plank output is false for this reset; the GUI was closed, the hotbar was empty, and the first pickup occurred at step 661.

## Evidence

- Step-600 frame shows empty hotbar and full bars; events.jsonl has no pickup entries.
- Step-600 frame plus step-593 INV and step-597 GRID/CURSOR resolve the live contents; current events contain no plank craft.
- Step-600 frame shows a closed GUI and empty hotbar; events contains no pickup before step 661.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
