# Spatial model — live step 11400

- Live pose is `(-3000.70,66.00,-5567.90)`, pitch `-52.9°`, cumulative yaw `-126.3°`; frame 11400 shows the empty-handed player looking up at exposed spruce bark. In the final, event-matching `visited.csv` trajectory, post-death coverage is x `[-3009.50,-3000.27]`, y `[66,73.25]`, z `[-5573.70,-5567.90]`; ignore the three earlier duplicate trajectory blocks.
- The live spruce trunk is roughly 2–3 blocks northwest of the pose, around block column `(-3001,*, -5571)` (target centre used successfully: `(-3000.5,68.5,-5570.5)`). Its y68 log was broken at 11285; the drop was not recovered. Bark still fills frame 11400.
- A this-run crafting table likely remains at block `(-3003,67,-5569)` (centre `-3002.5,67.5,-5568.5`), but interaction at 10794 opened no GUI and it is not a useful route to diamond now.
- The this-run open shaft at x/z `(-3000.70,-5565.36)` reaches y11. Its west tunnel follows z `-5562.30` to the lava death pocket near `(-3026,6,-5562)`; this is a lethal drop, not a surface route.
- All tools dropped in that lava pocket at 10624. No current-prefix event or frame verifies diamond ore anywhere; inherited post-11400 diamond coordinates are cross-trajectory contamination.
- Permanent ore facts remain in `locations/ore_registry.md`; this pass found no new ore.
