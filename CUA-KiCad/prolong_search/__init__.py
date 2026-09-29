"""PRO-LONG's programmatic memory, ported from MineExplorer to the search benchmarks.

The port that already exists (`MineExplorer:codex/*`, `prolong_mc/`) established what
survives a change of domain and what does not:

  survives   an append-only `logs.txt` the agent parses programmatically, a persistent
             workspace it may write helper files into, a JSON artifact as the only
             output that counts, `codex exec resume` for continuity with a cold start
             on overflow, and the log-window / stateless ablations *enforced* by
             building the directory the agent sees rather than by asking it not to look
  replaced   everything task-specific: the observation markers, the action vocabulary,
             and what one "step" is

`codex_backend` and `log` are the surviving half and are near-verbatim ports.
`prompts_bcp` and `plans` are the replaced half.

The benchmark maps onto an episode the way this repository's hypothesis arm already
implied:

  BrowseComp-Plus   episode = one question; step = one BM25 `search`. Memory is scoped
                    per question, matching `eval_hypothesis_browsecomp_plus.py`, whose
                    module docstring gives the reason: the questions are deliberately
                    disjoint.
"""
