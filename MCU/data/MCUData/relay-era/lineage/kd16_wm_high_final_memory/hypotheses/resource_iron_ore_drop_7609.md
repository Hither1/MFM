# resource_iron_ore_drop_7609

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 7609
- updated_step: 7987
- depends_on: goal_mine_iron_ore

## Statement

The loose iron ore from the step-7609 break was recovered at step 7975 and is now held as iron_ore x1.

## Evidence

- The iron block broke on the final mining tick at position (-2955.3,61.0,-5567.7), and no subsequent pickup iron_ore event or inventory increase appears in the log.
- At step 7619 collect_drops increased cobblestone x56 to x57, no pickup iron_ore event fired, and the authoritative state reports 0 slots free.
- events.jsonl has no pickup iron_ore through 7800. The first sweep stopped after cobblestone rose at 7619; later sweeps started near x=-2954.96 but ended west at -2957.49 and -2959.22. Empty hotbar cells are visible.
- events/events.jsonl records pickup iron_ore +1 at step 7975, and the authoritative step-7987 inventory reports iron_ore x1 in hotbar slot 2.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
