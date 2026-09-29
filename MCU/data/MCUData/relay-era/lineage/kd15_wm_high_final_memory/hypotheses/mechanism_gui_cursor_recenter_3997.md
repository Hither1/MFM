# mechanism_gui_cursor_recenter_3997

- kind: mechanism
- status: confirmed
- confidence: 0.95
- created_step: 3997
- updated_step: 4004

## Statement

Across planning turns the crafting GUI cursor may recenter away from its last landed slot, so each cursor_to_slot/cursor_to_cell must be paired with its click in the same actions plan.

## Evidence

- At step 3994 cursor_to_slot(3) verified over hotbar slot 3, but the next turn began with the cursor at (88,83); gui_click at step 3997 was guard-stopped 69 px from the landing point and lifted nothing.
- An unpaired click at step 3997 aborted 69px from the prior landing; pairing cursor_to_slot(slot=3) and gui_click in one plan at steps 4001-4004 successfully lifted the wooden pickaxe.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
