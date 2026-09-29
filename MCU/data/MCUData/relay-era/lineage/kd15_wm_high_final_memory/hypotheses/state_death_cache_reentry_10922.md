# state_death_cache_reentry_10922

- kind: state
- status: refuted
- confidence: 1.00
- created_step: 10922
- updated_step: 10923
- depends_on: state_death_drop_10606, location_diamond_depth_shaft_10138

## Statement

The second empty-handed shaft entry ended in lethal fall damage at y16 before any cache item was recovered; direct unsupported re-entry is refuted.

## Evidence

- Steps 10913-10922 moved from y26.16 to y16.00 near the shaft center; the last collect_drops stopped immediately because GUI open=True and CURSOR reports nothing off-inventory.
- At step 10922 the death screen opened at (-2998,16,-5569); closing it produced the harness death note and respawn at step 10923 with an empty inventory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
