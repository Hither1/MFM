"""The one paragraph the MFM arm appends to PRO-LONG's system prompt.

Kept out of `prompts.py` so the baseline arm's prompt hash does not move; appended by
`MemoryAgent.full_system_prompt` when the episode store is on.
"""

MFM_MEMORY_NOTE = """\
`episodes/` holds the same history as `logs.txt`, one directory per plan entry:
`state/state.json` (the `[STATE]`/`[INV]`/`[HOTBAR]`/`[GUI]`/`[VITALS]`/`[MOBS]`/`[GOALS]` \
fields at the entry's first tick, structured), `action.json` (the entry, its place in \
the plan, the briefing and plan), `outcome.json` (what the entry changed: moved, \
descended, inventory delta, milestone transition, tags) and `observation/image.png` (the \
frame the decision was made from). `./tools/episodes.py --last 5 | --steps A B | \
--near X Z | --tag stuck | --grep text` lists matching episodes one per line with their \
paths; `--sheet out.png` tiles their frames. Use it instead of parsing the log by hand \
when the question is "what happened when I was here / did this before"."""
