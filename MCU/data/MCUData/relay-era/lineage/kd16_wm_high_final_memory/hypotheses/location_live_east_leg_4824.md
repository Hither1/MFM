# location_live_east_leg_4824

- kind: location
- status: stale
- confidence: 1.00
- created_step: 4824
- updated_step: 6600
- depends_on: location_seed_north_iron_vein, location_current_iron_approach_3600

## Statement

The step-6000 east-leg endpoint is historical: the live route continued east to x=-2985.30 and north to the iron face at z=-5581.28 by step 6600.

## Evidence

- Action 295 ending at step 4824: mine_forward broke four stone blocks, advanced 0.4, and stopped after two no-movement cycles; authoritative STATE and final visited.csv rows give the current pose.
- Action 297 ending at step 4970: due-east mine_forward broke six stone, advanced exactly 1.0 block, and stopped after two break-without-movement cycles; authoritative STATE gives the new pose.
- Action 299 mine_forward broke 15 blocks and advanced 6.5 blocks in 360 ticks; authoritative STATE and visited.csv end at (-3003.30,44.00,-5575.70), while ore_registry places the reliable approach near (-2985.70,44,-5578.93).
- Final-reset visited.csv rows 5333-5400 give the fixed pose and yaw 270; events record diorite breaks at 5354 and 5374, and logs contain no completed mine_forward note for this still-partial leg.
- Final-reset visited.csv rows verify the pose and 13-block advance; events from 5336-6000 record only ordinary rock and stone-pick use.
- Final-reset visited rows and ordinary-rock events show progression from (-2990.30,44,-5575.70) at 6000 to (-2985.30,44,-5581.28) at 6600.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
