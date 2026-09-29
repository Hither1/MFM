# resource_current_iron_slot_4294

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 4294
- updated_step: 4800
- depends_on: goal_mine_iron_ore, resource_stone_pickaxe_secure, location_registered_iron_target_3822

## Statement

Refuted: inventory capacity is not a live gate; the HUD shows multiple empty hotbar cells, so dropping the wooden pickaxe and gravel was unnecessary for accepting iron ore.

## Evidence

- Step 4294 STATE reports 0 slots free with only cobblestone, stone pickaxe, and wooden pickaxe stacks; the confirmed resource_free_iron_slot_5508 precedent proves that lifting a stack and guarded force-closing removes it from inventory.
- The step-4303 inventory delta proves the wooden pickaxe left inventory. Step 4550 STATE nevertheless reports zero free slots because the four stacks are stone pickaxe, dirt, gravel, and cobblestone; gravel is expendable and occupies zero-based slot 2.
- Frames 4294 and 4800 visibly show several empty hotbar cells. The gravel dropped at 4562 was recollected at 4637, yet empty cells remain.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
