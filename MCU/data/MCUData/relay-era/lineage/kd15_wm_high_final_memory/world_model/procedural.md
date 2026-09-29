# Procedural model — step 11938

## Iron pickaxe — verified
1. In an open 3x3 table place ingots in `0,1,2`, sticks in `4,7`, and bank stick remainder.
2. Require `out=FULL`; re-land on output and click, then re-land on an empty player slot and click.
3. Evidence: milestone and `craft_item iron_pickaxe` at 10860; `[INV] iron_pickaxe +1` at 10865.

## Vertical mining — verified, now too late
1. Select iron pick and aim near absolute pitch 88.
2. If `dig_down` is truncated without y change, use fixed `mine_ahead` and verify map descent. This achieved about one level per 14–15 ticks from y65 to y32.
3. Stop on lava light/health loss. Reacquire any visible ore before fixed attack; require the matching mine event.

## Failed direct intercept
- Pitch 73/yaw 151 plus forward+attack is not a staircase procedure. It broke six blocks, gained no horizontal displacement, then no-op'd for 326 ticks. Never repeat it in this geometry.
- One-wide diagonal mining that breaks blocks without advance must be replaced by a cardinal two-high tunnel or a widened stair.

No unmet milestone procedure fits the final 62 ticks; surface return, GUI work, and drop sweeps without a target break are invalid final plays.
