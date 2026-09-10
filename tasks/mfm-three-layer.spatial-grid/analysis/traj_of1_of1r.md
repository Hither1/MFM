# Trajectory Analysis: of1_mfm vs of1r_mfm

## 1. Step Budget Allocation & Loop Patterns

**of1r: Furnace (step 5509) → Iron Ore (step 23519) = 18,010 steps**
- Actions 239-245 (steps 11472-13200, ~12.6k steps): Repetitive "guarded eastward stair cycle" descent at Z-5582.7.
  Each action mines 4 blocks and descends 2Y; plan repeats 7 times with identical "[PLAN] Repeat one guarded eastward stair cycle, monitoring for iron/coal" (logs lines 3000-3200).
  Loop breaks when ore found on wall face at Y19 after exhaustive east descent (~42 blocks from spawn Y71).
- Furnace interaction cost (steps 23762-23794): Mis-click on furnace slot, cursor held cobblestone+plank; recovery via cursor_to_slot (16 ticks) + gui_click (3 ticks).

**of1r: Iron Pickaxe (step 33104) → Diamond Ore (~step 55548) = 22,444 steps**
- Pattern: Extended horizontal tunneling with 72 go_to stall events throughout run.
- Harness overhead: go_to detouring over walked-cells, pillar_up queued after stalls (each pillar_up 176-224 ticks).

**of1: Water Shaft Trap (steps 40104-40593) = 489 step sequence, 3 deaths total**
- Steps 40104-40242 (Actions 801-808): Repeated "replay proven southward jump-swim ascent" at flooded chamber (-2998, 43-48, -5612).
  Four 4-directional surveys (40 ticks each) + jump-hold to Y48 + survey overhead.
- Step 40442 (Action 809): Hand-mine 200 ticks "clear headroom for pillar ascent"—mining support collapsed.
- Step 40593 (Action 810): Drowned at (-2998, 43, -5613); pos resets to spawn; go_to recovery fails (stalled 29.6 blocks short, then fully blocked at 16.5 blocks).
- Core failure: Low health (2/20) + flooded chamber hazard + no escape route; chose iron ore location that was lethal.

## 2. Harness Mechanics Costs

**go_to Stalls (of1r: 72 occurrences)**
- Type A (Detour): "go_to (-2997.6, -5582.7) stalled at (-3000.3, -5582.7), 2.7 blocks short -- detouring over 3 cells, ending at (-2998, 55, -5583)" (step 5919, Action 118).
  Full budget (80-100 ticks) consumed; zero progress.
- Type B (Hole climb): "go_to stalled at (-2999.3, -5582.5): 8 blocks below cell (-2999, 61, -5583) -- hole cannot climb; pillar_up(6) queued" (step 8690, Action 210).
  Recovery: 176 ticks + 6 cobblestone; then re-execute go_to.
- Type C (Blocked): "go_to blocked at (-3004.3, -5587.3), 6.9 blocks short -- wall/pit in way (detour stalled too)" (step 19707+).
  Requires manual mine_forward or goal reset.

**Fell Reflex Plan Drops** (exemplars)
- Step 5919 (Action 118): 2.7 block drop, dropped 2 actions; forced 4-directional survey (protective).
- Step 19707 (Action 332): fell at Y73→Y66 after go_to, then pillar_up(5) needed (152 ticks).
- Step 27478 (Action 498): fell at Y72→Y66, spawned 43-action plan drop (most severe interruption).

**GUI Interactions (Cursor Misalignment)**
- Step 23788-23794 (of1r Actions 398-401): furnace_load clicked wrong slot; cursor held cobblestone+plank off-inventory.
  Recovery: place_and_open (60 ticks) + furnace_load (56 ticks) + cursor_to_slot (16 ticks) + gui_click (3 ticks) = 135 ticks + plan re-expansion.

## 3. Memory Reuse (of1r → of1r_mfm)

**Previous/ References: 278 occurrences in of1r rollout**
- Paths: previous/life_1/mine/{digest,notes}.md, logs.txt, episodes/, procedures/deep_stair_step.py, reflexes/.

**Digest Influence on Routing**
- of1 death at (-2998, 45, -5612) documented; digest: "Refuse entry without known air route."
- of1r outcome: Did NOT attempt flooded corridor; instead descended to Y19 at Z-5582.7 (same x, different depth).
- Avoidance successful: no water death in of1r (vs. 2 drowned in of1).

**Repeated Hazard: Creeper Location**
- of1 death at (-2992, 54, -5583, step 12306); digest: "Light any descent, stop on hit reflex immediately."
- of1r hit reflex fires 3× (vs. of1's 1×): step 5933 (4 damage, health 16/20), step 9516 (3 damage, health 9/20), step 21289 (8 damage, health 12/20).
- Outcome: of1r survived all encounters; reflex correctly interrupted continued engagement.

## 4. Reflex Firing Patterns & Effectiveness

| Reflex | of1 | of1r | Observations |
|--------|-----|------|---|
| fell | 12× | 7× | Both: protective interruption of mining before major fall. of1r fewer falls → better vertical awareness or fewer risky descents. |
| hit | 1× | 3× | of1r: 3 mob encounters, all survived via pillar_up/escape. of1: 1 encounter, less mobile response. |
| starving | 4× | 2× | Both: fired when food <18/20. No critical situations. No food farming observed in either run. |

**Fell Reflex Helpfulness**
- Step 5919 (of1r Action 118): Dropped 2 actions after 2.7 block fall; forced required 4-directional survey before descent—protective.
- Step 8690 (of1r Action 210): Interrupted go_to detour; prevented chaining into worse stall.
- Step 27478 (of1r Action 498): Dropped 43 actions; severe but prevented continued mining into unstable area.

**Hit Reflex Outcomes**
- of1r step 5933: Identified mob threat, escape successful (wait 80 ticks + mine_west).
- of1r step 9516: Pillar_up called, no escalation to death.
- of1 (single occurrence): Did not prevent eventual death by drowning/creeper later.

## 5. Systematic Model Errors & Harness Artifacts

**EXPECT Mispredictions**
- of1r Action 118: "EXPECT: descends toward Y56, dirt returns toward eighteen" → OBSERVED: "Y reached 57, only one dirt recovered; short fall occurred."
- Pattern: Model assumes unobstructed descents but flooded/open shafts cause fall interruption.

**Hotbar Slot Desynchronization**
- of1r step 23788: furnace_load cursor clicked wrong slot; cobblestone+plank off-inventory. 
- Indicates GUI state tracking lag in model's action planning.

**Water/Drowning Mismanagement (of1)**
- Steps 40104-40593: Agent executes jump-swim in flooded chamber with health at 2/20.
- Step 40442: Attacks 200 ticks underwater (drowning damage ~4 ticks per second); mining support collapses.
- Core issue: Underestimated oxygen depletion rate; no torch placement for air pockets.

**Light Level Reactive vs. Proactive**
- of1r steps 5700-8000: Repeated "dark stone shaft", "dark wall", "close dark ceiling" → no torches placed.
- Both runs: Torch placement occurs late (of1 step 40546 mines wall_torch) after extensive darkness exposure.

---
**Key Insight:** of1r's memory reuse successfully averted water deaths but still consumed 18k+ steps on linear iron-ore descent search; go_to pathfinding overhead (72 stalls) is the dominant harness cost, surpassing reflex interruptions. The fell reflex, while plan-dropping, prevents catastrophic falls.
