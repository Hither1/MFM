# Progress

## 2026-09-06
- 23:25-23:45 evidence pass over ob1-ob4/obf1/obf2 and the 148 historical runs (findings.md;
  scripts/). Worktrees created: MFM-grid (spatial-grid @ f0fdb77), MFM-grid/MCU (spatial-grid @
  54ed3c9f), `.venv` symlink to MCU-AgentBeats/.venv. No code yet.
- Running arms (other session's): ob4_mfm (half, died at step 1365 to a mob at y 26, rebuilding),
  obf2_mfm (full, 4 table re-open failures by step 1073).

## 2026-09-07
- Layering (user): harness-level changes live in `mcu_worldmodel/` and apply to every arm
  (grid, map-aware macros, watchdog, presentation); MFM-mechanism changes are flags on the mfm
  arm (`--corridors`, `--expect`, `--frames`, `--session-turns N --frame-size`).
- Slice 1 (harness) DONE: `mcu_worldmodel/grid.py` (walked/floor/blocked/water/lava/hazard/
  placed/opened cells, edges from the walk, BFS routes, `grid.jsonl` beside the log, kept by
  the sweep, carried under previous/); runner hooks: per-tick `grid.observe`, hazards on hits
  and deaths, water from the water guard, lava cells from the guard's sighting, the placed cell
  + pose from place_and_open, the opening pose from every use_until_gui success;
  `go_to` detours once over walked cells (`_goto_stalled`), `use_until_gui(item=)` replays the
  opening pose before the cell estimate (`_pose_replay_tick`), the dig_down water refusal queues
  a walk along the trail to a cell 8+ blocks from water (`_queue_water_escape`); the turn
  message gains [RECENT] (last 6 entries, harness record), [MAP] (grid.summary) and a 2x2
  event-frame sheet as a second image (every arm but direct). Tests: tests/test_grid.py 14
  green; chassis pins re-recorded for prompts/report keys/workspace (+grid.jsonl,
  +attach/events.png) and the recall prompt; logbook logs.txt and actions unchanged.
  MCU commit: see git log (spatial-grid).
- Slice 2 DONE: harness -- `governor.check_plan` (CELL_STREAK_VETO 4 null entries of any label
  at an 8-block cell, or STALL_STEPS 600 without a productive one -> a plan that neither moves
  nor opens a screen is dropped for one no-op; SWITCH_STEPS 1200 adds "change the objective";
  `_stall_hint` names the placed table/furnace with a walked route or the farthest walked cell
  within 12 blocks). MFM options (mfm arm only, flags on worldmodel_purple_agent.py):
  `--expect` (EXPECT line parsed from the briefing, echoed as [EXPECTED]/[OBSERVED] next turn,
  MFM_EXPECT_NOTE in the contract), `--frames` (tools/zoom.py written for mfm, MFM_FRAMES_NOTE,
  `frame=` pointers on lava/pour/death/water lines of [KNOWN SITES] via previous.frame_for),
  `--corridors` (previous.corridors_from_log: runs of log sections at y<=14 with no damage/lava/
  death, <=8 blocks apart, >=8 blocks long; merged; up to 3 nearest rendered as DRY CORRIDOR when
  obsidian/diamond/iron is open; MFM_CORRIDOR_NOTE), `--frame-size WxH`. Tests:
  tests/test_watchdog.py 8 green; pins: only chassis_logbook_report_keys moved (+watchdog);
  logbook logs/actions unchanged (the fake's drift keeps its cells short of the streak).
- Replay (tools/grid_replay.py, trail interpolated between per-action positions = a lower
  bound): ob chain 13 runs: 120 blocked go_to, detour available 69 (57%); water refusals 28,
  escape available 27 (96%). Historical half 43 runs: 110 blocked, 72 detours (65%); 41
  refusals, 35 escapes (85%). Historical full/diamond 202 runs: 1148 blocked, 744 detours (65%).
  Gate (>= 50%) passed: S2a stays in the main line.
- Grid edges now only join cells <= 2 apart (a death/portal jump is not a walk).
- Stages written: s17_pond (walk to the rim, fill, refused dig -> escape along the trail, dig),
  s18_reopen (flat + the obf2 hole case, re-open by pose), s19_detour (L trail, 2-high wall,
  go_to detours and arrives).
- Stage s18_reopen: 13/13 green (flat and the hole case: the replayed pose re-opens the table in
  45 ticks after a 6-block walk away; `pose_reopens` 1 each). Stage s17_pond run 1: 9/10 (refusal,
  escape along the trail in 33 ticks, 8+ blocks from the rim; the last dig failed only because the
  stage never equipped the pickaxe -- fixed, rerunning). s19 running.
- Stages green on the engine (MFM-grid/MCU/logs): s17_pond run 2 10/10 (`logs/stages/s17_pond_*`),
  s18_reopen 13/13, s19_detour 8/8 (stalled 7.8 blocks short of D, detoured over 37 walked cells,
  arrived in 162 ticks). Gate for the half run passed.

## 2026-09-07 02:11-02:40 -- og1/og2 launched, then stopped: protocol change

- 02:11 `og1_mfm` (sites+corridors, 22 seeds incl. ob1..obf3) and 02:15 `og2_mfm` (same +
  session-turns 8, 320x180) launched from MFM-grid/MCU. Before the stop og1 showed the
  harness mechanisms in the wild: fill_bucket at the remembered pond (step ~600), the
  refused dig queued the walk along its own trail (15 cells, "8+ blocks from every water
  cell"), one blocked go_to detoured over 9 walked cells. `[MAP]`/`[RECENT]`/
  `[EXPECTED]`/`[OBSERVED]` all present in the turn-2 codex prompt (rollout inspected).
- 02:20 user: no previous-life memory except MFM's own reuse; the earlier mfm reuse was
  contaminated. Both arms stopped with `scripts/stop_arm.py --go` (24/24 pids).
- Slice 3 (this commit): `--sites` mfm option (default off) gates known_sites / corridors
  / frame pointers / `previous/sites.json`; `--corridors` requires `--sites`. The carry
  keeps linking the lives' records under `previous/` (widened from logs/index/episodes/grid
  to the whole record minus machinery: `previous.NOT_CARRIED`), merged `previous/index.jsonl`
  for `tools/episodes.py --previous`. Contract: MFM_PREVIOUS_NOTE rewritten as the carry
  note (the model reads), MFM_SITES_NOTE / MFM_FRAMES_SITES_NOTE only with --sites, the
  chain section's two [KNOWN SITES] sentences only with --sites (`prompts._with_sites`).
  Pins re-recorded: logbook/mfm AGENTS.md lose those two inert sentences (logbook never
  had the block); logs/actions pins unchanged. Tests: test_previous +1 (carry without
  sites), suites test_previous/pins/grid/watchdog/obsidian/retrieve/torch/seal green.
- Launcher renamed `scripts/launch-og.sh` (ARM/GP/PP/STEPS/SESSION_TURNS/WM_EXTRA/OB_SEEDS);
  default seeds = 12 first-gen lives, `--expect --frames --retrieval`.
- 03:10 og4 (step 5577-5657): LAVA AHEAD at 1% of the lower view ((-2991, 11, -5561), y 11);
  the model poured at the rim from 0.3 blocks ("something behind blocks the way back"),
  then `mine_obsidian` broke 3 blocks, none obsidian -- the ob1/ob1b failure (a sliver seen
  from afar is flowing lava: cobblestone after the pour; only SOURCE blocks turn to obsidian).
  The LAVA AHEAD note says "THIS IS THE LAVA THE OBSIDIAN NEEDS" at any fraction; the
  sliver-vs-lake distinction (LAKE_FRAC 8%) lived only in the [KNOWN SITES] digest. Candidate
  harness slice for the next generation: the note itself names a <8% sighting a sliver
  (likely flowing) and a >=30% one a lake; not changed mid-run.
- 03:40 merged dragon-obsidian into spatial-grid. MCU: hither/dragon-obsidian (bunker at the
  first hit bcb009bb, standoff/scoop/mine_obsidian aims 52a452ef, kit milestones open ce4d9404,
  carry-the-workshop doctrine 2eb053fb) merged cleanly in a scratch worktree
  `Collab/MFM-grid-merge-mcu` on branch `spatial-grid-merge` (da93083e) -- NOT in the live
  `MFM-grid/MCU`, which og3/og4 import from; fast-forward it when they end. MFM: origin/
  dragon-obsidian merged in place (tests/test_seal.py, test_obsidian additions, pins); conftest
  gained `MFM_MCU_ROOT` so the suite can run against another MCU checkout; pins re-recorded on
  the merged MCU; 60 tests green (`MFM_MCU_ROOT=.../MFM-grid-merge-mcu`). The MCU submodule
  pointer stays at c6bbf978 until the live worktree moves.
- og3 died at step ~2700 to a zombie in its dark shaft at y 32->23 (health 10 -> 6 -> 2 while
  the plan said "dig down to Y12"; the runner's counter-attack dealt 0 and the sprint back was
  blocked) -- the case the merged bunker slice addresses. It had read the carried logs
  itself (rg over previous/life_*/logs.txt, then sed of life_2/life_3 sections) and cited a
  lava pool near (-3049, 7, -5537) from them.
- 04:05 sliver slice (harness, all arms; MCU spatial-grid-merge 019b91de, MFM 5ef3287): the
  LAVA AHEAD advice under 8% of the lower view names a SLIVER, keeps its cells off the
  no-argument pour's record (`lava_slivers` stat) and asks for a closer 8%+ sighting; at lake
  size the pour sentence stands. tests/test_lava_note.py (2). og4 lost its water on the
  sliver at (-2991, 11, -5561) and is bucket-less at y 10 with ~3000 steps left; og3 found no
  drops at its death site and is rebuilding from cobblestone.
- Next generation (when og3/og4 end): fast-forward `MFM-grid/MCU` to `spatial-grid-merge`
  (bunker at the first hit, standoff/scoop aims, kit milestones open, workshop doctrine,
  --sites off, sliver note), bump the MFM MCU pointer, relaunch og5 (single-turn) / og6
  (8-turn, 320x180) with seeds = 12 first-gen + og3 + og4 (clean lives: no pushed sites).
- 04:5x **og4_mfm banked `mine_obsidian` (14/24) at step 11883** -- the milestone no dragon run
  reached in 148 historical runs, and the ob1..obf3 chain never did on the half task. Clean
  protocol: no pushed sites, seeds = 12 first-gen lives, `--expect --frames --retrieval`,
  8-turn sessions, 320x180 frames. Route: fill at the pond (step 844), the trail escape, dig
  to y 11, a 1% sliver at (-2991, 11, -5561) (step 5577), pour at its rim (the water was
  scooped back, then lost later at (-2992, 10, -5559)), `mine_obsidian` on the wrong cell,
  ~6000 steps of tunnelling around the spot (three more LAVA AHEAD stops there, an 8%
  reading), then `look_at` + `mine_ahead(280)` on `(-2992, 10, -5556)` from a bridge: three
  stone blocks, then `mine_block obsidian +1`. So the sliver held at least one source and the
  first pour did make obsidian; finding the cell cost 6,300 steps.
- og4 final (result.json score 25.0; 11999 steps; 4 milestones, last at 11883; 0 deaths):
  fill 844, fill->descent-8 414 steps (historical half-run median 612), fill->LAVA AHEAD
  4540, churn 0.11 (historical median 0.21); grid 179 walked / 7 blocked / 16 water / 3
  lava cells; goto 16 calls, 6 blocked, 2 detours (1 arrived); water escape 1; watchdog
  plan stalls 18, governor nudges 15; lava flagged 5; recall block on 97 of 98 act turns;
  previous: 12 lives, 0 pushes. og3 at 11335: 13/24, 1 death, fill 1353, fill->descent 1163,
  fill->lava 7083, churn 0.05.
- og6_mfm (8-turn, 320x180) launched from the merge worktree (`MFM_ROOT=MFM-grid`, ports
  9096/9106, output under `MFM-grid-merge-mcu/output/og6_mfm`) with seeds = 12 first-gen +
  og4 (og3 still running, so not a seed for og6); og5 follows from the live worktree after
  og3 ends, seeded with og3 + og4.
- og3 final (score 41.67; 11999 steps; 13/24 ledger, 1 death): fill 1353, fill->descent-8
  1163, fill->LAVA AHEAD 7083, churn 0.05; grid 297 walked / 4 blocked / 21 water / 6
  hazard cells; goto 10 calls, 4 blocked, 1 detour; watchdog 0; recall block 76/77 turns.
  Scoring: og3 (41.67) outscored og4 (25.0, the obsidian arm) because after its death it
  re-made the kit's milestones (wooden/stone pickaxe, table, furnace...) and the half-task
  scorer credits only what happens in the run -- the finding behind dragon-obsidian's
  ce4d9404/2eb053fb, now merged (og6 banked 9 kit milestones in its first ~1500 steps).
- 03:37 og5_mfm launched from the fast-forwarded live worktree (MCU c45367f8 = spatial-grid
  == spatial-grid-merge; MFM pointer 5fd9294): single-turn, 640x360, seeds = 12 first-gen +
  og3 + og4, ports 9095/9105. og6 (8-turn, 320x180, seeds +og4) running since 03:28 from the
  merge worktree.
- Pit slice (harness; MCU spatial-grid-merge feb65878, MFM 91f0199): `scripts/pitstalls.py`
  over 208 runs -- 431 of 1,387 go_to blocked notes (31%, 144 runs) were made standing
  1.5+ blocks below the avatar's own recent trail. og5 sat at y 63-64 under its y 69 trail
  from step 552 (three stalled go_to, the detour "stalled too", governor tabu at 2/3).
  `grid.above` finds the rim cell (walked, within 6 blocks, 2+ higher); `_goto_stalled`
  queues `pillar_up(rise)` and the same go_to again once (`pit_climbs` stat) or, without
  blocks, says so. tests/test_grid.py +2. Not in the live worktree yet (og5 runs from it).
- og6 died at step ~7290 at (-3050, 10, -5554), y 12, 11/24 (score-relevant kit milestones
  banked early): under attack the merged bunker reflex "dig two down, cap" did not break the
  floor ("still at y 12") while the diamond pickaxe was swinging (use_item events); the
  model then believed itself sheltered and ran mine_forward(380); health 11 -> 7 -> 2 -> dead.
  Evidence for the dragon-obsidian seal slice (bcb009bb): the bunker dig fails under
  knockback / on that floor and the fallback flee came too late.
- og6 final (score 45.83 = 11 milestones, the last at step 1442 -- the kit re-made under the
  doctrine; 1 death at step ~7290; never filled the bucket; churn 0.10; grid 511 walked / 44
  water cells; goto 6 calls, 5 blocked, 0 detours; watchdog 1). og5 at 8330: 13 milestones
  (last 7175), no water yet, 0 deaths, churn 0.00, 4 detours; the watchdog dropped a
  mine_ahead/aim_at_ore plan after 2234 stalled steps (since 4941).
- 04:1x og7_mfm (8-turn, 320x180) launched from the merge worktree with the pit-climb code
  (feb65878+), seeds = 12 first-gen + og3 + og4 + og6 (`EXTRA_SEEDS`), ports 9097/9107.

## 2026-09-07 04:3x -- the Astra-aligned protocol (user decisions)

- User (after the comparison with wz1119/Codex-Minecraft-Gameplay and da03/astra-plays-gta):
  GPT-6 is available -- use gpt-6-astra at reasoning effort high; the step budget may be
  very long; set a wall-clock cap; plan approved ("立即开搞"). Memory mechanisms (mfm and
  the baselines) must stay supported by whatever aligns.
- What is borrowed, in order of expected impact: game-time budget (12k steps = 10 min of
  game time; their diamond took a night), one session for the whole run (session-turns 0 +
  compaction + 320x180 frames), the model, a look after every batch (short blind horizons),
  a thin contract with model-held control (`hold`/`watch` on ground-truth conditions).
  Not borrowed: pixel-compare checks (we have ground truth), real time, no memory.
- og8_mfm launched from the merge worktree: gpt-6-astra high, 60k steps, session never
  dropped, codex compaction at 100k tokens, 320x180, `--expect --frames --retrieval`, seeds
  = 12 first-gen + og3/og4/og6, ports 9098/9108, CODEX_MAX_CALLS 20000, wall-clock cap 10h
  (`logs/og8_mfm_wall.pid` -> stop_arm.py). Launcher gained COMPACT and WALL (3a64abd1).
- Next slice: `--thin` contract (one page + references) with `hold(keys, ticks<=100)` and
  `watch(until=<truth condition>, max_ticks)`; procedures stay available but optional;
  only the lava guard and the hit reflex kept as hard reflexes. Orthogonal to memory mode.
- og5 final (score 54.17 = 13 milestones, last at 7175 -- the kit re-made plus diamond gear;
  0 deaths; never filled the bucket; churn 0.03; grid 336 walked / 10 blocked; goto 8 calls,
  6 blocked, 5 detours; watchdog 2). Equals obf2's 54.17 record, on the half task.
- `--thin` + `watch` slice (MCU spatial-grid-merge; MFM tests/test_thin.py, pins re-recorded
  for the new procedure): the mfm contract goes 14,305 -> 4,767 words; references/
  {procedures,gui,skills,survival,control,more}.md hold the rest, read on demand.
- 04:5x og9_mfm launched: og8's protocol (gpt-6-astra high, 60k, one session + compaction,
  320x180, 10h cap, `--expect --frames --retrieval`) plus `--thin`; seeds = 12 first-gen +
  og3/og4/og5/og6 (og8 has no og5: it started before og5 ended). Ports 9099/9109. A/B:
  thin contract vs the full one, same model and budget.

## 2026-09-07 05:0x -- og7 final, og8's death in its own shaft

- og7 final (gpt-5.6, 8-turn, pit-climb code, seeds 12 first-gen + og3/og4/og6): score
  54.17 = 13 milestones, `mine_diamond_ore` at step 8587 (historically 3% of from-scratch
  runs, median step 11444; a `aim_at_ore` + `mine_ahead(ore_watch)` pair on a visible
  vein at y 9); 0 deaths; never filled the bucket; churn 0.12; governor 45; goto 9 calls,
  1 blocked, 1 detour. Equals og5/obf2's 54.17 (`logs/og7_mfm_result.json`,
  compare.py on `output/og7_mfm/episode_001/memory/logs.txt`).
- og8 (gpt-6-astra high, 60k) died at step 2603, y 9, 11 milestones, the kit dropped.
  Evidence (`output/og8_mfm/episode_001/memory/{logs.txt,grid.jsonl}`): walked
  (-3009, 12, -5569) at 2487 and (-3009, 11, -5569) at 2501 -- a vertical `dig_down`
  shaft; the hit came at 2523 while a torch went up on the shaft wall (place_at y 13);
  damage 4.5 per hit (a zombie on HARD) at steps 2523, 2543, 2563, 2583, 2603 -- exactly
  every 20 ticks (a zombie's attack cooldown) at y 11, 10, 9, 9, 9. The bunker reflex dug
  two blocks and reported "capped ... nothing can reach you in here" at 2563+; the hits
  went on inside the capped hole: the zombie had fallen down the shaft INTO the cell and
  the dig took it along. The model then opened the inventory to craft sticks (hit to 3),
  planned `fight(diamond_sword)` -- the sword was in the main inventory, not the hotbar --
  and died 7 ticks into the fight. s8_bunker's docstring already recorded "a zombie
  (run 4) followed the avatar INTO the hole" as "the model's to run from"; the reflex
  precedence armed the bunker on the first hit and never re-evaluated it ("not abandoned
  for further hits"), so the flee/fightback branches written for the melee cadence
  could not fire while a pickaxe and a block were in the hotbar.
- Slice (MCU spatial-grid-merge, agent.py): a melee-cadence hit while the bunker digs
  abandons it for the fightback with the best HOTBAR weapon (sword > axe > pickaxe,
  `_weapon_slot`, full-charge swing period per class); the fightback turns its aim a
  quarter after 16 ticks of swings that land nothing (`fightback_sweeps`); at the bottom
  of the avatar's own shaft (`_in_shaft`: a walked cell straight above) it fights to the
  end instead of handing over to the flee below CRITICAL_HP; a hit taken INSIDE a capped
  hole within 600 ticks (`_in_hole`) arms the same desperate fightback, closing an open
  screen first (`hole_fightbacks`). Notes name the weapon, the reason and the next step
  ("close the shaft over your head FIRST"). Tests: tests/test_fightback.py (4) + the
  reflex tests (38 passed). Stage s20_shaft (hard, a zombie WITH AI dropped down the
  runner's own 4-block shaft; A: diamond sword in the hotbar, B: pickaxes only) running
  from the merge worktree, `logs/stages/s20_shaft_0907_051153`.
- og8 at step 5176 (11 milestones, recovering: mining cobblestone at y 61 for a furnace);
  og9 at 3315 (12 milestones incl. iron_pickaxe, 0 deaths, heading for the pond).
- s20_shaft, five runs: the hand-over worked from the first run, the blind fightback did
  not -- 0-1 swings landed in 80 ticks and both rounds died at the fifth hit. Probes
  (`/data get entity` in the chat overlay, avatar pos every 10 ticks): the push leaves the
  two in opposite CORNERS of the 1x1 cell (avatar at (-.7, -.7) of it), every quarter
  turn of the sweep 45 degrees off; `forward` into the wall auto-jumped the eye over the
  mob's head (airborne at 3 of 5 probes). Fix: aim at the cell's centre from where the
  avatar stands now on every empty sweep (else an eighth of a turn), no forward in a
  cell; a shaft bottom with a sword fights at the FIRST hit; the bunker gives way the
  moment its swings hit the mob (damage_dealt moved -- og6's "floor did not break").
  Final run (`logs/stages/s20_shaft_0907_05xx`): A (sword) killed in 3 swings, 20 -> 8.8
  hp; B (iron pickaxe, og8's hotbar) bunker intercepted at tick 26, killed, 20 -> 2 hp.
  14 checks, 0 failed. MCU spatial-grid-merge 027b2cd9; tests/test_fightback.py (6).
- User (05:2x): keep monitoring; the memory-reuse runs (og8, og9) end when they end, no
  more of them; the next results are the new settings FROM SCRATCH (no memory).
- 05:26 og10_mfm (full contract) and og11_mfm (`--thin`) launched from the live worktree
  MFM-grid/MCU (fast-forwarded to 304bae53: thin/watch/compact, the launcher's new
  `NO_SEEDS=1`): gpt-6-astra high, 60k steps, session-turns 0 + compaction, 320x180,
  `--expect --frames --retrieval`, NO previous lives, 10h cap, ports 9100/9110 and
  9101/9111. They run the code BEFORE the shaft-fight slice (027b2cd9 came after).
- og9 at 5691: 13 milestones incl. mine_diamond_ore (the earliest diamond on record in
  the chain: og7 8587, historical median 11444), 0 deaths, bucket filled. og8 at 7262:
  11 milestones, rebuilding after the death.
- 05:5x og9 (thin, gpt-6-astra high, MFM carry) banked `mine_obsidian` at step 8675 --
  15/24, 0 deaths: the second obsidian in the chain (og4 at 11883) and a half-task record
  (62.5 if it ended now; 54.17 before). Sequence: 10% lava seen at (-2992, 11, -5559)
  ~step 6000 with the bucket in hand; `make_obsidian()` interrupted by lava damage (the
  douse spent the bucket); `mine_obsidian` at (-2992, 10, -5560) found nothing (governor
  stall 92 steps); flint_and_steel crafted (14/24 at 7889); bucket refilled twice at the
  spot, two hand pours ("pour onto the lip's top, let it spread, recover the source");
  `mine_obsidian(x=-2990, y=11, z=-5560)` succeeded at 8675. Both pit-climb false
  positives (og8 "54 blocks below", og9 "44 blocks below" the shaft mouth) came from
  grid.above before c9566fd8's max_rise cap; og8 re-made iron_pickaxe (13/24).
- 06:0x og8 (full contract, gpt-6, MFM carry) banked `mine_obsidian` at step 12884 (15/24)
  at the same pool og9 used (the carry: og4's pour was recorded there), mined 6, and DIED
  a second time at 14349: `mine_obsidian` emptied (-2988, 11, -5559) at the rim, the lava
  guard stopped the plan (27%), and the next turn's `go_to` west crossed that cell inside
  the guard's 150-tick cooldown -- fell onto the lava under it, 4 hp per 10 ticks, doused
  at 1 hp, dead with 5 obsidian and the kit (`output/og8_mfm/.../logs.txt` 7674-7744).
  Slice (MCU spatial-grid-merge, after c9566fd8): the guard re-checks every new action
  (cooldown only within the stopped action; deliberate lava macros exempt); the mined
  obsidian cell goes on the grid as lava and the note says to fill it from the rim
  (`place_at(x, y, z, cobblestone)`); the post-break drop sweep is gone (the drop burns
  when lava lies under it). tests/test_obsidian.py asserts the mark + the note; 74 pass.
- og9 at ~12.4k: 12 obsidian mined, 11 placed -- building the portal frame at
  (-2991, 13..14, -5559); 15/24, 0 deaths.
- 07:3x Lava-pool deaths (og10 at 8870, og11 at 10326, og8 #2 at 14349 -- all at the pool
  just found, 4.0 hp per 10 ticks): og10's first hit (14% lava in the frame) armed the
  BUNKER, which dug into the pool; og11's first hit got the 180-degree turn and the
  runner's back-step walked it deeper (its own pour had emptied the bucket). Slice (MCU
  spatial-grid-merge, s21_lava_escape): lava contact by its signature (a 4.0 loss with
  any lava in view, or sunk 0.4+ below the dry trail cell beside it -- inside the pool the
  frame reads 2%), no bunker with lava in view, the escape walks back toward the last
  dry walked cell with the jump held (instead of a blind back-step). Stage: A (bucket)
  one hit, doused, out, 20 hp; B (no bucket) two hits, out, 15 hp; 14 checks, 0 failed.
  tests/test_lava_escape.py (3); 77 pass. Live MFM-grid/MCU fast-forwarded (og10/og11
  still run the code they started with).
