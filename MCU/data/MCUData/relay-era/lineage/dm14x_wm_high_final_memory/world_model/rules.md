# Standing rules

- Trust only current-prefix events, matching STATE/map rows, and retained frames; reject future or cross-trajectory claims [x37]
- When `visited.csv` repeats a step, use the final trajectory block matching live events/frame; never merge duplicate paths [x10]
- Keep event-verified natural ore sites across resets, but treat shafts, workstations, furnaces, and caches as this-run-only [x13]
- After a zero-result, two-cycle stall, or governor stop, change aim, heading, position, or method before retrying [x30]
- After death, rebuild inventory from STATE deltas; milestone credit does not mean the crafted item is still owned [x2]
- Never jump into an open deep shaft; descend by a staged staircase with enough ticks and tools [x1]
- In lava, turn toward the exit and use forward sprint-jumps immediately; backward swimming is too slow [x1]
- Treat GUI cursor residue as stale after a verified craft and cleared active grid; do not search for phantom ingredients [x2]
- Sweep through the exact broken block and its far side immediately; near-side arcs are not pickup evidence [x7]
- If `aim_at_tree` fails while bark is visible, use exact world geometry or manually centre a bark face before chopping [x4]
- Treat ore pixels as candidates until texture plus a matching current-prefix event verifies the block [x9]
- Once cyan ore is visible, stop translation, exact-mine it, then sweep until `pickup diamond` fires [x5]
