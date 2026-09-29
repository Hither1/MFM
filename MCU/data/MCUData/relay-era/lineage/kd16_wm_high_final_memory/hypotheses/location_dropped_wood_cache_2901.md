# location_dropped_wood_cache_2901

- kind: location
- status: stale
- confidence: 0.95
- created_step: 2901
- updated_step: 2906
- depends_on: goal_wooden_pickaxe, goal_crafting_table

## Statement

The force-closed crafting ingredients did not remain as a usable loose cache: by step 2906 the player had automatically recovered the three remaining spruce planks and two sticks, filling all three inventory slots.

## Evidence

- Step 2901 ground truth shows the table GUI open at (-2999.3,65,-5568.7), wooden_pickaxe as the sole inventory stack, and spruce_planks x6 plus stick x4 off-inventory in 3x3 cells [0,1,2,4,7]. The planned force-close intentionally drops those ingredients at this pose.
- Step 2904 force-close dropped off-inventory ingredients; the step-2906 dig_down prelude records [INV] spruce_planks +3, stick +2, and the authoritative inventory has exactly those stacks plus the wooden pickaxe.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
