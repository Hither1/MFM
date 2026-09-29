# location_worksite_overhead_spruce_8062

- kind: location
- status: active
- confidence: 0.80
- created_step: 8062
- updated_step: 8419
- depends_on: location_furnace_worksite_4390, goal_iron_pickaxe

## Statement

The overhead worksite spruce block broke at step 8366 and its loose log drop should remain within a short sweep of the current worksite; the previous collection attempt failed because it immediately repicked the deliberately dropped sand.

## Evidence

- Historical frames step_2037 and step_2176 at this same worksite pocket visibly show a low hanging spruce trunk overhead and a stump/log immediately nearby; the current pose matches the utility pocket.
- The step-8250 frame visibly shows spruce log end grain and bark across the upper centre, while the prior aim_at_tree at pitch -25 reported no detection because the trunk face lay above the view centre.
- aim_at_tree centered the trunk at step 8301; chop_tree then produced mine_block spruce_log at step 8366, while authoritative inventory remained full and contains no spruce_log.
- mine_block spruce_log fired at 8366 with no spruce_log pickup afterward; current pose at step 8400 remains (-2998.68,64.50,-5568.70), directly under the break.
- No spruce_log pickup follows the verified break at 8366. The step-8419 collect_drops note explicitly stopped after picking up sand x8, so it did not disprove the nearby log drop.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
