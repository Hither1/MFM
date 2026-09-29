# resource_coal_5693

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 5693
- updated_step: 6000
- depends_on: state_inventory_5693, goal_iron_ingot

## Statement

The coal-at-5693 belief is refuted for this live trajectory: authoritative events at that stretch are diorite/stone only, and the step-6000 hotbar has no coal.

## Evidence

- Two coal pickups are verified at steps 5636 and 5667 and the authoritative inventory reports coal x2.
- Pickup coal events occurred at 5636 and 5667; craft_item torch +4 at 5746 consumed one; pickup coal at 5953 is also verified.
- events.jsonl records diorite at 5637/5657 and no coal pickup through 6000; frame shows no coal stack.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
