# The Minecraft chassis

One chassis runs the two arms on MCU-AgentBeats. The executor, the perception, the
plan caps and the milestone ledger are shared; an arm is the memory the model is given
and the contract that describes it.

| `--memory` | the paper's name | what the model has between turns |
|---|---|---|
| `direct` | Direct | nothing: each turn is the state block and the current view |
| `mfm` | MFM | the log, one episode per plan entry with its frame, the index and its query tool, the carried lives, its own procedures, closed loops and reflexes |

Both arms read a short contract and have the same procedure set, the 28 closed-loop
primitives of `procedures.ATOMS`; a call of any other procedure is refused with a note.
`mfm` reads the longer rules under `references/`; `direct` has no file access, so its
contract carries the procedures' full descriptions and the other references are left
out. The runner's own guards are off for both arms; the reflexes under `mine/reflexes/`
are the `mfm` arm's. A respawn close to the place of death is reported as a death in
both arms (`near_deaths`).

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
4. `actions.py` validates the plan; `procedures.py` and the `macros_*.py` modules expand
   each entry into environment actions, one per tick, under closed-loop stop conditions.
   An own procedure with `LOOP = True` is a closed loop of the model's own: the harness
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
  skills/              harness-written: how to use the memory, and example procedures
                       and reflexes to copy into mine/
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
| `actions.py`, `procedures.py`, `macros*.py`, `harvest.py` | plan validation and the closed-loop procedures (the arms are given the 28 of `procedures.ATOMS`) |
| `milestones.py` | the ledger: what the game's statistics say has happened |
| `grid.py`, `governor.py` | the cell map; the stall watchdog |
| `vision.py`, `vision_nether.py`, `cursor.py`, `gui.py`, `camera.py` | frame detectors, GUI geometry, camera arithmetic |
| `craft_env.py` | the `drop` action the simulator's spec leaves out |
| `portal.py`, `portal_probe.py` | the Nether portal case study: host-side geometry ground truth |

## Running

`scripts/run-arm.sh` runs one life end to end; `--help` prints every option. The README
at the top of the repository has the setup and the commands.
