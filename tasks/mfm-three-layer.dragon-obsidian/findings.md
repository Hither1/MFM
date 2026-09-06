# Findings (decision-relevant only)

Evidence root: `Collab/MCU-AgentBeats/output/<arm>/episode_001/{memory/logs.txt,worldmodel_report.json}`.

1. **mine_obsidian never fired** in 105 full + 43 half + 7 portal runs. Best full run 11/24
   (kdc3z_logbook, kd14x_wm). Full runs never craft a bucket (0/105). Confidence: high (grep over all logs).
2. **Half task (kit at milestone 11)**: bucket ~170 steps, water filled in 34/43 (~700 steps; water at
   (-3013,70,-5580), 9 blocks from spawn, 22 runs); lava seen 5/43, poured 4/43, obsidian mined 0/43.
   All 5 sightings came from strip_mine's guard, none from `find_lava` (6-9 blocks per 360 ticks; the
   400-tick plan cap shrinks it to 112-398 ticks, "NOT STARTED" under 250). hd41z: 3500 steps trapped at
   the pond (dig_down refused near water, swimming stuck).
3. **After the pour** (hd12z A75-A80, hd39z A80-A85, hd32z A56-A61, hd43z A72-A75): flow pushes the
   avatar back, mined cell off by one (stone mined), source not scooped (out of reach 4.5-5.5 blocks),
   `mine_obsidian` shrunk to 74-102 ticks (needs ~190 + aim); 2 of 4 died within ~400 steps.
4. **Deterministic world**: spawn (-3009.5,71,-5572.5) in every run. Lava lakes recorded (LAVA AHEAD):
   (-2986,11,-5556) 52%, (-3029,10,-5545) 42%, (-3006,23,-5568) 35%, (-2995,8,-5544) 33%. Iron vein
   (-3024, 51-56, -5553). Deaths cluster at the two big lakes (kd26z_lb, kd35z_lb, kd29z2_lb).
5. **From scratch, 12k steps**: iron ore found in ~half the runs (median 6.3-8k), iron pickaxe 4/33 lb,
   12/46 wm, diamond 1/33, 1/46 at 10.5k+. 22/105 full runs died (inventory dropped). Relay
   (`--seed-memory`, distilled docs) took diamond 7->10/10 but dragon children fell 11->9/24: nothing
   about obsidian existed to inherit. Raw-log relay scored below control.
6. **mfm arm today**: `--seed-memory` skips `episodes` (worldmodel_purple_agent.py SEED_SKIP); mfm
   mode's `sweep_foreign` removes anything but logs/episodes/index/tools; `carry.py` is KiCad-only;
   `previous_expedition_log.txt` would be swept in logbook mode on this branch.
7. **Engine stage s5** verified pour+mine only on a 3x3 pool sunk one level, from a fixed rim; no
   stage covers a floor-level lake, the flow's push, or a guard-originated sighting.
8. Runs cost ~1-3 h per 12k steps locally (50-300 codex calls); green does not cap long-task steps.

## gen-1 / gen-1b (2026-09-06, confidence: high, evidence in progress.md)

- The `[KNOWN SITES]` block IS acted on: both runs went straight to the top-ranked line. That makes the
  ranking the lever: a 3% sliver's pour rim sent both to a stone rim over a lava pocket. Slivers now rank
  after lakes and pour rims need a lake sighting within 6 blocks.
- Water is the bottleneck after a failed pour: without the scoop back the run has no second pour and
  `make_obsidian` refuses ("you carry no water_bucket"). The scoop's ray must meet the source cell's top
  (centre hits the flow); verified on the engine (s12: 1 press).
- A melee mob at y 10 killed gen-1b with everything carried (health 5 -> 1 in one turn; the bunker
  dig was interrupted). Deaths cost the chain a whole life; no fix attempted (out of scope).
