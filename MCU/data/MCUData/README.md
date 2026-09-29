---
pretty_name: MCU long-horizon trajectories (dragon / diamond)
tags:
  - minecraft
  - agents
  - long-horizon
  - trajectories
  - llm-agents
size_categories:
  - n<1K
---

# MCU long-horizon trajectories — dragon / diamond

> **2026-09-01 — diamond solved. New `relay-era/` directory.** The distillation-relay
> campaign hands each run's structured memory to the next run as its starting state:
> **mine_diamond_from_scratch 10/10 (100.0)** by dm16_wm_high, third relay generation,
> and dragon's record **45.83 (11/24)** by cross-task-seeded kd14x_wm_high. The batch
> carries the full three-factor decomposition — from-scratch controls (70.0 / 29.17),
> distilled-relay chains (90 -> 90 -> 100 on diamond), and raw-log relay ablations that
> score *below* the controls on diamond — plus `relay-era/lineage/`, the per-generation
> distilled memories themselves. Both tasks run 12,000 steps in this era. Details in
> `relay-era/README.md`.

Trajectories from two long-horizon Minecraft tasks — killing the Ender Dragon and mining a
diamond from scratch — run under the MCU benchmark by several agent architectures, plus the
full scoreboard those runs sit in.

> **2026-08-29 — new records in `claim-m-records/`.** The claim-M campaign (structured
> world-model memory vs PRO-LONG's log memory on a byte-identical chassis, 12,000 steps,
> gpt-5.6-sol at high effort) retired this card's headline numbers: diamond is now
> **80.00** (8/10, both memory arms) and dragon **45.83** (11/24, worldmodel — iron
> pickaxe, diamond ore and diamond all banked; the diamond 23 steps before the horizon).
> The iron wall described below was broken by all four of those runs.
> `claim-m-records/` carries the four full trajectories (memory filesystem, per-turn
> codex records, report), the evaluator videos, per-run `result.json`, the code snapshot
> (`records-dm6kd6`, commit 9953e8d8), and its own README. Everything below this box
> describes the earlier dm4-era batch and its scoreboard, kept as the before/after.

The dm4-era batch below was produced on branch **`merge-agentbeats-main`** of
`Hither1/MCU`; the claim-m-records runs on branch **`claim-m-substrate`**.

## What is here

```
stats/                       the scoreboard: every scored run on both tasks
  runs.csv                   one row per run — score, milestones, timeline, model calls
  summary.json               aggregates, cost accounting, caveats
  README.md                  the same, written out

runs/                        agent workspaces, one .tar.gz per run

  top-scoring closed-loop runs (added 2026-08-28)
  dm4_final3.tar.gz    dm4_wmv22.tar.gz    dm4_wmv18.tar.gz          diamond, 60.00 each
  ked_final1.tar.gz    ked3_wmv15.tar.gz                             dragon,  25.00 each
  ked1_wmv12.tar.gz    ked2_wmv14.tar.gz                             dragon,  25.00 each

  earlier runs (08-23 / 08-24)
  dragon_pl.tar.gz     dragon_wm.tar.gz    night_dragon.tar.gz
  diamond_pl.tar.gz    diamond_wm.tar.gz   night_diamond.tar.gz
```

Each archive extracts to `<name>/episode_001/`. 13 runs, 177 MB compressed.

```python
from huggingface_hub import hf_hub_download
p = hf_hub_download("Ced-Collab/MCUData", "runs/dm4_final3.tar.gz", repo_type="dataset")
s = hf_hub_download("Ced-Collab/MCUData", "stats/runs.csv", repo_type="dataset")
```

## Scoring

`100 * milestones_reached / total`, a **count and not a sequence**. Diamond has 10 milestones
over a 6,000-step budget, dragon 24 over 12,000. Reaching them out of order scores the same,
and several of the runs here do exactly that.

## The seven top-scoring runs

All seven are the `worldmodel` arm on the closed-loop harness. They are the joint best score
on their task: **60.00 on diamond** (11 runs tied, 3 published here) and **25.00 on dragon**
(4 runs tied, all 4 published here).

| run | task | score | milestones | code at start | window |
| --- | --- | --- | --- | --- | --- |
| `dm4_final3` | diamond | **60.00** | 6/10, sixth at step 3467 | `436042b` ¹ | 08-26 09:21 → 10:57 |
| `dm4_wmv22` | diamond | **60.00** | 6/10, sixth at step 4760 | `bfb05b7` | 08-27 10:36 → 12:06 |
| `dm4_wmv18` | diamond | **60.00** | 6/10, sixth at step 3059 | `0f5ac26` | 08-26 03:52 → 04:55 |
| `ked_final1` | dragon | **25.00** | 6/24, sixth at step 7884 | `436042b` ¹ | 08-26 08:26 → 11:59 |
| `ked3_wmv15` | dragon | **25.00** | 6/24, sixth at step 8897 | `a2de9e8` | 08-26 05:50 → 08:21 |
| `ked1_wmv12` | dragon | **25.00** | 6/24, sixth at step 9101 | `0ecbf73` | 08-25 23:37 → 08-26 02:04 |
| `ked2_wmv14` | dragon | **25.00** | 6/24, sixth at step 9717 | `7efd05e` | 08-26 02:12 → 04:39 |

¹ HEAD at launch was `436042b`, but the world-model agent is frozen at `a2de9e8`; `436042b`
touches only the prolong baseline's knowledge injection. `dm4_final3` / `ked_final1` /
`ked3_wmv15` are therefore the three code-matched, zero-edit report-batch runs.

Why these three diamond runs out of eleven tied at 60: `dm4_final3` is the frozen report batch,
`dm4_wmv22` is the newest code, `dm4_wmv18` reached 6/10 faster than any other run in the
campaign. `manifest.json` carries a one-line note on what each run is good for, plus SHA-256
for every archive.

## Where the runs stop, and why it is the same place both times

*(dm4-era batch — superseded by `claim-m-records/`, where all four runs mine iron and
the dragon run reaches diamond.)*

**No run of this batch on either task ever mined iron ore.** Diamond caps at 6/10 and dragon
at 6/24, and the six are the same six: `mine_log`, `crafting_table`, `wooden_pickaxe`,
`mine_cobblestone`, `stone_pickaxe`, `furnace`. `mine_iron_ore` is next on both chains.

A trajectory audit of the runs published here puts the wall in this order:

1. **Displacement.** 58–97% of mining entries end with the agent having moved less than half a
   block — `dm4_final3` 18/22, `ked_final1` 36/37. The macros break blocks without advancing,
   so an iron search scans almost no fresh rock face. Both endgame agents independently
   re-derived the same physics into their own `world_model/dynamics.md`, each at a cost of more
   than a thousand late-run steps, and each losing it when the episode ended.
2. **Detector precision.** The ore sentinel fired four times live across the campaign; all four
   were false positives — grass top, water-over-stone, a dirt-and-gravel wall, tree bark. The
   model zoomed the named frame and correctly rejected 4/4. The verify layer works; the detector
   starves it. (`ked3_wmv15` carries two of the four, with the frames.)
3. **Light**, real but secondary: light-0 tunnels render at r ≈ 21.6, below any colour detector.
4. **Silent cursor drops** when a container auto-closes out of reach mid-move — this cost
   `ked3_wmv15` its stone pickaxe and its endgame.

## Scoreboard

Full tables in `stats/`. The headline, same model (`gpt-5.6-sol`) and same budget in every cell:

| task | arm | n | mean | best |
| --- | --- | --- | --- | --- |
| diamond | worldmodel, closed loop | 23 | 51.7 | **60.00** |
| diamond | prolong (per-tick baseline) | 1 | 40.0 | 40.00 |
| diamond | prolong + matched knowledge | 1 | 20.0 | 20.00 |
| diamond | worldmodel before the closed loop | 1 | 10.0 | 10.00 |
| diamond | default (upstream agent) | 1 | 0.0 | 0.00 |
| dragon | worldmodel, closed loop | 4 | 25.0 | **25.00** |
| dragon | prolong (per-tick baseline) | 1 | 20.83 | 20.83 |
| dragon | worldmodel before the closed loop | 1 | 20.83 | 20.83 |
| dragon | default (upstream agent) | 1 | 0.0 | 0.00 |

Cost, from `turn.completed` usage in the codex event stream: a 60-point diamond run costs
**13.4 M tokens over 62–66 model calls**, against **165.5 M over 1,089 calls** for the per-tick
baseline — 12.4× fewer tokens. On dragon the ratio is **≥16.8×**, a lower bound because 1,588 of
prolong's 2,394 dragon turns failed on usage limits and their server-side cost is unrecorded.

Three things to hold onto before quoting any of this: **every baseline cell is n = 1**; the
matched-knowledge control scores *below* the no-knowledge one on diamond (20.0 vs 40.0, which
with one seed each is variance, not an effect); and on dragon the closed-loop margin is exactly
one milestone, with prolong actually the *fastest* arm to 5/24. `stats/README.md` spells all
three out.

## The earlier six runs

The 08-23 / 08-24 archives predate the closed-loop harness and are kept for the before/after.

| run | arm | task | code at start | window | eval score |
| --- | --- | --- | --- | --- | --- |
| `dragon_pl` | prolong | kill_ender_dragon | `107e4da` | 08-24 04:02 → 08-25 01:18 | **20.83** / 100 |
| `dragon_wm` | worldmodel | kill_ender_dragon | `107e4da` | 08-24 04:04 → 08-24 22:17 | **20.83** / 100 |
| `diamond_pl` | prolong | mine_diamond_from_scratch | `8481a3a` | 08-24 10:05 → 08-25 01:10 | **0.00** / 100 |
| `diamond_wm` | worldmodel | mine_diamond_from_scratch | `8481a3a` | 08-24 11:58 → 08-25 01:11 | *unscored* — see below |
| `night_dragon` | prolong | kill_ender_dragon | `a28f3c1` | 08-23 14:21 → 18:02 | *unscored* |
| `night_diamond` | prolong | mine_diamond_from_scratch | `a28f3c1` | 08-23 14:21 → 18:02 | *unscored* |

Three of those six have **no evaluator score**, and that is a property of the data, not a gap in
this package:

- `diamond_wm` — its evaluator directory `20260824_115735_52966` is empty: no `result.txt`, no
  video. The run itself finished and self-reports 4/10 milestones in `worldmodel_report.json`.
  Under the mapping verified on `dragon_wm` that *would* be 40.00, but no evaluator ever wrote it
  down. **Treat it as unscored.**
- `night_dragon` / `night_diamond` — earlier exploratory runs from 08-23; both evaluator
  directories are empty.

`dragon_wm` is the one case where the two sides can be checked against each other: its
`worldmodel_report.json` reports `completion_rate` 0.20833 (5 of 24 milestones), and the
evaluator independently returned 20.83 / 100.

## The default arm has no trajectory here

The comparison is prolong / worldmodel / **default**, but no default-arm archive appears above.
That is not an omission.

The default arm is `test_purple_agent.py`, the upstream MCU-AgentBeats agent. It writes no
workspace of its own — no transcripts, no memory, no frames. Its entire output is
evaluator-side: `episode_1.mp4`, `result.txt`, `milestone_tracking.json`. On both tasks it
scored **0.00** (`logs/dg_client_bl.log`, `logs/dm_client_bl.log`), and that score is in
`stats/runs.csv`. Anyone building a three-way comparison from this data needs the evaluator
artefacts for that arm, which are not in this package.

## Layout

Each archive extracts to `<name>/episode_001/`, holding whichever set its arm writes.

**worldmodel arm** (`dm4_*`, `ked*`, `dragon_wm`, `diamond_wm`)

| path | what it is |
| --- | --- |
| `memory/` | the filesystem memory: `world_model/`, `hypotheses/`, `procedures/`, `episodes/`, `locations/`, `entities/`, `events/`, `maps/`, `notes/`, `tools/` |
| `memory/logs.txt` | the agent's own step log — each section carries a `[FRAME]` pointer |
| `codex_turns/` | per-turn request/response records (`*.prompt.txt`, `*.events.jsonl`) |
| `worldmodel_report.json` | steps, turn breakdown (act / induction / act_failed), milestone tracking |

**prolong arm** (`dragon_pl`, `diamond_pl`, `night_*`)

| path | what it is |
| --- | --- |
| `transcripts/` | per-turn `*.prompt.txt`, `*.events.jsonl`, `*.stderr.txt` — the full codex exchange |
| `actions.json` | the action stream sent to the simulator |
| `AGENTS.md` | the system prompt the run was given |
| `logs.txt` | the agent's own step log |
| `last_message.txt` | final assistant message |

## Frames

The **seven closed-loop runs keep their frames.** Those runs wrote no bulk `frames/` directory —
only the curated set under `memory/episodes/*/frames/`, 56 to 133 PNGs per run, which is exactly
what the run's own `logs.txt` `[FRAME]` pointers address. Keeping them means the text-as-index
behaviour is reproducible from the archive alone: when the agent zooms a frame to adjudicate a
detector flag, the frame it looked at is in the tarball.

The **earlier six runs** each wrote a full-resolution `frames/` — the first-person view at every
step, 640×360 PNG at roughly 350 KB a frame, **6.2 GB** across the six against 35 MB for
everything else. Those were left behind. They are still on the origin host at
`output/<run>/episode_001/frames/`; if they are ever wanted here, encode per run rather than
committing PNGs — the evaluator's own `episode_1.mp4` renders the same trajectory at 30–80 MB.

## Paths are anonymised

These are agent transcripts, so they quote whatever the agent saw — including `ls` output and
absolute paths on the machine the runs happened on. Substitutions applied before publishing:

| original | replacement | first six runs | seven runs added 08-28 |
| --- | --- | --- | --- |
| the repository checkout path | `<REPO>` | 13,784 | 3,677 |
| the user's home directory | `<HOME>` | 535 | 0 |
| the codex home directory | `<CODEX_HOME>` | — | 7 |
| the OS username (owner/group columns in captured `ls` output) | `user` | 2,770 | 332 |

Nothing else was altered: no transcript content, no timestamps, no scores. Binary files were
left byte-identical. After the pass, zero occurrences of the OS username or of any `/datapool/`
path remain anywhere in the package, binaries included. All runs were scanned for credentials
before packaging — no API keys, tokens, bearer strings, or e-mail addresses are present.

When reproducing, read `<REPO>` as your own checkout of `Hither1/MCU` and `<HOME>` as your own
home directory.

## Reproducing a run

```bash
git checkout merge-agentbeats-main
git checkout <code_head_at_start>          # from manifest.json
scripts/run-arm.sh --arm <name> --agent <prolong|worldmodel> \
                   --task <kill_ender_dragon|mine_diamond_from_scratch> \
                   --green-port <free> --purple-port <free> --steps <6000|12000>
```

Two caveats before treating that as an exact replay. `code_head_at_start` is reconstructed from
commit timestamps against each run's earliest artefact mtime, not stamped by the launcher, so an
uncommitted working-tree change at launch would not show up in it. And for the earlier pair, the
dragon runs launched at 04:02 and 04:04 on 08-24 while `8481a3a` landed at 04:12:56 — ten minutes
*into* the run; the running processes were unaffected, but the tree changed underneath them.
