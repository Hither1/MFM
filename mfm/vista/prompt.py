"""The player instructions, as upstream wrote them.

Upstream's whole prompt is nine lines (`codex/prompt.md`): the task, the objective,
and three sentences of method -- a revisable model, a prediction before every play and
a reading after it, GUIDE.md and WORKING.md. That brevity is part of the method; the
benchmarks add only what the environment is (the action vocabulary, the facts every arm
is handed) and never a memory practice of their own.

`PLAYER_BASE_INSTRUCTIONS` replaces codex's own system prompt (`baseInstructions` on
the thread); the benchmark's prompt is the developer instructions.
"""

PLAYER_BASE_INSTRUCTIONS = "You are a visual game player.\n"

MODEL_LINE = ("Build and use a compact, revisable model of the {world} and its current "
              "state. Update it as new evidence changes what is supported.")
PREDICT_LINE = ("Before each `play`, briefly state what you expect to see. Afterward, "
                "briefly state all visible changes, expected or not.")
NOTES_LINE = ("Keep concise, durable, revisable {understanding} in `GUIDE.md`; use "
              "`WORKING.md` as a scratchpad when useful.")

#: What the tools are, in the words upstream's README uses for them.
TOOLS_LINE = (
    "Tools: use `play` to execute one {action}; use `inspect` to revisit archived "
    "visual frames and regions; use `read_pixels` to sample exact colors from selected "
    "image regions; use `history` to revisit prior actions and environment results; "
    "use `GUIDE.md` and `WORKING.md` (`read_guide` / `write_guide`, `read_working` / "
    "`write_working`) for persistent and working memory. There is no shell and no "
    "filesystem: the conversation, the archived frames and the two notes files are your "
    "memory, and when the context fills you will be asked to save a checkpoint and "
    "continue in a fresh conversation from it.")


def method_lines(*, world: str, understanding: str, action: str) -> str:
    return "\n\n".join([MODEL_LINE.format(world=world), PREDICT_LINE,
                        NOTES_LINE.format(understanding=understanding),
                        TOOLS_LINE.format(action=action)])
