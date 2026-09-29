# Dynamics model — step 11400

- Iron-pick diamond/stone breaks usually need ~15–45 attack ticks when centered. At 11316 the ore servo lost the cluster; 60 ticks at pitch 4/yaw -4 broke nothing. After looking up, stone broke at 11394 and the step-11400 frame shows attack continuing on overhead clearance.
- A full remote discard costs ~29 ticks of GUI work plus travel. Andesite x8 was dropped 2.5 blocks south at 11295 and was not recollected; at least one pickup slot is durable now.
- Empty sweeps of 120 ticks (10962), 45 (11093), and 64 (11269) produced no pickup despite free capacity. More sweeping without first breaking the visible west-wall diamond and entering its exact cell has near-zero return.
- At yaw about -4°, `left+jump` moved x +0.40; use `right` to move toward smaller-x west wall. A 12–20 tick strafe should cover the sub-block gap once collision is removed.
- Open horizontal mining costs ~40–50 ticks per advanced block. Break-without-advance after two cycles means wrong geometry, not pick failure.
- Closed-loop turns can finish in a few ticks; `aim_at_ore` gives up after six undetected frames, so first place the cyan face near screen center.
- Cobble-pillar ascent y9→68 costs ~850–900 ticks. With 600 ticks left, returning to the surface table is infeasible. Plans remain capped at 400 ticks each.
