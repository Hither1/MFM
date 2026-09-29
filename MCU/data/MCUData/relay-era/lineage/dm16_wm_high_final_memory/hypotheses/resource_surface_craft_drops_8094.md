# resource_surface_craft_drops_8094

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 10624
- updated_step: 10794
- depends_on: location_current_crafting_table, goal_iron_pickaxe, mechanism_gui_cursor_stale_consumed_items

## Statement

No iron-ingot or stick cache exists at the surface table: those ingredients were consumed by the verified step-8008 iron-pick craft, and the step-8094 force-close note reflected a stale cursor label rather than real items.

## Evidence

- At step 8094 close_inventory(force=true) explicitly reported iron_ingotx3 and stickx2 dropped at the table-side pose; however the iron-pick craft had already fired and prior model notes describe lingering ingredient geometry as stale.
- craft_item iron_pickaxe fired at step 8008 and INV iron_pickaxe +1 fired at 8013; the active 3x3 grid was empty after crafting, no ingredient pickup followed the force-close, and a 120-tick surface sweep through step 10771 recovered nothing.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
