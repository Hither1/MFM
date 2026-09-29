# Causal model — live reset step 11400

## Milestone spine and blockers
- Verified spine is `9/24`. Iron pick + actual diamond face → `mine_diamond_ore`; nearby drop sweep + free slot → `diamond`. The inherited coordinate has narrowed the search region but has not supplied the face.
- Capacity was freed by dropping gravel, then lost to `pickup flint` at 11399. Mining credit does not need space; diamond pickup does.
- Three diamonds + held sticks x2 + table → diamond pick; two diamonds + stick + table → sword. The table is at y44 and only three planks remain, so both crafts are ascent-gated.
- Diamond pick → obsidian; spare ingot + held flint → flint-and-steel; those gate Nether/blaze, then pearl/eye/End. No spare ingot, portal, or time remains.

## Goal check
- With 600 ticks left, spend ~50–90 freeing capacity and ~200–350 testing adjacent faces around the current recess; reserve 40–80 for a verified break-cell sweep. Target portfolio: `mine_diamond_ore` then `diamond`.
- The stale plan to extend the west tunnel is wrong: it already passed x `-2999.3` and the exact candidate ray hit stone/gravel. Search locally by one-block ray offsets.
- Do not climb to the y44 table; even perfect recovery leaves the prerequisite diamond unresolved and consumes the budget.
- Cheapest unmet milestone is `mine_diamond_ore`; if time tightens, mine the ore first even without pickup capacity.
