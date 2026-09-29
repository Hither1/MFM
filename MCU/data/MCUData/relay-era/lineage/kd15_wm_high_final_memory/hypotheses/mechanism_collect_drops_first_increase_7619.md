# mechanism_collect_drops_first_increase_7619

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 7800
- updated_step: 7800
- depends_on: resource_iron_ore_drop_7609

## Statement

collect_drops stops on the first inventory increase even when that pickup is an irrelevant nearby item, so a cobblestone pickup does not test whether a farther iron drop is collectible.

## Evidence

- At step 7619 the procedure stopped after ten ticks because cobblestone increased by one; no pickup iron_ore event fired.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
