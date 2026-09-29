# mechanism_crafting_table_break_budget_4018

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 4018
- updated_step: 4200
- depends_on: location_live_surface_table_ep0000_1157

## Statement

A correctly centered crafting table breaks under a continuous 90-tick stone-pick attack; the live table broke after about 81 ticks, whereas earlier 60-70 tick holds ended too soon.

## Evidence

- At steps 3477 and 3853, centered attacks lasted only 60 and 70 ticks and broke nothing. The current step-4018 frame visibly shows the table at the expected rightward bearing, and no crafting-table break or pickup event exists.
- look_at the proven center followed by mine_ahead(n=90) produced mine_block crafting_table at step 4100.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
