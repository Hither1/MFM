# location_current_lower_east_tunnel_4087

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 4087
- updated_step: 4200
- depends_on: location_registered_iron_target_3822, resource_stone_pickaxe_secure

## Statement

Refuted as alternate-trajectory contamination: the live last-per-step route at step 4200 is y55 from (-3003.70,-5565.43) to (-3002.30,-5565.43), not the claimed y52 tunnel near z -5563.70.

## Evidence

- At step 4087 mine_forward broke nine stone, advanced 3.0 blocks east to (-2994.3,52,-5563.7), collected eight cobblestone, and left 107 stone-pick uses. The registered historical exposure is near player pose (-2993.3,55,-5563.7).
- Step 4087 mine_forward broke nine blocks and advanced 3.0 blocks; map fixes the endpoint. Four ceiling blocks broke by step 4163, then use events consumed one dirt and two cobble while STATE returned to y52.
- maps/visited.csv contains duplicate trajectories, but its final row for step 4200 is (-3002.30,55,-5565.43); current events lines 143-155 and frame 4200 match this y55 stone tunnel.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
