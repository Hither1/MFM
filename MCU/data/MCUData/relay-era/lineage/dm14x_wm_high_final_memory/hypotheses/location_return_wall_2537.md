# location_return_wall_2537

- kind: location
- status: active
- confidence: 0.70
- created_step: 2537
- updated_step: 3000
- depends_on: location_current_crafting_table

## Statement

The former return wall has been partly excavated to live pose (-3007.3,62,-5561.7); a raised opening is visible, but traversability to the old shaft is still unverified.

## Evidence

- Three closed-loop go_to attempts stopped after only 0.4 blocks and reported a wall/pit/tree obstruction; the step-2537 frame shows stone directly ahead and dirt at right.
- Ground-truth states moved from z=-5559.7 at step 2537 to z=-5561.7 at step 2825; mine_forward reported eight blocks broken and inventory gained seven cobblestone across the passage work.
- Mining through step 2966 moved about two blocks and exposed the opening, while prior go_to calls remained blocked.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
