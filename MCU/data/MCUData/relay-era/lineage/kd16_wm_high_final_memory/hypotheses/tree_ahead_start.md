# tree_ahead_start

- kind: location
- status: stale
- confidence: 0.95
- created_step: 133
- updated_step: 1200

## Statement

The original spawn-side trunk location is historical and should no longer guide navigation.

## Evidence

- At step 10 aim_at_tree centered on 2742 px of bark; chop_tree then spent 75 ticks without a break and diagnosed the trunk as out of reach. The step 133 frame still shows the trunk centered.
- The agent moved about 6.6 blocks from spawn and now has a different immediately adjacent trunk face; exact old trunk coordinates were never established.
- Current step-1200 position is about 12 blocks from spawn and local trunks remain visible; returning to an unlocated old trunk has no value.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
