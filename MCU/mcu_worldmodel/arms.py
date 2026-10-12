"""The arms of the paper on the Minecraft chassis.

One chassis (executor, perception, caps, milestone ledger) runs both arms; an arm is
the memory it is given and the contract that goes with it. `ARMS[name]` is what
`WorldModelAgent` is built with beside `memory_mode=MEMORY_MODE[name]`. Both arms read
a short contract and act through the same 28 closed-loop primitives
(`procedures.ATOMS`); neither is given a task-shaped macro, and the runner's own guards
are off for both.

    direct  no persistent memory: every turn is the present alone
    mfm     Multimodal Filesystem Memory: the log, one episode per plan entry (frame,
            state, action, outcome), the index and its query tool, the frame tools,
            the [RECALL] block and the carried lives under `previous/`; and the
            agent builds its own harness: its own `mine/` (notes, working memory,
            procedures, reflexes), the skill package, the contract written around them
"""
from __future__ import annotations

from typing import Any

#: What both arms are given.
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
    retrieval=True,           # the [RECALL] block in the turn prompt
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
    "direct": SHARED,
    "mfm": {**SHARED, **MFM_MEMORY, **MFM_OWN},
}

#: The memory mode of the chassis each arm runs in.
MEMORY_MODE = {"direct": "direct", "mfm": "mfm"}

#: Turns one model session is kept for (0 = the whole life, compacted by the CLI).
SESSION_TURNS = {"direct": 1, "mfm": 0}
