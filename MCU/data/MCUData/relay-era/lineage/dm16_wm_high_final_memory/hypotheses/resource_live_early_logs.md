# resource_live_early_logs

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 460
- updated_step: 3600
- depends_on: goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689, location_current_log_drop_600, location_candidate_log_landing_635, location_adjacent_spruce_face_924, location_adjacent_spruce_face_1463, location_adjacent_spruce_face_1545

## Statement

At step 3600 no logs remain and spruce planks x3 remain securely held in zero-based hotbar slot 2; two planks can supply four new sticks.

## Evidence

- Log pickups fired at 1545/1714, plank crafts at 1745/1768, and stick craft at 1800; frame 1800 visibly banks the resulting six planks and four sticks.
- The wooden-pick craft event fired at 1885; frame 2400 visibly shows planks x3 and sticks x2, while table placement/use fired at 1816 and no later table break/pickup exists.
- mine_block spruce_log fired at 480, but no pickup/INV event followed and the hotbar remains empty.
- Current-prefix events verify spruce-log pickups of two at step 880 and one at step 964; authoritative step-1064 STATE and hotbar both report spruce_log x3.
- Current-prefix pickup events supplied three logs at steps 880 and 964. craft_item spruce_planks +4 fired at step 1096, and authoritative step-1099 STATE/INV reports spruce_log x2 plus spruce_planks x4; the active 2x2 grid is empty, so the residual cursor log label is the already-documented stale phantom.
- Pickup events at 880 and 964 yielded three logs. Events verify planks at 1095/1156/1168, table at 1131, and sticks at 1200; INV and the magnified step-1200 frame resolve the final banked/cursor stacks despite stale cursor text in logs.
- events verify all plank/stick/tool crafts; magnified frames 1494 and 1800 visibly show banked sticks x2 and planks x3 despite the stale force-close aggregate.
- No post-1323 plank/log event changes the x3 remainder, and frame 3600 shows the x3 plank stack.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
