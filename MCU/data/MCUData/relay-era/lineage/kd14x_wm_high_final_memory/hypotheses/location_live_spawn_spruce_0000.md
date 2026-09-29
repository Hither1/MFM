# location_live_spawn_spruce_0000

- kind: location
- status: active
- confidence: 0.90
- created_step: 0
- updated_step: 814

## Statement

The original spruce still has visible trunk blocks near the spawn-side canopy, but at step 814 the current ray from (-3007.57,70,-5569.09) intersects foreground grass; reaching the visible bark requires a centred forward approach before chopping.

## Evidence

- The live step-0 frame visibly shows a large spruce trunk ahead through the canopy, and the player starts empty-handed at (-3009.5,71,-5572.5).
- The step-111 frame shows the broken-block gap and remaining bark; the authoritative mine_block spruce_log event proves reachability.
- The step-814 frame shows large spruce trunks ahead, while the centred stationary chop produced only grass_block breaks at steps 710 and 734 and no spruce_log event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
