# resource_current_lighting_kit

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 4800
- updated_step: 8600
- depends_on: resource_early_logs, goal_furnace, goal_stone_pickaxe, resource_surface_wood_after_furnace

## Statement

No lighting kit is owned at step 8600: sticks x4 are present, but no coal, charcoal, or torches exist.

## Evidence

- Step-9890 events record use_item torch +1, and step-9894 STATE reports torch x4 and coal x2.
- Frame/STATE at 9894 reports torch x4 and coal x2; events through 10200 contain no later torch use or stick acquisition.
- Step-10594 STATE explicitly reports torch x2 and coal x2, with no sticks. Events at 10424/10426 record two torch uses, but one torch was picked back up at 10460 after the support was mined.
- Authoritative step-10604 STATE reports torch x1 and zero free slots; events record use_item torch at 10602 and 10604.
- Step-10624 deltas remove coal x2 and every stack; frame 10800 has an empty hotbar.
- Frame 3600 shows only stone pick, dirt x2, wooden pick, and cobblestone x1; current events contain no coal pickup or torch craft/use.
- Frame 8000 hotbar contains pick, dirt, gravel, ingots, cobblestone, ore and sticks only; current-prefix events have no retained coal/torch after the earlier shallow coal was spent.
- Frame 8600 shows four sticks and no lighting/fuel stack; no current-prefix torch or charcoal craft follows.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
