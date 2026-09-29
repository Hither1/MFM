# location_shallow_coal_2297

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2344
- updated_step: 3000
- depends_on: resource_current_lighting_kit

## Statement

Seed-persistent shallow coal pocket near (-3008.7,63→62,-5559.7), re-proved in the live run by two coal breaks and pickups; it is exhausted only in this run and reset-full in future runs.

## Evidence

- events/events.jsonl records mine_block coal_ore at step 2297, and the step-2344 frame shows additional coal-speckled blocks in the enclosed face.
- Coal ore mined at 2297/2348 and coal picked up at 2352/2358.
- Inherited ground truth recorded coal ore breaks at 2297/2348 and pickups at 2352/2358; reset restores natural resources.
- events/events.jsonl: mine_block coal_ore at 2892/2921 and pickup coal at 2902/2931; coordinates from maps/visited.csv.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
