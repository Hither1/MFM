# location_visible_log_drops_970

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 970
- updated_step: 600
- depends_on: resource_live_early_logs, location_live_lower_spruce_689

## Statement

Retired as future-trajectory contamination: the claimed step-984 pickup has not occurred; current pickup count remains zero at step 600.

## Evidence

- A 4x crop of step_0970.png shows two unmistakable miniature spruce-log item models at lower right; current state is (-3006,69,-5568), yaw -40/pitch 3.
- Directed travel moved 2.90 blocks and produced pickup spruce_log +3 at step 984; the following 100-tick sweep found nothing else.
- events/events.jsonl ends at step 591 and contains no pickup event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
