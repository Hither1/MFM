# location_current_log_drop_600

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 600
- updated_step: 600
- depends_on: location_live_spawn_spruce_0

## Statement

No current log drop is verified at live step 600; the frame shows leaves and a trunk, while the event stream has no log break or pickup.

## Evidence

- A 4x crop of episodes/ep_0000/frames/step_0600.png clearly resolves the rotating dropped-log model.
- Current inventory/resource accounting and the furnace frame contain no log drop evidence; thousands of ticks have elapsed.
- events/events.jsonl has only four spruce-leaf breaks through step 600 and frame 600 does not prove a dropped item.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
