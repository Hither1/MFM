# goal_furnace

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 1200
- updated_step: 2400
- depends_on: goal_mine_cobblestone, goal_stone_pickaxe, location_current_crafting_table, location_live_table_957, resource_current_cobblestone

## Statement

The furnace milestone was verified at step 2261 and the furnace was securely deposited in zero-based hotbar slot 6 at step 2266.

## Evidence

- No craft_item furnace event exists through step 3000; live inventory has cobblestone x12.
- Live inventory reports cobblestone x11 and the crafting table GUI is open; the verified furnace recipe needs eight.
- events/events.jsonl records both MILESTONE furnace and craft_item furnace +1 at step 4025; the live milestone list reports furnace complete and the 3x3 grid is empty.
- No current furnace craft event exists; gathering twelve cobblestone covers this recipe and the adjacent tool milestones.
- No current craft_item furnace event exists; current events/frame verify seven owned cobblestone and the placed table remains on the surface.
- No current craft_item furnace event exists; event accounting and magnified frame 1800 verify cobblestone x20.
- events/events.jsonl and the live harness report both MILESTONE furnace and craft_item furnace +1 at step 2261; the real 3x3 grid is empty and the attached frame shows the furnace icon under the cursor over hotbar slot 6.
- events/events.jsonl records milestone and craft_item furnace at 2261; logs record [INV] furnace +1 at 2266 and frame 2400 shows it in hotbar slot 6.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
