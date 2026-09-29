# recover_crafting_table
Preconditions: exact placed-table center known, player within reach, GUI closed, pickaxe selected.

1. `look_at(x=-3002.5,y=68.5,z=-5569.5)` centered the live table from `(-3000.59,66,-5566.85)`.
2. `mine_ahead(n=90,ore_watch=false)` held one ray continuously. The table broke after about 81 attack ticks (`mine_block crafting_table` at step 4100); prior 60- and 70-tick holds had stopped too early.
3. `collect_drops(ticks=24)` from the break area picked it up after 10 ticks (`pickup crafting_table` at step 4119).

Failure guard: do not sweep until the break event exists, and do not keep attacking after it; approach the drop if the first nearby sweep reports nothing.
