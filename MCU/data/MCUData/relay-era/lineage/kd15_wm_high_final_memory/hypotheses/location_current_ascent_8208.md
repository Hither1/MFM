# location_current_ascent_8208

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 8208
- updated_step: 8509
- depends_on: location_parallel_lane_reconnect_7968, mechanism_dirt_pillar_return_2325, mechanism_pillar_ceiling_clearance_3000

## Statement

The reset-local return pillar and north lip route are fully traversed: by step 8504 the player reached the pond-side surface slope at (-2994.70,67.02,-5564.82), four blocks east of the known spruce/table worksite. The direct line ends in the tree canopy, so approach the utility blocks around the trunk rather than repeating go_to through it.

## Evidence

- Step 8208 ground truth is (-2988.70,55.18,-5568.70) after ten verified cobblestone placements. Current-run visited rows 4847-4852 record the descent route at y57 from (-2989.30,-5567.72) to (-2989.25,-5568.31).
- Steps 8243-8253 moved northwest from the pillar top onto stable y57 ground. The pose nearly matches the reset-local descent endpoint (-2989.25,57,-5568.31) at step 4852, whose preceding waypoints record the route from y64.
- Steps 8253-8268 reached the shaft center near (-2989.70,57,-5567.30) but repeated go_to calls could not climb the vertical ledges. Current-run descent events at steps 3562-3762 broke the grass/dirt/stone column from y63 toward y57, and the attached step-8268 view shows the selected cobblestone ray centered on solid footing beneath an open narrow shaft.
- Visited rows 8269-8338 show continuous pillar gain from y57 to y62.25; use_item cobblestone fires at 8277, 8289, 8309, and 8321, and frame 8338 shows the cobblestone pillar underfoot inside the dirt shaft.
- Step 8364 ground-truth state is y63 after six verified cobblestone placements; visited.csv steps 4839-4830 preserve the reverse surface path from (-2989.67,63.16,-5566.40) toward (-2991.09,65.17,-5564.22).
- Verified cobblestone use events raised the player to y63 at step 8364; mine_forward opened the north grass lip, and visited.csv then shows continuous surface travel to (-2994.70,67.02,-5564.82) by step 8504. The final go_to stopped exactly against the visible spruce canopy/trunk, proving the surface exit and locating the remaining obstruction.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
