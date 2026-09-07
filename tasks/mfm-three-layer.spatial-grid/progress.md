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
