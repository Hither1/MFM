# state_cursor_coal_5707

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 5707
- updated_step: 5720
- depends_on: state_inventory_5693, resource_coal_5693

## Statement

The step-5707 coal stack was split successfully by step 5720: one coal is in inventory 2x2 cell 0 and one coal is banked in hotbar slot 6 (inventory slot 6), with nothing held on the cursor.

## Evidence

- The authoritative step-5707 CURSOR reports coal x2 off-inventory over hotbar slot 6, and INV reports coal -2 after the successful lift.
- At step 5720 [GRID] shows 2x2 cell 0 occupied, [INV] reports coal +1, and [CURSOR] reports only the off-inventory grid coal while positioned over hotbar slot 6; inventory lists coal x1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
