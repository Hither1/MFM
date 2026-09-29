# Spatial model — live reset step 11400

## This-run topology
- Current map pose is `(-2999.75,9.00,-5572.30)`, pitch `46.7`, yaw `-259.1` (= `100.9`, west-northwest). The west y9 tunnel spans x about `-2985.5..-3000.7` at z `-5572.30`.
- Reset-local route: shaft `(-2985.48,-5578.70)` connects y43→9; its floor runs south to z `-5572.30`, then west to the live pocket. The route is open but the table is 35 levels above.
- The inherited diamond search center is around `(-2999.3,9,-5572.7)` / west wall center `(-3000.5,9.5,-5572.5)`. It is not an exact live block coordinate: the direct ray from `(-2999.66,9,-5572.30)` broke stone at 11365 and gravel at 11389, with no diamond event.
- The sole table is this-run-only at the y44 worksite near `(-2985.46,-5579.44)`; exact recovery ray remains unresolved. It is not carried.
- Final-reset coverage through 11400: x `[-3010.11,-2985.30]`, y `[9,73.25]`, z `[-5582.70,-5565.30]` (`maps/visited.csv` after final step-0 marker).

## Permanent seed sites
- Spawn `(-3009.5,71,-5572.5)` and north iron recess near `(-2985.5,44,-5581.7)` are proven. Keep the y9 diamond entry in `locations/ore_registry.md` as inherited search evidence, but current events and available frames do not verify its claimed exact face.
