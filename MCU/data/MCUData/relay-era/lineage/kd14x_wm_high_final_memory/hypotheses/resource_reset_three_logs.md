# resource_reset_three_logs

- kind: resource
- status: active
- confidence: 1.00
- created_step: 101
- updated_step: 1200
- depends_on: goal_mine_log, location_live_spawn_spruce_0000

## Statement

At step 1200 one spruce log remains banked after the table craft; two additional logs are needed to cover the wooden pick's five-plank minimum.

## Evidence

- events/events.jsonl has two pickup spruce_log events and a later mine_block spruce_log at 2104; the 72-tick sweep ending 2176 explicitly found nothing.
- events/events.jsonl records the third pickup at step 2444; [STATE] at step 2540 reports spruce_logx3.
- Step-111 inventory is empty and events contain no spruce_log pickup yet, while the frame shows additional trunk blocks at the worksite.
- events/events.jsonl has mine_block spruce_log at steps 111 and 384 and no pickup event; the step-420 frame visibly shows a dropped log item just left of the stump and more trunk overhead.
- events/events.jsonl records pickup spruce_log +2 at step 443, and the authoritative step-571 inventory is spruce_log x2.
- events/events.jsonl records pickup spruce_log +2 at step 443; step 580 records spruce_log -2 from inventory and [CURSOR] spruce_logx2, proving the stack is held rather than lost.
- pickup spruce_log +2 fired at step 443; GUI inventory/grid transitions through step 597 account for both without any craft event yet.
- Two logs were picked up at 443; one was crafted into four planks at 602 and consumed by the table at 638; the other is visible in hotbar slot 0 at 1200.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
