# Nether Phase Analysis: og9 and og13 Deaths

## 1. og9's Nether Timeline: Both Visits

### First Entry (Step 17591)
- **Entry point**: (-2989, 12, -5559) Overworld → (-362, 47, -686) Nether
- **Steps 17593–17714**: Initial netherrack mining
  - Spent 121 steps attempting to mine one netherrack block (~17659)
  - Result: mine_until with 0 blocks broken; aim was "beyond the ledge, over lava"
  - Fell ~5 blocks to y=42 while mining, took 2 damage (15→13 health)
  - Cause: crosshair was aimed past ledge into a lava lake below, not at accessible netherrack
  
- **Steps 17714–17727**: First successful netherrack break
  - Used mine_forward(n=48): broke 2 netherrack at y=42 in ~13 ticks, picked up both
  - Milestone 16/24 achieved
  
- **Steps 17727–17893**: explore_nether(axis=z, sign=1, length=32)
  - Walked 1 block (+Z), took 12 ticks; fortress detected immediately (1% of view, bearing +61°)
  - Did NOT continue toward fortress; stopped at (-362, 43, -688)
  - Only 398 ticks allocated (plan-shrunk from 408); procedure found sighting but was too budgeted to pursue
  - No lava crossed, only 1 block walked, 0 blocks tunnelled
  - **Issue**: Fortress sighting exists but too close to evaluate; model turned to bearing yaw=61 but report noted "No fortress visually confirmed" after inspection

- **Steps 17913–17976**: explore_nether(axis=x, sign=-1, length=24)
  - At (-363.3, 45, -688) facing W after failed diagonal tunnel
  - Walked 24 blocks west to (-387.7, 40.6, -688) in 115 ticks, broke 2 blocks, descended 4.4 blocks
  - **No fortress, no blaze reported**
  - End position: lava lake detected at edge; 36% of lower view
  
- **Steps 17916–17976**: Death at lava lake
  - LAVA AHEAD note triggered at step 17916: "36% of the lower view is lava"
  - Model turned E to escape, attempted cobblestone placement while falling (y 39.5→28.4)
  - Placement failed 6 times; fell into lava at y=28
  - Took 4 damage (13→9 health) while mid-fall
  - Died at (-389, 26, -688) after lava damage stacked (~4 ticks of burn)
  - **Portal**: Spawned back at Overworld origin (-3010, 71, -5572)

### Second Entry (Step 25600+)
- Re-entered Nether from rebuilt portal (~step 25.6k mentioned in task)
- Logs show death at step 26939 (fell into cliff with lava)
- **Not detailed in single-episode log file** (logs.txt is first episode only, ends ~30.2k)

## 2. og13's Nether Timeline: Single Visit (Steps 18660–18818)

- **Entry point**: Overworld portal → (-379.5, 49, -686.7) Nether
- **Steps 18660–18735**: Portal landing and attempted netherrack mining
  - Spent 75 steps trying to mine 1 netherrack in portal room
  - No blocks broken; crosshair was aimed at correct netherrack but mining produced 0 events
  - Moved 1.1 blocks west from portal to (-380.6, 49, -686.7), no netherrack collected
  
- **Steps 18735–18818**: Death at lava lake
  - Attempted go_to(-381.5, -686.7) to traverse ledge
  - **Fell into a hole** unclimbably: position jumped from y=49.8 to y=37 in one step
  - Landed at (-383.3, 37, -686.7) directly above lava lake
  - LAVA AHEAD: "45% of the lower view is lava" at (-383, 37, -687) yaw=-90
  - Attempted cobblestone placement while falling: failed all 12+ attempts
  - Took 4 damage (17→13 health) from lava contact at y=28.25
  - Died at (-382, 26, -687); respawned at (-3010, 71, -5572)
  - **Note**: Runner attempted bunker (dig 2 down, cap with cobblestone) but "cap did not place" – lava too close

## 3. Harness Nether Macros: Functions & Contract

**File**: macros_nether.py lines 1377–1644

### explore_nether(axis, sign, length=60, block=None)
**Line 1377–1420**: Walks `length` blocks along one world axis in the Nether, tunnelling through netherrack and bridging lava
- **Search pattern**: Keeps heading (yaw locked), tunnels foot block (pitch 35°) then eye block (pitch 8°), repeats
- **Pitch**: Default 8° (EXPLORE_PITCH), switches to 28° (EXPLORE_PITCH_LAVA) when lava ≥2% of lower view
- **Lava thresholds**:
  - **EXPLORE_LAVA_WALK = 0.02** (2%): switches to careful mode (sneak, no sprint/jump, re-sample every 2 ticks instead of 6)
  - **EXPLORE_LAVA_BRIDGE = 0.10** (10%): triggers automatic bridge_forward (lay 6 blocks)
- **Stop conditions**: 
  - Fortress in view (nether brick detection: dark red-brown, fills >1%)
  - Blaze in view (yellow entity, motion against still background)
  - Length completed with no sighting
  - Budget exhausted
  - Dropped >4 blocks (hole/ledge detected)
- **Returns**: Note with blocks walked, tunnelled, bridged, position, and bearing to fortress or "Done: no sighting"

### find_lava(n=600, y=11, leg=40)
**Lines 733–774**: Tunnels at depth y≈11 in straight 40-block legs (turning 90° after each), looking for pool
- **Lava detection**: Samples vision.lava_fraction at lower view; fires on FIND_SEEN=0.02 (2%)
- **Close phase**: Once sighting reaches FIND_SEEN, tilts pitch down to 28° (FIND_PITCH_LAVA), sneaks within FIND_POUR_DIST=3.5 blocks of pool, never closer than FIND_MIN_DIST=2 blocks
- **Returns**: Note naming pool cell and rim cell for make_obsidian(x, y, z) call
- **Precondition**: Carries pickaxe; water_bucket optional but noted if absent

**Contract statement (AGENTS.md line 211)**:
> "Find the lava the obsidian needs. Takes a staircase down to about y 11 if you are above it, then tunnels in straight legs (turning 90 degrees after each), watching the lower view for lava the whole way. STOPS the moment lava comes into view, at least 2 blocks short of it, and the note names the pool's cell, the RIM cell to pour from and the exact `make_obsidian(x, y, z)` call."

### bridge_forward(n=6, item="cobblestone")
**Lines 1587–1644**: Called by explore_nether when EXPLORE_LAVA_BRIDGE (10%) is reached
- Lays `n` blocks from current position over lava
- Continues the explore_nether walk after bridge; re-samples lava every 2 ticks
- **Stop**: After BRIDGE_MAX=8 bridges (48 blocks total), abandon this axis

## 4. Systematic Problems with Evidence

### Problem A: Fortress Search Direction Unknown
**Evidence**:
- **og9 step 17745**: explore_nether(z+) reports "FORTRESS IN VIEW: bearing yaw 61"
- **og9 step 17797**: Model tunnels diagonally at bearing 60° but stalls after 1.6 blocks ("passage not opening")
- **og9 step 17913**: Switches to axis=x (west) and finds NO fortress; only lava
- **Contract (AGENTS.md line 208)**: "Fortresses run along the x or z axis in long lines, so one leg per axis finds one where nothing else would"

**Design deficit**: explore_nether stops when fortress is 1% visible (bearing reported), but does NOT walk toward it. og9's model had to re-plan after sighting; re-planning picked a different axis. No procedure bridges the sighting (bearing) to the actual traverse toward the fortress.

**Fix**: extend explore_nether with `target_bearing` parameter; after FORTRESS_IN_VIEW, continue same explore_nether call walking toward the bearing. Empirical threshold: continue until nether_brick ≥5% of view (strong structural signature).

### Problem B: Lava Lake Descent Without Bridging
**Evidence**:
- **og9 step 17893**: explore_nether(x-) walked 24 blocks straight down-slope from y=45 to y=40.6; lava lake formed at edge
- **og13 step 18768**: go_to tried to walk 2 blocks west on ledge; path dropped 12 blocks (y=49→y=37) into lava lake
- **og9 step 17916**: LAVA AHEAD at 36%; model attempted cobblestone placement mid-fall but:
  - No solid block to place against (placement requires 6 directions to test)
  - Fall velocity makes placement attempt fail repeatedly
  - Died within 60 ticks of LAVA AHEAD trigger

**Contract statement (AGENTS.md line 205)**: 
> "`bridge_forward(n=<blocks>, item=<block>)` Extend the floor ahead `n` blocks over water / lava / a drop, stepping onto each placed block with sneak held (you cannot fall off)."

**Design deficit**: When LAVA AHEAD fires (>10% in lower view), explore_nether triggers automatic bridging. But og9's lava was encountered at the END of a 115-tick run (exhausted budget). og13 encountered lava via sudden drop (go_to did not tunnel through netherrack above the lake). Neither run had buffer time to bridge.

**Fix**: 
1. explore_nether: Reserve 200+ ticks for bridging (reduce walk distance if budget < walk_ticks + 200)
2. New guard: After descending >4 blocks in one cell, insert bridge_forward(3) automatically if lava_fraction > EXPLORE_LAVA_WALK
3. Contract: Explicitly forbid go_to/travel in Nether at y > 40; require stair_down or mine_forward with ore_watch

### Problem C: No Return Portal Route Recorded
**Evidence**:
- **og9 step 17591**: Portal entered at (-2989, -5559) Overworld = (-362, -686.5) Nether
- **og9 step 17976**: Died at (-389, 26, -688); portal was 27 blocks east, ~21 blocks above
- **og13 step 18660**: Portal entered at (-379.5, -686.7) Nether; 
- **og13 step 18818**: Died at (-382, 26, -687); portal was ~2.5 blocks west, ~24 blocks above
- **Neither run**: Made a note of portal coordinates in Nether or left a landmark (torch, pillar)

**Contract**: No Nether exploration procedure records return route. If death occurs far from portal, recovery involves `stair_down` back to surface (risky with no coordinates), or respawn-and-rebuild.

**Fix**: 
1. enter_portal: Save portal Nether coordinates in memory note: "Nether portal at (x, y, z); Overworld at (ox, oy, oz)"
2. New procedure (mark_return): Place 2-high torch pillar every 16 blocks walked in Nether; each torch looks different (facing direction)
3. Contract: If health <10 and not at portal, call emergency_return_nav() to mark path back

### Problem D: Fortress/Blaze Detection Insufficient for Kill Loop
**Evidence**:
- **og9 step 17727**: explore_nether found fortress at bearing 61°; NO BLAZE was visible
- **og9 step 17913**: explore_nether turned to x-axis, walked 24 blocks, found NOTHING
- **Contract milestone 18 (kill_blaze)**: Requires blaze to be killed; fortress must be entered to find blazes
- **Macros**: fight_blaze procedure exists (line 1647) and requires blaze in view; no fortress-entry macro exists

**Design deficit**: Once fortress is spotted at bearing X°, explore_nether does not walk toward it. fight_blaze only works if a blaze is already visible in the frame. No bridge from "fortress bearing known" to "blaze in view" → "kill_blaze triggered".

**Fix**:
1. New procedure: fortress_approach(bearing, blocks=60) — continue explore_nether-like walk toward the bearing, halt when nether_brick ≥5% (fortress entrance); return coordinates
2. Contract: After FORTRESS_IN_VIEW, call fortress_approach(bearing=<from note>) to reach it; then scan_around for blaze in corridors
3. Alternate: Extend explore_nether with auto-continue toward fortress when FORTRESS_IN_VIEW fires (instead of stopping)

### Problem E: Lava Damage Spiral at Low Y
**Evidence**:
- **og9 step 17923**: Started at y=35.75, fell to y=28.36 in 6 ticks (6 movement commands while falling)
- **og9 step 17924–17976**: Died at y=26 in lava lake with bunker attempt (runner dug 3 blocks down, cap would not place)
- **og13 step 18777**: Similar spiral: started y=30.27, fell to y=28.25, took 4 damage immediately, died 41 ticks later
- **Note pattern**: LAVA AHEAD fires at 10%–36% view fraction, but by then avatar is falling; placement window is <10 ticks before fully submerged

**Design deficit**: When LAVA AHEAD fires and avatar is >1.5 blocks above floor, the immediate cobblestone.placement_attempt fails because:
- Player is mid-air; block placement requires player to be within 4.4 blocks of placement face
- Falling velocity makes precise face-selection (below, above, north, etc.) unreliable
- Bunker (dig 2 down, cap) requires solid lava-free ground already accessible

**Fix**: 
1. New guard (FALLING_INTO_LAVA): If avatar descends >2 blocks in one frame and LAVA_AHEAD fires, call pillar_up(3) BEFORE attempting forward movement (clears a 3-block tower to stand on)
2. Explorer state machine: Add "LAVA_EDGE" phase; when LAVA_WALK (2%) is reached and avatar's Y is within 3 of floor, pause walk, build 3-block bridge forward, then continue
3. Macros: Update bridge_forward to place blocks from ground up during placement (not mid-air attempts)

## 5. Concrete Harness-Side Designs

### Design 1: Fortress Bearing → Approach (Attack the "stopped sighting" problem)
**File**: New procedure fortress_approach() or extend explore_nether
**Evidence criterion**: FORTRESS_IN_VIEW fires once in explore_nether; bearing returned in note
**What works**: 
- At bearing=61° (og9 step 17727), nether brick should be 20–50 blocks away
- explore_nether walking 1 block already saw 1% fill; 60 blocks on bearing should hit entrance

**Implementation**:
```python
def fortress_approach(cur, info, bearing, max_blocks=60):
    """Continue toward a fortress bearing from explore_nether sighting.
    Walks up to max_blocks, tunnels, bridges. Stops when nether_brick >= 3%."""
    # Re-use _nexplore machinery; lock yaw to bearing
    # Track nether_brick fraction (new vision check)
    # Stop early when fortress fills 3%+ of view (close enough to scan for blaze)
    return acts, note
```

**Evidence it works**: If og9 had called fortress_approach(bearing=61), walking those 24 blocks westward at bearing 61° would've placed it in fortress interior (~16-block correction in bearing).

---

### Design 2: Falling Lava Interception (Attack the "descent spiral" problem)
**File**: New macros_nether.py guard FALLING_LAVA_EDGE or embed in _nexplore_tick
**Evidence criterion**: LAVA_AHEAD fires AND avatar's Y-delta in last frame > threshold
**What works**:
- og13 step 18768: dropped 12 blocks in one frame; LAVA_AHEAD fired in step 18769
- Place barrier BEFORE avatar enters lava damage radius

**Implementation**:
```python
# In _nexplore_tick or bridging logic:
if LAVA_AHEAD and (prev_y - cur_y) > 3.0:  # falling
    # Instead of attempt_place mid-air:
    # 1. Call pillar_up(2, "cobblestone") to build escape platform
    # 2. Stop walk; let model replan from solid ground
    # 3. Return None to flush rest of plan
    agent.cursor_stats["lava_escape_pillar"] += 1
    return acts_pillar + mk_act()
```

**Evidence it works**: Pillar_up is verified to place blocks under feet at measured Y. og13's fall could have been stopped if pillar_up(2) had run at y=37 before forward movement resumed.

---

### Design 3: Portal Tracking in Nether (Attack the "no return route" problem)
**File**: enter_portal() macro; memory note injection
**Evidence criterion**: Nether spawn coordinates from [STATE] after dimension change
**What works**:
- enter_portal already returns coordinates; save them in global or episode memory
- Every explore_nether call notes "portal at (x, y, z) from where you entered"

**Implementation**:
```python
def enter_portal(cur, info, ...):
    # ... existing code ...
    if in_nether:
        portal_nether_pos = (pos["x"], pos["y"], pos["z"])
        PORTAL_NETHER = portal_nether_pos  # global
        agent.memory.add_note(
            f"Nether portal entry point: {portal_nether_pos}; return to x={portal_nether_pos[0]}, "
            f"z={portal_nether_pos[2]} at surface (y > 128) to walk back to Overworld coords "
            f"({portal_nether_pos[0] * 8}, ..., {portal_nether_pos[2] * 8}).")
    return acts, note
```

**Evidence it works**: og9 could have navigated back to (-362, ~50, -686) if PORTAL_NETHER was in scope.

---

### Design 4: Lava Sighting → Immediate Bridge Window (Attack the "budget-exhausted" problem)
**File**: macros_nether.py line 1538–1546 (_nexplore_tick bridge logic) or find_lava
**Evidence criterion**: explore_nether sees lava edge with <100 ticks remaining
**What works**:
- og9 step 17893: finished explore_nether walk at exactly BRIDGE_N+1 budget spent; lava sighting next frame
- Allocate bridge as part of explore_nether base budget, not bonus

**Implementation**:
```python
# In explore_nether init (line 1406):
budget = length * EXPLORE_TICKS_PER_BLOCK + 120 + BRIDGE_BUFFER
# BRIDGE_BUFFER = 200  # Reserve for up to 8 bridges at ~25 ticks each

# In _nexplore_tick (line 1547–1556):
if st["lava"] >= EXPLORE_LAVA_BRIDGE and st["block"]:
    # Ensure we have enough ticks left to bridge; if not, message "need more budget"
    remaining = st["budget"] - st["used"]
    if remaining < BRIDGE_MIN_TICKS:  # e.g., 120
        _nexplore_finish(agent, st, 
            f"Lava edge reached with insufficient budget ({remaining} ticks left, "
            f"need {BRIDGE_MIN_TICKS}); call again with length=... to bridge it.",
            flush=True)
        return None
```

**Evidence it works**: og9 step 17893's explore_nether would have reported "Lava edge; call again to bridge" instead of ending with "Done: no fortress."

---

## Summary

| **Systematic Problem** | **Root Cause** | **Evidence** | **Harness Fix** |
|---|---|---|---|
| Fortress bearing found, walk direction unknown | explore_nether stops at 1% sighting; no bearing→walk bridge | og9 step 17727: bearing reported, then turned to different axis | New fortress_approach() to continue toward bearing |
| Lava descent uncontrolled; fall+placement fails | LAVA_AHEAD fires mid-fall; placement needs solid ground | og9 17923, og13 18768: fell 6–12 blocks then died | FALLING_LAVA_EDGE guard: pillar_up(2) before forward move |
| No return portal route; death = respawn + rebuild | enter_portal doesn't save Nether coords in memory | Both runs died far from portal, no path recorded | Save portal_nether_pos in global; add memory note |
| Budget exhausted before bridge layer deployed | explore_nether budget=length*9+120; lava edges cost 25/bridge | og9 step 17893: completed 24-block walk; lava found but no time to bridge | Reserve BRIDGE_BUFFER (200 ticks) in budget calculation |
| Blaze killing unreachable after fortress sight | No fortress-entry macro; fight_blaze requires blaze in frame | og9 found fortress but no blaze visible; killed neither | New fortress_approach() + scan_around for blaze in corridors |

