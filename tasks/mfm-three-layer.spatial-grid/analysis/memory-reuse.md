# Memory Reuse Analysis: Previous Lives vs From-Scratch Arms

## Executive Summary

Previous-life memory was read in 20-35% of turns by carry arms (og3-og9, toolcalls.py), but milestones per step were not systematically faster than from-scratch arms on equivalent code. The digest mechanism in og19 (23 lives) and og15 (1 life) reused coordinates and hazard warnings in plans, but the model rarely (0-3 calls) examined previous life *frames* (vision_use.py). Multi-life arms (og5, og9) spent time reading previous logs but achieved speeds comparable to single-seed arms (og15). The systematic transfer: hazard locations (lava pools, shafts, water) and structured coordinates made it into plans; frames of previous places were not leveraged; rediscovery of known resources (iron, gravel) was common.

---

## Part 1: What Carry Arms Read from Previous/

### Per-arm reading patterns (from codex_turns, toolcalls.py, turn counts)

**og3 (carry, 12 lives, 1 seed):**
- 49 `previous/` commands in 77 turns (21% episode.py)
- Commands: rg over previous/life_*/logs.txt (grep), sed extraction, conditional reads of notes/digest
- Read at: grep logs for [STATE]/[EVENT]/death/lava, sed on life sections ~step 700-1300
- File:line evidence: `output/og3_mfm/episode_001/codex_turns/turn_*.events.jsonl` contains commands (not inspected in detail; summarized by toolcalls)

**og4 (carry, 12 lives, 1 seed, seeds og5+):**
- 22 `previous/` commands in 98 turns (8% episodes.py, lowest rate)
- Lighter memory usage; early death at step 5614 ended exploration phase
- File:line: `output/og4_mfm/episode_001/memory/logs.txt:5614` death marker

**og5 (carry, 12+3 lives, seeded with og3/og4):**
- 70 `previous/` commands in 79 turns (35% episodes.py, highest rate)
- Aggressive use of episodes.py --previous flag (11 uses), --json (30), grep (13)
- Earliest to reach obsidian milestone (8.3k steps, 13/24 at step 7175)
- File:line: toolcalls.py count `previous/: 70`

**og8 (carry, 12+3 lives):**
- 39 `previous/` commands in 266 turns (15% episodes.py)
- Extended run: 3 deaths, reached 15/24 at obsidian step 12884
- File:line: toolcalls.py count `previous/: 39`

**og9 (carry, 12+3+1 lives, seeds og10+):**
- 48 `previous/` commands in 251 turns (22% episodes.py)
- Reached obsidian at step 8675 (second-fastest after og5)
- File:line: toolcalls.py count `previous/: 48`; obsidian at `output/og9_mfm/episode_001/memory/logs.txt` line showing mine_obsidian event

**og15 (carry, 1 life og14 only, self-harness task):**
- 48 `previous/` commands in 336 turns (4% episodes.py)
- Same reading rate as og9 (48 commands) despite 1 vs 4 lives, lower episodes.py rate
- Seeded with just og14's single life, yet reached 14/24 at step 13251
- File:line: toolcalls.py count `previous/: 48`

**og19 (carry, 23 lives, memory-reuse task):**
- 35 `previous/` commands in 172 turns (12% episodes.py)
- Fewer than og15 and og9 per command rate (0.20/turn vs 0.14-0.19)
- Explicitly wrote digest.md in turn 1 from all 23 previous logs
- File:line: `output/og19_mfm/episode_001/memory/mine/digest.md` first 50 lines (see below)

### Digest.md content (og19's first 30 lines from previous lives analysis)

From `output/og19_mfm/episode_001/memory/mine/digest.md`:
```
# Prior-life digest — current run, step 0
Read programmatically from all 23 previous logs. Detailed events, action/step headers, 
positions, lava and portal notes are in mine/prior_evidence.json.

## Verified useful places and routes
- Spawn (-3009.5,71,-5572.5). Several lives: first collect_drops stops on dirt16...
- Initial table: life17 explicit place_at at block(-3010,71,-5571) succeeded...
- Surface water/gravel: life17 filled bucket at player(-3083.35,71,-5628.68)...
- Iron: life17 mine_iron_ore at player(-3008.54,47,-5596.70)...
- Diamond ore repeatedly verified in lives9/19/20/21 near player(-2999.3,8..9,-5570.7)...
- Closest productive obsidian pool: lives14/15/19/21 east of player(-2992.6,11,-5559.5)...
  Life21 first verified exact target block(-2990,11,-5560), step8675, mine_obsidian300...
- Nether access verified in life21, arrival near(-362.6,47,-686.5)...
```

**Classification:** The digest contains coordinates (spawn, iron, diamond, obsidian pools, Nether), hazard analysis (lava locations with exact block targets), death records per life (20 summarized), and procedural notes (pour techniques, re-break cycles).

---

## Part 2: Recorded Facts Used vs Rediscovered

### Facts that were used (textual citations in plans)

**og9's obsidian mining (step 8675, `output/og9_mfm/episode_001/memory/logs.txt`):**
- Plan cited: "This is the 3rd plan the same lava has stopped within 3 blocks of here"
- Exact location used: (-2990, 11, -5560) – matches digest "life21 first verified exact target"
- Evidence: logs.txt line shows mine_obsidian at (-2990, 11, -5560); prior log lines from og4 recorded lava at same pool
- File:line: `output/og9_mfm/episode_001/memory/logs.txt` LAVA AHEAD note mentions "These cells are on record"

**og19's iron mining (step 1933, `output/og19_mfm/episode_001/memory/logs.txt:1155`):**
- Plan cited: "Probe east toward the previously verified iron vein"
- Location: (-2997.30, 55, -5565.64) – within 1 block of digest "life21 iron milestone at (-2997.30, 55, -5565.39)"
- Evidence: logs.txt line 985 "Center on the recorded descent column, dig to Y55"
- File:line: `output/og19_mfm/episode_001/memory/logs.txt:1007` plan text

**og19's descent target (step ~1800, `output/og19_mfm/episode_001/memory/logs.txt:1013`):**
- Plan: "Center on the recorded descent column, dig to Y55, and place a torch"
- Coordinate: (-2998.54, 55, -5565.64) – near recorded iron descent
- Evidence: used exact Y-level (55) from digest, "previously verified iron vein" language
- File:line: `output/og19_mfm/episode_001/memory/logs.txt` line 985-1110

### Facts available but rediscovered (steps wasted)

**Gravel / flint_and_steel:**
- og19 started at spawn (-3009.5, 71, -5572.5) per digest
- og14 never found gravel (from-scratch control, 26.4k steps, no flint_and_steel milestone)
- og18 (human-play, from-scratch) spent 5.7k steps on flint (no water/lava found)
- Digest recorded: "Surface water/gravel: life17 filled bucket at player(-3083.35,71,-5628.68)" – 74 blocks west
- og19 found water elsewhere but flint not recorded in early milestones
- File:line: `output/og19_mfm/episode_001/memory/mine/digest.md` surface water entry; `output/og18_mfm/episode_001/memory/logs.txt` step 5727 flint

**Diamond ore search:**
- Digest: "Diamond ore repeatedly verified in lives9/19/20/21 near player(-2999.3,8..9,-5570.7)"
- og9 mined at step 5691 after finding vein visually (near (-2999, 9, -5570))
- og19 at last snapshot (14.5k steps) had only reached 13/24, no diamond_ore milestone yet
- Evidence: og9 found it naturally within 100 blocks per exploration; re-finding was not systematic rediscovery
- File:line: `output/og9_mfm/episode_001/memory/logs.txt` mine_diamond_ore milestone line

**Water / bucket locations:**
- og4 filled bucket at pond near spawn (step 844)
- og5 reached obsidian without finding water early (8.3k steps to obsidian, no fill before)
- og9 filled bucket only after Nether entry (step ~17.5k), late in the run
- Digest recorded water at (-3083.35, 71, -5628.68) but not actively used by carries before Nether
- File:line: `output/og5_mfm/episode_001/memory/logs.txt` no fill_bucket milestone; compare.py fill=None

---

## Part 3: Outcomes Comparison – Carry vs From-Scratch

### Milestone times (steps to first event, formatted from logs.txt and compare.py)

| Arm | Setting | Steps | Score | First Iron | Obsidian | Deaths | Cmd/turn |
|-----|---------|-------|-------|-----------|----------|--------|----------|
| og5 | Carry 15L | 8,328 | 13/24 | ~3k | 7,175 | 0 | 2.1 |
| og9 | Carry 16L | 30,220 | 16/24 | 5,691 | 8,675 | 3 | 3.5 |
| og8 | Carry 16L | 34,431 | 15/24 | ~1.2k | 12,884 | 3 | 3.0 |
| og15 | Carry 1L | 13,806 | 14/24 | ~1.7k | 13,251 | 0 | 2.6 |
| og19 | Carry 23L | 14,484 | 13/24 | 1,933 | (no) | 2 | 3.0 |
| **og10** | **Scratch** | **54,668** | **15/24** | **~5k** | **35,170** | **3** | **2.8** |
| **og11** | **Scratch** | **34,954** | **14/24** | **~4k** | **22,274** | **2** | **2.7** |
| **og12** | **Scratch** | **33,869** | **15/24** | **~3k** | **6,134** | **1** | **2.4** |
| **og13** | **Scratch** | **27,755** | **14/24** | **~3k** | **13,358** | **2** | **3.1** |
| og14 | Scratch+own | 26,412 | 15/24 | ~3k | (no) | 0 | 2.8 |
| og16 | Scratch+guards | 43,372 | 15/24 | 2,577 | 41,835 | 2 | 3.3 |

**Key finding:** og12 (from-scratch) reached obsidian at 6,134 steps (fastest on record); og9 (carry) at 8,675 (2nd); og5 (carry) at 7,175 (3rd). Carry arms were NOT systematically faster to obsidian. Iron times similar (1.2k–5.7k range for both carry and scratch).

Comparison (same code, og8/og9 carry vs og10-og13 scratch):
- Carry pair: og8 34.4k, og9 30.2k → mean 32.3k for 15-16/24
- Scratch pair: og10 54.7k, og11 35.0k → mean 44.8k; post-fix og12/og13 30.8k mean
- **Carry advantage:** ~30% faster on pre-fix code (32.3k vs 44.8k); negligible on post-fix code

### Goal-achievement rate

Both carry (og5, og8, og9) and scratch (og12, og13, og14) reached 14-15/24 milestones. No arm broken by loss of previous-life records.

### Death causes

**Carry arms (og8, og9 with 3 deaths each):**
- og8: zombie in own shaft (2603), lava at pool (14349, 18261)
- og9: Nether lava lake (17976), own first-life shaft (19286), cliff fall (26939)

**From-scratch arms (og10-og13, 1-3 deaths each):**
- og10: lava pool x3 (pre-fix, same pool)
- og13: Nether lava (18818), zombie (24675)

No systematic death reduction from carry.

---

## Part 4: Frame Use in Reuse (Previous-Life Visual Memory)

From `vision_use.py` (codex_turns/* rollout analysis):

| Arm | Total views | Current zoom | This-life ep | Previous-life ep | Digest |
|-----|-------------|--------------|--------------|------------------|--------|
| og3 | 3 | 2 | 1 | 0 | 0 |
| og4 | 3 | 1 | 1 | 0 | 0 |
| og5 | 3 | 1 | 2 | 0 | 0 |
| og8 | 118 | 80 | 35 | 0 | 0 |
| og9 | 98 | 62 | 30 | 0 | 0 |
| **og15** | **32** | **23** | **3** | **3** | **0** |
| og16 | 0 | 0 | 0 | 0 | 0 |
| **og19** | **76** | **68** | **6** | **0** | **0** |

**Finding:** Only og15 viewed previous-life frames (3 calls), despite og9/og19 carrying multiple lives. og19 with 23 lives accessed 0 previous-life frames (all views were current-view zooms or this-life episodes). Vision memory reuse did not happen.

File:line evidence: `tasks/mfm-three-layer.spatial-grid/scripts/vision_use.py` output above; confirmed by scanning `codex-homes/<arm>/sessions/*/*/*/rollout-*.jsonl` for `view_image.*previous` patterns (none found in og19, og8, og9).

---

## Part 5: Multi-Life vs Single-Life Arms (Scalability)

### Reading load (commands per turn)

| Arm | Lives | Turns | Prev/ cmds | Prev/ per turn | Episodes.py % |
|-----|-------|-------|-----------|---|---|
| og5 | 15 | 79 | 70 | 0.89 | 35% |
| og9 | 16 | 251 | 48 | 0.19 | 22% |
| og15 | 1 | 336 | 48 | 0.14 | 4% |
| og19 | 23 | 172 | 35 | 0.20 | 12% |

**Pattern:** Multi-life arms (og5, og9) did NOT proportionally increase reading. og5 read heavily early (35% episodes.py); og9 stabilized at 22%. og19 with 23 lives read FEWER commands (0.20/turn) than og9 (0.19/turn) despite 6x more lives.

**Hypothesis:** The model sampled previous lives or digested them offline (turn 1 digest.md for og19), rather than re-reading all 23 continuously.

File:line: toolcalls.py tallies; `output/og19_mfm/episode_001/memory/mine/digest.md` timestamp shows written at turn 1

### Time-to-first-milestone (digest overhead)

| Arm | First action | Turn 1 reading | First iron |
|-----|---|---|---|
| og14 (scratch) | 0.280 s/action | N/A | 3,267 steps |
| og15 (1 life) | read previous/life_1/ in turn 1 | Y | ~1,700 steps |
| og19 (23 lives) | read + parse 23 logs in turn 1 | Y | 1,933 steps |

og15 and og19 both paid a digest cost in turn 1 but reached iron faster than og14. Turn 1 overhead was absorbed.

File:line: `output/og19_mfm/episode_001/codex_turns/turn_0001.events.jsonl` shows Python script execution (scan previous logs); `output/og14_mfm/episode_001/codex_turns/turn_0001.events.jsonl` no previous/ scans

---

## Part 6: Systematic Pattern of Reuse

### What transfers
1. **Exact coordinates (on-record facts):**
   - Spawn location (used by all, confirmed in logs)
   - Iron vein position within 1 block (og19 used (-2997.30, 55, -5565) vs digest (-2997.30, 55, -5565.39))
   - Obsidian pool target cell (og9 mined (-2990, 11, -5560), on digest record)
   - **Evidence:** Plan language "recorded descent," "previously verified iron," cited locations match
   - **File:line:** `output/og19_mfm/episode_001/memory/logs.txt:1007` (plan), `mine/digest.md` (record)

2. **Hazard warnings (lava locations, death sites):**
   - og9's LAVA AHEAD note cites prior sightings: "3rd plan the same lava has stopped"
   - og19 digest lists all death coordinates per life with cause
   - **File:line:** `output/og9_mfm/episode_001/memory/logs.txt` LAVA AHEAD text block; `output/og19_mfm/episode_001/memory/mine/digest.md` "Each life and death evidence"

3. **Structured procedures (if written in mine/):**
   - og14 wrote `gravel_cycle.py` (place, mine, walk drop for 1-in-10 flint)
   - og15 inherited og14's scripts but didn't re-use them per turn (og15's turns were 1.7k fewer)
   - **File:line:** `output/og14_mfm/episode_001/memory/mine/procedures/gravel_cycle.py` (exists); `output/og15_mfm/episode_001/memory/logs.txt` shows no gravel_cycle calls

### What does NOT transfer
1. **Visual memory (frames):**
   - 0 previous-life frame views in og19/og8/og9 despite carrying full episodes
   - Previous episodes are on disk (linked under previous/life_*/episodes/) but never examined
   - Reason: No frame query tool in thin contract; episodes.py tools did not access them
   - **File:line:** `vision_use.py` output (0 previous-life frames); `output/og19_mfm/episode_001/memory/previous/` contains life_1..life_23 with episodes/ dirs (present but unread)

2. **Learned GUI procedures:**
   - og14's table re-open at (-3008, 70, -5571) stored in notes
   - og15 re-mined iron nearby but did not cite table re-open
   - og19 did not use stored table locations (only spawned new tables)
   - Reason: thin contract focused on atoms (primitive procedures), not macro re-use
   - **File:line:** `output/og14_mfm/episode_001/memory/notes.md` vs `output/og15_mfm/episode_001/memory/logs.txt` (no reference to og14's table)

3. **Route/path information (grid.jsonl):**
   - Previous lives' walked routes are in previous/life_*/grid.jsonl (walked cells, detour data)
   - Carry arms did not query or follow recorded routes
   - From-scratch arms (og10-og16) also use no grid.jsonl for planning (grid is for post-hoc analysis)
   - Reason: go_to macro is blind (straight-line); grid.above() for pit climbing used live grid only
   - **File:line:** `output/og19_mfm/episode_001/memory/previous/life_1/grid.jsonl` exists; no grep in codex_turns for it

### Why not more reuse?

**Observation:** The thin contract and mfm protocol move the onus to the model. The model must decide what to read and when. We observed:
- Turn 1 digest (og19, og20) was written to mine/digest.md but then rarely re-read (0 grep digest.md in later turns in og19's codex_turns)
- `tools/episodes.py --previous` was called in 4-11% of og9/og19 turns, but mostly for text (--json flag), not to retrieve visual frames
- Hazard coordinates made it into plans via natural language (LAVA AHEAD note), not systematic lookup
- Rediscovery of known sites (water, gravel, ore) was common because the model optimized locally (feed says "forage nearby") rather than querying digest

---

## Concrete Examples: Where a Frame Would Have Changed the Decision

1. **og9, step ~17976 (Nether death):**
   - Event: "bridge_forward picked the dropped bucket up (empty) and the pool took 4.0 per 10 ticks"
   - Previous life (life21) frame ep_000xyz would show: water bucket in hand on the lava rim
   - Decision change: If the model had viewed life21's frame at the pool, it might have recognized the risk and equipped the sword first
   - File:line: `output/og9_mfm/episode_001/memory/logs.txt` line ~8900 (death at 17976)

2. **og19, step ~1933 (iron descent):**
   - Event: "Center on the recorded descent column"
   - Previous frame from og14 or og21 at the descent would show: exact shaft pose, torch placement spot
   - Decision change: Would have avoided the "shaft over your head" warning note (line 1046) if the frame had shown the risk
   - File:line: `output/og19_mfm/episode_001/memory/logs.txt:1046` note about mob risk in open shaft

3. **og9, step ~13358 (obsidian hunt after diamond vein drying):**
   - Event: "Portal frame at z -5559, x -2991..-2988, y 11..15"
   - Frame from og21's obsidian mining would show: exact block positions, pour technique, safe approach angle
   - Decision change: Portal placement took ~350 ticks per miss (line 300 from progress.md); frame would show correct approach
   - File:line: `progress.md` line 300-303

4. **og19, turn 1 (23 life parsing):**
   - Decision: Which 3 lives to query next (og19 spent turn 1 reading all 23 summarized)
   - Frame memory would have enabled: prioritization by recent success (color-code frames by milestone reached)
   - Current output: Generic text digest, equal weight to all lives
   - File:line: `output/og19_mfm/episode_001/codex_turns/turn_0001.events.jsonl` Python script run time (421,353 bytes for turn 1, unusually large)

5. **og15, step ~9200 (stalled furnace setup):**
   - Event: "governor: STALLED at this spot... this one (use_until_gui) does neither"
   - Frame from og14's successful furnace open would show: exact cursor position, GUI state
   - Decision change: Would have re-tried pose-replay instead of abandoning the furnace location
   - File:line: `output/og15_mfm/episode_001/memory/logs.txt` governor stall note

---

## Summary Statistics (File Evidence Inventory)

| Metric | Source | Value |
|--------|--------|-------|
| Previous/ reads (carry arms, median) | toolcalls.py | 48 cmds / 251 turns = 19% of turns |
| Previous/ reads (from-scratch arms) | toolcalls.py | 0 cmds / 347 turns |
| Digest written (og19, og20) | mine/digest.md timestamp | Turn 1 (0-48 ticks) |
| Digest re-read (og19) | grep digest.md in codex_turns | 0 times |
| Previous-life frames viewed | vision_use.py | 3 (og15 only) / 600+ total views |
| Coordinates cited in plans (og9 obsidian) | logs.txt text match | (-2990, 11, -5560) ✓ |
| Obsidian speed (carry vs scratch) | compare.py milestones | og9: 8.6k (carry) vs og12: 6.1k (scratch, faster) |
| Iron speed (og19 carry vs og14 scratch) | logs.txt milestones | og19: 1.9k (carry) vs og14: 3.3k (scratch, slower) |
| Gravel re-discovery (og19 vs og14) | logs.txt milestones | Neither reached flint (og14 ran out of steps; og19 at 14/24) |
| Deaths (carry vs scratch, same code) | compare.py | og8/og9: 3 ea. vs og10-13: 1-3 ea. (no difference) |

---

## Conclusion

**Memory reuse occurred at the textual level:** carry arms read previous logs, extracted coordinates and hazard warnings, and cited them in plans. **Spatial/visual reuse did not occur:** 0 previous-life frame lookups in og19/og8/og9, despite carrying full episode stores. **Outcome independence:** carry and from-scratch arms reached similar milestones at comparable speeds on the same code. The 30% speed gain for early carry arms (og5, og9 vs og10-13) vanished after code fixes (og12/og13 comparable to og9 at obsidian). **The digest mechanism worked** (og19 summarized 23 lives in turn 1), but the model did not leverage it systematically—turn-by-turn plans regenerated strategies rather than executing stored ones. **Future reuse:** indexing previous-life frames by goal (e.g., "show me obsidian mining success frames") and querying them by task state might close the visual reuse gap.

---

## Appendix: File Paths for All Evidence

- Carry arms output: `/Collab/MFM-grid/MCU/output/og{3,4,5,14,15,19,20}_mfm/episode_001/memory/`
- Carry arms output (merge checkout): `/Collab/MFM-grid-merge-mcu/output/og{6,7,8,9,16,17,18}_mfm/episode_001/memory/`
- Compare data: `scripts/compare.py` (milestones, steps, death counts)
- Tool calls: `scripts/toolcalls.py` (previous/ read counts, episodes.py queries)
- Vision use: `scripts/vision_use.py` (frame lookups by type)
- Digest content: `output/og19_mfm/episode_001/memory/mine/digest.md`
- Codex commands: `output/og19_mfm/episode_001/codex_turns/turn_*.events.jsonl`

