# mechanism_respawn_pit_hand_notch_11097

- kind: mechanism
- status: confirmed
- confidence: 0.98
- created_step: 11097
- updated_step: 11185
- depends_on: mechanism_dirt_wall_clutch_10923

## Statement

The respawn pocket was blocked by a shallow dirt bank; two hand-breaks opened a walkable notch, returned dirt drops, and let the player climb from (-3009.3,69,-5572.3) onto the surface canopy by step 11165.

## Evidence

- Steps 11023-11097 show repeated go_to failures from the same x/z despite jump-height oscillation, and the current frame has the crosshair centered on a close dirt face with open daylight beyond its left edge.
- Steps 11120 and 11141 mined grass/dirt and picked up both drops; authoritative movement then reached (-3006.35,72.17,-5572.26) at step 11165, escaping the formerly immobile pocket.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
