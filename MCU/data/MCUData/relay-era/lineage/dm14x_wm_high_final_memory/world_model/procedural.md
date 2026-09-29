# Procedural model — live step 11400

## Verified reusable sequences
- Recipe details are preserved in `procedures/`. Events verify table 591, wooden pick 781, stone pick 2194, furnace 2261, iron ingot 5211, and iron pick 8008.
- For this spruce, exact geometry beat the detector: from about `(-3001.7,67,-5569.3)`, `look_at(-3000.5,68.5,-5570.5)` then `chop_tree(n=100,until_logs=1)` produced `mine_block spruce_log` at 11285.
- After any real ore alert: `aim_at_ore` -> `mine_ahead(n=120)` -> immediate on-block `collect_drops`, using the required tool tier and a free slot.
- Deep search previously worked as `dig_down` to y11, then level ore-watched mining, but the west branch ended in lava without diamond.

## Current emergency guidance
1. No complete diamond procedure is feasible from the empty inventory in 600 ticks.
2. If testing the visible tree anyway, do not retry `aim_at_tree`; exact-aim a visible bark face. After a break, move through/around the trunk column before one sweep because near-side arcs missed the log.
3. Do not enter the open shaft or plan around the lava death kit. Rebuilding to an iron pick requires the full saved crafting/smelting chain and more time than remains.

Failed: repeated detector-led chops timed out; y67 target broke grass, y69 target broke leaves, four 24-tick sweeps recovered no log, and table use at 10794 opened no GUI.
