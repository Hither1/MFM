# resource_current_cobblestone

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 2400
- updated_step: 7200
- depends_on: goal_wooden_pickaxe, goal_mine_cobblestone, location_live_return_shaft_3449, resource_wooden_pickaxe_secure, location_live_shaft_1200, location_surface_recovery_7749, location_live_descent_2308, location_live_dirt_face_2400, location_corrected_surface_shaft_1727

## Statement

Frame 7200 shows cobblestone x35 in hotbar slot 4 (zero-based), plus dirt x3 and diorite x4; the player has 42 placeable blocks, enough for a y40-to-surface pillar but that detour is not budget-optimal.

## Evidence

- Frame 9200 visibly shows cobblestone x35; placement events through 8961 account for the reduction from the prior stack.
- Logs record INV cobblestone -35 at step 10191 and the force-close drop note at 10194; the 72-tick sweep through 10342 gained nothing, events contain no later cobblestone pickup, and frame 10400 shows slot 5 empty.
- events line 25 records pickup cobblestone +1 at 1775; frame 1800 visibly shows x1, and no later pickup follows the 1794 stone break.
- events lines 25-78 total pickup cobblestone +19; use_item cobblestone at 2053 consumed one; frame 2400 visibly shows x18.
- Current-prefix events through 3000 total pickup cobblestone +22 and use_item cobblestone +9; the enlarged frame-3000 hotbar independently shows x13.
- Step 3000 had x13; verified recipes consume 3 and 8; frame 3600 independently shows cobblestone x2 in hotbar slot 4.
- Frame 4800 visibly shows cobblestone x22; current-prefix pickup/use events reconcile the stack and no later placement occurs.
- Frame 7200 visibly shows the three stack counts; current-prefix pickup events through 7195 reconcile the cobblestone and diorite accumulation.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
