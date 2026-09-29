# resource_dropped_cobblestone_10194

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 10400
- updated_step: 10400
- depends_on: resource_current_cobblestone

## Statement

Cobblestone x35 was removed from inventory at the live surface pose around (-3000.30,65,-5569.36) by the intentional force-close at step 10194, but its item entity was not recovered by the later directed sweep and should not be treated as available.

## Evidence

- The cursor held cobblestone x35 and INV fell by 35 before close; the close note says it became a floor entity, but no pickup event or INV restoration follows through step 10400.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
