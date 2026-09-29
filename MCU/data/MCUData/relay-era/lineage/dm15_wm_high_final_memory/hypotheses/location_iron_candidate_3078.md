# location_iron_candidate_3078

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 3078
- updated_step: 3600
- depends_on: location_shallow_stone_shaft, location_fresh_direct_descent_2530

## Statement

The alleged step-3078 ore-watch candidate is cross-trajectory contamination and provides no current-run ore evidence.

## Evidence

- The ore watcher stopped mining at step 3078 and localized a 16-pixel candidate around screen (292,235); the saved zoom places it at the visible stone/dirt boundary, partially behind the held pickaxe.
- aim_at_ore lost the detection, mine_ahead then produced three mine_block stone events and no mine_block iron_ore event through step 3216.
- aim_at_ore lost detection; mine_ahead produced only stone events at 3101, 3119, and 3137 and no iron event.
- At live steps 3075-3081 the log/map show cobblestone pillar actions near y57-58, not an ore-watcher stop; no iron event exists through 3600.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
