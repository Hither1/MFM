# Dynamics model — measured through live step 11400

- Normalize cumulative yaw modulo 360; positive pitch looks down. Closed-loop look procedures already handle cumulative yaw.
- Exact `look_at(-3000.5,68.5,-5570.5)` followed by hand `chop_tree` broke one spruce log in 70 ticks. Neighboring y67/y69 targets instead broke grass/leaves; three detector-led chops each timed out after 75 ticks.
- A 24-tick `collect_drops` sweep moves roughly 0.4–1.1 blocks around this uneven tree base. Four such sweeps recovered nothing; pickup requires crossing the actual drop, likely on the far side/above the broken trunk block.
- Lava dealt 4 damage about every 10 ticks; backward escape moved only 0.33 block in 16 ticks, then death removed every stack.
- The open shaft falls about 54 blocks from y65 to y11 and is fatal. `stair_down` costs about 32 ticks/level, so a safe 54–62-level route costs 1,730–1,980 ticks before travel/search.
- Historical from-scratch milestones cost 781 ticks to wooden pick and 2,194 to stone pick; replacing an iron pick and reaching diamond exceeds the 600-tick remainder by several times.
- The lost iron pick advanced level tunnels at 49–59 ticks/block; exact ore mining fit in `mine_ahead(n=120)`, but no iron-tier tool or diamond sightline now exists.
