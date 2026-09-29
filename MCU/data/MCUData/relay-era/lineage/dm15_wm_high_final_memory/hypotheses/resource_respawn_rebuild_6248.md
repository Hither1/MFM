# resource_respawn_rebuild_6248

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 6248
- updated_step: 7200
- depends_on: state_death_and_dropped_kit_6248, location_live_lower_spruce_689, goal_mine_log, location_live_spawn_spruce_0, goal_crafting_table

## Statement

Refuted as cross-trajectory contamination: no post-6248 log recovery, plank/stick rebuild, or wooden-pick craft occurred in the current event prefix.

## Evidence

- events/events.jsonl verifies mine_block spruce_log at step 6339; both subsequent 48-tick sweeps reported no pickup, while the step-6437 frame clearly shows the next hanging spruce-log underside centered and within apparent reach.
- No pickup follows the step-6339 log break; three sweeps failed, while aim_at_tree at 6591 and frame 6600 center a visible overhead trunk.
- At step 6699 [INV] reported spruce_log +2, events recorded pickup spruce_log +2, and live inventory lists spruce_logx2 in hotbar slot 0.
- At step 6699 events and inventory verified pickup spruce_log +2; at step 6708 [INV] verified spruce_log -2 while [CURSOR] measured spruce_logx2 over hotbar slot 0, proving the full stack is safely on the GUI cursor.
- At step 6699 events verified pickup spruce_log +2. At step 6725 events verified craft_item spruce_planks +4, and step 6728 [INV] verified spruce_planks +4 in hotbar slot 0 while the 2x2 grid still showed cell 0 and out=FULL.
- events record craft_item spruce_planks +4 twice and craft_item stick +4; live inventory at step 6901 is spruce_planksx6 and stickx4, while the attached personal grid is visibly empty.
- Events verify pickup spruce_log x2 at 6699, two plank crafts, stick craft, and wooden-pick craft at 6994. The step-7127 runner note explicitly says x3 planks/x2 sticks were dropped from off-inventory on forced close.
- events through 7200 contain no spruce_log pickup, spruce_planks/stick craft, or wooden_pickaxe craft after step 6248.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
