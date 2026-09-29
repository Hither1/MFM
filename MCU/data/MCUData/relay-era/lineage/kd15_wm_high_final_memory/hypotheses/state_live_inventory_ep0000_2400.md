# state_live_inventory_ep0000_2400

- kind: state
- status: stale
- confidence: 1.00
- created_step: 2400
- updated_step: 3000
- depends_on: goal_mine_cobblestone, resource_cobblestone_portfolio_2303, state_inventory_3000

## Statement

The step-2575 inventory snapshot is historical and superseded by the return pillar and exact step-3000 snapshot.

## Evidence

- The step-2400 hotbar shows these five stacks; events total 18 wooden-pick uses, six net cobblestone, four net granite, and one net dirt.
- The authoritative step-2430 state reports these six stacks and the selected wooden pickaxe; the step-2430 events verify the newest andesite break and twentieth wooden-pick use.
- The authoritative step-2575 state provides the inventory and pose; events record the newest stone break and wooden-pick use at 2575 but no pickup after that break.
- Events after 2575 add two cobblestone pickups and consume all decorative blocks plus two cobblestone during ascent.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
