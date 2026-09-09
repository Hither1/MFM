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
- 07:4x og8 DIED a third time at step 18261, at the pool again (`logs.txt` 9040-9121): back
  for the kit dropped at death #2 with no water bucket in the hotbar, `mine_forward` east
  at y 15 fell four blocks to (-2987, 11, -5559) beside the lava, `bridge_forward` picked
  the dropped bucket up (empty) and the pool took 4.0 per 10 ticks; the old code's escape
  "only stepped you back 0.5 block(s)", the model strafed toward a remembered water cell
  and died at 1 hp. Four of the day's five deaths are at the lava pool the run had just
  found; all four ran code before 421aa327 (og8/og9 loaded agent.py at 027b2cd9 or
  earlier, og10/og11 at 304bae53). og8: 3 deaths, 15/24, kit lost again.
- og9 (thin, carry) at 17.4k: portal frame at z -5559, x -2991..-2988, y 11..15, 0 deaths.
  Placements recorded (place_at notes): both sides x -2991 / -2988 at y 12-14, the bottom
  (-2990, 11) (-2989, 11), the top (-2989, 15); (-2990, 15) never reported. Three
  flint_and_steel tries at (-2990, 12) (below face) "no visible effect" at 17.2-17.4k --
  the frame is not complete. Mechanism seen at 17166: `place_at(x=-2989, y=15, z=-5559,
  face=above)` from (-2989.3, 13, -5555.6) reported "placed at (-2989, 15, -5559)" (the
  note trusts use_item +1 / obsidian -1), but the block landed on the nearer stone the
  ray hit first (the model later mined "the misplaced obsidian near (-2990, 14, -5557)",
  290 ticks each way). The runner cannot see where a placed block lands; the portal frame
  costs ~350 ticks per miss. og9 rate ~5.7k steps/h: the 10h wall cap (~14:45) binds
  before the 60k budget.
- og10 (full, scratch) at 23.3k: 12/24, last milestone at 4581 (iron_pickaxe), 14k steps
  since the pool death rebuilding (chasing torches, 69 governor notes); og11 (thin,
  scratch) at 14.9k: 13/24 (diamond ore at 8549), rebuilding a furnace + iron after the
  death at 10326.
- 07:50 og12_mfm (full) and og13_mfm (`--thin`) launched FROM SCRATCH from the live
  MFM-grid/MCU at 421aa327 (shaft-fight, obsidian-hole, lava-escape, grid.above cap all
  in): gpt-6-astra high, 60k, session-turns 0 + compaction, 320x180, `NO_SEEDS=1`, 10h cap
  (~17:50), ports 9102/9112 and 9103/9113. Load 24/255 cores, 703 GB RAM free, `/` 9.8 GB
  free (a codex home is ~150 MB). Purpose: the from-scratch read with the pool deaths
  fixed (og10/og11 run the code before the fixes); starting now instead of at 15:26
  saves the wall-clock cap eight hours.
- 09:2x og9 (thin, carry) lit the portal and entered the Nether at step ~17.5k (16/24,
  netherrack at 17.8k), then DIED twice: (1) at a Nether lava lake (-389, 26, -688): the
  model tried to bridge over the lake ("hold jump while placing cobblestone"), the lava
  hit armed the BUNKER (pre-421aa327 code), which dug into the lava -- "the cap did not
  place (the dig met lava)", 4 hp per 10 ticks, dead with the kit; (2) after the respawn,
  walking to the recorded tree at (-3004, -5576) it fell down its OWN first-life shaft to
  (-3005, 9, -5581) and died on landing. The shaft mouth is a walked column in the grid
  but not a hazard cell: `go_to` does not detour around it (candidate slice: mark
  dig_down mouths as hazard for walks). og9 went back through the portal at 25.6k with
  a rebuilt kit (2 deaths, 16/24).
- 09:25 status: og8 32.2k 15/24 3 deaths; og9 25.6k 16/24 2 deaths; og10 34.5k 14/24
  (flint_and_steel) 1 death; og11 22.0k 13/24 1 death; og12 (full, scratch, 421aa327)
  14.7k 13/24 with mine_obsidian at step 6134 -- the EARLIEST obsidian on record (og9
  8675, og4 11883, og8 12884) -- 0 deaths, one douse at the pool (the lava escape
  fired, no bunker); og13 (thin, scratch, 421aa327) 11.6k 13/24 (flint_and_steel) 0
  deaths. Both post-fix arms are alive past the pool.
- 10:10 og8 and og9 STOPPED (user rule 10:0x: a run that has gone very long without
  progress may be stopped; `stop_arm.py --go`, 26 of 26 pids, the two wall watchdogs
  killed by pid). Final numbers (compare.py, worldmodel_report.json):
  og8 (full, carry): 34.4k steps, 15/24 (last: mine_obsidian 12884), 3 deaths (2603,
  14349, 18261); the 5 obsidian mined at 12.9-14.1k were lost at death #2 (obsidian -5 at
  14349) and none was mined in the 20k steps since -- the run was still at the pool at
  34.2k "building three walls around a water basin ... storing water will free the bucket
  for collecting lava to cast the portal". toolcalls: 266 turns, 3.0 commands/turn,
  episodes.py in 15% of turns, previous/ 39 commands, image items 0.
  og9 (thin, carry): 30.2k steps, 16/24 (last: netherrack 17714, the record), 3 deaths
  (17976 Nether lava lake + bunker; 19286 its own first-life shaft; 26939 fell to y 30.8
  tunnelling into a Nether cliff, "the lost kit fell into lava"); respawned empty at 26939
  and by 29.7k had rebuilt only a wooden + stone pickaxe, a stone sword and a table,
  chopping trees at (-3032, 65, -5591) stuck in leaves. toolcalls: 251 turns, 3.5
  commands/turn, episodes.py 22%, previous/ 48, image items 0.
  Carry pair, final: thin 16/24 (obsidian at 8675) vs full 15/24 (obsidian at 12884),
  both 3 deaths, steps/h 5.6k vs 6.3k.
- 10:10 status of the five arms left: og10 (full, scratch, 304bae53) 38.2k, 15/24
  (mine_obsidian at 35170, then death #2 at 35834), 8.3k steps/h, cap 15:26; og11 (thin,
  scratch, 304bae53) 24.9k, 14/24 (flint_and_steel 22274), 1 death, 5.4k/h; og12 (full,
  scratch, 421aa327) 18.8k, 13/24, no milestone in the 12.7k steps since mine_obsidian at
  6134 (no flint_and_steel: walking the river banks south of spawn for gravel), 0 deaths,
  8.4k/h, cap 17:50; og13 (thin, scratch, 421aa327) 15.1k, 14/24 (mine_obsidian 13358,
  9 obsidian in hand at (-2959, 11, -5641)), 0 deaths, 6.8k/h; og14 (thin+atoms+own)
  1.8k, 11/24, 3.1k/h (see the self-harness progress). Rule for og12: if it has no new
  milestone by 12:30 (about 30k steps) it is stopped under the same user rule.
- 10:20 og10's two deaths (8870 and 35834) are the SAME pool cell (-2957, 9..10, -5511)
  and the same mechanism on the pre-fix code (304bae53): the lava hit armed the bunker,
  "the dig met lava", 4 damage per interruption down to death, the kit lost both times
  (the second time 660 steps after mine_obsidian at 35170). Pool-fix read-out so far:
  pre-fix scratch arms og10/og11 3 pool deaths between them; post-fix og12/og13 0 deaths
  at 18.8k / 15.1k steps, both past the pool with obsidian.
- 10:35 SLICE: the SHAFT AHEAD guard (MCU spatial-grid-merge, next commit after
  ed34754c; tests/test_shaft.py, stage s23_shaft_ahead). Mechanism of og9's death #2,
  re-read from the log: at 19233 a stair_down from (-3004.6, 69, -5576.3) facing north
  ended at (-3004.6, 67.5, -5579.7); mine_forward(100) then broke the wall into the
  y 9..67 shaft dug at steps 3955-4663 at (-3005, -5581) one block north, the avatar
  walked into the column and fell 58 blocks (YOU DIED at (-3005, 9, -5581)). og9's
  grid.jsonl holds that column as 59 walked levels (a second one, (-2999, -5566), 54
  levels); dm4_wmv9 died the same way earlier (agent.py's death note). Slice:
  `Grid.drop_ahead(cell)` = a column of CONSECUTIVE walked levels whose top is the cell
  or the one under it, 4+ deep, last walked downward (a pillar_up or a shaft pillared
  out of is walked upward last: solid; a staircase is one level per column; a fall
  records no intermediate levels). `agent._shaft_guard` runs in observe beside the lava
  guard: candidate cells along the last tick's motion out to a jump's reach at that
  speed (1..5 blocks, sp x 14) and along the facing at 1 and 2 blocks when the queued
  action holds forward/back; on a hit it drops the plan, ends a flee/fightback, marks
  the hazard for [MAP] and notes SHAFT AHEAD with the levels, the dig steps and the fall
  (hp, FATAL at 23+). Once per column and plan entry; nothing when no plan and no moving
  reflex runs; a teleport (>1 block a tick) is ignored.
  Stage s23 (a 1x2 hole 9 deep through a lit platform): first run, 5 of 7 FAILED and
  taught three things -- the go_to servo sprint-jumps (0.35/tick; it cleared the hole
  in the control and a 1-block lookahead fired in mid-air), the cooldown keyed by cell
  fired 3x on one walk, and SNEAK + FORWARD WALKED OFF THE EDGE (the avatar ended at
  y 78.9 in the hole): sneaking does not hold an edge in this simulator, so the guard
  has no sneak exemption and the note says so. Second run after the rework: control
  (raw forward, map blank) fell 9 blocks (took 6 damage); guarded go_to stopped on the
  platform in 13 ticks with one note; raw forward from 0.8 block off the edge stopped;
  sneak + forward stopped: 7 checks, 0 failed. Unit tests: 87 pass (84 + 3).
  Observation, not changed: the lava guard's cooldown `action_num <= last + 1` covers
  the NEXT plan's first entry (action_num advances when the stopped entry closes), so a
  go_to re-issued as the first entry within 150 ticks is not re-checked -- candidate.
  The live MFM-grid/MCU is NOT fast-forwarded while five arms run from it; ff before
  the og15 launch (only agent.py/grid.py change, both loaded at start).
- 10:45 SLICE: the lava guard's cooldown (MCU spatial-grid-merge, the commit after
  a71e86cc; tests/test_lava_cooldown.py). og8's death #2 re-read: LAVA AHEAD (27%)
  fired during Action 617 `mine_obsidian` (action_num 616 while it ran); the next plan's
  FIRST entry, Action 618 `go_to(x=-2989, z=-5558.5, within=0.2, n=30)` at step 14294,
  ran with action_num 617, inside `same_action = action_num <= last + 1`, and the guard
  stayed silent while the walk crossed the cell the obsidian had come out of (douse at
  14348, dead at 14349 with 5 obsidian). action_num advances when the stopped entry
  closes, so `+ 1` covered exactly the next plan's first entry -- the comment beside it
  claimed the opposite. Fix: `<= last` (the same entry only). The test replays og8's
  sequence: stop at 616, the refilled same entry stays quiet, the go_to at 617 eight
  ticks later is stopped again. 88 tests pass. The stage s23 run at 10:28 had shown the
  same window on the shaft guard (its second stop landed on the second column because
  the first was still in the +1 window) -- the shaft guard shipped with `<= last`.
- 10:41 og12 (full, scratch, 421aa327) banked flint_and_steel at ~21.8k (14/24, 0 deaths),
  15.7k steps after mine_obsidian at 6134 -- the 12:30 stagnation rule lapses; it has the
  obsidian and the lighter, the portal is next. og13 (thin) also 14/24 with 9 obsidian.
- 10:5x USER RULE CHANGE: runs are no longer stopped for lack of progress -- every arm
  runs to its wall-clock cap (10h) and is stopped there by the launcher's watchdog only.
  og8/og9 (stopped 10:10 under the earlier rule) stay stopped: a purple process cannot
  resume a life mid-episode, their scores are banked.
- 11:35 status. og10 (full, pre-fix) 46.5k, 15/24, death #3 at 45621 at the SAME pool
  (-2962, 10, -5512), the old bunker dug into lava again ("no water bucket in your
  hotbar, so it only stepped you back 1.1 block"); rebuilding tools. og11 (thin, pre-fix)
  28.8k, 14/24, death #2 at 27469 on the surface at (-2982, 64, -5667) DURING
  `craft(furnace)` with the screen open: no damage note at all in the 147 ticks (og8 has
  3 damage notes with a GUI open, so health is observed there) -- an instant kill, most
  likely a creeper at the freshly placed table; the kit lost: 2 diamonds, the iron
  pickaxe, flint_and_steel, 82 cobblestone. og12 (full, post-fix) 26.8k, 14/24, 0
  deaths, mining beside the water at the pool (-2955, 10, -5513): the portal is next.
  og13 (thin, post-fix) 19.0k, 14/24: it built the portal and ENTERED THE NETHER by
  ~18.7k (og9 needed 17.5k with a carried life), then died at 18818: go_to at y 50 walked
  into a 13-block hole (y 37, "a hole the walk cannot climb"), LAVA AHEAD 45%, it pressed
  forward+jump+use and fell further to y 28, a melee mob followed it down, the bunker
  cap failed, the fightback dealt 0, dead with the kit; now chopping spruce at spawn.
  og14 (thin+atoms+own) 5.2k, 12/24 (mine_iron_ore 3267), 0 deaths, ~3k steps/h.
  Pool-fix read-out so far: pre-fix scratch arms 4 pool deaths (og10 x3, og11 #1),
  post-fix 0 at the pool in 45k combined steps. The Nether is the next death cluster:
  og9 x2 and og13 x1, all falls into holes/lava on Nether terrain, none at the pool.
- 12:00 AUDIT (user 11:4x: "look at the existing problems and improve the systematic
  ones"). Four read-only tracks in `findings-0907/` (A phase costs + scripts/phases.py,
  B flint/bucket, C obsidian->Nether, D falls/Nether) plus E wall clock (mine). What
  held up as SYSTEMATIC, with the evidence, and what was done (MCU 6f79b0e6, tests 92):
  1. Lava REPEAT clause sent a bucket-carrier away from its pool: og13 stops at 5764
     (2%) and 5820 (4%) at (-2998, 12, -5554), the second with "tunnel away ... do not
     target this spot again"; it obeyed and searched 7.6k steps for another pool
     (obsidian at 13358). og12 took obsidian at 6134 from the SAME pool ((-2996, 11,
     -5553), five sliver stops) by ignoring the clause. 17 of 21 lava stops before the
     first obsidian across og8-og13 are slivers (<10%). FIX: with the bucket and the
     obsidian open, a sighting that grew since the last stop in the cell says CLOSER.
  2. Flint: og12 15.5k steps between obsidian and flint_and_steel, og11 11k, og6/og14
     never found gravel (B). The contract had the 1-in-10 rate but not that gravel can
     be placed and broken again, nor where it lies. FIX: one contract sentence.
  3. Mid-air cells on the map: og13's 13-block fall (18768) recorded cells at y 39-49;
     grid.above() (min_rise 2..max_rise 8) took the y 39 one for a rim, the stall branch
     queued pillar_up(2) at the bottom of a 13-block hole (D). FIX: grid.observe skips a
     tick that drops faster than 0.3 blocks (free fall after ~1.7 blocks); standing
     ticks always record.
  4. Unplanned falls: og13 18768 (13 blocks, then 9 more on a jump, dead), og9 26888
     (20 blocks into Nether lava, dead); the plan kept running after each (D: 9 Nether
     falls, 3 deaths; 89 Overworld falls, 0 deaths). FIX: _fall_guard drops the plan
     on landing after a 4+ block free fall with a FELL note (Nether clause). Stage s24.
  NOT systematic / not changed: A's "governor refusals are the bottleneck" (a count,
  not a cause; the refusals are the symptom of stalls already handled); C's "portal
  frame never placed" for og12 (it holds 7-8 obsidian, still mining -- no stall); the
  portal-frame miss (og9, one miss, ~350 ticks; og13 10/10). E: wall clock per turn is
  the same for every contract (57-67 s), steps/h differ only by ticks per plan (full
  129-167, thin 87-120, atoms 49); the model's first command each turn re-reads the
  last plan's log sections -- a prompt change for og15+, not now.
  Phase costs (A): kit 182-1021 steps; diamond_sword -> obsidian median 12.4k (og12
  5.9k, og10 34.9k with a death); lava sighting -> first obsidian: og9 1.7k, og12 2.1k,
  og13 7.6k (item 1), og10 26.3k (death + rebuild).
- 12:2x og16_mfm launched 11:59 from MFM-grid-merge-mcu at 6f79b0e6 (thin, scratch, all new
  guards; ports 9105/9115; cap ~21:59): og13's twin on the new code. og17_mfm (thin +
  `--visual-only`, 640x360, ports 9106/9116) launched next -- see
  tasks/mfm-three-layer.visual-only/task_plan.md. Nether audit F in findings-0907/.
- 12:35 og16/og17 FAILED TO START at 11:59/12:14: launched from MFM-grid-merge-mcu without
  MFM_ROOT, run-arm.sh put `$ROOT/..` (= Collab) on PYTHONPATH and the purple died at
  import (`No module named 'mfm'`); the green server of the first og16 start outlived its
  wrapper on 9105 (killed by pid 52621 after checking its cwd). Relaunched with
  MFM_ROOT=.../MFM-grid: og17 (thin + `--visual-only`, 640x360) 12:16 on 9106/9116, og16
  (thin, 320x180) 12:17 on 9107/9117; both verified (no Traceback, first Action written,
  og17's contract has the visual section and no go_to/look_abs, its log no [STATE]/[INV],
  no grid.jsonl; og16's skills.md has the gravel line). Caps ~22:16 / ~22:17.
- 12:40 SLICE from audit F (Nether): `explore_nether(bearing=<yaw>)` walks along a yaw
  instead of an axis with the same tunnelling/bridging, and the FORTRESS IN VIEW note
  now says to call it (it said "travel/go_to toward it"): og9 at 17727 saw nether brick
  at 1% on bearing 61, turned, tunnelled 1.2 blocks with mine_forward, stalled, went west
  and never saw it again -- the only fortress sighting in all runs. MCU e13fe9be,
  tests/test_nether_bearing.py, 98 pass. n=1 evidence; the walk itself is the proven
  explore walker, only the heading is new.
- 12:45 og12 (full, scratch, 421aa327) LIT THE PORTAL AND ENTERED THE NETHER: netherrack at
  30305 (15/24), 0 deaths -- the first post-fix arm to reach the Nether alive (og13 got
  there at 18.7k and died at 18818). Now at (-328, 38, -682) in the Nether placing
  netherrack against a cliff shelf. og14 (self-harness) wrote a second procedure at 10:26:
  `gravel_cycle.py` -- the gravel re-break trick (place a carried gravel, mine it, walk
  over the drop) with guards on the pose and the held item, called 22 times (111 ticks
  each) after "worked twice by hand (7295-7362, 7362-7429)"; its notes: 34 gravel breaks,
  all returned gravel, NO flint. Empirical flint rate across runs checked next.
- 12:50 flint per gravel break, from `[EVENT] mine_block gravel` and `[INV] flint +`:
  og8 1/94, og9 1/2, og10 3/29, og11 7/24, og12 3/28, og13 1/21, og14 0/34 -- pooled
  16/232 = 6.9% (vanilla 10%; the 95% band for n=232 at p=0.1 is ~6-14%, so the sim's
  rate is consistent with 10% and og8's 1/94 and og14's 0/34 are the unlucky tails).
  The contract's "about 1 block in 10" and the new re-break line stand; og14's
  gravel_cycle (34 breaks, no flint) is variance, not a broken mechanic.
- 12:55 status. og12 DIED in the Nether at 30505 (200 steps after netherrack): at (-328, 36,
  -682) LAVA AHEAD 24%, then y 31, 29, 28 -- it slid down a slope into the lava sea and
  burned (5 -> 1 hp), kit lost; respawned, 15/24 banked. og13 died a second time at 24675
  at (-3017, 30, -5570), a zombie fight underground with a stone sword (16 -> 7 -> 3 hp
  in one entry), 14/24. og16 (new guards): FELL guard fired at step 2530 (5 blocks, plan
  dropped, no damage note), 11/24 at 2.9k, 0 deaths. og17 (visual-only): 10/24 at 991
  steps, 0 deaths; 23 turns, 0 view_image, 3 episodes.py calls so far (still in the kit
  phase). og10 15/24 at 53.6k (trying to board a boat), og11 14/24 at 32.8k, og14 12/24
  at 9.1k. All three Nether entries so far (og9 x2, og13, og12) died within 300-400 steps
  of arriving, all at lava: the lava sea at y ~31 is the next systematic problem.
- 13:12 og10-og13 STOPPED on the user's word (their read-outs are in; the compute goes to
  the new settings). Final (compare.py / toolcalls): og10 (full, pre-fix) 54.7k, 15/24,
  3 deaths, 347 turns; og11 (thin, pre-fix) 35.0k, 14/24, 2 deaths, 400 turns; og12 (full,
  post-fix) 33.9k, 15/24 (netherrack 30305), 1 death (the Nether lava sea, 30505), 249
  turns; og13 (thin, post-fix) 27.8k, 14/24, 2 deaths (Nether 18818, zombie 24675), 251
  turns. Pairs: thin vs full on milestones per step -- og11 14 @35k vs og10 15 @55k (og11
  reached 14 at 22.3k, og10 at 28.1k); og13 14 @13.4k vs og12 14 @21.6k, but og12 got to
  15 (the Nether) and og13 died twice; thin faster to each milestone, full survived
  longer. Pool-fix: pre-fix 4 pool deaths in 2 arms, post-fix 0 at the pool in 2 arms
  (their 3 deaths: Nether lava x2, a zombie). Steps/turn: og10 158, og11 87, og12 136,
  og13 111 (E-wallclock). Codex homes of all finished arms moved from /var/tmp to
  /datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes/ (user: not in /tmp);
  future launches set MCU_CODEX_ROOT there. No leftover codex processes from our arms
  (the other codex processes on the node belong to other sessions).
- 2026-09-07 22:1x-23:1x (new session; user: "继续监控当前正在进行的实验；根据系统性问题（下界）改tick
  反射；对于自己写harness的，可以告诉它或者建议它可以写什么（例如反射）；同时开始记忆reuse的线，但是
  不要用harness消化记忆，而是让模型自己消化记忆"). FINAL read-outs at the wall caps (compare.py):
  og16 (thin, scratch, all guards, 6f79b0e6): 43.4k steps, 15/24, obsidian at 41835 (flint
  31383, mine_diamond_ore 7192 after losing the kit), 2 deaths -- #1 at 3179 underground
  (y 30): a melee mob, the bunker's cap did not place ("a melee mob is coming down with
  you"), the fightback dealt 0 hp, 11 -> 6 -> 2 -> dead; #2 at 7263 at y 10: aim_at_ore's
  30-tick walk toward the speckles FELL 4 blocks into a hole beside lava, the bucket was in
  the inventory but not the hotbar so the escape only stepped it back 0.8 block, burned.
  og17 (thin + visual-only, 640x360): 20.4k steps in 10 h (2.0k/h -- 1953 actions, 10
  steps each), 15/24, 0 deaths, flint 10368, obsidian 18259, six obsidian mined and the
  lighter in hand when the cap hit (the portal was next). og18 (human-play, 640x360, cap
  23:25): 16.6k steps, 13/24 (flint 5727), 0 deaths, 22 own scripts (break_*, walk_*,
  level_tunnel, pillar_one, water_descend...), 1232 actions of ~13 steps, health 2/20 since
  ~15.6k, never found lava to pour on (mine/cave_lava.png exists) -- 11k steps at 13/24.
  og15 (self-harness, seeded with og14's life): 3.4k, 12/24, 0 deaths; turn 1 read
  previous/life_1 (22 previous/ commands in 21 turns) and wrote "Prior-life evidence" into
  mine/notes.md by itself; two new scripts (descend_north_step, clear_north_step), og14's
  seven stay under previous/life_1/mine/ (not copied into mine/).
- 22:3x-23:1x NETHER SLICE (the user's "systematic problems (the Nether)"; every Nether visit
  on record -- og9 x2, og12, og13 -- died within 400 steps of arriving, walking, sprinting or
  jumping down a slope or off a ledge into the lava sea at y ~31: og12's last keys were
  forward+sprint+jump from y 36 to 28 with LAVA AHEAD already in its notes). MCU
  spatial-grid-merge c972f3af, live MFM-grid/MCU fast-forwarded:
  1. `agent._nether_lock`: in the Nether every plan action that moves gets sneak, loses
     sprint and a moving jump (pillar_up's vertical jump stays); the runner's reflex ticks
     are untouched; one NETHER LOCK note per visit; the flee reflex never sprints there.
  2. `agent._nether_descent_guard`: every 4th tick the lower view's lava share is sampled;
     a plan entry that has walked the avatar 0.9+ blocks below its start with lava in view
     is dropped with a NETHER DESCENT note (dug descents and the runner's escapes exempt).
     explore_nether re-bases its budget under the lock (18 ticks/block).
  3. The contract's survival text carries the lock (pins re-recorded: the diff is that
     paragraph alone).
  MEASURED (stage runs 22:4x-23:1x, s25 + a per-tick trace): sneaking does NOT reliably
  hold an edge in this engine -- forward+sneak stopped 0.29 over a 1-block step and held
  150 ticks, but fell over a 6-block edge (+0.4) and fell at once when the step under the
  overhang was dug out (the bridge macro's 2026-09-03 note said the same) -- so the note
  promises the pace (0.063 blocks/tick, a quarter of a walk: four times the ticks per
  block for the sampled guards) and the descent guard, never "you cannot step off".
  Tests: tests/test_nether_lock.py (6). Stage s25_nether_lock: 9 checks, 0 failed (the
  crept walk, one note, the played descent dropped within 8 ticks with the note, pillar_up
  rises, the Overworld control covers 5+ blocks in 30 ticks). NOT changed: the lava guard's
  y <= 40 gate (with the sea visible from most of the Nether it would stop every walk).
  Second death cluster left open (not the Nether): underground melee with a failed bunker
  cap and a 0-hp fightback (og16 #1, og13 #2, og11 #2).
- 23:0x LAUNCHED og19_mfm (tasks/mfm-three-layer.memory-reuse: thin + own + the digest note
  + the Nether lock; 23 previous lives -- the 12 first-gen + og3 og4 og12 og13 og14 +
  og8 og9 og16 og17; gpt-6-astra high, 320x180, 60k, 10h cap ~09:03; ports 9123/9133) and
  og20_mfm (tasks/mfm-three-layer.self-harness: og15's settings + `--own-reflexes`, seeded
  with og14's life; ports 9124/9134; cap ~09:05). Both verified: no Traceback, the purple
  args carry the flags, og19's contract has the digest note and 23 lives under previous/,
  og20's has the reflex note; og20 wrote mine/digest.md in its FIRST turn ("read
  programmatically": iron at (-3010, 47, -5597), the flooded lava pocket at z -5679, the
  diamond ore at (-3066, 11, -5667), which of og14's scripts to reuse and which not).
- 23:26 og18 (human-play) at the cap: 17.2k, 13/24, 0 deaths, 24 own scripts / 356 calls,
  1.7k steps/h; flint at 5727 (og16: 31383) but never a bucket to lava -- see
  tasks/mfm-three-layer.human-play/task_plan.md. og19 mined iron at 1933 (og16 2577,
  og14 3267, og15 3318) at (-2997, 55, -5566), a spot of its own 12 blocks from spawn,
  not a recorded vein; its mine/digest.md ("read programmatically from all 23 previous
  logs") + mine/prior_evidence.json were written in turn 1. og20 11/24 at 1050.
- 2026-09-08 01:5x VISUAL-MEMORY TEXT (user: the old analysis -- the mfm prompt describes
  frames as furniture, never names view_image, never asks to look -- "还存不存在"; then
  "文字层面要整体修"). Measured first (scripts/vision_use.py over the codex rollouts, the
  only place view_image calls are recorded): og14 163 calls (138 zooms of the current
  view, 12 this life's episode frames, 7 mine/), og15 29 (21 / 3 / 3 previous-life
  frames), og18 43 (23 / 11), og19 65 (57 / 6), og20 6, og21 9, og22 10 -- all zooms of
  the current view or the attached sheet. The model looks, but almost never BACK; the
  contract listed no image tool (logbook tool line verbatim), named view_image once as
  zoom.py's consumer, [RECALL] cited ids without frames. Fixed across settings (MCU
  spatial-grid-merge, live fast-forwarded; MFM mfm/memory/retrieve.py): the mfm tool
  line names view_image and what it opens (zoom.py only with --frames); MFM_MEMORY_NOTE
  gains **Look back.** (before a walk to a remembered place; after a hit; after two
  failures of one plan; before unwalked ground; before an earlier life's place, with
  the episodes.py query for each); the retrieval note, the turn prompt's hint, the human
  contract and the memory skill name the command; recall_block cites each entry's frame
  path and closes with "view_image the cited frame". Pins re-recorded (logbook pin
  unchanged). tests/test_vision_prompt.py (3). Applies to the next launches; the five
  running arms keep their contracts.

## 2026-09-08 02:xx — references read: VISTA + arXiv 2606.00579; frames-note gate removed

- User handed over https://github.com/joshhhhhan/VISTA (Han, Hu, Qiu, Wu, He, Aug 2026; ARC-AGI-3,
  Opus 5.0 RHAE 100) and arXiv 2606.00579v1 (Chen et al., "Sandboxed Coding Agents are Competitive
  Omni-modal Task Solvers"). Notes in memory `visual-harness-references.md`.
- Mapping: our `--expect` IS VISTA's expect/observe protocol (episodes.py MFM_EXPECT_NOTE cites it; all
  og14+ arms ran it: og14 1539 EXPECT lines / 426 compare lines, og21 377/97, og22 123/72 so far).
  Difference: VISTA's OBSERVED is "all visible changes" (the frame); ours is the harness record
  (moved/descended/inv/events/note) with no frame pointer, so a mismatch never leads to a look.
- Found and fixed a contradiction: MFM_FRAMES_NOTE said "open the frame only when the [STATE]/[NOTE]
  lines cannot answer it" -- a text-first gate against the Look-back doctrine (13d96ba0) and the
  paper's "insufficient exploration of modal content" mode. Now: name the question, then look; one
  look costs one image. MCU 0b76c648 (spatial-grid-merge; live MFM-grid/MCU ff'd). Tests: pins_chassis,
  vision_prompt, visual, thin, skills pass.
- Paper Finding 4 (log-driven self-distillation 76.7 > calibration self-iteration 73.0 > human-written
  skills 70.5 > none 61.4 on OmniGAIA) backs the model-digests-its-own-traces line; their distiller is a
  SEPARATE agent pass over raw logs between runs, ours is the player at life start (og19/og20/og21).
- Candidates (not done): (a) `[OBSERVED]` entries carry the frame path of the episode where the entry
  ended, so a surprise has a one-step look; (b) an offline distiller pass by the model between lives
  (previous lives' logs + episodes -> mine/digest.md + candidate procedures/reflexes) as the
  memory-reuse comparison to in-life digest.
- Arms at 02:04 CST, all alive: og15 12448 steps 13/24 (flint_and_steel); og19 13578 13/24
  (mine_diamond_ore, 2 deaths); og20 9279 12/24; og21 5171 11/24; og22 3652 12/24 (mine_iron_ore, a
  diamond_sword already at 3626 -- the gpt-5.6-sol pair is ahead of og21 at equal steps).
- **og15 banked `mine_obsidian` (14/24) at step 13251** (logs.txt:10830): placed a water bucket on
  lava, recovered the water, mined one obsidian from the ledge with the diamond pickaxe; the EXPECT
  line before it predicted `mine_block obsidian +1, progress 14/24` and matched. First mine_obsidian
  in an mfm arm; the dragon-obsidian anchor lists it as never reached in 148 earlier runs. Still running.

## 2026-09-08 03:3x — memory v2 plan frozen (items 1,2,3,6,8; 4/5/7 as skill examples only)

- `analysis/SYNTHESIS.md` (checked) and `plan-memory-v2.md` hold the evidence and the plan; the user
  chose items 1, 2, 3, 6, 8, "build all, then run", and that hazard avoidance / death forensics /
  phase bottlenecks go to the model via examples + meta hints, not harness code.
- Build order: (2) frames into decisions, (3) session checkpoint, skills examples, (6) distiller
  pass, (8) minimal contract, (1) metrics parsers [worker], launch og23/og24, then the judge.

## 2026-09-08 04:xx — memory v2 built (items 2, 3, 6, 8 + skill examples); og15 15/24, og19 obsidian

- MCU fdafe37a (spatial-grid-merge, live MFM-grid/MCU ff'd): [OBSERVED] frame citations + visible-change
  wording; RECALL bearings, milestone line off; `--then-now`/`--q`; mine/working.md as [WORKING];
  skills: death_sheet.py, known_hazards.py, working memory, death forensics, budget section;
  mcu_worldmodel/distill.py + scripts/distill.{py,sh}; `--minimal`; `--seed-mine`.
- MFM-grid: retrieve.bearing(), then_now() in the episodes tool, tests/test_memory_v2.py (6 tests);
  chassis subset (13 files) green; pins chassis_mfm_agents.md / chassis_mfm_recall_prompt.txt re-recorded.
- Distiller workspace smoke (og14+og15 seeds): 2 lives, 11,243 files linked in 51 s on data3 (`output/distill_smoke`);
  the tool's `--previous --grep` over 2,800 episodes exceeds 120 s -- the prompt says grep the logs.
- Metrics kit (worker, branch metrics-kit -> merged): match_rate / recall_retarget / repeat_deaths /
  procedure_reuse + analysis/metrics-kit-baseline.md. Headline: RECALL cited 0.1 world coordinates per
  turn (re-targeting was bounded by the input, now fixed by bearings); 11 of 19 deaths within 8 blocks
  of a hazard the same life had recorded; 6 of 59 own procedures inherited by name.
- Arms: og15 15/24 (mine_diamond_ore at 17,022); og19 14/24 (mine_obsidian at 16,933); og22's starter
  reflex `fell` fired at 6,064 (first own-reflex firing on record).

## 2026-09-08 03:5x — distiller pass done; og23/og24 launched

- Distiller (`output/og23_distill`, gpt-5.6-sol xhigh, 25 lives = og19's 23 + og15 + og18): 1,106 s, 142+
  commands, GUIDE.md 87 lines (verified places with life/step/frame, 19 deaths each with a rule, phase ladder
  per life), frames.md 11 landmarks, 17 procedures copied under their names (og18's set), reflexes/known_hazards.py.
  Report: `output/og23_distill/distill_report.json`. Fix: codex -o path made absolute (MCU 4b72c3d5).
- og23_mfm (ports 9127/9137): og22's flags + memory v2 + `--seed-mine`; og24_mfm (9128/9138): og23 + `--minimal`.
  Both 60k steps, 10 h wall, seeds = the 25 lives under previous/. Launcher: scripts/launch_og23_og24.sh.
- Monitor restarted with og23/og24 (poll_arms2.sh). og21 14/24 (mine_obsidian at 12,913).
- 04:01 check (turn 2): og23 AGENTS.md 4,304 words (thin) / og24 2,371 words (minimal, references/own.md present);
  both turn-2 prompts carry [EXPECTED] with frame citations and a [WORKING] block (both models wrote
  mine/working.md in turn 1); og23's first briefing: "Prior-life routes and hazards are now digested." No tracebacks.
- 04:2x correction: the monitor's milestone count was a loose grep; og24's EXPECT lines quote "[EVENT] MILESTONE x
  verified", so it read 17/24 where the log has 11 events. Anchored (`^\[EVENT\] MILESTONE`) from now on
  (poll_arms3.sh). Kit phase, real numbers: og24 11/24 at step 1,115 (iron_ingot), og23 9/24 at 683
  (diamond_sword), og22 11/24 at 1,315, og21 10/24 at 991 -- og24 is on the fast side, not off the chart.
- Judge v1 (before the plan_after fix) judged the PREVIOUS turn's plan: 7/30 agreement, 15 "should_have_looked".
  Fixed (section after the step), rules tightened (concrete triggers; "when in doubt, ok"; new label
  stale_rederivation for briefings that grep the log and restate the prompt's numbers wrongly -- a real
  pattern the judge found in og21 turns 59/63/71/75). Hand labels redone on the correct plans: 27 ok,
  2 should_have_looked (re-open the table by pose; walk to the noted pond), 1 should_have_used_memory
  (another jump after RECALL's never-changed warning). v2 run in flight.
- Judge v2 (og21, 30 turns, gpt-5.6-sol high, 04:25): 23/30 agreement with the hand labels; labels ok 20,
  should_have_used_memory 5, should_have_looked 3, stale_rederivation 2. Of the 7 disagreements, 3 are the
  judge being right (turn 103: recovering a placed table/furnace without its frame; 79 and 115: the briefing
  restated the prompt's numbers wrongly after grepping the log) and 4 are one RECALL artifact: 1-tick raw
  `forward` nudges inside plans register "moved 0.0", so the streak line reads "forward changed nothing in its
  last 34 calls ... never changed anything" while the avatar walks fine. Adjusted agreement ~26/30: usable as a
  flagger with a human pass. Fix queued: short raw movement entries leave the streak statistic.

## 2026-09-08 04:36 — all seven arms stopped (user: API cost)

`scripts/stop_arm.py --go og15_mfm og19_mfm og20_mfm og21_mfm og22_mfm og23_mfm og24_mfm` (one PermissionError mid-way on a pid
that had already exited; the dry run afterwards found no wrapper left, ports 9121-9138 free), wall watchdogs killed by pid,
monitor stopped. Final state at the stop:

| Arm | Steps | Milestones (last) | Deaths | Reflex fires |
|---|---|---|---|---|
| og15 | 21546 | 15/24 (mine_diamond_ore) | 0 | 0 |
| og19 | 22783 | 14/24 (mine_obsidian) | 2 | 0 |
| og20 | 16885 | 13/24 (flint_and_steel) | 0 | 0 |
| og21 | 15232 | 14/24 (mine_obsidian) | 0 | 0 |
| og22 | 9334 | 12/24 (mine_iron_ore) | 0 | 5 |
| og23 | 1028 | 11/24 (mine_cobblestone) | 0 | 0 |
| og24 | 1649 | 11/24 (iron_ingot) | 0 | 3 |

og23/og24 ran ~44 min (kit phase only); their memory-v2 read-outs (match rate, memory looks, recall re-targets) need a
longer run -- the arms are stoppable/relaunchable from scripts/launch_og23_og24.sh once the budget allows.

## 2026-09-08 -- the mfm-era trajectories staged for HF (Ced-Collab/MCUData)

- User (mid-morning): "把目前有代表性的或者分数高的轨迹总结一下，我准备上传 ... agent自己写的相关的代码啥的也可以
  作为轨迹的一部分"; then "你整理好以后上传到 https://huggingface.co/datasets/Ced-Collab/MCUData/tree/main".
- `scripts/stage_hf_mfm_era.py` builds `MCU-AgentBeats/output/hf_staging/mfm-era/`: 14 runs (obf2 54.17 full-task
  record, obf1; og9 16/24 half-task record, og8 repeat-death exemplar, og19 23-life carry; og12/og16 from scratch;
  og14/og15/og20/og21/og22 self-harness ladder; og17 visual-only; og18 human-play) + `lineage/og23_distill/` +
  `agent-code/INDEX.md` (every mine/ file with call counts). Per run: provenance.json, trajectory/episode_001
  (episodes/ packed as one `episodes.tar`; previous/life_* replaced by LINEAGE.json), slimmed codex rollouts
  (compaction snapshots + base64 frames out: 200-500 MB -> ~20 MB), launcher logs, evaluator mp4 where flushed
  (og12, og22, obf1, obf2). Anonymised (<MCU>/<MFM>/<CODEX_HOMES>/<HOME>/user); leak grep = 0 files. 2.42 GB,
  9,190 files (the unpacked tree would have been ~65k files against the repo's 100k budget).
- README caveats recorded: the half task credits only milestones triggered in the episode (compare by the
  beyond-kit timeline); obf1/obf2 ran with --sites/--corridors; og15/og19-og22 were stopped 04:36 mid-run.
- Facts settled while staging: og14 reached mine_obsidian at 15505 (earlier notes had it short of obsidian);
  the ob/obf arms ran at the purple default effort (medium: run-arm.sh passes no --reasoning-effort).
- `stats/runs.csv` gained the 14 rows + 17 scoreboard-only rows (og3-og7, og10/og11/og13, og23/og24, ob1-ob6,
  obf3); the top-level README got the dated mfm-era box. Upload: `hf upload` from the staging dir (user's word).
- 06:08-06:28 UPLOADED on the user's word ("你整理好以后上传到 .../MCUData"): `hf upload` of mfm-era/ (30 commits,
  2.23 GB transferred, last commit de2145c4), then README.md (f323fbf4) and stats/runs.csv (dd84cc41). Verified with
  HfApi.list_repo_tree: 9,191 files / 2.42 GB under mfm-era/ on HF = the local staging; README box present; 32 mfm_era
  rows in stats/runs.csv. Before upload the scoreboard rows of og3/og4 and ob1-ob5 were re-read from the evaluator's
  result.json (their reports pre-credited the kit at step 0: report 13/24 vs evaluator 25.0-41.67).

## 2026-09-08 -- of1 prepared: the FULL task from nothing on gpt-5.6-sol high (the user's decisions)

- Why (user): gpt-6 costs too many tokens; start over. Evidence laid out in the session, from the codex rollouts'
  token_count events (per 1k steps, uncached input / cached input / output; steps per hour):
  sol medium cold-start (og3, og5, ob*) 110-190k / 260-560k / 5-10k, 11-17k steps/h; sol medium 8-turn threads
  (og4/og6/og7) 33-56k / 460-800k / 4-8k; gpt-6 high unlimited thread, fixed library (og8-og13, og16) 120-220k /
  1.5-2.6M / 7-11k, 4.5-7k steps/h; gpt-6 high self-harness (og14/15/19-21) 280-370k / 3-5M / 13-17k, 2.6-4k
  steps/h; sol xhigh three-layer (og22) 276k / 4.4M / 27k, 2.7k steps/h. og21's thread: 770 API calls over 241
  turns, per-call input median 79k / max 102k, 31 codex compactions at the 100k limit (the report's
  `compactions: 0` counter misses them: it watches the --json stream, the events are in the rollout).
- Decisions: task ender_dragon (never run on this branch; obf1-obf3 ran it on dragon-obsidian with --sites),
  NO_SEEDS, gpt-5.6-sol high, --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills, one thread
  compacted at 100k (SESSION_TURNS=0 COMPACT=1), 320x180, --no-event-sheet, WALL=8h with STEPS=100000 (never the
  stop), the reflex starters demoted to examples (nothing under mine/reflexes/ until the model copies one).
- Code: MCU spatial-grid-merge f40e9000 (fast-forwarded into the live checkout); tests in this repo: 135 passed
  (tests/ minus test_carry, test_kicad_eval and the kicad store tests). Pins unchanged (the full-library
  contracts keep their dig_down example; the atom example applies only under --atoms/--visual-only).
- Launch line: `tasks/mfm-three-layer.spatial-grid/scripts/launch_of1.sh` (ARM/GP/PP overridable). NOT launched:
  the user launches, or says go. Expected from the record: 3-6k steps/h -> 20-40k steps in 8 h; the clean
  full-task record to beat is 11/24 (kd14x, kdc3z, 12k steps with a fixed library); obf2's 13/24 had pushed sites.

## 2026-09-08 08:32 -- of1 LAUNCHED (full task, gpt-5.6-sol high, three-layer minimal)

- Cleanup first (the user's ask): four orphan engines left by the 04:36 stop (og15/og21/og23/og24, `java mcprec` pids
  39312/41696/34246/33303, ppid 1) killed by pid; this track's stale `tail -F` monitors killed; 11 dead `/tmp/.X*-lock`
  + sockets removed; six dead `stark_tech_instances/` dirs removed. Root disk stays 96% (36G /usr, 6.2G /var/log: not ours).
- Two launch failures fixed before it ran: (1) `--skills needs --thin and --own` -- `--minimal` does not imply `--thin`,
  og24 also carried both; `--thin` added to launch_of1.sh. (2) `WorldModelExecutor.__init__() got an unexpected keyword
  argument 'event_sheet'` -- the purple executor never forwarded the new flag (tests build the agent directly); MCU 6eb4ea17.
- Third launch 08:32:43: launch pid 19612, wall watchdog 19615 (stops at ~16:32), green 9121, purple 9131 (pid 19650),
  codex home `codex-homes/of1_mfm`. Checks at 08:34: 0 tracebacks; purple line `model=gpt-5.6-sol ... thin=True atoms=True
  own=True own_reflexes=True harness_reflexes=False skills=True minimal=True frame_size=320x180`; AGENTS.md 2,002 words,
  task "Starting from nothing, defeat the Ender Dragon", no previous/ mention, `mine_ahead` example, "none is installed
  for you"; `mine/reflexes/` empty, five examples under `skills/reflexes/scripts/`; own.md "guards are OFF in this run";
  toml task_category=ender_dragon max_steps=100000. Turn 1 at 08:33:55 (images=1); leaves being mined by 08:35.

## 2026-09-08 10:05 -- of2 LAUNCHED: head-to-head of of1 on gpt-6-astra medium (the user's ask)

- Same FLAGS as of1 except `--model gpt-6-astra --reasoning-effort medium`; ports 9122/9132; STEPS=100000 WALL=8h
  (watchdog 40648 -> ~18:05); launch pid 40635, purple 40779; `launch_of2.sh` (MFM-grid 79679af).
- Account: the user asked for "~/.codex-eval". `~/.codex-eval/auth.json` is a symlink to `~/.codex/runtime-home/auth.json`
  = ChatGPT-plan login, account 7631363f (jl17319@nyu.edu, pro). `~/.codex/auth.json` is a DIFFERENT plan login
  (8a17dd5d, guoruihan.sansi@gmail.com, pro). Both wrappers relink the arm home's auth.json to their own account
  (`link_or_replace` replaces a symlink that points elsewhere), so the plan-wrapper probe silently ran on 8a17dd5d.
  Fix: CODEX_BIN = the raw binary `~/.nvm/versions/node/v22.18.0/bin/codex`, MCU_CODEX_AUTH = runtime-home/auth.json;
  the purple backend exports CODEX_HOME=<arm home> itself (codex_backend.py:756). Probes: PROBE_OK on 7631363f,
  14-19 s per call (wrapper 25 s); every call logs `failed to refresh available models: timeout waiting for child
  process` once -- harmless, the wrapper path has it too.
- Checks at 10:06: 0 tracebacks; purple env CODEX_BIN=raw binary, MCU_CODEX_AUTH=runtime-home; arm home auth.json ->
  runtime-home/auth.json; the turn-1 codex child is `node .../bin/codex exec --json ...` under the purple; AGENTS.md
  2,002 words, full task text, no previous/, "none is installed for you"; mine/reflexes empty. Turn 1 at 10:06:20.
- Both arms share the node: load ~11 on 255 cores; each arm has one engine (java mcprec) + Xvfb.

## 2026-09-08 11:11 -- of3 LAUNCHED: gpt-6-astra HIGH on the ~/.codex-eval account (the user's ask)

- `launch_of3.sh` = launch_of2.sh with `--reasoning-effort high`, ARM of3_mfm, ports 9123/9133; same raw-binary +
  MCU_CODEX_AUTH plumbing, same plan account 7631363f as of2 (one symlinked credential, as codex-home.sh intends).
  Launch pid 14133, purple 14189, wall watchdog 14136 (-> ~19:11).
- Checks at 11:13: 0 tracebacks; purple env CODEX_BIN=raw binary, MCU_CODEX_AUTH=runtime-home; arm home auth.json ->
  runtime-home; harness_reflexes=False skills=True minimal=True; AGENTS.md 2,002 words, full task, no previous/,
  "none is installed for you"; mine/reflexes empty. Turn 1 at 11:12:42. Load spiked to 34 during the engine start.
- At launch time of1 (turn 150, 18.8k steps) and of2 (turn 41, ~6.6k steps) were both at 6/24 (furnace), no iron yet.

## 2026-09-08 12:38 -- memory-reuse chain armed (the user, before sleeping: "如果跑完了，就跑各自的memory reuse，让模型自己处理memory而不是用harness处理memory")
- Head-to-head at 12:35: of3 9/24 (iron_pickaxe @ 6,243, 12:23), of2 9/24 (iron_pickaxe @ 12,883, 12:35),
  of1 8/24 (iron_ingot @ 22,218; at 30k steps still stuck at health 2/20 in a water shaft at y43 since ~24.6k,
  no death). Iron-ore steps: of3 5,325 / of2 11,787 / of1 21,733; records kdc3z 6,490 / kd14x 7,905 for the pickaxe.
- Reuse = the MFM carry alone: `scripts/launch_ofr.sh N` launches `ofNr_mfm` with ofN's flags and model,
  `EXTRA_ONLY=1 EXTRA_SEEDS=output/ofN_mfm/episode_001/memory` (previous/life_1 hard-linked, the model's
  workshop turn reads it; no --sites, no --seed-mine/distiller). Ports of1r 9124/9134, of2r 9125/9135,
  of3r 9126/9136; WALL=8h. Checks: run-arm.sh --dry-run prints the seed line; PreviousLives.seed on of1's
  live memory linked 2,657 files, "no sites pushed"; the minimal contract adds the previous/ clause when lives exist
  (prompts.py:1397) and the skills package's workshop-turn doctrine (skills.py:316).
- `scripts/chain_ofr.sh N` waits for logs/ofN_mfm_launch.pid to exit (the wall stop; wall-stopped arms write no
  _result.json -- og15/og23/og24 have none, scores come from the purple log's [milestone] lines / worldmodel_report.json),
  sleeps 90 s, then runs launch_ofr.sh. Watchers detached 12:38: pids 37334 (of1, wall ~16:32), 37336 (of2, ~18:05),
  37335 (of3, ~19:11); logs/ofNr_mfm_chain.log. Nothing else is launched.

## 2026-09-08 16:35 -- of1 wall-stopped: 8/24, 3 deaths; of1r launched by the chain
- of1_mfm (gpt-5.6-sol high, from nothing): stopped by the wall at 16:32:43 mid-turn 416, 56,800 steps, 8/24
  (iron_ingot @ 22,218), 3 deaths, 0 tracebacks. The story after the ingot: drowned twice in the same water
  shaft at (-2998, 43-45, -5612) -- trapped there from ~24.6k to the first death at 40,593 (hand-mining upward
  while the current pulled it down), the second at 45,364 was deliberate ("wait for the last two damage pulses"
  as a teleport home, its recovered items dropped again); the third at 52,7xx inside a go_to's queued
  pillar_up(6) at (-2992, 54, -5583), no damage note before it (the runner ran 400 ticks). Never crafted the
  iron pickaxe though it held 3 ingots at 22k. Scores from logs/of1_mfm_purple.log [milestone] lines (no _result.json).
- Chain: run-arm exited 16:33:35; of1r_mfm launched 16:35:05 (launch pid 24406, wall 24409 -> ~00:35, ports
  9124/9134). Checks: model=gpt-5.6-sol sites=False minimal=True seed_mine=None; "[previous] 1 live(s) carried
  (4613 files linked, 1148 indexed episodes), no sites pushed"; previous/life_1 = episodes grid.jsonl index.jsonl
  logs.txt mine skills; mine/reflexes empty; 0 tracebacks; auth -> ~/ccr/.codex/auth.json.
- of2 (gpt-6 medium) died once at 23,285 (lava at y10 while stair-digging; its lava_ahead reflex stepped it
  back INTO the lava during the escape, it had a water bucket it never poured), 9/24. of3 (gpt-6 high) 10/24
  (flint_and_steel @ 23,032 -- flint + iron before diamond), 0 deaths.

## 2026-09-08 17:10 -- of1r relaunched: the minimal contract never told the model about previous/
- FINDING: of1r's first attempt (16:35-17:09, 27 turns, 2/24) ran 0 commands touching `previous/` (its codex
  rollout, `"command"` entries; turn 1 read skills/memory/SKILL.md incl. the workshop-turn doctrine, then
  `rg --files skills references mine` -- not previous/ -- and went to cut a tree). Cause: `minimal_contract`
  (prompts.py) appended no carried-lives paragraph; every other mfm contract adds MFM_PREVIOUS_NOTE when lives
  exist (prompts.py:1037, :1595), the minimal one only had the phrase "`previous/life_<i>/` the earlier lives in
  this same world;" in the Memory line. og15 (the self-harness reuse precedent that read previous/ in turn 1)
  ran the thin contract WITH the note.
- FIX (MCU b2f8c832, ff'd into MFM-grid/MCU; MFM-grid acbae40 test): `**Previous lives.** <MFM_PREVIOUS_NOTE>`
  + "Your first turn is the workshop turn (`skills/memory/SKILL.md`): read them before you play." after the
  Memory paragraph when previous lives exist; from-scratch contracts unchanged. The note is a pointer ("Nothing
  from them is put in front of you ... reading it is yours to do"), no digest, no sites: the MFM carry holds.
  tests/test_memory_v2.py 7 pass. of2r/of3r launch from the live checkout and get it automatically.
- of1r stopped by pid (wall watchdog 24409 killed, stop_arm 13 pids); its life kept as output/of1r_noprev_mfm +
  logs/of1r_noprev_mfm_*.log + codex-homes/of1r_noprev_mfm (evidence, not a scored arm). Relaunched 17:10:52:
  launch pid 6506, wall 6511 -> ~01:11, ports 9124/9134; checks: carry 4613 files, AGENTS.md has both new
  lines, 0 tracebacks, auth -> ~/ccr/.codex/auth.json. Decision taken without the user (asleep): the reuse life
  as launched was not a reuse life; 34 min of gpt-5.6 turns spent.

## 2026-09-08 18:08 -- of2 wall-stopped: 9/24, 1 death; of2r launched by the chain
- of2_mfm (gpt-6-astra medium): stopped 18:05:09 mid-turn 427, 34,000 steps, 9/24 (iron_pickaxe @ 12,883),
  1 death (lava at y10, 23,285), 0 tracebacks. of2r launched 18:08:06 (launch 64645, wall 64648 -> ~02:08, ports
  9125/9135) on MCU b2f8c832: carry 5732 files / 1426 episodes, no sites; AGENTS.md has the previous-lives lines;
  mine/reflexes empty; 0 tracebacks; auth -> ~/.codex/runtime-home/auth.json (nyu plan).
- of1r (relaunched 17:10) at 17:53: 6/24 (furnace @ 5,509; life 1 needed 8,494); digest.md written from
  previous/life_1 in its workshop turn.

## 2026-09-08 19:13 -- of3 wall-stopped: 10/24, 0 deaths; of3r launched by the chain. First generation closed.
- of3_mfm (gpt-6-astra high): stopped ~19:11, 30,200 steps, 10/24 (iron_pickaxe @ 6,243, flint_and_steel @
  23,032), 0 deaths, 0 tracebacks. Head-to-head of one setting (full task from nothing, minimal contract, 8h):
  | arm | model | steps | milestones | deaths | iron_pickaxe |
  | of1 | gpt-5.6-sol high | 56,800 | 8 | 3 | never (3 ingots at 22k) |
  | of2 | gpt-6-astra medium | 34,000 | 9 | 1 | 12,883 |
  | of3 | gpt-6-astra high | 30,200 | 10 | 0 | 6,243 |
  None reached diamond; the record (11/24 at 12k) stands. The gpt-6 arms are ~2x slower per step (turn cost).
- of3r launched 19:13:06 (launch 50442, wall 50450 -> ~03:13, ports 9126/9136): carry 4708 files / 1170
  episodes, no sites; AGENTS.md has the previous-lives lines; 0 tracebacks; nyu plan auth.
- Second generation at 19:15: of1r 6/24 @ 18,400 steps (stuck after the furnace, 0 deaths); of2r 6/24 @ 7,600
  (furnace @ 4,123), 0 deaths. Both read previous/life_1 in the workshop turn and wrote mine/digest.md.

## 2026-09-08 22:54 -- of2r 12/24 (diamond_pickaxe @ 27,591); walls extended to 12h (the user's call)
- of2r_mfm (gpt-6 medium, seeded with of2's own life, the model read it): mine_diamond_ore @ 27,258, diamond @
  27,280, diamond_pickaxe @ 27,591 (22:48) -- 12/24, above the clean from-scratch record kdc3z 11/24 and one
  below obf2's 13/24 (which had --sites). of1r 9/24 @ 44k (1 death, pillar fall at (-2998,56,-5583) ~28k);
  of3r 9/24 @ 15.8k, 0 deaths.
- The user (awake, 22:5x) asked to extend the walls: all three +4h. Old watchdogs killed by pid (6511, 64648,
  50450), new ones sleep to 12h after launch: of1r pid 2893 -> 05:10, of2r 3080 -> 06:08, of3r 4345 -> 07:13
  (logs/<arm>_wall.pid rewritten; setsid forks, so the pid was resolved from ps, not $!).

## 2026-09-09 00:09 -- of2r mine_obsidian @ 31,911 (13/24): the first obsidian on the FULL task
- of2r (gpt-6 medium, own-life carry, no sites): poured its water bucket on lava, scooped it back, mined the
  exposed obsidian with the diamond pickaxe. 13/24 ties obf2's count (which had --sites and stopped at
  flint_and_steel); no full-task run ever mined obsidian before. of3r 13/24 (diamond_sword @ 18,403) hunting
  lava at y9; of1r 11/24 (diamond @ 56,546). All 0 deaths since the extension.
- 00:18 of2r died at (-3007, 8, -5680), step ~32,270: trapped under the obsidian cap it had made, burning in the
  lava/water mix; its own `hit` reflex read the burn as a mob and cut the escape plan. Everything (diamond
  pickaxe, diamonds, bucket, 336 cobble) dropped at the lava. 13/24 stands.

## 2026-09-09 01:2x -- systemic review recorded; waiting for the reuse lives (the user: 先记录和排查, 继续等)
- `analysis/systemic_of_2026-09-09.md` (+ traj_of1_of1r.md, traj_of2_of3_reuse.md from two read-only subagents):
  nine ranked problems and the multimodal-memory use table. Verified against code/logs in this pass:
  1. the cut-short note (agent.py:1991) is unconditional and names mine_forward/strip_mine/stair_down, none in
     procedures.ATOMS -- 300-400 notes per gpt-6 life;
  2. the navigator's stall path (agent.py:3115-3143) queues `pillar_up(n)` + the same go_to; of1 death 3 and of1r's
     only death happened inside it, 6 blocks apart (repeat_deaths.py);
  3. the reflex example set is fell/hit/lava_ahead/starving/known_hazards (skills.py:234); no arm installed
     known_hazards, none wrote a drowning/burning class; hit's text (skills.py:92) asserts "a mob is at you";
  4. NEW: codex compacted the thread 28-58 times per life (rollout `"type":"compacted"` records, ~every 12 min for
     of3r) while codex_backend.py:860 counted 0 -- it scans the exec event stream, not the rollout. working.md
     (40-68 KB, rewritten every turn, put in front of the model every turn) is the token item that drives it;
  5. 0 eat actions in six lives (eat is an atom), of1 at 2/20 for 16k steps, of3r 11-13/20 now;
  6. memory use: view_image 0.14-0.49/turn, almost all this life's latest frames; episodes.py --near/--sheet/
     --then-now used by sol only (65/49 calls), gpt-6 0/0 first lives, 6/6 reuse lives; previous-life frames 2-6
     per reuse life; digests are grep-of-logs.txt text.
- Nothing changed in the running arms; no launches. Walls: of1r 05:10, of2r 06:08, of3r 07:13. Fix candidates
  are listed in the analysis §4 for the user's morning decision.
- 01:56 **of3r flint_and_steel @ 28,009 -- 14/24, the full-task record** (obf2 13/24 with --sites; kdc3z 11/24 from
  scratch). gpt-6 high, own-life carry, no sites, 0 deaths, 6h41 in; wall 07:13.
- 02:54 **of3r mine_obsidian @ 32,685 -- 15/24**, 0 deaths, 7h40 in (wall 07:13). of1r died twice more at the pond
  (02:13 skeleton at 2/20 health, 02:24 charging the same skeleton with the diamond sword after recovering its
  drops) -- 3 deaths, 13/24, no food in 73k steps. of2r rebuilding at y11 after its obsidian death, 13/24.

## 2026-09-09 04:40 -- morning discussion recorded; gen-3 plan written (no launches)
- 04:14 status: of1r 13/24 4 deaths (go_to blocked near old shaft); of2r 13/24 1 death (46.9k, y11, 0 torches);
  of3r 15/24 0 deaths (36.6k; 80 min on the portal: 345 plans since mine_obsidian, top plans repeated 11-17x,
  10 obsidian placed into an invalid frame, 7 mined back; viewed ep1890/1896/1907 to diagnose). Walls 05:10/06:08/07:13.
- Findings for the user's four questions: --sites vs carry-only (previous.py docstring); the wz1119 SKILL.md is a
  desktop-control skill (process rules, no world knowledge); our skills never reached codex's catalog (of3r rollout has
  no `### Available skills` list; codex home skills/ = .system only); AGENTS.md re-injected each turn says only
  "read all four in your first turn"; [RECALL] is atom-grain and noisy (hotbar.6 "61 calls changed nothing").
- User decisions: SESSION_TURNS=1; codex-native skills; AGENTS.md gets the wz1119 rules + world knowledge; one
  ranked plan -> `plan-gen3.md` (P0 closeout, P1 method, P2 bugs, P3 arms A/B/C with pre-registered read-outs).

## 2026-09-09 05:10-05:35 -- of1r ended at its wall; P1/P2 implementation slice
- of1r stopped 05:10 (wall): 84,400 steps, 690 act turns, 13/24 (54.17), 4 deaths, 96 compactions in its rollout.
  mine/: digest.md 19 lines, notes.md 3, procedures deep_stair_step / horizontal_tunnel_step / safe_stair_step.
- 05:03 smoke (raw codex, gpt-5.6-sol low, scratch CODEX_HOME): under `--ignore-user-config` codex 0.147 lists
  `$CODEX_HOME/skills/*` AND `<cwd>/.agents/skills/*` in the session's `## Skills` catalog (a bare `skills/` is not a
  root); trigger rule "task clearly matches a skill's description -> use it that turn, not carried across turns".
- MCU 1ac1c7f7 (spatial-grid-merge, pushed): gen-3 minimal contract (Routines, Rules of play from the wz1119 skill,
  Improve yourself, digest beside working, context-does-not-persist note, compact procedure index -> 12.6 KB carried /
  11.2 KB scratch); skills.py: trigger descriptions, skills/minecraft (1.16-style rules, no places), skills/mining
  (search doctrine), hit.py "source unknown", burning.py + drowning.py, `.agents/skills` catalog synced every turn
  (skills/ + mine/skills/); agent.py: [DIGEST] block (2000 chars), 40-line working.md rule visible, reflex state
  fire_frac/water_frac, pit climb queues the pillar and STOPS the plan (no go_to from the pillar top), atoms-aware
  cut-short hint. MFM-grid 5940cb4: tests/test_gen3_contract.py (13 tests pass incl. test_memory_v2, pytest now in
  merge-mcu/.venv).
- Not done in P2: GUI settle (no harness note found for the models' "stale slot" complaint -- their own words in
  working.md; nothing to change without a reproduction); entities (not in the observation; green-layer); compaction
  counter (moot under session-turns 1).
- Worker (worktree MFM-grid-wk-recall, branch spatial-grid-recall): plan-grain RECALL in mfm/memory/retrieve.py,
  `--ores`/`--y-profile` in the episodes tool, stall.py / memory_use.py / selfimprove.py. Running.
- 05:35 the gen-3 settings smoke (g3smoke_mfm from merge-mcu, ports 9127/9137, gpt-6 high, SESSION_TURNS=1, seed of3,
  STEPS=600, WALL=30m) was NOT launched: the session's permission classifier blocked the launch command; the exact
  command is handed to the user to run with `!`. Purpose: does the catalog show, does the carried contract render, what
  does a fresh-session turn cost.
- scripts/launch_g3.sh written (not run): of{N}g_mfm seeded with of{N}r (carries gen 1 too), SESSION_TURNS=1,
  WALL=12h; `scratch` mode = the from-scratch control on the same contract.

## 2026-09-09 06:0x -- worker merged; the repeat finding corrected; suite green except the environment
- Worker branch spatial-grid-recall rebased and fast-forwarded into spatial-grid (69d5a66 plan-grain recall +
  hotbar out of streaks, 2ea00b5 episodes tool --ores/--y-profile, 353e95b stall.py/memory_use.py/selfimprove.py,
  40389e4 report analysis/worker_recall_2026-09-09.md). Read-outs on the six lives are in the report.
- CORRECTION: the "same plan repeated 11-30x" numbers counted logs.txt sections (plan entries), not turns; no life
  re-issued an identical EXPECT three turns running. The stall is one long plan (15-24 entries) achieving nothing:
  34-43% of entries. Added `retrieve.plan_stall` (outcome-based: N quiet turns, or one plan of >= 12 entries that
  changed nothing; notes "same EXPECT, numbers aside"), wired first into recall_block; the Routine and the mining
  skill's Stalls paragraph reworded; MCU RECALL_IGNORE_KINDS lists hotbar.1-9 explicitly.
- Tests adapted to the gen-3 behaviour: test_grid (pillar then stop, no re-queued go_to), test_own_reflex (working
  note names the digest), test_skills (six skills, burning/drowning). Whole suite: only the 8 environment failures
  remain (gym_codex / CUA-KiCad submodule missing: test_carry x2, kicad pins x6), identical on unmodified HEAD.
- of2r 05:29 diamond_sword 15/24 (@50,492). Walls: of2r 06:08, of3r 07:13 (monitors armed).

## 2026-09-09 06:08-06:35 -- of2r ended; P2 completed on the user's five points
- of2r stopped 06:08:51 (wall): 52,433 steps, 15/24 (diamond_sword @50,492), 1 death. of3r 15/24, wall 07:13.
- User (06:1x): fix the compaction counter anyway; GUI settle is to be fixed; look at the stale slot/station
  carefully; a test script; resolve the environment failures.
  * Compactions: scan_rollout counts `"type":"compacted"`; report = max(stream, rollout) + both parts (MCU).
  * GUI: the frame trails isGuiOpen by 1-2 ticks -> `_opengui_tick` idles GUI_OPEN_SETTLE=3 after the flag;
    `gui.CRAFT_SETTLE` 2->6 so the next craft's leftovers precheck (macros_gui.py:653, reads slot occupancy
    from the frame) stops seeing emptied cells as busy (5 false refusals in six lives, models' own watch(12)).
  * Stale station: the [MAP]/stall-hint/use_until_gui placed record was never dropped when the model mined its
    table/furnace back up (of3 "map furnace placement STALE" for 10k steps) -> `_station_picked_up` pops
    `_placed` and `grid.placed` on the mine_block event, with a note.
  * scripts/run_tests.sh (whole suite or --core; picks merge-mcu's venv; prints MCU commit).
  * Environment: CUA-KiCad (gym_codex) is a private submodule this host cannot clone (SSH denied; Collab/MFM's
    copy is an empty dir) -> conftest skips test_carry + the ::test_kicad* pins with the reason when
    CUA-KiCad/gym_codex is absent. Whole suite now: all pass, 9 skipped, 0 failed. Real fix: check the
    submodule out from a host with access (`git submodule update --init CUA-KiCad`).
- MCU 121d500a -> (this) ; MFM-grid tests: test_gen3_contract +2 (rollout compactions; GUI settle + station).

## 2026-09-09 06:32-06:38 -- of3r enters the Nether (16/24); wall extended +2h (user)
- 06:32 of3r netherrack @41,584 -> 16/24 (66.7): the portal lit, the Nether entered. First of this track's lives.
- User: "现在第二代的都延长2h" -- of3r is the only gen-2 arm still running: watchdog 4345 (07:13) killed by pid,
  new watchdog 4806 fires 09:13 (`sleep 9189; stop_arm.py --go of3r_mfm`). of1r/of2r already ended.
- Gen 3 (of1g/of2g/of3g via launch_g3.sh, seeds of{N}r) waits for of3r to stop, then MFM-grid/MCU ff -> 3a63e24a.

## 2026-09-09 06:42-06:48 -- long-session smoke: the gen-3 mechanisms hold on a resumed thread
- User: maybe not SESSION_TURNS=1; test that the changes hold with long sessions. Raw-codex two-turn smoke
  (gpt-5.6-sol low, scratch CODEX_HOME, workspace .agents/skills): turn 1 fresh -> "WS-ECHO"; between turns a
  skill `late-echo` was added under .agents/skills and AGENTS.md's secret word changed APPLE -> PLUM; turn 2 via
  `codex exec resume <id>` -> "LATE-ECHO WS-ECHO", rollout holds PLUM (2) and late-echo (2), "Available skills" x5.
  So codex 0.147 re-scans the skill roots AND re-reads AGENTS.md on every turn of a resumed session: the native
  catalog (incl. mine/skills written mid-life), the Routines and the per-turn [WORKING]/[DIGEST]/[RECALL] all work
  under SESSION_TURNS=0+COMPACT exactly as under 1. SESSION_TURNS=1 buys only the "MFM is the sole continuity"
  framing. launch_g3.sh now takes SESSION_TURNS (0 -> COMPACT=1; N; default 1) from the environment.

## 2026-09-09 08:06-08:11 -- of3r stopped early (user); gen 3 launched and aborted within 2 minutes (user: analyse first)
- User 08:05: "直接停掉吧" -> of3r watchdog 4806 killed by pid, stop_arm.py --go of3r_mfm (12 pids). Final: 43,479 steps,
  ~520 turns, 16/24 (66.7), 1 death (06:52 in the Nether at (-408,43,-704), health 10, no food, sneaking between fires
  with a zombified piglin in view; all gear lost; rebuilt from spawn to dirt-only inventory in the remaining 74 min).
- MFM-grid/MCU fast-forwarded b2f8c832 -> 3a63e24a (pushed hither spatial-grid); MFM-grid 36c8e4b bumps the submodule.
- 08:08:04/26/28 launched of3g/of2g/of1g (launch_g3.sh, SESSION_TURNS=0 + COMPACT). 08:09 user: "先别开跑，我觉得再分析一下
  跑完的这三个arm的系统性问题，看看我们现在新改动是否都adress了" -> watchdogs 39874/42308/42681 killed by pid,
  stop_arm.py --go on all three (31 pids) after ONE codex turn each. Outputs, logs and codex homes moved to *.aborted-0808.
  Next: the coverage analysis (analysis/gen3_coverage_2026-09-09.md), then relaunch on the user's word.

## 2026-09-09 08:12-08:50 -- coverage analysis of the gen-2 endgames against the gen-3 code
- analysis/gen3_coverage_2026-09-09.md: final gen-2 table (of1r 13/4 deaths/84k, of2r 15/1/52k, of3r 16/1/43.5k;
  dead-plan entry share 34/28/42%; digest re-read 0/0/13; then-now 2/0/0; eat 0/0/0; new reflex classes 0) and a
  15-row problem -> change -> status matrix: 8 rows fixed in the harness (stall line, reflex state, pillar stop,
  cut-short hint, GUI settles, station pickup, catalog, hotbar), 7 rows given as knowledge/routines whose effect gen 3
  must show (search doctrine, food, portal geometry, flint, Nether entry, self-improvement, memory hypotheses), and
  the honest gaps: animals are not perceived by the harness, no portal verifier, turn wall time, the entry cap.
- Added from the endgames (MCU f943269a, live MCU fast-forwarded, MFM-grid 55e3cce): gravel is at water's edge and in
  caves; enter the Nether at health 16+ with cooked food; copy known_hazards.py after the first death.
- analysis/traj_gen2_final.md (subagent) kept with a caveat header: its death steps and GUI counts failed checking.
- Gen 3 not relaunched: waiting for the user's word.

## 2026-09-09 09:0x -- knowledge as general rules (user), starving stop, no harness perception for animals/portal
- User: knowledge = general rules a human player knows, not specific recipes; the harness never decides for the model;
  animals and the portal frame are for the model to recognise (no frame-based animal hint, no portal verifier).
- MCU (this commit): skills/mining rewritten as "game facts + principles" (where ore generates, expose-look-break,
  cover volume not distance, evidence decides depth/heading, segment plans, budget the way back); the branch-spacing /
  torch-interval / segment-length numbers are gone. minecraft skill: portal "checked by looking, not by counting",
  Nether "go in healthy and fed; the portal is the way to heal", hunger phrased as cost. Contract: geometry "verified
  by looking at what stands"; pre-Nether "healthy" instead of a number. starving.py: note at the 18 crossing, STOP
  when health <= 10 with food < 18 or food <= 6 (a decision handed to the model, no action taken for it).
- Live MFM-grid/MCU fast-forwarded; core tests pass (test_gen3_contract adapted). Gen 3 still waits for the user's go.

## 2026-09-09 09:2x-09:5x -- late-game knowledge as general rules; the atoms references rewritten macro-free
- User: add the missing late-game knowledge (beds/respawn, 1:8, piglins/gold, blazes, bows/arrows, void/cages/perch,
  stronghold room, everyday dangers) in general form; fix survival.md's stale macro line; and rewrite the 27 KB
  references/skills.md, which named the old macro library, before relaunching.
- MCU (spatial-grid-merge, ff'd into the live checkout): prompts.SITUATIONS_ATOMS + situations_atoms() replace the
  situations/chain sections under --atoms (skills.md 30.0 KB -> ~14 KB incl. the kept recipe list and write-down
  section; no macro names); survival_atoms() rewrites the two Movement bullets; the references tail describes
  skills.md as "the situations". skills/minecraft gains five sections of general rules. Tests: test_gen3_contract +2
  (macro-free references; late-game rules), all affected files pass.
- Gen 3 still waits for the user's go.

## 2026-09-09 09:15-09:45 -- gen-3 pre-launch review (user's four checks), no code changed
- analysis/gen3_review_2026-09-09.md. Knowledge for all 24 milestones is present as rules (skills/minecraft,
  skills/mining, the atoms references + recipe list), no coordinates; grey area = harness-digested earlier-life
  anecdotes in the skill texts (user's call). Skill catalog verified on the arms' binary (codex is 0.153.4 now,
  not 0.147): symlinked .agents/skills lists all six + an own skill with full descriptions; the catalog also
  carries 5 codex .system skills and 4 host ~/.agents/skills (skill-creator collides with "write a skill").
  Frictions: `.agents` not in KEEP_BETWEEN_TURNS (rebuilt each act turn), `skills` not in NOT_CARRIED
  (previous/life_1/skills exists), DIGEST_CAP 2000 < of3r's digest 2142 B. The 08:08 launches never reached a
  codex turn (of3g: agent constructed, no AGENTS.md/skills/codex_turns) -> the gen-3 path is untested end to
  end; the 600-step smoke is still the next step. Tests on live MCU dc27d08c: 22 passed.

## 2026-09-09 09:5x-10:5x -- the review's four items fixed (user: anecdotes out, frictions fixed, codex home isolated, multimodal flow checked)
- Rule (user): the model reads previous/ itself; the harness gives no earlier life's outcome. Every anecdote in the
  model-facing text is now a rule (skills x6, the reflex/procedure example comments, Routines/Rules of play, the atoms
  situations, gui.md/survival.md's three old sentences); tests/test_gen3_fixes.py guards it with a regex over the
  rendered contract, references, skills and scripts. Chassis pins re-recorded (three sentences + index fields).
- Frictions: `.agents` in KEEP_BETWEEN_TURNS; `skills` in NOT_CARRIED (a seed's harness skill package is no longer
  under previous/life_N/); DIGEST_CAP 3000.
- Codex home: the per-arm home is isolated, but codex 0.153.4 (both accounts run it now; the 05:03 smoke was 0.147)
  re-installs its 5 bundled skills into `$CODEX_HOME/skills/.system` at every start and also lists `$HOME/.agents/
  skills` (this host: deepspeed, find-skills, health, flash-attention) -- 9 strangers in every arm's catalog, with
  `skill-creator` matching the moment the contract says "write a skill". Six one-turn smokes (gpt-5.6-sol low):
  an empty or read-only `.system` dir is replaced; `-c skills.config=[...enabled=false]` is ignored; a plain FILE at
  `skills/.system` makes the install fail (logged, harmless) and HOME=<arm home> drops the host root -> the catalog
  is the workspace's `.agents/skills` alone (symlinks followed, full descriptions, own skills included).
  codex-home.sh + codex_backend.py do both now.
- Multimodal flow, checked on of3r's real record: episode frames and attach/frame.png are 320x180, previous-life
  frames hard-linked (nlink 3), previous/index.jsonl paths resolve; `--last/--near/--tag --sheet/--then-now` (own
  and previous frames), `--y-profile`, zoom.py all produce the right images (viewed sheet.png/tn.png); [OBSERVED]
  and [RECALL] cite frame paths in real turn prompts (turn 120: 4 citations); the model's shell python has PIL and
  numpy (of3r ran crops and `--previous --steps --q`). Found and fixed: `--grep` opened action/outcome/state of
  every episode (>120 s at 2,787 episodes on data3) and `--ores` every outcome.json (84 s) -- longer than a turn.
  Now the index row carries note/events/inventory_delta (store.py) and the carry enriches old lives' rows at seed
  time (previous.py): seeding of3r into a scratch workspace took 3m31s for 3,957 rows (all with events, 1,512 with
  a note); then `--previous --grep lava` 0.04 s, `--previous --ores` 0.01 s. `--deep` keeps the old file search.
  recall_block on the full record from a cold cache: 13.4 s (in the arm the files are page-cache warm; not changed).
  worldmodel_report's `view_image_calls` (10,887 for of3r) is inflated by the 0.153 exec-tool echo; the read-out
  scripts (vision_use.py, memory_use.py) count calls correctly.
- MCU d3d567e2 (spatial-grid-merge, live MFM-grid/MCU fast-forwarded), MFM-grid e3e4e11; whole suite green (9 skips).
  Not pushed. Still not run end to end on an arm: the 600-step g3smoke (user's launch).

## 2026-09-09 10:33-10:49 -- g3smoke_mfm: the gen-3 path end to end (user: "smoke一下吧", then "尽快跑完")
- Launch (live MFM-grid/MCU d3d567e2): TASK=ender_dragon, gpt-6-astra high (nyu plan, raw binary), seed of3r
  (carries of3 -> 2 lives), SESSION_TURNS=0+COMPACT, STEPS=600, WALL=30m, ports 9127/9137, BASE flags of
  launch_g3.sh. Servers up in 20 s; seeding 3m15s (15,866 files linked, 3,957 rows all with events/1,512 with a
  note); 17 skill files written; ended at step 599 by itself at 10:49 (11.5 min of play, 11 act turns).
- What the smoke had to show, all seen: the arm's codex home has `skills/.system` as a file and the session
  catalog lists exactly harness/memory/minecraft/mining/procedures/reflexes (no imagegen/skill-creator, no host
  skills); the model read minecraft/memory/procedures/reflexes SKILL.md in turn 1; AGENTS.md 15.8 KB; turn-4+
  prompts carry [WORKING] [DIGEST] [RECALL] [MAP] [RECENT] [OWN]x2 [EXPECTED]/[OBSERVED] (9.3 KB); previous/ holds
  life_1+life_2 without skills/; 0 tool errors, 0 attach misses, 0 compactions, frames attached 11/11.
- The model's turn 1 (2m11s): 6 commands over previous/, viewed a life-1 frame and a then-now pair, wrote
  mine/digest.md (2.3 KB, its own reading of both lives incl. the diamond site of life 2), copied west_level +
  west_stairs under their own names and fell/hit/lava_ahead/known_hazards into mine/reflexes (380 reflex runs,
  0 firings, 0 failures), then mined a log by step 123. 3/24 by step 513 (log 123, table 379, wooden pickaxe
  513). memory_use: prev/ later 0, digest later 2, notes later 1, view_image 6 (attached view/sheet 4, previous
  frame 1), --then-now 2, --previous 2. Turn wall 41-83 s after the workshop turn; ~52 steps/min.
- stderr classes only two, both known: "failed to install system skills ... Not a directory" (the .system file,
  by design) and "failed to refresh available models: timeout waiting for child process" -- account-side: a
  raw-binary turn on the plan account WITHOUT the HOME override shows it too (3x), the API-key wrapper with or
  without HOME shows none. Watchdog 57305 killed by pid after the arm ended; output kept under output/g3smoke_mfm.
- Gen 3 can launch on the user's word: `bash tasks/.../scripts/launch_g3.sh 3` (SESSION_TURNS=0 in the env for
  the compaction mode, default 1), then 2 / 1 / `3 scratch`.

## 2026-09-09 10:55 -- gen 3 launched by the user: of3g_mfm
- `SESSION_TURNS=0 bash launch_g3.sh 3` (user's shell): of3g_mfm, gpt-6-astra high (nyu plan), seed of3r (carries
  of3), one thread + COMPACT, STEPS=100000, WALL=12h -> stops ~22:55; launch pid 4357, watchdog 4360; ports
  9128/9138; live MFM-grid/MCU d3d567e2. Codex home has the `.system` file. First-turn check to follow.
- 11:00:36 seeded (2 lives, 15,866 files, 3,957 rows with events); turn 1 11:00:36-11:02:41: catalog = the six
  skills only, `.system` file in place, previous/ without skills/; the model ran 6 commands over previous/, viewed 2
  previous-life frames, wrote mine/digest.md (2.5 KB) + notes.md, copied west_level/west_stairs and
  fell/hit/lava_ahead/known_hazards (hit.py edited); stderr only the by-design system-skills line. Turn-2 prompt
  carries [WORKING]/[DIGEST]/[OWN]. Pushed by the user 11:0x (MCU d3d567e2 on spatial-grid-merge and
  spatial-grid; MFM-grid 2f97331).
- 11:08 user: "我们停止一下，我觉得我们要换一个账号跑" -> watchdog 4360 killed by pid, stop_arm.py --go of3g_mfm
  (12 of 12 pids). It had 3/24 @641 in turn 6 (11:07). Output, logs and codex home set aside as
  *of3g_mfm.stopped-1108*. launch_g3.sh takes ACCOUNT=api|nyu (default per arm as before).

## 2026-09-09 11:27-11:52 -- OpenRouter attempt abandoned; of3g_mfm relaunched on the nyu plan
- User: run the next experiment on an OpenRouter account. Key handed over as a 600 file outside every repo
  (`Collab/secrets/openrouter.env`, one line, never pasted into the session). Wiring tried: the backend's
  `--base-url` path (model_provider=local, wire_api responses, env_key LOCAL_API_KEY) through a wrapper that
  read the file and exec'd codex; codex-home.sh `MCU_CODEX_AUTH=none`; `ACCOUNT=openrouter` in launch_g3.sh.
- Finding 1 (one-turn codex smoke, `openai/gpt-6-astra`, frame attached): HTTP 403 "This model is not available
  in your region" on both /responses and /chat/completions, six retries; same for gpt-5.6-sol/luna and
  claude-sonnet-5 ("failed_routing_step": "Gate Endpoints with Geo Restrictions"). This host's egress is
  Beijing / China Telecom (ipinfo). Through the user's configured proxy 192.168.1.64:7890 (git http.proxy, ssh
  ProxyCommand, `withproxy` alias; exit Los Angeles) both endpoints answered gpt-6-astra ($0.00033 each).
  OpenRouter price for openai/gpt-6-astra: $10 / $50 per M in/out, $1 cached; ctx 1,050,000; image+tools+reasoning.
- Finding 2 (security, independent of OpenRouter): codex 0.153's exec cells inherit the WHOLE codex environment.
  Probe (gpt-5.6-sol low, API key, 3 one-turn calls, cents): the model's `printf "${GITHUB_PERSONAL_ACCESS_TOKEN:+set}"`
  printed set for GITHUB_PERSONAL_ACCESS_TOKEN, WANDB_API_KEY and LOCAL_API_KEY; `-c shell_environment_policy.exclude=
  ["*KEY*","*TOKEN*","*SECRET*"]` changed nothing. The user's shell exports the GitHub token and the W&B key
  globally (their own ~/.codex and ~/ccr/.codex/runtime-home shell_snapshots carry both), so every arm's model could
  have read them. Evidence they never did: grep over every arm workspace's logs.txt / last_message.txt / mine/
  (MFM-grid/MCU, MFM/MCU, MCU-AgentBeats outputs) finds no mention of the names. Codex also writes a shell snapshot
  (`$CODEX_HOME/shell_snapshots/<thread>.sh`, `declare -x` of every variable) at thread start and deletes it on a
  clean exit; 21 of 54 codex homes (arms stopped mid-turn) still hold one with those variables in plaintext.
  `-c features.shell_snapshot=false` stops the file (probed: 0 files during a 25 s turn, exec unaffected).
  TODO for the next MCU slice (not while an arm runs): filter `*KEY*|*TOKEN*|*SECRET*` out of the env the backend
  hands codex (LOCAL_API_KEY excepted) and add `features.shell_snapshot=false` to SAFE_CODEX_FLAGS; delete the
  stale snapshots. Recorded, not fixed: the user asked for the launch first.
- Decision (user 11:49): "算了，我觉得我们就先用nyu账号跑吧，开始跑吧". Everything OpenRouter-related reverted
  (codex-home.sh, the wrapper, launch_g3.sh back to 64117f1); probe codex homes orsmoke1 (its snapshot held the
  real key) and snapprobe1-5 removed; the derived secrets/openrouter-auth.json removed; secrets/openrouter.env
  left as the user made it.
- Launch 11:51:41 (my shell, `env -u GITHUB_PERSONAL_ACCESS_TOKEN -u WANDB_API_KEY -u CLAUDE_CODE_MESSAGING_TOKEN`
  so this run's tree carries none of them): `SESSION_TURNS=0 ACCOUNT=nyu bash launch_g3.sh 3` -> of3g_mfm,
  gpt-6-astra high, seed of3r (carries of3), one thread + COMPACT, STEPS=100000, WALL=12h (stops ~23:51),
  launch pid 13636, watchdog pid 13639, ports 9128/9138, live MCU d3d567e2. Orphan `sleep 12h` processes
  (4362, 39877, 42313, 42686; parents already killed) fire nothing.
- 11:55 stopped on the user's word ("先停一下"), 3.5 min in: green/purple up, seeding in progress, 0 codex turns.
  `stop_arm.py --go of3g_mfm` stopped 11 of 11 pids (3 SIGKILLed); watchdog 13639 and its sleep 13641 killed by
  pid; ports 9128/9138 free. output/of3g_mfm and logs/of3g_mfm_* left in place (a relaunch overwrites them).
  Relaunch line (from MFM-grid/MCU): `env -u GITHUB_PERSONAL_ACCESS_TOKEN -u WANDB_API_KEY SESSION_TURNS=0
  ACCOUNT=nyu bash ../tasks/mfm-three-layer.spatial-grid/scripts/launch_g3.sh 3`.

## 2026-09-09 11:57-12:11 -- proxy test (OpenAI + Anthropic through OpenRouter), the hires frame record, relaunch
- User: (1) keep a higher-resolution copy of every frame the agent is NOT shown, for a video on the website;
  (2) test whether the proxy lets us use OpenAI and Anthropic models; (3) make the resolution fed to the agent
  an option.
- Proxy (192.168.1.64:7890, LA exit), python in-process key, OpenRouter: openai/gpt-6-astra, anthropic/claude-
  sonnet-5 and anthropic/claude-opus-5 all answer on /chat/completions and /responses, with an image attached
  (the 320x180 frame described correctly); opus-5 returns empty text on chat with a small max_tokens (thinking
  eats it), fine on /responses. reasoning.effort reaches gpt-6-astra (37 vs 31 reasoning tokens high vs low on
  a small counting question). Anthropic prices on OpenRouter: fable-5.1 $10/$50, opus-5 $5/$25, sonnet-5
  $2/$10 per M; all 1M ctx, image input.
- The codex path through the proxy WORKS with one recipe and fails with the others:
  * OPENAI_BASE_URL env: ignored -- codex 0.153 went to api.openai.com (websocket first, then HTTP; OpenAI's own
    401 text) -- and `-c model_providers.openai.base_url=...` is refused ("reserved built-in provider IDs").
  * WORKS: `-c model_provider="openrouter" -c model_providers.openrouter.name="OpenRouter"
    -c model_providers.openrouter.base_url="https://openrouter.ai/api/v1" -c model_providers.openrouter.wire_api=
    "responses" -c model_providers.openrouter.requires_openai_auth=true` with HTTPS_PROXY set for the codex
    process and the arm's auth.json a symlink to `secrets/openrouter-auth.json` ({"OPENAI_API_KEY": sk-or-...},
    600, derived from the user's env file). One turn, gpt-6-astra high, frame + shell command: 12 s, image
    described, exec ran, and `${OPENAI_API_KEY:+set}` printed EMPTY inside the exec cell -- the key never
    enters the environment. A second one-turn call answered the primes question (21) in 8 s.
    Wiring it into launch_g3.sh needs: a wrapper that sets HTTPS_PROXY for codex only (never for the tree:
    the A2A hop is localhost), the backend's --base-url branch emitting requires_openai_auth instead of env_key
    (a 3-line switch), `openai/` model ids, CODEX_MODEL_CONTEXT_WINDOW=1050000. Not done: the user chose nyu.
  * The key's spend for the whole investigation: $0.24.
- Hires record (MCU 44978744, live MFM-grid/MCU ff'd): the purple adapter writes every observation's frame
  exactly as the green agent sent it (640x360 JPEG, the MinecraftSim obs_size; `src/agent.py:473`) to
  `episode_NNN/hires/<step:07d>.jpg` -- beside memory/, outside the model's cwd, never named in any prompt/
  skill/tool (tests/test_hires_record.py greps mcu_worldmodel/ for it), never carried. `--hires-every N`
  (default 1; 0 off). A write failure is logged once and stops the record. Higher than 640x360 needs the
  green obs_size raised (benchmark layer; the user's call). FRAME_SIZE env in launch_g3.sh sets the frames
  the model is shown (default 320x180). Tests: test_hires_record.py 4 pass; whole suite exit 0.
- Relaunch 12:10:40 (my shell, env -u of the secret vars): `SESSION_TURNS=0 ACCOUNT=nyu bash launch_g3.sh 3`
  -> of3g_mfm, gpt-6-astra high, frames 320x180, seed of3r, one thread + COMPACT, STEPS=100000, WALL=12h
  (stops ~00:10 on 09-10), launch pid 52676, watchdog 52690, ports 9128/9138; live MCU 44978744.

## 2026-09-09 12:12-12:45 -- of3g_mfm died at start (JVM crash); env filter + snapshot off landed; the 320x180 question
- The 12:10 relaunch ended at 12:12 after ONE request: green log "Error during task 'kill_ender_dragon':
  TypeError - a bytes-like object is required, not 'NoneType'", and logs/mc_2026-09-09_12-12-01_3131.log shows why:
  the Minecraft JVM died of SIGSEGV in native code, `liblwjgl_stb.so+0x2e144`, at mission init ("Setting width,
  height to 640, 360"). The purple agent never got an observation (no `[adapter] episode 1` line), so the hires
  adapter code never ran. The only mc log this week with a fatal error (10:56 and 11:53 instances were fine);
  nothing under /tmp/MineStudio-ruihan was written 11:50-12:00 outside the instance dirs; hs_err was cleaned with
  the instance dir. Verdict: a one-off native crash; relaunch when the user says so, dig if it recurs.
  User 12:20: (1) do the filter + snapshot-off, (2) no launch for now, (3) is 320x180 enough for the model?
- (1) DONE, MCU 90e4dc78 (live ff'd, no arm running): `scrub_env` drops KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL
  names from the environment codex gets (LOCAL_API_KEY and CODEX_* kept), logged once per CodexTurn; SAFE_CODEX_FLAGS
  += features.shell_snapshot=false. tests/test_codex_env.py (2), whole suite exit 0. The 21 stale snapshot files
  under Collab/codex-homes deleted. NOT touched (the user's own dirs): ~/.codex/shell_snapshots (16 files) and
  ~/ccr/.codex/runtime-home/shell_snapshots (18) still hold GITHUB_PERSONAL_ACCESS_TOKEN and WANDB_API_KEY.
- OpenRouter's own codex recipe (docs/cookbook/coding-agents/codex-cli, user's link): `[model_providers.openrouter.auth]
  command = "sh" args = ["-c", "echo $OPENROUTER_API_KEY"]` -- command-based auth. Tested with the key read by the
  command from the 600 file instead of the environment (`auth.command="sed" auth.args=["-n","s/^OPENROUTER_API_KEY=//p",
  ".../secrets/openrouter.env"]`, wire_api responses, proxy): one turn, 15 s, image described, exec ran, both
  OPENROUTER_API_KEY and OPENAI_API_KEY unset inside the exec cell, stderr clean. This is the recipe to wire if the
  OpenRouter route is ever used (no auth.json copy needed; secrets/openrouter-auth.json deleted).
- (3) A/B, gpt-6-astra low effort through OpenRouter, the same 640x360 frames shown whole and downscaled to 320x180
  (obf2/ob1/ob1b lives, 10 frames, $0.20): at 640x360 the model reads the hotbar (item names and counts, e.g. "Dirt
  x5, cobblestone x21, wood logs x3, pickaxe x1"); at 320x180 it says "unreadable" for the hotbar in 5 of 6 frames
  (the sixth: "dirt, count unreadable"). Block-level scene reading (logs, leaves, stone, gravel, dropped item,
  tentative coal in a dark cave) was the same at both sizes on all 10 frames; no clean ore-in-view frame exists in
  the indices to test ore spotting. Tokens per image: 387 (640x360) vs 171 (320x180) -- +216 per turn, ~1-2% of a
  turn. The harness gives the inventory as text ([INV], hotbar/held lines, the cursor's slot from the 640x360
  pov), so the GUI digits are not something the model has to read from pixels; what 320x180 costs is fine texture
  (item icons, distant ore, small mobs). The 320x180 choice (og2, 2026-09-07) was about bytes in resumed threads
  ("payload wall around turn 12", run-arm.sh), not tokens; codex_backend counts attachment bytes per session
  (attachment_bytes_peak in the report) for that. Gen 1-3 all ran 320x180; the ob era 640x360.
- State: nothing running; live MFM-grid/MCU 90e4dc78; MFM-grid 738f02f+; ports 9128/9138 free. Relaunch line:
  `[FRAME_SIZE=640x360] SESSION_TURNS=0 ACCOUNT=nyu bash ../tasks/mfm-three-layer.spatial-grid/scripts/launch_g3.sh 3`.

## 2026-09-09 12:25-12:40 -- the gen-3 setup confirmed and decided; the OpenRouter route wired
- User's decisions (after the setup read-back): (1) OpenRouter; (2) seed = the gpt-6-astra-high lineage's
  gen-2 life (of3r, which carries of3; launch_of3.sh / launch_ofr.sh both gpt-6-astra high, logs
  model=gpt-6-astra); (3) sites/corridors explained (harness-digested [KNOWN SITES] / dry corridors from
  earlier lives; banned since 09-07, off); (4) frames 640x360; (5) SESSION_TURNS=0, one thread per life.
- launch_g3.sh (MFM-grid fed13d3) defaults now: ACCOUNT=openrouter, FRAME_SIZE=640x360, SESSION_TURNS=0
  (COMPACT on), `SMOKE=<steps>` = g3smoke_mfm on 9127/9137 with WALL 30m. MCU 725574f3 (live ff'd):
  `provider_auth_args()` -- CODEX_LOCAL_AUTH_COMMAND (JSON list) makes the --base-url provider authenticate by
  running that command (OpenRouter's documented auth.command form) instead of env_key, so the key is in no
  process environment; scripts/codex-openrouter.sh sets the proxy for the codex process alone;
  codex-home.sh MCU_CODEX_AUTH=none. tests/test_codex_env.py 4 tests; whole suite exit 0.
- Backend-level smoke (CodexTurn.run through the wrapper, no auth.json, a 640x360 frame): ok in 24 s, the
  model read the hotbar (5 dirt, 21 cobblestone, 2 sticks, 3 planks, pickaxe), inside the exec cell
  OPENROUTER_API_KEY and OPENAI_API_KEY unset and LOCAL_API_KEY=EMPTY, the env-scrub log line present, no
  key anywhere in the home or workspace, no snapshot.
- Attachment bytes in one thread: of3r's harness counter peaked at 35.2 MB (516 turns, 320x180) with 0
  harness-visible compactions and no failure; the harness only counts what it attached, codex's compaction
  drops the images from the wire. At 640x360 each frame is ~2-3x the bytes; watch attachment_bytes_peak and
  the purple log for any payload error in the first hour of the real run.
- Cost at OpenRouter: of3r's rollouts sum to 1,585 model calls, 121.5M input tokens (93% cached), 0.51M
  output (0.11M reasoning) -> $82 + $113 + $25 = $221 for ~13h, ~$204 per 12h run. The key had no credit
  limit when checked (auth/key: limit None); worth setting one on the OpenRouter side.
- 12:37:26 `SMOKE=150 bash launch_g3.sh 3` -> g3smoke_mfm (pid 9540, watchdog 9544): the decided setup end
  to end (seed of3r, OpenRouter through the proxy, 640x360, one thread). Result below.
  RESULT 12:50 (ended at step 150; 13 min wall, 7 of them seeding: obs 12:39:27 -> carried 12:46:28, 3.5 min
  at 11:00, data3 load): the whole gen-3 path ran on OpenRouter.
  - Codex: 1 turn (workshop + first plan in one; 12:46:29-12:49:24 = 2m55s, 12 exec cells, one exit-1 retried,
    0 tool-error turns; session 01a0847d): read digests/procedures/reflexes of both carried lives, ran
    tools/episodes.py --grep, installed 4 reflexes into mine/reflexes (fell, hit, known_hazards, lava_ahead),
    wrote mine/digest.md, working.md, notes.md, emitted an 8-entry plan (clear leaves -> punch the known
    trunk). Usage 378.8k input (332.3k cached, 46.5k cache-write), 6.5k output (1.2k reasoning) = ~$1.1 at
    OpenRouter prices. 0/24 at step 149 (plan entry 6/8, spruce_leaves broken; 150 steps is one plan).
    stderr has only the by-design skills/.system lines (4x "failed to install system skills"); no 403, no
    region error, no websocket/HTTP fallback line.
  - Frames: model-side attach/frame.png is 640x360; attachment_bytes_peak 474,569 (one frame). Hires record:
    149 JPEGs, 14.1 MB, avg 97 KB, 640x360, 0000001..0000149.jpg under episode_001/hires/, none inside
    memory/. ~97 KB/step -> a 42k-step life (of3r's length) writes ~4 GB; data3 has 76 T free.
  - Hygiene: the codex home has no auth.json and 0 shell_snapshots; the OpenRouter key prefix occurs nowhere
    under output/g3smoke_mfm or codex-homes/g3smoke_mfm; purple log: "[codex] env: not passed to codex:
    CLAUDE_CODE_MESSAGING_TOKEN, GITHUB_PERSONAL_ACCESS_TOKEN, MAX_THINKING_TOKENS, WANDB_API_KEY".
  - Not covered by this smoke: the long thread (codex's 100k compaction over OpenRouter's responses path) and
    the payload wall at 640x360 -- watch attachment_bytes_peak and the purple log in the run's first hour.
  The 12h launch waits for the user's word: from MFM-grid/MCU, `bash ../tasks/mfm-three-layer.spatial-grid/
  scripts/launch_g3.sh 3` (defaults: openrouter, 640x360, SESSION_TURNS=0, seed of3r); set a credit limit on
  the key first (~$204 per 12h).
- 12:56:51 user: "开跑". LAUNCHED of3g_mfm = the gen-3 arm (`bash launch_g3.sh 3` from MFM-grid/MCU, live MCU
  725574f3): ACCOUNT=openrouter (proxy wrapper, auth by sed on the 600 key file, no auth.json), openai/gpt-6-astra
  high, frames 640x360, SESSION_TURNS=0 (one thread, codex compacts), seed of3r (carries of3 -> of3r), no
  sites/corridors, hires record on, env scrub + snapshot off. launch pid 52493, watchdog 52496, WALL 12h ->
  ~00:57 2026-09-10, ports 9128/9138, logs/of3g_mfm_*.log, output/of3g_mfm, codex-homes/of3g_mfm. Preflight:
  no arm running, all four ports free, load 12.7/255. The 12:12 JVM-crash leftovers were set aside as
  `*of3g_mfm*.crashed-1212*` (logs, output, codex home) so the launcher wrote a fresh tree.
  First-hour watch: attachment_bytes_peak / payload errors at 640x360, turn cadence, any 403 or fallback line.
- 13:02:03 of3g_mfm seeded (4 min); turn 1 (workshop) 13:02-13:05:22; mine_log 1/24 @158 13:06, crafting_table
  2/24 @526 13:09, wooden_pickaxe 3/24 @657 13:10. 13:35: 25 turns, step 1200, ~77 s/turn, attachment_bytes_peak
  7.83 MB (of3r's was 35 MB with no failure), 2 codex compactions, 0 tool-error turns, no 403/fallback lines.
  Thread usage at turn 21: 5.67M input (5.09M cached, 0.49M cache-write), 42.6k output -> ~$12 for 37 min,
  i.e. ~$19/h, ~$230 per 12h (of3r-based estimate was $204).
  INCIDENT 13:12-13:16 (turns 6-8 lost, ~4 min): codex's linux-sandbox panicked "failed to create synthetic
  bubblewrap mount marker directory /tmp/codex-bwrap-synthetic-mount-targets-637400009/... No space left on
  device" -- the root filesystem (/tmp is on /) filled up transiently; every exec cell and every apply_patch
  failed, the harness logged "act turn attempt 1..3 produced no actions.json" and moved on; turn 9 wrote a
  one-tick plan and play resumed. At 13:37 / has 114 GB free (58%), inodes 11%; the filler is unknown (shared
  node; not this arm -- its /tmp use is a few model-written PNGs). codex hardcodes /tmp for the marker (no
  TMPDIR string in the binary), so it cannot be moved to data3. Not restarted: transient, self-healed, 3 turns
  cost. The overnight monitor (task bm3cxz4uh) now also counts stderr files with sandbox/stream faults and
  prints root free space; a recurrence is the trigger to look for the filler.
  The overnight mandate (user 13:05, asleep): keep it running, fix and relaunch on infrastructure faults
  without asking (seed of3r + this life's own memory if it had progress), never inject facts.
- 14:42 hourly: 49 turns, step 3000, 6/24 (mine_cobblestone @1356 13:39, stone_pickaxe @1507 13:43, furnace @2318
  14:03), load 21, hires 3131 files. PACE: turns are 2x slower than of3r -- last 30 turns codex wall median 108 s
  (mean 125, max 440) + plan execution median 25 s, vs of3r's turn-to-turn median ~60 s; 2.8 exec cells per turn
  (of3r 1.8), ~3k output tokens per turn (of3r ~0.6k). The model re-reads .agents/skills/*/SKILL.md, mine/working.md
  and previous/ logs most turns and validates actions.json with json.tool; the time is model generation over
  OpenRouter, not the environment. Consequence: ~1,500 steps/h -> ~18k steps at the 12h wall (of3r: 41.6k in 13h),
  so the wall, not the model, may cap this life's milestone count. Gen-3 design consequence (skills catalog +
  "Improve yourself"), not an infrastructure fault: no intervention; the user decides on wall/contract changes.
  ROOT FS: 114 GB free at 13:37 -> 94 GB at 14:42 (-20 GB/h). `du -x` sees only 55 GB of the 176 GB used (rest
  in other users' unreadable dirs or open-deleted files); no >200 MB file of the last 90 min is readable; this
  arm's /tmp use is 0.45 GB (MineStudio engine) + a few PNGs. A shared-node job fills and frees / in cycles; each
  fill = a sandbox-fault window (turns lost, the harness moves on). Nothing on our side can move codex's bwrap
  marker out of /tmp; watching root_free hourly and sandbox faults per turn.
- 17:43 hourly: 154 turns, step 6000, 6/24, load 22, root fs 55 GB free (drained 93->55 between 15:42 and 16:42,
  flat since). Two transient stream errors (turn 114 16:44 "502", turn 142 17:31 "error decoding response body"),
  both reconnected on codex's first retry. No sandbox faults since 13:16.
  PACE vs of3r by wall time since first obs (of3r first obs 19:14:50 09-08): of3r 6/24 at +20 min (step 2507),
  mine_iron_ore +52 min (@5033), iron_pickaxe +1h07 (@6060), diamond_pickaxe +4h06 (@18155); of3g 6/24 at
  +1h01 (@2318) and still 6/24 at +4h41 (@6000). Both slower per hour (2x) and, past the furnace, less
  productive per step (of3r had iron by step 5033; of3g has none at 6000: it spent 14:03-17:40 hopping toward
  life-1's iron entrance one block at a time, climbed into the spruce canopy at Y72 clearing leaves, plans of
  1-14 steps, RECALL nudges present in the prompts). Model play, not infrastructure: no intervention under the
  overnight mandate. Decision for the user in the morning: at ~1,300 steps/h the 12h wall (~00:57) yields
  ~15k steps, far short of the 41.6k of3r used for 16/24; the gen-3 setup (skills catalog, 640x360, OpenRouter,
  "Improve yourself") is underperforming gen-2 on this life -- the seed is the same, so the cause is the
  gen-3 changes and/or the provider's speed, to be separated before the next arm.
- 18:43 hourly: 197 turns, step 8200, 9/24 -- mine_iron_ore @6565 17:56 (+4h55), iron_ingot @6989 18:10, iron_pickaxe
  @7880 18:33 (+5h31; of3r +1h07). 2,200 steps in the last hour (was ~1,300): once underground the plans got
  longer. Root fs 55 GB free, load 16, no faults.
- 19:50 analysis/gen3_vs_gen2_2026-09-09.md: of3r vs of3g over the first ~220 turns (same seed, model, session
  mode). Turns to step 10k 81 vs 217; steps/turn 123 vs 46; cells/turn by kind: skill reads 0.01 -> 0.73, looks
  0.01 -> 0.70, queries 0.02 -> 0.51, json validation 0 -> 0.96, working+digest+actions rewrite 0 -> 0.68/turn.
  Defects found: the contract's "context does not persist" sentence (prompts.py:1495) is unconditional and false
  in one-thread mode; digest.md became a per-turn log (100.6 KB, 207 lines, newest first; the [DIGEST] block shows
  its head, so the cross-life facts at the tail are never shown); Rules of play always-on halve the plan grain;
  skill triggers fire ~every turn; no model-authored skill; RECALL entry-grain noise in 75-90% of prompts (both
  gens). Positives: 0 deaths, prepared descent, iron via life 1's recorded entrance (then-now). Ranked gen-3b
  changes and the decisive experiment are in the file. User is awake and deciding; of3g_mfm keeps running.
- 20:35 GEN-3b PATCH (MCU cf86f15a on spatial-grid-merge, pushed; NOT in the live MFM-grid/MCU while of3g runs):
  prompts.py -- `_PERSISTENCE[one_thread]` (the contract says the thread persists and codex compacts it;
  minimal_contract(one_thread=) wired from codex.session_max_turns == 0), digest = 20 one-line facts written in
  the first turn + at most one line per milestone/death, notes.md append-only, one look per plan, then-now once
  on arrival, Rules of play = open-loop pace rule (60+ steps on known ground) + no replay after a stall + the
  skills pointer (the five wz1119 step rules and the two facts moved to skills/minecraft), Improve-yourself moment
  = a banked milestone or a death, actions.json validated by the runner (no json.tool cell); skills.py -- once per
  stage in the catalog paragraph, memory/reflexes/harness/minecraft triggers narrowed, the geometry rule under
  The portal; agent.py -- [DIGEST] shown in full on act turns 1-2, afterwards a one-line pointer with the file's
  shape and a rewrite note over 20 lines / 3,000 chars; episodes.py -- `watch` in RECALL_IGNORE_KINDS. MFM-grid --
  retrieve.py recall_block streak_min 4 (was 3), max_streaks 2 (was 3), the closing view_image nudge replaced by a
  neutral note (frame paths kept); tests: test_gen3_contract (one-thread text, once-per-stage triggers, digest
  pointer/shape), test_retrieve, test_vision_prompt, pin chassis_mfm_recall_prompt.txt re-recorded (1 line).
  Contract 15.8 -> 13.1 KB. Targeted suites 44 pass; full suite re-run in progress. HF: look_examples_of3g
  uploaded to Ced-Collab/MCUData (commit dcc36d25, 17 files). User's decisions so far: 1/4/6 yes, frames stay in
  RECALL; the relaunch timing (stop of3g now vs. after the 00:57 wall) is theirs.
