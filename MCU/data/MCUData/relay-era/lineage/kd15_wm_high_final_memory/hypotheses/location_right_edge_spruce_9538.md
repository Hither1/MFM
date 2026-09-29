# location_right_edge_spruce_9538

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 9538
- updated_step: 10138
- depends_on: goal_iron_pickaxe, mechanism_foreground_tree_ray_9538

## Statement

The hillside spruce candidate was a reachable natural log: after closing the reach gap, it broke at event step 9946 from about (-2983.59,69,-5550.50) and its drop was picked up at 9956. The broken block is exhausted only in this run.

## Evidence

- The attached step-9538 frame visibly shows a vertical bark column at the extreme right while the center crosshair remains on dirt.
- The step-9640 right-side zoom shows an unambiguous broad spruce-bark face above the foreground grass ledge, while the full frame and state provide the steering offset and pose.
- Step 9816 chop reported 75 ticks with nothing broken and explicitly diagnosed out of reach; step 9876 collect_drops moved 0.91 blocks closer, and the attached step_9876 frame shows bark directly under the crosshair.
- events/events.jsonl records mine_block spruce_log at 9946 and pickup spruce_log at 9956; logs report the pickup after a 10-tick sweep.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
