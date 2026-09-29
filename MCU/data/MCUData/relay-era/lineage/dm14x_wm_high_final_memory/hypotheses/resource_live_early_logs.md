# resource_live_early_logs

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 460
- updated_step: 600
- depends_on: goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689, location_current_log_drop_600, location_candidate_log_landing_635

## Statement

Three logs were recovered at step 524; one was converted into the planks consumed by the table, leaving two spruce logs banked in hotbar slot 0 at live step 600.

## Evidence

- events verifies mine_block spruce_log at 342/467/591 and no pickup; zoomed frame 600 clearly shows a rotating log item.
- Directed travel southeast from the worked trunk produced pickup spruce_log +3 at step 668; authoritative step-729 STATE lists spruce_log x3 in hotbar slot 0.
- pickup spruce_log +3 was verified at step 664; craft_item spruce_planks +4 was verified at step 760; authoritative step-765 inventory lists spruce_planks x4 and spruce_log x2.
- Live inventory is empty immediately after the verified spruce_log break, and the remaining trunk is visible within reach.
- events/events.jsonl verifies spruce_log mine_block at steps 161, 284, and 440 with no pickup event through step 494. Three local canopy sweeps failed; current inventory is empty. A prior same-tree trajectory recovered three drops by moving southeast through (-3006.3,-5567.9) toward (-3004.2,-5565.3).
- events/events.jsonl records pickup spruce_log +3 at step 524; live step-527 STATE lists spruce_logx3 in hotbar slot 0.
- events/events.jsonl verifies pickup spruce_log +3 at step 524; live step 533 reports GUI open, empty player inventory, and spruce_log x3 off-inventory on the measured cursor.
- Pickup spruce_log +3 at 524, craft spruce_planks +4 at 555, and frame 600 visibly shows spruce_log x2.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
