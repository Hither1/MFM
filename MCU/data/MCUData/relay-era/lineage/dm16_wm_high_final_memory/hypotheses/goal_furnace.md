# goal_furnace

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 1200
- updated_step: 3494
- depends_on: goal_mine_cobblestone, goal_stone_pickaxe, location_current_crafting_table, location_live_table_957, resource_current_cobblestone, goal_crafting_table, goal_wooden_pickaxe

## Statement

The furnace milestone was environment-confirmed at live step 3494 when the completed eight-cobblestone ring output was taken from the crafting table.

## Evidence

- No craft_item furnace exists in current events; the 6/10 header leaves furnace unchecked and frame 5400 confirms x52 cobblestone.
- At step 5989 the cobblestone remainder was returned to hotbar slot 4; at step 5992 the 3x3 output was FULL; after gui_click at step 5995 the active 3x3 grid cleared. procedures/craft_furnace.md records this exact stale-cursor pattern after a successful output take.
- events/events.jsonl records both the furnace milestone and craft_item furnace at step 5997; the active 3x3 grid cleared after output pickup.
- events/events.jsonl records craft_item/milestone furnace at 5997; logs records [INV] furnace +1 at step 6002; authoritative step-6075 STATE lists furnacex1 in hotbar slot 3.
- events lines 353-354 verify craft/milestone at 5997; logs show INV furnace +1 at 6002, INV furnace -1 at 6275, and events line 366 use_item furnace at 6279.
- No furnace craft exists in current events; no cobblestone is yet owned.
- No craft_item furnace exists through 2400; x18 cobble exceeds the combined 11-block cost.
- At Action 281 / Step 3494, events/events.jsonl and the harness report MILESTONE furnace verified and craft_item furnace +1; the active 3x3 grid cleared.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
