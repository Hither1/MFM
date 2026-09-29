# location_current_surface_furnace_ep0000_7002

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 7002
- updated_step: 7800
- depends_on: goal_furnace, goal_iron_ingot, resource_current_wood_fuel_ep0000_6000

## Statement

The this-run surface furnace remains reachable and open at step 7800 from (-3004.51,68,-5568.46), pitch 25/yaw 217; its completed output is under the cursor.

## Evidence

- At step 7002 furnace x1 is in zero-based hotbar slot 8, the player is at (-3003.87,68,-5568.30), and the placed crafting table remains adjacent at this surface worksite.
- Step 7010 records [INV] furnace -1 after place_block from the unchanged pose (-3003.87,68,-5568.30), and the attached frame visibly centers the newly placed furnace under the crosshair.
- Step 7010 records furnace -1 and use_item furnace +1 from the unchanged pose; frame 7010 visibly centers the furnace face under the crosshair.
- furnace placement inventory delta at 7010, use_item furnace at 7013, and the live step-7200 furnace screen from the unchanged pose.
- The final map row gives the pose; logs report GUI open and cursor over furnace output, and frame step_7800 shows the furnace screen.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
