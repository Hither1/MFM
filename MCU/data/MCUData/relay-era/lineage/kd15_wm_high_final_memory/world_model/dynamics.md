# Dynamics model — step 11938

- Fixed downward iron-pick attack descended y65→60 in 80 ticks and y60→32.92 in 401 ticks: about one level per 14–15 ticks. From y32 to y9 therefore costs roughly `336–360` ticks before horizontal travel.
- `dig_down` was repeatedly truncated with no y change; a fixed pitch-88 `mine_ahead` produced the descent. Judge success by map y and events, not requested budget.
- The pitch-73/yaw-151 raw forward+attack intercept failed: over its first 200 ticks it broke six ordinary blocks, changed y only `32.77→32.00`, and changed x/z by `0`; the following 200 ticks produced no event or movement. A steep ray does not carve a walkable staircase in one-wide stone.
- A cardinal two-high approach over 8–10 blocks costs about `300–450` ticks. Diagonal one-wide cuts repeatedly break blocks without advancing.
- The iron pick has 43 verified uses after crafting (about 207 nominal uses left); durability is ample.
- A nearby drop sweep can succeed in about 10 ticks, but only after the target break and bodily entering the recess.
- GUI landings cost up to 16 ticks and smelting one ore about 200–208; neither can fit a useful unmet chain now.
