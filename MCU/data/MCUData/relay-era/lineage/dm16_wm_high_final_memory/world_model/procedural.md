# Procedural model - final through live step 11600

## Verified diamond extraction and recovery

1. Exact targeting plus `mine_ahead(120)` produced `mine_block diamond_ore` at 11261.
2. Ensure a real inventory slot is free; the stone pickaxe force-drop at 11399 supplied capacity.
3. Return toward the registered break coordinate with `go_to`; use `collect_drops` only as a local sweep, not as proof of target pickup.
4. If `collect_drops` stops on an incidental item, inspect `[INV]/[EVENT]`. At 11440 it stopped on cobblestone, so the correct continuation was the queued coordinate-directed movement.
5. The next 0.19-block nudge produced `[INV] diamond +1`, `pickup diamond +1`, and the verified milestone at 11444.

Failure signature: `collect_drops: inventory rose ... stopping` names no target and can be satisfied by debris. The separating check is the item identity in `[INV]/[EVENT]`; continue locally when it is not the desired item.

## Completion state

All milestones are verified. Do not mine, travel, open inventory, or repeat recovery procedures. Remaining stationary is the lowest-risk terminal policy.
