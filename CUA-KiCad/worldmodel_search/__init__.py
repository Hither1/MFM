"""World-model memory for the search benchmarks.

The fourth arm of the memory comparison, alongside direct (no memory), hypothesis
(a belief DAG re-rendered into every prompt) and prolong (an append-only log plus a
workspace). This arm is the hypothesis arm's structure given the prolong arm's
substrate, plus the one thing neither has: the DAG lives in the filesystem instead of
the prompt, the raw trace is periodically compiled into structured world-model
documents by an induction pass, and that pass -- not the act turns -- is where the
current approach itself gets re-evaluated.

The compiled documents double as the index over the non-text memory: every entry cites
the Q ids and [FRAME] paths it rests on, which is what makes a store of pixels
addressable from text.
"""
