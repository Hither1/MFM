# Dynamics model — live reset step 11400

- `dig_down` reached y9 from y43 in 479 ticks (14.1 ticks/level) without damage; ascent/table recovery would consume most of the 600 remaining ticks.
- West `mine_forward(345)` advanced 8.22 blocks and the next `mine_forward(320)` broke 14 blocks/advanced 6.5: budget about 42–50 ticks per tunnel block. It overshot from x `-2993.7` to `-3000.7` without a diamond event.
- The exact candidate ray began at 11353: stone broke after 12 ticks (11365), gravel after another 24 (11389), and flint was picked up 10 ticks later. Fixed `look_at` coordinates can traverse ordinary blocks without testing adjacent faces.
- A deliberate inventory drop costs about 30 GUI ticks plus separation travel; gravel dropped at x `-2995.33` was not recollected after returning four blocks west. Any later pickup can immediately consume the freed slot.
- `collect_drops(80)` after no ore break moved 1.24 blocks and collected nothing. Use a 24–48 tick sweep only from a verified break cell.
- Iron pick: 71/250 uses consumed, about 179 remain. Correctly centered stone/ore blocks generally break in 12–30 attack ticks; table recovery needs about 81 centered attack ticks plus travel.
