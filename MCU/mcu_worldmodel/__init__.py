"""World Model as/from Multimodal Filesystem Memory for Embodied Agents.

The system this package implements is the union of two designs from the sibling
MineExplorer repo, scaled onto MCU's long-horizon tasks:

    mc_agent/hypothesis_agent.py   a typed DAG of beliefs about the world, plus a
                                   *harness-enforced* discipline on that DAG (a goal
                                   is confirmed by the environment, never by the model)
    mc_agent/prolong_agent.py      a coding agent whose memory is a persistent
                                   filesystem it reads programmatically, rather than a
                                   context window it re-reads

Neither alone is the system in the figure. A belief DAG kept in the prompt must be
re-sent every step, so it can only ever be as large as the context window allows. An
append-only record holds everything the episode produced but has no
structure over it beyond `grep` -- it re-derives what it believes from raw log lines on
every turn. Putting the DAG *into* the filesystem is what makes the belief store outlive
the context, and adding an explicit induction pass is what turns an append-only trace
into something with entities, topology and causal structure in it.

So the loop here has two kinds of turn, not one:

    act turn        cheap, frequent. Read the current observation and the world model,
                    write `actions.json`. This is PRO-LONG's turn.
    induction turn  expensive, periodic. Read the accumulated filesystem -- frames,
                    events, positions, the hypothesis graph -- and rewrite the five
                    structured world-model documents. This box has no counterpart in
                    either source agent; it is what the figure adds.

Ground truth comes from MineRL's own statistics (`mine_block`, `craft_item`,
`kill_entity`, `inventory`), which MCU exposes and MineExplorer's remote sandbox did
not. That is what the discipline layer is re-grounded on: MCU's action space has no
`ESC`, so the "did the model just declare victory for itself" check that ESC-gating
performed upstream is instead performed against the statistics (see discipline.py).
"""

__all__ = ["memory", "hypotheses", "discipline", "milestones", "induction", "agent"]
