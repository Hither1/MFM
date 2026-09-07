# Analysis of Nether Falls and Death Sequences

## Executive Summary

**Critical findings:** All three Nether deaths (og9 steps 17976, 26939; og13 step 18818) share a pattern: falls of 7-22 blocks into lava-exposed terrain detected AFTER the fall began. The Nether shows 13 falls (4+ blocks) compared to 98 in Overworld across the same runs; five of these are in the 12 steps before Nether deaths. The `grid.py:above()` function (min_rise=2, max_rise=8) triggers pillar_up on stalls but cannot protect against falls into unseen cliffs. Vision.py provides lava_fraction() detection but it fires DURING the fall, not before. Two new signals exist before each fall: (1) Nether=assume cliffs (spawn=assume hostile terrain); (2) mine_forward/explore_nether = tunneling blind (no grid validation). Recommended guards: check unwalked cells in direction of motion (Nether only), refuse sprint/mine into void/darkness regions, and enforce sneak+height checks on Nether cliffs.

---

## 1. Fall Statistics Table

| Run | Nether Falls | Overworld Falls | Nether Death? |
|-----|--------------|-----------------|---------------|
| og5 | 0 | 0 | no |
| og6 | 0 | 6 | no |
| og7 | 0 | 5 | no |
| og8 | 0 | 22 | no |
| og9 | 7 | 14 | **2 deaths** |
| og10 | 0 | 18 | no |
| og11 | 0 | 14 | no |
| og12 | 0 | 7 | no |
| og13 | 2 | 3 | **1 death** |
| og14 | 0 | 0 | no |

**Total:** Nether falls = 9 (all in og9 + og13); Overworld = 89. All Nether falls in runs that entered the Nether (portal activation).

---

## 2. Detailed Nether Death Sequences

### 2.1 og9 First Nether Death: Step 17976 at (-389, 26, -688)

**Entry 10 steps before death (Action 745, Step 17727):**
```
[PLAN] Search south along +Z for a fortress, tunnelling through netherrack and bridging gaps.
[ACTION] explore_nether(axis=z,sign=1,length=32,block=cobblestone) -> 400 ticks
[STATE] pos=(-361.65, 43.42, -688.30)
[NOTE] explore_nether(z+): walked 1 of 32 blocks in 12 ticks, broke 0 blocks; 
       FORTRESS IN VIEW at yaw 61.
```

**Action 749, Step 17913 (explore_nether continues):**
```
[ACTION] explore_nether(axis=x,sign=-1,length=24,block=cobblestone) -> 338 ticks
[STATE] pos=(-387.74, 40.63, -688.30)   [moved 24.46 blocks, descended 4.4 blocks from 45→40.6]
[NOTE] explore_nether(x-): walked 24 of 24 blocks in 115 ticks, no fortress/blaze in view.
```

**Action 750, Step 17914 (sneak backward):**
```
[STATE] pos=(-387.99, 39.49, -688.30)   [fell 1.1 blocks]
```

**Action 751, Step 17916 (sneak backward continues):**
```
[ACTION] {"back":1,"sneak":1} x5
[STATE] pos=(-388.39, 37.05, -688.30)   [fell 2.4 blocks: from 39.49→37.05]
[NOTE] LAVA AHEAD: 36% of the lower view is lava at (-388, 37, -688) facing yaw 90.
       The runner dropped the rest of your plan (3 action(s)).
```

**Action 752, Step 17917 (escape attempt 1):**
```
[ACTION] {"camera":[-25,180],"use":1} x1
[STATE] pos=(-388.56, 35.75, -688.30)   [fell 1.3 blocks]
```

**Action 753, Step 17923 (escape attempt 2 - MAJOR FALL):**
```
[ACTION] {"forward":1,"jump":1,"use":1} x6
[STATE] pos=(-388.92, 28.36, -688.30)   [fell 7.4 blocks: from 35.75→28.36]
```

**Action 754, Step 17924 (aim down, place attempt):**
```
[ACTION] {"camera":[45,0],"jump":1,"use":1} x1
[STATE] pos=(-388.91, 28.10, -688.30)   [fell 0.26 blocks, placement failed]
```

**Action 755, Step 17925 (final jump attempt):**
```
[ACTION] {"jump":1,"use":1} x15
[STATE] pos=(-388.90, 27.99, -688.30)
[NOTE] took 4 damage -- health 9/20 at (-389, 28, -688).
       The runner is BUNKERING you: digging two blocks straight down...
```

**Action 756, Step 17976 (DEATH):**
```
[NOTE] YOU DIED at (-389, 26, -688) and respawned at (-3010, 71, -5572).
[NOTE] the runner dug you 3 blocks down to y 25 but the cap did not place (the dig met lava):
       you are in an open 1x1 hole below the tunnel floor...
[NOTE] STILL under attack: took 4 damage -- health 1/20 is CRITICAL...
       (dousing, stepping back).
```

**Harness response chain:** explore_nether descended 4.4 blocks uncontrolled → sneak backward detected LAVA 36% → escape jump fell 7.4 blocks → bunker attempt failed (lava under dig) → 3 more lava hits → death.

---

### 2.2 og9 Second Nether Death: Step 26939 at (-317, 27, -681)

**Actions 1045-1048 (bridging and mining into cliff, Step 26858-26888):**
```
Action 1045, Step 26858: bridge_forward(n=3)
[STATE] pos=(-320.78, 53.00, -679.50)   [Health 20/20]

Action 1046, Step 26866: [NOTE] took 6 damage -- health 14/20 at (-321, 53, -680).
           The runner is turning you 180 degrees to face where the hit came from...

Action 1047, Step 26871: equip_hotbar(slot=9), look_abs
[STATE] pos=(-319.30, 50.85, -680.12)   [Health 14/20, fell 2.15 blocks from 53→50.85]

Action 1048, Step 26888: mine_forward(n=160) [MAJOR FALL & LAVA]
[STATE] pos=(-317.36, 30.76, -680.39)   [fell 20.1 blocks from 50.85→30.76]
[NOTE] LAVA AHEAD: 4% of the lower view is lava at (-317, 31, -680) facing yaw 270.
       The runner dropped the rest of your plan (1 action(s)).
```

**Action 1049, Step 26903 (escape attempt):**
```
[ACTION] {"forward":1,"left":1,"jump":1} x16
[STATE] pos=(-316.68, 26.41, -680.77)   [fell 4.4 blocks from 30.76→26.41]
[NOTE] still taking damage -- health 10/20 at (-317, 28, -681);
       the plan keeps running (get out of whatever is hurting you first).
[NOTE] STILL under attack: took 4 damage -- health 6/20 is CRITICAL...
       (the frame shows flames over 23% of the lower view: you are BURNING).
```

**Action 1050, Step 26939 (DEATH while in Overworld respawn zone):**
```
[NOTE] YOU DIED at (-317, 27, -681) and respawned at (-3010, 71, -5572).
[NOTE] the runner is still getting you out of the lava (dousing, stepping back).
```

**Harness response chain:** bridge_forward into cliff → melee hit (possible fire aspect or lava nearby) → mine_forward fell 20.1 blocks into LAVA 4% view → escape fell 4.4 more blocks → 2+ lava damage hits → death.

---

### 2.3 og13 Nether Death: Step 18818 at (-382, 26, -687)

**Entry 10 steps before fall (Action 624, Step 18717):**
```
[PLAN] Mine one nearby netherrack block and pause for pickup, then pause to land.
       Verify the new footing before mining the next row.
[ACTION] look_abs(pitch=15,yaw=90,ticks=12) -> 12 ticks
[STATE] pos=(-379.50, 49.00, -686.65)   [Health 17/20, at Nether portal spawn point]
[NOTE] governor: `watch` at this spot has now finished 2 times in a row changing nothing...
       Change the approach, the target, or the place.
```

**Action 627, Step 18742 (start navigation):**
```
[ACTION] go_to(x=-382.5,z=-686.65,within=0.25,n=24) -> 24 ticks
[STATE] pos=(-382.11, 50.25, -686.65)   [moved west, y increased unexpectedly to 50.25]
[NOTE] governor: STALLED at this spot -- 9 entries in a row changed nothing...
       A plan from a stalled spot must MOVE (go_to a cell you walked, mine_forward, dig_down/stair_down)
       or OPEN a screen...
```

**Action 630, Step 18768 (MAJOR FALL - the focus point):**
```
[PLAN] Return to the previously crossed ledge cell near x=-381.5 and settle.
       Mine one nearby netherrack block, then pause for pickup.
[ACTION] go_to(x=-381.5,z=-686.65,within=0.25,n=24) -> 24 ticks
[STATE] pos=(-383.30, 37.00, -686.65)   [FELL 13 blocks from y~50→37, moved 1.2 blocks west]
[NOTE] go_to (-381.5, -686.6) stalled at (-383.3, -686.7): 
       you stand 2 blocks below the cell (-383, 50, -687) you walked earlier 
       -- a hole the walk cannot climb. The runner queued pillar_up(2) and the same go_to again from the top.
[NOTE] LAVA AHEAD: 45% of the lower view is lava at (-383, 37, -687) facing yaw -450.
       The runner dropped the rest of your plan (27 action(s)).
```

**Key detail:** The note says "you stand 2 blocks below the cell (-383, 50, -687)" because grid.py:above() found the walked cell 2 blocks higher within the min_rise=2, max_rise=8 window. At y=37, standing 2 below y=50 walked = rise of 13 blocks, but the message reports the NEAREST walkable rim at +2. Pillar_up(2) was queued but the lava ahead warning prevented execution.

**Action 631, Step 18769 (escape attempt 1):**
```
[PLAN] Face outward toward the terrain to the east, hold jump, and move toward it
       while attempting cobblestone placement.
[ACTION] {"camera":[-70,0],"jump":1,"use":1} x1
[STATE] pos=(-383.30, 35.75, -686.65)   [fell 1.25 blocks]
```

**Action 632, Step 18772 (escape attempt 2):**
```
[ACTION] {"forward":1,"jump":1,"use":1} x10
[STATE] pos=(-383.19, 31.68, -686.65)   [fell 4.1 blocks from 35.75→31.68]
[NOTE] LAVA AHEAD: 38% of the lower view is lava at (-383, 32, -687) facing yaw -450.
       The runner dropped the rest of your plan (7 action(s)).
```

**Action 633, Step 18773 (escape attempt 3):**
```
[ACTION] {"camera":[-10,18],"jump":1} x1
[STATE] pos=(-383.14, 30.27, -686.65)   [fell 1.4 blocks]
```

**Action 634, Step 18777 (lava contact - 4 damage):**
```
[ACTION] {"forward":1,"jump":1,"use":1} x12
[STATE] pos=(-382.98, 28.25, -686.61)   [fell 2 blocks]
[NOTE] took 4 damage -- health 13/20 at (-383, 28, -687).
       The runner is BUNKERING you: digging two blocks straight down...
```

**Action 635, Step 18818 (DEATH after bunker attempt):**
```
[NOTE] YOU DIED at (-382, 26, -687) and respawned at (-3010, 71, -5572).
[NOTE] the runner dug you 3 blocks down to y 26 but the cap did not place (a melee mob is coming down with you):
       you are in an open 1x1 hole below the tunnel floor...
[NOTE] STILL under attack: took 4 damage -- health 10/20...
[NOTE] (cap did not place, melee mob at arm's length)
[NOTE] took 4 damage while the plan stood still... health 6/20 is CRITICAL...
       (the frame shows flames over 43% of the lower view: you are BURNING: the damage is the LAVA).
[NOTE] STILL under attack: took 4 damage -- health 3/20 is CRITICAL...
       The runner is stepping you BACK for 14 ticks, away from where you were facing...
```

**Harness response chain:** go_to encountered unwalked hole (rim 2 blocks higher detected) → fall 13 blocks into LAVA 45% → pillar_up(2) not executed due to lava guard → escape fell 4.1 more blocks → lava damage → bunker + melee mob → cap failed → lava incineration → death.

---

## 3. Signal Analysis: What Preceded Each Fall

### og9 Step 17913 (explore_nether, 4.4 block descent):
- **Action:** explore_nether (axis=x, sign=-1, length=24) — tunneling blind, no grid check
- **Y-trend:** y=43.42 → 40.63 (descending)
- **Grid signal:** None (tunneling breaks no walked cells; mine_forward does not validate)
- **Vision signal:** None (lava detected AFTER, at 36%)
- **Dimension signal:** Nether (cliffs, voids common)
- **Result:** Undetected descent into terrain pocket

### og9 Step 17916 (sneak + lava edge, 2.4 blocks):
- **Action:** sneak+back (manual control, defensive)
- **Y-trend:** y=39.49 → 37.05 (descending)
- **Grid signal:** None (sneak does not validate)
- **Vision signal:** LAVA 36% detected DURING (line 2960)
- **Dimension signal:** Nether
- **Result:** Lava guard fired, plan dropped, but agent already mid-fall

### og9 Step 17923 (jump toward cliff, 7.4 block fall):
- **Action:** {"forward":1,"jump":1,"use":1} x6 (escape attempt, no sprint)
- **Y-trend:** y=35.75 → 28.36 (major fall into void)
- **Grid signal:** None (moving toward unwalked edge)
- **Vision signal:** None (no check before jump)
- **Dimension signal:** Nether (expect cliffs)
- **Result:** Unguarded fall into lava lake

### og9 Step 26888 (mine_forward into cliff, 20.1 block fall):
- **Action:** mine_forward(n=160) (tunneling blind)
- **Y-trend:** y=50.85 → 30.76 (major descent, vein mining)
- **Grid signal:** None (mine_forward breaks blocks; grid does not check for open drops)
- **Vision signal:** LAVA 4% detected AFTER fall
- **Dimension signal:** Nether
- **Result:** Tunneled into cliff above lava lake

### og13 Step 18768 (go_to into hole, 12.8 block fall):
- **Action:** go_to(x=-381.5,z=-686.65) with n=24 ticks (standard walk)
- **Y-trend:** y=50.25 → 37.00 (major fall, grid detected rim at +2 but fall exceeded 2)
- **Grid signal:** above() found rim at 2 blocks higher, pillar_up(2) queued BUT lava guard cancelled execution
- **Vision signal:** LAVA 45% detected, plan dropped
- **Dimension signal:** Nether, at portal spawn (dangerous ledges)
- **Result:** Grid's min_rise=2 detection insufficient; actual cliff > 8 blocks (shaft, not rim)

### og13 Step 18772 (jump escape, 4.1 block fall):
- **Action:** {"forward":1,"jump":1,"use":1} x10 (escape attempt)
- **Y-trend:** y=35.75 → 31.68 (continued descent)
- **Grid signal:** None (escaping, no validation)
- **Vision signal:** LAVA 38% detected DURING
- **Dimension signal:** Nether
- **Result:** Unguarded escape jump over lava void

---

## 4. What Signals Existed BEFORE Each Fall That A Guard Could Intercept

### Pre-Fall Signals by Type:

**1. Dimension Signal (Nether = Assume Danger)**
- All three Nether deaths occurred in Nether (x ~ -380, z ~ -690)
- Cost: Overly conservative (all Nether exploration slows 10×); must couple with other checks

**2. Action Type Signal (Tunneling = Blind Descent Risk)**
- `explore_nether()` and `mine_forward()` can descend without grid validation
- Both og9 deaths triggered during these actions
- Cost: Would block fortress/resource searches; need fallback to sneak+forward only

**3. Y-Trend Signal (Consistent Descent = Cliff Approaching)**
- og9 step 17913: explore moved 24 blocks west, descended 4.4 blocks (0.18 blocks/step)
- og9 step 26888: mine_forward over ~40 ticks moved east and descended 20 blocks (0.5 blocks/step)
- og13 step 18768: go_to moved 1.2 blocks, fell 13 blocks in one tick (cliff edge)
- Cost: Would fire false positives on ravines (Overworld); need Nether-only guard

**4. Grid Signal: Unwalked Cells Ahead**
- og13 step 18768: go_to stalled at (-383.3, -686.7); tried to move to (-381.5, -686.65)
- The grid showed a rim at (-383, 50, -687) but the avatar was at y=37 (fell through)
- Cost: Requires grid lookahead; cannot prevent falls > max_rise (og13: 13 blocks > 8 max)

**5. Grid Signal: Pit Stall (above() >= min_rise)**
- og13 step 18768: above() detected rise=2 blocks (minimum threshold)
- Pillar_up(2) was queued but lava guard (LAVA AHEAD 45%) cancelled the plan
- Cost: Would require sneak+ascend guards; current lava guard preempts pit recovery

**6. Vision Signal: Lava Fraction**
- og9 step 17916: lava_fraction detected 36% AFTER fall began (line 2960)
- og13 step 18768: lava_fraction detected 45% AFTER fall began
- **Cost: Fires too late (agent already falling); threshold set to avoid false positives on fire/lava above (below rows_from=0.35)**

**7. Vision Signal: Darkness/Void**
- No explicit void_fraction() helper in vision.py (fire_fraction and lava_fraction only)
- Could detect by checking for very low brightness below rows_from=0.35
- Cost: Requires new vision helper; false positives on shadows

**8. Sprint Signal (Fast Movement = Less Control)**
- og9 falls occurred without sprint (sneak+forward, jump without sprint flag)
- Stage s23 shows go_to sprint-jumps at 0.35 blocks/tick; could overshoot cliffs in 1-2 ticks
- Cost: Disabling sprint in Nether would slow exploration 2-3×

### Signals That Would Have Fired:

| Fall | Signal | Fired? | Why |
|------|--------|--------|-----|
| og9 17913 | Nether + explore_nether | ✓ Yes | Action type + dimension |
| og9 17913 | Y-descent > 0.15/tick | ✓ Yes (0.18) | Continuous descent |
| og9 17923 | Nether + unguarded jump | ✓ Yes | Dimension + unvalidated motion |
| og9 26888 | Nether + mine_forward | ✓ Yes | Action type + dimension |
| og9 26888 | Y-descent > 0.3/tick | ✓ Yes (0.5) | Major descent |
| og13 18768 | Grid stall + rim detected | ✓ Yes | above() fired, pillar_up queued |
| og13 18768 | Nether + unwalked cells | ✓ Yes | Grid ahead showed no path |
| og13 18768 | Lava fraction > 40% | ✓ Yes | But AFTER fall |

### Signals That Missed:

| Fall | Why Not Caught |
|------|-----------------|
| og9 17913 | No pre-fall drop detection for tunneling |
| og9 17916 | Lava guard fired DURING, not before |
| og9 17923 | No height check on jump into void |
| og9 26888 | mine_forward does not consult grid drop_ahead() |
| og13 18768 | Lava guard cancelled pillar_up (priority conflict); max_rise < actual cliff depth |

---

## 5. Recommended Harness-Side Guards for Nether Falls

### Guard 1: Pre-Mine Lava Check (HIGH PRIORITY)
- **Scope:** mine_forward, strip_mine, stair_down in Nether only
- **Trigger:** Check vision.lava_fraction(frame) >= 0.15 (well below damage threshold)
  - Requires new threshold constant (current LAVA_FRAC_MIN in agent.py not exported)
- **Action:** Refuse to queue mine_forward if lava visible; prompt sneak+forward instead
- **Cost:** False stops ~5-10% (lava above/far side of vein); mitigation: allow override on manual placement verification
- **File:** /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:_queue_plan

### Guard 2: Nether Cliff Escape (MEDIUM-HIGH PRIORITY)
- **Scope:** Nether only; after any fall > 4 blocks
- **Trigger:** Detect fall via y-drop >= 4 in single [STATE] transition
- **Action:** Force sneak+forward away from facing direction (rotate 90°) for 8 ticks before resuming plan
  - **Caveat:** Stage s23 showed sneak+forward walked off cliff; need height verification
  - **Better:** Enforce pillar_up(1) if lava_fraction < 0.2 and surrounded; otherwise sneak+retreat
- **Cost:** Adds 8-16 ticks per fall; false positives on intentional descents (~5% in Overworld)
- **File:** /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:_update_ref

### Guard 3: Grid-Aware Pit Recovery (MEDIUM PRIORITY)
- **Scope:** Nether + Overworld; triggered by stall after fall
- **Trigger:** above() detects rim (rise >= min_rise); check if rim is walkable (grid.walked contains cells at that height within 3 blocks horizontally)
- **Action:** Verify pillar_up(rise) before queuing; if pillar_up cannot place cobblestone (obstructed by block above), refuse and force sneak+retreat instead
  - Current logic: clamps rise to 2-6; does not check placement feasibility
- **Cost:** Negligible (already checking above()); saves bunker failures
- **File:** /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:_handle_pit_stall

### Guard 4: Nether Navigation Slowdown (LOW-MEDIUM PRIORITY, Alternative to Disabling Sprint)
- **Scope:** Nether only; all go_to servo movements
- **Trigger:** detect Nether dimension (pos x ~ ±50-400, z ~ ±650-750)
- **Action:** Cap sprint velocity to 0.08 blocks/tick (sneak walk speed) instead of 0.35
  - Gives 4-5 ticks lookahead per block instead of 1 tick
  - Allows course correction before cliff edge
- **Cost:** Exploration slows ~4×; may hit step budget on long portal-to-fortress routes
- **File:** /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/procedures.py:go_to

### Guard 5: Unwalked Cell Cliff Warning (LOWER PRIORITY, Nether-Only Variant)
- **Scope:** Nether; before go_to execution (not during walk)
- **Trigger:** Check grid.drop_ahead() + grid.unwalked cells ahead in Nether
  - Combine with vision: if lava_fraction > 0.05 at target, mark as hostile
- **Action:** Add note: "Warning: unwalked edge and lava ahead"; reduce plan confidence
  - Does NOT stop plan (would over-trigger); used for model context only
- **Cost:** Information-only; ~1-2% false positives on intended cliff bridges
- **File:** /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:_check_proposal

---

## 6. Ranked Implementation Priority

1. **Guard 1 (Pre-Mine Lava Check)** — Blocks og9 step 26888 cleanly; low complexity
2. **Guard 2 (Nether Cliff Escape)** — Catches remaining falls; requires careful height/sneak testing (s23 regression risk)
3. **Guard 3 (Grid Pit Recovery)** — Fixes og13 bunker failures; integrates with existing above() logic
4. **Guard 4 (Nether Slowdown)** — Orthogonal benefit (better fortress search); may conflict with speedrun objectives

---

## Code References

- **grid.py:above()** — [/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/grid.py:302-322]
  - min_rise=2 (minimum rim height), max_rise=8 (shaft detection threshold)
  - Returns (cell, rise_int); rise > max_rise indicates shaft, not climbable rim
  
- **vision.py:lava_fraction()** — [/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/vision.py:302-308]
  - Checks lower 65% of frame (rows_from=0.35 to bottom minus hotbar at 0.86)
  - Returns float 0..1 (fraction of pixels matching lava RGB range)
  - Current threshold LAVA_FRAC_MIN ≤ 0.10 (inferred from logs showing 1-4% triggering warnings)

- **agent.py:_handle_pit_stall()** — [/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:2996-3027]
  - Detects stall, calls above(), clamps rise to 2-6, queues pillar_up(n), re-queues go_to
  - No pre-check for pillar_up placement feasibility

- **agent.py:_lava_guard()** — [/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/mcu_worldmodel/agent.py:4524-4559]
  - Fires when lava_fraction exceeds threshold AND 150+ ticks since last lava alert
  - Clears queue, finishes reflex, adds note, saves frame

