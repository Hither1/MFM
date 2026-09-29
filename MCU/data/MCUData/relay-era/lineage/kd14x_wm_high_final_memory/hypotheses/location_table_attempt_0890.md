# location_table_attempt_0890

- kind: location
- status: stale
- confidence: 1.00
- created_step: 890
- updated_step: 1200
- depends_on: goal_crafting_table, location_table_live_0912

## Statement

The failed straight-down table-placement attempts are superseded by the successful oblique placement at step 912.

## Evidence

- Step-890 authoritative inventory still contains crafting_table x1 and Held: crafting_table; the attached frame shows spruce end-grain and bark rather than a crafting-table texture.
- At step 905 the authoritative inventory still contains crafting_table x1 and Held: crafting_table after place_block; pitch is exactly 90 and the frame shows grass underfoot. The inherited successful placement used an oblique pitch near 60 with raw right-click.
- [INV] crafting_table -1 at 912 and use_item crafting_table at 919 verify the later placement and opening.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
