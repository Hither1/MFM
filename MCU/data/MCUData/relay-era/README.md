# Relay-era records (MCU-AgentBeats, 2026-08-31 / 09-01)

The distillation-relay campaign: what happens when a run's structured world-model memory is
handed to the next run as its starting memory, on a benchmark whose world resets
deterministically between episodes. Headline: **mine_diamond_from_scratch is solved —
dm16_wm_high reached 10/10 milestones (score 100.0)** as the third relay generation, and the
controlled decomposition separates how much of that is chassis, inheritance, and distillation
quality.

## The three-factor decomposition

Same chassis, same model (gpt-5.6-sol, reasoning effort high), same 12,000-step budget,
same deterministic world (seed 0, fixed spawn). The only variable is what the run starts with:

| run | task | starts from | milestones (score) | model calls |
|---|---|---|---|---|
| dm15z_wm_high | diamond | from_scratch | **7/10 (70.0)** | 336 (+127 failed) |
| kd15z_wm_high | dragon | from_scratch | **7/24 (29.17)** | 286 (+145 failed) |
| dm14x_wm_high | diamond | distilled_relay&larr;kd12(cross-task) | **9/10 (90.0)** | 127 |
| kd14x_wm_high | dragon | distilled_relay&larr;dm11c(cross-task) | **11/24 (45.83)** | 137 |
| dm15_wm_high | diamond | distilled_relay&larr;dm14x | **9/10 (90.0)** | 273 (+130 failed) |
| kd15_wm_high | dragon | distilled_relay&larr;kd14x | **9/24 (37.5)** | 293 (+163 failed) |
| dm16_wm_high | diamond | distilled_relay&larr;dm15 | **10/10 (100.0)** | 159 |
| kd16_wm_high | dragon | distilled_relay&larr;kd14x | **9/24 (37.5)** | 127 |
| dm15_lb_high | diamond | raw_log_relay&larr;dm10_lb | **6/10 (60.0)** | 328 (+150 failed) |
| kd15_lb_high | dragon | raw_log_relay&larr;kd10_lb | **8/24 (33.33)** | 318 (+160 failed) |

Read vertically, three findings:

1. **Distilled relay compounds.** Diamond: from-scratch 7/10 -> one relay generation 9/10 ->
   dm16 (third generation) 10/10. Dragon: from-scratch 7/24 -> relay 9-11/24. Each generation
   inherits a registry of *verified* world facts (ore sites, shaft routes, hazards) plus
   procedures debugged in earlier lives.
2. **Raw-log inheritance does not.** The logbook arms inherit the parent's full append-only
   log (everything the worldmodel arms' distillation was made *from*), yet dm15_lb scored
   **below** the from-scratch control (6/10 vs 7/10). Inheritance per se is not the lever;
   distillation quality is.
3. **Call counts split by outage, not by seed.** The four outage-free arms (waves 4 and 6)
   finished 12,000 steps in 127-159 model calls (~75-94 steps per call); all six arms that
   crossed the provider outage needed 273-336 *successful* calls (~36-44 steps per call) on
   top of their failed retries — the outage fragmented planning into shorter arcs, not just
   burned retries. Because every outage-free arm happens to be a seeded one, steps-per-call
   cannot be cleanly attributed to memory maturity in this batch; treat it as an
   infrastructure effect.

dm16's full milestone line: `mine_log@480 crafting_table@1131 wooden_pickaxe@1323 mine_cobblestone@2085 stone_pickaxe@3427 furnace@3494 mine_iron_ore@4446 iron_ingot@5568 iron_pickaxe@6330 diamond@11444`.

## How the relay works

- `--seed-memory <parent>/episode_001/memory` copies the parent run's final memory directory
  into the child's workspace before step 1. Nothing else transfers: fresh world, fresh
  inventory, fresh position, fresh session.
- The child is told, in its standing memory preamble, that the world has reset: coordinates
  and terrain facts stay valid, everything built or emptied is restored (an "exhausted" ore
  site is full again), and stale goals must be re-derived. Internalising these reset
  semantics is itself part of what the later generations learned; dm16's registry marks
  sites with per-run exhaustion annotations.
- The logbook (`raw-log-relay`) arms are the symmetric probe: `--seed-log` hands the child
  the parent's raw `logs.txt` instead of a distilled memory.
- Cross-task seeding works: dm14x (diamond) started from kd12's *dragon* memory, kd14x from
  a diamond run's, and both set records for their tasks. The two tasks share their first
  eight milestones, so a good registry transfers.

`lineage/LINEAGE.md` draws the full family tree; `lineage/<arm>_final_memory/` holds each
generation's distilled documents alone (world_model/, locations/, procedures/, hypotheses/,
...) without the bulky per-turn logs, so the evolution of the memory can be diffed directly.

## Setup

- Model: gpt-5.6-sol via codex CLI, reasoning effort high, one model turn per session
  (cold start every call). Plan-based control: each call returns a whole action plan
  (<=40 entries), the evaluator plays it out.
- Episode: 12,000 env steps for BOTH tasks (this era runs diamond at the long-task budget;
  the dm4-era batch used 6,000), step_timeout 600 s, CODEX_MAX_CALLS 4000 (never hit —
  verified zero ceiling markers in every log).
- Environment: MCU-AgentBeats green agent (MineStudio), world seed 0, fixed spawn
  (-3009.5, 71, -5572.5), identical across all runs and both tasks.
- Milestones are environment-verified; score = 100 x milestones / total.
- Code: branch `claim-m-substrate`. Wave-4 and the wave-5 worldmodel/from-scratch arms ran
  commit `e1785d15`; the wave-5 logbook arms and waves 6-7 ran `70825f83` (delta between
  the two: the `--seed-log` launcher plumbing only — the agent chassis is byte-identical).
  `code-relay-era-70825f83.tar.gz` in this directory is the exact `git archive` of 70825f83.

## Provider-outage disclosure

The six wave-5 arms (dm15z, kd15z, dm15, kd15, dm15_lb, kd15_lb) flew through a 2h20m
model-provider quota outage (08-31 08:05-10:24). The evaluator holds its request while the
agent retries, so **sim steps did not advance during the outage — no step budget was lost**,
but failed retry calls were burned: that is the "+N failed" column above. Waves 4, 6 and 7
were outage-free (0 failed calls).

## Layout per run

Same as `claim-m-records/`: `trajectory/episode_001/` (memory filesystem incl. full
`logs.txt`, per-turn codex records, `worldmodel_report.json`), `result.json` (benchmark
output), `episode_1.mp4` (full-episode evaluator video), plus `milestone_tracking.json`
(the evaluator's own milestone timeline) new in this batch.

## Paths are anonymised

Same protocol as the rest of this dataset: repository checkout -> `<REPO>`, home directory
-> `<HOME>`, per-arm codex home -> `<CODEX_HOME>`, OS username -> `user` (7,875
substitutions across 19,340 text files; 1,908 binary files byte-identical to the originals).
Post-pass scan: zero identity strings, zero credential patterns, zero e-mail addresses.

## Pending

Wave 7 (dm17 <- dm16, and kd17 <- dm16 cross-task) was still in flight when this batch was
packaged; both runs will be added here on landing.
