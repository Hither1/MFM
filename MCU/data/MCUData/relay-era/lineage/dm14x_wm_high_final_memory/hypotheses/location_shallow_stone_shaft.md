# location_shallow_stone_shaft

- kind: location
- status: refuted
- confidence: 0.95
- created_step: 2196
- updated_step: 6600
- depends_on: goal_mine_cobblestone

## Statement

The active west tunnel face is at (-3022.7,63.0,-5556.3), reached from the shallow junction by following the west branch; its eastward rear floor is open for local workstation placement.

## Evidence

- Ground-truth position reached y=64 at step 2248; the frame shows a centered stone floor, while inventory/events recorded dirt pickups only and no cobblestone.
- maps/visited.csv is stationary there through 2400; stone events occurred at 1945, 2280, 2309, then dirt events at 2342, 2363, 2384.
- Ground-truth state at step 2499 and stair_down note: four dirt blocks broken, 1.0 block advanced, 0.0 descended; current frame visibly shows stone floor below the dirt face.
- maps/visited.csv step 3000 gives the coordinate; the stair note reports 1.0 advance and 0.0 descent, while stone was mined at 2977.
- Ground-truth state and mine_forward diagnosis at step 3362.
- maps/visited.csv step 3600 gives the coordinate/yaw 90; events 3385-3598 show repeated stone breaks and nine pickups after the turn west.
- Step 3716 state gives the position and yaw 90 after mine_forward advanced 6.18 blocks; the frame and route history show the excavated tunnel behind.
- At step 6466 direct go_to was blocked at (-3016.7,64.2,-5556.6), six blocks short; it is not the currently reachable launch face.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
