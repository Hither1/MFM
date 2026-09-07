# Self-harness: the model writes and keeps its own procedures

Opened 2026-09-07 08:3x from the spatial-grid track (`../mfm-three-layer.spatial-grid/`);
user decisions of that morning: thin contract from now on (og12 is the last full control);
procedures.py keeps simple atoms and the model adds its own; the model may write and keep
files and scripts. References: jerber/arc-code ("the harness has no solver, planner, world
model, or grid tooling; the model writes those while it plays"; Opus 5 high 24/25, ~$540)
and arXiv 2606.00579 (sandboxed coding agents decompose media with self-authored scripts;
log-driven self-distillation of skills from execution traces: OmniGAIA 61.4 -> 76.7).

## Stable Anchor

- Scientific question: does an mfm agent that writes and KEEPS its own scripts and
  procedures (within a life, and carried to the next life) score higher on the dragon
  half-task than the same agent with the fixed 77-procedure library and a fixed contract?
- Target claim: (a) within a life, the self-harness arm reaches at least the control's
  milestones per step with no more deaths; (b) across lives, the second life seeded with
  the first's scripts reaches mine_obsidian earlier than the first did.
- Success criterion: (a) half-task milestones at the 10h cap >= the control (og13: thin,
  fixed library, from scratch, same code otherwise); (b) >= 3 self-written procedures each
  called >= 3 times within a life; (c) life 2's mine_obsidian step < life 1's.
- Constraints: the benchmark's green/I-O/scoring layer untouched; no hand-written
  coordinates or world facts in any prompt (the model's own scripts are its own); `--sites`
  off; gpt-6-astra reasoning high, `--thin`, 60k steps, session-turns 0 + compaction,
  320x180, 10h wall cap; `CODEX_BIN=$HOME/ccr/bin/codex`; ports outside 9071-9087 and
  9098-9103; check node load and `/` free space before a launch; never edit `Collab/MFM`.
- Budget: two arms in parallel on the local node (the six running arms end 14:35-17:50).
- Non-goals: tick-level model-written reflexes (bunker, lava escape, fightback, drown,
  pillar stay harness-owned: a model turn is 20-60 s, lava is 4.0 hp per 10 ticks); the
  worldmodel/logbook/direct baselines; the full contract; deleting procedure code (the
  composites stay importable for the reflexes, macros_* and the stages).

## Evidence behind the decisions (2026-09-07 morning)

- Thin vs full (carry og9 vs og8: 15/24 at 8675 and 0 deaths vs 15/24 at 12884 and 3
  deaths; scratch og11 vs og10: 13/24 vs 12/24): thin wins both pairs on milestones per
  step; thin is slower in wall-clock (5.8-6.4k vs 7.0-10.2k steps/h) because it re-reads
  references/ ~5 times a turn (og9: procedures.md read 904 times in 184 turns).
- The 77 procedures: 46 used across og3..og11 (~5000 actions); look_abs 850, RAW 622,
  equip_hotbar 450, mine_ahead 323, craft 244, go_to 234, mine_forward 215. The
  procedure index is 18.7k of the thin contract's 31k characters.
- Multimodal memory: every turn carries the current 320x180 view (1 image), ~10% of turns
  also the harness's event sheet (the last three event frames); the model opened an extra
  image in 32-59 exec cells per ~190 turns (zooms of the current frame), queried episodes
  by place 3-9 times per run vs 25-55 by recency, and never opened a previous life's
  frame. The archive is stored, not retrieved.
- Model-written files: the model runs bash/python every turn (og9: 216 bash cells per
  100 turns) but `memory.sweep_foreign` deletes everything outside AGENTS.md, logs.txt,
  actions.json, grid.jsonl, references/, episodes/, index.jsonl, tools/, previous/ at the
  end of each turn: zero model-written files survive (og9 workspace listing).

## Current Cycle

- Working hypothesis: with the library cut to atoms and its own files kept, the model
  rebuilds the composites it needs as scripts (a chop, a strip mine, the obsidian dig)
  and reuses them, and the carry of those scripts is worth more than the carry of logs.
- Main uncertainty: the turn budget (~190 turns per 10h) -- arc-code spent 12.7k lines
  over 25 games; here every turn spent writing code is a turn not mining.
- Next decisive experiment: og14 (thin + `--atoms` + `--own`, from scratch) vs og13
  (thin, fixed library, from scratch, already running from 07:50).
- Expected signal: og14 >= og13 on milestones per step; >= 3 reused self-written
  procedures; deaths <= og13.
- Fallback: if og14 writes nothing, the contract's "write it after it worked twice" rule
  is the first suspect (S4); if it writes but regresses on crafting, restore `craft`'s
  companions (place_and_open, furnace_load/take) to the atom set.

## Slices (MCU code on `spatial-grid-merge` in `Collab/MFM-grid-merge-mcu`, tests in `MFM-grid/tests`)

- S1 `--atoms`: the registry the contract shows is the atomic set -- look, look_at,
  look_abs, equip_hotbar, open_inventory, close_inventory, cursor_to_slot, cursor_to_cell,
  gui_click, gui_right_click, craft, place_and_open, furnace_load, furnace_take, place_at,
  use_at, use_held, go_to, watch, mine_ahead, collect_drops, fill_bucket, pillar_up, eat,
  throw, drop_and_pickup, stow_items, discard_stack (28). `craft` stays: 9 of 24
  milestones are crafts and the raw-cursor craft cost ~450 steps in the first run. The
  task-shaped composites (chop/harvest_tree, strip_mine, stair_down, dig_down, mine_until,
  find_lava, make/mine_obsidian, build_portal_frame, light_portal, the Nether/End set,
  build_*, bridge_forward, scan_around, ...) are unregistered under the flag; their code
  stays. V1: test asserting the index under the flag; stage: a 2x2 craft, a go_to and a
  mine_ahead through the atom set only.
- S2 `--own`: the mfm arm keeps `mine/` (any file the model writes there: scripts, notes,
  procedures) across turns and the carry links it into `previous/life_<i>/mine/`. V1:
  tests/test_previous.py carries mine/.
- S3 own procedures: at the start of every turn the harness lists `mine/procedures/*.py`;
  each is a script that prints a PLAN (the same JSON the model writes: procedure calls and
  raw actions) given `--info <json>` on stdin (position, inventory, health, the [MAP]
  cells) and its own `--args`; it runs in a subprocess with cwd = workspace, a 10 s
  timeout and no network; its stdout goes through `parse_actions` (same caps, same
  validator, depth 1: an own procedure may call built-ins, not other own ones). The name
  is the file name (cannot shadow a built-in); the first docstring line is its index entry;
  a failure is one [NOTE] with the last traceback line, never an exception. V1: rig test
  with a scripted `chop.py` composed of look_at + mine_ahead + collect_drops; a broken
  script yields the [NOTE] and the rest of the plan runs.
- S4 contract (thin): a "Your own procedures" section -- where to write, the interface,
  "write one only after the same sequence worked twice, and call it by name from then
  on", that `mine/` persists and is carried; a "Frames are files" line pointing at
  `tools/frames.py` and scripting over frames instead of viewing (arXiv 2606.00579). The
  index shows built-ins then own procedures with their call counts. V1:
  tests/test_thin.py.
- S5 launch og14 (thin, `--atoms --own`, from scratch, 421aa327 + S1-S4) against og13.
  Read-out at the caps: milestones per step, deaths, obsidian step, number of own
  procedures and calls per procedure, RAW/look share of actions, steps per hour,
  references reads per turn.
- S6 (after og14): og15 = og14's settings seeded with og14's life ONLY (log + mine/): the
  across-lives claim.
- Phase 2, if S5 holds: S7 log-driven self-distillation between lives -- one separate
  codex pass over life N's logs.txt + mine/ writes `mine/procedures/*.py` and
  `mine/notes.md` for life N+1 (the paper's skill mining), compared with the raw carry.

## Decisions And Blockers

- 2026-09-07 user: thin from now on; procedures.py keeps atoms, the model adds its own;
  the model may write and keep files and scripts (L2, approved).
- Open: whether own procedures may call other own procedures (depth 1 for now).

## Verification Contract

- S1-S4: V1 each (a unit test + one rig stage where the runner executes the path);
  the existing 77 tests stay green; the stage output under `<MCU>/logs/stages/`.
- S5/S6: E1 -- one arm each, compare.py + the own-procedure counts; a claim is frozen only
  with a second seed.

## Next Action

(2026-09-07 10:15) og14_mfm in flight (thin + `--atoms --own`, from scratch, gpt-6-astra high,
60k, session-turns 0 + compaction, 320x180, ports 9104/9114, 10h cap ~19:30, live MFM-grid/MCU
at ed34754c). Control: og13 (thin, fixed library, scratch, 07:50, cap ~17:50). First own
script seen at 10:07 (north_stair.py, progress.md 10:10). Watch: further scripts and their
call/failure counts, milestones per step vs og13, deaths, the RAW/look share, and the
steps/h gap (3.1k vs 6.8k: at this rate og14 reaches ~30k steps by the cap; the read-out is
per step). At the caps: compare.py on both, `own_calls`/`own_failures` from the report and the
[OWN] blocks. Then og15 seeded with og14's life only (S6).
