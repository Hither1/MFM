# location_current_furnace_7851

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 7858
- updated_step: 11000
- depends_on: goal_furnace

## Statement

The portable/current-furnace trajectory is stale and contradicted by the authoritative live prefix; retire it in favor of location_y56_furnace_4810.

## Evidence

- Step 7851 records [INV] furnace -1 after raw use at pos (-3040.70,61,-5556.43), pitch 65, yaw 270; step 7858 records GUI open=True and use_item furnace +1.
- events records mine_block furnace at step 8190; current inventory has no furnace, while the step-8218 frame visibly shows the furnace item entity on the floor ahead.
- pickup furnace +1 and INV furnace +1 fired at step 8319; current authoritative inventory reports furnace x1.
- Step 8380 decremented furnace on raw use; step 8387 verified use_item furnace and GUI open; the step-8400 frame shows the furnace screen.
- Position/yaw are unchanged through visited.csv step 9000; latest frame is the furnace screen, and craft_item iron_ingot +2 fired at 8834.
- events records mine_block furnace at 9041 and pickup furnace at 9245; step-9600 hotbar visibly shows the furnace in slot 6.
- events/events.jsonl has use_item furnace at 4810 and no later furnace event; step 9846 authoritative inventory and hotbar omit furnace, contradicting the stale portable-furnace claim.
- Authoritative events in this live prefix show furnace placement/use at 4810 and no later furnace mine or pickup; the placed furnace remains near (-3006,56,-5567).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
