# Semantic model - live step 11400

- Score is 9/10. `mine_block diamond_ore` is ground-truth at 11261, but the scored condition is specifically `pickup diamond`; no such event or milestone exists through 11400.
- Diamond ore is cyan-speckled stone and requires an iron pick. The selected iron pick successfully broke this block and one stone behind it; extraction tier and durability are no longer gates.
- Breaking ore spawns an item entity near the broken cell. It is not owned until a pickup/INV event fires, even if the block statistic fired.
- Pickup radius is about one block. The player must stand at the break site; `collect_drops` from several blocks away can sweep in the wrong direction.
- Capacity is available: `INV stone_pickaxe -1` at action step 11396 plus the forced-close note at 11399 prove hotbar slot 0's unique stack was dropped. Move away before its pickup delay expires.
- Granite x5 was recollected at event step 11389, explaining why the earlier granite disposal did not remain useful. Do not reopen inventory or discard anything else.
- Natural ore sites persist across resets; item entities, mined cells, tunnels, and deliberate drops are this-run-only.
