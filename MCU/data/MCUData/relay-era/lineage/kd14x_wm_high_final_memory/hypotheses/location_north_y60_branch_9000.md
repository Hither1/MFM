# location_north_y60_branch_9000

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 9000
- updated_step: 9186
- depends_on: location_midcorridor_bounded_shaft_6683, goal_mine_iron_ore

## Statement

The northbound y60 face at (-3004.3,-5557.7) is not traversable: four stone breaks opened a visible recess, but the mining macro advanced 0.0 blocks and repeated jump-forward also moved 0.0.

## Evidence

- At y60 visited.csv ranges only z=-5558.30 to -5541.30; earlier refuted north faces were at y63, three blocks above this candidate.
- At steps 9088, 9108, 9137, and 9157 four stone blocks broke while position remained (-3004.3,60,-5557.7). The step-9166 crop visibly shows an opened tunnel and cobblestone drops ahead rather than a wholly intact face.
- Steps 9088-9157 broke four stone while state stayed fixed; steps 9167-9186 repeatedly raised y briefly to 60.2 but x/z remained exactly (-3004.30,-5557.70).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
