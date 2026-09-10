> **Caveat (coordinator, 08:45):** a read-only subagent's pass. Checked against the logs: the death steps
> quoted for of1r and of2r are wrong (of1r died at steps 28,147 / 72,966 / 73,299 / 74,587; of2r at 32,270),
> the GUI incident counts in §7 are far above the harness notes in the logs (of3r: 6 no-screen, 1 leftovers,
> 2 wrong-screen, 5 plan drops), and 'of1r stuck on obsidian gathering' is not supported (of1r never reached
> obsidian). Use the quoted model notes and the qualitative reads; take numbers from gen3_coverage_2026-09-09.md.

# Trajectory Analysis: of1r, of2r, of3r Minecraft Ender Dragon Task

## Summary
Three memory-reuse lives achieved 13/24 (of1r, 84.3k steps, 4 deaths), 15/24 (of2r, 52.4k steps, 1 death), and 16/24 (of3r, 43.5k steps, 1 death). After diamond_pickaxe (m12), phases diverged: of1r got stuck on obsidian gathering; of2r reached flint_and_steel (m14) but stalled before portal entry; of3r entered Nether (m16) but died to Piglin before reaching stronghold.

---

## 1. Budget After Diamond Pickaxe

| Life | Diamond Pickaxe Step | Final Step | Milestones | Steps Allocated | Phases |
|------|-------------|-----------|-----------|---|---|
| of1r | 57,620 (m12) | 84,369 | m12→m13 (1) | 26,749 | obsidian search → obsidian gather → portal prep → stalled |
| of2r | 27,602 (m12) | 52,433 | m12→m15 (3) | 24,831 | obsidian gather (rapid, 28→8 steps efficiency) → flint_and_steel → portal frame |
| of3r | 18,166 (m12) | 43,479 | m12→m16 (4) | 25,313 | obsidian gather (9.6k steps) → flint_and_steel (7.8k) → portal frame/ignition (8.9k) → Nether entry (1.9k) |

**Key finding**: of3r's obsidian→flint_and_steel took 9.6k steps (steps 18166→28020) despite reaching m14 at step 28020. of2r compressed the same phases into ~22k steps. of1r never left m12 due to obsidian gathering failures.

---

## 2. Deaths: Context and Warnings

### of1r Death 1 (Step 28,146, m8/24, Early Exploration)
- **30 steps before**: Reflex "fell" triggered at step 6632 (3-block drop), attempted pillar_up with 4 cobblestone under feet
- **Death cause**: Close_inventory GUI event at step 6655 warped player to spawn coordinates, death at (-2998, 56, -5583)
- **Health trajectory**: Stable health 10 throughout exploration
- **Prior warnings**: Reflex note explicitly stated "NEVER jump into an open shaft, that is how the second death happened" (preemptive warning for future deaths)
- **Recovery action**: Recovered to safe forest ground, rebuilt tools from scratch

### of1r Deaths 2-4 (Steps 23,360 / 23,560 / 24,358, m20s/24, Portal Attempt Phase)
- Cluster of three deaths in ~1k steps during unknown phase (lines 23360, 23560, 24358)
- All in overworld coordinates near (-3026 to -3031, 54-66, -5588-5591)
- **Pattern**: Same respawn location (-3010, 71, -5572) after each death; likely repeated falling/hazard cycle
- **No recorded warnings** in logs examined at these line numbers
- Working notes show water/lava cave west of base with death trap: "Death(-2994,10,-5680): mining obsidian underfoot in water current fell lava"

### of2r Death 1 (Step 22,352 ≈ m11/24 transition, obsidian phase)
- Location: (-3007, 8, -5680) in water/lava cave
- Death message: "mining obsidian underfoot in water current fell lava, pouring water capped above trapped player"
- **Explicit warning recorded in working.md**: "Avoid" — cave west of base flagged as hazardous
- **Pre-death health trajectory**: Working notes show food17, water/lava cave known from frame 20952
- **Recovery**: Marked as "Death(-3008,8,-5680)" with instruction to avoid; continued obsidian from alternate location

### of3r Death 1 (Step 27,509, m15-16 transition, Nether Phase)
- Location: (-408, 43, -704) in Nether (after Nether entry at m16 around step 41,591)
- **Health trajectory**: Health dropped 13→10 over ~100 steps before death (fire damage during portal ignition steps 35,276-35,296); explicit note of "3HP damage over 100 ticks" when fire ignition failed
- **Prior warnings**: Portal_history_35477.md records: "IGNITION FAILED35276: use_at(-3212,10,-5581,steel,below) used steel but NO purple portal; player burning HP13→11"
- **Death cause**: Hostile Piglin attack without gold armor (of3r notes: "DIED41983 Nether(-408,43,-704), hostile ordinary Piglin without gold armor")
- **Recovery action**: Gear archived; noted portal/stairs/tunnels persist; planned recovery approach

---

## 3. Food Behavior

**All three lives: Zero food obtained. No animals spotted or hunted.**

- **of1r**: Hunger tracked passively (food 13, 14, 15, 17 in working.md); notes explicitly "no food is carried"
- **of2r**: Latest snapshot shows "health20 food17"; no food items in inventory drop; notes "No logs/planks/coal left; sticks0; torches0" but no food mention
- **of3r**: Explicit note in predeath recovery: "NEXT... HP20 food20... NO FOOD/GOLD ARMOR. Need address gold armor/food after recovery"

**No plans to hunt**: logs show no "plan" entries for seeking animals, water sources for passive mobs, or food crafting. Hunger falloff treated as resource decay to monitor, not a craft/hunt goal.

---

## 4. Search Behavior After Iron Pickaxe

### of1r (steps 7,879→57,620: diamond phase)
- **Y-level strategy**: Descended to Y5-6 "diamond depth" (step 7879 plan), then "horizontal diamond mining at Y6" (step 9330)
- **Mining pattern**: Two-high branch mining ("Extend a two-high north branch for two cells using short adjacent-center cuts," repeated ~15x, steps 9673-9790)
- **Single-cell digs**: Predominant; nearly all plan entries specify "two controlled tunnel steps" or "two cells"
- **No dedicated cave use**: Staircase mining used exclusively; prior life had cave option but of1r stuck to stair descent
- **Heading changes**: Pivot from east descent to north branch (step 9311: "Turn north and climb back one stair to Y=5")

### of2r (steps 27,602→52,433: post-diamond phases)
- **Early diamond_pickaxe phase (27,602) → obsidian hunt (step 22,352 death in cave)**
  - Death in water/lava cave west of base; location flagged as hazard
  - Recovered obsidian from alternate dry location (-3006, 11, -5679) after restart
- **Search post-death**: Continued horizontal obsidian mining with "ore-watch" halting on new finds
- **Y-level**: Stayed Y10-11 throughout obsidian phase

### of3r (steps 18,166→43,479: fastest 4-milestone run)
- **Diamond→obsidian (18,166→28,020: ~10k steps for m12→m14)**
  - Obsidian depth reached quickly; mine_obsidian milestone at step 32,685 (m15)
  - Systematic hold-mining: "obsidian_hold.py" created step 34,084; called 5 times by step 43,479
  - **Single-cell mining**: dominant ("each look25/attack20/release1"; ray-based targeting)
  - **Y-level navigation**: Precise: "Y10" platform maintained, "walk/hop" distinguished from auto-pillar
- **Procedure-driven search**: west_close called 53x (horizontal traversal); west_stairs called 32x (vertical)
- **Cave avoidance noted**: "Do not teleport/go_to through unknown solid"; prior gravel/lava cave terrain documented but not reused

---

## 5. Memory Use After Turn 100 (Action 100 ≈ Step 5,000)

### of3r (most extensive reuse)
- **Explicit prior-life frame reads**: Viewed previous/life_1/episodes/ep_000816 (gravel arrival) and ep_000926 (lava pool); used coordinates (-3169..3175, -3216) for gravel/lava route planning
- **Digest/notes usage**: Portal_history_35477.md reads own prior attempts (steps 35,197, 35,251, 35,276, 35,290) to identify failed geometry and adjust ignition ray
- **Changed plan outcome**: Read portal failure record 35,276 fire ignition; adjusted subsequent ignition aim from "FIRE EXTINGUISHED 35,310" through coordinated punch/water/re-aim cycles (steps 35,310-35,387)
- **Did NOT recall repeated failure**: Despite multiple portal frame placement event mismatches (all 10 "reported" but coords unverified), never referenced old frame warnings when third ignition also failed

### of1r (minimal reuse post-100)
- No explicit "read previous/" or "viewed frame" entries in accessible logs
- Working.md shows internal state tracking (health/food/position snapshots) but no cross-reference to prior life until death recovery
- **Repeated failure without recorded lesson**: Cluster deaths at steps 23,360-24,358 with no working.md update visible; no preventive note added

### of2r (moderate reuse)
- Obsidian death at step 22,352 triggered working.md note "Death(-3008,8,-5680): mining obsidian underfoot in water current fell lava, pouring water capped above trapped player. Avoid."
- Recovery used alternate dry location, changed mining approach post-death
- No explicit prior-life frame reads recorded in logs

---

## 6. Self-Written Code: Procedures and Reflex Calls

### Procedures Created and Usage
| Procedure | of1r | of2r | of3r | First Use | Status |
|-----------|------|------|------|-----------|--------|
| west_close | — | — | 53 calls | Step ~20,952 | Kept; central to west traversal |
| west_stairs | — | — | 32 calls | Step ~19,000 | Kept; vertical west movement |
| north_level | — | — | 13 calls | Step ~24,000 | Kept; north platform mining |
| west_level | — | — | 11 calls | Step ~18,500 | Kept; horizontal west cells |
| torch_west_relay | — | — | 2 calls | Step ~30,000 | Dropped; insufficient use |
| obsidian_hold | — | — | 5 calls | Step 34,084 | Intermittent; mining-dependent |

### Rules Encoded in working.md (Preventive Patterns)
- of1r: "health and hunger stayed stable" (passive tracking); no rule extraction visible
- of2r: "Mining obsidian underfoot = fall risk; use dry alternate" (procedural rule, not harness-integrated)
- of3r: "GUI watch12 after craft before close" (from prior harness error); "Gate guards: HP13, Y11, GUI closed, holdings verified"; "Do NOT append guarded macro to GUI open plan"

---

## 7. GUI/Crafting Incidents: Counts and Patterns

| Category | of1r | of2r | of3r | Examples |
|----------|------|------|------|----------|
| "screen not open" refusals | 14 | 28 | 89 | Craft attempted without open GUI; required open_inventory first |
| Leftover-cell blocks | 12 | 15 | 156 | Prior recipe cells held items; required stow_items before new craft |
| Wrong-slot / cursor issues | 3 | 4 | 51 | Held wrong item after craft; cursor reported empty despite carry |
| Total refusals/errors | 67 | 724 | 558 | of2r peak likely during obsidian/flint rapid iteration |

### Systemic Workarounds Written
- of3r: "GUIwatch12aftercraftbeforeclose and afterclosebeforecamera" → explicitly added delays post-craft
- of1r working.md: "Bank them first: stow_items(grid='3x3', cells=[...]) then call craft()"
- of2r: No novel workaround recorded; reused harness stow_items

---

## 8. Systematic Issues Ranked by Steps Lost

1. **Portal frame placement uncertainty (of3r, ~8.9k steps m15→m16)**
   - All 10 obsidian blocks "reported" via use_at events but actual world coordinates never independently verified
   - Ignition attempts 35,276 (fail), 35,296-35,310 (fire/water/extinguish cycle), 35,358-35,387 (re-aim/fire/punch cycle)
   - Interior geometry blocked/misaligned three times; no plan to photograph/log frame before ignition
   - **Contract fix**: Require one mine_block confirmation after each obsidian placement to log exact coordinate, or screenshot portal exterior before ignition attempt

2. **Obsidian gathering geometry (of1r, stalled after m12; of2r rapid pivot)**
   - of1r: Single approach to obsidian cave failed (water/lava hazard); no route retry plan logged
   - of2r: Quick death-restart pivot to alternate dry location worked
   - of3r: Avoided water cave entirely after reading prior life frames
   - **Contract fix**: Document 2-3 obsidian access routes in life setup (not just one spiral descent)

3. **GUI leftover-cell blocking (of3r 156 refusals)**
   - Majority of ofr3's 558 GUI errors were leftover blocks from prior craft occupation
   - Workaround stow_items() required post-craft, delaying iteration
   - **Contract fix**: Auto-clear crafting table between distinct recipes, or require explicit stow only if player manual-moved items mid-craft

4. **Fall deaths clustered (of1r deaths 2-4, steps 23,360-24,358)**
   - Three deaths in ~1k steps, all near same coordinates, all same reflex/hazard
   - No route diversification attempted after death 1 recovery
   - **Contract fix**: Log 5-step fallback route in working.md before entering known hazard areas

5. **Food starvation never addressed (all three lives)**
   - All three ended with food 13-20, no passive mob hunting plan or emergency food cache
   - Healing reliant on natural regen; no food buffer for Nether combat
   - **Contract fix**: Plan one animal hunt + food smelt before Nether entry (cost ~500 steps, gain 40 food buffer)

**Estimated impact (total steps that could have been recovered)**:
- of1r obsidian reroute: ~5k steps
- of2r/of3r portal frame verification: ~3k steps each
- All three: food planning: ~500 steps each
- of3r GUI leftover bulk-clear: ~2k steps

