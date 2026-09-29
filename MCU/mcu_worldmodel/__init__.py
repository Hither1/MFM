"""The Minecraft chassis of the paper's four arms (MCU-AgentBeats).

One chassis -- executor, perception, plan caps, milestone ledger -- runs every arm; an
arm is the memory it is given and the contract that goes with it (`arms.py`):

    direct   no persistent memory
    logbook  PRO-LONG: one append-only `logs.txt` the model greps
    vista    VISTA: one thread calling `play`, the frame archive behind `inspect`
    mfm      Multimodal Filesystem Memory: the log, one episode per plan entry with its
             frame, the index and its query tool, the carried lives, the model's own
             procedures and reflexes

`agent.WorldModelAgent` is the turn loop; `worldmodel_purple_agent.py` (one directory
up) serves it to the benchmark's green agent. See README.md beside this file.
"""
