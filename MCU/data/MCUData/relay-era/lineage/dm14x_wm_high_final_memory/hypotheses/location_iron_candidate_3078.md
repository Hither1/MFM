# location_iron_candidate_3078

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 3078
- updated_step: 3600
- depends_on: location_shallow_stone_shaft

## Statement

The step-3078 speckle patch was ordinary stone, not iron ore.

## Evidence

- The ore watcher stopped mining at step 3078 and localized a 16-pixel candidate around screen (292,235); the saved zoom places it at the visible stone/dirt boundary, partially behind the held pickaxe.
- aim_at_ore lost the detection, mine_ahead then produced three mine_block stone events and no mine_block iron_ore event through step 3216.
- aim_at_ore lost detection; mine_ahead produced only stone events at 3101, 3119, and 3137 and no iron event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
