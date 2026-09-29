# The mfm arm on branch `spatial-grid`: options and how to run

The active development branch of this fork (MCU `spatial-grid`, edited on
`spatial-grid-merge`; MFM `spatial-grid`) runs one purple agent,
`worldmodel_purple_agent.py --memory mfm`: the world-model chassis (procedures, GUI cursor,
milestone ledger, the runner's tick loop) with the **Multimodal Filesystem Memory** beside
its log (`episodes/` with a frame per plan entry, `index.jsonl`, `tools/episodes.py`), the
**carry** of earlier lives' records under `previous/`, and the experiment options added in
September 2026: the thin contract, the atoms, the model's own scripts and reflexes, the
meta-level skill package, the visual-only and human-play settings, the Nether lock. This
file explains what each option means, how to launch an arm, and where its results land.
The chassis itself is documented in `mcu_worldmodel/README.md`; the general arm runner in
the top of `README.md`.

## Worktrees and branches

| Checkout | Branch | Role |
| --- | --- | --- |
| `Collab/MFM-grid` | MFM `spatial-grid` | the `mfm` package (episode store, retrieval), `tests/`, `tasks/` (plans, progress, findings, read-out scripts) |
| `Collab/MFM-grid/MCU` | MCU `spatial-grid` | the LIVE checkout: arms are launched from here and import from here |
| `Collab/MFM-grid-merge-mcu` | MCU `spatial-grid-merge` | the scratch checkout: edit, unit-test and stage-test here, then `git merge --ff-only spatial-grid-merge` in the live checkout |

A running arm loaded its Python at start, so fast-forwarding the live checkout does not
change it; the next launch picks the new code up. `.venv` in both MCU checkouts is a
symlink to `Collab/MCU-AgentBeats/.venv`. The mfm store is the `mfm` package of the MFM
repo, so `PYTHONPATH` must contain the MFM root: `run-arm.sh` puts `${MFM_ROOT:-$ROOT/..}`
there, which is right from `MFM-grid/MCU` and wrong from `MFM-grid-merge-mcu` (set
`MFM_ROOT=.../MFM-grid` when launching from the scratch checkout).

## Options

All options are flags of `worldmodel_purple_agent.py`, passed through `run-arm.sh
--wm-extra "..."` (from `launch-og.sh`: the `WM_EXTRA` variable). Everything on this
branch needs `--memory mfm` (`--agent mfm` in `run-arm.sh`).

### Memory protocol

| Flag | Meaning |
| --- | --- |
| `--memory mfm` | the logbook protocol (append-only `logs.txt`, grep) plus the episode store: one `episodes/ep_NNNNNN/` per plan entry with the frame it started from, `state.json`, `action.json`, `outcome.json`; `index.jsonl`; `tools/episodes.py --last/--steps/--near/--tag/--action/--grep [--sheet out.png] [--previous]` |
| `--retrieval` | a harness-computed `[RECALL]` block in the turn prompt: entries that changed nothing in their last calls, what happened at this spot before, the entries that scored each milestone (`mfm.memory.retrieve`) |
| `--refuse` | veto a plan from the record: an entry that changed nothing in its last 5 calls anywhere, or a descent away from the placed table, unless the entry says `why` / `leave_table` |
| `--expect` | the prediction protocol: the briefing ends with `EXPECT: ...`, echoed next turn against the record as `[EXPECTED]` vs `[OBSERVED]` |
| `--frames` | `tools/zoom.py` in the workspace (the 2x2 sheet of this turn's event frames is attached in every mfm run unless `--no-event-sheet`) |
| `--no-event-sheet` | no 2x2 event sheet on the turn: the current view alone (the frames stay in `episodes/`) |
| `--frame-size WxH` | the frames attached to the model (the render is 640x360; 320x180 halves the image tokens and was the choice for gpt-6-astra; visual-only and human-play use 640x360 so the HUD reads) |
| `--seed-memory DIR` (repeatable) | the CARRY: the earlier life's record hard-linked under `previous/life_<i>/` (its `logs.txt`, `episodes/`, `index.jsonl`, `grid.jsonl`, `mine/`), oldest first; `previous/index.jsonl` merges their indexes for `--previous` queries. The contract says where they are; reading them is the model's act. A seed that itself carried lives contributes them (deduplicated by content) |
| `--sites`, `--corridors` | push the carried lives' verified places (`[KNOWN SITES]`) and dry corridors into the turn prompt. **Not the MFM protocol** (the harness remembering for the model); kept only to reproduce the ob1..obf3 chain of 2026-09-06, whose lives are contaminated as seeds. Do not use |

The user's rule (2026-09-07): memory reuse across lives is the carry alone, digested by the
model. With `--own` and previous lives, the contract adds one instruction
(`previous.MFM_DIGEST_NOTE`): the model's first act is its own `mine/digest.md`, carried on
with the rest of `mine/`. Clean seeds are the lives that never saw `--sites`: the 12
first-generation worldmodel/logbook lives in `MCU-AgentBeats/output/`, and the og arms.

### Contract and harness shape

| Flag | Meaning | Arms |
| --- | --- | --- |
| `--thin` | a one-page contract: task, memory protocol, response format, action schema, procedure index; the GUI, skills, survival and control sections go to `references/*.md` in the workspace, read on demand (`prompts.thin_split`). The default since 2026-09-07 (thin beat full on milestones per step in both pairs) | og11, og13-og22 |
| `--atoms` | the procedure set is `procedures.ATOMS` (28: closed-loop aims and walks, the GUI cursor, one-call craft, placements, the bucket, watch/pillar/eat/throw); the task-shaped macros (a tree, a strip mine, a shaft, the obsidian, the portal, the Nether, the End) are refused with a note. The model composes them | og14, og15, og20-og22 |
| `--own` | `mine/` persists across turns (the sweep keeps it) and is carried to the next life; `mine/procedures/<name>.py` scripts are procedures: run in a subprocess with the state on stdin and `--args '<json>'`, their printed plan (the actions.json shape) parsed with the same caps; depth 1; the `[OWN]` block lists them with call counts (`mcu_worldmodel/own.py`) | og14, og15, og19-og22 |
| `--own-reflexes` | `mine/reflexes/<name>.py` scripts run every 4 ticks while a plan executes (never in a screen, never during a runner escape) on the procedure state plus `lava_frac`, `health_prev`, `food_prev`, `pos_prev`, `entry`, `queue_len`, `runner_reflex`; quiet, or one JSON `{stop, note, actions}` (stop drops the plan, the note reaches the next turn as `[REFLEX <name>]`, actions run through the parser and governor); 40-tick cooldown per script, off after 3 failures until edited, at most 4. The contract names the classes to write first | og20-og22 |
| `--no-harness-reflexes` | the runner's own guards (lava, shaft, fall, water, the Nether lock and descent guard), escapes (bunker, pillar, flee, fightback, lava escape, swim-up), governor refusals and nudges are OFF, as in human-play; the atoms, the thin references and the memory stay; `references/survival.md` says the runner does not act. Needs `--own-reflexes` | og21, og22 |
| `--skills` | the meta-level skill package (`mcu_worldmodel/skills.py`): `skills/{memory,procedures,reflexes,harness}/SKILL.md` (frontmatter + doctrine, no world facts) with `scripts/` examples, written once per life and kept by the sweep; a `**Skills.**` paragraph in the contract; the reflex examples `lava_ahead`, `fell`, `hit`, `starving`, `known_hazards` under `skills/reflexes/scripts/`; nothing is installed under `mine/reflexes/` since 2026-09-08 (og21-og24 had the first four installed, active from tick 1) -- the model copies what it wants, `_name.py` retires one. Needs `--thin --own` | og21, og22 |
| `--visual-only` | the model is served the frame alone: no `[STATE]`/inventory/map text, no retrieval block, no event sheet; coordinate-free atoms (no go_to/look_at/look_abs/place_at/use_at); notes scrubbed of coordinates; nothing with a position on disk (`mcu_worldmodel/visual.py`). Needs `--thin` | og17 |
| `--human-play` | play like a person: the memory kept, the frame and the state text, no built-in procedure beyond the GUI cursor primitives and `watch`, no references, no advice, no reflexes, no governor; `--own` implied and the contract asks the model to invent its skills as scripts (`mcu_worldmodel/human.py`) | og18 |

### The runner's tick layer (on unless `--no-harness-reflexes` / `--human-play`)

Guards sampled every 4th tick in `agent.observe`: `_lava_guard` (lava in the lower view
while moving below y 40 stops the plan: LAVA AHEAD), `_shaft_guard` (the avatar about to
step into a walked column: SHAFT AHEAD), `_fall_guard` (landing after an unplanned 4+ block
free fall: FELL), `_water_guard` (water seen within reach, for the dig refusal), and in the
Nether `_nether_lock` (every moving plan action gets sneak, loses sprint and a moving jump;
one NETHER LOCK note per visit) and `_nether_descent_guard` (a plan entry that walked the
avatar a block down with lava in view: NETHER DESCENT). On a hit the runner arms one
escape (a bunker underground at 10 hp or less, a pillar on the surface at 6, a flee, a
fightback, the lava escape with the water bucket, the swim-up), the governor refuses plans
that keep changing nothing at one spot, and two nudges point at a sword and torches. Every
one of these writes a `[NOTE]`; their counts are in `cursor_stats` of
`worldmodel_report.json` (`lava_flagged`, `fall_stops`, `nether_lock_ticks`,
`nether_descents`, `pillar_reflexes`, `governor_plan_stalls`, ...).

### Model and session

| Flag | Meaning |
| --- | --- |
| `--model`, `--reasoning-effort` | the codex model and effort (`gpt-6-astra high` for og10-og21; `gpt-5.6-sol xhigh` for og22). The purple defaults are `gpt-5.6-sol medium`: always pass both |
| `--session-turns N`, `--compact` | resume one codex conversation for N turns (0 = unbounded) and let codex compact it instead of cold-starting; the og arms run `--session-turns 0 --compact` |
| `--codex-timeout` | seconds one turn may take (480 under the green agent's 600 s step timeout) |
| `--entry-cap 40 --repeat-cap 200 --step-cap 400` | a plan's size: entries, repeats of a raw action, ticks |
| `--max-steps` | the step budget shown to the model (the half task runs 60000 under a 10 h wall cap) |

## How to run

Everything goes through `scripts/launch-og.sh` (detached; pid in `logs/<ARM>_launch.pid`),
which calls `scripts/run-arm.sh` (green server + purple agent + evaluation client, each arm
on its own ports and codex home). Environment first:

```bash
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU      # the live checkout
export CODEX_BIN=$HOME/ccr/bin/codex                                      # the API-key account (the default)
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes   # codex homes: not /var/tmp
# from MFM-grid-merge-mcu also: export MFM_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid
```

`launch-og.sh` variables: `ARM` (output/<ARM>, the codex home name), `GP`/`PP` (green and
purple ports; the launcher refuses a busy port, and a failed start leaves its green server
listening, so a relaunch needs new ports), `STEPS` (default 12000; the og arms use 60000), `TASK` (default `ender_dragon_half`;
`ender_dragon` is the full task from nothing),
`SESSION_TURNS`, `COMPACT=1`, `WALL=10h` (a watchdog stops the arm by pid at that
wall-clock time; `logs/<ARM>_wall.log`), `WM_EXTRA` (the purple flags), and the seeds:
by default the 12 first-generation lives plus `GRID_SEEDS` (default `og3_mfm og4_mfm`,
names under this checkout's `output/`); `EXTRA_SEEDS="/abs/.../episode_001/memory ..."`
adds memory dirs by path; `EXTRA_ONLY=1` makes those the only seeds; `NO_SEEDS=1` runs
from scratch; `OB_SEEDS=1` adds the contaminated ob chain (never without `--sites`).

Recipes (the settings of the arms on record):

```bash
# thin, from scratch (og16's setting; og13 before the guards of 2026-09-07)
ARM=ogNN_mfm GP=91xx PP=91yy STEPS=60000 SESSION_TURNS=0 COMPACT=1 WALL=10h NO_SEEDS=1 \
WM_EXTRA="--expect --frames --retrieval --frame-size 320x180 --model gpt-6-astra --reasoning-effort high --thin" \
bash scripts/launch-og.sh

# memory reuse, digested by the model (og19): thin + own, the clean lives carried
ARM=ogNN_mfm GP=91xx PP=91yy STEPS=60000 SESSION_TURNS=0 COMPACT=1 WALL=10h \
GRID_SEEDS="og3_mfm og4_mfm og12_mfm og13_mfm og14_mfm" \
EXTRA_SEEDS="$M/og8_mfm/episode_001/memory $M/og9_mfm/episode_001/memory $M/og16_mfm/episode_001/memory $M/og17_mfm/episode_001/memory" \
WM_EXTRA="--expect --frames --retrieval --frame-size 320x180 --model gpt-6-astra --reasoning-effort high --thin --own" \
bash scripts/launch-og.sh          # M = .../MFM-grid-merge-mcu/output

# the self-harness chain (og14 from scratch; og15 = og14's life as the only seed; og20 adds --own-reflexes)
ARM=ogNN_mfm GP=91xx PP=91yy STEPS=60000 SESSION_TURNS=0 COMPACT=1 WALL=10h EXTRA_ONLY=1 \
EXTRA_SEEDS="$G/og14_mfm/episode_001/memory" \
WM_EXTRA="--expect --frames --retrieval --frame-size 320x180 --model gpt-6-astra --reasoning-effort high --thin --atoms --own --own-reflexes" \
bash scripts/launch-og.sh          # G = .../MFM-grid/MCU/output

# the three-layer setting (og21; og22 = the same with --model gpt-5.6-sol --reasoning-effort xhigh)
... WM_EXTRA="... --thin --atoms --own --own-reflexes --no-harness-reflexes --skills" bash scripts/launch-og.sh

# visual-only (og17) and human-play (og18), from scratch, 640x360
... NO_SEEDS=1 WM_EXTRA="--expect --frames --retrieval --frame-size 640x360 --model gpt-6-astra --reasoning-effort high --thin --visual-only" ...
... NO_SEEDS=1 WM_EXTRA="--expect --frames --retrieval --frame-size 640x360 --model gpt-6-astra --reasoning-effort high --human-play" ...

# the full task from nothing on gpt-5.6-sol high (of1, 2026-09-08): minimal contract, atoms, own scripts
# and reflexes (the examples copied by the model, none installed), skills, no runner guards, no event sheet
TASK=ender_dragon ARM=of1_mfm GP=91xx PP=91yy STEPS=100000 SESSION_TURNS=0 COMPACT=1 WALL=8h NO_SEEDS=1 \
WM_EXTRA="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --model gpt-5.6-sol --reasoning-effort high --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills" \
bash scripts/launch-og.sh
```

Verify a launch within two minutes: `grep -c Traceback logs/<ARM>_purple.log` is 0, the
purple's command line carries the flags (`ps -o args= -p <pid>`), and
`output/<ARM>/episode_001/memory/` holds `AGENTS.md` (the contract) and, when seeded,
`previous/life_*`. Stop an arm with `scripts/stop_arm.py --go <ARM>` (by pid, never by
pattern). Several arms run at once on this host (five on 2026-09-08); each needs distinct
ports and about one core-heavy Java process.

## Outputs and read-outs

- `output/<ARM>/episode_001/memory/`: `logs.txt` (the workspace log: `Action N | Step M`
  headers, `[PLAN]`, `[ACTION]`, `[STATE]`, `[EVENT]`, `[INV]`, `[NOTE]`), `episodes/`,
  `index.jsonl`, `grid.jsonl`, `references/`, `skills/`, `mine/` (the model's own:
  `notes.md`, `digest.md`, `procedures/`, `reflexes/`), `previous/`.
- `output/<ARM>/episode_001/codex_turns/turn_NNNN.{prompt.txt,events.jsonl}`: every turn's
  prompt and the model's shell commands.
- `output/<ARM>/episode_001/worldmodel_report.json`: `milestones`, `steps`, `turns`,
  `cursor_stats` (deaths, the guard and reflex counters, `own_calls` / `own_failures`,
  `own_reflex_runs` / `own_reflex_fires` / `own_reflex_failures`), `own` (procedures and
  calls, reflexes and fires), the flags.
- `logs/<ARM>_{launch,green,purple,client,wall}.log`, `logs/<ARM>_result.json` (the
  benchmark's score, written when the episode ends on its own; a wall-capped arm has
  none: its score is the milestones in `logs.txt`).
- Read-out scripts in `MFM-grid/tasks/mfm-three-layer.spatial-grid/scripts/`:
  `compare.py <logs.txt>...` (steps, milestones, the bucket-to-lava chain, deaths, go_to
  and governor counts, churn) and `toolcalls.py <codex_turns dir>...` (the model's shell
  commands by kind: grep/read logs, episodes.py, previous/, png, own writes) and
  `vision_use.py <arm>...` (what the model pointed `view_image` at, from the codex
  rollouts under `MCU_CODEX_ROOT`: zooms of the current view vs this life's episode
  frames vs an earlier life's -- the check on whether an arm ever looks BACK).

The half task (`ender_dragon_half`) starts with the first ten milestones' kit and scores
the remaining fourteen plus those it re-earns; a run's headline is milestones/24 (15/24 =
62.5). Steps per hour matter as much as milestones per step: the arms end on the 10 h wall
cap before the 60k steps (fixed library 4-7k steps/h, self-built harness 1.7-3.1k).

## Tests and stages

Unit tests live in `MFM-grid/tests/` and import the MCU checkout named by `MFM_MCU_ROOT`
(default `MFM-grid/MCU`). pytest is not in the venv; it is in `~/.local`:

```bash
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid
MFM_MCU_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu \
PYTHONPATH=$HOME/.local/lib/python3.10/site-packages:<a dir holding iniconfig and pluggy> \
../MFM-grid-merge-mcu/.venv/bin/python -m pytest tests -q -p no:cacheprovider \
  --ignore=tests/test_carry.py --ignore=tests/test_kicad_eval.py      # KiCad tests need gym_codex
```

The contract texts are pinned (`tests/pins/`, `test_pins_chassis.py`): a deliberate
contract change is re-recorded with `MFM_RECORD_PINS=1` and the diff reviewed.

Stage tests run the real runner against the real simulator from a prepared world, no
model (`mcu_worldmodel/stages/rig.py`); each is a few minutes:

```bash
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu
source ./env.sh; export PYTHONPATH=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid:$PYTHONPATH
xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s25_nether_lock      # output under logs/stages/
```

Stages of this branch: `s20_shaft`, `s21_lava_escape`, `s22_own` (own procedures),
`s23_shaft_ahead`, `s24_fall`, `s25_nether_lock` (the lock and the descent guard),
`s26_own_reflex` (an own reflex in the loop), `s27_starters` (the starter reflexes with the
guards off). The older stages (s0-s19) cover the GUI, the world macros, the obsidian and
portal chain, the Nether and the End.

## The arms on record (half task, 10 h cap unless noted)

| Arm | Setting | Result |
| --- | --- | --- |
| og3, og4 | the first spatial-grid harness arms, carry (12 lives) | 41.67, 25.0 |
| og5-og7 | spatial-grid harness, carry (12 + og3/og4) | 54.17, 45.83, 54.17 |
| og8, og9 | carry (12 + og3/og4), the map-aware go_to and escapes | 62.5, 66.67 (the record; og9 entered the Nether twice and died there both times) |
| og10, og11 | full / thin contract, from scratch, before the pool fixes | 15/24 (3 deaths), 14/24 (2 deaths) |
| og12, og13 | full / thin, from scratch, after the pool fixes | 15/24 (the Nether at 30305, died there), 14/24 (the Nether at 18.7k, died there) |
| og14 | thin + atoms + own, from scratch | 15/24 at 26.4k, 0 deaths, 7 own scripts / 177 calls |
| og15 | og14's setting, seeded with og14's life only | running |
| og16 | thin, from scratch, all guards of 2026-09-07 | 15/24 at 43.4k, 2 deaths |
| og17 | thin + visual-only, 640x360 | 15/24 at 20.4k (2k steps/h), 0 deaths |
| og18 | human-play, 640x360 | 13/24 at 17.2k (1.7k steps/h), 0 deaths, 24 own scripts |
| og19 | thin + own + the digest note + the Nether lock, 23 clean lives carried | running (13/24, 2 deaths at 10.2k) |
| og20 | og15 + own reflexes | running |
| og21 | og20 + no harness reflexes + the skill package | running |
| og22 | og21 on gpt-5.6-sol xhigh | running |

The per-arm story -- launch lines, read-outs, the audits behind each guard -- is in
`MFM-grid/tasks/mfm-three-layer.{spatial-grid,self-harness,visual-only,human-play,memory-reuse}/`.

## Memory v2 (2026-09-08)

Evidence: `MFM-grid/tasks/mfm-three-layer.spatial-grid/analysis/SYNTHESIS.md`; plan:
`plan-memory-v2.md`. Everything below is text, tools and one pass -- no new fact is pushed.

- **`[OBSERVED]` cites frames** (`--expect`): each finished entry carries `frame: episodes/ep_x/observation/image.png`
  (the view it started from) and the compare line asks for one visible change. `[RECALL]`'s
  here-before citations carry a bearing and distance ("ep_000037 step 378, 4 blocks NE: ...");
  the milestone line is gone (it repeated [STATE]).
- **`./tools/episodes.py --then-now <id> --q "..."`** writes the remembered frame beside the
  current view (`then_now.png`); `--q` on any query records what the look was for.
- **`mine/working.md`** (own arms): the model's continuation note, shown every turn as
  `[WORKING]` (cap 1500 chars); the contract says what goes in it (own.py MFM_WORKING_NOTE).
- **Skills package additions**: `skills/memory` (working memory, death forensics,
  `scripts/death_sheet.py`), `skills/reflexes` (class 7: known hazards, `scripts/known_hazards.py`),
  `skills/procedures` (where the budget went; keep inherited names).
- **The distiller pass** (`scripts/distill.sh <name> <out> <seed-memory>...` -> `mcu_worldmodel/distill.py`):
  one codex run with no game context over the seeds' records; writes `<out>/memory/mine/{GUIDE.md,
  procedures/, reflexes/, frames.md}` and `<out>/distill_report.json`. Launch the next life with
  `--seed-mine <out>/memory/mine` (copied into its mine/ before start) plus the same seeds under previous/.
- **`--minimal`** (needs `--skills`): prompts.MINIMAL_CONTRACT -- task, loop, tools, memory, one safety
  line, the procedure index; the rules go to `references/` as `--thin` writes them, the own/reflex
  contract to `references/own.md`. ~3.8k words against 5.7k thin / 13.9k full.
- Tests: `tests/test_memory_v2.py` (MFM-grid); pins `chassis_mfm_agents.md` (Look-back sentence) and
  `chassis_mfm_recall_prompt.txt` (no milestone line) re-recorded.
