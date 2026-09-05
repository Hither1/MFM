# Plan: MFM agents (Multimodal Filesystem Memory)

Scope: a new memory arm, the **MFM agent**, for MCU (diamond / dragon) and for the KiCad
GUI benchmark. On KiCad it is PRO-LONG plus the episode store. On MCU, **revised
2026-09-04 (evening)**: it is built on the world-model chassis's *logbook* mode, not on
the original PRO-LONG port -- see "Status: the MCU chassis decision" below. The rule
"built on PRO-LONG instead of on the world-model code" that the rest of this document
still states is therefore overturned for MCU; `mfm/` (backend, agent base, memory) is
unchanged by that decision, only the MCU adapter layer moved.

Design rule, unchanged: **the MCU arm is the current PRO-LONG agent with the smallest
possible delta**, so its measured behaviour is preserved. What changed in this revision is
*how* that is guaranteed. The first draft guaranteed it by never editing a baseline file
and stacking subclasses on top, which meant writing every MFM piece twice (once per repo)
and reaching into the parent's private fields. This revision lifts the code the two repos
already share into one package, in three layers, and guarantees the baseline with pinned
tests (section 7) instead of with untouched files. MFM is then written once.

## Status: the MCU chassis decision (2026-09-04, evening)

**Decision.** The MCU MFM arm is `worldmodel_purple_agent.py --memory mfm`: the logbook
arm (the world-model chassis -- macros, cursor, vision, governor -- with PRO-LONG's
memory protocol, one append-only `logs.txt`) plus the episode store beside the log.
The ladder on one chassis is now direct -> logbook -> **mfm** -> wmlite -> worldmodel,
so MFM's memory effect separates from the chassis. The PRO-LONG-based MFM arm stays
launchable as `--agent plmfm` (the dmw3 wave) for the original PRO-LONG-vs-PRO-LONG+MFM
comparison; it is no longer the ladder rung.

Why. Prompt-tuning PRO-LONG towards longer plans cannot close the gap: its caps are
already 40 entries / repeat 200 / 400 ticks and the model still writes 1-2 tick plans,
because raw keypresses give no in-plan feedback -- two to three times fewer calls at
best, not the twenty times the chassis's macros give (median plan entry ~40 ticks). And
"episode = plan entry" maps onto a macro call naturally: the chassis already writes one
log section per finished entry with position delta, [INV], [EVENT]s and the governor's
[NOTE], which is the outcome record.

What was built (all gated on `memory_mode == "mfm"`; the logbook arm is pinned):

- `mcu_worldmodel/episodes.py`: `EpisodeBridge`, the adapter that drives
  `mfm.memory.store.EpisodeStore` from four chassis hook points (`start`, entry open
  in `next_action`, `observe`, `_log_entry_done`) and implements the store's
  `episode_*` hooks for Minecraft. `MFM_MEMORY_NOTE` lives there; `prompts.py` builds
  the mfm contract from the logbook contract by replacing one paragraph, every other
  segment being the same object as the logbook's.
- `memory.py`: `episodes=True` keeps `episodes/`, `index.jsonl`, `tools/` between
  turns (the sweep otherwise removes them) and writes `tools/zoom.py`.
- `codex_backend.py` (chassis): counts `tools/episodes.py` runs in the rollout scan;
  `session_max_turns` is a constructor argument.
- `worldmodel_purple_agent.py`: `--memory mfm`; explicit `--session-turns 1` and
  `--codex-timeout 480` (no environment defaults); the open episode is closed and the
  report written on the last step.
- `tests/test_pins_chassis.py`: the logbook arm replayed through the selftest's fakes
  (120 ticks, 15 sections, a procedure, governor notes, a hit reflex, a failed
  attempt): `logs.txt`, `AGENTS.md`, every prompt, every action, the workspace listing
  and the report keys, plus the four modes' system-prompt hashes. Recorded before the
  mfm changes; green after.

Fixes from the 2026-09-04 review (all pinned or covered by `tests/`):

- Results-losing: `slurm/arm.sbatch` walltime 24 h -> 2.5 days (a PRO-LONG-cadence arm
  needs 18-29 h; sapphire allows 3 days). `prolong_purple_agent.py` now writes
  `prolong_vision_audit.json` every 200 steps and calls `save_state` (closing the
  store's open episode) on the last step -- nothing ever called it before, so no MCU
  run of this arm had an audit and its last episode never closed. The subscription
  account's usage limit: the shared backend gained the chassis's gate as an MCU policy
  knob (after 5 refusals in a row the calls stop, one probe every 40th) and the MCU
  adapter waits 2/4/8/16/30 s between contentless failed attempts (the chassis's own
  rule); prompts, log and actions unchanged.
- Ablations: the store's `publish` keeps an episode under a window only when the frame
  it opened on is visible (it kept by `last_step`, leaking pre-window frames); under
  stateless the system prompt no longer names the tool the publish removes.
  `tests/test_pins_ablation.py` pins `--log-window 3` and `--stateless`, with and
  without the store.
- Data: state.json `moved` was always 0.0 (the state hook was called twice per
  observation; now once, cached per step, after the flush decision so it carries the
  updated verification state); a flushed entry no longer absorbs the default-action
  ticks of a failed turn (a `refill` sink hook closes it when the turn starts).
- Backend: `audit()` remembers each session's rollout path (was O(N^2) in sessions);
  the empty-output session discard no longer starts the new session with one failure
  already counted; `session_max_turns` / `timeout` are explicit arguments from both
  purple agents.

## Status: what the first KiCad waves showed (2026-09-05)

Measured on the gpt-5.6-sol `_projdir` pair and the GPT-6 low pair (25 tasks each):

- **The model reads the text log every turn and never reads the store.** PRO-LONG made
  1,183 log reads in 1,186 turns on GPT-6, MFM 1,184; `tail -n 12..25 logs.txt` (744)
  and `cat logs.txt` (430) dominate. The episode tool was called 0 times on GPT-6 and 2
  on gpt-5.6; earlier screenshots were re-opened twice in 1,410 shell commands. The two
  GPT-6 arms scored identically on all 25 tasks.
- **Why the store has nothing to add within a task**: KiCad tasks are 9-110 turns in a
  fresh per-task workspace; the screen changes every step (27 repeated screenshot hashes
  in 1,247 episodes, all the initial/first-turn pair), `screen_unchanged` fired twice.
  The index carries nothing the log's last 15 lines do not.
- **`tools/zoom.py` was promised and never written** (both arms; the sandbox even
  provisions a Pillow `python` for it). Every zoom attempt failed, then the model stopped
  looking back. Fixed 2026-09-05: `mfm.memory.log.install_zoom_tool`, called by the KiCad
  agent for both arms; baseline prompt, log and argv pins unchanged.
- **The success rate is bounded by the grader, not memory.** Three exact-set checks
  (library part names, (ref,pin) net sets, net names including KiCad's auto-generated
  `Net-(D1-K)`); no design-from-scratch task has ever been solved by any arm; only
  modify-existing tasks are solvable (5-7 of 10). Task 34877be3 asks for "LN271" while
  its reference uses `LD271`; a6414tw4's reference is an empty netlist. The
  `--kicad-project-hint` flag (EVAL_EXTRA) is what makes scratch tasks gradable at all;
  the GPT-6 wave ran without it (15 tasks never reached the grader).
- **Where memory could matter on KiCad: across tasks.** Median 7 turns per task
  (122 of 1,222) are the same preamble -- dismiss the first-run and update dialogs,
  create the project, find the save directory -- and the same GUI lessons recur (Escape
  cancels a wire). Section 5's `carry` layer (a memory that persists across a run's
  tasks) is the only MFM mechanism with a plausible effect here; it changes the
  benchmark's task-independence assumption and needs a decision.

**Decision (2026-09-05): memory may persist across a run's tasks.** Built as the carry
rung (`mfm/memory/carry.py`, `CarrySink`): `previous/<task>/` holds every finished
task's record (logs.txt, frames, episodes, index; hard links), `notes/` is the model's
own directory copied in at task start and out at task end, `<out>/carry/manifest.json`
is the task order. Two new KiCad arms, `prolong-carry` (the control: carry-over without
structure) and `mfm-carry` (plus the merged `previous/index.jsonl`, `--previous` and
`--same-screen` in the query tool, and a `[SEEN BEFORE]` line pushed into the turn prompt
when the current screen matches an earlier episode, since the model does not pull). Both
require `--concurrency 1`; task order is part of the arm and is reported. The per-task
arms are unchanged (pins green). The ladder on KiCad is therefore
prolong -> prolong-carry -> mfm-carry, with prolong vs mfm as the within-task control
pair that is expected to tie.

**Re-scorable runs and a relaxed score (2026-09-05).** `run_eval` now saves what the
grader reads (`<task>/kicad_project/*.kicad_sch|.kicad_pro|.net` and the netlist
`kicad-cli` exports, `<task>/graded.net`) after the final step, so a nine-hour run can
be re-scored offline under any grader. `gym_codex/kicad_rescore.py` reports a relaxed
score beside the official one and never instead of it: symbol-style suffixes ignored
(`R_US` = `R`), nets compared up to renumbering of interchangeable components, KiCad's
auto-generated net names dropped. Every reference scores 1.0 against itself and against
a style-variant copy of itself, where the official grader gives that copy 0.67 on 16 of
the 25 tasks. `gym_codex/patch_kicad_tasks.py` re-applies the LN271 -> LD271 fix to the
dataset cache (34877be3); a6414tw4 (empty reference netlist) is skipped with
`--exclude-tasks`. Wave launched 2026-09-05 on GPT-6 low, codex 0.153, project-dir hint,
24 tasks, one node per arm: `kicad_{prolong,mfm,plcarry,mfmcarry}_gpt6hint`
(jobs 44622955, 44622961, 44622965, 44622968). Why ~9 h per arm: of the measured 8.9 h,
~8.5 h is codex latency (1,180 calls, median 19 s) and 1.6 h environment steps; the plan
queue does not shorten it (94% of turns are single-action batches) and only the
per-task arms can be sharded with `--tasks`, so the carry arms stay sequential.

## Status (2026-09-04)

Steps 1-4 of section 6 are implemented and green; section 5 (optional layers) and the
A/B waves are not started. What exists:

- `mfm/` at the MFM root (`pip install -e .` into the `vla` env; MCU's own venv needs
  the same once it exists): `backend/codex_turn.py`, `backend/errors.py`,
  `agent/base.py`, `memory/{log,sink,store,retrieve}.py`, `memory/tools/episodes.py`.
- Both repos' `codex_backend.py`, KiCad's `log.py` and `backend_errors.py` are shims
  onto `mfm`; MCU's `prolong_mc/log.py` keeps the Minecraft renderers and a
  compatibility `EpisodeLog`. `mc_agent/prolong_agent.py` and the new
  `gym_codex/prolong_agent.py` are the two agents on `MemoryAgent`.
- `--agent mfm` in `scripts/run-arm.sh` (via `prolong_purple_agent.py --mfm`) and in
  `gym_codex/run_eval.py` (via `make_agent`).
- `tests/` holds the section-7 pins, recorded from the pre-refactor code and green on
  the refactored code: `pytest tests` compares, `MFM_RECORD_PINS=1 pytest tests`
  re-records. Plus `test_store.py`: the same traces with the store on.

Deviations from the text below, each deliberate:

- The "adapter" is the benchmark's agent subclass overriding `MemoryAgent`'s hook
  methods, not a separate object. Same separation, one less indirection.
- `codex_sandbox.sh` and `sandbox_proxy.py` stay in each repo: the wrapper bind-mounts
  the proxy into a namespace with no site-packages, so the proxy must be a
  self-contained file beside the script that mounts it. The two wrappers also differ
  (KiCad's is newer); MCU's measured runs do not use one.
- `prepare_codex_home` / `resolve_codex_bin` stay inside `codex_turn.py` (no `home.py`).
- No `render_logs_txt`. Its job -- "the store changes nothing the model sees" -- is done
  more directly by `test_store.py`, which replays the pinned traces with the store on
  and asserts `logs.txt`, every prompt and every returned action equal the baseline pins.
- `scan_rollout` keeps its three-key result (a KiCad selftest pins it); the MCU
  tool-error counters and `episodes_tool_calls` come from `scan_rollout_full`.
- The store's `publish` under a window links the episodes whose `last_step` is within
  the last N steps (MCU) / turns (KiCad); the unablated arms never reach it.
- KiCad's `_MemoryGuiAgent` is still in `memory_agents.py` for the world-model arm until
  the cleanup commit; `MemoryAgent` was written from it rather than moving it.

Pre-existing defects found on the way, not fixed (not on the measured paths):
`prolong_mc/prompts.py:340` raises `TypeError` for the no-log control's system prompt
(`log_window == -1`); `prolong_search/selftest.py` crashes at
`test_task_framing_matches_baseline` on a file removed in commit fb46ac9, so the four
tests after it must be run by hand (they pass).

Not done: `tools/zoom.py` output into the episode's `crops/`; section 5. The retrieval
block exists since 2026-09-05 (below), off by default. The MCU purple agent closes the
store on the next `init`, so an episode killed by the launcher loses only its open entry.

**Wave 1 is running (2026-09-04).** KiCad: `--agent mfm` as job 44469925, from a git
worktree of the run checkout so the three arms already mid-run were not disturbed, with
the already-running `--agent prolong` (44396608) as its baseline -- legitimate because
the pins show the rendered system and turn prompts are byte-identical across the
refactor, checked again by hashing both trees' `build_system_prompt`/`build_turn_prompt`.
Its first task scored 1.0 in 11 steps and wrote 12 episodes. MCU: `dmw3_prolong` and
`dmw3_mfm` on `mine_diamond_from_scratch` at 12000 steps, one job each, forced onto
different nodes.

Two things that cost three launches and are worth knowing before the next wave. The
green server's readiness ceiling was 300 s and its import time off NFS is
node-dependent by more than an order of magnitude -- 10 s on a warm node against 210 s
on a cold one in the same wave, and past 300 s twice -- so arms were being killed for a
cold page cache; the ceiling is now 900 s with a heartbeat. And `run-arm.sh` must not be
edited while a job is executing it, since bash reads a script by byte offset as it runs,
which is why the wave was relaunched rather than patched in place.

The MFM and PRO-LONG task orders differ within a KiCad run, so the arms must be compared
on the task ids they both finished, not on whatever each got through.

**lad1/lad2 (2026-09-05) and the retrieval block.** Diamond, 12,000 steps, from the
`MCU-ladder` worktree: logbook 70 / 80, mfm 60 / 80 -- both lad2 arms 8/10, missing
`iron_pickaxe` and `diamond`, no MFM effect. The model ran `tools/episodes.py` in 28% of
its turns but almost only as `--last N`, which listed less than `tail logs.txt` (the
index row has no note). Where the steps went, in every run: the "one plank short"
wood/table/open-GUI loop (2,650 steps in lad2 mfm; the same loop after the logbook arm's
death), a descent to Y=12 with no furnace and no torches (5,030 steps of `view was DARK
throughout`), and a death whose drop was never recovered. Each is a repetition the model
never saw as one thing, because it read the last few sections each turn.

So the flag the plan reserved is now built: `mfm.memory.retrieve.recall_block` computes,
from the rows the store already holds, (1) streaks -- actions that changed nothing
(no `milestone`/`inventory_changed` tag; for movers, `stuck`) in their last >=3 calls,
with the note the last one ended on and the step the same action last worked, dropped
once the run is older than the last 30 rows; (2) the harness note that ended the last
>=3 noted entries (one sentence, digits ignored) -- the dark descent is not a no-change
loop, every entry banked cobblestone, but eight in a row ended on "The view was DARK
throughout"; (3) what happened within 6 blocks of here, older than the six rows the
model can see; (4) the entry that scored each milestone. On lad2 mfm's own index at
step 2266 it reads "`craft` changed nothing in its last 23 calls ... `harvest_tree` ...
18 calls ... It last changed something at step 563", and at 6104 "The same harness note
ended the last 7 entries that carried one (since step 4164; strip_mine x3, dig_down x3,
mine_forward x1)"; a chain is present in 25 of that run's 337 entries; 0.5-1.6 KB.
`WorldModelAgent(retrieval=True)` inserts it into the mfm turn prompt between the
present and the log pointer and adds one paragraph (`MFM_RETRIEVAL_NOTE`) to the
contract; `worldmodel_purple_agent.py --retrieval`, `run-arm.sh --agent mfm --wm-extra
--retrieval`. The logbook arm is untouched (its pins are green); the flag-off mfm arm
differs from lad2's only in the CLI listing the first outcome note and in `_MOVERS`
naming the real procedures (`go_to`, not `goto`, so movers now get the `stuck` tag).
Pinned: `tests/test_pins_chassis.py::test_chassis_mfm_retrieval`, `tests/test_retrieve.py`.
The lad3 pair is `mfm` against `mfm --retrieval`; the ladder worktree needs the MCU
commits and `PYTHONPATH` at the MFM root, since the run venv's `mfm` is a frozen copy.

---

## 0. What exists, and what is duplicated

Three agents matter. Sizes are real line counts.

| | MCU PRO-LONG (the base) | MCU world model (retired) | KiCad memory arms |
|---|---|---|---|
| code | `mc_agent/prolong_agent.py` (504) + `prolong_mc/{log,prompts,actions,goals,codex_backend}.py` (~2260) | `mcu_worldmodel/` (agent.py 3845, memory 558, hypotheses 294, discipline 259, prompts 1186, plus ~10k of macros/vision) | `gym_codex/memory_agents.py` (731): `ProlongGuiAgent` and `WorldModelGuiAgent` on `prolong_search/log.py` + `worldmodel_search/` |
| memory | one append-only `logs.txt`, one section **per env tick**, `frames/step_NNNN.png` per tick, persistent workspace | `logs.txt` per plan entry, `episodes/`, `events.jsonl`, `hypotheses/` DAG, `world_model/*.md`, induction | same two shapes, one screenshot per turn |
| model calls | one Codex turn when the plan queue runs dry (~2,200 calls / 12k steps) | one per act turn (~130 / 12k steps) plus induction | one per turn |
| what the model sees | `AGENTS.md` contract + a near-empty turn prompt pointing at `logs.txt` + the current frame attached | compiled docs + graph view + state block | as the respective MCU arm |

The same machinery exists in both repos, copied and then patched separately:

| piece | MCU | KiCad | third copy |
|---|---|---|---|
| Codex backend (`CodexTurn`) | `prolong_mc/codex_backend.py`, 894 lines | `prolong_search/codex_backend.py`, 1117 lines | `mcu_worldmodel/codex_backend.py`, 1017 lines |
| diff between the first two | 1101 lines raw, 706 lines of code once comments and blanks are dropped | | |
| `sandbox_proxy.py` | byte-identical | byte-identical | |
| `codex_sandbox.sh` | present | present | |
| log (`EpisodeLog`) | `prolong_mc/log.py`, Minecraft-specific writers (`write_action` renders `state_block`) | `prolong_search/log.py`, generic (`write_section(title, lines)`, attachment markers configurable) | |
| turn protocol | inline in `ProlongAgent.get_action` + `_refill` | `_MemoryGuiAgent`: `_open_turn / _before_act / _act / _close_turn / _run_with_retries / _no_op / audit` | |
| retry policy | fixed `analyzer_retries` loop with `RETRY_NUDGE` | the same loop plus `backend_errors`: refusals and capacity errors extend the budget | |

KiCad's copy is the superset on every row: its `CodexTurn` adds `LocalServerGate`
(a preemptible local server treated as a pause), `prepare_codex_home` / `resolve_codex_bin`
(per-episode home, sandbox wrapper detection), `artifact_name` / `message_name`,
salvaged timeouts, poisoned-session resets, a per-call `stats` list and an `audit()`.
MCU's copy has three things KiCad's lacks: `split_briefing` / `extract_plan` (a prompt
convention, not a backend concern), `vision_audit` (the same rollout scan under another
name), and the `_sessions_root` / rollout mtime caches inside it. KiCad's `EpisodeLog` is
already the generic one; MCU's differs only in that its section renderer is inlined.

Measured problems the episodes are meant to fix (from
`CUA-KiCad/experiments/WORLDMODEL_MECHANISM_AUDIT.md`, the MCU README and code comments):
frames are addressable but almost never revisited (0-6 look-backs per MCU run, 10% of
KiCad act turns) because the frame and the state that explains it live in different
files; the one retrieval mechanism that measured well in the earlier search-benchmark arm
(paste the earlier same-image section) was never ported to either embodied arm; the belief
DAG view froze and 84% of turns read `graph.json` by hand.

Reference point: `stanford-iris-lab/meta-harness` (`experimental/harbor_meta_harness`)
defines a harness as "the code around a fixed base model that decides what to store,
retrieve, and show", and splits it into environment (`environment.exec`), model channel
(`acompletion`) and harness (`BaseAgent.run`). The three layers below are the same split.
Two of its properties are worth keeping on purpose: the harness is one unit behind a
small validated interface, so it can be swapped or searched over; and generated code is
staged into a temporary directory and never imported by the controller, which is the same
line our `record_dir` / visible-workspace split draws.

---

## 1. The unit, and the layout

Unchanged from the first draft. Decided.

```
<workspace>/                          Codex cwd, unchanged
  AGENTS.md  logs.txt  actions.json  last_message.txt      exactly as PRO-LONG writes them
  frames/step_NNNN.png                 unchanged: one per tick, what [FRAME] lines name
  episodes/
    ep_000042/                         one per PLAN ENTRY ({"action": {...}, "repeat": N})
      observation/
        image.png                      hard link to frames/step_<first tick>.png
        crops/                         zoom outputs and (later) harness crops; append-only
      state/
        state.json                     state at the entry's first tick, structured
        ticks.jsonl                    one line per tick: the same fields state_block prints
      action.json                      the entry, its repeat, its position in the plan,
                                       the turn that produced it, briefing + [PLAN] text
                                       (on the plan's first entry only)
      outcome.json                     written when the entry's last tick has been observed
  index.jsonl                          one line per episode: id, steps, tags, summary, paths
  tools/zoom.py                        as today; default output moves into the episode's crops/
  tools/episodes.py                    query the index (see 2.2)
```

- **No `artifacts/`, no `links.json`.** Agent-made files go in the workspace root or
  `notes/`; links are the sequential ids, the `turn` field in `action.json`, and
  `ep_NNNNNN` citations in any text.
- **`logs.txt` stays the primary model-facing record.** Written exactly as today;
  `episodes/` is written beside it from the same call sites. `render_logs_txt` regenerates
  the log from the episodes and the bytes must match (section 7).
- **Episode = plan entry, not tick** (MCU). Per-tick facts go into `state/ticks.jsonl`.
  The KiCad episode is one turn: one screenshot, one batch, one feedback.
- **Ownership.** Everything under `episodes/*/` except `observation/crops/`, and
  `index.jsonl`, is harness-written and immutable once closed.

Schemas (MCU):

```jsonc
// state/state.json and each line of state/ticks.jsonl
{"step": 4812, "pos": {"x":..,"y":..,"z":..,"pitch":..,"yaw":..}, "moved": 0.31,
 "inventory": {"spruce_log": 3, ...}, "hotbar": {"1": "spruce_log x3", ...},
 "gui_open": false, "mainhand": "wooden_pickaxe",
 "vitals": {"health": 20, "food": 18, "light": 7, "sky": true},
 "mobs": {"zombie": 1},                 // null over A2A: the green agent withholds `mobs`
 "goals": {"done": ["mine_log"], "next": "crafting_table"}, "verified": "no"}
// action.json
{"turn": 37, "plan_index": 2, "plan_total": 5, "entry": {"action": {"forward":1,"sprint":1}, "repeat": 20},
 "ticks": 20, "first_step": 4812, "briefing": "...", "plan": "..."}   // last two on plan_index 1 only
// outcome.json
{"last_step": 4831, "moved": 6.2, "descended": 0.0, "inventory_delta": {"spruce_log": 1},
 "milestone_transition": null, "verified_after": "no", "notes": ["ESC was rejected ..."],
 "flushed": false, "tags": ["inventory_changed"]}
```

Tags are derived from `outcome.json` by the adapter: `milestone`, `inventory_changed`,
`stuck`, `gui`, `damage`, `note`, `flushed`; KiCad adds `feedback`, `screen_unchanged`,
`terminate`.

---

## 2. The three layers

One package, `mfm/`, at the MFM repo root. Stdlib only (KiCad's env has no pydantic; the
backend is already subprocess + json + pathlib). Installed editable into whichever
environment runs each benchmark (the `vla` env, Python 3.11, for KiCad; MCU's own venv,
which this checkout does not contain). The submodules keep only what is theirs.

```
mfm/                       (as built)
  backend/
    codex_turn.py        CodexTurn (+ LocalServerGate, prepare_codex_home, resolve_codex_bin):
                         argv, run, session policy, per-call stats, audit; MCU_POLICY
    errors.py            is_filter_refusal, is_transient_infra, reason keys
  agent/
    base.py              MemoryAgent: Observation, Plan, the queue, observe/act/refill,
                         the retry policies, the sink dispatch, the hook methods
  memory/
    log.py               EpisodeLog + prepare_workspace: sections, attachments, plan and
                         briefing blocks, notes, window/stateless, publish
    sink.py              MemorySink: the hook set a second memory implements
    store.py             EpisodeStore(MemorySink): the section-1 layout, index.jsonl
    retrieve.py          re-exports the query functions of tools/episodes.py
    tools/episodes.py    the CLI written into every workspace (stdlib only)
tests/                   the pins (section 7) and the store tests
```

### 2.1 Backend: `mfm.backend`

`CodexTurn` is KiCad's, moved. It is the superset; MCU's three extras are handled thus:

- `split_briefing` / `extract_plan` move to the MCU adapter. They parse the `[PLAN]`
  marker the MCU prompt asks for; the backend returns the message and does not read it.
- `vision_audit` becomes `audit()`. The rollout scan (`scan_rollout`, `find_rollout`, the
  mtime cache, the fixed `_sessions_root`) is the same in both; the merged `audit()`
  returns the union of both dicts. `vision_audit` stays as an alias for the MCU
  `save_state` writer.
- The MCU `-o last_message.txt` is the default `message_name`; MCU passes nothing new.

What the backend owns and nothing else does: the argv (`_args`), the session policy
(overflow, timeout, empty, age, poisoned-session resets, every one a counter), the
sandbox (`sandbox_mode="workspace-write"` set through `-c` so it survives `resume`, the
egress allowlist, the per-episode `CODEX_HOME`), the server gate, the transcript and
rollout bookkeeping, and `write_system_prompt` (write-once `AGENTS.md`). Its interface to
the layer above is three calls: `write_system_prompt(text)`, `run(prompt, images) ->
result`, `audit() -> dict`. The result dict is KiCad's (`ok`, `error`, `artifact`,
`message`, `overflow`, `stats`), which is MCU's plus `artifact`; MCU today reads
`actions_json` from it, and the adapter reads `artifact` instead.

`mcu_worldmodel/codex_backend.py` is not merged. It dies with the world-model arm.

### 2.2 Agent base and memory: `mfm.agent`, `mfm.memory`

**`MemoryAgent`** is `_MemoryGuiAgent` lifted, with MCU's plan queue added as a
component. It owns the workspace pair (`prepare_workspace`, KiCad's, which is MCU's
crashed-attempt logic plus `resume`), one `CodexTurn`, one `PlanQueue`, an ordered list
of memory sinks, an `Adapter`, and the counters every arm reports (`turns`, `act_turns`,
`parse_failures`, `no_op_turns`, `plan_flushes`, `files_removed`, plus the backend audit).

The turn protocol, one method, benchmark-neutral:

```
step(obs) -> entry
    if first: sinks.initial(obs); codex.write_system_prompt(adapter.system_prompt(...))
    section = adapter.section(prev_entry, obs, prev_obs)     # title + lines, rendered by the adapter
    sinks.open(section, obs)                                  # log writes it; store opens/ticks an episode
    reason = queue.flush_reason(prev_obs, obs, prev_entry)    # adapter-supplied policy
    if reason: queue.clear(); sinks.note(reason); plan_flushes += 1
    if queue.empty: refill(obs)
    entry = queue.pop()                                       # None when refill failed: adapter.default_entry()
    sinks.act(entry, index, total, tick)                      # log appends the action line; store writes action.json
    return entry

refill(obs)
    published = sinks.publish(visible, window, stateless, current=obs.attachment)
    prompt = adapter.turn_prompt(ctx)                         # ctx: first?, turns, step, window, state text
    for attempt in adapter.retry_policy:                      # MCU: fixed loop; KiCad: budget extension
        result = codex.run(prompt or prompt + nudge, images=[obs.attachment])
        plan = adapter.parse_plan(result)                     # None -> retry
        reason = adapter.accept_plan(plan, attempt)           # MCU goals review; default None
        if reason: nudge = reason; continue
        sinks.plan(turn, plan.briefing, plan.text)
        queue.extend(plan.entries)                            # each entry carries its own tick count
        return True
    sinks.note(no-op reason); return False
```

The two drivers stay outside this: MCU's `get_action(frame_buffer, ..., info) -> (think,
wire, "")` and KiCad's `predict(instruction, png, step_idx, max_steps) -> (message, calls,
done)` are ten-line shims in the benchmark subclass that build `obs`, call `step`, and
unpack the entry. So are `load_system_prompt`, `get_default_action`, `on_esc_rejected`,
`save_state` (MCU) and `reset`, `add_feedback`, `finish`, `audit` (KiCad).

Two things about parity with the current MCU loop. The retry policy is a `RetryPolicy`
the adapter supplies: MCU's is today's fixed loop (`analyzer_retries` attempts, the same
`RETRY_NUDGE` after a failure, no budget extension, a default action at the end); KiCad's
is today's `_run_with_retries` (refusals and capacity errors extend the budget, a
transient infra error at the end is raised to the driver). Neither benchmark's loop
changes. Decided: MCU does not adopt KiCad's extension. The goals review
(`prolong_mc/goals.py`) is off in the measured arm and stays an adapter hook
(`accept_plan`), constructed only when `goal_budget_steps` is set.

**Memory sinks.** A sink is anything with `initial / open / plan / act / note / close /
publish`. The base calls them in order at the points above. Two sinks exist:

- `EpisodeLog` (`mfm/memory/log.py`): KiCad's `EpisodeLog` with the two MCU features
  folded in. `set_plan(plan, briefing=None, persistent=False)`: MCU sets a one-shot
  briefing and a persistent plan that repeats in every section until replaced; KiCad sets
  a one-shot plan. `publish(..., current=...)` takes MCU's `window == -1` no-log control.
  Section rendering is entirely the adapter's `lines`; the log knows titles, `[PLAN]`,
  `[NOTE]`, attachments, the window and stateless rules. This is what makes MCU's
  `Action N | Step k | Plan Step i/T | Verified: x` sections and KiCad's `Turn N | Step
  k/N` sections the same writer.
- `EpisodeStore` (`mfm/memory/store.py`): the section-1 layout. `open` on a new plan
  entry (hard-links the frame, writes `state.json`), `tick` on every observation inside
  the entry (`ticks.jsonl`), `act` writes `action.json`, `close` writes `outcome.json` and
  the index line when the next entry opens or the episode ends; atomic `.tmp` + `replace`.
  `publish` applies the same window rule as the log (only episodes whose first step is in
  the window are linked into the visible tree; none under stateless). `mfm/memory/index.py`
  holds the index and `render_logs_txt(store, adapter)`; `retrieve.py` and
  `tools/episodes.py` are as in the first draft (`--last`, `--steps`, `--near`, `--tag`,
  `--grep`, `--sheet`), one implementation serving the agent's CLI and, behind a flag,
  a retrieval block in the turn prompt.

An arm is therefore `MemoryAgent(adapter, sinks=[log])` for PRO-LONG and
`MemoryAgent(adapter, sinks=[log, store])` plus one appended prompt paragraph for MFM.
No `MFMLog`, no `MFMAgent`, and nothing reaches into private fields: the store receives
the entry, tick and outcome at the same call sites the log does.

**The MFM prompt paragraph** (`MFM_MEMORY_NOTE`, one per adapter for the wording, the
content identical) is appended to the adapter's system prompt when the store sink is on:

> `episodes/` holds the same history as `logs.txt`, one directory per plan entry:
> `state/state.json` and `state/ticks.jsonl` (structured `[STATE]`/`[INV]`/... fields),
> `action.json`, `outcome.json` (what the entry changed), `observation/image.png`.
> `./tools/episodes.py --last 5 | --steps A B | --near X Z | --tag stuck | --grep text`
> lists matching episodes one per line with their paths; `--sheet out.png` tiles their
> frames. Use it instead of parsing the log by hand when a question is "what happened
> when I was here / did this before".

The turn prompt is unchanged. The retrieval block in the turn prompt is a flag, default
off, because it changes what the turn carries and is an arm variant to measure.

### 2.3 Benchmark adapters

What differs between the benchmarks is legitimately different, and is expressed as the
hook methods each benchmark's agent subclass overrides (`mc_agent/prolong_agent.py:
ProlongAgent(MemoryAgent)`, `gym_codex/prolong_agent.py: ProlongGuiAgent(MemoryAgent)`).
The hooks, as implemented (`observe` is the driver shim building the `Observation`):

| method | MCU (`mc_agent/prolong_agent.py`) | KiCad (`gym_codex/prolong_agent.py`) |
|---|---|---|
| `observe(raw) -> Obs` | frame from `frame_buffer[-1]`, `state` dict from `info` (the section-1 schema), attachment `frames/step_NNNN.png` | screenshot bytes, `state` = {step, max_steps, png_sha256, feedback}, attachment `frames/step_NNNN.png` |
| `system_prompt(task, caps)` | `prolong_mc/prompts.build_system_prompt` | `prompts_prolong.build_system_prompt` |
| `turn_prompt(ctx)` | `prolong_mc/prompts.build_turn_prompt` (+ state text under the no-log control) | `prompts_prolong.build_turn_prompt` |
| `section(prev_entry, obs, prev_obs)` | `Action N \| Step k \| ...` header, `Tool Call:`, `state_block`, `[FRAME]`, milestone line: the current `write_action` body | `Turn N \| Step k/N`, `[FEEDBACK]`, `[SCREEN]`; `[ACTIONS]` appended at `act` |
| `parse_plan(result) -> Plan` | `prolong_mc/actions.parse_actions` on `result["artifact"]`; `split_briefing` on the message; entries carry `repeat` | `parse_batch` per batch of a `{"plan": [...]}` or a bare `{"actions": [...]}` (section 4); each batch is one entry with one tick |
| `flush_reason(prev_obs, obs, entry)` | verification state changed while the queue is non-empty | env feedback arrived; screen hash unchanged after a click/key/type batch; a queued `terminate` not decided on this screen |
| `outcome(first, last, notes) -> (dict, tags)` | moved, descended, inventory delta, milestone transition, verified, tags per section 1 | feedback, next screen hash, screen_changed, terminate, reward on finish |

Plus `on_no_plan(result)` (MCU: log an error, the driver takes its default action;
KiCad: the `_no_op` batch with feedback), `accept_plan(plan, attempt, budget)` (MCU goals
review; KiCad none), `adopt_plan` / `after_pop` (where each arm writes its [PLAN] and
[ACTIONS]), and the store's questions `episode_state`, `episode_action`,
`episode_action_kind`, `episode_outcome`, `episode_index_fields`.

`state_block`, `milestone_checklist`, `describe_entry`, `parse_actions`, `ActionPlan`
stay in `prolong_mc/`; `parse_batch`, `ParsedBatch`, the action reference strings stay
in `gym_codex/actions.py`. The adapters call them; they do not move.

---

## 3. What every existing file becomes

| today | after |
|---|---|
| `MCU/prolong_mc/codex_backend.py` | a re-export shim: `from mfm.backend.codex_turn import *`, so `prolong_purple_agent.py` and the selftests keep importing; deleted once nothing imports it |
| `CUA-KiCad/prolong_search/codex_backend.py` | same shim |
| `MCU/mcu_worldmodel/codex_backend.py` | deleted with `mcu_worldmodel/` |
| `MCU/prolong_mc/sandbox_proxy.py`, `CUA-KiCad/prolong_search/sandbox_proxy.py`, both `codex_sandbox.sh` | stay where they are (see Status: the wrapper mounts the proxy into a namespace without site-packages) |
| `CUA-KiCad/gym_codex/backend_errors.py` | `mfm/backend/errors.py` |
| `CUA-KiCad/prolong_search/codex_client.py` (the direct-arm client) | stays; imports `LocalServerGate` and the helpers from `mfm.backend` |
| `MCU/prolong_mc/log.py` | `state_block` and friends stay, plus the two renderers `initial_section` / `action_section`, `make_log`, and a compatibility `EpisodeLog` with the old signatures; the writer is `mfm/memory/log.py` |
| `CUA-KiCad/prolong_search/log.py` | a module alias of `mfm/memory/log.py` (`EpisodeLog`, `prepare_workspace`, `SEPARATOR`) |
| `MCU/mc_agent/prolong_agent.py` | `ProlongAgent(MemoryAgent)`: the MCU driver shims and the `mcu_adapter`; `_refill`, the queue and the section writing are gone from it |
| `CUA-KiCad/gym_codex/memory_agents.py` | `ProlongGuiAgent(MemoryAgent)` and the shared constants moved to `gym_codex/prolong_agent.py`; `_MemoryGuiAgent`, `WorldModelGuiAgent`, `CampaignWorldModel` stay for `--agent worldmodel` until the cleanup commit (section 8) |
| `MCU/prolong_mc/prompts.py`, `CUA-KiCad/gym_codex/prompts_prolong.py` | unchanged; the adapters call them; the MFM paragraph lives beside each (`mfm_prompts.py`) so the baseline prompt hash does not move |
| `MCU/prolong_mc/goals.py`, `actions.py`; `CUA-KiCad/gym_codex/actions.py` | unchanged |
| `MCU/prolong_purple_agent.py` | `--mfm` flag: `ProlongAgent(episodes=True)`; closes the previous episode's store on the next `init` |
| `MCU/scripts/run-arm.sh` | `--agent mfm` case added (prolong + `--mfm`); `worldmodel` / `wmlite` cases stay until the cleanup commit |
| `CUA-KiCad/gym_codex/run_eval.py` | `--agent mfm` through `make_agent` (`ProlongGuiAgent(episodes=True, plan_queue=True)`); `--wm-*` stays until the cleanup commit |
| `MCU/mcu_worldmodel/`, `CUA-KiCad/worldmodel_search/`, `prompts_worldmodel.py` | frozen, not launched, deleted in a cleanup commit after the first MFM wave (section 8) |

The unmodified baseline arms (`--agent prolong` in both repos) run on the moved code.
That is the point of section 7.

---

## 4. The KiCad plan queue

Both existing KiCad arms call the model once per environment step, each call returning a
batch of up to `MAX_BATCH` (5) GUI actions. The KiCad MFM agent adopts MC's protocol: a
multi-batch plan drained one batch per `predict`, the model called only when the queue is
empty or a flush fires. This is a `PlanQueue` policy chosen by the adapter, not KiCad-only
code, and it is the one deliberate deviation from the KiCad PRO-LONG baseline: the A/B in
section 6 therefore measures "episodes + queue" against PRO-LONG.

- **Plan contract.** `actions.json` becomes `{"plan": [batch, ...]}`, each `batch` today's
  `{"actions": [...]}` object, so `parse_batch` is reused per batch. A bare
  `{"actions": [...]}` is a one-batch plan. Cap `plan_cap` batches (default 5), mirroring
  MC's `action_cap`.
- **Drain.** Each `predict` pops one batch, logs the screenshot and the batch as its own
  section and episode, returns it. `Plan Step i/T` goes in the section header.
- **Flush** (the adapter's `flush_reason`): env feedback for the last batch; screenshot
  hash unchanged after a batch that contained a click, key or type action; a popped
  `terminate` that is not the plan's last batch. Counted as `plan_flushes`.
- **Verification hold.** `terminate(success)` executes only when decided on the current
  screen; a queued terminate from an earlier call triggers a refill first.
- **Prompt.** The KiCad `MFM_MEMORY_NOTE` gains the plan contract and the flush rules.

Cost and benefit: fewer model calls per episode, bounded below by the flush count, against
the risk that an open-loop plan runs 1-4 batches past an unexpected dialog before the hash
flush catches it. The GUI has no per-step ground truth beyond the screenshot, which is why
the flush rules lean on the hash.

KiCad notes: `--save-screens` and the agent-side `frames/` store the same PNG twice and
the episode links the agent-side one; the live run tree is in the sibling worktree
`mllm-search/runs/cua_bench_codex/`; `scripts/stage_hf_release.py` addresses frames by
sha256, which `png_sha256` in `state.json` matches.

---

## 5. Optional layers (off by default, second phase)

The world-model arm's mechanisms, re-based on episodes, each a flag on the one agent so
the comparison "PRO-LONG + episodes" vs "+ compiled documents" vs "+ beliefs" is three
flags rather than three agents. Each is a further memory sink or a `refill` hook:

- `mfm/memory/compile.py`: periodic rewrite of a configurable document set (default one
  `world_model/world.md`, the `wmlite` shape) from the retrieval block over the window
  since the last pass; the silent-pass tripwire (`doc_stamps`, mtime+size for NFS).
- `mfm/memory/beliefs.py`: a flat `beliefs.jsonl`, each belief citing episode ids, with
  the three rules that had a measured failure behind them (citations must exist,
  independence by distinct observation hash, confidence ceiling by independent count,
  ledger-backed verifier for MCU goals). No DAG, no per-node `.md` projection.
- `mfm/memory/carry.py`: `seed_memory_dir` / `CampaignWorldModel` generalised: copy
  documents, beliefs, notes and only the cited episodes (re-rooted under
  `episodes/carried/`) so citations still dereference to pixels; a one-off `graph.json ->
  beliefs.jsonl` converter for the lineage memories under `data/MCUData/relay-era/lineage/`.

What was `--agent worldmodel` is `--agent mfm` with these on; `--agent wmlite` is
`--agent mfm` with only the one-document `compile` layer on.

---

## 6. Order of work

In this order, each step ending with the section-7 pins green. The backend merge is the
one step with judgement in it: 706 code lines of diff, most of them dated fixes with an
incident behind them, each kept (KiCad's copy is the superset) unless it changes MCU's
argv or session policy, in which case it is gated on the adapter.

1. **Pins first.** Write the section-7 tests against the *current* code and
   record their expected values: argv snapshots, prompt hashes, log-byte traces. No
   behaviour change.
2. **Backend.** Create `mfm/` with `pyproject.toml`; move KiCad's
   `codex_backend.py`, `LocalServerGate`, `backend_errors`, `sandbox_proxy.py`,
   `codex_sandbox.sh` in; fold MCU's `vision_audit` into `audit()`; leave shims. Both
   repos' selftests and the argv pins run against the shim imports.
3. **Agent base and log.** Lift `_MemoryGuiAgent` and `prepare_workspace` into
   `mfm/agent/base.py`, `EpisodeLog` into `mfm/memory/log.py` with the two MCU features;
   write `mcu_adapter.py` and `kicad_adapter.py`; reduce `ProlongAgent` and
   `ProlongGuiAgent` to shims plus adapter. Log-byte pins must pass here, on both
   benchmarks, before step 4.
4. **Episodes.** `EpisodeStore`, index, `render_logs_txt`, retrieve, the two
   tools, the prompt paragraph, `--agent mfm` in `run-arm.sh` and `run_eval.py`, the audit
   fields (`episodes: {n, tags, episodes_tool_calls}`), the KiCad queue policy. Submit the
   MCU stage run and one short KiCad task for the render check and move on.
5. **One A/B wave** per benchmark: `--agent prolong` vs `--agent mfm` (episodes + tool, no
   retrieval block; in KiCad also the plan queue). Same seeds, model, caps.
6. **Optional layers** (section 5), each behind a flag, each its own wave.

Steps 2 and 3 edit baseline files. Step 1 is what makes that safe.

---

## 7. Parity: what stays fixed, and the pin tests

The comparison against the baseline arms and against the benchmarks' own published
settings has to stay fair, so these are invariants of the refactor, not defaults:

- **Driver interfaces.** MCU: `ProlongAgent(action_space, provider, ...)` with the same
  keyword arguments, `load_system_prompt`, `get_action(frame_buffer, thought_history,
  action_history, current_step, ..., info)` returning the same `(think, wire, "")`
  triple, `get_default_action`, `on_esc_rejected`, `save_state`. KiCad:
  `make_agent(kind, **kw)`, `predict(instruction, png, step_idx, max_steps)` returning
  `(message, calls, done)`, `reset`, `add_feedback`, `finish`, `audit`. `run-arm.sh` and
  `run_eval.py` keep every existing flag and default; `--agent mfm` is added, nothing is
  renamed.
- **What the model receives.** The same `AGENTS.md`, the same turn prompt, the same
  attached image, the same `logs.txt` and `frames/` layout, the same `sandbox_mode`,
  egress allowlist, `CODEX_HOME` policy, timeouts, caps (`action_cap`, `repeat_cap`,
  `step_cap`, `MAX_BATCH`, `analyzer_retries`, session age) and the same retry loop per
  benchmark. With `--agent mfm` the only additions are the `episodes/` tree, the two
  tools, and one paragraph in `AGENTS.md`.
- **What comes out.** The same `actions.json` / `last_message.txt` contract, the same
  workspace files, the same audit keys in `prolong_vision_audit.json` and the KiCad
  `results.jsonl` (new keys are added under `"mfm"`, none removed), the same
  `result.json` / `--resume` behaviour.

The baseline guarantee moves from "no file edited" to "three things pinned". All three
were recorded from the pre-refactor code (`tests/pins/`) and are green on the refactored
code. `tests/test_pins_argv.py`, `test_pins_prompts.py`, `test_pins_replay.py`; a fake
`codex` (`tests/fake_codex.py`) plays a scripted reply per call and records argv, cwd,
attachments, resume flag, environment and prompt. Run from the MFM root with the `vla`
env: `python -m pytest tests`.

1. **Argv snapshot.** `CodexTurn._args()` for each of {MCU, KiCad} x {hosted, `base_url`
   set} x {first call, resumed}: the full list, element by element. The two repos' lists
   are already identical except the `-o` file name, and `prolong_search/selftest.py`
   already asserts the safe flags and the resume order; this pins the whole list.
   Extended to the sandbox environment the wrapper is given (`CODEX_HOME`,
   `CODEX_SANDBOX_ALLOW`).
2. **Prompt hash.** sha256 of `AGENTS.md` as written and of the turn prompt for the first
   and a later turn, per benchmark, the way `gym_codex/selftest.py` pins the direct arm's
   `PROMPT_SHA`. With the store sink on, `AGENTS.md` differs by exactly the appended
   paragraph; the turn prompt does not differ.
3. **Log bytes.** A recorded trace per benchmark (a sequence of observations and model
   replies, no engine: MCU's `MCU_STAGE_OUT` stage outputs and one saved KiCad task)
   replayed through the agent with a fake `CodexTurn`; `logs.txt` and `frames/` must
   equal the recording byte for byte. After step 4 the same trace with the store on must
   produce the same `logs.txt`, and `render_logs_txt(store)` must reproduce it too.

The audit additionally records `episodes_tool_calls` (from the rollout scan, matching
`tools/episodes.py`), so a wave can say whether the agent used the new surface at all,
separately from whether the score moved. `compactions` must stay 0, as today.

---

## 8. Decisions that need your call

- **Episode granularity in MCU:** plan entry (proposed; hundreds of directories, per-tick
  detail in `ticks.jsonl`) versus tick (6k-12k directories) versus Codex turn (fewer, but
  loses the per-entry outcome).
- ~~Retry policy parity~~ Decided: MCU keeps its fixed loop; the policy is per adapter.
- **Retrieval block in the turn prompt:** off in the base arm (proposed); on as a second
  arm. Decided: the KiCad plan queue is on in the base arm (section 4).
- **When `mcu_worldmodel/` and `worldmodel_search/` are deleted:** in the same change or
  (proposed) in a cleanup commit after the first MFM wave, so the published world-model
  numbers keep a runnable source until the successor has numbers of its own.
- **Whether the submodule shims stay:** one release with `prolong_mc.codex_backend` and
  `prolong_search.codex_backend` re-exporting `mfm.backend` (proposed), then delete.
