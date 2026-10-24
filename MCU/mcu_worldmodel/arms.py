"""The arms of the paper on the Minecraft chassis.

One chassis (executor, perception, caps, milestone ledger) runs every arm; an arm is the
memory it is given and the contract that goes with it. `ARMS[name]` is what
`WorldModelAgent` is built with beside `memory_mode=MEMORY_MODE[name]`. Every arm reads
the short contract and acts through the raw keys alone: no arm is given a built-in
procedure of any grain (procedures.py), and the runner's own guards are off for all of
them. The mfm arm's own scripts are the only procedures there are.

    direct       no persistent memory: every turn is the present alone
    logbook      PRO-LONG: one append-only `logs.txt` the model greps
    vista        VISTA: one thread calling `play`, the frame archive behind `inspect`,
                 GUIDE.md / WORKING.md, a checkpoint handoff when the context fills
    mfm-matched  Multimodal Filesystem Memory on the baselines' contract: the log, one
                 episode per plan entry (frame, state, action, outcome), the index
                 and its query tool,
                 the frame tools and the carried lives under `previous/`
    mfm          the same memory, and the agent builds its own harness: its own `mine/`
                 (notes, working memory, procedures, reflexes), the skill package, the
                 contract rewritten around them
"""
from __future__ import annotations

from typing import Any

#: What every arm is given.
SHARED: dict[str, Any] = dict(
    thin=True,                # the short contract; the rules under references/
    harness_reflexes=False,   # the runner's guards and escapes are off
)

#: The memory itself, common to both MFM arms.
MFM_MEMORY: dict[str, Any] = dict(
    expect=True,              # the EXPECT line, echoed next turn against the record
    frames=True,              # tools/zoom.py
    event_sheet=False,        # the current view alone is attached
)

#: What the self-writing arm adds to it.
MFM_OWN: dict[str, Any] = dict(
    minimal=True,             # the contract written for an arm with files of its own
    own=True,                 # mine/ persists; mine/procedures/*.py are procedures
    own_reflexes=True,        # mine/reflexes/*.py run on the live state
    own_live=True,            # LOOP = True scripts run during the plan on the live frame
    skills=True,              # the skill package under skills/
)

ARMS: dict[str, dict[str, Any]] = {
    "direct": SHARED,
    "logbook": SHARED,
    "vista": SHARED,
    "mfm-matched": {**SHARED, **MFM_MEMORY},
    "mfm": {**SHARED, **MFM_MEMORY, **MFM_OWN},
}

#: The memory mode of the chassis each arm runs in.
MEMORY_MODE = {"direct": "direct", "logbook": "logbook", "vista": "vista",
               "mfm-matched": "mfm", "mfm": "mfm"}

#: Turns one model session is kept for (0 = the whole life, compacted by the CLI).
SESSION_TURNS = {"direct": 1, "logbook": 0, "vista": 0, "mfm-matched": 0, "mfm": 0}
