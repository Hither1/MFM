"""Subset of MineExplorer's `mc_agent`, vendored for the PRO-LONG purple agent.

Only the modules `prolong_agent.py` actually needs are carried over -- upstream's
`__init__` pulls in DefaultAgent, HypothesisAgent and the context builders, none of
which are on ProlongAgent's path (Codex is its model channel, not a provider).
The module files themselves are byte-identical to
MineExplorer@codex/qwen35-27b-minecraft-0313-0544 so they can be re-synced.

Source: /datapool/data3/storage/ruihan/data_share/jh/Collab/MineExplorer
"""
