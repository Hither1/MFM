# resource_live_furnace_3494

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 3494
- updated_step: 3600
- depends_on: goal_furnace, mechanism_gui_cursor_stale_consumed_items, location_surface_furnace_3591

## Statement

The verified furnace output was stowed at 3498 and then consumed by a successful world placement at the surface worksite by step 3594; no furnace item remains in inventory.

## Evidence

- The output click at step 3492 cleared the active 3x3 grid and fired craft_item furnace at 3494; the existing craft_furnace procedure records this exact stale-label mechanism and requires a click into a genuinely empty slot.
- At step 3498, [INV] furnace +1 fired after gui_click over hotbar slot 1; authoritative step-3501 STATE lists furnace x1 in hotbar.2, and the active 3x3 GRID row has no occupied cells.
- INV furnace +1 at 3498, INV furnace -1 at 3591, event line 106 use_item furnace at 3594, and frame 3600 shows the placed block.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
