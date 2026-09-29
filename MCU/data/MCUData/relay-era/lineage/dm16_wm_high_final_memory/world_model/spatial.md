# Spatial model - live step 11400

- Use each duplicated map step's last row. Authoritative pose is `(-3055.47,11.00,-5558.48)`; final map yaw `-3720` normalizes to 240°. Frame 11400 is underground, disproving alternate surface-reset records.
- This-run-only route: shaft `(-3000.70,-5566.70)` to y11 -> west to x about `-3015` -> +z correction to `-5558.48` -> straight west tunnel to the diamond pocket.
- Verified natural diamond block centre: approximately `(-3060.5,12.5,-5558.5)`. `look_at` targeted it from `(-3058.21,12,-5558.48)`; ground truth then records `mine_block diamond_ore` at 11261. Permanent entry is in `locations/ore_registry.md`; the mined cell is empty this run.
- The resulting diamond item is this-run-only and should lie at/under that cell, about 5.0 blocks west of the current pose. No pickup event exists through 11400.
- The failed 24-tick sweep moved east from `x=-3058.70` to `-3055.78`, away from the drop. Return by coordinate, not by another remote sweep.
- A stone pickaxe was deliberately dropped at the current pose at 11399; move west and do not cross this fresh drop again. Older dirt/redstone/coal/andesite drops are farther east and irrelevant.
