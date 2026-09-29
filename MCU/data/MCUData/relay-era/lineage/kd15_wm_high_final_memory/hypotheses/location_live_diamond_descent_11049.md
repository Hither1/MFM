# location_live_diamond_descent_11049

- kind: location
- status: active
- confidence: 0.99
- created_step: 11049
- updated_step: 11938
- depends_on: goal_iron_pickaxe, goal_mine_diamond_ore, mechanism_shaft_floor_fixed_aim_8898, mechanism_vertical_mine_ahead_rate_10200

## Statement

The this-run shaft remains centered at (-2996.70,-5565.70) and ends at y32.00. The permanent ore face near (-3000.5,9.5,-5572.5) is still about 24 levels and 7.8 horizontal blocks away; the steep cut is not traversable.

## Evidence

- Authoritative step-11049 state fixes the pose and pitch; the attached frame shows the crosshair on a dirt block directly below. Prior mechanism_shaft_floor_fixed_aim_8898 records fixed mine_ahead breaking five downward blocks and lowering the player when dig_down was stuck.
- Steps 11049-11129 record five downward dirt/stone breaks, three cobblestone pickups, and authoritative descent from y65 to y60 at fixed x/z. Current pitch is 88 and yaw 159.6, matching the bearing to the registered vein.
- maps/visited.csv steps 11129-11338 hold x/z fixed and descend y60 to y45; events verify fifteen intervening stone breaks.
- Authoritative step-11530 state and maps/visited.csv fix (-2996.70,32.92,-5565.70), pitch 88, yaw 159.6. Steps 11338-11530 continued the steady fixed-ray descent with ordinary stone, coal, and andesite breaks and no diamond event.
- Authoritative map rows at 11731, 11931, and 11938 all show (-2996.70,32.00,-5565.70); no diamond event exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
