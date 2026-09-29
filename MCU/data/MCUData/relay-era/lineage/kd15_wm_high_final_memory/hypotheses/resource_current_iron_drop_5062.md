# resource_current_iron_drop_5062

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 5062
- updated_step: 5710
- depends_on: goal_mine_iron_ore, resource_free_slots_5400

## Statement

The current-reset north-vein recovery is complete: three iron ore are held after mine_forward opened the narrow bore and the player crossed the drop sites.

## Evidence

- The step-5062 event stream ends with the iron-ore break and no pickup iron_ore event; the attached frame shows a floating block item immediately ahead.
- The step-5062 iron break generated no pickup event. Granite x4 was force-dropped near z=-5577.35 to free a slot; the step-5189 sweep near the recess found nothing, while the live frame still shows an iron-speckled wall face ahead and a gray nuisance drop to the right.
- Iron blocks broke at steps 5062 and 5222 with no pickup iron_ore event. Mine_ahead broke four blocks, forward moved only 0.01, and step_5400 shows a floating item ahead.
- At step 5670 the authoritative event stream records pickup iron_ore +3, and step 5710 inventory lists iron_ore x3.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
