# Procedural model — live step 11600

## Iron chain — verified this run

1. One ore plus two sticks in a furnace produced output after ~214 ticks; clicking output fired `craft_item iron_ingot` at 11199, and stowing fired `INV iron_ingot +1` at 11203.
2. At the table, put three ingots in cells 0/1/2 and sticks in 4/7. Clicking output fired `craft_item iron_pickaxe` and milestone at 11323; re-land on an empty hotbar slot and click until `INV iron_pickaxe +1` (11328).
3. Replay `procedures/craft_iron_pickaxe.md`. Trust the craft event, active grid, and INV deltas over stale consumed-ingredient cursor labels.

## Failed direct-diamond transfer

The direct surface plan toward `(-3060.5,-5558.5)` is not a working 400-tick procedure. A 205-tick sprint moved 10.35 blocks; `go_to` reported dense-tree obstruction 51.8 blocks short, and by 11600 the player remained at surface y68, 42.8 horizontal blocks short with a trunk ahead. No descent or diamond event occurred.

Force-close is safe only when every cursor label is proven phantom. At 11336 the cursor also held a real stone pick (`INV -1`), so the close intentionally dropped it; do not generalize that close as lossless for mixed real/ghost contents.
