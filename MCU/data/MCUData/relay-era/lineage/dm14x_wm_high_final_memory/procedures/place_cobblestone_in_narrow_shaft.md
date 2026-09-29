# Place cobblestone in a narrow shaft

Preconditions: cobblestone selected; a solid wall face is visible two blocks ahead; the adjacent destination block is empty.

1. Back into the block behind the intended placement cell, leaving at least one full block of clearance.
2. `look_at` the centre of the solid wall block beyond the empty destination cell.
3. Send raw `{"use":1}` for one tick.
4. Verify `[INV] cobblestone -1` before attempting to mine the placed block.

Worked at step 2527 from `(-3015.69,64.00,-5561.30)`, targeting `(-3013.5,64.5,-5561.5)`. Earlier attempts failed when the player overlapped the destination cell.
