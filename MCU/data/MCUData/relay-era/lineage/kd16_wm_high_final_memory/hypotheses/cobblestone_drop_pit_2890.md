# cobblestone_drop_pit_2890

- kind: location
- status: stale
- confidence: 0.10
- created_step: 3000
- updated_step: 3000
- depends_on: state_stone_below_pit_2443, resource_free_slot_for_cobble_2543

## Statement

Retired as future-branch contamination; no live step-3000 event or frame establishes the claimed three-drop pit or a step-3326 collection.

## Evidence

- step_2890.png clearly shows a grey cobblestone entity to the right of a dirt entity; no later pickup:cobblestone event is recorded.
- A targeted 24-tick sweep through the estimated entity position at steps 3064-3088 picked up nothing, and the current frame shows no loose cobblestone.
- Ground-truth events record two mine_block stone events at steps 3152 and 3181. The following sweep moved toward the table and stopped on pickup stick, with no pickup cobblestone event, so both fresh drops should remain at the break face.
- A 4x zoom of step_3282.png clearly shows several grey-white cobblestone item sprites on the stone floor beyond the centered dirt block; no pickup:cobblestone event has occurred.
- events/events.jsonl records pickup:cobblestone +3 at step 3326 and current inventory contains cobblestone x3.
- events/events.jsonl currently ends at step 2993, while this hypothesis's decisive evidence is from steps 3064-3326 outside the live horizon.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
