# state_current_inventory_ep0000_1896

- kind: state
- status: active
- confidence: 0.99
- created_step: 1896
- updated_step: 1896
- depends_on: goal_crafting_table, goal_wooden_pickaxe

## Statement

At step 1896 the live inventory contains crafting_table x1 and spruce_log x1; the selected table must not be used while reacquiring the next spruce trunk, and the current crosshair is on dirt rather than wood.

## Evidence

- Authoritative step-1896 STATE lists crafting_table x1 and spruce_log x1. Frame step_1896.png shows a grass-topped dirt block under the crosshair; events record dirt mined at step 1827 and no later spruce-log break or pickup.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
