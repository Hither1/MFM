# resource_live_plank_craft_1073

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 1073
- updated_step: 1102
- depends_on: resource_live_early_logs

## Statement

The current run securely crafted four spruce planks at step 1095, banked them in hotbar slot 1 at step 1099, and lifted all four onto the cursor at step 1102 for the crafting-table recipe; two spruce logs remain banked in slot 0.

## Evidence

- Step-1073 STATE has GUI open; CURSOR reports spruce_log x3 over hotbar slot 0; INV recorded spruce_log -3 when the stack was lifted. The current-prefix inventory was otherwise empty.
- events/events.jsonl records craft_item spruce_planks +4 at step 1095; step-1099 INV records spruce_planks +4, and step-1102 INV records spruce_planks -4 after lifting the stack. STATE still lists spruce_log x2 banked. The displayed cursor spruce_log x1 is the known stale GUI label and conflicts with authoritative inventory/event evidence.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
