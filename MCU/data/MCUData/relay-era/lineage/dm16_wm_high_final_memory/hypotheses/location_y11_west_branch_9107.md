# location_y11_west_branch_9107

- kind: location
- status: stale
- confidence: 1.00
- created_step: 9107
- updated_step: 10200
- depends_on: location_y11_plus_z_branch_8921, goal_iron_pickaxe, state_death_diamond_run_10624

## Statement

Retire the cross-trajectory lava/death forecast: the current prefix at step 10200 is alive on z=-5558.48, and events/maps beyond this checkpoint cannot establish the fate of the live branch.

## Evidence

- The authoritative final visited.csv block fixes the endpoint and branch line; events from 9130 through 9598 contain 24 stone/diorite breaks and no diamond event; frames 9480/9600 show the enclosed tunnel.
- The step-9867 mine_forward note reports 19 blocks broken and 9.0 blocks advanced; step-9878 STATE and visited.csv fix the endpoint at (-3017.70,11,-5562.30), and events contain no diamond mine or pickup.
- The authoritative final visited.csv trajectory fixes step 10200 at (-3022.70,11,-5562.30); events 9919-10175 contain one andesite, seven stone, and four gravel breaks, with no diamond mine or pickup event.
- Step-10275 STATE is (-3023.70,11.00,-5562.30); events 10210-10270 show three gravel breaks and no diamond mine or pickup event.
- Authoritative STATE/visited.csv at step 10416 and the mine_forward note report 4 blocks broken, 1.2 blocks advanced, then a two-cycle no-movement stall; events 10314-10407 are gravel only and contain no diamond.
- Maps trace the branch to lava; death at 10624 leaves the player 62 levels above it.
- The branch ended at the step-10624 lava death; final-trajectory maps keep the live player at the surface through 11400.
- Current-prefix last-row map data fixes (-3031.77,12,-5558.48) with no damage or lava event through 10200; the node's former evidence cited steps 10210-11400 beyond the live checkpoint and a different z-line.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
