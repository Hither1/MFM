# state_iron_pick_cursor_9000

- kind: state
- status: stale
- confidence: 1.00
- created_step: 9000
- updated_step: 4800
- depends_on: goal_iron_pickaxe

## Statement

The step-9000 cursor-held iron pick belongs to another trajectory; iron_pickaxe remains unmet in the live reset at step 4800.

## Evidence

- The step-8996 output click fired the craft at 8998; the following cursor_to_slot(slot=4) landed at container (91,153), with no subsequent banking click before the induction boundary.
- Current milestone list is 5/24 and current events end before any iron acquisition.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
