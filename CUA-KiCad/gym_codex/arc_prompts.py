"""arc-code's method and brief for the KiCad GUI episode.

`mfm/arc/prompt.py` holds upstream PROMPT.md re-nouned for MCU (milestones, ticks,
inventory). Upstream's file names no environment and travels between games; the brief
above it is the benchmark's, and re-nouning it is the adapter's job (see
`mfm/arc/__init__.py`: "the benchmark adapters own the brief -- what this environment
is and what `./act do` accepts -- and the log format"). This module is that file with
only its nouns moved from Minecraft to a desktop GUI, so the method under test is
upstream's and not a paraphrase of it; every substitution is listed at the bottom.

What is different about KiCad, and shows up in the method: there is one task rather
than a ladder of milestones, and no score moves until the episode ends, so `do` never
stops a batch early -- it plays the batch and gives back the screen it produced. The
budget is steps, one per batch.
"""
from __future__ import annotations

from gym_codex.actions import ACTION_REFERENCE, MAX_BATCH

#: PROMPT.md, adapted for the GUI episode. `{brief_file}` is the file the session reads
#: first (AGENTS.md for codex, CLAUDE.md for Claude Code); the brief itself precedes it.
METHOD = """\
The brief above says what this environment is. Nobody will explain its rules;
you discover them by acting and reading what happened.

Finish the task: that is what you are here for. Spend as few steps as you can
along the way, but treat that as a distant second -- a task you never finish scores
nothing, while running well past a sensible step count on one you *do* finish costs
only a little. When the two pull against each other, finish the task.

## Acting

`./act do` plays a batch of actions in order and gives you back the screen they
produced -- one batch is one step, whether it holds one action or {max_batch}. Nothing
tells you a batch worked; the next screenshot is the only evidence. Pass `--plan "..."`
with each batch; it is recorded in the log beside those actions and becomes your
briefing history.

Every batch counts against the budget. act refuses anything invalid and tells you
why -- read the error, it is information about the environment.

## Memory

`logs.txt` holds the whole episode: a section per step with your plan, the actions,
and the screen they produced. It is written for you, verbatim, and it is the only
complete record -- your context is not. Its section format is documented in the brief
above; read the first sections before anything else.

**Read it with code, not with your eyes.** Use grep, sed and Python on the states it
records: a long log taken in by eye from your context comes with transcription
errors, and those send you chasing phantoms. Diffing two states to see exactly what
changed is the single most useful thing you can do.

Never print the log whole into your own context. The log grows to thousands of lines,
and a section you have read by eye is a section you may have read wrong. Orient with
`wc -l`, then `grep -n` for the headers you want and `sed -n 'a,bp'` for the range you
need; pipe sections into a script and print the conclusion, not the sections.

Each section names the frame it produced (`[SCREEN] frames/step_N.png`); `./act view`
prints the current one. This environment is a screen: the frame is the ground truth
and the log's [FEEDBACK] and [ACTIONS] lines are what the runner made of it, so open
the frame with your image tool whenever the question is what is actually in front of
you. Crop it when the label is small -- a 1920x1080 frame at a normalized coordinate
[cx, cy] has that point at pixel (cx*1.92, cy*1.08).

Keep durable findings in `notes.md`: confirmed mechanics, dialogs and shortcuts that
worked, hypotheses you have ruled out. Your context may compact; files survive.
Helper scripts you write are worth keeping too -- a parser over the log or a planner
you can re-run beats re-deriving it.

## Playing well

- Guess how something works, then spend **1-2 actions** checking the guess and
  diff what changed. Once you have a mechanic nailed down, send a full batch in one
  call rather than paying for a round trip each.
- Break what you see into distinct objects -- position, appearance, size and
  behaviour are the evidence -- and give each one a role: the thing you steer, the
  things that block it, the thing that finishes the task, a counter, decoration.
- Expect hidden limits. A batch that was cut short says why in its [FEEDBACK]; a
  guard that refuses an action says what it saw.
- If a step of the task has cost several times what the steps before it did and you
  still cannot say what finishes it, your model is probably *wrong* rather than
  incomplete, and a wider search inside a wrong frame finds nothing. Say so in
  `notes.md` with what you have ruled out, then re-derive what the things in
  front of you *are*, as if you had just arrived.
- Shell and Python loops around `./act` are encouraged -- branch on a parsed
  state, repeat until something changes, search for a coordinate. You are not
  limited to fixed action lists.
- Before committing a long sequence, simulate it against your model of the
  rules and say what you expect; then check the log against that expectation.

Play until the task is done and saved and you have ended the episode, or `./act
status` reports the budget spent. Do not stop to ask questions -- there is nobody to
answer them.
"""

#: The environment half of the brief: what this is, what `./act` accepts, how the log
#: reads. The action reference is spliced in verbatim from `gym_codex/actions.py`, so
#: every arm of this benchmark describes one action space.
BRIEF = """\
You are operating a real Linux desktop through a GUI to complete a task. The desktop
is XFCE with KiCad installed; work inside KiCad's own editors (schematic editor etc.)
using its menus and keyboard shortcuts (e.g. 'a' to add a symbol, 'w' to wire, ctrl+s
to save). The evaluator checks real system state at the end -- it compares the saved
project's netlist against a reference -- so save the project before ending the
episode.

TASK: {task}

Step budget: {max_steps} batches. Nothing tells you whether the task is going well:
there is no score until the episode ends.

## `./act`, your only actuator

    ./act do ENTRY [ENTRY ...] [--plan "..."]   play the actions in order; one step
    ./act do --file batch.json [--plan "..."]   the same batch from a file
    ./act status                                step, budget, how the episode stands
    ./act view                                  the path of the current screenshot

An ENTRY is one action object, written as JSON: `{{"action": "click", "coordinate":
[500, 500]}}`. A batch is at most {max_batch} of them, and `--file` takes
`{{"actions": [ ... ]}}`. `do` blocks until the batch has played and then prints the
log section it produced, so a batch is one call.

{action_reference}

To END the episode, play the terminate entry as the only entry of a batch:

    ./act do '{{"terminate": {{"status": "success"}}}}'           # the task is complete
    ./act do '{{"terminate": {{"status": "failure", "reason": "..."}}}}'

An empty batch is read as terminate(success). Terminate as soon as the task is durably
done; every further step is budget, not progress.

## The log

`./logs.txt` gains one section per step, written by the runner:

    [TASK]     the task instruction, in the first section.
    [SCREEN]   frames/<file> -- the screenshot at the START of that step, on disk.
    [FEEDBACK] what the environment or the runner rejected since the previous step
               (an unknown action, a dropped coordinate, an env error).
    [ACTIONS]  the actions that were actually executed for that step, compactly.
    [PLAN]     the `--plan` text you passed with that batch.
    [NOTE]     something the runner recorded about a call.

## Rules that have cost episodes before

- Before typing into any app or field, verify in the CURRENT screenshot that the
  target window/field exists and is focused -- text typed blind goes to whatever is
  active and is lost.
- Never batch input in the same call that opens the app or dialog it targets; open,
  look, then act.
- After typing something long, check the screenshot that it appears complete before
  pressing enter.
- Save the project (ctrl+s, confirm any dialog) and verify the title bar no longer
  shows an unsaved marker before terminating.
- If the screen has not changed after the same action twice, the action is not doing
  what you think: open the frame, re-read the log, and change approach.
"""

#: What changed from `mfm/arc/prompt.py`'s METHOD (itself upstream's PROMPT.md), for
#: the record. The method's shape and order are untouched; only the environment's
#: nouns and the two facts that differ (no early stop, no milestone ladder) move.
SUBSTITUTIONS = (
    ("Verify every milestone", "Finish the task"),
    ("milestone / ticks", "task / steps"),
    ("`do` stops as soon as a milestone verifies, discarding the rest -- the state you "
     "planned against is gone",
     "`do` plays the batch and gives back the screen it produced (one batch is one "
     "step; nothing verifies mid-batch on this benchmark)"),
    ("Every tick counts against the budget", "Every batch counts against the budget"),
    ("a section per entry", "a section per step"),
    ("tens of thousands of lines", "thousands of lines"),
    ("[FRAME] frames/step_N.png", "[SCREEN] frames/step_N.png"),
    ("the [STATE], [INV] and [EVENT] lines are the ground truth, and they are what your "
     "scripts should parse",
     "the frame is the ground truth and the log's [FEEDBACK]/[ACTIONS] lines are what "
     "the runner made of it -- so open the frame (added: the crop arithmetic, which the "
     "other arms get from tools/zoom.py)"),
    ("confirmed mechanics, routes and recipes", "confirmed mechanics, dialogs and shortcuts"),
    ("1-2 entries / 10-20 entries in one batch",
     "1-2 actions / a full batch in one call (the parser caps a batch at 5)"),
    ("A procedure that stops early says why in its [NOTE]",
     "A batch that was cut short says why in its [FEEDBACK]"),
    ("If a milestone has cost several times what the milestones before it did",
     "If a step of the task has cost several times what the steps before it did"),
    ("Play until `./act status` reports every milestone verified or the budget spent",
     "Play until the task is done and saved and you have ended the episode, or the "
     "budget is spent (added: this benchmark needs an explicit terminate)"),
)


def build_brief(task: str, max_steps: int, brief_file: str) -> str:
    """The whole brief: what the environment is, then upstream's method."""
    head = BRIEF.format(task=task.strip(), max_steps=max_steps, max_batch=MAX_BATCH,
                        action_reference=ACTION_REFERENCE)
    return f"{head}\n\n# Method\n\n{METHOD.format(max_batch=MAX_BATCH)}"
