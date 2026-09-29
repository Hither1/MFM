# Causal model — step 11400

## Milestone spine
- Verified 10/24. `mine_diamond_ore` is complete; `diamond` remains blocked by no pickup event despite three old breaks.
- Inventory capacity is now resolved: stone pick and remote andesite were deliberately dropped with no later pickup. Targeting was the second blocker: recent attacks hit forward iron or empty space while frames prove intact diamond low on the west wall.
- Current overhead clearing removes entry collision. Next dependency chain is: center cyan west block → break it with iron pick → move to smaller x into its cell → `pickup diamond`.
- `diamond_pickaxe` needs 3 diamonds + 2 sticks + 3x3 table; sword needs 2 + 1 stick + table. Both are blocked by the y68 table. Obsidian and all Nether/End milestones depend on still longer chains.

## Goal check
- Spend ~80–180 of the remaining 600 ticks extracting and physically entering the known diamond cell; this is the only plausible additional milestone.
- If one pickup fires, spend the remainder exhausting adjacent cyan faces and sweeping the recess; stacked diamonds do not create another milestone here.
- Surface return alone costs ~850–900 ticks, so diamond-pickaxe/sword crafting is mathematically out of budget even if enough diamonds drop.
- Cheapest unmet milestone is `diamond`; do not divert to strip mining, surface ascent, flint, or Nether setup.
