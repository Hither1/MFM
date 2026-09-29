# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 3874
- depends_on: goal_wooden_pickaxe, location_current_shallow_pit_2400, location_shoreline_shaft_3000, location_current_dry_pit_3600

## Statement

The current reset achieved mine_cobblestone at step 3874 when the deliberately placed wall-socket cobblestone was re-mined with the wooden pickaxe.

## Evidence

- The current event stream has no mine_block event and all inherited placed blocks were erased by reset.
- Current events end with dirt mining at 2298 and contain no stone/cobblestone event; frame 2400 shows the continued dirt ray and two compact slots have been freed.
- Events through step 3000 contain no stone/cobblestone event or milestone; frame 2809 shows bottom stone while two lip-level mine_ahead attempts broke zero blocks.
- Steps 3028-3045 used direct forward movement to enter the opening; step 3245 records mine_block sand +2, pickup sand +2, and authoritative y=59.9, while no stone/cobblestone event has yet fired.
- Events at 3488, 3509, and 3530 verify grass/dirt breaks; live state at 3562 remains y63 and frame shows exposed stone below. The dig_down diagnosis explicitly says the avatar is on the shaft edge. Dirt was dropped at 3386 and sand at 3426, followed by travel beyond pickup range.
- Current milestone header is 3/24 and events through 3600 contain no stone/cobblestone event. Final-segment visited rows show the y63-to-y62 fall at step 3597, and the zoomed step-3600 frame identifies dirt under the centered ray.
- Ground-truth events record mine_block stone at steps 3668, 3697, and 3726 followed by pickup cobblestone +3 at step 3787; the authoritative state reports cobblestone x3 in hotbar slot 2 and wooden pickaxe 42/59 at (-2989.5,57,-5567.5).
- events/events.jsonl records MILESTONE mine_cobblestone and mine_block cobblestone at step 3874; the authoritative state reports 4/24 verified.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
