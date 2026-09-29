# location_return_blocked_by_furnace_6570

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 6570
- updated_step: 6654
- depends_on: location_live_east_branch_3600, location_live_iron_pocket_4800

## Statement

The blocking furnace was broken and recovered at live steps 6609-6619, reopening the south passage; movement to z=-5559.85 verifies that obstruction is cleared.

## Evidence

- At step 6570 the player is fixed at (-2993.7,55,-5564.3); both go_to attempts toward the southern waypoint were collision-blocked, and the attached downward frame shows the furnace face directly between the player and the corridor.
- Two go_to attempts stopped at (-2993.7,55,-5564.3); frame 6600 clearly shows the aimed furnace with advanced cracking under the selected stone pick.
- events record mine_block furnace at 6609 and pickup furnace at 6619; go_to then moved from z=-5564.30 to z=-5559.85 by step 6654.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
