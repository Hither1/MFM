# Task Plan: spatial-grid

> **Protocol (user, 2026-09-07 02:20): no previous-life memory outside MFM's own reuse.**
> The harness-digested `[KNOWN SITES]` (sites, corridors, frame pointers) is not allowed;
> memory reuse is the MFM carry only -- earlier lives' records linked under `previous/`
> for the model to read (`grep`, `./tools/episodes.py --previous`). It is now the mfm
> option `--sites` (default off, kept to reproduce the ob chain). The ob1..obf3 chain
> ran with the pushed sites, so its lives are contaminated as seeds and its runs are not
> a baseline: og1/og2 (launched 02:11/02:15 with sites+corridors and ob seeds) were
> stopped at ~step 700 / ~200. Clean seeds = the 12 first-generation lives. Baseline for
> the navigation claim = the historical half runs (no previous lives) in findings.md.

> **Phase 2 (user, 2026-09-07 04:35): the Astra-aligned protocol.** After comparing with
> wz1119/Codex-Minecraft-Gameplay and da03/astra-plays-gta: gpt-6-astra at effort high, a long
> step budget with a wall-clock cap, one session for the run (session-turns 0 + compaction,
> 320x180), memory modes kept. Question: which of their advantages carry -- budget, one
> context, the model, a thin contract with model-held control (`--thin`, `watch`)? Arms:
> og8 (full contract) vs og9 (`--thin`), both 60k steps / 10h / same seeds (og9 also has
> og5). Read-outs per compare.py: milestones and their steps, deaths, water->lava, churn,
> turns per 1k steps, references/ reads (codex_turns), watch calls. Gen-2 on gpt-5.6:
> og5 54.17 (13, no death), og6 45.83 (11, 1 death), og7 running.



## Stable Anchor
- Question: does a harness-maintained 3D cell map (built from exact positions and the runner's own
  events, no benchmark change) remove the navigation losses that eat the dragon budget: blind go_to,
  the pond trap, remembered-site re-opens, and the standing-still churn?
- Target claim: a half-task mfm run on the map-aware code spends fewer steps on those four losses
  (pond escape < 300 steps, reopen by pose succeeds, blocked go_to resolved via walked cells) and
  reaches the lake with more budget left than the ob chain (water at ~700, lake at 7600 in ob3).
- Success criterion: engine stages green (pond escape, reopen-by-pose, detour), replay over the 148
  logs shows walked detours existed for most blocked go_to's, then one half run beats ob3's
  water-to-lake leg and the churn fraction.
- Constraints: purple side only; observation/action/scoring untouched; branch `spatial-grid` in
  `Collab/MFM-grid` (MFM) and `Collab/MFM-grid/MCU` (MCU worktree, from dragon-obsidian 54ed3c9f);
  the `dragon-obsidian` worktree is being edited by another live session (seal slice): never touch it.
- Non-goals: no model-written maps; no hand-written coordinates; no Nether/End; no mob/combat work.

## Current Cycle
- Hypothesis: the four losses share one cause, the harness knows where the avatar has stood and what
  it did there, and throws it away; a map plus three map-aware macros recovers most of it.
- Main uncertainty: whether cell-exact facts (walked cells, placement pose) are enough without
  voxels, i.e. whether the detour over walked cells exists often enough (replay check answers this).
- Next decisive experiment: S1 grid + S2 consumers, engine stages s17-s19, replay over 148 logs.
- Expected signal: stages green in < 300 ticks each; replay: >50% of blocked go_to's had a walked
  cell within 3 blocks of the target's line. Fallback: if detours are rare, keep S2b (reopen by pose)
  and S2c (pond escape) and drop the go_to rewrite.

## Slices
- [x] S1 `mcu_worldmodel/grid.py`: sparse cell map, per-tick fill (walked/floor, broken, placed +
      opening pose, water, lava, hazard, blocked), `memory/grid.jsonl` persisted, kept by the sweep.
- [x] S2a map-aware go_to: on block, route via walked cells (BFS) toward the target; note names the route.
- [x] S2b reopen by pose: use_until_gui(item=) first replays the pose that opened it.
- [x] S2c pond escape: the water refusal names a walked cell >= 8 blocks from water and walks there.
- [x] S2d `[MAP]` block in the turn message (5 lines: cell, routes to base/water/table, hazards).
- [x] S3 cross-life (`--corridors`, mfm option): dry corridors from previous lives' [STATE] trajectories into [KNOWN SITES].
- [x] S4 churn watchdog (harness) + `--expect` protocol (mfm option): plan-level null streak per cell, label-agnostic veto after 3 null entries of
      any label with no screen open, objective switch after 1200 null steps.
- [~] Stages s17_pond, s18_reopen, s19_detour written (running); replay tool done (57-65% detours, 85-96% escapes); unit tests 59 green.
- [ ] Half run on the map-aware code vs ob3/ob4.

## Decisions And Blockers
| Item | Decision | Evidence |
|---|---|---|
| branch/worktree | `spatial-grid` in MFM-grid + MFM-grid/MCU | user 2026-09-06 23:xx |
| dragon-obsidian worktree | owned by the other live session (agent.py edited 23:37, s16 stages) | ls/ps 23:42 |

## Verification Contract
- `cd MFM-grid && PYTHONPATH=.:<pytest_shim> MCU/.venv/bin/python -m pytest tests -q`
- `cd MFM-grid/MCU && bash probes/run_stage.sh -m mcu_worldmodel.stages.s17_pond` (and s18, s19)
- replay: `MCU/.venv/bin/python tools/grid_replay.py <logs.txt>...`

## Next Action
(2026-09-07 12:05, user asleep, autonomous) Five arms in flight to their 10h caps: og10/og11
(304bae53, 15:26), og12/og13 (421aa327, 17:50), og14 (ed34754c, thin + atoms + own, 19:30).
No stagnation stops (user rule 10:5x). MCU spatial-grid-merge 6f79b0e6 = ed34754c + SHAFT AHEAD
guard + lava-guard cooldown + lava CLOSER clause + gravel line + mid-air cells + FELL guard
(progress.md 10:35, 10:45, 12:00); tests 92. Launch og16_mfm NOW from MFM-grid-merge-mcu
(thin, fixed library, from scratch, ports 9105/9115, 10h): the first arm with the new guards,
og13's twin otherwise. At each cap: compare.py + toolcalls.py, record. After og14's cap
(19:30): ff the live MFM-grid/MCU to 6f79b0e6, bump the submodule, launch og15 = og14's
settings seeded with og14's life only (the self-harness task_plan S6). Read-outs: thin vs full
(og10/og11, og12/og13), pool-fix (og12/og13 vs og10/og11), guards (og16 vs og13: deaths,
falls, lava stops, steps to obsidian), self-harness (og14 vs og13). Candidates: the turn
prompt carrying the last plan's log sections (E), the portal-frame placement check (C).
