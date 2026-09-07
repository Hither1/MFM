# Milestone Costs and Bottleneck Analysis: ender_dragon_half Runs

## 1. Milestone Verification Table

| Run  | diamond | diamond_sword | mine_obsidian | flint_and_steel | max_step | deaths | death_steps |
|------|---------|---------------|---------------|-----------------|----------|--------|-------------|
| og6  | 341     | 1021          | -             | -               | 11996    | 1      | 7295        |
| og7  | 121     | 288           | -             | -               | 11995    | 0      | -           |
| og8  | 241     | 449           | 12884         | 11470           | 34431    | 3      | 2603,14349,18261 |
| og9  | 284     | 573           | 8675          | 7888            | 30220    | 3      | 17976,19286,26939 |
| og10 | 100     | 238           | 35170         | 28076           | 47812    | 3      | 8870,35834,45621 |
| og11 | 45      | 182           | -             | 22274           | 29179    | 2      | 10326,27469 |
| og12 | 100     | 284           | 6134          | 21647           | 28601    | 0      | -           |
| og13 | 100     | 534           | 13358         | 8331            | 20020    | 1      | 18818       |
| og14 | 45      | 248           | -             | -               | 5586     | 0      | -           |

**Notes:**
- First 10 milestones credited at start.
- og14 is thin self-harness (atoms+own), runs still in progress (og10-og14).
- og6-og9 have shorter budgets or memory carry; og8-og9 show high death frequency.
- og10 shows extreme obsidian-search cost (35170 vs 238 at diamond_sword).

---

## 2. Phase Cost Analysis

### Start → Diamond Sword (Kit Phase)
**Median: 288 steps | Max: 1021 (og6) | Min: 182 (og11)**

All runs achieve this phase rapidly (182–1021 steps). Fast crafting dominates; kit phase is well-handled except for og6's outlier.

**Breakdown (sorted by cost):**
- og11: 182
- og10: 238
- og14: 248
- og12: 284
- og7: 288
- og8: 449
- og9: 573
- og13: 534
- og6: 1021

**Issue in og6 (1021 steps):** Excessive time on tool placement, inventory swaps, and collection operations. Log notes at step 1021 show repeated `place_at`, `craft`, and `collect_drops` operations with [NOTE] governor refusals.

---

### Diamond Sword → Mine Obsidian (Search Phase)
**Median: 12435 steps | Max: 34932 (og10) | Min: 5850 (og12)**

This is the **costliest single phase** across all runs (5 runs achieved it).

**Breakdown:**
- og12: 5850 (obsidian after sword within ~20k budget)
- og9: 8102
- og8: 12435
- og13: 12824
- og10: 34932 (extreme cost)

**Root Causes (extracted from [PLAN] and [NOTE] samples):**

1. **Governor Refusals (primary bottleneck):** 43–126 refusals per run
   - og10: 126 governor refusals over 34932 steps → ~1 refusal per 277 steps
   - og8: 56 governor refusals over 12435 steps → ~1 refusal per 222 steps
   - og13: (partial) showed repeated plan-retry cycles

2. **Harness Stalls (go_to blocked, LAVA_AHEAD):** 40–43 go_to_blocked, 3–15 LAVA_AHEAD per run
   - og10: 43 go_to_blocked, 3 LAVA_AHEAD
   - og12: 19 go_to_blocked, 15 LAVA_AHEAD → lava detection dominating
   - og8: 3 go_to_blocked, 3 LAVA_AHEAD

3. **Place Operations (place_at stalls):** 52–71 place operations per run
   - og10: 71 place operations (e.g., torches, crafting tables)
   - og12: 62 place operations
   - og8: 52 place operations
   - [NOTE] examples: "place_at(crafting_table) at (-3107, 11, -5523)", indicating repeated tool placement for mid-phase ore furnacing

4. **Search Behavior:** [PLAN] samples show:
   - og10 at step 23659: "Place torch on north wall… Continue west with iron pickaxe and ore detection"
   - og12 at step 15275: "Fill mined hole and approach gaps with cobblestone… working back toward our feet"
   - Repeated tunnel-following and gap-repair suggests inefficient corridor navigation or dead-end backtracking

---

## 3. Secondary Phases

### Mine Obsidian → Portal (Flint/Netherrack)
**Note:** In 4 of 5 runs (og8, og9, og10, og13), flint_and_steel is achieved *before* mine_obsidian, creating negative cost phases. Only og12 follows expected sequence.

**og12 only (21363 steps):**
- Dominated by: 43 governor refusals, 62 place operations, 15 LAVA_AHEAD
- [PLAN] at step 18790: "Clear leaves at eye height while edging south with sneak held"
- [PLAN] at step 21604: "Craft flint and steel… resume tunneling east with diamond pickaxe"
- Classification: Mixed harness stalls + lava safety navigation

### Death Rebuild Phases
- **og6 (death at 7295):** 7295 → iron_ingot (1442) = ~145 steps recovery (data shows max_step 11996 total, so death cost ~4700 steps to end)
- **og8 (3 deaths):** 2603 → mine_diamond_ore (8267) = 5664 steps; subsequent deaths show increasing costs
- **og9 (3 deaths):** 17976 → 19286 (rebirth point marker unclear); expensive recovery cycles
- **og10 (3 deaths):** 8870 → mine_diamond_ore (24994) = 16124 steps; deaths at 35834, 45621 (near end)
- **og13 (1 death):** 18818 (near end, limited recovery)

---

## 4. Three Costliest Phases: Detailed Analysis

### Phase A: og10 - Diamond Sword → Mine Obsidian (34932 steps)
**Classification: Search problem + Harness stall**

[PLAN] samples reveal:
- Step 238: Initial crafting setup
- Step 9570: Rebuilding supplies after recovery cycle
- Step 16411: "Mine east into confirmed old corridor at X=-3008.5. Follow that corridor south"
- Step 23659: "Place torch on north wall… Continue west with ore detection"
- Step 28233: "Fuel furnace ore… mine wall above furnace"
- Step 34978: "Aim at purple patch… hold diamond pickaxe for 230 ticks"

[NOTE] breakdown: 126 governor, 71 place, 43 go_to_blocked, 41 collect, 23 watch, 3 LAVA_AHEAD

**Interpretation:** Model executed a massive exploration loop (16k+ steps) while repeatedly hitting governor refusals. Crafting-table placement recurred frequently (71 times), suggesting multiple furnace cycles needed for ore processing. Corridor-following and ore detection indicate search behavior without clear map memory. The extreme cost (34932 steps vs og12's 5850 for the same phase) points to inefficient exploration strategy.

---

### Phase B: og12 - Obsidian → Portal (21363 steps, actually start to flint_and_steel)
**Classification: Knowledge gap + Lava hazard**

[PLAN] samples:
- Step 284: Initial crafting
- Step 7193: "Reached tunnel at Y=12 without damage" (confidence checkpoint)
- Step 15275: "Fill mined hole… repair floor"
- Step 18790: "Clear leaves at eye height while edging south with sneak"
- Step 21604: "Craft flint and steel… resume tunneling east"

[NOTE] breakdown: 62 place, 43 governor, 19 go_to_blocked, 18 watch, 15 LAVA_AHEAD, 14 harvest

**Interpretation:** Model struggled with lava-adjacent mining (15 LAVA_AHEAD notes vs 3–5 in other runs). Repeated leaf-clearing (18 watch + 3 harvest) and block-filling (19 go_to_blocked) suggest cautious, low-speed navigation. High place count (62) with governor refusals (43) indicates frequent recalculation or procedural replay, possibly due to terrain surprises.

---

### Phase C: og8 - Diamond Sword → Mine Obsidian (12435 steps)
**Classification: Harness stall + Death recovery pattern**

[PLAN] samples:
- Step 449: Initial tool crafting and descent
- Step 4475: "Axe succeeded but no logs collected" (inventory issue)
- Step 7428: "Descend to y10 beside recovery site"
- Step 8832: "Clear gravel sections, collect drops"
- Step 10389: "Mine upper east wall"
- Step 12678: "Mine upper east wall, look toward pool"

[NOTE] breakdown: 56 governor, 52 place, 23 collect, 6 watch, 3 go_to_blocked, 3 LAVA_AHEAD

**Interpretation:** After death at step 2603, recovery consumed large tick budget. Governor refusals (56) and repeated placement (52) dominate, with collection stalls (23) indicating inventory mismanagement or drops spread across multiple locations. [PLAN] at step 4475 ("no logs collected") suggests item-drop tracking failure. Model recovered and reached obsidian at step 12884, but inefficient inventory recovery extended the phase.

---

## 5. Harness Bottleneck Patterns

**Top refusal sources (governor):**
- Repeated `cursor_to_slot`, `gui_click`, `place_at` without progress
- Inventory loops attempting to swap items with full cursor or locked grids
- Procedural proposal replay after observing cached state (e.g., "finished 2 times in a row changing nothing")

**LAVA_AHEAD dominance (og12 outlier):**
- 15 LAVA warnings in 21k steps → model over-cautions or reacts slowly to hazard
- og10: only 3 LAVA warnings despite 35k steps → possible under-caution or map avoidance

**Placement inefficiency:**
- 52–71 place operations across 12k–35k-step phases
- Evidence: crafting tables placed mid-tunnel for fuel/tool resupply but dropped repeatedly
- Hypothesis: stateless planning; no persistent map of tool/supply drop locations

---

## 6. Candidate Systematic Improvements

### (A) Governor-Aware Procedural Caching (Est. savings: 2000–5000 steps per phase)
**Evidence:** og10 step 238–35170 shows 126 refusals; og8 shows 56/12435. Pattern: identical `cursor_to_slot` or `place_at` attempts fail 2–3 times before refusal.

**Improvement:** Add a local "refused_actions" buffer (last 5 actions). If an action is proposed twice after a refusal, substitute a contextual alternative (e.g., swap `place_at(table_A)` → `place_at(table_B)` at different coordinates, or `cursor_to_slot(n)` → `close_inventory()` + retry).

**Estimated savings:** 20–30% of governor stalls = ~600 steps/1000 in refusal-heavy phases like og10 (34932 steps * 0.15 = ~5240 steps).

---

### (B) Persistent Crafting-Table Map (Est. savings: 1500–3000 steps per phase)
**Evidence:** og10 and og12 show 62–71 place operations; [PLAN] at steps 9570, 25458 reference furnace ore cycles requiring table placement. No evidence of remembering prior table locations.

**Improvement:** Maintain a set of {(x, y, z), table_state} for placed tables. Before placing a new table, check if an existing table in inventory can reach a known safe location (e.g., within 20 blocks). Reduce duplicate placements.

**Estimated savings:** 10–15% of place ops; in og10 (71 places), ~7–11 place operations = ~350–550 ticks per operation = ~2500–6000 steps saved if mid-phase refueling is consolidated.

---

### (C) Lava-Adaptive Navigation (Est. savings: 500–2000 steps, especially og12)
**Evidence:** og12 has 15 LAVA_AHEAD warnings over 21k steps; model responds with cautious leaf-clearing (18 watch + 3 harvest) but no evidence of pre-emptive mining or water-bucket strategy.

**Improvement:** When LAVA_AHEAD is detected, immediately equip water bucket (if held), pre-mine a 1-block buffer above/beside lava, or call a verified "safe descent" procedure (rotate blocks with water + mining). Reduce the watch/harvest loop.

**Estimated savings:** 10–20% of lava-stall steps in og12 (~15 stalls * ~50 steps each check/stall = ~750 steps base; improve to ~5 stalls * 50 = 250 steps = ~500 steps saved). Scales higher if multiple lava patches encountered.

---

### (D) Stateful Inventory Checkpoint (Est. savings: 500–1500 steps)
**Evidence:** og8 at step 4475 ([PLAN] "Axe succeeded but no logs collected"); og14 shows 10+ steps of cursor_to_slot loops with no effect (steps 252–287 show "governor: finished 2 times in a row"). Inventory state divergence between expectation and reality.

**Improvement:** After any craft, collect, or equip action, log an (expected_inventory_delta, observed_delta) tuple. If divergence >3 items for 2 consecutive actions, trigger an explicit `open_inventory()` + `check_screen()` read cycle before proceeding. This prevents stale inventory assumptions.

**Estimated savings:** Avoid ~3–5 no-op cursor loops per phase = ~20 steps per loop = 60–100 steps per phase; amortizes to ~500–1500 across multiple phases in a run.

---

### (E) Cached Tunnel Corridors (Est. savings: 2000–8000 steps for exploration phases)
**Evidence:** og10 steps 16411, 23659 show repeated "east corridor at X=-3008.5… follow south"; og8 step 7428 "descend to y10 beside recovery site." No evidence of path memory or frontier tracking.

**Improvement:** Maintain a visited-block frontier map updated each action step (use only recent visited positions, e.g., last 500 steps in a circular buffer to keep memory O(1)). When planning a mine sequence, prefer unexplored directions (not in frontier) over revisiting known dead ends. This is a lightweight alternative to full SLAM.

**Estimated savings:** Reduce backtracking by ~20–30% in search phases. og10's search phase (34932 steps) with 30% overhead = ~10k wasted steps; reduce by 20–30% = 2000–3000 steps. og12 (~21k steps) similarly: 20% * 21k ≈ 4200 steps, conservative improvement ~1500–2000.

---

## Summary

**Phase Cost Ranking:**
1. og10: diamond_sword → obsidian (34932 steps) — outlier, gov+search
2. og12: start → flint+steel (21363 steps, obsidian→portal) — lava + gov stalls
3. og8: diamond_sword → obsidian (12435 steps) — gov + inventory

**Dominant Harness Issues:**
- Governor refusals (43–126 per phase): cursor/placement loops after failed state change
- Lava awareness (og12: 15 vs og10: 3) — inconsistent hazard response
- Placement inefficiency (52–71 ops) — no persistent tool/supply map
- Inventory divergence (og14, og8) — stale assumptions lead to no-op loops

**Top 3 Improvements:**
1. Governor-aware action substitution (~2000–5000 steps/run)
2. Persistent crafting table/supply location map (~1500–3000 steps/run)
3. Lava-adaptive descent + stateful inventory (~500–2000 steps/run)

Combined potential: ~4000–10000 steps saved per run, or ~15–25% median phase cost reduction.

