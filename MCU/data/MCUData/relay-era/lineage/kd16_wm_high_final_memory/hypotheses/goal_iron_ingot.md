# goal_iron_ingot

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 9432
- depends_on: goal_mine_iron_ore, goal_furnace, resource_iron_ore_drop_6296, state_live_furnace_output_8193

## Statement

The live reset achieved iron_ingot at step 9432 when the three ingots released from the destroyed furnace were collected; both pickup iron_ingot +3 and the environment milestone are verified.

## Evidence

- events/events.jsonl records craft_item iron_ingot +1 at step 7303 but no pickup iron_ingot; step 7307 authoritative state shows iron_ingot x1 in zero-based hotbar slot 7, with furnace input and fuel still occupied.
- events/events.jsonl records MILESTONE iron_ingot and pickup iron_ingot +1 at step 7354; live inventory contains iron_ingot x1.
- Current events contain no pickup iron_ingot.
- At step 8193 the furnace GUI showed input and output occupied but fuel empty. Step 8238 inventory is full and still includes a wooden pickaxe; events contain craft_item iron_ingot at 7843 but no pickup iron_ingot or milestone.
- Events verify iron_ingot crafting +1 at step 7843 and +2 at 8274 but no pickup; step 8559 zoom shows the silver ingot sprite overlapping the furnace face, while the hotbar visibly has empty slots 2, 3, and 5 after stone_pickaxe -1 and forced close at 8535.
- Events verify iron_ingot production +1 at step 7843 and +2 at 8274 but no pickup. After attack x200 through step 8759 there is still no mine_block furnace event; frame 8799 retains the centered outlined block with dropped pickaxe sprites overlapping it, and the step-8799 sweep found nothing.
- No pickup iron_ingot event exists through step 9419. Frame 9419 shows the furnace absent after the continuous break, so collision no longer blocks reaching the newly released output.
- Step 9432 records [INV] iron_ingot +3, pickup iron_ingot +3, and MILESTONE iron_ingot verified.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
