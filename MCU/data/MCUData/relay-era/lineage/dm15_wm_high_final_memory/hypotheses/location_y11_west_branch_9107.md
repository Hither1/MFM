# location_y11_west_branch_9107

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 9107
- updated_step: 11400
- depends_on: location_y11_plus_z_branch_8921, goal_iron_pickaxe, state_death_diamond_run_10624

## Statement

The this-run y11 west branch is retired for the remainder: its frontier opens into lethal lava and the empty-handed surface player has no safe return route within 600 ticks.

## Evidence

- Step-9480 STATE fixes the endpoint; the mine_forward note reports 18 blocks broken and 8.0 blocks advanced in 364 ticks, while current-prefix events contain only stone/diorite and no diamond.
- The authoritative final visited.csv block fixes the endpoint and branch line; events from 9130 through 9598 contain 24 stone/diorite breaks and no diamond event; frames 9480/9600 show the enclosed tunnel.
- The step-9867 mine_forward note reports 19 blocks broken and 9.0 blocks advanced; step-9878 STATE and visited.csv fix the endpoint at (-3017.70,11,-5562.30), and events contain no diamond mine or pickup.
- The authoritative final visited.csv trajectory fixes step 10200 at (-3022.70,11,-5562.30); events 9919-10175 contain one andesite, seven stone, and four gravel breaks, with no diamond mine or pickup event.
- Step-10275 STATE is (-3023.70,11.00,-5562.30); events 10210-10270 show three gravel breaks and no diamond mine or pickup event.
- Authoritative STATE/visited.csv at step 10416 and the mine_forward note report 4 blocks broken, 1.2 blocks advanced, then a two-cycle no-movement stall; events 10314-10407 are gravel only and contain no diamond.
- Maps trace the branch to lava; death at 10624 leaves the player 62 levels above it.
- The branch ended at the step-10624 lava death; final-trajectory maps keep the live player at the surface through 11400.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
