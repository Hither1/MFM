# Procedural model — live reset step 11400

## Verified sequences
- Iron pick recipe is recorded in `procedures/iron_pickaxe.md`; `craft_item iron_pickaxe` fired at 9550 and banking at 9555. The y43→9 shaft descent took 479 ticks.
- Durable disposal worked once: retreat east from the target by ~4 blocks, open inventory, lift expendable stack, force-close, then return west. Gravel x3 stayed behind, but subsequent flint pickup refilled the slot.

## Final local diamond search
1. Free one slot again by dropping an expendable non-merging stack at least 4 blocks east; return to x about `-2999.7`. Recheck events after every gravel break because flint can refill capacity.
2. Treat `(-3000.5,9.5,-5572.5)` as a region center, not a proven face. The current pitch `46.7`/yaw `100.9` ray already proved stone then gravel. Do not repeat it unchanged.
3. Inspect/target one adjacent exposed face at a time (upper/lower and north/south offsets around the west recess), then `mine_ahead(30–60)`. Require a live `mine_block diamond_ore`; ordinary stone/gravel means shift the ray by one block.
4. On a diamond break, stand into that exact recess and `collect_drops(24–48)`; require `pickup diamond`. Mine any visibly contiguous cyan face while capacity and durability remain.

## Failed sequences
- `mine_forward` passed through the inherited x coordinate without ore, and exact `look_at(-3000.5,9.5,-5572.5)` hit stone/gravel. Blindly extending either path is not a coordinate test.
- Leaving the only table at y44 with three planks blocks both diamond tool crafts at y9.
