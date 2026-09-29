# location_current_log_drop_600

- kind: location
- status: refuted
- confidence: 0.10
- created_step: 600
- updated_step: 796
- depends_on: location_live_spawn_spruce_0, location_fresh_spawn_spruce_0

## Statement

The log entity from the step-480 break was not recovered by repeated directed sweeps through step 796 and is no longer a useful live target; harvest fresh visible trunk blocks instead.

## Evidence

- A 4x crop of episodes/ep_0000/frames/step_0600.png clearly resolves the rotating dropped-log model.
- Current inventory/resource accounting and the furnace frame contain no log drop evidence; thousands of ticks have elapsed.
- events/events.jsonl has only four spruce-leaf breaks through step 600 and frame 600 does not prove a dropped item.
- Frame 480 visibly shows the rotating dropped-log model; step 528 reports no pickup after a 48-tick sweep, and events remain pickup-free through step 600.
- No spruce_log pickup or inventory delta occurred through step 796 despite sweeps at steps 528, 691, and 796; the current frame instead exposes intact spruce directly overhead.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
