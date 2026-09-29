# location_live_y56_north_branch_5492

- kind: location
- status: refuted
- confidence: 0.90
- created_step: 5492
- updated_step: 5859
- depends_on: goal_mine_iron_ore, location_y56_west_strip_4800, resource_current_lighting_kit

## Statement

The north branch entrance at (-2991.7,56,-5566.7) is currently non-walkable: repeated ore-watched and manual clearing broke about 15 stone blocks without any avatar advance, and the live frame indicates an irregular floor gap/threshold. Retire this entrance unless it is deliberately bridged later.

## Evidence

- STATE at step 5492 gives (-2991.7,56.0,-5566.7), yaw 270; events since 5400 verify five more stone blocks and no iron, while the torch placed at 5356 is only about two blocks behind the current face.
- The ore-watched strip from step 5495 to 5593 recorded four mine_block stone events and stopped after two cycles with 0.0 blocks advanced; the live frame shows a stone threshold/wall and no iron speckles.
- Events from steps 5493-5815 verify about 15 stone breaks after turning north, while every STATE remains fixed at (-2991.72,56.00,-5566.70); strip diagnostics at steps 5593 and 5859 both report 0.0 blocks advanced.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
