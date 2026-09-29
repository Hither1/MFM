# Procedural model — step 11400

## Extract the exposed west-wall diamond
1. Preconditions: GUI closed, iron pick selected, pose near `(-2999.31,9,-5572.74)`, andesite left at z -5575.30, at least one free slot.
2. Finish only the currently cracked overhead stone (`mine_ahead` briefly), then stop. The target is not farther down the corridor.
3. Center the low-left cyan block: from yaw ~-4 use `look_abs(pitch=30..40,yaw=-20..-25)`, then `aim_at_ore`. Coordinate fallback is candidate block center `look_at(-3000.5,9.5,-5572.5)`; visually/event-check that it is cyan diamond, not tan iron.
4. `mine_ahead(n=60,ore_watch=false)`. Require a new `mine_block diamond_ore` event; if absent, re-aim rather than swing again.
5. Immediately enter the opened west cell. At yaw near 0, use `right+jump` 12–20 ticks (prior left strafe moved east), or `go_to(x=-3000.2,z=-5572.5,within=0.4,n=30)`. Then run one `collect_drops(48)`.
6. Require `pickup diamond` in events. If it fires, traverse the recess once for merged/older drops and mine any newly exposed cyan faces; do not leave for the surface.

## Proven reusable
- Iron-pick crafting is in `procedures/iron_pickaxe.md` (craft 7905, bank 7910). Surface crafting is unavailable inside the remaining budget because y9→68 pillar ascent alone costs ~850–900 ticks.
