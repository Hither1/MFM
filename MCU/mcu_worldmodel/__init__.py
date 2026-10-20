"""The Minecraft chassis of the arms mfm, mfm-atoms and direct (MCU-AgentBeats).

One chassis -- executor, perception, plan caps, milestone ledger -- runs every arm; an
arm is the memory it is given and the contract that goes with it (`arms.py`):

    mfm        (the default) Multimodal Filesystem Memory: the log, one episode per plan
               entry with its frame, the index and its query tool, the carried lives, the
               model's own procedures and reflexes; no built-in procedure: the model
               builds every skill from raw actions
    mfm-atoms  mfm with the 28 closed-loop primitives (`procedures.ATOMS`)
    direct     no persistent memory; the 28 primitives

`agent.WorldModelAgent` is the turn loop; `worldmodel_purple_agent.py` (one directory
up) serves it to the benchmark's green agent. See README.md beside this file.
"""
