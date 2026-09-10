# Trajectory Analysis: of2, of3, of2r, of3r Minecraft Runs

## 1. Large Step Budget Gaps: Patterns and Root Causes

### of3: 17k steps between iron_pickaxe (step 6,243) and flint_and_steel (step 23,032)
**Pattern:** Horizontal single-cell tunneling at y=11 searching for diamonds with zero yield.
- Lines 8920-14000 of of3 logs show repeated "Mine two blocks west at Y=11. Inspect the exposed faces for diamonds" plans.
- Each plan cycle typically consumed 20-30 steps with 2-3 blocks mined and inspected per cycle.
- No diamond found; terrain contained only stone, andesite, and diorite.
- **Root cause:** Blind horizontal search in an unlucky region; model lacked a systematic depth/region strategy.

### of2: 10.4k steps between iron_pickaxe (step 12,884) and lava death (step 23,285)
**Pattern:** Staircase descent mining from y35→y10 with single-block cycle repetition.
- Lines 8550-12400 show "Place torch, descend one step north, inspect" repeated ~150+ times.
- Each cycle: 15-25 steps per 1-block descent with torch placement.
- Reached lava face at y10 (-3006, 10, -5706) but lost focus on survival checks.
- **Root cause:** Procedural staircase routine continued mechanically into hazard zone without rerouting.

### of2r: ~16.7k steps from iron_pickaxe (step 10,528) to diamond (step 27,280)
**Pattern:** Vertical descent searching for diamond layer y≤-64 using stair-cutting.
- Lines 9350-10400 show "Cut northward stair toward diamond depth" repeated with iron sword as a battering tool.
- Descents were systematic but slow (1 block per cycle in places).
- **Root cause:** Deeper search was necessary (of2r had no diamonds in early mining); less horizontally "lucky" than of3r which eventually tunneled into gravel.

### of3r: ~4.5k steps tunneling at y=11 for lava (step 14k+)
**Pattern:** Westward tunnel repetition: "Mine two westward tunnel cells toward remembered gravel" (lines 13240-13487).
- Same target x≈-3109.7 repeated in EXPECT across 20+ actions.
- Model was reusing of3's life_1 digest location (gravel x=-3169..-3175) but stalled at movement=0 (line 13331).
- **Root cause:** Fixed target from memory caused plan drift; model did not detect stall or re-search.

## 2. Harness Mechanics Cost: Frequencies and Examples

### 2a. Crafting-Slot Confusion (2-3 occurrences per run; 50-150 ticks each)
**of2 line 273:** "craft(stick): 5 cells already hold leftovers... the rest of the plan (3 entries) was dropped."
- Required stow_items() call before retry; full plan drop triggered.

**of3 line 1139:** Similar crafting grid overflow; 5 occupied cells.

**Cost:** 50-200 ticks + plan replan overhead.

### 2b. GUI/Screen Rendering Interruptions (~8-15 per run; 10-50 ticks each)
**of3 line 1262:** "[PLAN] furnace crafting was blocked. The GUI reports open while the image still shows the world, suggesting a stale frame."
- Frame lag between state report and visual update caused mismatch.

**of2 line 12457:** Death inventory shows bucket still carried but never used; GUI state did not match player readiness.

**Cost:** 10-50 ticks stall per occurrence; delayed action-taking.

### 2c. go_to Detours and Stalls (11-36 references across runs)
**of3 line 925:** "[PLAN] Movement stalled and cobblestone remains at two. The view shows a cleared passage beyond a near obstruction."
- go_to navigation hit terrain irregularity and stopped.

**of2 line 734 [fell reflex]:** "dropping 2.1 blocks in four ticks... look at four yaws before moving; go back up the way you came... plan dropped (1 action)."
- Reflex interrupted go_to; forced pillar_up recovery.

**of3 line 2525:** "Movement stalled beside the leaf wall; the view changed very little."

**Cost:** 50-200 ticks per stall; frequent in early/mid runs.

### 2d. Occupied-Cell Grid Conflicts (~5-10 per run; 30-100 ticks)
**of3 line 7552:** "[PLAN] sticks were blocked by an occupied-cell report. The visible grid looks empty, suggesting a delayed update."
- Cached inventory state vs. actual slots conflict.

**of3 line 2705:** "Both trench advances stalled; nothing visibly changed during the last advance."

**Cost:** 30-100 ticks re-check + re-attempt.

### 2e. Plan Drops by Hit/Fell Reflexes (3-7 major drops per run)
**of2r line 22345-22355:** "[REFLEX hit] took 4 damage with no lava in view: a mob is at you... the runner dropped the rest of your plan (8 actions)."
- Burn damage (from obsidian cap) misread as mob; hit reflex fired.
- Subsequent action: "Resume swimming forward" = model's own improvisation.

**of2 line 734:** Fell reflex stopped digging plan; forced climb-back.

**Cost:** 100-500 ticks per drop (replan, re-approach, re-execute).

## 3. Memory Reuse: Use of previous/ and Life-1 Constraints

### Evidence of Memory Reuse in of2r and of3r
Both reuse lives show `previous/life_1/` directories with digest.md, notes.md, procedures, and reflexes.

**of2r digest (line 4):** "Death step23285: lava at (-3006,10,-5706). Avoid approaching within six blocks without inspecting terrain."
- Successfully avoided of2's death location; did not revisit lava trap.

**of3r digest (line 4):** "Shallow iron: x=-3030,y=61-62,z=-5580. Target block approximately at (-3030,62,-5580)."
- Used to guide initial iron routing efficiently (by step 10,528 vs. of2's step 12,884).

**Codex rollout grep:** of2r rollout contains 100+ references to `previous/life_1/mine/`, `procedures/level_north.py`, `procedures/north_stair.py`, reflexes like `lava_ahead.py`.

### Route Shaping by Digest
**of3r:** Digest named gravel at x=-3169..-3175, y11, z=-5576; lines 13240-13487 show westward tunnel mining *toward* this exact x range.
- Model copied west_level and west_stairs procedures from life_1.
- Tunnel stalled at movement=0 without reaching gravel; did not retry or abandon.

**of2r:** Digest warned of lava frontier at (-3217,11,-5576.3); of2r instead descended southward (y=10→8) and mined obsidian there successfully (step 31,911).
- Digest guidance avoided lava face but did not prevent obsidian trap death.

### Mistake Repetition
**of2r lava escape (step 23,285 remembered):** of2r did NOT die in the remembered lava at step 23,285 location; instead died at (-3007,8,-5680) under obsidian, ~800 ticks after mining obsidian successfully. Reflex misinterpreted burn as mob.

**of3r tunnel stall:** Same "two blocks west" plan repeated 15+ times after movement=0 reported; model did not break loop.

## 4. Deaths Near Lava/Obsidian: Reflex Role and Water Bucket Awareness

### of2 Death: Step 23,285 at (-3006, 10, -5706) in Lava

**Last ~15 actions:**
1. (Action 1014, step 23268) Mining obsidian face; health 8/20, flame visible.
2. (Action 1015, step 23280) Attempted dirt placement in lava (jump+use×20); **placed 0 blocks**, health drops to 4/20. Plan observed mismatch.
3. (Action 1015b, step 23283) Lava_ahead reflex fires: "lava fills lower view during raw -- stepped back 6 ticks; seal the flow."
4. (Action 1016, step 23285) "Hold jump plus forward to swim" ×30 ticks; **jumped 134 blocks south** into respawn zone.
5. **YOU DIED at (-3006, 10, -5706)**.

**Water bucket evidence (line 12457, at death):** `bucket -1, water_bucket -1` in inventory.
- Model carried bucket AND water_bucket but neither was deployed.
- No [ACTION] use_at water_bucket recorded in preceding 20 actions.
- **Interpretation:** Model did not recognize bucket placement as an escape route; focused on dirt staircase and swimming instead.

**Reflex role:** lava_ahead reflex stepped the model *back* into the lava during raw action execution (6 ticks of backstepping), contradicting the forward swimming plan.

### of2r Death: Step 32,270 at (-3007, 8, -5680) Under Obsidian Cap

**Last ~15 actions:**
1. (Action 1958, step 31,911) Successfully mined obsidian; milestone 13/24 verified.
2. (Action 1959, step 31,921) Poured water onto (-3007,10,-5680) below face; obsidian +1 pickup.
3. (Actions 1960-1975, steps 31,930-32,250) Tunneling north/west inside the water-flooded chamber; health 20/20.
4. (Action 1975, step 32,260) Still digging; health 8/20 (took damage from **burning**, not noted as lava in-view).
5. (Action 1976, step 32,270) "[REFLEX hit] took 4 damage with no lava in view: a mob is at you." Health 4/20. Plan dropped.
   - **Key issue:** Burn (from obsidian fire) misread as mob attack.
6. (Action 1976b, step 32,270) Resume swimming forward×8 ticks; reflex lava_ahead fires.
7. **YOU DIED at (-3007, 8, -5680)** and respawned.

**Water bucket:** Model HAD placed water after mining obsidian (step 31,921, "bucket +1, water_bucket -1"). But the chamber still contained lava/fire below, and the water cap was built over the model's own head by the obsidian block.

**Reflex role:** hit reflex fired on burn damage, interpreting fire as mob; lava_ahead reflex then kicked in but model was already trapped under its own obsidian. The two reflexes contradicted: one said "fight" (stop digging), the other said "back away" (lava_ahead stepping back). Model suffocated under its own build.

## 5. Systematic Issues: EXPECT Mismatches, Torch/Light, Food/Hunger, Single-Block Pacing

### EXPECT Line Mismatches (Recurring pattern)
**of3 line 10078:** "[PLAN] Mine two blocks west... [EXPECT] x≈-3109.7..." repeated 30+ times identically → movement=0 after first cycle.
- EXPECT remained static despite move failure; model did not update prediction or diagnose stall.

**of2 line 12373:** Repeated "[EXPECT] Position near z=-5706.7, 286 cobblestone, 42 pickaxe uses, 15 torches..." across 8+ plans.
- Walked into lava while repeating the same z-target; no re-evaluation.

### Single-Block Cell Tunneling Pace
**of2 lines 8550-9100:** Descending 8 blocks (y35→y27) consumed ~550 steps.
- Pattern: place torch (10-15 ticks) + reequip pickaxe (5 ticks) + mine 1 block (30-50 ticks) = ~60 ticks/block for descent.
- Horizontal tunneling (of3 diamond search): 2 blocks per 25-30 step cycle = ~12-15 ticks/block.
- **Cost:** Vertical single-cell descent is 4-5× slower than horizontal; of2 lost ~6k steps to vertical inefficiency.

### Torch and Light Management
**No systematic issues** observed in logs; torches consistently placed and used. Both of2r and of3r maintained 8-15 torches throughout.

### Food and Hunger
**No recorded hunger deaths or starvation events** in of2/of3/of2r/of3r runs.
- of2 died at step 23,285 with full health before lava (health 4/20 at end).
- of3 reached step 30,200 without food crisis.
- of2r reached step 32,270 with food visible in inventory.
- **Likely:** Mobs (spiders, etc.) or hazards (lava/fall) prioritized over hunger mechanics.

## Summary of Cost Allocation

| Cost Source | Est. Ticks/Freq | Impact on of2 (10.4k gap) | Impact on of3 (17k gap) |
|---|---|---|---|
| Single-cell tunnel descent pace | 60/block | ~4,500 ticks (75 blocks down) | ~2,000 ticks (35 blocks) |
| Diamond search inefficiency | 25-30/cycle | N/A | ~8,000 ticks (320+ cycles, zero yield) |
| Crafting slot conflicts | 50-150 × 2-3 | ~300 ticks | ~300 ticks |
| GUI/frame lags | 10-50 × 8-15 | ~400 ticks | ~500 ticks |
| go_to stalls/detours | 50-200 × 3-5 | ~600 ticks | ~900 ticks |
| Plan drops (reflex/fall) | 100-500 × 1-3 | ~800 ticks | ~600 ticks |
| **Remaining (uncharted routing, loop repetition, inspection overhead)** | — | **~3,400 ticks** | **~4,700 ticks** |

**What would have broken the patterns:**
1. **of2:** Landmark-based routing (avoid y<11 until fully prepared) + immediate water pour on lava entry → prevented 10k-step death.
2. **of3:** Depth-first diamond search (y=11→y8→y4) instead of horizontal at single y; would have found diamonds or abandoned in 5k steps.
3. **of2r/of3r:** Stall detection + explicit termination of looping plans; of3r tunneling would exit after 3 repeated movement=0 outcomes.
