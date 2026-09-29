# cobblestone_drop_pit_2890

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 3335
- depends_on: state_stone_below_pit_2443, resource_free_slot_for_cobble_2543

## Statement

The visible drops in the lower stone pocket were three cobblestone items and were collected at step 3326.

## Evidence

- step_2890.png clearly shows a grey cobblestone entity to the right of a dirt entity; no later pickup:cobblestone event is recorded.
- A targeted 24-tick sweep through the estimated entity position at steps 3064-3088 picked up nothing, and the current frame shows no loose cobblestone.
- Ground-truth events record two mine_block stone events at steps 3152 and 3181. The following sweep moved toward the table and stopped on pickup stick, with no pickup cobblestone event, so both fresh drops should remain at the break face.
- A 4x zoom of step_3282.png clearly shows several grey-white cobblestone item sprites on the stone floor beyond the centered dirt block; no pickup:cobblestone event has occurred.
- events/events.jsonl records pickup:cobblestone +3 at step 3326 and current inventory contains cobblestone x3.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
