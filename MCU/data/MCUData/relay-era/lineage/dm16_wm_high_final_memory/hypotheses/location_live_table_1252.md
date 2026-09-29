# location_live_table_1252

- kind: location
- status: stale
- confidence: 1.00
- created_step: 1259
- updated_step: 8400
- depends_on: goal_crafting_table

## Statement

The surface table location remains historical this-run geometry but is stale for planning because every crafting milestone is complete and only diamond pickup remains.

## Evidence

- At step 1252 the raw use caused [INV] crafting_table -1 from pose (-3007.70,69.00,-5567.70), and use_until_gui from the same pose produced GUI open=True plus use_item crafting_table at step 1259; the attached frame centers the table directly ahead.
- Milestones through iron_pickaxe are verified; current player is y11 with no recipe dependency.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
