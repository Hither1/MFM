# Task Plan: dragon-obsidian

## Stable Anchor

- Scientific question: can the MFM arm (logbook chassis + episode store) on the dragon task get past
  `mine_obsidian` (milestone 14/24, never reached in 148 runs) by reusing its own previous lives'
  records, and does a larger step budget then carry the chain further?
- Target claim or outcome: a relay chain of mfm runs (each seeded with the previous lives' records)
  banks `mine_obsidian` on `ender_dragon_half`, then a 24k-step full `ender_dragon` run seeded the
  same way scores above the 45.83 (11/24) record.
- Success criterion: `MILESTONE mine_obsidian verified` in a half-task run; then full-task score > 45.83.
- Constraints and budget: local node only (255 cores, load ~20; `/` has 13 GB free so codex homes
  and /tmp engine only; outputs on data3); codex via `~/ccr/bin/codex` (API key, `CODEX_BIN`);
  one arm at a time unless CPU allows; all changes on branch `dragon-obsidian` in both repos
  (MFM and its `MCU` submodule = worktree of MCU-AgentBeats at `MFM/MCU`).
- Non-goals: no hand-written coordinates or facts (only what previous runs recorded); no change to
  the worldmodel/direct/logbook arms' measured behaviour beyond the shared macro fixes and the
  doctrine paragraph (pins re-recorded with the diff named); no Nether/End work.

## Current Cycle

- Working hypothesis: the obsidian chain fails for three mechanical reasons (corridor `find_lava`
  never sees lava; after a pour the flow pushes the avatar and the mined cell is wrong or the
  procedure is shrunk below the 190-tick break time; no coordinates survive across lives). Fixing the
  macros and pushing previous lives' verified sites (water, lava lakes, ore) into the turn prompt
  makes `mine_obsidian` reachable within the half task's 12k steps.
- Main uncertainty: whether the model acts on a `[KNOWN SITES]` block (lad3 showed narration
  is weakly read) and whether the pour/mine macros survive a real lake (only a 3x3 sunk pool was
  ever staged).
- Next decisive experiment: gen-1 half-task mfm run seeded from the existing half runs' logs
  (hd12z, hd39z, hd32z, hd43z, hd41z), after the macro fixes pass the engine stage.
- Expected pass/fail signal: `mine_obsidian` fires (pass); or the run reaches the lake and the pour
  or mine fails again (mechanics still wrong); or never reaches the lake (sites block not acted on).
- Fallback: seed gen-2 from gen-1 plus the same logs; if the model ignores the block, turn the
  known lava site into a refusal-style push (a plan without `make_obsidian` while standing at a
  known rim with a water bucket is refused once).

## Success Criteria

- [ ] Half-task relay run banks `mine_obsidian` (green log / worldmodel_report.json milestones).
- [ ] Engine stage `s12_obsidian` green: pour at a floor-level 5x5 lake, scoop back, mine one obsidian.
- [ ] Chassis pins green (logbook log/actions unchanged; prompt hashes re-recorded for the doctrine diff).
- [ ] Full-task 24k run seeded from the chain scores > 45.83.

## Parallel Tracks

| track | owner | mode | worktree / branch | dependency | deliverable | status |
|---|---|---|---|---|---|---|
| primary | primary | integrate | MFM `dragon-obsidian` + MFM/MCU `dragon-obsidian` | none | macros, carry, doctrine, launches, synthesis | active |

## Phases

### Phase 1: Discover and specify
- [x] Trajectory analysis (148 dragon runs) and code reading; findings recorded.
- [x] Branches and worktree; chassis pins green at baseline (10 tests).
- **Status:** complete
- **Evidence:** findings.md; `PYTHONPATH=.:<pytest_shim> ../MCU-AgentBeats/.venv/bin/python -m pytest tests/test_pins_chassis.py` -> 10 passed.

### Phase 2: Implement
- [x] A. Chassis macros: `_min` tick floor at compile time (find_lava, fetch_water, mine_obsidian); `LAST_LAVA` sighting so `make_obsidian()`/`mine_obsidian()` default to the sighting's cells; closed-loop scoop-back and closed-loop obsidian mining; water-refusal names a `go_to` away from the water.
- [x] B. Carry for mfm: `--seed-memory` (repeatable) links previous lives under `previous/`, merged `previous/index.jsonl`, `previous` kept by the sweep; `[KNOWN SITES]` block from previous records (index rows + logs.txt notes) pushed into the turn prompt.
- [x] C. Doctrine: bucket right after the iron pickaxe, fill before the descent, lakes not corridors, known sites first.
- [x] D. Launcher: `CODEX_BIN` default `~/ccr/bin/codex`, `PYTHONPATH` to the MFM root, `--seed-memory` passthrough, `--steps 24000` for full runs.
- [~] E. Tests: unit green (10), pins re-recorded; engine s5 (pour ok, mine fixed to swing through the rim), s12 running.
- **Status:** in_progress
- **Evidence:** none yet

### Phase 3: Run and interpret
- [ ] gen-1 half-task mfm run (seeded from existing half logs) -> mine_obsidian?
- [ ] gen-2/3 as needed; then full 24k seeded run.
- **Status:** pending
- **Evidence:** none

## Decisions And Blockers

| Item | Decision or blocker | Evidence / owner |
|---|---|---|
| macro fixes in scope | yes (user, 2026-09-06) | user message |
| coordinates | only from previous runs' own records; no hand-written facts | user message |
| steps | 24k first for full runs | user message |
| where to run | local node; watch CPU/mem/disk | user message |
| branch | `dragon-obsidian` in MFM and MCU | user message |
| MCU checkout | worktree of MCU-AgentBeats at `MFM/MCU` (submodule path), based on hither/mfm-three-layer + cherry-picks c1da5101 b5599690 | git log |
| pytest | run venv lacks pytest; shim copied from la-rna-bb (py3.11) into scratchpad `pytest_shim` | this session |

## Verification Contract

- Command or probe: `cd MFM && PYTHONPATH=.:<shim> ../MCU-AgentBeats/.venv/bin/python -m pytest tests -q`; `cd MFM/MCU && bash probes/run_stage.sh -m mcu_worldmodel.stages.s12_obsidian`
- Expected signal: pins green (re-recorded ones listed in progress.md), s12 checks all pass
- Experiment/run pointer, if any: `MFM/MCU/output/<arm>/episode_001/worldmodel_report.json`, `MFM/MCU/logs/<arm>_*.log`

## Next Action

Read the s12 engine stage result (`MFM/MCU/logs/stages/s12_obsidian.log`); if green, rerun s5, commit both repos, launch gen-1 (`ob1_mfm`, half task, 12k steps, 6 seed lives).
