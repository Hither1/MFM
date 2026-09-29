# location_reachable_spruce_5400

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 5400
- updated_step: 5400
- depends_on: goal_mine_log

## Statement

Refuted: frame 5400 is an underground furnace GUI and shows no reachable spruce trunk.

## Evidence

- The step-5400 frame clearly shows multiple lower trunk columns ahead-left and ahead-center; exact block targeting remains untested.
- At step 5407 a spruce trunk fills the crosshair area at close range; this turn tests it with aim_at_tree followed by up to three verified chop cycles.
- Steps 5415-5650 remained at (-3016.27,67.00,-5558.58), pitch -5, yaw -70 and each aim reported no trunk; the current frame visibly places a thick trunk to the right of the unchanged crosshair.
- Step 5874 aim_at_tree reported crosshair centred on 4514 px of bark, 0/9 px off; current frame shows the broad trunk directly ahead, while earlier chops occurred before this successful re-aim and reported out of reach.
- events/events.jsonl records mine_block spruce_log at step 5958 after the approach to (-3015.54,68.00,-5554.60); this settles reachability, though not pickup.
- Frame step_5400 visually suggests trunks, while events through 5400 contain no post-984 spruce_log mine/pickup; all later claimed evidence is outside the current horizon.
- Direct inspection of episodes/ep_0000/frames/step_5400.png shows furnace inventory and stone surroundings.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
