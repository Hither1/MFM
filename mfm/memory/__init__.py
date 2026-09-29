"""What the agent remembers between model calls, as files in its workspace.

`log.EpisodeLog` is the append-only `logs.txt` plus the attachment tree.
`store.EpisodeStore` is the episodic record beside it: one directory per episode
(observation, state, action, outcome) and one row per episode in `index.jsonl`.
`tools/episodes.py` and `tools/zoom.py` are the programs the model queries and inspects
the record with; `retrieve` and `recall` compute the `[RECALL]` block from the index.
`carry` and `consolidate` are what outlives a task on KiCad.
"""
