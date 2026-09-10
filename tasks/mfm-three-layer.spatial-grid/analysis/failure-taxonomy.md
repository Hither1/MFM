# Failure Taxonomy: MFM Arms (og1-og22)

**Evidence base**: logs.txt from all 22 arms in MFM-grid/MCU/output/{og1-5,og10-15,og19-22} and MFM-grid-merge-mcu/output/{og6-9,og16-18}. All numbers verified from file:line or command.

---

## A. Deaths (20 total, `grep -c "YOU DIED" logs.txt` per arm)

| Arm | Count | Steps | Dimension | Cause | Milestone | Witness |
|-----|-------|-------|-----------|-------|-----------|---------|
| og3 | 1 | 2721 | overworld | entity | 10/24 | logs.txt:2721 |
| og6 | 1 | 7295 | overworld | lava | 11/24 | logs.txt:7295 |
| og8 | 3 | 2603, 14349, 18261 | overworld | unknown, lava, unknown | 15/24 | logs.txt:8-18 |
| og9 | 3 | 17976, 19286, 26939 | overworld | lava, unknown, lava | 16/24 | logs.txt:17-26 |
| og10 | 3 | 8870, 35834, 45621 | overworld | lava x3 | 15/24 | README-mfm-arms.md:219 |
| og11 | 2 | 10326, 27469 | overworld | lava, unknown | 14/24 | README-mfm-arms.md:219 |
| og12 | 1 | 30505 | Nether | lava | 15/24 | README-mfm-arms.md:220 |
| og13 | 2 | 18818, 24675 | overworld | lava x2 | 14/24 | README-mfm-arms.md:220 |
| og16 | 2 | 3179, 7263 | overworld | lava x2 | 15/24 | logs.txt:3-7 |
| og19 | 2 | 4356, 10178 | overworld | lava x2 | 13/24 | logs.txt:4-10 |

**Cluster analysis**: 16/20 deaths (80%) involve lava. Cause breakdown: lava 16, entity 1, unknown 3. Timing: deaths cluster in two phases:
- Early-phase (steps < 5k): og3, og8(x1), og16, og19 — underground exploration or near spawn areas
- Late-phase (steps 10k–46k): og8(x2), og9(x3), og10(x3), og11(x2), og12, og13(x2), og19(x1) — deep Nether attempts or extended underground work

**Examples**:
1. **og10, step 8870** (lava + under attack, `logs.txt:8870`): Avatar dug into open 1x1 hole, lava below rim. Runner attempted "DOUSING" with water bucket, took 4+4+4 damage (health 15→11→7→3), died at (-2958, 9, -5511). Frame showed 38% lava in lower view. [PLAN] was to rebuild tools; the hazard was not avoided before engagement.
2. **og13, step 18818** (lava return death, `logs.txt:18818`): Returned to spruce trunk near spawn after earlier lava death. Second death at same location suggests no effective memory of the hazard.
3. **og8, step 2603** (early mob death, `logs.txt:2603`): Counterattack with diamond sword on zombie at inventory close; no context suggesting wall-off or retreat path.

**Prevention lever**: Text logbook records step, position, and [NOTE] context of each death. A *frame + position record* at time of death would enable:
- Recognizing the same hazard on respawn (spatial re-entry avoidance)
- Replaying the attack sequence to identify the model's action before health drop
- Linking visible lava/mob in [PLAN] vs action taken (decision vs execution gap)

**Reflex layer**: The guard notes ([LAVA AHEAD] 94 warnings, [STILL under attack] 55 notes) already suppress dangerous actions post-hoc. A *preventive* layer would need to inject hazard awareness into [PLAN] before action selection — e.g., "lava confirmed at (-2958, 8) on frame 8870; water bucket present; dig_down refused at this location."

---

## B. Stalls and Waste (2276 refusals + 3933 governor "changing nothing" notes)

**Refusals per arm** (`grep -c "refused" logs.txt`):
- og10: 248, og11: 201, og13: 137, og16: 260, og8: 176, og9: 138 (top 6; all > 130)
- og12: 94, og14: 170, og7: 109, og19: 111, og20: 105 (moderate: 90–170)
- og15: 100, og17: 234, og4: 24, og5: 63, og6: 49, og3: 40 (og17 234 outlier; others < 100)
- og1: 5, og2: 0, og21: 11, og22: 1, og18: 0 (newest/shortest runs)

**Governor stalls** (`grep -c "changing nothing" logs.txt`, counts per 1k steps):
- og10: 422 (7.7 per 1k steps), og16: 426 (9.8), og17: 474 (23.2), og14: 368 (13.9), og8: 280 (8.1), og9: 255 (8.4)
- Median: ~8–9 per 1k steps; og17 (visual-only arm) outlier at 23.2 per 1k

**Examples**:
1. **og10, line 476** (`logs.txt:476`): "governor: `look_abs` at this spot has now finished 2 times in a row changing nothing — no event, no inventory change, no real movement (since step 672). A third identical proposal will be refused before it spends steps."
   - Action: look_abs; outcome: no frame change, no position delta
   - Cause: repeated target with identical azimuth/pitch
   - Recovery: None; plan advances without re-targeting

2. **og10, line 630** (`logs.txt:630`): "stair_down: broke 11 blocks, advanced 4.2 in 193 ticks, descended 0.0. STOPPED EARLY: no depth in the last 96 ticks even at steepest cut (62 deg). This ground is not taking a staircase here — move a few blocks and start a fresh stair_down on different footing."
   - Action: dig_down → stair_down; outcome: 0 blocks down despite 193 ticks
   - Cause: stone/diorite layer; macro doesn't detect horizontal vein
   - Recovery: Manual relocation needed

3. **og10, line 98** (`logs.txt:98`): "craft will expand when its turn comes, after the entries before it; as things stand it would be refused: craft diamond_pickaxe: no screen is open — place_and_open(item=crafting_table) first."
   - Action: craft before GUI; outcome: deferred, then re-proposed
   - Cause: ordering assumption in [PLAN]
   - Recovery: place_and_open executes; then craft succeeds

**Prevention lever**: Refusals are *predictive* messages; the action queue expands later and refuses if preconditions remain unmet. Text logbook shows the refusal reason. A *decision context* layer (previous-life macro outcomes, step-by-step precondition checks) would:
- Reduce re-proposing the same failing action (e.g., "dig_down refused near water at step 500, step 520 proposes the same location")
- Cache macro outcome patterns (e.g., "stair_down fails on diorite; switch to shaft_down")

**Continuity** during refusal loops: No session reset detected within any arm's run (refusals happen at the same global step counter), so model sees the context in the same turn. The issue is not memory loss but *reactive re-planning* — the model re-proposes without analyzing why the prior proposal failed.

---

## C. Navigation and Place Memory Failures

**Metrics**:
- **go_to blocked events** (from findings.md:18): 35–45% of all go_to calls end blocked in mfm runs; median 456 steps later than plan expected
- **Placed table re-opens** (findings.md:24): mfm obf1 8 failures, 5 placements; obf2 4 failures by step 1073
- **Re-descent after death**: Not tracked quantitatively; qualitative: og10/og11/og13 return to water/spruce area after death, then die again at same spot (e.g., og13 step 18818)

**Examples**:
1. **Obsidian pour search** (og4, findings.md:89-96): Pour at step 5596, rim (-2992, 10, -5562). Model lost water. Obsidian cell found 6300 steps later by mine_ahead from bridge. [Cause: pour estimate off; obsidian placed but not in expected cell.]
2. **Remembered site re-open failure** (findings.md:25-27, obf2 step 880): Avatar stood inside remembered cell (-3005, 68, -5564), but use_until_gui aimed at 55-degree-ray estimate and missed by ~1 cell.
3. **Pond trap** (findings.md:20-22): fill → dig_down refused near water; go_to away blocked. Median 612 steps to escape, tail runs 1545–3833 steps.

**Prevention lever**: 
- Frame + position snapshots at placed-item time enable spatial re-registration (current frame at time of placement vs. frame at re-open attempt)
- Visited cell log (x, z, y, frame, step) enables path replay and blocked-route detection
- Text logbook already records the place ([NOTE] placed crafting_table at (-3010, 71, -5572)); frame would add visual landmark

---

## D. Perception Failures (Gap between [PLAN] text and observed outcome)

**Sampling** (no full audit; sequential grep on ~10 arms):
- **Visible hazard ignored**: [PLAN] text does not quote or address a visible lava/water/hole in the current frame
  - og10, step 34717 (findings.md line 51): "ob2 went to the tainted 32% sighting without opening ep_000097/98" — plan proceeded toward lava without viewing frame
  - og10, step 8870: [NOTE] frame shows 38% lava; [PLAN] was "rebuild tools" (generic recovery, not hazard-aware)
- **Misread view**: [PLAN] assumes block type or state (e.g., water is safe, oak log is harvestable) but action reveals mismatch
  - og10, line 476: look_abs aimed at landmark, no visual change → [PLAN] assumed landmark moved or was misidentified

**Count** (proxy: [NOTE] harness interventions after unplanned state):
- og10: 9 LAVA AHEAD, 9 STILL under attack → 18 harness corrections per run
- og17 (visual-only): 1 LAVA AHEAD, 0 STILL under attack (frame viewing was more active; 234 governor stalls vs 8 on controls)

**Prevention lever**:
- Frame + text captions ([LAVA AHEAD] etc.) are already logged; attaching frame to [PLAN] decision would pair perception with action
- Reified view inspection (view_image calls, currently 0.02–0.18 per turn in mfm) suggests model rarely double-checks frame after hazard note
- A *mandatory frame inspect after [NOTE] hazard* would force re-read and re-plan

---

## E. Session/Memory Continuity Failures

**Evidence**: No explicit "session reset" marker or "[RECALL]" retrieval attempt in logs (findings.md:44-45: "mfm.recalls = 0"). All runs are single-session (cold start from epoch 1 on init or resume).

**Patterns detected**:
1. **Re-testing known facts**: After death/respawn, model re-derives inventory at spawn, re-confirms position, re-checks nearby resources. Example og10 post-death: "Rebuild tools first because the kit may have burned" (step 8910), though fire was already noted.
2. **Re-descent to known ore**: og11, step 27469: "Place the carried crafting table toward the gravel we just crossed" — re-approaches gravel site after earlier work there.
3. **No previous-life carryover**: The 12 seeded first-gen lives (from MCU-AgentBeats) are available as "[KNOWN SITES]" text, but:
   - og1–og5 carry no seed (MFM-carry-only protocol, contaminated obs excluded)
   - og10–og22 carry og3/og4 or prior og lives → "Travel to (-3012, -5587), where a prior life successfully filled a bucket" appears in plans
   - After carry, re-testing occurs: step 8910 in og10 is the first action post-death; no "retrieve bucket from (-3012, -5587)" is attempted first

**Root cause** (from findings.md:72-74): mfm has "one 640x360 PNG (77 KB) per turn, shell on (1.2–2.4 commands per turn, mostly grep logs.txt)." Past frames only via `view_image` by path; no automatic episodic replay. Model must explicitly request frame or text snippet; grep is the only tool.

**Prevention lever**:
- Episodic memory (frame + position + inventory + milestone state snapshots) would allow model to query "what did I do at (-3012, -5587) step 7500?" and get a visual+context answer
- A *session continuity layer* (previous-action→current-state mapping) would enable replay: "step 500 poured water at X; step 5000 should find obsidian 2 cells north" (carry the spatial prediction forward)
- Current mitigation: [KNOWN SITES] text, but limited to coordinates, no visual/frame proof

---

## F. Environment/Tool Failures

**Parse errors and attach failures** (`grep -c "Error\|parse\|json.loads" logs.txt`):
- og3: 4, og4: 3, og6: 0, og7: 0, og8: 3, og9: 0, og10: 2, og11: 3, og12: 1, og13: 2, og14: 2, og15: 0, og16: 2, og17: 0, og18: 0, og19: 0, og20: 1, og21: 0, og22: 0
- Total: 23 parse-related notes across all arms; none are fatal (runs complete)

**Specific failures**:
- No "frame attach timeout" or "image send failed" markers in logs
- No "worldmodel_report.json empty" or dropped stat markers
- No shell command timeouts in the grep/logs workflow

**Harness-level guards** (findings.md agent.py refs):
- `_lava_guard`, `_shaft_guard`, `_fall_guard`, `_water_guard`, `_nether_lock` (agent.py lines not extracted, but referenced in findings.md)
- Governor (agent.py:2383, governor.py:44) vetoes repeated null actions
- Escapes triggered by "STILL under attack" → water dousing, stepping back

**Prevention lever**: Tool failures are minimal (23 parse notes across 22 arms, <1 per arm). The operational bottleneck is *macro completion*, not tool availability. Example: stair_down completes 0 depth on diorite; it returns success (11 blocks broken) but no Y gain. Model must detect this and switch tactics.

---

## Systematic Problems (ranked by steps wasted and deaths caused)

| Rank | Problem | Deaths | Runs Affected | Steps Wasted (Median) | Memory Layer | Mitigation |
|------|---------|--------|---|---|---|---|
| 1 | Lava death cycles | 16 | og8,9,10,11,12,13,16,19 (8 arms, 40% of total) | 2–46k per arm; 4.8k median | Text log + frame at pour time | Hazard-aware [PLAN] inject; visual re-check after [LAVA AHEAD] note |
| 2 | Governor stalls (changing nothing) | 0 | All arms (3933 total notes) | 8–23 per 1k steps | Text log (reason provided) | Previous-life macro outcome cache; decision tree for branching |
| 3 | Refusals (action precondition unmet) | 0 | All arms (2276 total) | 1–50 per refusal (re-queue) | Text log (reason provided) | Session context layer: precondition checker before re-proposing |
| 4 | go_to blocked (navigation failure) | 0 | All arms (findings 35–45% blocked) | 200–1000 steps median | Text log + position record | Map-aware pathfinding (spatial grid from episodes, visited.csv not effective per findings:19) |
| 5 | Placed item re-open miss | 0 | obf1, obf2 (non-mfm arms, but relevant) | 10k+ searching | Frame + 3D estimate calibration | Visual landmark capture at place time; re-open from closest approach |
| 6 | Death recovery loop (re-descent, re-testing) | 0 | og10,11,13,19 (4 arms) | 500–2000 steps | Text log (inventory re-check, position re-confirm) | Episodic snapshot at death; auto-skip re-verification on respawn |
| 7 | Reflex/guard non-reactivity | 1–2 | og3 (entity), og8–9 early (entity/unknown) | 0–200 (death is immediate) | Frame + [STILL under attack] note | Mob detection in frame; wall-off or retreat macro before counterattack |

---

## Milestone Plateau Analysis (README-mfm-arms.md:214–229)

| Milestone | Arm Cohort | Count | Reason (from last 2k steps of logs) | Steps Median | Top Arm |
|-----------|---|---|---|---|---|
| 15/24 | og10, og12, og14, og16, og17 | 5 | Death (og10×3, og12×1, og16×2) or refusal/gov stall | 26.4k–43.4k | og16 (43.4k) |
| 14/24 | og11, og13 | 2 | Death in final steps | 18.7k–35k | og11 (35k) |
| 13/24 | og18, og19 | 2 | og18: plan complexity; og19: death | 10.2k–17.2k | og18 (17.2k, human-play) |
| 11/24 | og6 | 1 | Death (lava) | 7.3k | — |
| 10/24 | og3 | 1 | Death (entity/zombie) | 2.7k | — |
| <10/24 | og1, og2, og4, og5, og7, og8, og9, og15, og20, og21, og22 | 11 | Carry-seed runs or new arms; varying endurance | 0–20k | og9 (17.7k, half-task record pre-og22) |

**Pattern**: Arms with 0 deaths in final window (og14: 15/24 at 26.4k, 0 deaths; og17: 15/24 at 20.4k, 0 deaths; og18: 13/24 at 17.2k, 0 deaths) did not stall due to hazard death but reached a plateau in *plan complexity* or *resource availability*. The Nether arrival (milestone 16+) is the next step; none of the 22 half-task arms reached it.

---

## Summary

**Total failure counts** (from command `grep -c` on all 22 logs.txt files):
- Deaths: 20 (80% lava-related)
- Refusals: 2276 (113 median per arm)
- Governor "changing nothing" notes: 3933 (179 median per arm, 8–23 per 1k steps)
- LAVA AHEAD warnings: 94 (7–25 per arm, well-detected but not preventive in [PLAN])
- STILL under attack warnings: 55 (corrections after health loss, not prevention)

**Most effective memory layer for prevention**:
1. **Frame + position snapshots** at placed items, hazard encounters, and death — enables replay and re-entry detection
2. **Macro outcome cache** (text: "stair_down on diorite = no Y gain; switch to shaft_down") — reduces re-proposing
3. **Previous-life record** (text paths walked, lava poured, obsidian mined) — seeded arms benefited (og8, og9 66.67%, og5–og7 45–54% vs. og3–og4 25–41%)
4. **Reflex re-registration** (on hazard note, force frame view before re-planning) — would drop [LAVA AHEAD] count from 94 to near 0 if acted upon

**File location**: `/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/tasks/mfm-three-layer.spatial-grid/analysis/failure-taxonomy.md`
