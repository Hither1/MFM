"""The paragraphs the MFM arm appends to PRO-LONG's system prompt.

Kept out of `prompts_prolong.py` so the baseline arm's prompt hash does not move;
appended by `MemoryAgent.full_system_prompt` when the episode store is on.
"""

MFM_MEMORY_NOTE = """\
`episodes/` holds the same history as `logs.txt`, one directory per turn: \
`state/state.json` (step, screenshot hash, the feedback the turn received), \
`action.json` (the batch executed and the plan text), `outcome.json` (the feedback and \
whether the screen changed after it, tags) and `observation/image.png` (the 1920x1080 \
screenshot the batch was decided on, the same file the `[SCREEN]` line names). \
`./tools/episodes.py --last 5 | --steps A B | --tag feedback | --tag screen_unchanged | \
--grep text` lists matching episodes one per line with their paths; `--sheet out.png` \
tiles their screenshots. Use it instead of parsing the log by hand when the question \
is "have I seen this screen / tried this before"."""

PLAN_QUEUE_NOTE = """\
You may plan several batches in one turn: write `./actions.json` as \
`{"plan": [batch, batch, ...]}` where each `batch` is the usual `{"actions": [...]}` \
object (or a `terminate`), at most {plan_cap} batches. The batches execute one per \
step without calling you again, each logged as its own turn section (`Plan Step i/T` \
in the header). The rest of the plan is dropped and you are called at once when the \
environment reports an error for a batch, when the screen did not change after a batch \
that clicked, typed or pressed keys, or when a queued `terminate` comes up: a terminate \
is only executed when you decided it on the screen you are looking at. A plain \
`{"actions": [...]}` is still accepted as a one-batch plan."""

RECALL_NOTE = """\
Each episode's index row also records what you said you saw (`perception`), meant \
(`intent`) and what the next turn said the action did (`effect`), with a perceptual \
hash of its frame. When the situation and action of your last turn happened before, \
the turn prompt carries a `[RECALL]` block: the earlier turn(s) with the same \
perception and action, what followed, and the step after that. It is your own history \
retrieved for this moment; if the chain matches what you intend, queue its steps as \
one plan."""


NETLIST_NOTE = """\
`./netlist.txt` is the netlist exported from your saved project the way the evaluator \
exports it, refreshed by the runner whenever the saved schematic changes. It is what \
your work amounts to in the only form that is scored: the components with their \
reference designators, values and library parts, and the nets with the pins on them. \
It is not a score and says nothing about whether the values or the topology are the \
ones the task asked for -- only what you actually built. It is empty until you save \
the project, and stale for anything you have changed since. Read it before you \
terminate, and check it against the task: every part the task names present, every \
connection the task describes on one net. A part you meant to place that is missing \
from it was never placed, and a wire that did not land on a pin is a net that is not \
there."""


NETLIST_VERIFY_NOTE = """\
Your first `terminate` with status success does not end the episode. It is held once: \
`netlist.txt` is refreshed from your saved project at that moment and the turn after it \
asks you to check what you built against what the task asked for. Save the schematic \
before you terminate, or there is nothing to refresh and nothing to check. Terminating \
a second time ends the episode whatever the netlist says -- the hold is a chance to look, \
not a verdict, and nothing in it tells you whether you are right."""

#: Queued as turn feedback when a terminate(success) is held and the project was saved.
NETLIST_VERIFY_FEEDBACK = (
    "terminate(success) held once, and not executed. `netlist.txt` has just been "
    "refreshed from your saved project: it is exactly what would be scored if you "
    "stopped now. Before you terminate again, go through the task line by line -- every "
    "component it names, with its value, and every connection it describes -- and find "
    "each one in `netlist.txt`. A part the task names that is not in the component list "
    "was never placed. Two pins the task says are joined that appear on different nets "
    "are not wired, and a pin missing from every net is a wire that did not land. Fix "
    "what is wrong, save, and then terminate; terminating now ends the episode.")

#: Queued instead when the hold found no saved project to export.
NETLIST_VERIFY_FEEDBACK_UNSAVED = (
    "terminate(success) held once, and not executed. Nothing could be exported from "
    "your project directory: there is no saved schematic there, so stopping now scores "
    "nothing whatever is on the screen. Save the schematic into the project directory, "
    "then read the refreshed `netlist.txt` and check it against the task before you "
    "terminate again.")


CONVENTIONS_NOTE = """\
Schematic conventions the netlist comparison is sensitive to:
- Ground is the plain `GND` power symbol on every return, a battery's or connector's \
negative terminal included -- not GNDA, GNDD, GNDREF or a labelled wire, unless the \
task names another ground. A power symbol named for the voltage goes on a rail the task \
supplies the circuit with. The output of a regulator or converter is not one of \
those: it is labelled only when the task asks for it to be, and otherwise keeps \
KiCad's automatic name.
- A net carries a label only where the task asks for one, with the task's text \
verbatim (same case, same characters). Nets the task does not name stay unlabelled; \
KiCad's automatic names are the expected ones there.
- Every part keeps KiCad's own designator prefix for its kind -- R a resistor, RV a \
potentiometer or variable resistor, C a capacitor, L an inductor, D a diode or LED, Q \
a transistor, U an integrated circuit, SW a switch, J a connector, BT a battery, M a \
motor -- never a different prefix. Only the NUMBER within a prefix follows the order \
the task mentions parts, so the first resistor the task names is R1 and the first \
potentiometer is RV1. KiCad annotates in placement order, so place them in that \
order."""


DESIGN_NOTE = """\
`./design.md` and `./intent.json` hold the circuit design you committed to before the \
first action turn, worked out at length from the task: the parts in placement order \
with their symbols and values, every net with its pins, and a build order. Build \
exactly that design. Read it before you place or wire anything, and check each wire \
against its net list rather than against your recollection of the task. If you find \
the design wrong while building, correct the files first, then the schematic."""


#: The design turn's prompt: one call at its own reasoning effort, before the first
#: action turn, whose whole output is the two design files. `{task}` is the task text
#: as the log carries it (with the deliverable hint when that flag is on).
DESIGN_PROMPT = """\
This call comes before the episode's first action turn and takes no GUI action: do not \
write ./actions.json, do not read the screen. Its whole output is two files in ./ that \
the action turns will build from.

[TASK] {task}
{existing}
Design the circuit completely before anything is drawn, the way a reference schematic \
for this task would be drawn: the canonical topology for the circuit the task names; \
the datasheet's required connection for every IC pin (bypass and reference pins, \
enable/shutdown pins, unused pins); the polarity of every polarized part; every part \
the task names exactly once, with the value the task states; no part the task does \
not name, apart from power symbols. Where the task leaves a choice, take the textbook \
one and say which it is.

Write `./design.md` with three sections:
1. Parts, in the order they will be placed. KiCad annotates in placement order, so \
list resistors in the order the task mentions them (the first resistor the task names \
is R1), and likewise capacitors and every other prefix. One line each: designator, \
KiCad library symbol (`Device:R`, `Device:C_Polarized`, `Transistor_BJT:2N3904`, \
`power:GND`, ...), value string, and for polarized parts which pin faces which net.
2. Nets, one line each: the label if the task names one (verbatim), else none, and \
the pins on it as `REF.pin` with pin numbers as KiCad's symbol has them (name an IC's \
pins by function as well, e.g. `U1.3 (~SHDN)`). Every pin that must be connected \
appears in exactly one net; say which pins are left unconnected and why.
3. Build order: which parts to place first, which wires, which power symbols, which \
labels, and what to check on screen after each group.

Write `./intent.json`, the same design machine-readably:
{{"parts": [{{"ref": "R1", "symbol": "Device:R", "value": "10k"}}, ...],
 "nets": [{{"label": "GND", "pins": ["R1.2", "Q1.1"]}}, {{"label": null, "pins": [...]}}, ...]}}

End with one paragraph on the design choices you made where the task was open."""

#: Slotted into DESIGN_PROMPT's `{existing}` on a task whose project already holds a
#: schematic (read back and summarised by the driver before the design call); the
#: from-scratch tasks get an empty slot and the prompt is what the pilot ran. In the
#: pilot the design call could not see the existing circuit, so on the modify tasks
#: it abstained and the action turns put the new parts on the wrong nets.
DESIGN_EXISTING = """
The project already holds a schematic; its netlist is summarised below. The task \
modifies this circuit: keep every existing part with its designator, symbol and \
value, and design only what the task adds or changes, connecting new pins to the \
existing nets by the names given here. A new part continues its prefix's numbering \
after the highest existing one (KiCad annotates in placement order) and is placed \
fresh from the symbol chooser under the canonical library symbol (`Device:R`, \
`Device:C`, ...), even where existing parts use a variant such as `Device:R_US`. \
`intent.json` lists the complete circuit as it should be when the task is done.

{summary}
"""
