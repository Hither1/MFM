# mechanism_gui_drop_outside_4078

- kind: mechanism
- status: confirmed
- confidence: 0.95
- created_step: 4078
- updated_step: 4085
- depends_on: mechanism_gui_cursor_recenter_3997

## Statement

close_inventory(force=true) closes a crafting screen and drops all items that remain off-inventory, including the cursor stack and crafting-grid ingredients; stacks banked in player slots remain safe.

## Evidence

- Minecraft container semantics support outside-click dropping; this turn tests it with the obsolete wooden pickaxe after re-landing on cell 3.
- At step 4082 cursor_to(dx=-4,dy=0) visibly moved outside to (-77,44), but gui_click was guard-aborted because the last registered absolute landing remained cell 3. The wooden pickaxe is already lifted and is the only cursor-held stack; forced close is documented to drop what the cursor holds.
- The step-4085 close note reported cobblestone x3, sticks x2, and wooden pickaxe x1 off-inventory; afterward the GUI was closed and inventory contained only the previously banked cobblestone x9, sticks x4, and dirt x17.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
