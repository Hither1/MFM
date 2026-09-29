# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 5062
- depends_on: goal_stone_pickaxe, location_current_east_tunnel_4200

## Statement

The current reset achieved mine_iron_ore at step 5062 when the north y44 tunnel broke a seed-stable iron-ore block with the stone pickaxe.

## Evidence

- Current milestone list marks it unmet; current events contain no iron event and the reset note erases old tunnels.
- Current events end with two stone-pick uses and contain no iron event; stone_pickaxe was crafted at 3377, and locations/ore_registry.md preserves the prior verified vein.
- Current events through step 4200 contain no iron event; stone_pickaxe craft fired at 3377 and exactly 26 uses followed; ore_registry preserves three prior verified iron breaks at this seed-stable site.
- Action 293 used mine_forward for 340 ticks, broke 14 blocks, advanced 6.6 tunnel blocks, and moved the authoritative pose from (-2999.70,49,-5576.70) to (-2992.30,49,-5576.70); no iron event fired and the held stone pick now has 98/131 uses.
- Steps 4372-4672 advanced the east tunnel by 6.0 blocks and collected 11 cobblestone; step 4674 only aimed downward because the prior plan hit its tick cap, so no descent or iron event occurred.
- Authoritative step-4771 STATE confirms y44, position, north-facing yaw -180, and 80/131 uses; locations/ore_registry.md records the prior-reset approach and vein coordinates.
- Current events end at 4800 with no iron event; current-reset visited coordinates match the permanent approach in locations/ore_registry.md.
- events/events.jsonl records both MILESTONE mine_iron_ore and mine_block iron_ore +1 at step 5062.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
