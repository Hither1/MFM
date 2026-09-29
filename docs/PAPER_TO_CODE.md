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
| Semantic memory (`notes.md`, `GUIDE.md`) | `mine/notes.md`, `mine/GUIDE.md` or `mine/digest.md` (Minecraft); `notes/` (KiCad) | model | contract text in `MCU/mcu_worldmodel/own.py`, `skills.py`; `mfm/memory/carry.py` |
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

Beside the search the model starts, the harness computes a `[RECALL]` block from the
index and puts it in the turn prompt when there is something to report: repeated plans,
runs of an action that changed nothing, what happened at this place before
(`mfm/memory/retrieve.py` `recall_block`; on KiCad `mfm/memory/recall.py`).

## Section 3.4: consolidation

Consolidation is the model's own work, inside its turns, under the contract: it writes
and revises `mine/notes.md`, `mine/GUIDE.md`, `mine/working.md` and its procedures, and
cites episode ids so that a note can be checked against its frame later. The harness
never edits those files and never rewrites the episodic record.

- Minecraft: the first turn of a life that carries earlier lives is a workshop turn: the
  model reads `previous/life_<i>/` and writes its digest before it plays
  (`skills/memory/SKILL.md`, from `MCU/mcu_worldmodel/skills.py`; the carry is
  `MCU/mcu_worldmodel/previous.py`).
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
| MFM | `--memory mfm` with the settings of `MCU/mcu_worldmodel/arms.py` (`--memory mfm-matched` is the same memory on the baselines' harness, see difference 2); `--agent mfm-carry` with the settings of `CUA-KiCad/gym_codex/memory_agents.py` |
| MFM (no cross-task memory), Table 3 | `--agent mfm` |
| Step budgets: Diamond 12,000, Ender Dragon 36,000 | defaults of `MCU/scripts/run-arm.sh` by task |
| Seeds: the Minecraft world, the KiCad task order | `--world-seed` (`MCU/src/util.py` `load_world_spec`), `--task-order-seed` (`CUA-KiCad/gym_codex/run_eval.py`) |
| Milestone scoring | the benchmark's own `MilestoneTrackerCallback`; the chassis keeps the same count in `MCU/mcu_worldmodel/milestones.py` |
| Section 4.4, the Nether portal case study | task `nether_portal` (`MCU/MCU_benchmark/task_configs/tasks/nether_portal/`), host-side geometry ground truth in `MCU/mcu_worldmodel/portal.py`, `portal_probe.py`; read-out `MCU/scripts/portal_stats.py` |
| Section 4.5, skills written by the agent | `mine/procedures/`, `mine/reflexes/` of a life's workspace; the turn prompt lists them with call counts under `[OWN]` |

## Differences between the paper and this code

1. **Table 4 is not reproducible from this release.** The four ablation switches (no
   visual observations, flat log, no agent procedures, no consolidation) were removed;
   the code runs the full method and the baselines only.
2. **The arms do not share one contract on Minecraft.** The `mfm` arm runs the short
   contract with the primitive procedure set (28 atoms), the skill package, its own
   procedures and reflexes, and with the runner's own guards (the lava stop, the
   pillar on a hit, the refusals) switched off. `direct`, `logbook` and `vista` run the full contract
   with the macro procedure library and the runner's guards on. Shared by all four:
   the executor, the perception, the plan caps, the frame size (320x180), the model
   and its reasoning effort, the milestone ledger. Table 5 of the appendix lists the
   12 KB brief and the 28 atoms for every method; in the recorded runs and in this
   code they are the `mfm` arm's (its contract is 11,947 bytes, those of `direct` and
   `logbook` 76,144 and 77,341). `--memory mfm-matched` is the arm that removes the difference: the memory
   of `mfm` on the contract, procedure library and guards of the baselines, without
   procedures of its own. No result of the paper was recorded with it.
3. **The MFM arms on KiCad have a design call.** Before the first action the `mfm` and
   `mfm-carry` arms make one call at reasoning effort `high` that writes `design.md`
   and `intent.json`, and their system prompt carries a paragraph of schematic
   conventions. The baselines have neither.
4. **Names.** The agent-written files of the paper (`notes.md`, `GUIDE.md`,
   `working.md`, `procedures/`) live under `mine/` on Minecraft, and the guide may be
   named `digest.md`; on KiCad the model's directory is `notes/`.
5. **Examples shipped with the harness.** `skills/procedures/scripts/` and
   `skills/reflexes/scripts/` hold working examples written by the authors, which the
   model may copy into `mine/` (`MCU/mcu_worldmodel/skills.py`). A procedure found
   under `mine/` of a run is therefore the model's own only if it differs from the
   shipped example of the same name.
6. **Lives carried into a run.** An `mfm` or `mfm-matched` life may be started with the
   records of earlier lives in the same world (`--seed-memory`), and a `logbook` life with an
   earlier log (`--seed-log`). `vista` and `direct` take none.
7. **Figures from earlier code.** The qualitative figures of the appendix were drawn
   from lives recorded before the final contract; the mechanisms they show (frame
   lookup, then-now comparison, zoom) are the ones in this release, the contract text
   those lives read is not.
