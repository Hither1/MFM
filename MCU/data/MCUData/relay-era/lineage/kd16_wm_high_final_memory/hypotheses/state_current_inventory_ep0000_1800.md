# state_current_inventory_ep0000_1800

- kind: state
- status: stale
- confidence: 1.00
- created_step: 1800
- updated_step: 2400
- depends_on: goal_wooden_pickaxe

## Statement

The step-1800 inventory snapshot is historical and superseded by verified mining, placement, and pickup events through step 2400.

## Evidence

- The live frame shows dirt x4, sticks x2, and the selected wooden pick. Events verify exactly four pick uses after its craft and contain no stone/cobblestone event through step 1800.
- At step 2400 the frame and event accounting show dirt x1, cobblestone x6, sticks x2, wooden pickaxe with 41 uses left, and granite x4.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
