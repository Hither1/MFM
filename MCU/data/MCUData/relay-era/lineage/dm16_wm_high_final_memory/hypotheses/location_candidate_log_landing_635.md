# location_candidate_log_landing_635

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 635
- updated_step: 600
- depends_on: location_live_spawn_spruce_0

## Statement

The claimed live log-drop cache near (-3004.4,68.8,-5565.3) belongs to another trajectory and does not exist in this reset.

## Evidence

- Live events verify three spruce-log breaks and zero pickups through step 635. The prior trajectory recorded two visible dropped-log models near (-3006,69,-5568) and then pickup spruce_log +3 after 2.9 blocks of directed travel; the current player is only about 1.7 horizontal blocks from that landing coordinate.
- At step 668, 24 ticks of travel from (-3006.3,71,-5567.9) toward the southeast ended near (-3004.2,69.2,-5565.3) and triggered pickup spruce_log +3.
- Travel via (-3006.3,-5567.9) to (-3004.2,-5565.3) ended at (-3004.37,68.75,-5565.30), where collect_drops immediately produced pickup spruce_log +3 at live step 524.
- The final live map reaches (-3004.24,68,-5565.36) at step 600, but current events contain no spruce-log break or pickup from which such a cache could exist.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
