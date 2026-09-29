# resource_live_ingots_6000

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 6000
- updated_step: 6202
- depends_on: goal_iron_ingot, resource_current_iron_ore

## Statement

Exactly three iron ingots are securely owned in zero-based hotbar slot 3 at step 6202; the final furnace output was taken and merged at live steps 6158-6161.

## Evidence

- Pickup/INV +1 fired at 5568; the second craft fired at 5945 and INV +1 at 5949; no later consumption exists and frame 6000 shows the ingot stack.
- events/events.jsonl records the third craft_item iron_ingot at 6157; logs record INV iron_ingot +1 at 6161; current STATE reports iron_ingot x3 in hotbar.4 and the active furnace GRID is empty.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
