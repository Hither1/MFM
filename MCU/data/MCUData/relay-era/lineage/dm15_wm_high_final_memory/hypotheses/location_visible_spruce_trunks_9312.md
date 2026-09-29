# location_visible_spruce_trunks_9312

- kind: location
- status: refuted
- confidence: 0.05
- created_step: 9312
- updated_step: 9800
- depends_on: location_live_fuel_spruce_8970

## Statement

Refuted as an exact location claim: candidate centres (-3000.5,68.5,-5570.5) and (-3000.5,69.5,-5570.5) are not reachable trunk faces from the live pose; one produced a full no-break guard and the other points into sky.

## Evidence

- Frame step_9312.png visibly shows a large bark face on the upper-right hillside and another trunk beside the pond; closed-loop aim_at_tree can test reachability without spending the nearly depleted stone pick.
- The verified lower column block at (-3000.5,67.5,-5570.5) was removed at step 9107; frame 9631, viewed straight up from only 0.82 horizontal blocks away, visibly shows the exposed underside and continuation of the same spruce trunk overhead.
- From (-3000.30,65,-5569.70), exact look_at on y68.5 followed by chop_tree spent 75 ticks with no break at 9707; exact look_at on y69.5 yields the sky-centred frame 9800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
