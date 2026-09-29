"""The four arms of the paper on the Minecraft chassis.

One chassis (executor, perception, caps, milestone ledger) runs all four; an arm is the
memory it is given and the contract that goes with it. `ARMS[name]` is what
`WorldModelAgent` is built with beside `memory_mode=name`.

    direct   no persistent memory: every turn is the present alone
    logbook  PRO-LONG: one append-only `logs.txt` the model greps
    vista    VISTA: one thread calling `play`, the frame archive behind `inspect`,
             GUIDE.md / WORKING.md, a checkpoint handoff when the context fills
    mfm      Multimodal Filesystem Memory: the log, one episode per plan entry
             (frame, state, action, outcome), the index and its query tool, the
             carried lives under `previous/`, and the model's own `mine/`
"""
from __future__ import annotations

from typing import Any

#: The mfm arm as the paper's runs configured it.
MFM: dict[str, Any] = dict(
    expect=True,              # the EXPECT line, echoed next turn against the record
    frames=True,              # tools/zoom.py
    retrieval=True,           # the [RECALL] block in the turn prompt
    event_sheet=False,        # the current view alone is attached
    thin=True, minimal=True,  # the short contract; the rules under references/
    atoms=True,               # the procedure set is the closed-loop primitives
    own=True,                 # mine/ persists; mine/procedures/*.py are procedures
    own_reflexes=True,        # mine/reflexes/*.py run on the live state
    harness_reflexes=False,   # the runner's guards and escapes are off
    skills=True,              # the skill package under skills/
)

ARMS: dict[str, dict[str, Any]] = {"direct": {}, "logbook": {}, "vista": {}, "mfm": MFM}

#: Turns one model session is kept for (0 = the whole life, compacted by the CLI).
SESSION_TURNS = {"direct": 1, "logbook": 0, "vista": 0, "mfm": 0}
