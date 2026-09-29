# location_table_reapproach_6921

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 6921
- updated_step: 7200
- depends_on: location_live_surface_table_1624, resource_respawn_rebuild_6248, state_death_and_dropped_kit_6248

## Statement

Refuted for the current prefix: at step 6921 the player was underground near (-2994.7,54,-5559.3), not opening a surface table at (-3001,64,-5564).

## Evidence

- Authoritative step-6921 state gives the live position and inventory of six planks/four sticks; the same table center previously opened successfully at step 1669.
- At step 6929, look_at the known block center followed by use_until_gui changed authoritative GUI state from false to true; the current frame shows the table immediately below the player.
- Authoritative logs/maps and frame sequence 6924-7200 show the underground west return tunnel; no table use event occurs.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
