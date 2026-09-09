"""arc-code's prompt, ported. Upstream (PROMPT.md, 2026-08-12) names no environment and
travels unchanged between games; the brief above it is the benchmark's. The text below
is that file with only its ARC nouns replaced, so the method under test is upstream's
and not a paraphrase of it. Each substitution is listed at the bottom of this module.
"""
from __future__ import annotations

#: PROMPT.md, adapted. `{brief_file}` is the file the session is told to read first
#: (AGENTS.md for codex, CLAUDE.md for Claude Code); the brief itself precedes this.
METHOD = """\
The brief above says what this environment is. Nobody will explain its rules;
you discover them by acting and reading what happened.

Verify every milestone: that is what you are here for. Spend as few ticks as
you can along the way, but treat that as a distant second -- a milestone you never
reach scores nothing, while running well past a sensible tick count on one you *do*
reach costs only a little. When the two pull against each other, reach the milestone.

## Acting

`./act do` plays a batch of entries in order and **stops as soon as a milestone
verifies**, discarding the rest -- the state you planned against is gone. Pass
`--plan "..."` with each batch; it is recorded in the log beside those entries and
becomes your briefing history.

Every tick counts against the budget. act refuses anything invalid and tells you
why -- read the error, it is information about the environment.

## Memory

`logs.txt` holds the whole run: a section per entry with your plan, the entry, and
the state it produced. It is written for you, verbatim, and it is the only complete
record -- your context is not. Its section format is documented in the brief above;
read the first sections before anything else.

**Read it with code, not with your eyes.** Use grep, sed and Python on the states it
records: a long log taken in by eye from your context comes with transcription
errors, and those send you chasing phantoms. Diffing two states to see exactly what
changed is the single most useful thing you can do.

Never print the log whole into your own context. The log grows to tens of thousands
of lines, and a section you have read by eye is a section you may have read wrong.
Orient with `wc -l`, then `grep -n` for the headers you want and `sed -n 'a,bp'` for
the range you need; pipe sections into a script and print the conclusion, not the
sections.

Each section names the frame it produced (`[FRAME] frames/step_N.png`); `./act view`
prints the current one. View a frame with your image tool when the numbers cannot
tell you what is in front of you; the [STATE], [INV] and [EVENT] lines are the ground
truth, and they are what your scripts should parse.

Keep durable findings in `notes.md`: confirmed mechanics, routes and recipes that
worked, hypotheses you have ruled out. Your context may compact; files survive.
Helper scripts you write are worth keeping too -- a parser over the log or a planner
you can re-run beats re-deriving it.

## Playing well

- Guess how something works, then spend **1-2 entries** checking the guess and
  diff what changed. Once you have a mechanic nailed down, send **10-20 entries**
  in one batch rather than paying for a round trip each.
- Break what you see into distinct objects -- position, appearance, size and
  behaviour are the evidence -- and give each one a role: the thing you steer, the
  things that block it, the thing that reaches the milestone, a counter, decoration.
- Expect hidden limits. A procedure that stops early says why in its [NOTE]; a
  guard that refuses an entry says what it saw.
- If a milestone has cost several times what the milestones before it did and you
  still cannot say what reaches it, your model is probably *wrong* rather than
  incomplete, and a wider search inside a wrong frame finds nothing. Say so in
  `notes.md` with what you have ruled out, then re-derive what the things in
  front of you *are*, as if you had just arrived.
- Shell and Python loops around `./act` are encouraged -- branch on a parsed
  state, repeat until something changes, search for a coordinate. You are not
  limited to fixed entry lists.
- Before committing a long sequence, simulate it against your model of the
  rules and say what you expect; then check the log against that expectation.

Play until `./act status` reports every milestone verified or the budget spent. Do
not stop to ask questions -- there is nobody to answer them.
"""

#: run.py's TASK and RESUME_TASK, with the brief's filename substituted.
TASK = ("Read {brief_file}, then play with ./act until `./act status` reports every "
        "milestone verified or the budget spent. Work autonomously and do not stop to "
        "ask questions.")
RESUME_TASK = ("A previous session playing this episode was interrupted. Its workspace is "
               "yours: read {brief_file}, then recover what it had established from "
               "notes.md and logs.txt before acting. Continue with ./act until `./act "
               "status` reports every milestone verified or the budget spent. Work "
               "autonomously and do not stop to ask questions.")

#: What changed from upstream's PROMPT.md, for the record.
SUBSTITUTIONS = (
    ("Clear every level", "Verify every milestone"),
    ("actions", "entries / ticks (an entry spends the ticks it takes)"),
    ("a level you never clear scores nothing and ends the run there",
     "a milestone you never reach scores nothing (the episode runs to its budget)"),
    ("stops as soon as one changes the score -- a score increase means a level was cleared",
     "stops as soon as a milestone verifies"),
    ("Every action counts against the budget, including RESET.",
     "Every tick counts against the budget. (there is no RESET)"),
    ("an entry per action with your plan, the action, and the state it produced",
     "a section per entry with your plan, the entry, and the state it produced"),
    ("Its format and legend are documented in its opening lines",
     "Its section format is documented in the brief above"),
    ("a large grid taken in by eye", "a long log taken in by eye"),
    ("hundreds of thousands of lines / a grid", "tens of thousands of lines / a section"),
    ("(added) the frame paragraph: sections name a PNG, `./act view`, the image tool",
     "upstream's boards are text inside the log; here the view is an image beside it"),
    ("confirmed mechanics, level solutions", "confirmed mechanics, routes and recipes that worked"),
    ("a parser or a simulator", "a parser over the log or a planner"),
    ("1-2 actions / 10-20 actions", "1-2 entries / 10-20 entries"),
    ("Break the state into distinct objects", "Break what you see into distinct objects"),
    ("the thing that ends the level", "the thing that reaches the milestone"),
    ("Many environments reset a level once too many steps have gone by.",
     "A procedure that stops early says why in its [NOTE]; a guard that refuses an entry says what it saw."),
    ("If a level has cost several times what the levels before it did", "If a milestone has cost ..."),
    ("fixed action lists", "fixed entry lists"),
    ("Play until `./act status` reports you have won or the budget is spent",
     "Play until `./act status` reports every milestone verified or the budget spent"),
)
