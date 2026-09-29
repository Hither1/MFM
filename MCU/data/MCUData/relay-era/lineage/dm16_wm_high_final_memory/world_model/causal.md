# Causal model - re-priced at live step 11600

- Final chain is complete: iron pickaxe -> y12 tunnel -> diamond ore break at 11261 -> free inventory slot -> diamond pickup at 11444. The environment verifies 10/10.
- From the 11400 diagnosis checkpoint, recovery cost 44 ticks versus the prior 80-150 tick estimate. From ore break to pickup it cost 183 ticks, mostly because the first sweep moved away and the later target-local sweep stopped early on cobblestone.
- The final effective alternative to another broad `collect_drops(48)` was a coordinate-directed nudge: after the incidental pickup at 11440, only 4 more ticks and 0.19 blocks of movement were needed for diamond pickup at 11444. At that point this was plainly cheaper than restarting a full sweep.
- There is now no path that can improve milestone count: 10 is the maximum. The cheapest path to the same milestone count is zero further interaction; remain stationary and preserve the verified inventory/state.
- No crafting, mining, lighting, surface return, exploration, claim, or recovery dependency remains.
