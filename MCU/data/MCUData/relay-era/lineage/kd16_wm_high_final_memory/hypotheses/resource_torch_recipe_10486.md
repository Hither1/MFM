# resource_torch_recipe_10486

- kind: resource
- status: active
- confidence: 0.95
- created_step: 10486
- updated_step: 10545
- depends_on: goal_diamond

## Statement

Both torch batches were crafted, but the remaining coal/stick stack was force-dropped during the hostile interruption. Three torches remain in hotbar slot 9 after one placement; placing those three at separated tunnel positions will consume the stack and create a pickup slot without reopening the dangerous GUI.

## Evidence

- Live GUI reports 2x2 cell [0], off-inventory coal x2 and stick x2, while [INV] records stick -2 after clicking its former hotbar slot.
- events records craft_item torch +4 at step 10499 and logs record torch +4 at step 10503; authoritative step-10513 GRID still shows cells 0/2 occupied and out=FULL while hotbar.9 holds torch x4.
- events verify torch crafts at steps 10499 and 10523 and one torch use at 10537; step-10545 authoritative inventory reports torch x3, zero free slots, and health 6.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
