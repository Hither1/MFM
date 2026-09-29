# resource_restore_diamond_slot_9867

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 9867
- updated_step: 10200
- depends_on: goal_diamond, mechanism_raw_block_placement

## Statement

The attempted cobblestone/andesite cleanup did not create a durable diamond slot: step 9894 still had zero free slots, and the only verified andesite placement was subsequently mined and picked back up.

## Evidence

- At step 9867 slot 3 contains the only expendable one-item placeable stack; the player is in a one-wide tunnel and can turn east before using place_block so the placed block remains behind the active west face.
- Step-9878 STATE reports zero free slots and hotbar.3=cobblestone x2. The straight-down placement failed because the intended cell was occupied by the player, so this test precisely targets the floor behind for the lower block and then the lower block's top face for the upper block.
- Events verify use_item cobblestone at 9884 and 9886, while step-9886 STATE reports 0 slots free, hotbar.3 cobblestone x1, and hotbar.8 andesite x3. Three distinct targets east/side of the player avoid the active west face and test complete consumption of the isolated stack.
- Events verify cobblestone placements at 9884 and 9886 and a torch placement at 9890. Step-9894 STATE retains andesite x3 and zero free slots, proving the attempted z=-5563.5 andesite placements failed; the successful torch target at (-3017.5,12.0,-5561.5) identifies the opposite wall as a valid support face.
- STATE at 9894 reports zero slots; events record use_item andesite at 9900, mine_block andesite at 9919, and pickup andesite at 9929, reversing the sole successful placement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
