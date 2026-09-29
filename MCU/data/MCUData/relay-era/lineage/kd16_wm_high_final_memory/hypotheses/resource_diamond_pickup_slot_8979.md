# resource_diamond_pickup_slot_8979

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 8979
- updated_step: 9600
- depends_on: goal_mine_diamond_ore, mechanism_gui_drop_outside_4078

## Statement

The prediction that dropping dirt x16 at y9 would preserve a diamond slot was refuted: the stationary/bobbing player re-collected the entire stack at step 9569.

## Evidence

- Step 8979 authoritatively reports zero free slots and dirt x13 in hotbar.1; prior verified force-closes removed cursor-held dirt/sand stacks, including dirt at step 10167.
- Step 8988 records [INV] dirt -13 and step 8991 reports force-closing dirt x13 onto the floor. Step 8998 lists no dirt and no hotbar.1 item, although its aggregate capacity line reports zero free slots.
- Step 8988 records dirt -13, step 8991 reports it dropped, and the step-9000 hotbar shows slot 0 empty; the flag-time frame visibly shows the dirt entity immediately below.
- The authoritative step-9199 inventory reports 0 slots free and hotbar.1=dirt x13; events verify pickup dirt +13 at step 9032. Andesite x4 in slot 7 is the smallest expendable stack and can be left above the diamond-depth workspace.
- Steps 9202-9211 opened inventory, lifted andesite x4 from zero-based slot 7, and force-closed it onto the floor. The authoritative hotbar now omits hotbar.8 and inventory omits andesite; the next standalone descent moves away from the entity.
- Step 9252 records pickup andesite +4, and the authoritative step-9511 inventory reports zero free slots. Dirt x16 occupies zero-based hotbar slot 0 and is unlikely to refill while mining ordinary stone at y9; immediate horizontal strip mining should move away before the dropped stack becomes collectible.
- Inventory lost dirt x16 at 9520 and force-close dropped it at 9523, but events record pickup dirt +16 at 9569 before meaningful horizontal movement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
