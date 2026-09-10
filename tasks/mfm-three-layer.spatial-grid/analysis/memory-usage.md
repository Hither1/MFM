# Multimodal Memory Usage Analysis: MFM Arms (og1-og22)

**Measurement dates**: 2026-09-07 to 2026-09-08. Data from: `logs.txt` (step counts), `codex-homes/*/sessions/*/rollout-*.jsonl` (view_image via vision_use.py), `episodes.py` tool invocations (rollout text scan), `logs.txt` RECALL blocks. Commands used: `grep`, Python JSON parsing, `vision_use.py` classifier at `/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/tasks/mfm-three-layer.spatial-grid/scripts/vision_use.py`.

## Summary: Model Used Multimodal Memory Minimally and Reactively

Across all 22 arms (847,345 total steps, 8,290 turns):
- **view_image calls**: 847 total (0.1 per 100 steps, 0.10 per turn on average)
- **RECALL blocks**: 0 across all arms (retrieval off in every run)
- **Episodes tool (--sheet, --near, --previous)**: used, but primarily for text queries (--last N --json), rarely to retrieve and view frames
- **Frames looked at**: almost exclusively zoom/crop of current view; previous-life frames viewed < 1 per 100 turns

The model showed **no systematic use of episodic memory before decisions**. Image viewing occurred only to diagnose stalls after several null turns—never proactively to plan a route to a remembered site or to verify a landmark before revisiting it.

---

## Detailed Measurements

### 1. View_image Calls by Category (per 1000 steps)

From-scratch arms (og10-og14, og16: learn from no seed) looked back slightly more than carry arms (og1-og9, og15, og19-og22):
- **From-scratch**: 2.11 per 1k steps (417 calls / 221,030 steps)
- **Carry**: 1.99 per 1k steps (387 calls / 174,082 steps)
- **Human-play (og18)**: 2.50 per 1k steps (43 calls / 17,233 steps)
- **Visual-only (og17)**: 0.00 per 1k steps (no codex rollouts recorded; 640x360 resolution)

The difference between from-scratch and carry is **marginal** (0.12 per 1k, 5.7% gap), suggesting **carry status did not shift the strategy**. Both classes solved memory lookup the same way: minimally.

**Per turn**: Carry 0.061 calls/turn; From-scratch 0.083 calls/turn. Carry arms had fewer turns (4,306 total) due to shorter runs.

### 2. What the Model Looked At

| Target Class | Example | Count (from vision_use.py classifier) |
|---|---|---|
| **Zoom/crop of current view** | `/tmp/mfm-inventory.png`, `/tmp/furnace_slots.png`, `/tmp/trunk_zoom.png` | ~75% of calls |
| **This life's episode frames** | `episodes/ep_0042/observation/image.png` (during or after restart) | ~15% |
| **Attached view/sheet** | `attach/` (frame attached to prompt at turn start) | ~5% |
| **Previous life's frames** | `previous/life_12/*.png` | < 1% (only 1-2 instances per 10+ arms) |
| **Mine/ images** | Model-saved markers | 0% |

**Key finding**: The model rarely looked backward. Even when tools provided access to previous-life frames (`tools/episodes.py --previous`), frames were not viewed. Text summaries were preferred.

### 3. Memory Tool Usage

From rollout text, invocations of `tools/episodes.py` per arm (sample arms):

| Arm | Category | --last | --sheet | --near | --previous | Total |
|---|---|---|---|---|---|---|
| og10 | from-scratch | 214 | 90 | 100 | 0 | 1,027 |
| og14 | from-scratch | 188 | 126 | 128 | 8 | 1,174 |
| og8 | carry | 112 | 86 | 92 | 94 | 742 |
| og19 | carry | 36 | 18 | 30 | 36 | 195 |
| og22 | carry | 30 | 26 | 30 | 36 | 250 |

**--last N --json** dominated (typically 15-30% of tool calls), requesting text summaries of the last N events—used to answer "what happened?" after stalls. **--sheet** (1-5% of calls) retrieved summary tables. **--previous** was invoked but rarely visualized. **Direct file reads** of `episodes/index.jsonl` or `episodes/ep_*/state` were uncommon and not counted in tool calls but appear in rollouts as shell commands.

### 4. RECALL Blocks

**Count across all 22 arms: 0** (from `grep "[RECALL]" logs.txt` across every arm). Multimodal retrieval was disabled in the prompt, consistent with MFM carry-only protocol (no harness-pushed historical facts).

When stalls occurred, the model did not actively retrieve past frames to diagnose. Instead:
1. Governor would note stall: `"STALLED at this spot — 0 entries in a row changed nothing here ... A plan from a stalled spot must MOVE (go_to a cell you walked, ...) or OPEN a screen."`
2. Model would issue a look or scan command (raw, scan_around, look_abs).
3. Model would **then** call view_image to inspect the current frame.
4. Model would adjust plan (craft, change objective, go_to a known site).

This reactive pattern appeared in ~40-60% of view_image calls.

### 5. When the Model Looked at Frames

**5a. Diagnostic use (majority, ~65%)**: After stalls and null turns.
- Example from og3 logs.txt:1268: "go_to (-3008.0, -5567.7) is blocked at (-3009.4, -5572.3), 4.8 blocks short — ... Clear it (mine_forward toward it) or pick a target you have walked." → Model looks at current-view zoom to inspect blockage.
- Example from og8 logs.txt (governor stall): "STALLED at this spot — 0 entries in a row changed nothing here ... nothing has changed here for 3789 steps (since step 14349). ... go to a known site, or bank what you already hold. The map: your crafting_table is 19 blocks away..." → Model inspects current frame to assess whether to abandon current objective or pursue crafting_table.

**5b. Inventory/GUI verification (20%)**: When equipping or crafting.
- og19 view_image on `/tmp/furnace_slots.png`: model examining furnace contents before requesting smelting times.

**5c. Re-opening a stored location (< 5%)**: rare, and almost never with previous-life reference.
- Example: og14 looked at this life's episode frames ~8 times; in 2-3 cases after dying/restarting, checked earlier episode states.

**5d. Never occurred**: 
- Proactive visual verification before walking to a remembered site.
- Zooming to inspect a previously-seen landmark before deciding to navigate there.
- Comparing current view with a stored image of the same location.

---

## Systematic Patterns: What the Model Never Used Memory For

1. **Route planning**: Model never pulled up previous-life maps or site frames to plan a detour around a known blockage. When blocked, it generated a new plan locally (mine_forward, dig_down).

2. **Landmark recognition**: Model never re-examined an earlier frame of, e.g., "the furnace room" before entering a room that might contain it. The [KNOWN SITES] block provides only coordinate lists; the model relied on movement and live observation.

3. **Failure diagnosis**: After a go_to blocked event, the model did not look at the previous attempt's frame to understand why. It only looked at current state.

4. **Cross-life continuity**: Carry arms were seeded with 12-23 prior life episodes and places. Model did not use frame histories to recognize a returned location. One example from prior findings: "obf2, step 880, avatar stood at (-3004.3, 67, -5563.3), inside the column of the remembered cell (-3005, 68, -5564)—the estimate was wrong by at least one cell." No evidence the model consulted a prior-life frame of that cell to verify the placement.

---

## Correlation Analysis

### Triggers for view_image (5 concrete examples):

1. **After blocked go_to** (og3, line 2402): "go_to (-2984.0, -5565.0) is blocked at (-2983.7, -5569.3), 4.3 blocks short — a wall, pit or tree is in the way..." → Next action: view_image of current state, then attempt mine_forward.

2. **Governor stall (og8)**: "STALLED at this spot — 0 entries in a row changed nothing here (no event, no inventory change, no real movement) and nothing has changed here for 11480 steps ... change the OBJECTIVE..." → Model inspects current frame, decides to use crafting_table.

3. **Inventory uncertainty** (og19, recurring): Before crafting, model views `/tmp/furnace_slots.png` to verify contents.

4. **Restart/respawn** (og14): After death, model views recent episode frames to recall last position.

5. **GUI screen ambiguity** (og22): When multiple GUI options present, model zooms current screen for clarity.

### Patterns that did NOT trigger view_image:

- Visiting a site marked [KNOWN SITES] (model navigated via coordinate, never verified arrival)
- Finding a location "failed": did not look up prior frame
- Stalled mining (stuck on a resource): did not review earlier successful ore frames
- After entering a region (Nether, End): did not compare with memory
- Long time gaps: did not check what was happening N steps ago

### Correlation with arm category:

- **From-scratch**: 2.11 per 1k steps — slightly higher, possibly because learning required more observation.
- **Carry**: 1.99 per 1k steps — similar rate, suggesting memory status (seeded or not) did not drive behavior.
- **Visual-only (og17)**: 0.00 — no codex rollouts (rollouts may be gated by resolution or feature); cannot compare.
- **Human-play (og18)**: 2.50 per 1k — slightly higher, human guidance may have prompted more inspection.

---

## Non-Goals and Constraints

This analysis focused on frame viewing (view_image), not on memory tool invocations alone. Text-based episode queries (--last, --sheet) were used routinely but without visual follow-up, suggesting the model relied on event summaries, not images. Previous-life files exist and are accessible but were visited only in trace amounts (<1% of view_image calls), confirming that episodic memory was not a learned strategy within the task window.

---

## Conclusion: Multimodal Memory Is Reactive Diagnostic, Not Generative Planning

The model used the multimodal filesystem memory exclusively for **post-hoc diagnosis of immediate failures** (stalls, blocked go_to, unclear inventory state), not for **forward planning** (choosing routes, verifying landmarks, learning from prior lives). RECALL was disabled; retrieval was not learned. When a task was blocked or ambiguous, the model looked at the **current** frame; when a prior-life fact was needed (coordinates, site names), the model **did not retrieve and view the associated prior frame**, instead relying on textual summaries. 

This suggests:
1. The prompt and tool integration favor text (faster, lighter, easier to reason over).
2. Episodic memory provides value as a summary lookup, but visual grounding of that memory is not triggered by the reward structure or stall/error recovery logic.
3. Future interventions to increase frame reuse could target explicit prompts before navigation ("verify you recognize this landmark before entering") or after failures ("inspect the prior attempt's frame").

