# mechanism_hostile_damage_cycle_10566

- kind: mechanism
- status: stale
- confidence: 1.00
- created_step: 10566
- updated_step: 9600
- depends_on: goal_diamond

## Statement

The repeated y12 damage-cycle claim belongs to an older trajectory and is stale; this current reset has only one unresolved four-damage interruption at y28 through step 9600.

## Evidence

- Damage interruptions occurred at steps 10486, 10526, and 10566, each exactly 40 ticks apart, while the player remained at (-2997.3,12,-5568.3). The north-facing frame shows no attacker, making the rear/south side the likely source.
- Steps 10526 and 10566 interrupted after four damage each. Saved frames 10545_ore and 10566 show only stone, iron ore, torch, and tunnel geometry; the south-facing attack then mined stone at step 10584 rather than producing a kill or hit event.
- Current-reset logs report one damage interruption at step 9199, whereas the node's 10486-10566 evidence lies outside the current 9600-step segment.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
