# The Minecraft chassis

One chassis runs the arms on MCU-AgentBeats. The executor, the perception, the plan
caps and the milestone ledger are shared; an arm is the memory the model is given, the
procedures it is given, and the contract that describes them.

| `--memory` | what the model has between turns | built-in procedures |
|---|---|---|
| `mfm` (default) | the log, one episode per plan entry with its frame, the index and its query tool, the carried lives, its own procedures, closed loops and reflexes | none |
| `mfm-atoms` | the same as `mfm` | the 28 closed-loop primitives of `procedures.ATOMS` |
| `direct` | nothing: each turn is the state block and the current view | the 28 primitives |

The default `mfm` arm has no built-in procedure of any grain: the procedure set is
empty, so every plan entry is a raw action or a script the model wrote under
`mine/procedures/`, and a call of a built-in is refused with a note. `skills/` holds no
example procedure or reflex to copy (only the memory scripts and one example reflex,
`ore_watch.py`, that is not installed), and the runner does not watch the walls for ore.
To click in a screen without a craft procedure, the turn prompt adds a `Main rows:` line
(the slot number of each item), the script stdin adds `slots` and `cursor`, and
`references/gui.md` starts with the screen geometry (slot centres, cursor speed).

`mfm-atoms` is the setting of the paper's runs: the 28 primitives, and example
procedures and reflexes under `skills/`. A call of any other procedure is refused with a
note. `direct` has the same 28 primitives and no file access, so its contract carries
the procedures' full descriptions and the other references are left out. Every arm reads
a short contract, and the runner's own guards are off for all of them; the reflexes
under `mine/reflexes/` are the model's own. A respawn close to the place of death is
reported as a death in every arm (`near_deaths`).

The settings of the arms are in `arms.py` and nowhere else.

## One turn

1. The green agent (the benchmark) sends an observation: the first-person frame and the
   game's own statistics.
2. `agent.WorldModelAgent.observe` updates the milestone ledger and the cell map from the
   statistics, and closes the plan entry that just ran: its outcome goes to the log and,
   for `mfm`, to the episode store with the frame it started from.
3. When the plan queue is empty, `next_action` runs one model turn through the Codex CLI
   or Claude Code (`codex_backend.py`, `claude_backend.py`). The model works in the
   workspace directory, reads what its arm gives it, and writes `actions.json`.
4. `actions.py` validates the plan. A raw entry is held for its ticks; in `mfm-atoms`
   and `direct`, `procedures.py` and the `macros_*.py` modules expand a built-in entry
   into environment actions, one per tick, under closed-loop stop conditions. An own
   procedure with `LOOP = True` is a closed loop of the model's own: the harness
   calls it again with the state and the frame of each tick it runs (`own_live`,
   `own.py`). The simulator has no crafting action: a craft is a sequence of clicks in
   the inventory screen (`gui.py`, `macros_gui.py`).

## The workspace of the `mfm` arm

```
memory/
  AGENTS.md            the contract (CLAUDE.md on the Claude Code channel)
  logs.txt             append-only: every plan entry and what the game said happened
  index.jsonl          one row per episode: step, position, action, outcome, frame
  episodes/<id>/       observation/ (the frame), state/, action.json, outcome.json
  grid.jsonl           the runner's cell map, kept between turns and lives
  tools/episodes.py    the query tool over the index (filters, --sheet, --then-now)
  tools/zoom.py        crop and magnify a region of a saved frame
  references/          the rules the short contract points to
  skills/              harness-written: how to use the memory, what makes a good
                       script, how reflexes run (mfm-atoms: also example procedures and
                       reflexes to copy into mine/)
  mine/                the model's own: notes.md, working.md, GUIDE.md,
                       procedures/*.py and reflexes/*.py
  previous/life_<i>/   the record of an earlier life in the same world (--seed-memory)
```

`logs.txt`, `index.jsonl` and the contract are harness-owned: a turn that shrinks one of
them is a fault (`memory.py`). Everything the model is told about the past is a file it
can open; the turn prompt carries only `mine/working.md` and the `[RECALL]` block, which
the harness computes from the index (`mfm/memory/retrieve.py`).

## Modules

| module | what it is |
|---|---|
| `arms.py` | the arms and their settings |
| `agent.py` | the turn loop, the executor and its guards |
| `prompts.py` | the contract and the action reference each arm reads |
| `memory.py`, `episodes.py`, `previous.py` | the workspace, the episode store adapter, the carried lives |
| `own.py`, `skills.py` | the model's own procedures and reflexes; the skill package |
| `codex_backend.py`, `claude_backend.py` | one model turn through either CLI |
| `actions.py`, `procedures.py`, `macros*.py`, `harvest.py` | plan validation and the closed-loop procedures (`mfm-atoms` and `direct` are given the 28 of `procedures.ATOMS`; `mfm` none) |
| `milestones.py` | the ledger: what the game's statistics say has happened |
| `grid.py`, `governor.py` | the cell map; the stall watchdog |
| `vision.py`, `vision_nether.py`, `cursor.py`, `gui.py`, `camera.py` | frame detectors, GUI geometry, camera arithmetic |
| `craft_env.py` | the `drop` action the simulator's spec leaves out |
| `portal.py`, `portal_probe.py` | the Nether portal case study: host-side geometry ground truth |

## Running

`scripts/run-arm.sh` runs one life end to end; `--help` prints every option. The README
at the top of the repository has the setup and the commands.
