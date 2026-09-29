# location_live_descent_2308

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 2308
- updated_step: 2400
- depends_on: goal_wooden_pickaxe, location_live_table_1813

## Statement

Refuted as cross-trajectory contamination: authoritative step 2308 is inside the current y56 east stone tunnel, not a surface staircase launch.

## Evidence

- At step 2308 the level mine_forward call broke three grass blocks and one dirt block but stalled after advancing only 1.6 blocks; the frame shows a dirt hillside with a grass top, so changing to stair_down tests the subsurface directly without repeating the stalled method.
- The player continued east-northeast from step 2308 to step 2400, ending at a different coordinate while breaking three more dirt/grass blocks; no stair_down event/note occurred.
- Last-per-step visited rows hold y56 and yaw -90; events at 2276/2307 are stone breaks in the active tunnel.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
