# Claim-M record runs (MCU-AgentBeats, 2026-08-29)

Best-scoring trajectories of the claim-M experiment: a structured world-model memory
(`worldmodel`) vs PRO-LONG's append-only log memory (`logbook`) on an otherwise
byte-identical chassis (same skills, perception, caps, knowledge; only the memory
protocol differs).

## Runs

| run | task | score | milestones (step) |
|---|---|---|---|
| kd6_wm_high | ender_dragon | **11/24 (45.83)** — project record | log 419, table 818, wood_pick 1175, cobble 2563, stone_pick 2663, furnace 3798, iron_ore 7522, ingot 8154, iron_pick 9161, diamond_ore 11887, diamond 11977 |
| kd6_lb_high | ender_dragon | 6/24 (25.0) | stalled after furnace 5124 |
| dm6_wm_high | mine_diamond_from_scratch | **8/10 (80.0)** — record (tie) | ... iron_ore 8109, iron_ingot 9781 |
| dm6_lb_high | mine_diamond_from_scratch | **8/10 (80.0)** — record (tie) | ... iron_ore 6522, iron_ingot 7149 |

## Setup

- Model: gpt-5.6-sol via codex CLI, reasoning effort high, one model turn per session
  (payload-wall mitigation), auto-compact disabled by limit.
- Episode: 12000 env steps, step_timeout 600 s, plan caps 40 entries / repeat 200 /
  400 ticks per entry, CODEX_MAX_CALLS 4000 (never hit).
- Environment: MCU-AgentBeats green agent (MineStudio/MineRL), world seed 0,
  fixed spawn (-3009.5, 71, -5572.5) — identical across all runs and both tasks.
- Code: MCU-AgentBeats claim-m-substrate branch, commit 9953e8d8
  (tag `records-dm6kd6`). Known symmetric flaw during these runs: place_block world
  clicks tripped a GUI guard (fixed later in f50d42e3).
- Milestones are environment-verified (game statistics), derived agent-side by a
  shared ledger; score = milestone count.

## Layout per run

- `trajectory/episode_001/memory/logs.txt` — the full append-only action/state/note log
- `trajectory/episode_001/memory/world_model/` — compiled documents (worldmodel arm)
- `trajectory/episode_001/memory/hypotheses/`, `procedures/` — belief graph, recipe cards
- `trajectory/episode_001/worldmodel_report.json` — turn/guard/codex counters
- `result.json` — the benchmark evaluation output
- `episode_1.mp4` — full-episode video from the green agent's recorder

## Code

`code-records-dm6kd6-9953e8d8.tar.gz` in this directory is the exact source snapshot
(`git archive`) of commit 9953e8d8 — the version every run here executed. The same commit
is tagged `records-dm6kd6` on `Hither1/MCU` branch `claim-m-substrate`.

## Paths are anonymised

Same protocol as the rest of this dataset: repository checkout -> `<REPO>`, home
directory -> `<HOME>`, per-arm codex home -> `<CODEX_HOME>`, OS username -> `user`
(5,615 substitutions across 816 text files). Binary files (frames, videos) are
byte-identical to the originals. Post-pass scan: zero identity strings, zero
credential patterns, dataset-wide.
