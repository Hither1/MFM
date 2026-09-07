# Portal Phase Analysis: Obsidian Mining to Nether Entry

## 1. Phase Timelines by Run

### OG9 (grid-merge-mcu): Step 8675-17591 (~8,916 steps)
- **First obsidian mine**: Step 8675 → 8984 (obsidian +2)
- **Obsidian mining** (23 mine_obsidian calls): 8675-14909, totaling 10 obsidian collected
- **Placement attempts** (14 place_at obsidian): Steps 11224-12272
  - Step 11224: placed (-2990,11,-5559) ✓
  - Step 11294: **FAILED "did not go down"** at (-2989,11,-5559) after 3 face attempts (north last)
  - Step 11412: placed (-2989,11,-5559) ✓ (retry, same location)
  - Steps 11749-11954: 7 more successful placements across frame
  - Result: 13/14 successful; 1 placement failure mid-frame
- **Portal frame** formed: X ∈ [-2991, -2988] (4 wide), Y ∈ [11, 15] (5 tall), Z=-5559 (single plane)
- **Flint & steel**: Crafted step 7888, used at 14274
- **Nether entry**: Step 17591 at (-361.88, 47.0, -686.5) after 3 deaths in Nether
- **Phase steps**: 8916 total (first obsidian mine 8675 → entry 17591)

### OG13 (MCU): Step 13358-18660 (~5,302 steps)
- **First obsidian mine**: Step 13358 → 13375 (obsidian +1)
- **Obsidian mining** (15 mine_obsidian calls): 13358-16650, totaling 14 obsidian collected
- **Placement attempts** (10 place_at obsidian): Steps 17080-17483
  - **ZERO failures**: All 10 placements successful on first attempt
  - Steps 17080, 17092, 17104, 17114, 17247, 17307, 17316, 17463, 17473, 17483
- **Portal frame** formed: X=-2959 (single plane), Y ∈ [10, 14] (5 tall), Z ∈ [-5627, -5624] (4 wide)
- **Flint & steel**: Crafted step 8331, used at 17473
- **Nether entry**: Step 18660 at (-379.5, 49.0, -686.65), died at 18818
- **Phase steps**: 5,302 total (first mine 13358 → entry 18660) — **36% faster than OG9**

### OG8 (grid-merge-mcu): Step 12884-14349 (~1,465 steps to death)
- **First obsidian mine**: Step 12884 → 12913 (obsidian +1)
- **Obsidian mining** (6 mine_obsidian calls): 12884-14052, totaling 5 obsidian collected
- **Placement attempts** (0 place_at obsidian): **NEVER attempted frame placement**
  - Instead, placed cobblestone scaffolding around mining sites (steps 12913-14080)
  - Pattern: mine obsidian → place cobblestone to contain/support
- **No portal frame built**
- **Death**: Step 14349 at (-2987,11,-5558) with all 5 obsidian lost
- **Phase duration**: 1,465 steps, incomplete (obsidian loss on death)

### OG12 (MCU): Step 6134-28364+ (still running; ~22,230 steps so far)
- **First obsidian mine phase 1**: Step 6134 → 6264 (obsidian +1)
- **Placement attempts phase 1** (0 place_at obsidian): Tried cobblestone scaffolding at 6195, 6273, 6275, 6364, 6496
- **MAJOR DIVERSION**: Steps 6264-27189 (~20,925 steps)
  - Descended to mine underground lava-based obsidian via make_obsidian at step 7421
  - Spent ~8500 steps mining and exploring underground (steps 15000-17700)
  - Climbed surface and traversed to flint location (~1500 steps)
  - Attempted pig hunting, failed
  - Eventually resumed obsidian mining at step 27189
- **Second obsidian phase**: Steps 27189-28358, collected 6 more obsidian blocks
- **Placement attempts phase 2** (0 place_at obsidian): **ZERO frame placement attempts**
  - Only cobblestone scaffolding placed around mining sites
- **Flint & steel**: Crafted at step 21647 (not used yet)
- **Nether entry**: NOT YET REACHED (still running)
- **Current status**: 7-8 obsidian collected, but no portal frame placement attempted despite having flint_and_steel

## 2. Comparison: OG13 vs OG9 (Success vs Delay)

**Speed advantage OG13 over OG9**: 3,614 steps saved (8,916 - 5,302 = 3,614; 40% faster)

### Key Differences in Execution

| Aspect | OG9 | OG13 | Impact |
|--------|-----|------|--------|
| **Obsidian mining efficiency** | 23 mine calls (8,675-14,909) | 15 mine calls (13,358-16,650) | OG13 mined more efficiently (14 vs 10 collected) despite fewer calls |
| **Placement reliability** | 13/14 success (1 failure at step 11294) | 10/10 success (0 failures) | OG13 had perfect placements; OG9 had mid-frame failure |
| **Frame orientation** | X-direction wide (4 blocks) | Z-direction wide (4 blocks) | Both valid 4×5 frames, different spatial layout |
| **Mining-to-placement gap** | ~2,550 steps (8,984 → 11,224) | ~1,705 steps (13,375 → 17,080) | OG13 started frame placement earlier in sequence |
| **Placement clustering** | Spread across 1,048 steps | Concentrated in 403 steps | OG13 rapid-fire placements (faster frame completion) |
| **Flint timing** | Crafted at 7,888; used at 14,274 (6,386 steps after craft) | Crafted at 8,331; used at 17,473 (9,142 steps after craft, but earlier in mining) | OG9 had flint ready earlier but placed portal later |

### The Placement Failure Pattern

**OG9 failure at step 11294**: target (-2989,11,-5559), "did not go down after 3 face(s) (north last)"
- This was the **second obsidian block** in the lower-left row
- Harness tried faces: below (Y-1), then others, finally north face — all refused
- Message: "target spot is probably occupied, or nothing solid stands on the side being clicked"
- Hypothesis: first block at (-2990,11,-5559) placed successfully, but second block position was blocked or un-clickable from current approach

**OG13 success**: all 10 blocks placed without retry, different spatial pattern may have avoided same block-conflict geometry

## 3. OG8 & OG12: Portal Frame Building Never Attempted

### OG8 (Failure to Build)
- **Why no portal placement**: After mining 5 obsidian, died at step 14349 with obsidian inventory wiped
- **Why only 5 obsidian**: Mining effort was scaffolding-heavy (place cobblestone after each obsidian mine), consuming time
- **Pattern**: place_at(cobblestone) → mine_obsidian → place_at(cobblestone) loop = inefficient mining support
- **Total loss**: 1,465 steps with 0 portal blocks placed

### OG12 (Diversion and Stall)
- **Phase 1 failure (steps 6134-6364)**: Got 1 obsidian, then attempted cobblestone scaffolding but encountered placement refusals ("did not go down at (-2993, 11, -5558) after 3 face(s)")
- **Diversion trigger**: Unable to place frame at starting location, harness then pivoted to underground mining (make_obsidian) instead of retrying surface frame
- **Stall from steps 6264-27189**: Spent ~20,925 steps on:
  - Underground lava-based obsidian conversion
  - Vertical mine exploration
  - Surface pig hunting detour
  - **Never returned to portal frame building**
- **Phase 2 attempt (steps 27189-28358)**: Mined 6 more obsidian but again only placed cobblestone scaffolding around mines, **zero frame placement calls**
- **Current impasse**: Has flint_and_steel (step 21647) and 7-8 obsidian, but harness has not issued `place_at(obsidian)` commands for portal frame
- **Inference**: harness plan logic may have abandoned frame-building path after phase 1 refusal, treating underground obsidian as alternative path that then deadended

## 4. Systematic Problems Identified (2+ runs with same failure)

### Problem A: Placement Block Position Conflicts
**Evidence**: OG9 step 11294, OG8 step 6364, OG12 steps 6275, 6364
- **Symptom**: "did not go down after 3 face(s)" or "cobblestone did not go down"
- **Trigger**: Attempting to place obsidian/cobblestone in frame-building sequence at coordinates where previous block already exists or face is unsupported
- **Runs affected**: OG9 (1 failure, recovered via retry), OG8 (led to death before retry), OG12 (phase 1 abandoned)
- **Harness note format**: `[NOTE] place_at(obsidian): the obsidian did not go down at (x,y,z) after N face(s) (face_name last): ...`
- **Cost**: OG9 = 118 steps retry; OG8 = unrecovered loss; OG12 = triggered entire diversion

### Problem B: Portal Frame Never Placed After Mining Obsidian
**Evidence**: OG8 (0/14 place_at obsidian calls), OG12 (0/0 place_at obsidian calls across both phases)
- **Symptom**: Obsidian blocks mined and carried, but harness never executes frame placement sequence
- **Root cause candidate**: Harness plan graph may collapse when early placement fails (OG12 phase 1), falling back to alternative mining paths instead of replan-and-retry
- **Cost**: OG12 = 20,925 steps wasted on underground mining + surface exploration; OG8 = death without portal frame
- **Pattern**: Both runs placed cobblestone scaffolding but never attempted obsidian placement for portal frame

### Problem C: Placement Sightline Geometry Not Validated
**Evidence**: OG9 step 11294, OG8 step 13831
- **Symptom**: place_at action called with specific face (e.g., "below"), but that face is not clickable from current position
- **Harness check missing**: Before `place_at(obsidian, face=below)`, no verification that:
  - Target block face is accessible (not behind player hitbox, not obscured by prior blocks)
  - Supporting block actually exists on that face
  - Frame geometry doesn't create self-blocking conflicts
- **Cost**: Cascading retries (OG9: +118 steps), frame completion delays, or abandonment (OG12, OG8)

## 5. Concrete Harness-Side Fixes

### Fix 1: Frame Placement Verification Procedure
**What**: Add `verify_frame_placements(x_range, y_range, z_range)` procedure before and after placement sequence
**Check**:
- Scan target obsidian coordinates via raycast/sightline check before each `place_at` call
- Verify all target faces are accessible (no self-blocking)
- After placement, confirm inventory delta matches expected (obsidian -1 per block)
- Inventory count vs. frame size must be sufficient (10 obsidian for 4×5 frame)

**Harness note format example**:
```
[NOTE] verify_frame_placements: scanning 10 target coords...
[NOTE]   (-2959, 10, -5626): below face ACCESSIBLE ✓
[NOTE]   (-2959, 10, -5625): below face ACCESSIBLE ✓
...
[NOTE] frame verification complete; 10/10 targets ready; obsidian count = 10 ✓
```

**Estimated steps saved**: 150-300 per failed run (avoids retries + frame abandonment)

### Fix 2: Placement Face Auto-Selection with Fallback
**What**: Change `place_at(x, y, z, item=obsidian, face=below)` to smart-face mode
**Logic**:
- Try primary face (below for frame base, west/east for uprights)
- On failure, scan adjacent faces in priority order (west → east → north → south → above)
- On second failure, move back or sideways one block and retry from better sightline angle
- Refuse only after 2 position attempts + 6 face attempts with explicit [NOTE]

**Harness note format example**:
```
[NOTE] place_at(obsidian) at (-2989, 11, -5559): below face failed; trying west face...
[NOTE] place_at(obsidian): placed at (-2989, 11, -5559) (west face) — sidestep applied
```

**Estimated steps saved**: 200-400 per run (eliminates mid-frame hangs)

### Fix 3: Plan-Collapse Recovery: Portal Frame Fallback
**What**: If `place_at(obsidian)` encounters >1 placement failure, do NOT abandon frame building; instead trigger frame-rebuild plan
**Logic**:
- On first placement failure: log [NOTE], issue retry with face rotation
- On second consecutive failure at same location: issue `look_abs` to change sightline angle, retry from new position
- On third failure: back up, scan frame geometry, and issue full `equip_hotbar + place_at` sequence for that block
- If frame reaches 80% completion (8/10 blocks), proceed to flint_and_steel and portal lighting (accept minor frame damage)

**Harness note format example**:
```
[NOTE] place_at(obsidian) retry 2 at (-2989, 11, -5559): failure mode = unsupported face
[NOTE] frame_fallback: adjusting sightline and retrying from position (-2989, 11, -5560)
[NOTE] place_at(obsidian): placed at (-2989, 11, -5559) (north face) — sightline adjust
```

**Estimated steps saved**: 800-3000 per run (prevents OG12-style 20k-step diversion, prevents OG8-style frame abandonment)

### Fix 4: Portal Readiness Check Before Diversion
**What**: Add gating check before any mining diversion: `if obsidian < 10: SKIP frame building; else: COMMIT to frame building until 10 blocks placed`
**Logic**:
- After each obsidian mine, calculate remaining count needed
- If 1-2 blocks remain, place them immediately before any other activities
- If frame is 80%+ complete, do NOT pivot to alternative tasks (flint hunting, surface exploration, etc.)
- Issue explicit [NOTE] when frame is "locked in" or when a diversion is triggered

**Harness note format example**:
```
[NOTE] obsidian inventory: 7/10; frame progress 7/10; locked in to portal completion
[NOTE] obsidian inventory: 1/10; < 2 blocks needed; proceeding to alternative mining before frame commit
```

**Estimated steps saved**: 500-2000 per run (prevents phase 1 frame abandonment by OG12, prevents OG8-style pivot-to-death)

## Summary

| Run | Duration | Outcome | Failure Type | Steps Wasted | Fix Priority |
|-----|----------|---------|--------------|--------------|--------------|
| OG9 | 8,916 | ✓ Nether entry | 1 placement retry (+118) | 118 | Fix 2 (face auto-selection) |
| OG13 | 5,302 | ✓ Nether entry (fastest) | None | 0 | N/A (reference) |
| OG8 | 1,465 | ✗ Death/loss | Early placement failure → no retry → death | ~1,465 | Fix 3 (plan collapse recovery) + Fix 4 (frame lock-in) |
| OG12 | 22,230+ | ✗ Still running; no portal | Phase 1 failure → diversion → stall | ~20,925 | Fix 1 (verification) + Fix 3 + Fix 4 |

**Cumulative cost**: (118 + 1,465 + 20,925) / 3 runs = **~7,500 steps average wasted per failed run**
**All fixes combined estimated savings**: **3,000-5,000 steps per run** (30-50% phase speedup for slow runs)

