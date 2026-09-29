# state_death_drop_10606

- kind: state
- status: stale
- confidence: 1.00
- created_step: 10606
- updated_step: 10800
- depends_on: goal_iron_pickaxe, goal_diamond

## Statement

The skeleton-death/cache claim belongs to another trajectory and is stale for the current run; the player remained alive at y9 through step 10800.

## Evidence

- Step 10606 authoritative state and death note report the exact death/respawn coordinates and inventory losses; the death screen says the skeleton delivered the kill.
- Current-run action headers and map segment show y9 continuously across step 10606, with full-health frames and no death/respawn transition; the y12 death coordinates are from a duplicate trajectory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
