# state_cache_A_partial_recovery_11452

- kind: state
- status: stale
- confidence: 1.00
- created_step: 11452
- updated_step: 11453
- depends_on: goal_iron_pickaxe

## Statement

The step-11452 cache pickup occurred during a lethal shaft landing: the death screen was already open, and closing it at step 11453 respawned the player empty while re-dropping all briefly collected stacks at y12.

## Evidence

- Authoritative step-11452 state is (-2998.32,12,-5568.30) at full health; pickup events record dirt, stone_pickaxe, diorite, cobblestone, iron_ore, sand, and granite, while the frame visibly shows remaining tool/torch drops and GUI open=True.
- Action 723 records close_inventory followed by YOU DIED at (-2998,12,-5568), respawn at (-3014,70,-5572), and removal of every briefly recovered inventory stack; the attached frame explicitly says 'fell from a high place'.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
