# resource_reset_three_logs

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 101
- updated_step: 978
- depends_on: goal_mine_log, location_live_spawn_spruce_0000

## Statement

Exactly three spruce logs are held at live step 978, completing the safe three-log reserve before crafting begins.

## Evidence

- events/events.jsonl records pickup spruce_log +2 at step 443; step 580 records spruce_log -2 from inventory and [CURSOR] spruce_logx2, proving the stack is held rather than lost.
- pickup spruce_log +2 fired at step 443; GUI inventory/grid transitions through step 597 account for both without any craft event yet.
- Two logs were picked up at 443; one was crafted into four planks at 602 and consumed by the table at 638; the other is visible in hotbar slot 0 at 1200.
- Authoritative step-0 inventory and hotbar are empty.
- At step 365 mine_block spruce_log +1 fired, while [STATE] still reports empty inventory; the attached frame shows dense remaining spruce logs around the now-adjacent player.
- mine_block spruce_log fired at 365 and pickup spruce_log +1 at 375; no later mine, pickup, or craft event exists, while the current frame shows several nearby natural logs.
- Current events verify spruce-log pickups at steps 375 and 757, and the authoritative step-757 inventory contains spruce_log x2.
- Current-reset events record spruce-log pickups at steps 375, 757, and 978 with no intervening craft or loss; authoritative step-978 inventory is spruce_log x3 in hotbar slot 0.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
