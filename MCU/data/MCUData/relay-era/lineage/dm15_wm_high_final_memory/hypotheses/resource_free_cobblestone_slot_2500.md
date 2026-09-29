# resource_free_cobblestone_slot_2500

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 2500
- updated_step: 2872
- depends_on: resource_current_cobblestone, goal_mine_cobblestone

## Statement

The deliberate dirt drop freed the unique-stack slot, and that slot is now successfully occupied by the live cobblestone x8 stack.

## Evidence

- Authoritative step-2500 STATE reports zero free slots with dirt x8 in zero-based slot 3. The episode's confirmed resource_free_iron_slot_5508 precedent shows that lifting dirt and guarded force-closing deliberately drops it and frees the slot.
- At step 2509, cursor_to_slot(3) followed by gui_click produced authoritative [INV] dirt -8 and [CURSOR] dirtx8, proving the expendable stack is off-inventory and ready for deliberate forced dropping.
- Step 2509 removed dirt x8 from inventory; current STATE at step 2872 contains cobblestone x8 and dirt x1 with all five slots occupied.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
