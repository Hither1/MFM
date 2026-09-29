# location_y55_crafting_table_8081

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 8081
- updated_step: 8600
- depends_on: goal_crafting_table, resource_rebuild_stone_pick_7259

## Statement

Refuted as cross-trajectory contamination: no crafting table was placed at y55 in the live prefix; the current table remains at the surface.

## Evidence

- Step 8081 records [INV] crafting_table -1 after place_block, and the attached frame visibly centers the table at close range.
- Step 8081 records crafting_table -1 after placement, and step 8088 records GUI open=True plus use_item crafting_table +1 from the same stationary position.
- At step 8081 crafting_table inventory decreased by one; use_item crafting_table fired at 8088 and GUI open remained true through step 8101.
- use_item crafting_table fired at 8088; craft stone_pickaxe fired at 8149; no mine_block crafting_table follows through step 8400.
- Current events at 8000-8600 contain only cobblestone mining/pickups and no table use/placement; frame 8600 is an open shaft, not a table alcove.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
