# The paper and the code

Where each part of *Multimodal Filesystem Memory for Long-Horizon Embodied Agents* is
implemented, and where the code and the text differ. Paths are relative to the
repository root. `W` is the workspace of one life (Minecraft) or one task (KiCad): the
directory the model works in.

## Section 3.2: memory representation

| paper | files in `W` | written by | code |
|---|---|---|---|
| Episodic memory `e_i = (id, interval, V, S, A, m)` | `episodes/ep_<N>/observation/image.png` (V), `state/state.json` (S), `action.json` (A), `outcome.json` (m: moved, inventory change, events, notes, tags) | harness, one episode per plan entry (Minecraft) or action batch (KiCad) | `mfm/memory/store.py` `EpisodeStore`; adapters `MCU/mcu_worldmodel/episodes.py`, `CUA-KiCad/gym_codex/prolong_agent.py` |
| Associative index `z_i = (id, k_i, rho_i)` | `index.jsonl`, one row per closed episode: step interval, position, action kind, tags, a one-line action and outcome summary, the paths of the evidence | harness | `mfm/memory/store.py` (`_close`) |
| The log | `logs.txt`, append-only sections of `[STATE]`, `[INV]`, `[EVENT]`, `[NOTE]`, `[PLAN]` | harness | `mfm/memory/log.py` (KiCad), `MCU/mcu_worldmodel/memory.py` (Minecraft) |
| Spatial memory | `grid.jsonl` (traversed cells); the position in every index row; the model's landmarks in `mine/notes.md` | harness / model | `MCU/mcu_worldmodel/grid.py`; `--near X Z` in `mfm/memory/tools/episodes.py` |
| Semantic memory (`notes.md`, `GUIDE.md`) | `mine/notes.md`, `mine/GUIDE.md` (Minecraft); `notes/` (KiCad) | model | contract text in `MCU/mcu_worldmodel/own.py`, `skills.py`; `mfm/memory/carry.py` |
| Procedural memory (`procedures/`) | `mine/procedures/*.py`: executable, run by the harness on the live state and expanded to primitive actions. `mine/reflexes/*.py`: run every 4 ticks, may stop or replace the plan | model | `MCU/mcu_worldmodel/own.py` |
| Working memory (`working.md`) | `mine/working.md`, put in front of the model every turn as `[WORKING]` (first 1,500 characters) | model | `MCU/mcu_worldmodel/agent.py` (`WORKING_CAP`) |

The harness-written files are immutable for the model: a turn that shrinks `logs.txt`,
`index.jsonl` or the contract is reported as a fault (`MCU/mcu_worldmodel/memory.py`
`HARNESS_OWNED_FILES`).

## Section 3.3: memory retrieval

| paper | code |
|---|---|
| Agent-initiated search over the index: by time, location, action, tag, text; chronological, with a limit | `mfm/memory/tools/episodes.py`, in `W` as `./tools/episodes.py`: `--steps A B`, `--near X Z [--radius]`, `--action`, `--tag`, `--grep`, `--last N`; `--previous` searches the carried records |
| Loading the referenced evidence | the model opens the files the rows name: `view_image` (Codex) or `Read` (Claude Code) on a frame, plain reads of `state.json`, `action.json`, `outcome.json` |
| Contact sheet | `./tools/episodes.py ... --sheet out.png` |
| A past observation beside the current view | `./tools/episodes.py --then-now <episode> --q "..."` |
| Magnifying a region | `mfm/memory/tools/zoom.py`, in `W` as `./tools/zoom.py` |
| The question kept with the lookup | `--q "<question>"` is printed back into the tool output, which the turn transcript keeps |

On Minecraft the search is the model's alone: the harness computes no recall from the
index. What the turn prompt does carry from the record is the recent past -- `[RECENT]`,
the last six finished entries, and `[OBSERVED]`, the last plan's entries with the frame
each started from (difference 2). On KiCad the harness also computes a `[RECALL]` block from the index
when the last turn's situation and action occurred before (`mfm/memory/recall.py`).

## Section 3.4: consolidation

Consolidation is the model's own work, inside its turns, under the contract: it writes
and revises `mine/notes.md`, `mine/GUIDE.md`, `mine/working.md` and its procedures, and
cites episode ids so that a note can be checked against its frame later. The harness
never edits those files and never rewrites the episodic record.

- Minecraft: the first turn of a life that carries earlier lives is a workshop turn: the
  model reads `previous/life_<i>/` and writes its guide before it plays
  (`skills/memory/SKILL.md`, from `MCU/mcu_worldmodel/skills.py`; the carry is
  `MCU/mcu_worldmodel/previous.py`). The earlier lives' procedures are not installed:
  the model copies the ones it keeps. The carry writes one table beside them,
  `previous/scripts.md` (each earlier script's calls, guard refusals and last outcome,
  counted from the carried index and log), so that choice is made on the record.
- KiCad (`mfm-carry`): the finished tasks' records are linked under `previous/<task>/`,
  the model's `notes/` persists across tasks, the evaluator's score of each finished
  task is given in `previous/outcomes.md`, and the harness folds the carried index into
  `previous/situations.md` at each task boundary (`mfm/memory/carry.py`,
  `mfm/memory/consolidate.py`).

## Section 4: experiments

| paper | code |
|---|---|
| Direct evaluation | `--memory direct` (Minecraft), `--agent direct` (KiCad) |
| PRO-LONG | `--memory logbook`, `--agent prolong-logonly`: the append-only log is the only memory |
| VISTA | `--memory vista`, `--agent vista`: `mfm/vista/`, adapters `MCU/mcu_worldmodel/vista.py`, `CUA-KiCad/gym_codex/vista_agent.py` |
| MFM | `--memory mfm` with the settings of `MCU/mcu_worldmodel/arms.py` (`--memory mfm-matched` is the same memory without procedures of its own, see difference 2); `--agent mfm-carry` with the settings of `CUA-KiCad/gym_codex/memory_agents.py` |
| MFM (no cross-task memory), Table 3 | `--agent mfm` |
| Table 5: the standing brief, the procedure set | every arm has the short contract and no built-in procedure (`SHARED` in `MCU/mcu_worldmodel/arms.py`, `procedures.refusal`); sizes in difference 2 |
| Step budgets: Diamond 12,000, Ender Dragon 36,000 | defaults of `MCU/scripts/run-arm.sh` by task. The recorded 16/24 dragon lives ran on 100,000-step budgets under a 13 to 14 h wall clock, as lives 2 and 3 of a chain (see difference 8) |
| Seeds: the Minecraft world, the KiCad task order | `--world-seed` (`MCU/src/util.py` `load_world_spec`), `--task-order-seed` (`CUA-KiCad/gym_codex/run_eval.py`) |
| Milestone scoring | the benchmark's own `MilestoneTrackerCallback`; the chassis keeps the same count in `MCU/mcu_worldmodel/milestones.py` |
| Section 4.4, the Nether portal case study | task `nether_portal` (`MCU/MCU_benchmark/task_configs/tasks/nether_portal/`), host-side geometry ground truth in `MCU/mcu_worldmodel/portal.py`, `portal_probe.py`; read-out `MCU/scripts/portal_stats.py` |
| Section 4.5, skills written by the agent | `mine/procedures/`, `mine/reflexes/` of a life's workspace; the turn prompt lists them with call counts under `[OWN]` |

## Differences between the paper and this code

1. **Two of Table 4's four ablations are in this release, on Minecraft only.**
   `--no-history-images` (no frame of an earlier moment: no episode image, saved images
   swept before every turn, the hires record unreadable, and the codex thread stripped of
   every earlier attachment before each call -- a resumed thread otherwise re-sends them
   all; the current view is still attached) and `--flat-retrieval` (the same `episodes/`, `index.jsonl` and frames,
   without `tools/episodes.py`) are flags of `--memory mfm` for a life from scratch;
   with both off the arm is the full method, byte for byte, and both together give
   the indexing x visual-evidence 2x2 (`MCU/mcu_worldmodel/agent.py`, `episodes.py`,
   `prompts._memory_paragraph`; `tests/test_mfm_ablations.py`). The other two (no agent
   procedures, no consolidation) are not in this release. Table 4's numbers were
   recorded on an earlier configuration of the arm (built-in procedures on).
2. **What the arms share on Minecraft, and what they do not.** Shared by every arm, as
   in Table 5: a short contract, no built-in procedure at all (every entry is a raw
   action; the `mfm` arm's own scripts are the only procedures), the runner's own guards switched off (the lava stop, the pillar
   on a hit, the refusals), the executor, the perception, the plan caps, the frame size
   (320x180), the model and its reasoning effort, the milestone ledger. Not shared:
   - The contracts are short but not one text: `mfm` 6,541 bytes, `logbook` 7,051,
     `direct` 12,850, `vista` 13,556 (`tests/pins_release/*_contract.md`).
     `logbook` and `mfm` read the longer rules under `references/`; `direct` and `vista`
     have no file access, so their contract carries the GUI facts and the recipe list,
     and the GUI, skills and survival references are left out for them.
   - The turn message: every arm gets the state, the inventory and the milestone
     ledger. The two MFM arms also get `[RECENT]` (the last six finished entries, from
     the record), `[MAP]` (the cells this life walked, its hazards and water) and
     `[EXPECTED]`/`[OBSERVED]` (last turn's EXPECT line against what the harness
     recorded, with each entry's frame); `mfm` also gets `[WORKING]`, the head of its
     `mine/working.md`. `logbook` reads its past from `logs.txt` alone, and `vista`
     from its own thread and `inspect` (`MCU/mcu_worldmodel/agent.py` `_turn_message`).
   - `mfm` alone has the skill package and its own procedures and reflexes; the
     reflexes it copies or writes act on every fourth tick, and no other arm has a
     tick layer.
   - The baseline results of the paper were recorded with an earlier configuration of
     the baselines (the full contract of 76 to 77 KB, the macro procedure library, the
     runner's guards on); this release runs them as the paper describes them.

   `--memory mfm-matched` is the memory of `mfm` on the contract of `logbook`, without
   procedures of its own. No result of the paper was recorded with it.
3. **The MFM arms on KiCad have a design call.** Before the first action the `mfm` and
   `mfm-carry` arms make one call at reasoning effort `high` that writes `design.md`
   and `intent.json`, and their system prompt carries a paragraph of schematic
   conventions. The baselines have neither.
4. **Names.** The agent-written files of the paper (`notes.md`, `GUIDE.md`,
   `working.md`, `procedures/`) live under `mine/` on Minecraft; on KiCad the model's
   directory is `notes/`.
5. **Examples shipped with the harness.** `skills/procedures/scripts/` and
   `skills/reflexes/scripts/` hold working examples written by the authors, which the
   model may copy into `mine/` (`MCU/mcu_worldmodel/skills.py`). A procedure found
   under `mine/` of a run is therefore the model's own only if it differs from the
   shipped example of the same name. The examples, and two passages of the shared
   reference text (the portal recipe, the lake rule), were revised after the recorded
   runs from what those runs' lives died of; the README's results section names the
   commits.
6. **Lives carried into a run.** An `mfm` or `mfm-matched` life may be started with the
   records of earlier lives in the same world (`--seed-memory`), and a `logbook` life with an
   earlier log (`--seed-log`). `vista` and `direct` take none.
7. **Figures from earlier code.** The qualitative figures of the appendix were drawn
   from lives recorded before the final contract; the mechanisms they show (frame
   lookup, then-now comparison, zoom) are the ones in this release, the contract text
   those lives read is not.
8. **The dragon result is a chain of lives.** The paper's 16/24 is `of3r_mfm` (life 2)
   and `of3m_mfm` (life 3) of one chain in one world, each seeded with the lives before
   it, on 100,000-step budgets under a 13 to 14 hour wall clock (16/24 at 43,400 and
   49,400 steps; 15 and 16 of the 24 by step 36,000). Life 1 of that chain reached
   10/24. A single life on the 36,000-step default is a different protocol; the README
   lists what such lives scored on this release.
