"""Multimodal Filesystem Memory for embodied agents on MCU.

One chassis -- procedures, the GUI cursor, perception, the guards and the milestone
ledger -- and one axis, the memory mode, which is the only thing an arm may change:

    logbook   PRO-LONG's protocol: an append-only logs.txt the model greps, nothing else
    mfm       the logbook plus the episode store beside it (episodes.py) and a query tool
    vista     VISTA's protocol: one long thread, `play`/`inspect` tools, a handoff (vista.py)
    arc       arc-code's harness: one coding-agent session, `./act` as its actuator (arc.py)
    direct    no memory at all: each turn is the present alone

Every act turn reads the current observation and the arm's memory, and writes
`actions.json` (or, for direct, a fenced JSON block). Ground truth comes from MineRL's
own statistics (`mine_block`, `craft_item`, `kill_entity`, `inventory`), which MCU
exposes: the ledger verifies milestones from them and never from a model output.
"""

__all__ = ["memory", "milestones", "agent", "episodes", "vista", "arc"]
