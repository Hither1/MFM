# location_surface_recovery_7749

- kind: location
- status: stale
- confidence: 1.00
- created_step: 7749
- updated_step: 8400
- depends_on: location_current_crafting_table, mechanism_pillar_requires_downward_aim

## Statement

The surface-recovery instruction is stale and no longer describes live state; the player is safely mining at y11.

## Evidence

- Step 7749 STATE fixes y64 after the failed surface go_to; steps 7705-7732 show the player falling from y67.2 to y64, step 7735 picked up three dirt, and the attached frame shows close dirt faces.
- Final visited row fixes the pose through 7800; mine_block spruce_leaves fired at 7770 and frame 7800 shows sky, grass, dirt, stone, and remaining leaves overhead.
- maps/visited.csv and STATE place the live player at (-3014.70,11,-5566.30) at step 8400.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
