# Scoreboard

Every scored MCU-AgentBeats run on the two long-horizon tasks, as of 2026-08-28. Same model
(`gpt-5.6-sol`) and same step budget in every cell; the arms differ only in agent architecture.

- `runs.csv` — one row per run: score, milestones reached, milestone timeline, model calls.
- `summary.json` — the aggregates and cost figures below, machine-readable.

Scoring is `100 * milestones_reached / total`, a **count and not a sequence**: diamond has 10
milestones over 6,000 steps, dragon 24 over 12,000. Reaching them out of order scores the same.

## mine_diamond_from_scratch (6,000 steps, 10 milestones)

| arm | group | n | scores | mean | best |
| --- | --- | --- | --- | --- | --- |
| worldmodel | iteration (strategy block on) | 17 | 20–60 | 51.2 | **60.0** |
| worldmodel | ablation (strategy block off) | 2 | 50, 50 | 50.0 | 50.0 |
| worldmodel | frozen report batch, zero-edit | 3 | 40, 60, 60 | 53.3 | **60.0** |
| worldmodel | post-freeze validation | 1 | 60 | 60.0 | **60.0** |
| prolong | baseline, no knowledge injection | 1 | 40 | 40.0 | 40.0 |
| prolong | baseline, matched knowledge | 1 | 20 | 20.0 | 20.0 |
| worldmodel (pre-closed-loop) | baseline | 1 | 10 | 10.0 | 10.0 |
| default (upstream agent) | baseline | 1 | 0 | 0.0 | 0.0 |

Across all 23 comparable world-model runs: mean **51.7**, median 50.0, 60.0 in 11 runs (48%),
≥50.0 in 18 (78%), worst 20.0.

Fastest to 6/10: `dm4_wmv18` at step 3059. Fastest to 5/10: `dm4_wmv9` at step 2014.

## kill_ender_dragon (12,000 steps, 24 milestones)

| arm | group | n | scores | mean |
| --- | --- | --- | --- | --- |
| worldmodel | all runs | 4 | 25.0, 25.0, 25.0, 25.0 | **25.0** |
| prolong | baseline | 1 | 20.83 | 20.83 |
| worldmodel (pre-closed-loop) | baseline | 1 | 20.83 | 20.83 |
| default (upstream agent) | baseline | 1 | 0 | 0.0 |

All four world-model runs land on exactly 6/24, with zero variance. Both baselines stop at 5/24.

## The two tasks share one wall

No run of any arm on either task has ever mined iron ore. Diamond caps at 6/10, dragon at 6/24,
and **the six are the same six**: `mine_log`, `crafting_table`, `wooden_pickaxe`,
`mine_cobblestone`, `stone_pickaxe`, `furnace`. `mine_iron_ore` is the next milestone on both
chains and is where every run in this dataset ends.

The diagnosis behind that wall, from a trajectory audit of the runs published here:

1. **Displacement.** 58–97% of mining entries end with the agent having moved <0.5 blocks
   (`dm4_final3` 18/22, `ked_final1` 36/37) — the macros break blocks without advancing, so an
   iron search scans almost no fresh rock face. Both endgame agents independently re-derived
   the same physics in their own world-model files, each at a cost of >1,000 late-run steps.
2. **Detector precision.** The ore sentinel fired 4 times live across the campaign; all 4 were
   false positives (grass top, water-over-stone, dirt+gravel wall, tree bark), and the model
   correctly vetoed 4/4 by zooming the named frame. The verify layer works; the detector starves it.
3. **Light**, real but secondary: light-0 tunnels render at r≈21.6, below any colour detector.
4. **Silent cursor drops** on involuntary container closes when out of reach.

## Cost

Token accounting reads `turn.completed` usage from the codex event stream;
`input_tokens` includes `cached_input_tokens` as a subset.

| | score | model calls | tokens |
| --- | --- | --- | --- |
| worldmodel, diamond (frozen batch mean) | 53.3 | 62–66 | 13.36 M / run |
| prolong, diamond | 40.0 | 1,089 | 165.46 M |
| prolong + matched knowledge, diamond | 20.0 | 743 | 106.19 M |
| worldmodel, dragon | 25.0 | 104 / 127 | 19.5 M mean |
| prolong, dragon | 20.83 | 2,394 | **≥** 327.78 M |

Diamond: **12.4× fewer tokens, ~17× fewer calls**. Dragon: **≥16.8× fewer tokens** — a lower
bound, because only 806 of prolong's 2,394 dragon turns carry a usage record; the other 1,588
failed on usage limits and their server-side cost is unrecorded. That 66% failure rate is itself
a property of the per-tick architecture under a 12,000-step budget.

Per-call prompt size is comparable between the arms (~150–215K input tokens per call). The
multiplier comes from call count: the world-model arm advances 75–90 simulator steps per model
call, the per-tick baseline roughly one.

## Read these numbers carefully

- **Every baseline cell is n=1.** The matched-knowledge control scores *below* the no-knowledge
  prolong on diamond (20.0 vs 40.0). With one seed each, treat that inversion as GUI-grind
  variance rather than an effect — the two runs crafted their table at step 5,835 and 681.
- **Out-of-order banking is in the rules and is load-bearing.** Several 60-scoring runs bank the
  furnace before the stone pickaxe. Under strict sequential scoring the gaps between arms would
  look different.
- **On dragon the world-model margin is exactly one milestone.** It is also not a speed win:
  prolong is the *fastest* arm to 5/24 (step 3,294, against 3,699–9,035 for the world-model
  runs). The advantage there comes from endgame banking discipline, not front-chain throughput.
- **`dm4_wmv` is excluded from every aggregate** — it ran a 1,500-step budget, not 6,000.
- The strategy-block ablation is n=2. Both ablated runs hit 50.0 while 6 of 7 comparable coached
  runs hit 60.0; the ablated runs re-derived the same banking decision through the agent's own
  goal check, one induction cycle later than the coached runs. Read it as "coaching buys margin,
  not decisions", on two seeds.


## Relay era (added 2026-09-01)

`runs.csv` rows with group `relay_era` are the distillation-relay campaign (waves 4-6,
2026-08-31): from-scratch controls, distilled-memory relay chains, and raw-log relay
ablations on one chassis, both tasks at 12,000 steps. Headline: dm16_wm_high 10/10 (100.0)
— diamond solved by the third relay generation. Full story and per-run records in
`relay-era/`; NOTE the era's diamond budget is 12,000 steps, so diamond rows are not
comparable with the 6,000-step dm4-era aggregates above. The `codex_calls` column for these
rows counts successful calls only; failed quota-outage retries are broken out in
`relay-era/README.md`.
