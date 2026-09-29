# resource_early_logs

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 419
- updated_step: 1800
- depends_on: goal_mine_log, resource_live_early_logs

## Statement

Retired inherited-inventory claim: it does not describe this trajectory; current wood quantities are exclusively tracked by resource_live_early_logs.

## Evidence

- At step 1471 the crafting table pickup was verified, at step 1473 one spruce log pickup was verified, and step 1485 inventory lists crafting_tablex1, spruce_logx1, spruce_planksx3, stickx2.
- The 2663 recipe used cells 4 and 7 and the 3x3 grid then emptied; table pickup was verified at 2903, and current frames retain the log and planks.
- Events verify stick +4 at 4930, charcoal +1 at 5224, and torch +4 at 5289; the step-5400 hotbar shows sticks x3 and no logs/planks.
- craft_item spruce_planks +4 fired at 7831; after fueling, step 8426 returned one plank, and the step-9000 frame shows plank x1, sticks x3, and the table secured.
- Reset note plus empty live hotbar and no current pickup/craft events contradict the inherited current-inventory statement.
- Its statement concerns erased prior-expedition resources, while live events through 1800 establish the current conversion chain; the live-specific node is authoritative.
- Reset note, empty live hotbar, and absence of current log pickup events invalidate all prior inventory quantities.
- Reset semantics invalidate inherited inventory, while current events lines 10-22 and frame 1800 fully account for the live wood resources.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
