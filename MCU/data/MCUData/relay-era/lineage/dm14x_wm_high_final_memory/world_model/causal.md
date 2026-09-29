# Causal model — live step 11400

- Nine milestones are banked, but death removed every produced item. Prior `iron_pickaxe` credit does not satisfy diamond ore's physical tool requirement.
- Required live chain is logs/pickup -> planks/sticks -> wooden pick -> cobblestone -> stone pick -> iron ore + fuel + furnace -> three ingots -> iron pick -> safe y5–12 access -> expose diamond ore -> break -> pickup.
- The player currently has none of those resources. The one newly broken log was not picked up, and even owning it would not skip the stone/iron/smelting chain.
- The old iron pick dropped in lava near `(-3026,6,-5562)`; safe access alone costs about 1,980 ticks and item survival is unverified. The open shaft is fatal.
- No event-verified diamond location shortens the chain; y55 and visible-diamond beliefs from duplicate trajectories are invalid.

## Goal check
- Portfolio: only `diamond` remains. About 600 ticks remain versus 1,730–1,980 for safe descent alone and 2,194 historically just to reach a stone pick.
- Diamond pickup is infeasible from the empty surface state; the recent tree work cannot change score within budget.
- Cheapest unmet milestone is necessarily `diamond`; no cheaper credit remains to bank. Avoid shaft entry, lava-kit recovery, and cross-trajectory coordinates.
