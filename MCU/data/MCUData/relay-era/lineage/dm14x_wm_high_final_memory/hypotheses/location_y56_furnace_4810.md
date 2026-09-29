# location_y56_furnace_4810

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 5400
- updated_step: 5400
- depends_on: goal_furnace, location_live_return_shaft_3449

## Statement

Refuted for this trajectory: the live furnace is near (-2993.5,55.5,-5563.5), not (-3006,56,-5567).

## Evidence

- At step 4808 inventory lost furnace x1 while the player faced yaw 90 at the shaft foot, and use_item furnace fired at 4810.
- Step-7638 attached frame clearly shows the furnace front centered ahead at arm's reach; use_until_gui failed while the crosshair was visibly below the furnace face.
- Step 7644 reports GUI open=True and the active furnace GRID row as [fuel] after interaction with the visible furnace front.
- use_item furnace at 4810 verifies placement; GUI opened at 7644 from the stated pose and aim; step 7800 shows the active furnace screen.
- use_item furnace at 4810 verifies placement; no later mine_block or pickup furnace event exists through 10400, while all old ore was converted by 8780.
- Current furnace use at 4630 and GUI openings from (-2993.3,54,-5564.7) contradict the alternate location.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
