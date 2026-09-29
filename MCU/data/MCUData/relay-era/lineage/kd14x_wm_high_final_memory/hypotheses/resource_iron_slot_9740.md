# resource_iron_slot_9740

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 9740
- updated_step: 10200
- depends_on: goal_mine_iron_ore

## Statement

The older sand-slot workaround is historical; sand and later dirt are gone, and step 10200 has four empty hotbar slots.

## Evidence

- The authoritative step-9740 state reports 0 slots free and dirt x3 in hotbar slot 5; confirmed mechanism_gui_drop_outside_4078 shows force-closing with a cursor stack removes it from inventory.
- At step 9749 gui_click yielded [INV] dirt +2 while [CURSOR] ended empty over hotbar slot 4, so the click deposited rather than lifted.
- Step 9752 gui_click produced [INV] dirt -5 while the GUI remained open and [CURSOR] reported dirt off-inventory over the now-empty hotbar slot; the confirmed forced-close mechanism drops cursor-held items.
- Step 9890 state reports 0 slots free and sand x2 in hotbar slot 9; the current plan opens inventory and lifts that exact stack.
- Step 9899 reports [INV] sand -2 and [CURSOR] sandx2 off-inventory over the emptied hotbar slot 9; confirmed mechanism_gui_drop_outside_4078 supports force-closing to discard it.
- Step 9902 force-close reports sand x2 dropped; step 10155 authoritative state again reports zero free slots after cobblestone, diorite, and torch pickups.
- Sand was dropped at 9902; dirt was dropped at 10167; the latest hotbar supersedes this slot belief.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
