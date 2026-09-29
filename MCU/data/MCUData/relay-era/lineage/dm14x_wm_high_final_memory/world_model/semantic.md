# Semantic model — live step 11400

- Score is 9/10; only `pickup diamond` is unmet. Current events contain neither `mine_block diamond_ore` nor `pickup diamond` through 11400.
- The player is alive at full health/hunger, GUI closed, and inventory/hotbar empty. Milestone credit persists, but the physical iron, stone, and wooden picks plus all materials were lost in lava at 10624.
- Spruce logs can be broken by hand; one break took about 70 attack ticks. A break event is not ownership: the 11285 log never produced a pickup despite a local sweep.
- The nearby table would afford 3x3 crafting, but wood only starts a long rebuild chain: planks/sticks -> wooden pick -> stone -> stone pick -> iron ore/smelting -> new iron pick.
- Diamond ore is cyan-speckled deep stone and requires a physically held iron-tier pick. The goal fires only when the diamond item enters inventory.
- Lava drops may burn and are not recoverable merely because normal despawn time has not elapsed. No pickup followed the death.
- Treat unverified textures, duplicate-map routes, and post-checkpoint coordinates as candidates, never live resources.
