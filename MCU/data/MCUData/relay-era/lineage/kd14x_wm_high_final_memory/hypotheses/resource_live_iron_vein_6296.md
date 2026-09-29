# resource_live_iron_vein_6296

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 6296
- updated_step: 4800
- depends_on: goal_mine_iron_ore, resource_iron_ore_drop_6296

## Statement

The claim that three ore have already been supplied is stale for this reset; only the vein coordinates remain permanent in the ore registry.

## Evidence

- Step-6296 frame visibly shows multiple tan-speckled iron blocks ahead; events verify one block broke but contain no pickup iron_ore event yet.
- mine_block iron_ore events occur at 6296, 6335, and 6364.
- The attached step-6952 frame clearly shows tan-speckled iron ore centered immediately ahead and another ore-textured face above/behind it.
- The step-7042 mining action added the third held ore, and step-7103 inventory confirms iron_ore x3.
- Current events through 4800 contain no mine_block or pickup iron_ore; the milestone is unmet.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
