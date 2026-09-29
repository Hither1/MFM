# resource_diamond_pickup_slot_10126

- kind: resource
- status: refuted
- confidence: 0.99
- created_step: 10126
- updated_step: 10200
- depends_on: goal_diamond

## Statement

Dropping sand at y27 did not preserve a diamond slot because the descending player re-collected sand x8 at step 10179; capacity must be freed at y11-12 immediately before horizontal departure.

## Evidence

- Step 10126 authoritative inventory reports zero free slots and sand x8 in hotbar.2. The runner documents force-close as an intentional way to drop the cursor stack; unlike cobblestone, sand is not expected in the y11 tunnel.
- events/events.jsonl records pickup sand +8 at step 10179 after the force-drop at step 10138.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
