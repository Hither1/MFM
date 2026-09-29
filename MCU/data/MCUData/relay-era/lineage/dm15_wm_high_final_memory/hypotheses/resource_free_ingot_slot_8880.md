# resource_free_ingot_slot_8880

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 8880
- updated_step: 5400

## Statement

Refuted as future-trajectory contamination; current capacity is handled by the empty slot 7 created when ingot #1 was lifted.

## Evidence

- Step 8880 STATE explicitly reports 0 slots free, dirt x25 in hotbar slot 2, and no iron ingot inventory entry after repeated drop sweeps.
- Step 8887 showed dirt x25 off-inventory, step 8890 force-close dropped it, and step 8905 has no dirt in inventory at (-3004.70,57.25,-5566.59), approximately the furnace/ingot position.
- INV cobblestone -64 at step 9646 and the force-close warning at 9649 verify the stack left inventory; subsequent cobblestone pickups can merge with a retained partial stack.
- Step 9846 STATE reports 0 slots free and cobblestone x3 after pickups at 9746, 9788, and 9821.
- Cobblestone was force-dropped at 9883, then pickups from 9944 through 10389 accumulated again; no new item-type slot was freed.
- Step 5378 removed one ingot from slot 7 onto the cursor; step 8880 has not occurred.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
