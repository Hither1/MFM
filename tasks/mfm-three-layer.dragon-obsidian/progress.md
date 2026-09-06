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

## Next

- s5 result -> s12 run -> fix what they show -> commit MCU + MFM slices.
- gen-1 launch: `--agent mfm --task ender_dragon_half --steps 12000 --seed-memory <5 dirs>`.
