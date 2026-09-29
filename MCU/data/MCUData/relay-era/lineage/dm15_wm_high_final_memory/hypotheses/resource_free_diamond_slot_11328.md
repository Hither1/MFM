# resource_free_diamond_slot_11328

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 11328
- updated_step: 11600
- depends_on: goal_iron_pickaxe

## Statement

A diamond pickup slot is free: the stone pickaxe was removed from hotbar slot 0 and deliberately dropped at step 11336, while the iron pick remains in slot 1.

## Evidence

- STATE at step 11328 reports zero free slots and exactly two pickaxes; the GUI remains open and force-close explicitly drops a real cursor stack.
- INV stone_pickaxe -1 fired at 11333, force-close reported the drop at 11336, and frames 11552/11600 show only the iron pick in the hotbar.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
