# mechanism_torch_recipe_5707

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 5707
- updated_step: 5753
- depends_on: resource_coal_5693

## Statement

Coal in inventory 2x2 cell 0 above a stick in cell 2 crafts four torches while separately banked remainder stacks are preserved.

## Evidence

- The supplied recipe specifies coal above stick in the 2x2 grid; the current cursor holds exactly two coal and its source slot is empty for banking the remainder.
- The completed layout reported 2x2 cells [0,2] out=FULL; events verify craft_item torch +4 at step 5746, and step 5753 inventory verifies torch x4, coal x1, and sticks x3.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
