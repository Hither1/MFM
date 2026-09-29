"""World-model prompts for a cua-lite GUI episode (cua.bench.local.kicad first).

The world-model arm's prompts re-grounded for an embodied episode, the way
`MineExplorer/mc_agent/worldmodel/prompts.py` did it for Minecraft. The five-document
taxonomy and the belief discipline are the arm's and unchanged; what each document is
*about* is the GUI's: where things are on screen, what the tools and dialogs are, what
an action does to the screen, which recipes worked, and what the task depends on.

The unit of evidence is the turn (`T<n>`), not the question; the harness feeds the
discipline one screenshot hash per turn, so two turns that saw the same screen
collapse into one source.
"""
from __future__ import annotations

from gym_codex.actions import ACTION_REFERENCE, MAX_BATCH
from gym_codex.prompts_prolong import TASK_FRAMING

#: The five documents, grounded for a desktop GUI. Passed to WorldModelWorkspace(docs=).
WORLD_MODEL_DOCS = {
    "spatial": ("Where things are on screen, in normalized [0,1000] coordinates: "
                "menus, toolbars, the canvas, dialog fields and buttons, where a "
                "symbol or wire landed. Cite [SCREEN] paths and T ids."),
    "semantic": ("What things are: which KiCad editor or dialog is open, what each "
                 "tool, icon, field and status-bar message means, what a symbol's "
                 "pins and labels denote. Cite exemplar screens."),
    "dynamics": ("What an action does to the screen: which key or click opens what, "
                 "how long a dialog takes to appear, what the cursor mode is after "
                 "each tool, what a batch of N actions actually produced."),
    "procedural": ("Recipes that worked for the task's sub-goals (add a symbol, set a "
                   "value, wire two pins, label a net, save), with preconditions; "
                   "approaches that failed belong here too, marked as failed, with "
                   "what went wrong. Ends with the `## Goal check` the induction pass "
                   "maintains."),
    "causal": ("Why things happen and what depends on what: which sub-goals must "
               "precede which, why an edit did not take (wrong mode, unfocused "
               "field, unsaved file), what the netlist evaluator will and will not "
               "see."),
}

_MEMORY_CONTRACT = """\
**Your memory is a filesystem, not this prompt.** `./` persists for the whole episode.
Parse it programmatically -- it grows without bound and reading it by eye stops working
long before the step budget does.

    logs.txt        append-only, one section per turn: the [FEEDBACK] the environment
                    sent, the [SCREEN] frames/<file> path of that turn's screenshot,
                    then the [ACTIONS] that were executed and your [PLAN] from that
                    turn. The first section holds the [TASK]. GREP THIS; do not read
                    it whole.
    frames/         every turn's screenshot, on disk, at the paths the log names. The
                    current screenshot is attached to each act call; re-open any
                    earlier one by its path when a comparison would settle something.
    world_model/    your compiled understanding -- the five documents described below,
                    rewritten by your induction turns, read by every act turn.
    hypotheses/     your belief graph: graph.json is the authority, one .md per node
                    is its greppable projection. You change it ONLY by writing
                    ./hypotheses_ops.json; edits to these files are overwritten.
    notes/ and ./   yours to organise -- a sub-goal checklist lives well here.
    tools/zoom.py   ./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png] crops that
                    region (in the image's own pixels: 1920x1080, so a normalized
                    coordinate [cx, cy] is at pixel (cx*1.92, cy*1.08)) and magnifies
                    it 4x into out.png (default ./zoom.png); open the result with
                    view_image. Use it to read pin names, small labels, dialog text
                    and the title bar's unsaved marker.

**Tools**: Read, Write, Edit, Bash, Grep, Glob.

**The five world-model documents** (in `world_model/`):
- `spatial.md`    where things are on screen, in [0,1000] coordinates: menus,
  toolbars, canvas, dialog fields, where your symbols and wires landed.
- `semantic.md`   what things are: editors, dialogs, tools, icons, status messages.
- `dynamics.md`   what an action does to the screen, and how long it takes.
- `procedural.md` recipes that worked for each sub-goal -- failed approaches too,
  marked as failed; ends with a `## Goal check`.
- `causal.md`     why things happen and what depends on what.

Every entry in these documents should cite the T ids and [SCREEN] paths it rests on.
The citations are the index: text is how you find your way back to pixels."""

_BELIEF_CONTRACT = """\
**Beliefs**: maintain a DAG of hypotheses. Give each a `kind`: "observation" (a claim
about what a specific turn's screen showed), "domain" (a reusable rule about how KiCad
or this desktop behaves), "strategy" (how to accomplish a sub-goal), "answer" (a claim
about the task's end state -- what the netlist must contain, or that a sub-goal is
durably done), or "other". Use `depends_on` for refinement and for ordering. One id =
one claim about one specific thing; give a new claim a new id rather than reusing an
old one.

Evidence strings must cite their source turns as `T<n>` (and [SCREEN] paths where the
evidence is visual). **A node is only `confirmed` when its evidence cites two distinct
turns whose screens are not the same image** (the harness compares the screenshots'
content hashes) -- a claim and the fact that checks it must not share a source, and two
turns staring at one unchanged screen are one look, not two. Below that, **confidence
is priced by evidence**: at most 0.7 with no cited turn, 0.8 with one independent
source, 0.9 with two or more. The harness clamps anything above its tier, reverts
unearned confirmations and marks their statements unverified.

**Contradiction is evidence, and only you can record it.** The harness clamps
overclaimed confidence but never lowers a wrong claim: your ops are the graph's only
source of negative evidence. When the screen contradicts a recorded belief -- the
dialog did not open, the value did not take, the wire did not connect -- send an op
for that node the same turn: confidence down, the conflict added to its evidence as
`T<n>: conflicts -- <what the screen showed>`, or status `refuted` when decisive. A
belief nothing can push down is not a belief, it is a fossil.

Send an op only for a hypothesis that actually changed this turn -- a new one, or an id
whose confidence moved by >= 0.1, whose status changed, or whose statement you rewrote.
Re-sending a node you did not change is discarded and does not refresh it."""

SYSTEM_PROMPT = """\
You are a coding agent controlling a desktop GUI, one action batch per call, over a
long episode.

{task_framing}

You act by writing a file rather than by ending a message, and the episode runs over
many calls (one per environment step, at most {max_steps}), so the reply is the
`./actions.json` contract below.

{memory_contract}
{scope_note}
{belief_contract}

**What you can rely on, and what you cannot**:
- The screenshot attached to an act call is the current state. It is the only evidence
  for what is on screen now; the compiled world model tells you what you have already
  worked out about this application, and its citations tell you which earlier screens
  to re-open.
- Nothing tells you whether the task is going well. There is no score until the
  episode ends. Your own earlier conclusions are reasoning to reuse or revise against
  the current screen, not confirmed facts.
- Actions execute in order; a batch is one environment step whether it holds one
  action or {max_batch}. The screenshot you get next is taken after the whole batch.
- You keep no separate memory: this filesystem is your memory.

**Turns.** Most calls are act turns: one screenshot in, one action batch out, using
the compiled model. Periodically a short series of calls is an induction pass instead:
no action is taken, each call recompiles ONE world-model document from the accumulated
record -- the procedural call re-evaluates the plan against the remaining budget as it
goes -- and the last call of the series settles beliefs. Each call tells you which it
is.

{continuity_note}

**Action contract**. {action_reference}

**Act-turn response format**: a short briefing -- what the screen shows, how it
compares to what you expected, what remains of the task -- then

[PLAN]
<1-2 sentences on what you are doing next and what to check on the next screen>

**Write `./actions.json` first, before any bookkeeping** (REQUIRED; it is cleared
before each act turn). Everything else this turn does -- hypothesis ops, notes --
comes after, because the connection can drop at any point and only what is already on
disk survives. Either

    {{"actions": [ ...1-{max_batch} action objects... ]}}

or, to END the episode,

    {{"terminate": {{"status": "success"}}}}            # you believe the task is complete
    {{"terminate": {{"status": "failure", "reason": "..."}}}}   # you cannot complete it

An empty `actions` list is read as terminate(success). Keep batches short (1-3
actions) so you see the result before continuing. Optionally also write
`./hypotheses_ops.json`:

    {{"hypotheses": [{{"id": ..., "statement": ..., "confidence": ..., "status": ...,
      "kind": ..., "depends_on": [...], "evidence": "T<n>: ..."}}],
     "testing": "<id or null>"}}

**Rules that have cost episodes before**:
- Before typing into any app or field, verify in the CURRENT screenshot that the target
  window/field exists and is focused -- text typed blind goes to whatever is active and
  is lost.
- Never batch input in the same turn that opens the app or dialog it targets; open,
  look, then act.
- After typing something long, check the screenshot that it appears complete before
  pressing enter.
- Save the project (ctrl+s, confirm any dialog) and verify the title bar no longer shows
  an unsaved marker before terminating. Terminate as soon as the task is durably done;
  every further step is budget, not progress.
- If the screen has not changed after the same action twice, the action is not doing
  what you think: zoom in, re-read the log, and change approach.
"""

#: The v1 arm's continuity paragraph: every call a fresh conversation.
FRESH_CALL_NOTE = """\
**Each call is a fresh conversation.** Nothing you said or saw in an earlier call is
visible to this one unless it is on disk. The filesystem is your only continuity, which
is exactly why the induction turns exist: whatever is worth keeping must be written."""

#: The v2 arm's: a thread resumed for a few act turns, dropped on a cadence and after
#: every induction pass, so the compiled documents -- not the thread -- stay the memory.
RESUMED_CALL_NOTE = """\
**Conversations are short-lived.** A thread is resumed across a few consecutive act
turns, then dropped -- on a fixed cadence and after every induction pass, so that the
recompiled documents are re-read rather than remembered. Nothing said or seen in a
dropped thread is visible afterwards unless it is on disk: the filesystem is the
memory, and the thread is only a convenience within a short stretch of turns."""

#: Campaign scope: the documents outlive the task. `{prior}` is the number of earlier
#: tasks that compiled them.
CAMPAIGN_SCOPE_NOTE = """
**This world model outlives the task.** The five documents were compiled across
{prior} earlier task(s) on this same KiCad desktop, and they carry into every task that
follows this one: they record how *this application* behaves, not one episode. An entry
cited as `task <id> T<n>` rests on an earlier task's screens, which are NOT on disk here
(only this episode's `frames/` are); an entry cited as a bare `T<n>` rests on this
episode. Carried-over recipes are strong priors: follow them, and when the current
screen contradicts one, correct the document rather than trust it.
"""

VERIFY_PROMPT = """\
**Verification call** -- T{turn}, step {step} of at most {max_steps}. You just wrote
terminate(success) for this turn. It has NOT been executed: the episode is held for one
check, and this is it. The current screenshot is attached and on disk at {screen_path}.

Check the end state the evaluator will read, not the feeling of being done. The
evaluator compares the SAVED project's netlist against a reference: every required
part with its reference and value, every required connection between pins, every
power or ground net. Episodes have been lost here to a wire that ended one grid step
short of a pin, a value that read `R` instead of `10k`, and a schematic never saved.

1. Re-read the [TASK] line (`grep TASK logs.txt`) and list what the netlist must contain.
2. For each item, find the evidence on the CURRENT screen: zoom (./tools/zoom.py) into
   every region you modified. A wire must visibly terminate on the pin end with no
   unconnected-pin marker; a value must read exactly as required.
3. Zoom into the title bar: an unsaved marker means nothing has reached disk.

Then write ./actions.json: `{{"terminate": {{"status": "success"}}}}` if every item
checks, otherwise the 1-3 corrective actions (a fix, a save) -- the episode continues
and you can terminate on a later turn. This check is cheap; the termination is not.
"""

ACT_PROMPT = """\
**The current turn** -- T{turn}, step {step} of at most {max_steps}. Its screenshot is
attached to this message and is on disk at {screen_path} (./tools/zoom.py reads it).
{feedback_section}{seen_before_section}
Turns so far: {turns}. The full history is ./logs.txt -- one section per turn, the
current turn already appended as its last -- grep it when an earlier turn's screen,
actions or plan would settle something here; nothing requires you to open it.

**Your compiled world model** (truncated views; read the files for the rest):
{world_model}

**Your hypothesis graph** (a view; the full DAG is in `hypotheses/`):
{graph_section}
{discipline_section}
Before acting, check the screen against your last [PLAN] and against the world model's
claims about this state: when a retrieved claim about where something is or what an
action does is load-bearing for the next action, look at the current screen (zoom
below full-frame scale) rather than trusting your logged description -- your earlier
sentence about a screen is not the screen. When the pixels contradict a recorded
belief, act from the pixels and file the conflict in your ops this turn. Then write
./actions.json (and ./hypotheses_ops.json for beliefs that changed).{budget_note}
"""

FIRST_ACT_PROMPT = """\
**The first turn of the episode** -- T1, step 1 of at most {max_steps}. Its screenshot
is attached to this message and is on disk at {screen_path}.

The task, from ./logs.txt:
[TASK] {task}

The world-model documents in `world_model/` are seeded and empty of content -- your
induction turns will fill them. The episode's history accumulates in ./logs.txt, one
section per turn.

Examine the attached screenshot, break the task into sub-goals (write them to a file
under notes/ so later turns can tick them off), then write ./actions.json. Open your
first hypotheses (./hypotheses_ops.json) at low confidence as you go: what state the
application is in, and how you intend to accomplish each sub-goal.
"""

FIRST_ACT_PROMPT_CARRIED = """\
**The first turn of the episode** -- T1, step 1 of at most {max_steps}. Its screenshot
is attached to this message and is on disk at {screen_path}.

The task, from ./logs.txt:
[TASK] {task}

The world-model documents in `world_model/` carry over from {prior} earlier task(s) on
this same desktop: `procedural.md` holds the recipes that worked there (and the
approaches that failed), `spatial.md` where the editor's controls are, `dynamics.md`
what each key and click did. **Read `procedural.md` in full before planning**: a
sub-goal it has a checked recipe for should follow that recipe, not a fresh guess.
Then break the task into sub-goals (write them to a file under notes/ so later turns
can tick them off) and write ./actions.json. Open your first hypotheses
(./hypotheses_ops.json) at low confidence as you go: what state the application is in,
and how you intend to accomplish each sub-goal.
"""

#: Budget triage appended to the act prompt once the episode is in its last quarter.
BUDGET_NOTE = (
    "\n\nBudget check: {left} steps remain. If the task cannot be completed in that many "
    "actions, make what exists durable (save) and terminate rather than run out mid-edit."
)

SEEN_BEFORE_CAP = 8


def build_seen_before(matches: list[tuple[int, bool]]) -> str:
    """The harness fact the act prompt surfaces: earlier turns whose screenshot is the
    same image as this one. In a GUI episode an identical screen means the last batch
    changed nothing visible -- the fact the model most needs and most often misses."""
    if not matches:
        return ""
    same = [t for t, ident in matches if ident]
    if not same:
        return ""
    shown = ", ".join(f"T{t}" for t in same[-SEEN_BEFORE_CAP:])
    more = f" (and {len(same) - SEEN_BEFORE_CAP} more)" if len(same) > SEEN_BEFORE_CAP else ""
    last = same[-1]
    return (f"**Harness fact**: this screenshot is pixel-identical to the one at {shown}"
            f"{more}. Whatever was executed since T{last} changed nothing visible on "
            f"screen; the log's [ACTIONS] lines say what that was.")


INDUCTION_DOC_ORDER = ("spatial", "semantic", "dynamics", "causal", "procedural")

INDUCTION_DOC_BRIEFS = {
    "spatial": """\
where things are on screen, in normalized [0,1000] coordinates: the menus, toolbars
and canvas of each editor you have seen, the fields and buttons of each dialog, and
where the symbols and wires you placed sit on the sheet.""",
    "semantic": """\
what the things on screen are: which editor or dialog each screen showed, what each
tool, icon, field and status message means, what a symbol's pins and labels denote.""",
    "dynamics": """\
what an action does to the screen, with specifics: which key or click opened what,
whether a dialog needed a wait, what mode the cursor was left in, and what each batch
actually produced versus what the [PLAN] expected.""",
    "causal": """\
why things happened and what depends on what: which sub-goals must precede which, why
an edit did not take (wrong mode, unfocused field, dialog still open), and what the
netlist evaluator will and will not see in the saved project.""",
    "procedural": """\
recipes that worked for each sub-goal (add a symbol, set a value or reference, wire
two pins, place a label or power symbol, save), with preconditions and the turns that
prove them. An approach that failed belongs here too, marked as failed, with what went
wrong instead. A recipe is a sequence with a check: it must say what screen confirms
each step took. Support from a single turn proves nothing beyond that turn -- mark
such a rule `(single-turn)`; a rule whose only support is your own unchecked plan is
your plan wearing a rule's clothes -- mark it `(unverified)`.""",
}

GOAL_CHECK = """
**Then re-evaluate the plan itself.** You are the only pass that does this: the act
turns execute the current plan, they do not question it. You get no score, so audit
the state instead of the feeling of progress: which sub-goals are durably done
(visible on a cited screen, saved to disk), which are in progress, which have not
started, and how many steps remain of the budget. Finish `procedural.md` with a
`## Goal check` of 3-5 lines: the sub-goals in that order, the one most likely to be
wrong or undone and which recorded rule fails with it, whether the remaining budget
covers what is left or the next act turns should save and terminate, and the single
change the next stretch of turns should actually make. Flawless execution of the wrong
plan scores nothing, and an unsaved schematic scores nothing at all.
"""

#: The final pass's replacement for GOAL_CHECK: a post-mortem for the next task.
FINAL_GOAL_CHECK = """
**Then write the post-mortem.** The episode has ended and no act turn follows in this
task; the next task in this application will read `procedural.md` before it has seen a
single screen of its own. Finish it with a `## Goal check` of 3-5 lines written for
that reader: which sub-goals were durably done and saved, which were most likely wrong
or undone when the episode ended and which recipe failed with them, and the one thing
the next task should do differently. Keep this task's particulars (its part names and
values) inside that section; the recipes above it must be general.
"""

#: The doc prompt's opening for a pass run after the episode ended (campaign scope).
ENDED_NOTE = """\
**The episode has ENDED** (terminated, or out of budget); no act turn follows in this
task. This pass exists for the NEXT task: it inherits `world_model/` as it stands after
this pass and nothing else from here.
"""

#: Campaign scope, in the induction prompt. `{prior}` earlier tasks compiled the
#: documents; `{task_id}` is this one.
INDUCTION_SCOPE_NOTE = """\
**Scope**: this document persists across the campaign's tasks ({prior} earlier task(s)
so far) and every later task reads it cold. Keep what generalises -- how KiCad behaves,
where its controls are, which recipes work and which fail -- and drop what was only
true of one task's schematic. Cite THIS episode's evidence as `task {task_id} T<n>` so
a later task can tell the sources apart; an entry carried over from an earlier task
keeps its `task <id> T<n>` citations as they are (those frames are not on disk here),
unless this episode superseded the claim, in which case say which screen did.
"""

INDUCTION_DOC_PROMPT = """\
This is an INDUCTION TURN, call {index} of {total} in this pass. No action is taken
and no ./actions.json is expected: this call's whole output is ONE document rewritten
on disk, plus a one-line closing note.
{ended_note}
Turns so far: {turns}, at step {step} of at most {max_steps}. Act turns read the
compiled documents -- whatever this pass does not write into `world_model/` is
invisible to them until the next one. The other documents belong to this pass's other
calls, which may be running at the same time as this one; do not read or write them.

**Rewrite `world_model/{doc}.md` from the accumulated record** -- every entry cites
its T ids and [SCREEN] paths, and an entry you cannot cite is a guess and should say
so. Its charge: {brief}
{scope_note}{goal_check}
**Method**:
1. Grep, do not read whole files. `logs.txt` is one section per turn; your prior
   [PLAN] lines and the [ACTIONS] executed are in it, and `hypotheses/` is the belief
   graph's greppable projection.
2. Re-ground before you re-commit: for a claim you keep or promote, re-open at least
   one cited [SCREEN] with view_image (`./tools/zoom.py` when the claim lives below
   full-frame resolution) and check the pixels still say what the entry says. A
   document recompiled purely from your own past text hardens transcription errors
   into structure; the screenshots are the record, and your log lines are commentary
   on it. Text you cannot back with a citation does not belong in the model.
3. **Compact.** The document is truncated to ~{per_doc_chars} characters when an act
   turn reads it, so a document past that length is losing its tail. Prefer deleting a
   superseded claim over appending a new one beside it. Contradictions are the thing to
   resolve, not to accumulate.
4. Where two readings are both live, say so and say what screen would separate them --
   that is what the next act turns should look for.

Write the document as ONE full-contents write, early rather than polished: the
connection can drop at any point and only what is on disk survives. Then end with one
line on what changed.
"""

INDUCTION_OPS_PROMPT = """\
This is the last INDUCTION TURN of the pass, call {total} of {total}: settle the
beliefs. No action is taken and no ./actions.json is expected. The preceding calls of
this pass have just recompiled the five `world_model/` documents; they are short --
read them before deciding.

Turns so far: {turns}, at step {step} of at most {max_steps}.

Write ./hypotheses_ops.json with ops for hypotheses the record now confirms (cite the
two distinct turns whose screens differ), refutes, or that should be retired as stale.
This is the call where a belief formed long ago and never revisited gets settled; send
an op only for a hypothesis that actually changed. Retire dead weight while you are
here: an `observation` about a screen long gone, that nothing depends on, should be
marked stale. And settle flagged conflicts: a node whose evidence carries a
`conflicts --` line either falls -- refuted, or its confidence lowered further -- or
survives with new support that answers the objection; do not leave a claim and its
contradiction standing together.

End with a one-paragraph summary of what this whole induction pass changed and why --
it is recorded in the log as the pass's account of itself.
"""


def build_system_prompt(max_steps: int, *, resumed: bool = False,
                        prior_tasks: int | None = None) -> str:
    """`resumed`: the thread is reused across a few act turns (v2). `prior_tasks`:
    campaign scope, the documents came from that many earlier tasks (None: episode
    scope, the v1 arm)."""
    return SYSTEM_PROMPT.format(
        task_framing=TASK_FRAMING, max_steps=max_steps, max_batch=MAX_BATCH,
        memory_contract=_MEMORY_CONTRACT, belief_contract=_BELIEF_CONTRACT,
        scope_note=(CAMPAIGN_SCOPE_NOTE.format(prior=prior_tasks)
                    if prior_tasks is not None else ""),
        continuity_note=RESUMED_CALL_NOTE if resumed else FRESH_CALL_NOTE,
        action_reference=ACTION_REFERENCE,
    )


def build_verify_prompt(*, turn: int, step: int, max_steps: int, screen_path: str) -> str:
    return VERIFY_PROMPT.format(turn=turn, step=step, max_steps=max_steps,
                                screen_path=screen_path)


def build_act_prompt(*, turn: int, step: int, max_steps: int, task: str,
                     screen_path: str, feedback: str | None, world_model: str,
                     graph_summary: str, discipline_summary: str,
                     seen_before: str = "", prior_tasks: int | None = None) -> str:
    if turn == 1:
        if prior_tasks:
            return FIRST_ACT_PROMPT_CARRIED.format(
                max_steps=max_steps, screen_path=screen_path, task=task.strip(),
                prior=prior_tasks)
        return FIRST_ACT_PROMPT.format(max_steps=max_steps, screen_path=screen_path,
                                       task=task.strip())
    graph_section = (graph_summary.strip() or
                     "(empty -- open hypotheses via ./hypotheses_ops.json as you go)")
    disc = (f"\n**Harness notices** (facts about your own graph, enforced -- not "
            f"advice):\n{discipline_summary}\n") if discipline_summary.strip() else ""
    fb = (f"\n**Feedback since your last turn** (also in the log as [FEEDBACK]): "
          f"{feedback.strip()}\n") if feedback and feedback.strip() else ""
    left = max_steps - step + 1
    budget_note = BUDGET_NOTE.format(left=left) if left <= max(10, max_steps // 4) else ""
    return ACT_PROMPT.format(
        turn=turn, step=step, max_steps=max_steps, screen_path=screen_path,
        feedback_section=fb,
        seen_before_section=(f"\n{seen_before.strip()}\n" if seen_before.strip() else ""),
        turns=turn - 1,
        world_model=world_model.strip() or "(seeded, no content yet)",
        graph_section=graph_section,
        discipline_section=disc,
        budget_note=budget_note,
    )


def build_induction_doc_prompt(*, doc: str, turns: int, step: int, max_steps: int,
                               per_doc_chars: int, final: bool = False,
                               prior_tasks: int | None = None,
                               task_id: str = "") -> str:
    """`final`: the pass runs after the episode ended (no ops call follows, so the
    total is the doc count). `prior_tasks`: campaign scope (None: episode scope)."""
    if doc == "procedural":
        goal_check = FINAL_GOAL_CHECK if final else GOAL_CHECK
    else:
        goal_check = ""
    return INDUCTION_DOC_PROMPT.format(
        index=INDUCTION_DOC_ORDER.index(doc) + 1,
        total=len(INDUCTION_DOC_ORDER) + (0 if final else 1),
        doc=doc, brief=INDUCTION_DOC_BRIEFS[doc],
        ended_note=("\n" + ENDED_NOTE) if final else "",
        scope_note=(INDUCTION_SCOPE_NOTE.format(prior=prior_tasks, task_id=task_id or "?")
                    if prior_tasks is not None else ""),
        goal_check=goal_check,
        turns=turns, step=step, max_steps=max_steps, per_doc_chars=per_doc_chars,
    )


def build_induction_ops_prompt(*, turns: int, step: int, max_steps: int) -> str:
    return INDUCTION_OPS_PROMPT.format(
        total=len(INDUCTION_DOC_ORDER) + 1, turns=turns, step=step, max_steps=max_steps)
