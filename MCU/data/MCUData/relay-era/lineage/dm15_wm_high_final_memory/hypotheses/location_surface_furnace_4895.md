# location_surface_furnace_4895

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 4895
- updated_step: 5400
- depends_on: goal_furnace, mechanism_place_block_helper_gui_guard

## Statement

The claimed furnace at (-3007.7,70,-5566.2) is future-contaminated and does not exist in current evidence.

## Evidence

- The successful step-4895 placement targeted the top face centered near (-3006.5,68.95,-5569.5), and [INV] furnace -1 verified that the furnace left inventory; the attached frame shows it ahead.
- The step-4895 frame visibly centers the furnace top while STATE is pos=(-3007.70,70.00,-5566.24), pitch=34, yaw=59. Re-aiming at the inferred coordinate produced yaw=-160 and no furnace visible or GUI.
- At step 4973 look_abs restored pitch 34/yaw 59, and at step 4978 use_until_gui changed GUI open from false to true while the player remained stationary.
- Events verify mine_block furnace at 5335 and pickup furnace at 5345; the step-5400 hotbar contains it.
- Current events have no furnace placement at 4895 and no furnace mine/pickup at 5335/5345; the only verified placement is at 4688-4691 near (-2988.5,65,-5547.5).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
