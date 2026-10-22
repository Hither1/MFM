"""The arms on the Minecraft chassis.

One chassis (executor, perception, caps, milestone ledger) runs every arm; an arm is
the memory it is given and the contract that goes with it. `ARMS[name]` is what
`WorldModelAgent` is built with beside `memory_mode=MEMORY_MODE[name]`. Every arm reads a
short contract, none is given a task-shaped macro, and the runner's own guards are off
for all. The default arm, `mfm`, has no built-in procedure (no primitives): every plan
entry is a raw action or a script the model wrote. `mfm-atoms` and `direct` act through
the 28 closed-loop primitives of `procedures.ATOMS`.

    mfm     (the default) Multimodal Filesystem Memory: the log, one episode per plan entry (frame,
            state, action, outcome), the index and its query tool, the frame tools
            and the carried lives under `previous/`; and the
            agent builds its own harness: its own `mine/` (notes, working memory,
            procedures, reflexes), the skill package, the contract written around them.
            No hand-written skill of any grain: the procedure set is empty (not even
            the atoms), skills/ ships no procedure or reflex example, and the runner's
            wall watcher is off; the model acts through the raw keys and the
            procedures, closed loops and reflexes it writes itself
    mfm-atoms  mfm with the 28 atoms and the example procedures and reflexes under
            skills/ (the setting of the paper's runs)
    direct  no persistent memory: every turn is the present alone; the 28 atoms
"""
from __future__ import annotations

from typing import Any

#: What every arm is given (`mfm` then empties the procedure set: primitives=False).
SHARED: dict[str, Any] = dict(
    thin=True,                # the short contract; the rules under references/
    atoms=True,               # the procedure set is the closed-loop primitives
    harness_reflexes=False,   # the runner's guards and escapes are off
    near_deaths=True,         # a death at the spawn is named too (agent._respawned_here)
)

#: The memory of the mfm arm.
MFM_MEMORY: dict[str, Any] = dict(
    expect=True,              # the EXPECT line, echoed next turn against the record
    frames=True,              # tools/zoom.py
    event_sheet=False,        # the current view alone is attached
)

#: The harness the mfm arm writes for itself.
MFM_OWN: dict[str, Any] = dict(
    minimal=True,             # the contract written for an arm with files of its own
    own=True,                 # mine/ persists; mine/procedures/*.py are procedures
    own_reflexes=True,        # mine/reflexes/*.py run on the live state
    skills=True,              # the skill package under skills/
    own_live=True,            # a script with LOOP = True runs on the live state and view
)

ARMS: dict[str, dict[str, Any]] = {
    "mfm": {**SHARED, **MFM_MEMORY, **MFM_OWN, "primitives": False},
    "mfm-atoms": {**SHARED, **MFM_MEMORY, **MFM_OWN},
    "direct": SHARED,
}

#: The memory mode of the chassis each arm runs in.
MEMORY_MODE = {"direct": "direct", "mfm": "mfm", "mfm-atoms": "mfm"}

#: Turns one model session is kept for (0 = the whole life, compacted by the CLI).
SESSION_TURNS = {"direct": 1, "mfm": 0, "mfm-atoms": 0}
