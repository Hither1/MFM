# Progress

## 2026-09-06

- Analysis of 148 dragon runs delivered to the user (findings.md). User decisions: macro
  fixes in scope; no hand-written coordinates; 24k steps first; run locally; new branch.
- Branches: MFM `dragon-obsidian` (from `mfm-three-layer` @ dd9a99e); MCU worktree at
  `MFM/MCU` on `dragon-obsidian` = hither/mfm-three-layer @ 832a3628 + cherry-picks
  c1da5101 (API-key credential default) + b5599690 (env.sh copier lock). `.venv` symlink
  to `../MCU-AgentBeats/.venv`; pytest shim (la-rna-bb py3.11 site-packages copy) in the
  scratchpad `pytest_shim` because uv cannot reach the network from this node.
- Baseline: chassis pins 10/10 green before any edit.
- Slice A (MCU `mcu_worldmodel/`): `procedures.shrink_marker` honours a marker `_min`
  (find_lava 250, fetch_water 250, `_scoop` 60, `_mineobs` 240); `macros_nether.LAST_LAVA`
  + `remember_lava` (set by find_lava's stop and the runner's LAVA AHEAD guard with a
  bucket); `make_obsidian()` / `mine_obsidian()` without coordinates use it; new ticks
  `_scoop` (walk back into reach, re-aim, press use until water_bucket) and `_mineobs`
  (servoed aim, attack never released, ends on `mine_block obsidian`, says when the wrong
  block broke or the cell is out of reach); `_dig_water_refusal` names a `go_to` away from
  the water.
- Slice B: `mcu_worldmodel/previous.py` (PreviousLives: link lives under previous/, merged
  previous/index.jsonl, sites from logs.txt, `[KNOWN SITES]` block, audit);
  EpisodeBridge.seed_previous/known_sites; WorldModelAgent(previous_lives=...); turn prompt
  carries the block before [RECALL]; contract gains MFM_PREVIOUS_NOTE; memory sweep keeps
  `previous/`; purple agent `--seed-memory` repeatable, mfm carries instead of copying.
- Slice C: prompts.py doctrine paragraph (bucket first, lakes not corridors, known sites).
- Slice D: run-arm.sh `CODEX_BIN` default `~/ccr/bin/codex`, `PYTHONPATH` to the MFM root,
  `--seed-memory` passthrough; probes/run_stage.sh PYTHONPATH likewise.
- Tests: `tests/test_previous.py` (5) and `tests/test_obsidian.py` (5) green; chassis pins
  re-recorded (only `chassis_logbook_agents.md`, `chassis_mfm_agents.md`,
  `chassis_prompt_hashes.json` moved: the two macro descriptions and the doctrine
  paragraph; logs/actions/workspace pins unchanged). KiCad tests fail only because the
  CUA-KiCad submodule is not checked out here (ModuleNotFoundError gym_codex) -- pre-existing.
- Extractor on the real half logs (hd12z, hd32z, hd39z, hd43z, hd41z): 5 lives, 999 files
  linked, sites: 5 lava, 2 pour rims, 3 water, 19 ore, 5 deaths; block reads sensibly.
- Engine: stage s5 running in the background (`MCU/logs/stages/s5_nether.log`); stage
  `s12_obsidian.py` written (floor-level lake, guard sighting, no-argument calls), not yet run.

- Engine: s12_obsidian 11/11 green (guard sighting at 4 ticks, make_obsidian() 171 ticks with the
  scoop back in 1 press, mine_obsidian() 193 ticks -> mine_block obsidian +1, neighbour by
  coordinates 196 ticks, plan-cap rule). s5 rerun: pour and mine green (the mine broke the rim
  in front, then the obsidian, 225 ticks); the two Nether-leg checks failed on a death in the
  Nether during `mine netherrack` -- files untouched by this work, not investigated.
- Commits: MCU 74def4ec (dragon-obsidian), MFM ed3c1fe (dragon-obsidian, submodule pointer,
  tests, pins, tasks).
- gen-1 LAUNCHED 2026-09-06 ~09:50 local: `ob1_mfm`, `--agent mfm --task ender_dragon_half
  --steps 12000`, ports 9071/9081, seeds hd12z/hd32z/hd39z/hd43z/hd41z/kd35z_lb (6 lives),
  detached via setsid (launcher pid in `MCU/logs/ob1_mfm_launch.pid`, run-arm pid 24610).
  Logs `MCU/logs/ob1_mfm_{green,purple,client}.log`, result `MCU/logs/ob1_mfm_result.json`,
  workspace `MCU/output/ob1_mfm/episode_001/`. Monitor task bc4xpylgf watches the purple log.

- gen-1 at step ~6000: bucket crafted, water filled at the known pond, descended to y 8-9,
  tunnelled 30 blocks to the KNOWN SITES pour rim (-2992, 10, -5561) and poured (step 5972);
  the flow pushed it 9 blocks back, the scoop's walk stalled at a one-block step (no jump), and
  mine_obsidian() was refused because a pour by coordinates set no LAST_LAVA. Both fixed:
  MCU ed6073ba / MFM c0a36db (explicit pour = sighting; scoop walk jumps after 4 stalled ticks).
- gen-1b LAUNCHED 10:05: `ob1b_mfm`, same seeds/budget, ports 9072/9082, fixed code, run-arm
  pid 10297; monitor bor5v0v3c. gen-1 (old code) runs on as the control.

- Both gen-1 and gen-1b were led by the KNOWN SITES "POUR RIM" line (life 1's 3% sighting) to
  (-2992, 10, -5561): poured, stone underneath. gen-1b's second pour: 20 scoop presses at the
  source's centre scooped nothing (the ray met flowing water first) while the model's own
  use_at at the top face worked once. Fixes committed for gen-2: slivers (<8%) de-ranked and
  labelled, pour rims verified only by a lake within 6 blocks, water behind lava once carried,
  scoop reach = use_at's 4.4, scoop aims at the source cell's top (MCU 0d80aa6e + top-aim
  commit; MFM ab53018, b8e6f34). gen-1 at step 10.1k still at the sliver; gen-1b at 5.8k
  heading for the 52% lake (-2986, 11, -5556).

- gen-1 (`ob1_mfm`, control, old code) FINISHED 10:43: score 25.0 (6/24 beyond the 10 given:
  diamond, diamond_pickaxe, diamond_sword), no obsidian. It lost its water at the sliver pour,
  later stood in lava at (-2992, 9, -5561) (32% sighting, 8 damage), used an empty bucket on
  it, and spent 5 mine_obsidian calls on stone cells (3 foreign breaks each, "none was obsidian").
- gen-1b (`ob1b_mfm`, ed6073ba code) FINISHED 10:55: score 37.5 (9/24), no obsidian. Two pours
  on the sliver rim (scoop 0 and 20 presses, nothing back), find_lava 0 blocks in 341 ticks,
  then KILLED by a melee mob at (-2988, 10, -5560) step 5951 (health 5 -> 1 -> dead, bunker
  failed); recovered the drop, spent the rest on a new dig; never reached the 52% lake.
  Evidence: `MCU/logs/ob1{,b}_mfm_result.json`, `MCU/output/ob1{,b}_mfm/episode_001/{memory/logs.txt,worldmodel_report.json}`.
- s12_obsidian rerun on the latest code (top-aim scoop): 11/11, scoop back in 1 press / 2 ticks
  (`MCU/logs/stages/s12_obsidian_0906_114307`).
- Bug found while previewing gen-2's block: lives carried under a seed's `previous/` were
  re-linked as new lives (8 seeds -> 20 lives, 5162 files). Fixed: dedupe by sha1(logs.txt)
  (MCU 92fb2a06); 8 seeds -> 8 lives, 46 sites. Block order with water carried: 52% lake
  (-2986, 11, -5556), 33% lake, gen-1's 32% sighting (-2992, 9, -5561), 10%, then the pour rim
  (now "beside a lake" because of that 32% sighting 1 block away), ore, sliver, deaths.
- gen-2 LAUNCHED 11:47: `ob2_mfm`, `--agent mfm --task ender_dragon_half --steps 12000`, ports
  9073/9083, 8 seeds (six lives + ob1_mfm + ob1b_mfm), first attempt died at the engine reset (TypeError bytes-like/None, 11:46, logs `ob2_mfm_fail1146_*`); relaunched 11:52, run-arm launcher pid 58188
  (`MCU/logs/ob2_mfm_launch.pid`), logs `MCU/logs/ob2_mfm_*.log`; monitor bu6shv106.

- User (12:10): asleep; keep iterating for the highest dragon score, purple side only (no change to
  the benchmark's green/I-O/scoring layer). Branches pushed by the user: hither/dragon-obsidian
  (MCU 92fb2a06), origin/dragon-obsidian (MFM 11eaf49).
- full 24k run LAUNCHED 12:23 in parallel with gen-2: `obf1_mfm`, `--agent mfm --task ender_dragon
  --steps 24000`, ports 9074/9084, the same 8 seeds, run-arm launcher pid 28152
  (`MCU/logs/obf1_mfm_launch.pid`), monitor bigtdzp7j. Load 42/255 with two engines.

- gen-2 (`ob2_mfm`): water filled by step ~800, diamond pickaxe, tunnelled 21 blocks in the dark to
  the KNOWN SITES "nearest lake" = gen-1's tainted 32% sighting (the fire overlay of a burning
  avatar read as lava) and its pour rim; poured on stone by coordinates at step 4436 (no lava in
  view: frames ep_000054-58 are black with only the water flow), scoop 7 presses nothing,
  mine_obsidian broke stone, then a mob took 4 + 10 health in 200 ticks and the bunker dig at y 9
  ended in death at step 4697 with the diamond pickaxe lost. No obsidian. Monitors on the purple
  log were blind (notes live only in the workspace logs.txt): re-armed on logs.txt.
- Fixes for gen-3 (MCU a51313cf, MFM 3f7295e; tests 20/20; pins: only the doctrine paragraph):
  blind pour by coordinates refused unless lava >= 1% of the lower view or a frame sighting is on
  record; LAVA AHEAD lines in a section with damage notes are dropped by the extractor; lava/pour
  lines carry a DEATH WARNING when a life died within 8 blocks; doctrine: largest lake, never the
  nearest, pour only after LAVA AHEAD. 9-seed block preview: 52% lake first (2 deaths flagged),
  the tainted line gone, pour rims out of the top 8.

- gen-2 FINISHED ~12:45: score 37.5 (9/24), no obsidian (`MCU/logs/ob2_mfm_result.json`).
- Torch slice (MCU c51bbd22, MFM 2107531): mine_forward/strip_mine plant a torch every 8 blocks
  below y 50 when one is in the hotbar (select, place on the floor behind via use_step, tool back,
  face the heading). Stage s13 (`MCU/logs/stages/s13_torch_0906_123954`): 1 torch planted in a
  400-tick strip_mine (8 blocks), tool back, 8 cycles; my two threshold checks assumed 12+ blocks
  per 400 ticks and were corrected to the engine's rate. Unit tests 22/22, pins unchanged.
- gen-3 LAUNCHED 12:47: `ob3_mfm`, half task 12k, ports 9075/9085, 9 seeds (six + ob1 + ob1b +
  ob2), code MCU c51bbd22 (blind-pour guard, tainted sightings dropped, death warnings, torches),
  run-arm launcher pid 27069, monitor on the workspace log.

- gen-3 (`ob3_mfm`) FINISHED: 37.5, no obsidian. It went to the 52% lake as ranked (water at ~800,
  torches planted, 1 per tunnel), the guard fired on a 2% sliver at the bottom of the view and put
  the pool "at most 3 blocks off"; frames ep_000097/98 show the lava in the NEXT cell. make_obsidian()
  poured from the lip (step 7610), the flow carried the avatar off the ledge, "tried to swim in
  lava", dead at 7651 (frame ep_000099 shows obsidian formed in the lake). The rest of the run
  rebuilt gear. Monitors did not wake this session (no notification arrived for ~10 h).
- obf1 (24k full) FINISHED ~22:50: 37.5 (9/24): iron_ingot at 5973 but iron_pickaxe only at 16089
  (10k steps lost to furnace GUI loops: "furnace_load: no screen is open" x9, ingots taken one by
  one), then no diamond by 24k. Same score as the half runs; the record 45.83 not beaten.
- Six previous lives mined diamond (dm16, dm17, kd6 at (-3059..-3061, 10-12, -5558); kd14x, kd31z at
  (-2999..-3002, 9-12, -5567..-5571); kdc3z at (-2973, 13, -5526)); their block lists "ORE:
  diamond_ore mined standing here" first when diamond is open -> seeds for the next full run.
- Pour fix (uncommitted until the stages pass): make_obsidian() first backs the avatar off the pool
  (`_backoff`: face the pool, walk back to >= 3.5 blocks from its cell and >= 1 block moved, wall
  stops it); mine_obsidian() walks the cell back into reach (<= 4.25 from the eye, 40 ticks max)
  instead of refusing. Tests 23/23. Stages s14_edge (lake in the next cell) + s12 rerun running.

- Pour fix committed (MCU 54ed3c9f, MFM ed36971). Stage s12 rerun 11/11; stage s14 (lake at the lip,
  `MCU/logs/stages/s14_run2`): backed off 1.5 blocks to 3.6, poured, scooped back in 10 presses,
  OBSIDIAN BROKEN twice (192/194 ticks) -- the milestone event fires from the lip; the one red check
  is the drop pickup (the sweep does not reach the lake cell; the portal's 10 obsidian will need a
  safe pickup later). First s14 attempt had the avatar's hitbox over the lava at spawn (stage bug).
- 23:35 LAUNCHED gen-4 `ob4_mfm` (half, 12k, ports 9076/9086) and `obf2_mfm` (full, 24k, ports
  9077/9087), both on MCU 54ed3c9f, seeded with the 12 first-generation lives (six half runs + the
  six diamond finders) plus ob1/ob1b/ob2/ob3 (obf2 also obf1). Polling monitors (60 s) on the
  workspace logs replace the tail -F ones, which never matched.

- 2026-09-07 00:00-01:00, mob deaths (3 of the 4 relay runs): stage s15 (live zombie, dark tunnel):
  the fight macro landed 1 swing for 15 hp taken ahead, found nothing behind; corpus: blind
  fightback 3x / 0 damage, bunker 0 of 4 completed, flee 3x. Stage s16 (zombie behind the avatar at
  its mining face): the old precedence (second hit -> fightback/flee) ran into the face, 20 -> 5 hp.
  Change (uncommitted until s8 passes): BUNKER_HP 14 -> 17.5 (the first 3+ hit underground arms
  the bunker), the bunker is never abandoned for further hits, bunker precedes fightback/flee; a
  flee-then-seal reflex (two blocks across the passage) added as the no-pickaxe fallback
  (tests/test_seal.py). s16 run 3: bunker capped under the hits, 20 -> 11 hp, no damage after
  (`MCU/logs/stages/s16_seal_*` run3). s8 section E rewritten for the new behaviour; s8 running.
- gen-4 (`ob4_mfm`) died at step 1413 to a zombie at y 26 during a stair_down (fightback dealt 0):
  the kit is gone, the run is spent.

## Next

- Watch gen-4 (obsidian from the lip?) and obf2 (diamond via the seeded sites, then the lake); on their
  end read scores/milestones, fix what they show, relaunch.
