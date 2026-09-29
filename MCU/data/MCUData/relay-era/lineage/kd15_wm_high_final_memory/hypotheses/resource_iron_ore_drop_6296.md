# resource_iron_ore_drop_6296

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 6528
- updated_step: 6693
- depends_on: goal_mine_iron_ore, goal_furnace

## Statement

The current-reset iron ore block broken overhead at step 6669 was collected at step 6685 after the furnace placement freed a slot; one iron ore is secured in zero-based hotbar slot 5 and the furnace GUI is open for smelting.

## Evidence

- events/events.jsonl verifies iron_ore mine_block events at steps 6296, 6335, and 6364, while every subsequent STATE through 6528 has zero free slots and no iron ore inventory stack.
- Events verify three iron breaks and no iron pickup; step-6600 hotbar shows two empty cells. Prior sweeps stopped on cobble or moved south.
- events/events.jsonl records pickup iron_ore at steps 6866 and 6871, and the authoritative step-6952 inventory reports iron_ore x2.
- events/events.jsonl records iron_ore pickups for the two recovered drops and the step-7042 block; authoritative step-7103 inventory reports iron_ore x3.
- Current events through step 6669 contain mine_block iron_ore but no pickup iron_ore; STATE remains at the break position and lists the furnace in hotbar slot 6 with zero slots free.
- events/events.jsonl records pickup iron_ore +1 at step 6685; the step-6693 authoritative inventory lists iron_ore x1 in zero-based hotbar slot 5 and GUI open=True.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
