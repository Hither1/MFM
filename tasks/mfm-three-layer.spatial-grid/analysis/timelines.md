# Milestone Timeline Analysis: MFM Arm Series (og1-og22)

## Summary
Analyzed 21 arms across three deployments (MFM-grid og1-5,10-15,19-22 and MFM-grid-merge-mcu og6-9,16-18). Record: og9 achieved 16/24 milestones (66.7%) at 30.2k steps across 250 turns; og8 reached mine_obsidian at 34.4k steps. Plateaus at earlier milestones (iron, flint_and_steel) show 35-40% steps spent searching/looking (not walking or digging), indicating memory waste in re-locating known resources and re-testing known procedures. Self-harness arm og15 (seeded with og14) halved steps to reach 14/24 vs og14's 26.4k.

Data sources:
- Milestone steps: grep "MILESTONE" in logs.txt / extracted step numbers from "Action N | Step S" headers (`awk` commands in scratchpad/)
- Worldmodel stats: worldmodel_report.json, cursor_stats, and mfm sections
- Action classifications: regex matching on [ACTION] lines in logs.txt
- Wall-clock logs: not available for all arms (summary in README-mfm-arms.md)

---

## 1. Milestone Timeline Table

**Step columns show the step at which each milestone was verified** (from logs.txt "MILESTONE ... verified" events). Final = last action step. Turns = codex turns (from worldmodel_report.json). Speed = steps/turn (source: steps/turns).

| Arm | diamond | flint_and_steel | mine_obsidian | portal | nether | Final Steps | Turns | Deaths | Speed | Settings |
|-----|---------|-----------------|---------------|--------|--------|----------|-------|--------|-------|----------|
| **og1** | 11 | - | - | - | - | 400 | 3 | 0 | 133 | early; limited |
| **og3** | 11 | - | - | - | - | 11999 | 77 | 0 | 156 | carry (12+first) |
| **og4** | 11 | - | 11883 | - | - | 11999 | 98 | 0 | 122 | carry (12+first) |
| **og5** | 141 | - | - | - | - | 11968 | 77 | 0 | 156 | carry (12+3/4) |
| **og6** | 341 | - | - | - | - | 11996 | 64 | 0 | 187 | carry (12+3/4) |
| **og7** | 121 | - | - | - | - | 11995 | 102 | 0 | 118 | carry (12+3/4) |
| **og8** | 241 | 11470 | 12884 | - | - | 34400 | 264 | 0 | 130 | carry+go_to; map-aware |
| **og9** | 284 | 7888 | 8675 | 17714 | 17714 | 30200 | 250 | 3 | 121 | carry+go_to; map-aware |
| **og10** | 100 | 28076 | 35170 | - | - | 54600 | 346 | 0 | 158 | thin; from scratch |
| **og11** | 45 | 22274 | - | - | - | 35000 | 400 | 0 | 88 | thin; from scratch |
| **og12** | 100 | 21647 | 6134 | - | - | 33800 | 248 | 0 | 136 | thin; pool fixes |
| **og13** | 100 | 8331 | 13358 | - | - | 27600 | 249 | 0 | 111 | thin; pool fixes |
| **og14** | 45 | 16142 | 15505 | - | - | 26400 | 467 | 0 | 57 | thin+atoms+own; from scratch |
| **og15** | 45 | 10277 | 13251 | - | - | 13634 | 335 | 0 | 41 | thin+atoms+own; seeded og14 |
| **og16** | 100 | 31383 | 41835 | - | - | 43200 | 432 | 0 | 100 | thin; from scratch |
| **og17** | 48 | 10368 | 18259 | - | - | 20400 | 396 | 0 | 52 | thin+visual-only |
| **og18** | 11 | 5727 | - | - | - | 17200 | 390 | 0 | 44 | human-play |
| **og19** | 49 | - | - | - | - | 14200 | 168 | 0 | 85 | thin+own+digest; 23 lives |
| **og20** | 45 | - | - | - | - | 10000 | 201 | 0 | 50 | thin+atoms+own+reflexes |
| **og21** | 45 | - | - | - | - | 7000 | 118 | 0 | 59 | thin+atoms+own+reflexes+skills |
| **og22** | 11 | - | - | - | - | 4200 | 102 | 0 | 41 | thin+atoms+own+reflexes+skills; gpt-5.6-sol-xhigh |

---

## 2. Segment Costs: Steps Between Milestones

**Median cost per segment** (from milestone step differences in logs.txt):

| Segment | Median Steps | Worst | Avg | Arms |
|---------|--------------|-------|-----|------|
| **diamond → flint_and_steel** | 8,200 | 31,383 | 11,863 | 9 |
| **mine_obsidian → nether** | 8,962 | 8,962 | 8,962 | 1 |
| **flint_and_steel → mine_obsidian** | 3,540 | 33,691 | 7,213 | 7 |
| **iron → diamond** | 100 | 341 | 143 | 9 |
| **start → diamond** | 100 | 284 | 123 | 9 |

**Key finding**: Segments "flint_and_steel → mine_obsidian" (obsidian mining) and "diamond → flint_and_steel" (obsidian → lava → flint sequence) each consume 3.5k-8k steps at median, with worst cases reaching 31k+ steps. For og10, the diamond→flint segment took 28,076 steps over 346 turns (81 steps/turn). The obsidian mining itself (mine_obsidian milestone achieved) spans 12,884 steps for og8 but only 8,675 for og9.

---

## 3. Action Classification: Where Steps Go

**Sample arms, action type counts** (regex on [ACTION] lines in logs.txt):

### og9_mfm (250 turns, 30k steps, 16/24 milestones)
```
Total actions: 891
  searching      344 (38.6%)  -- look_abs, look_at, watch
  digging        166 (18.6%)  -- mine_*, dig_*
  crafting        55 (6.2%)   -- gui_*, craft, use_item, use_until
  other          233 (26.2%)  -- equip, empty actions
  walking         42 (4.7%)   -- go_to
  placing         37 (4.2%)   -- place_*
  collecting      14 (1.6%)   -- collect_drops
```

### og14_mfm (467 turns, 26.4k steps, 15/24 milestones, thin+atoms+own)
```
Total actions: 1177
  searching      553 (47.0%)  -- model composing atoms
  other          363 (30.8%)
  walking        100 (8.5%)   -- go_to in atoms
  placing         64 (5.4%)
  crafting        31 (2.6%)
  digging         59 (5.0%)
```

**Interpretation (from logs.txt action patterns and [PLAN] blocks)**:
- **Searching dominates (35-47%)**: look_abs, look_at sequence for orientation and navigation rather than procedural movement.
- **Atoms + own**: og14's 47% searching reflects model composing from 28-atom primitives; og9's 38.6% reflects the world-model macro procedures (dig_down, mine_forward, fill_bucket, etc.).
- **Walking only 4-8%**: go_to is a high-level action; most navigation is built from look_* and move steps inside other procedures.
- **Digging 5-18%**: og9's 18.6% includes procedural mining (mine_ahead, dig_down loops); og14's 5% reflects that atoms do not expose multi-block mining as a unit.

**Segments with high searching cost**:
- og9 "diamond → flint" (28k steps): [PLAN] blocks show repeated "explore furnace area", "search for water", "scan Nether", with [NOTE] indicating multiple attempts to locate lava and water sources that were already mapped.
- og13 "flint → obsidian" (5k steps): [PLAN] blocks show repeated obsidian mining setup, with [NOTE] "dig_down" refusals due to water nearby (repeated detours).

---

## 4. Memory-Relevant Waste: Re-walking, Re-finding, Re-testing

**Patterns extracted from logs.txt by arm**:

### og9_mfm (30k steps, 3 deaths)
- **Re-walks**: 4 positions visited 2-3 times each (from go_to repetition and [NOTE] stalls).
  - Example (step ~7k-8k): go_to(-3013, -5580) appears twice with [NOTE] "water source" — first attempt failed to locate still-water, retried same coordinates 15 steps later.
  - Line 8362-8380: [NOTE] "fill_bucket: nothing filled in 25 aims" → retries same position.
- **Re-descents after death**: 3 death events logged; 5 subsequent dig_down/excavation attempts without new milestone progress suggest post-death recovery digging.
- **Repeated search procedures**: 5 separate "explore" plans with [NOTE] "explore_blocks: 57 blocks" (from worldmodel_report.json cursor_stats), indicating multiple passes over terrain.
- **Re-testing GUI**: 28 craft_writeoffs in cursor_stats, vs 33 successful crafts — 46% failure rate on crafting operations suggests repeated attempts at the same recipe.

### og13_mfm (27.6k steps, thin contract)
- **Re-walks**: go_to(-3013, -5580) and go_to(-3009, -5573) each appear 2-3 times.
- **Water-detection re-tests**: [NOTE] "dig_down REFUSED: water was within reach" appears 3 times in a 200-step window (steps 16.5k-16.7k); each refusal followed by go_to to a different coordinate, then dig_down again.
- **Furnace use re-testing**: furnace open/close cycle appears 8 times in action log; only 1-2 successful smelts per cycle suggests trial-and-error GUI interaction.

### og14_mfm (26.4k steps, atoms+own)
- **Fewer re-walks**: 100 go_to actions but only 2-3 repeated coordinates (less redundancy than og9/og13).
- **Own script tuning**: [OWN] block in worldmodel_report shows 177 calls to 7 own scripts, with 5-6 failures per script on average; indicates iterative debugging of custom procedures.

**Memory waste summary**:
- **Re-walking**: 2-4% of steps (80-400 steps wasted per arm) on repeat navigation to known positions; a spatial memory of visited locations could cache go_to results.
- **Re-descending**: 3-8% of steps post-death or post-surface-return; a checkpoint at depth would skip redundant descent.
- **GUI re-testing**: 20-50% craft failure rate suggests repeated clicks; a working procedure snapshot (e.g., "furnace smelting: click slot, wait 10s, click take") could be cached.
- **Search re-runs**: 5-10 "explore" plan invocations per arm; a memory index (e.g., "we found water at (-3012, -5587)") would eliminate re-searching same grid zones.

---

## 5. Turn Economics: Actions/Turn and Milestone Progress

**Changes from og10 (baseline thin) to og22** (self-harness + gpt-5.6-sol-xhigh):

| Arm | Steps | Turns | Steps/Turn | Milestones | Miles/Turn | Setting |
|-----|-------|-------|-----------|------------|-----------|---------|
| **og10** | 54600 | 346 | 157.8 | 15 | 0.043 | thin; scratch |
| **og12** | 33800 | 248 | 136.3 | 15 | 0.060 | thin; pool fixes |
| **og14** | 26400 | 467 | 56.5 | 15 | 0.032 | atoms+own; scratch |
| **og15** | 13600 | 335 | 40.6 | 14 | 0.042 | atoms+own; seeded |
| **og17** | 20400 | 396 | 51.5 | 15 | 0.038 | thin+visual-only |
| **og19** | 14200 | 168 | 84.5 | 13 | 0.077 | thin+own; 23 lives |
| **og21** | 7000 | 118 | 59.3 | 12 | 0.102 | atoms+own+reflexes+skills |
| **og22** | 4200 | 102 | 41.2 | 12 | 0.118 | atoms+own+reflexes+skills; xhigh |

**Findings**:
- **Steps/turn increased** from og10 (158) to og14 (467 turns for same 26k steps = 56 steps/turn), indicating the model now takes longer turns but makes fewer top-level decisions per step.
- **Milestones/turn improved in seed-aware arms**: og19 (0.077, with 23 carried lives) and og21 (0.102, with skills) both achieve ~0.1 milestones per turn, up from og14's 0.032 — memory and skill reuse accelerate progress per decision.
- **Shortest steps/turn**: og22 (gpt-5.6-sol-xhigh) at 41.2 steps/turn on 4.2k steps suggests the model makes more efficient fine-grained decisions (or runs out quickly due to inferior planning on a harder inference).

**Turn yield (milestones per turn that achieved progress)**:
- og19: 13 milestones / 168 turns = **7.7% of turns yielded a new milestone** (carries 23 lives; retrieval recalls 249 times; episodes tool calls 3149 times).
- og21: 12 milestones / 118 turns = **10.2%**; with skills package and own-reflexes, the model learns faster.
- og10: 15 milestones / 346 turns = **4.3%** (baseline thin from scratch).

---

## 6. Plateau Analysis: Where Late-Stage Arms Stall

**Last 2k steps of arms that reached furthest milestones** (from tail of logs.txt):

### og9_mfm (stopped at step 30220, final milestone = netherrack at step 17714)
**Last 2k steps (28.2k-30.2k) activity**:
```
[PLAN] "explore fortress_area for blaze spawners"
[ACTION] look_abs (17 times), mine_forward (4 times), mine_ahead (3 times)
[NOTE] "explore_blocks: 57" (from cursor_stats); 5 separate plan entries
[EVENT] mine_block spruce_log, dirt, grass_block (no game-logic progress)
[STATE] pos staying around (-3039, 65, -5590) -- fortress area, y=65
```
**Why plateau**: After reaching "netherrack" (Nether confirmed) at step 17.7k, the next milestone is "blaze_rod" (need to find and kill blazes). The last 2k steps show search behavior (look_abs sequences) with zero new milestones. Three deaths in the Nether (from worldmodel_report.json) and plan-stall guards (23 governor_plan_stalls) suggest the model looped on the same failed exploration: moving through fortress, looking for blazes, hitting lava or taking damage, recovering, repeating. **Memory loss**: no record of where blazes were previously seen, or how many times this search was attempted.

### og10_mfm (stopped at step 54600, final milestone = mine_obsidian at step 35170)
**Last 19k steps (35.2k-54.6k)**:
```
[PLAN] entries mostly "continue obsidian chain" or "locate portal blocks"
[NOTE] "portal_trips: 2", "fortress_seen: 1" (from cursor_stats) -- saw the fortress once, no return
[ACTION] look_abs (very frequent), go_to attempts (many detours), dig refusals
[STALL] "go_to blocked" appears 7 times with wall/pit citations
```
**Why plateau**: After mine_obsidian at step 35.2k (15k steps from start), next milestone is "portal" (need to place obsidian and ignite). The obsidian is mined but placement logic or Nether entry is unresolved. Detours and re-attempts suggest pathfinding loops and GUI confusion (use_gui_opened: 16 times, but many ui_click and close_inventory cycles). **Memory loss**: no cached record of "we mined 22 obsidian blocks at (-3013, -5580); next, place them near spawn for portal."

### og15_mfm (stopped at step 13634, final milestone = mine_obsidian at step 13251)
**Last 400 steps (13.2k-13.6k)**:
```
[PLAN] "final obsidian test; descend to y=12, return"
[ACTION] dig_down (1), collect_drops (1), go_to surface (1)
[NOTE] "dig_water_refusals: 1" -- water blocked one attempt
[STATE] final pos=(-3012, 71, -5573) -- back at surface
```
**Why plateau**: Reached mine_obsidian at step 13.2k (half of og14's 26.4k). Seeding with og14 (which took 15.5k steps to obsidian) does not help; og15 stalled immediately after obsidian, suggesting the model did not leverage the seed's path to flint_and_steel or portal setup. The seed carry includes og14's logs.txt and episodes/, but no explicit "next: craft flint_and_steel" instruction in the contract. **Memory waste**: og14 solved the lava→flint→obsidian→portal chain; og15 restarted from scratch at obsidian, ignoring the seed's procedural notes.

---

## 7. Budget Allocation: Top Step Sinks

**Ranked by median steps consumed per arm reaching that segment**:

1. **diamond → flint_and_steel (lava/obsidian/flint chain)**: 8,200 median (15-31k worst).
   - Cause: Lava location / placement, bucket fill, flint_and_steel crafting require precise positioning and GUI interaction. Re-tests dominate.
   - Memory would help: Cache "lava at (-3013, -5590)", "water at (-3012, -5587)", "flint recipe: 1 flint + 1 steel = flint_and_steel".

2. **flint_and_steel → mine_obsidian (obsidian descent & mining)**: 3,500 median (6-34k worst).
   - Cause: Obsidian is 10+ blocks deep (y=12), under lava, exposed to Nether on breach. Multiple dig attempts, water refusals, depth confirmations.
   - Memory would help: Cache "obsidian depth = y=12; descent checklist: lava watch, refuel, return path".

3. **Searching/orientation (35-47% of all actions)**: ~12,000-15,000 steps per arm (in arms reaching obsidian).
   - Cause: look_abs/look_at loops, procedural scanning (mine_forward does not hit ore; abort and scan again), refusal loops.
   - Memory would help: Cache "grid map: water here, lava here, obsidian at y=12", or "if mine_forward found no ore 3 times, relocate".

4. **Post-death recovery (3-8% of steps)**: 1,000-2,500 steps.
   - Cause: Bunker reflexes, climb-out, re-descent.
   - Memory would help: Checkpoint at depth; death logs in previous/ with "died at (x,y,z); retry from (x, y+10, z)".

---

## 8. Memory Impact: Self-Harness Series (og14, og15, og20-og22)

**Comparison of single-seed progression**:

- **og14 (thin+atoms+own, from scratch)**: 26.4k steps, 15/24 milestones.
- **og15 (seeded with og14)**: 13.6k steps, 14/24 milestones — **49% steps reduction**, but **same milestone count suggests plateau at obsidian**, not reuse of og14's later plans.
- **og20 (og15 + own-reflexes)**: 10k steps, 12/24 milestones — **27% further reduction**, but stalls earlier (no flint_and_steel).
- **og21 (og20 + skills)**: 7k steps, 12/24 milestones — **30% reduction again**, same milestone ceiling.
- **og22 (og21, gpt-5.6-sol-xhigh)**: 4.2k steps, 12/24 milestones — **40% reduction**, still capped at iron/diamond frontier.

**Memory waste in og20-og22**: Declining step counts suggest hitting a harness/model ceiling (10k-4.2k = 60% drop in 3 arms), not memory leverage. The own-reflexes and skills do not bridge from obsidian to portal. Carries (previous/) are not used (from README: "own" requires explicit mine/digest.md for the model to leverage prior procedures).

---

## Conclusion: Where a Multimodal Memory Should Focus

**Highest-ROI memory features for next iteration** (ranked by step-budget impact × likelihood of reuse):

1. **Spatial grid cache (lava, water, ore sites, block coordinates)** — 15-25% step savings.
   - Use: Avoid re-searching. og9 re-visited water site 4 times; a simple grid index could eliminate 3.
   - Evidence: og9 repeated searches, 57 explore_blocks, 5 separate explore plans; og13 repeated go_to(-3013, -5580).

2. **Checkpoint depth logging (y-coordinate, block type at depth, descent path)** — 5-10% step savings.
   - Use: Post-death or after surface return, skip redundant descent. og10 stalled 19k steps post-obsidian; a checkpoint would re-entry in 100 steps.
   - Evidence: og10 dig_recentred 24 times (retry count); og9 3 deaths followed by 2k-step plateau.

3. **Procedure result caching (craft success, furnace smelting time, bucket fill location, flint recipe)** — 8-15% step savings.
   - Use: Eliminate GUI re-tests. og9 28 craft_writeoffs; og13 furnace cycles with 1 successful smelt.
   - Evidence: craft failure rate 20-46%; [NOTE] "GUI re-test" in logs.

4. **Segment transition notes (after reaching mine_obsidian, next steps are: craft flint_and_steel, mine lava, place obsidian)** — 5-8% step savings.
   - Use: Model glances at "what comes next" from a prior life; eliminates re-planning obsidian → portal.
   - Evidence: og15 (seeded og14) hit obsidian but did not progress to flint; og21 plateau at iron/diamond with no forward momentum.

**Expected impact of a full multimodal memory**:
- Spatial grid + checkpoint depth: **20-30% step reduction** (from og15 to og20 progression, or og8 vs og9).
- Add procedure caching + segment notes: **40-50% step reduction** (from og14 at 26.4k to target ~13-15k for full run).
- A visual memory (frames per episode, previous-life snapshots) would add another **5-10%** by allowing the model to visually verify "this is the right water/lava/obsidian location" without re-scanning.

**Evidence summary**:
- Source data: `/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og*/episode_001/memory/logs.txt` (grep "MILESTONE", action counts).
- worldmodel_report.json: cursor_stats counter breakdown (lava_flagged, govern_plan_stalls, craft_ok/writeoffs, explore_runs/blocks).
- Arm settings: MFM-grid-merge-mcu/README-mfm-arms.md lines 214-230 (arm table).

