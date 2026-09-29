# location_visible_log_drop_0420

- kind: location
- status: stale
- confidence: 0.98
- created_step: 420
- updated_step: 571
- depends_on: resource_reset_three_logs

## Statement

The step-420 loose log drop was recovered in the combined spruce_log +2 pickup at step 443 and is no longer present as a recovery target.

## Evidence

- The attached step-420 frame shows the floating log item at lower-left while the stump is directly ahead; inventory and event stream confirm it remains uncollected.
- After a westward strafe, collect_drops raised inventory by two and events/events.jsonl recorded pickup spruce_log +2 at step 443.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
