# resource_live_early_logs

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 460
- updated_step: 2400
- depends_on: goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689, location_current_log_drop_600, location_candidate_log_landing_635, location_adjacent_spruce_face_924, location_adjacent_spruce_face_1463, location_adjacent_spruce_face_1545

## Statement

Live wood conversion is complete: after crafting the wooden pickaxe, the current reserves are 3 spruce planks and 2 sticks, with the crafting table placed nearby.

## Evidence

- events/events.jsonl lines 8-10 verify the break, milestone, and pickup; frame 1200 visibly shows the held log.
- events/events.jsonl verifies spruce_planks crafting at 1235 and crafting_table crafting at 1272; step-1463 STATE lists only crafting_table x1. The runner's step-1281 cursor spruce_log note was a stale GUI label, as no spruce log exists in authoritative STATE.
- Step-1545 STATE lists spruce_logx1; events verify mine_block spruce_log at 1535 and pickup spruce_log at 1545.
- events/events.jsonl verifies spruce-log pickups at steps 1545 and 1714; authoritative step-1714 STATE lists spruce_log x2 and crafting_table x1.
- Authoritative pickups at steps 1545 and 1714 supplied two logs; craft_item spruce_planks +4 fired at step 1745, and step 1749 STATE lists one banked log plus four banked planks with an empty active 2x2 grid.
- events/events.jsonl verifies spruce_planks +4 at steps 1745 and 1768; step-1772 STATE lists spruce_planks x8 and crafting_table x1, while the authoritative 2x2 GRID is empty.
- Log pickups fired at 1545/1714, plank crafts at 1745/1768, and stick craft at 1800; frame 1800 visibly banks the resulting six planks and four sticks.
- The wooden-pick craft event fired at 1885; frame 2400 visibly shows planks x3 and sticks x2, while table placement/use fired at 1816 and no later table break/pickup exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
