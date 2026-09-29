"""`--human-play`: the model plays the way a person does (user, 2026-09-07 13:0x-13:3x).

Keep the memory mechanism (logs.txt, episodes and their frames, [RECALL], mine/,
previous lives); give what the environment feeds back and what a player perceives (the
frame, position and facing, vitals, the inventory, events, damage, a death, the task's
ledger and clock); provide NO built-in skills beyond the GUI cursor primitives and
`watch`, NO advice and NO harness reflexes; tell the model it can write code and invent
its own actions, and keep them as scripts (`--own`). Harness notes reach the model as
feedback only: their first sentence, never the advice that follows.
"""
from __future__ import annotations

import re

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\[(\"'])")


def feedback_only(note: str) -> str:
    """The first sentence of a harness note: the fact, without the advice."""
    note = (note or "").strip()
    if not note:
        return note
    return _SENT.split(note, 1)[0].strip()


HUMAN_NOTE = """\
**Invent your skills.** There are no built-in skills in this run: no chopping, no walking
to a place, no recipe, no descent. You have a shell: write any code you like (python with
numpy and PIL, bash) to read your log, your frames and your notes, to measure how the game
answers your keys, and to compute a plan. A key sequence that worked TWICE by hand becomes a
procedure: save it as `mine/procedures/<name>.py` (the contract of such a script is below)
and from the next turn on call it by name like a built-in -- that is how you grow from keys
to skills, and your scripts are carried to your next life. Keep what you learn about this
game in `mine/notes.md`: the recipes you confirmed, how far a hold moves you, what each
screen looks like, where things are. Nothing here will advise you; the game's answers are
in [EVENT], [INV], [STATE] and the frame. Expect to be slow at first -- a person is too."""

WHAT_YOU_GET = """\
**What you get each turn.** The current frame (640x360, HUD included; `view_image <png>`
opens any other -- an episode's `observation/image.png`, an earlier life's, a crop) and the turn message:
the step budget and the milestone ledger (the task's clock and quest list), `[STATE]`
position, pitch and yaw (yaw is cumulative: reduce it mod 360), vitals, the inventory with
its slot ids, the hotbar, the held item, nearby entities, whether a screen is open and where
the GUI cursor is, `[RECENT]` (what your last entries did, measured), `[MAP]` (cells you
walked, hazards, water and lava you sighted), `[OWN]` (your scripts), `[EXPECTED]` against
`[OBSERVED]`, and the game's feedback as `[EVENT]` and `[NOTE]` lines: what broke, what you
picked up, damage taken, a death, what a screen did. None of it is advice, and the runner
never acts for you: no reflexes, no guards, no refusals -- when you take damage or die, the
plan stops and you decide."""

GUI_ADDRESSING = """\
GUI addressing, for the cursor primitives: in the inventory screen slots 0-8 are the hotbar
and 9-35 the three main rows (the ids `[INV]` shows); a crafting grid's cells are row-major
from 0 (the inventory's own 2x2: 0-3, a crafting table's 3x3: 0-8); a furnace has cell 0
(smelt input), cell 1 (fuel) and `out`. `cursor_to_slot`/`cursor_to_cell` land the cursor
there (closed loop, measured in the frame), `gui_click` picks up or places a stack,
`gui_right_click` places one item. `watch(until=..., n)` is your one closed-loop primitive
outside screens: it holds still and stops the plan the moment its condition holds."""

RAW_SCHEMA = """\
**Actions.** Write `./actions.json` = `{{"actions": [...]}}`: at most {entry_cap} entries and
{step_cap} game ticks in total (20 ticks = 1 second). An entry is either a raw action held
for N ticks, `{{"action": {{"forward": 1, "jump": 1, "camera": [dpitch, dyaw]}}, "repeat": N}}`
-- keys: forward, back, left, right, jump, sneak, sprint, attack, use, inventory (toggles
the inventory screen), pickItem, hotbar.1 .. hotbar.9; `camera` is degrees PER TICK,
+pitch looks down, +yaw turns right; an empty action `{{}}` waits -- or a call
`{{"procedure": "<name>", "args": {{...}}}}` to one of the few primitives below or to one of
your own scripts. A milestone, damage or a death ends the plan early and returns the turn
to you."""
