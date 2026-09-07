# Task plan: a visual-input-only setting (proposal, 2026-09-07 12:10)

User (11:5x, before sleeping): "我觉得我们还可以尝试只有 visual input 的 settings". Not launched:
the variants below are materially different arms; the user picks one.

## What the model sees today (thin, og13)
Each turn: the 320x180 frame (HUD included: health and hunger bars, the hotbar with item
icons -- legible but small at 320x180; see episodes/ep_000191), PLUS text: `[STATE]
pos=(x,y,z) pitch yaw`, the inventory with counts and slots, health/food numbers, the
harness notes (with coordinates), [MAP] (walked cells, hazards, water, lava cells),
[RECALL] (episodes near here), the milestone ledger. Its memory `logs.txt` carries the same
text for every past entry. About half of the procedures take absolute coordinates
(go_to, look_at, look_abs(yaw), place_at, use_at, mine_obsidian, make_obsidian, ...).

## Variants
- **V1 pixels-only (strict).** The model gets the frame(s) and the step budget; no position,
  no inventory text, no health numbers, no [MAP]/[RECALL] coordinates, and the notes are
  scrubbed of coordinates; the procedure set is cut to the egocentric atoms (look deltas,
  forward/back/strafe ticks, mine_ahead, collect_drops, the GUI cursor by cell index, craft
  by name, use_held, pillar_up, eat). Inventory/health come from the HUD in the frame
  (frame size should go to 640x360 so the icons and bars read). The harness keeps its own
  telemetry for the reflexes (bunker, lava escape, guards) -- the ablation is what the
  MODEL sees, not what the runner knows. Cost: ~2 days (prompt/log scrubbing across
  memory.write_action, episodes tools, [MAP]/[RECALL], the procedure index; a chassis
  test; a stage). Expected: much weaker navigation (no coordinates = no place memory),
  a clean answer to "can it play from pixels".
- **V2 no-telemetry, coordinates kept in the harness's replies.** As V1 but the harness
  notes still name coordinates when THEY act (LAVA AHEAD at (...), placed at (...), YOU
  DIED at (...)), and go_to/look_at stay: the model never sees its own position line but
  can target places the harness named. Cheaper (~1 day: drop [STATE]/[INV]/health lines
  and [MAP]/[RECALL] from the turn prompt and from logs.txt; keep everything else).
  Expected: the model learns to ask the frame for what the text used to say; still
  navigates by named places.
- **V3 vision-heavier, not vision-only.** Keep the text, add vision: a four-yaw panorama
  (4 frames) at the start of every turn and the event frames, 640x360. Not what the user
  asked, listed only as the control for "does more vision help at all".

## Recommendation
V2 first (it isolates "telemetry text vs frame" at a day's cost and keeps the action
interface, so its milestones compare with og13/og16), then V1 if V2 holds up. Both need
`--frame-size 640x360` (the 320x180 HUD is at the edge of legibility) -- check the codex
image token cost first (the frames are attached every turn).

## Open question for the user
Which variant, and is the HUD-in-frame acceptable as the only source of health/food/
inventory (V1), or should inventory text stay (V2)?
