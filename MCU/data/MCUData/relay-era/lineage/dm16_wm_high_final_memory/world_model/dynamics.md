# Dynamics model - diagnosed through live step 11600

- All 10 milestones are verified. `mine_block diamond_ore` fired at 11261; `[INV] diamond +1`, `pickup diamond +1`, and `MILESTONE diamond verified` fired together at 11444.
- The apparently failing procedure was `collect_drops(ticks=48)`. It is target-insensitive and stops on the first inventory increase: at 11440 it acquired incidental cobblestone, emitted `inventory rose by 1 ... stopping`, and ended before acquiring the nearby diamond. This was normal procedure behavior, not evidence that the diamond was absent.
- A follow-on `go_to(-3060.5,-5558.48)` moved only from `(-3062.34,12,-5558.48)` to `(-3062.15,12,-5558.48)` before the diamond pickup fired at 11444. Thus the item was nearby and capacity was valid; the prior sweep simply terminated on the wrong drop.
- Best explanation: mixed drops make `collect_drops` an unreliable target-completion test because any pickup satisfies its stop condition. Next-best explanation (wrong coordinate or despawn) is refuted by the separating observation: the first 0.19-block movement after the cobblestone stop immediately produced the diamond pickup event.
- Prescriptive rule: after `collect_drops` stops on a non-target `[INV]` delta, re-check the target event and continue with a short coordinate-directed nudge/sweep. Do not infer target recovery from the procedure's generic success note.
- Repeated post-completion no-ops changed no statistic because no subgoal remains. This is safe state preservation, not a procedure failure requiring another approach.
