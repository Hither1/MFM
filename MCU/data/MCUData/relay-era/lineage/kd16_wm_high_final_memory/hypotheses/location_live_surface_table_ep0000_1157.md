# location_live_surface_table_ep0000_1157

- kind: location
- status: stale
- confidence: 1.00
- created_step: 2400
- updated_step: 4200
- depends_on: goal_crafting_table

## Statement

The former live table cell (-3003,68,-5570) is now empty: its table broke at step 4100 and was collected at step 4119.

## Evidence

- use_item crafting_table fired at step 1157 from that fixed map pose; no later mine_block crafting_table event exists.
- At step 1153 one use at the recorded pose/ray consumed the crafting table, and use_until_gui opened it at step 1160. Ray intersection with the y=67 support plane resolves the placed block as (-3004,67,-5571); the current frame shows the table at the matching range and rightward bearing.
- At step 1153 the table item was consumed on the pitch-35/yaw-165 placement ray; at step 1160 that unchanged ray opened the table. Steps 3239-3274 aimed at (-3003.5,67.5,-5570.5) and hit visible dirt while the table remained visibly one block right and one block higher.
- look_at the stated center at 3275 followed by use_until_gui changed GUI open false to true at 3280; events contain no mine_block/pickup crafting_table afterward.
- events/events.jsonl records mine_block crafting_table at 4100 and pickup crafting_table at 4119.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
