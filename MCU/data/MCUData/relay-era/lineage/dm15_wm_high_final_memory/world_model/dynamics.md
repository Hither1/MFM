# Dynamics model — measured through live step 11600

- Normalize cumulative yaw modulo 360; positive pitch looks down. GUI servos cost about 16 ticks and clicks 3; pair landing and click because cursor drift caused aborts at 10956 and 11323.
- One ore fueled by two sticks took about 214 ticks from fuel placement near 10985 to `craft_item iron_ingot` at 11199. The successful table recipe took 54 ticks from open screen at 11269 to `craft_item iron_pickaxe` at 11323, plus 5 ticks to stow it.
- Rough surface travel is slow: the 205-tick sprint from 11344 to 11549 moved only 10.35 blocks. From table to step 11600, about 18.9 horizontal blocks cost roughly 272 ticks (~0.07 block/tick).
- `go_to` through dense spruce can attack leaves (`mine_block spruce_leaves` and iron-pick use at 11569) yet still report obstruction. Do not price a 40+ block transfer as open-ground sprinting.
- At the observed rate, the remaining 42.8 horizontal blocks alone cost about 600 ticks. Surface y68 to y12 previously cost about 800–1,100 ticks with stone-tier descent; even faster iron descent cannot fit after travel in 400 ticks.
- Diamond break and drop collection add roughly 20–100 ticks after exact contact. Total residual path is safely above 1,000 ticks, excluding hazards and target uncertainty.
