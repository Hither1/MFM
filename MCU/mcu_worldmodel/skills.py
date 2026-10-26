"""`--skills`: the three-layer skill package the self-harness arm reads and owns.

The direction, after four runs: the model writes its
own harness -- the memory it keeps, the skills it composes, the reflexes that guard its
plans -- and the harness's part is META-level guidance per layer plus example code, packed
the way wz1119/Codex-Minecraft-Gameplay packs its play instructions: a `SKILL.md` per
skill with the doctrine, `scripts/` beside it with working examples. Nothing here is a
fact about this world (no coordinates, no sites -- the carry-only rule);
everything here is about how to play, how to remember, what to protect against.

What is written into the workspace, once per life, harness-owned and immutable:

    skills/memory/SKILL.md          using the multimodal memory: log, episodes, frames,
                                    previous lives, the guide, the workshop turn;
                                    scripts/death_sheet.py, where_was.py (memory queries)
    skills/procedures/SKILL.md      the skill layer: the right grain, guards, reuse
    skills/reflexes/SKILL.md        the reflex layer: how reflexes run, how to retire
                                    one; scripts/ore_watch.py, an example (nothing is
                                    installed under `mine/reflexes/`: the model copies
                                    what it wants, edits it, and a leading underscore in
                                    the file name keeps a copied script off)
    skills/harness/SKILL.md         the loop, the economics of turns vs steps, what the
                                    runner does and does not do in this run, the do-not
                                    list from the earlier runs

The SKILL.md texts were written for a harness with built-in procedures and shipped
procedure and reflex examples; `_NO_PRIMITIVES_EDITS` rewrites what names them. With the
runner's own guards off (`harness_reflexes=False`, every arm) the reflexes the model
writes are the whole tick layer.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path("skills")

# -- the reflex examples (skills/reflexes/scripts/; the model copies them into mine/reflexes/) --

# -- example procedures (skills/procedures/scripts/) ---------------------------------------

# -- example memory script (skills/memory/scripts/) ----------------------------------------

EXAMPLE_MEMORY: dict[str, str] = {
    "death_sheet.py": '''"""death_sheet: the frames of the last 60 steps before the last death in logs.txt, tiled, with the notes that preceded it."""
# Example (harness-written; copy and adapt). Usage:
#   python skills/memory/scripts/death_sheet.py [death.png]
# Finds the last "YOU DIED" in logs.txt, prints the [NOTE]/[EVENT] lines of the 60 steps
# before it (the cause is usually in them: "took 4 damage", "LAVA AHEAD", "DOUSED"), and
# tiles the episode frames of that span into one image for view_image. Then write the
# one-line verdict into mine/GUIDE.md yourself.
import json, re, subprocess, sys
out = sys.argv[1] if len(sys.argv) > 1 else "death.png"
HDR = re.compile(r"^Action (\\d+) \\| Step (\\d+)")
step, death, notes = 0, None, []
for ln in open("logs.txt", encoding="utf-8", errors="ignore"):
    m = HDR.match(ln)
    if m:
        step = int(m.group(2)); continue
    if ln.startswith(("[NOTE]", "[EVENT]")):
        notes.append((step, ln.strip()))
    if "YOU DIED" in ln:
        death = step
if death is None:
    sys.exit("no YOU DIED in logs.txt")
for s, ln in notes:
    if death - 60 <= s <= death:
        print(f"step {s}: {ln[:140]}")
cmd = ["./tools/episodes.py", "--steps", str(max(0, death - 60)), str(death), "--sheet", out,
       "--q", "what killed me"]
print(" ".join(cmd)); subprocess.run(cmd)
print(f"view_image {out}, then one line in mine/GUIDE.md: step, place, cause, what you refuse next time")
''',
    "where_was.py": '''"""where_was: every place a keyword was seen in this life and the earlier ones, with the frames to open."""
# Example: one script answers one question over the whole memory. Usage:
#   python skills/memory/scripts/where_was.py "lava" [--previous]
# It walks logs.txt (and previous/life_*/logs.txt with --previous), keeps the position of
# every [NOTE]/[EVENT] line matching the keyword, and prints them with the step and the
# life -- the same thing `./tools/episodes.py --grep` does per episode, from the log side.
import glob, re, sys
kw = sys.argv[1] if len(sys.argv) > 1 else "lava"
logs = ["logs.txt"] + (sorted(glob.glob("previous/life_*/logs.txt")) if "--previous" in sys.argv else [])
HDR = re.compile(r"^Action (\\d+) \\| Step (\\d+)")
ST = re.compile(r"^\\[STATE\\] pos=\\((-?[\\d.]+), (-?[\\d.]+), (-?[\\d.]+)\\)")
for log in logs:
    step, pos = 0, None
    for ln in open(log, encoding="utf-8", errors="ignore"):
        m = HDR.match(ln)
        if m:
            step = int(m.group(2)); continue
        m = ST.match(ln)
        if m:
            pos = tuple(round(float(v)) for v in m.groups()); continue
        if ln.startswith(("[NOTE]", "[EVENT]")) and kw.lower() in ln.lower():
            print(f"{log.split('/')[0] if '/' in log else 'this life'} step {step} at {pos}: {ln.strip()[:110]}")
''',
}

# -- example reflex (skills/reflexes/scripts/) ----------------------------------------------

# -- the SKILL.md texts --------------------------------------------------------------------

MEMORY_SKILL = """\
---
name: memory
description: Using the multimodal memory this run keeps for you -- the log, the episodes with their frames, the earlier lives, your own files -- and the workshop turn at the start of a life.
---

# Memory

You do not build a memory here; you USE one. The harness records everything (immutable,
grep-able) and keeps what you write under `mine/` (yours, carried to your next life).

## What is recorded, and how to ask it

- `logs.txt`: every turn -- `[STATE]` position/pitch/yaw, `[EVENT]` what broke, dropped,
  was crafted or picked up, `[NOTE]` what the runner and your procedures observed,
  `[INV]` inventory changes, `[PLAN]` your own briefings. `grep -n` is the query.
- `episodes/ep_NNNNNN/`: one per plan entry, with `observation/image.png` (the view the
  entry started from), `state/state.json`, `action.json`, `outcome.json` (moved,
  descended, inventory delta, events, tags such as `stuck`, `damage`, `milestone`).
  `./tools/episodes.py --last 5 | --steps A B | --near X Z [--radius R] | --tag damage
  | --action go_to | --grep text`; add `--sheet out.png` to tile the frames of the
  matches into one image, `--json` for rows; `--then-now <id> --q "<question>"` writes
  that episode's frame beside the current view as `then_now.png` -- the recognition
  check before you walk to a remembered place, or on arrival. Pass `--q` on every
  look: the record keeps what the look was for.
- Frames are files: `./tools/zoom.py <frame.png> x y w h [out.png]` magnifies a region
  4x for `view_image`; a script with numpy/PIL can read many frames and answer one
  question over all of them (where the orange was; which frames show a screen).
- `previous/life_<i>/`: the complete records of earlier lives in this same world
  (same seed, same spawn), oldest first, each with its logs.txt, episodes, index and
  `mine/` (its notes, guide and scripts). `./tools/episodes.py --previous ...` queries
  them all; `grep -n 'LAVA AHEAD\\|YOU DIED\\|obsidian' previous/life_*/logs.txt` is the
  fastest map of what they found and what killed them. The world resets between lives:
  terrain, water, lava and ore are where they were; nothing built or dropped survives;
  their step numbers are theirs.
- `mine/`: yours. `mine/notes.md` (what worked, what each script assumes),
  `mine/GUIDE.md` (what you took from the earlier lives), `mine/procedures/`,
  `mine/reflexes/`, any data or images you save. Carried whole to your next life.

## The workshop turn

The first turn of a life with `previous/` is a WORKSHOP, not a play turn: read the
lives' guides, notes and death lines, run the query tool over them, write or update
`mine/GUIDE.md` (verified places with coordinates, the life/step they come from and
the episode id whose frame shows the place, what each life died of and where, which scripts and reflexes earned their keep and
which assumptions broke), copy the scripts worth keeping into `mine/procedures/` and
`mine/reflexes/`, and only then plan. One no-op plan is a fine end to a workshop turn:
turns cost wall clock, not game steps.

## When to look at a frame

`view_image <png>` opens any frame: an episode's `observation/image.png`, an earlier
life's under `previous/`, a sheet from `--sheet`, a crop from `tools/zoom.py`, the pair
from `--then-now`. Write the question first ("is the lava in the next cell or two cells
off?", "is this the ledge I poured from?") and pass it as `--q`. The `[STATE]`/`[NOTE]`
numbers say WHERE and THAT; the frame says WHAT -- one look costs one image. Open frames
before you walk to a remembered place and on arrival (`--then-now`), after a hit (the
frame at the hit shows what hit you), when `OBSERVED vs EXPECTED` disagree (the entry's
frame is cited beside the outcome), before a route across ground you have not walked,
and when a plan failed twice for a reason you cannot name. The 22 runs before this one
opened an earlier episode's frame 32 times in 850,000 steps and an earlier life's 3
times; every one of those looks was after a stall, none before a walk.

## Working memory

`mine/working.md` is put in front of you every turn as `[WORKING]` and survives a
context reset: the plan you are on and why, its next visible prediction, the
contradictions you have not resolved, the entries and frames you would re-open (paths).
Rewrite it when the plan changes, under 40 lines. `mine/GUIDE.md`
is what is true of this world across lives; `working.md` is what you are doing now.

## Death forensics

After `YOU DIED`, before you rebuild anything: `./tools/episodes.py --steps <death-60>
<death> --sheet death.png --q "what killed me"`, view it, and write one line into
`mine/GUIDE.md`: step, place, cause, what you will refuse next time.
The frame tells a burn from a mob: flames over the lower view, orange at the feet. Of
the 20 deaths in the earlier runs, 11 were lava or fire, 5 a mob, and 3 happened within
5 blocks of a place the same life had already written down as lava or a death --
recorded, and never turned into a refusal. `skills/memory/scripts/death_sheet.py` does
the tiling for the last death in the log.

## Record every firing and every death

A reflex that fired, a fall, a hit, a death: one line in `mine/notes.md` with the step,
the place, the cause and what you changed. That line is what your next life reads
first. `skills/memory/scripts/where_was.py <keyword> [--previous]` is an example of a
memory query written as a script.
"""

PROCEDURES_SKILL = """\
---
name: procedures
description: The skill layer -- how to compose the atoms into skills of the right grain, guard them, reuse them across lives, and when NOT to write one.
---

# Procedures

The built-in set is the ATOMS (closed-loop aims and walks, the GUI cursor, one-call
craft, placements, the bucket, watch/pillar/eat/throw). Everything task-shaped you build
yourself as `mine/procedures/<name>.py` (the script contract is in the main contract).
This file says what a good one looks like.

## The ladder the task climbs

kit (table, tools) -> iron (ore, furnace, ingots) -> a bucket and water -> lava ->
obsidian -> the portal frame and the lighter -> the Nether -> blaze rods -> ender pearls
-> eyes of ender -> the stronghold -> the End. Each arrow is a phase; a skill is ONE
phase step, not one block and not the whole phase. The first three diamonds are the
PICKAXE, never the sword: the lake opens only to the pickaxe, and every life that made
the sword first mined exactly two diamonds and never saw obsidian.

## The right grain

- A skill is 50-400 ticks of atoms that you would otherwise write out by hand every
  turn: a staircase step, a tunnel segment with its torch, a GUI craft with its
  verification, a bucket fill from a bank, a pour and a scoop at a pool.
- One-block scripts (break one stone, walk one block) are not skills: they cost a turn
  each to call and a turn each to check, and the runs that wrote them (24 of them in
  one life) moved a block at a time all night.
- Every script guards the pose it was tested from: heading, stable y, the tool in the
  hotbar, a screen closed. Raise SystemExit with the reason when a guard fails -- the
  note tells you what to fix, and nothing runs.
- Compute targets from the state (your position, yaw, the hotbar) instead of asking the
  caller for coordinates; `skills/procedures/scripts/torch_wall.py` shows how.
- Write a skill after the same sequence worked TWICE by hand; call it by name from then
  on. A script you never call again was a turn spent on nothing.

## Where the budget went (the 22 runs before this one)

From nothing (the full task), the runs with a fixed library took 6,500-7,900 steps from
the first log to the iron pickaxe and about 11,000 to the first diamond, in a 12,000-step
budget; from the kit (the half task) the kit and the diamond tools took 2,000-6,000 steps.
Then the runs that got furthest
spent most of their steps between the diamond tools and the lighter -- water, gravel,
flint, the bucket: 6,000 to 31,000 steps -- and between the first obsidian and a lit
portal: 5,000 to 19,000, with one run spending 19,000 steps after its obsidian and never
lighting one; the one run that entered the Nether spent 12,000 steps there without a
blaze rod. Write the phase skills for water/gravel/flint and for pour -> frame -> light
before you polish a staircase; those are the turns the budget rewards.

## Reuse before rewrite

Your earlier lives' scripts are under `previous/life_<i>/mine/procedures/`. Read their
docstrings and notes in the workshop turn; copy the ones whose assumptions still hold
into `mine/procedures/` UNDER THEIR OWN NAMES (they are not copied for you; every one of
the last five lives rewrote its staircase step from scratch under a new name). `previous/scripts.md`
counts, for every earlier script, its calls, its guard's refusals and its last outcome:
copy by that record, not by the name. A script that failed in an
earlier life has the failure in that life's notes -- fix the assumption, do not rerun it.

## Examples

`skills/procedures/scripts/stair_step.py` (one step of a staircase down along the
heading: foot block, head block, step in; guards on ground and pickaxe),
`skills/procedures/scripts/torch_wall.py` (a torch on the wall beside you, computed
from your pose), `skills/procedures/scripts/shaft_down.py` (straight down to a
target y in one call, ~20 ticks per level against a staircase's ~80) and
`skills/procedures/scripts/strip_segment.py` (a lit 1x2 tunnel, 4 blocks a call at
~45 ticks a block, every hold watched for ore) and
`skills/procedures/scripts/aim_speckles.py` (the answer to a sighting [NOTE]: crosshair
onto its pixel, mine the block, sweep the drop). Copy, rename, make them yours.

## Mining one block

A raw `{"attack": 1}` hold of 30 ticks. The runner cuts it the moment the block breaks
and refunds the rest (the [NOTE] says so), and the wall watcher samples every hold for
iron- and diamond-ore speckles: a sighting drops the rest of the plan with a [NOTE]
and the flag-time frame. `mine_ahead(n)` spends all n ticks whatever breaks -- it is
for continuous digging (a shaft), not for a block.

## A sighting outranks everything

`[NOTE] mining stopped: iron-ore-like (or diamond-ore-like) speckles on screen at (x, y)`
is the one event this life is waiting for, and it is perishable: the runner dropped the
rest of your plan so the view is still the flag-time view, and the next look or step
loses it. Your next plan is ONE call of `aim_speckles(x=<x>, y=<y>)` from
`skills/procedures/scripts/` (copy it into `mine/procedures/` in your first turn) --
before any look, any craft, any step of the schedule below. The life that found the
diamond did this within 20 steps of the [NOTE]; the lives that "finished the column
first" or went to craft something first never mined the ore. If the hold breaks
stone, the speckles were a block further in: hold again at the same aim.

## The budget, as a schedule

Three lives before this one scored 9/10 on the diamond task, and all three lost the
diamond to the same clock, not to a death. In steps, what a 10/10 life looks like on
this action set:

- **by 1,000**: 6+ logs (stay at the tree until you have them -- a second trip to the
  surface for wood cost one life 2,700 steps), the table, the wooden pickaxe.
- **by 2,500**: cobblestone -> the stone pickaxe, the furnace (8), a stone axe (3). At
  the furnace, 4 logs -> 4 charcoal (~800 ticks: mine stone while it cooks) -> 16
  torches. One life went down with 2 torches and spent 1,400 steps walking back to
  move its last one forward. Break and carry the table and the furnace.
- **by 3,500**: at y 13 by shaft (shaft_down, three calls). Not a staircase: 80 ticks
  a level, 3,500-4,000 steps a life.
- **3,500 to the end**: lit strips at y 12-13 (strip_segment, light=true every other
  call). Iron ore is in the same walls: 3 ore -> a furnace placed in the tunnel, smelt
  while you keep mining -> the iron pickaxe (the diamond needs it). Two 40-block strips
  with no sighting: move 3 blocks sideways and strip back parallel. The life that found
  the diamond exposed ~300 blocks of wall at y 11; the lives that did not exposed 60.
"""

REFLEXES_SKILL = """\
---
name: reflexes
description: The reflex layer -- tick-level guards you write before the event, the classes that killed earlier runs, the starters already installed, and how to keep or retire them.
---

# Reflexes

A procedure runs when you call it, between turns. What killed the earlier runs happened
INSIDE a plan, between one turn and the next: lava coming into view on a walk, a hole
under a go_to, a mob at your back in a dig, a slope down into the lava sea. A reflex is
a script of yours that runs every 4 ticks on the live numbers while your plan executes
and may stop the plan, leave a note for your next turn, and run a short plan of its own
(`mine/reflexes/<name>.py`; the state fields and the output shape are in the main
contract).

## Doctrine

- Write reflexes BEFORE the event. "Worked twice by hand" is a rule for procedures; a
  reflex cannot be tried by hand -- write it from the class of danger, then refine it
  after each firing (was it right? too early? too late?). Record every firing in
  `mine/notes.md`.
- A stop costs no game steps: the plan halts, you get the turn, the world waits. Use
  stops freely for anything that changes what you would do next; use `actions` only
  for the reflexes whose answer is always the same (step back from lava).
- Read the state, not the logs: a reflex runs every 4 ticks and has 3 seconds; parsing
  logs.txt there is how a reflex gets switched off.
- The runner's own guards are OFF in this run: nothing stops you at lava, nothing
  pillars you when hit, nothing refuses a repeated plan. Your reflexes are the tick
  layer.

## The classes, from what killed the earlier runs

1. Lava in the lower view while a walk or a dig moves you (every lava death).
2. A drop of 3+ blocks in a few ticks (holes, ledges, your own old shaft).
3. Health falling with no lava in view: a mob you cannot see (most deaths underground:
   the plan kept digging or clicking through the hits).
4. In the Nether, any walk with lava in view: every ledge ends in the lava sea at
   y ~31; sneak, never sprint, never jump while moving, dig the way down.
5. The food bar below 18: no natural healing (a run sat at 2/20 for 3,000 steps).
6. Your only water bucket: pouring it as an elevator leaves you empty at the lava.
7. A walk toward a place where you, or an earlier life, died or saw lava. Three of the
   twenty earlier deaths were within 5 blocks of a spot the same life had already written
   down; the log knew, nothing refused. The cheapest reflex there is: read the hazard
   lines from `mine/GUIDE.md`, stop the plan when you come within 6
   blocks of one while moving. `skills/reflexes/scripts/known_hazards.py` is the example
   -- copy it into `mine/reflexes/` once your guide has coordinates in it.

## The examples

Under `skills/reflexes/scripts/`: `lava_ahead.py`, `fell.py`, `hit.py`, `starving.py`
(classes 1, 2, 3, 5) and `known_hazards.py` (class 7). Nothing is installed for you:
`mine/reflexes/` is empty until you copy a script into it (`cp
skills/reflexes/scripts/lava_ahead.py mine/reflexes/`), and from then on it runs every 4
ticks. Decide in your first turn which to copy, edit their thresholds, write the Nether
one (class 4) before you go there. At most 4 run, alphabetical; to retire one, rename it
with a leading underscore (`_hit.py` stays off).
"""

HARNESS_SKILL = """\
---
name: harness
description: How this run's loop works, what the runner does and does not do for you, the economics of turns versus steps, and the do-not list from the earlier runs.
---

# Harness

## The loop

Each turn: the frame and the turn message (state, inventory, ledger, `[RECENT]`,
`[MAP]`, `[OWN]`, the notes since your last plan) -> your briefing (`OBSERVED vs
EXPECTED`, then `[PLAN]`, then `EXPECT`) -> `actions.json`, a plan of up to the entry
and step caps, built from the atoms, your own procedures and raw actions. The runner
executes it tick by tick; a milestone, a death or a reflex stop ends the plan early and
hands you the turn.

## What the runner does, and does not do, in this run

Does: execute plans, verify closed-loop atoms (aims, walks, GUI cursor), record
everything, run your reflexes every 4 ticks, carry `mine/` and the records to your next
life. Does NOT: guard you (no lava stop, no fall stop, no pillar or bunker on a hit, no
water refusal), refuse a repeated plan, nudge you toward a sword or a torch. The notes
that say "the runner did X for you" in `references/survival.md` describe OTHER runs;
here those are your reflexes' jobs.

## Economics

A turn costs about a minute of wall clock; a game step costs almost nothing. The run
ends at a step budget AND a wall-clock cap, and every self-built run so far hit the
wall clock first (1.7-3.1k steps per hour, against 4-7k for a fixed library). So:
plans that run long between turns beat plans that check after every block; a script
that saves a turn pays for itself on its second call; a workshop turn that writes a
skill you call twenty times is the best turn of the life.

## Do-not list (each line cost an earlier run its night or its life)

- Do not re-issue an unchanged plan at the same spot; change the target, the tool, or
  the place.
- Do not descend without food in the inventory and a stack of blocks in the hotbar.
- Do not pour your only water bucket for anything but obsidian (or refill first).
- Do not jump down a hole you cannot climb out of; do not walk back into your own shaft.
- Do not fight a skeleton from the water or under 10 health; break its line of sight.
- Do not stand still under hits; do not walk toward orange.
- In the Nether: sneak, no sprint, no moving jump, dig the way down, bridge over lava.
- Do not write a one-block script; do not write a script you will not call twice.
"""

#: The memory skill's two paragraphs about `previous/`, as shipped and as they read when
#: the carried lives were played in another world on another task (`--carried-world
#: other`): their places are not here, so the workshop turn takes how to act from them.
_PREVIOUS_SAME = """\
- `previous/life_<i>/`: the complete records of earlier lives in this same world
  (same seed, same spawn), oldest first, each with its logs.txt, episodes, index and
  `mine/` (its notes, guide and scripts). `./tools/episodes.py --previous ...` queries
  them all; `grep -n 'LAVA AHEAD\\|YOU DIED\\|obsidian' previous/life_*/logs.txt` is the
  fastest map of what they found and what killed them. The world resets between lives:
  terrain, water, lava and ore are where they were; nothing built or dropped survives;
  their step numbers are theirs.
"""
_PREVIOUS_OTHER = """\
- `previous/life_<i>/`: the complete records of earlier lives of yours in ANOTHER world
  (a different seed and spawn) and on another task, oldest first, each with its
  logs.txt, episodes, index and `mine/` (its notes, guide and scripts).
  `./tools/episodes.py --previous ...` queries them all. No place in them exists in
  this world. Read them for how that life acted: which scripts and reflexes worked,
  how it got through each screen and recipe, what cost it steps and what killed it;
  their step numbers are theirs.
"""
_WORKSHOP_SAME = """\
`mine/GUIDE.md` (verified places with coordinates, the life/step they come from and
the episode id whose frame shows the place, what each life died of and where, which scripts and reflexes earned their keep and
which assumptions broke), copy the scripts worth keeping into `mine/procedures/` and
"""
_WORKSHOP_OTHER = """\
`mine/GUIDE.md` (what each life learned to do, the life/step it comes from and the
episode id whose frame shows it, what each life died of and why, which scripts and reflexes earned their keep and
which assumptions broke, what of it serves THIS task; none of their coordinates: this
is another world), copy the scripts worth keeping into `mine/procedures/` and
"""
assert MEMORY_SKILL.count(_PREVIOUS_SAME) == 1 and MEMORY_SKILL.count(_WORKSHOP_SAME) == 1, \
    "memory skill text drifted from the carried-world paragraphs"


def memory_skill(carried_world: str = "same") -> str:
    if carried_world == "same":
        return MEMORY_SKILL
    if carried_world != "other":
        raise ValueError(f"unknown carried_world: {carried_world!r} (same|other)")
    return (MEMORY_SKILL.replace(_PREVIOUS_SAME, _PREVIOUS_OTHER)
            .replace(_WORKSHOP_SAME, _WORKSHOP_OTHER))


# -- the record ablations of the mfm arm: the same package, told the truth about the run --
#
# `history_images=False` keeps no frame of an earlier moment; `flat_retrieval=True` keeps
# the record but not tools/episodes.py (agent.py). The memory skill is rewritten segment
# by segment -- every old text must occur exactly once, or the edit is stale -- and the
# harness skill gets a `## This run` section under its title.

_MEM_EPISODES = """\
- `episodes/ep_NNNNNN/`: one per plan entry, with `observation/image.png` (the view the
  entry started from), `state/state.json`, `action.json`, `outcome.json` (moved,
  descended, inventory delta, events, tags such as `stuck`, `damage`, `milestone`).
  `./tools/episodes.py --last 5 | --steps A B | --near X Z [--radius R] | --tag damage
  | --action go_to | --grep text`; add `--sheet out.png` to tile the frames of the
  matches into one image, `--json` for rows; `--then-now <id> --q "<question>"` writes
  that episode's frame beside the current view as `then_now.png` -- the recognition
  check before you walk to a remembered place, or on arrival. Pass `--q` on every
  look: the record keeps what the look was for.
"""
_MEM_EPISODES_NO_IMAGES = """\
- `episodes/ep_NNNNNN/`: one per plan entry, with `state/state.json`, `action.json`,
  `outcome.json` (moved, descended, inventory delta, events, tags such as `stuck`,
  `damage`, `milestone`). NO frame is kept in this run: no episode has an
  `observation/image.png`. `./tools/episodes.py --last 5 | --steps A B | --near X Z
  [--radius R] | --tag damage | --action go_to | --grep text`; `--json` for rows. Pass
  `--q` on every query: the record keeps what it was for.
"""
_MEM_EPISODES_FLAT = """\
- `episodes/ep_NNNNNN/`: one per plan entry, with `observation/image.png` (the view the
  entry started from), `state/state.json`, `action.json`, `outcome.json` (moved,
  descended, inventory delta, events, tags such as `stuck`, `damage`, `milestone`).
  `index.jsonl` is their flat chronological record: one JSON line per episode, in
  order, with the id, step range, tags, position, action, outcome summary, first note,
  events and the paths. There is NO query tool in this run: `rg`/`grep` `index.jsonl`
  and `episodes/*/outcome.json` the way you grep `logs.txt`, or write a script.
"""
_MEM_EPISODES_FLAT_NO_IMAGES = """\
- `episodes/ep_NNNNNN/`: one per plan entry, with `state/state.json`, `action.json`,
  `outcome.json` (moved, descended, inventory delta, events, tags such as `stuck`,
  `damage`, `milestone`). NO frame is kept in this run (no `observation/image.png`).
  `index.jsonl` is their flat chronological record: one JSON line per episode, in
  order, with the id, step range, tags, position, action, outcome summary, first note,
  events and the paths. There is NO query tool in this run: `rg`/`grep` `index.jsonl`
  and `episodes/*/outcome.json` the way you grep `logs.txt`, or write a script.
"""
_MEM_FRAMES = """\
- Frames are files: `./tools/zoom.py <frame.png> x y w h [out.png]` magnifies a region
  4x for `view_image`; a script with numpy/PIL can read many frames and answer one
  question over all of them (where the orange was; which frames show a screen).
"""
_MEM_FRAMES_NO_IMAGES = """\
- The only image is the CURRENT view, `../attach/frame.png` (rewritten every turn):
  `./tools/zoom.py <frame.png> x y w h [out.png]` magnifies a region 4x for
  `view_image`. No earlier frame exists in this run.
"""
_MEM_LOOK = MEMORY_SKILL[MEMORY_SKILL.index("## When to look at a frame"):
                         MEMORY_SKILL.index("## Working memory")]
_MEM_LOOK_NO_IMAGES = """\
## The current view is the only frame

`view_image <png>` opens the attached view (`../attach/frame.png`) or a crop of it from
`tools/zoom.py`; there is no earlier frame to open in this run. What a place looked
like lives in words: when you stand somewhere you will want to recognise again, say
what you see in your briefing (the log keeps it), and on arrival compare the live view
against those words and the `[STATE]` numbers.

"""
_MEM_LOOK_FLAT = """\
## When to look at a frame

`view_image <png>` opens any frame: an episode's `observation/image.png` (find the
episode in `index.jsonl`), an earlier life's under `previous/`, a crop from
`tools/zoom.py`. Write the question first ("is the lava in the next cell or two cells
off?", "is this the ledge I poured from?"). The `[STATE]`/`[NOTE]` numbers say WHERE
and THAT; the frame says WHAT -- one look costs one image. Open frames before you walk
to a remembered place and on arrival (that episode's frame beside the attached view),
after a hit (the frame at the hit shows what hit you), when `OBSERVED vs EXPECTED`
disagree (the entry's frame is cited beside the outcome), before a route across ground
you have not walked, and when a plan failed twice for a reason you cannot name. The 22
runs before this one opened an earlier episode's frame 32 times in 850,000 steps and
an earlier life's 3 times; every one of those looks was after a stall, none before a
walk.

"""
_MEM_DEATH = MEMORY_SKILL[MEMORY_SKILL.index("## Death forensics"):
                          MEMORY_SKILL.index("## Record every firing")]
_MEM_DEATH_STATS = MEMORY_SKILL[MEMORY_SKILL.index("Of\nthe 20 deaths"):
                                MEMORY_SKILL.index(" `skills/memory/scripts/death_sheet.py`")]


def _death_section(*, images: bool, flat: bool) -> str:
    if flat:
        look = ("`grep -n 'YOU DIED' logs.txt` and read the [NOTE]/[EVENT] lines of the 60 "
                "steps\nbefore it" + (", then `view_image` the frames of those episodes (find "
                                       "them in `index.jsonl`)," if images else ","))
    else:
        look = "`./tools/episodes.py --steps <death-60>\n<death> --q \"what killed me\"` (the notes and events of those entries),"
    frame_line = ("The frame tells a burn from a mob: flames over the lower view, orange at the feet. "
                  if images else
                  "The notes tell a burn from a mob: LAVA AHEAD or a fire note against `took N "
                  "damage` with no lava. ")
    return ("## Death forensics\n\nAfter `YOU DIED`, before you rebuild anything: " + look
            + " and write one line into\n`mine/GUIDE.md`: step, place, cause, what you will "
            "refuse next time.\n" + frame_line + _MEM_DEATH_STATS + "\n\n")


def _ablate(text: str, edits: list[tuple[str, str]], what: str) -> str:
    for old, new in edits:
        if text.count(old) != 1:
            raise ValueError(f"{what} drifted from its ablation edit: {old[:60]!r}")
        text = text.replace(old, new)
    return text


def ablate_memory_skill(text: str, *, images: bool = True, flat: bool = False,
                        pushed: bool = True) -> str:
    """skills/memory/SKILL.md for an arm with a record ablation on (unchanged otherwise)."""
    if images and not flat:
        return _ablate(text, _mem_unpushed(flat=False), "the memory skill") if not pushed else text
    edits = [(_MEM_EPISODES, {(True, True): _MEM_EPISODES_FLAT,
                              (False, True): _MEM_EPISODES_FLAT_NO_IMAGES,
                              (False, False): _MEM_EPISODES_NO_IMAGES}[(images, flat)]),
             (_MEM_DEATH, _death_section(images=images, flat=flat))]
    if not images:
        edits += [("the log, the episodes with their frames, the earlier lives",
                   "the log, the episodes, the earlier lives"),
                  (_MEM_FRAMES, _MEM_FRAMES_NO_IMAGES),
                  ("each with its logs.txt, episodes, index and\n  `mine/`",
                   "each with its logs.txt, episodes (no frames in this run), index and\n  `mine/`"),
                  ("the episode id whose frame shows the place", "the episode id of the place"),
                  ("any data or images you save", "any data you save"),
                  (_MEM_LOOK, _MEM_LOOK_NO_IMAGES),
                  ("the entries and frames you would re-open (paths)",
                   "the entries you would re-open (paths)")]
    else:
        edits.append((_MEM_LOOK, _MEM_LOOK_FLAT))
    if flat:
        edits += [("`./tools/episodes.py --previous ...` queries\n  them all;",
                   "their `index.jsonl` files are\n  grep-able like yours;"),
                  ("run the query tool over them", "search their records")]
    if not pushed:                      # with flat only (agent.py refuses no-images with it)
        edits += _mem_unpushed(flat=flat)
    return _ablate(text, edits, "the memory skill")


def _mem_unpushed(*, flat: bool) -> list[tuple[str, str]]:
    """`pushed_memory=False`: [WORKING] and [OBSERVED] are not in the turn. The look
    paragraph's line break differs between the full and the flat text."""
    cited = ("when `OBSERVED vs EXPECTED`\ndisagree (the entry's frame is cited beside the outcome)"
             if flat else
             "when `OBSERVED vs EXPECTED` disagree (the entry's\nframe is cited beside the outcome)")
    return [("`mine/working.md` is put in front of you every turn as `[WORKING]` and survives a\ncontext reset:",
             "`mine/working.md` is not put in front of you in this run (no `[WORKING]`: read it\n"
             "yourself) and survives a context reset:"),
            (cited, cited.replace("is cited beside the outcome", "is in its `index.jsonl` row"))]


#: The harness skill's `## This run` lines, one per ablation that is on.
_HARNESS_THIS_RUN = {
    "images": ("- No frame of an earlier moment is kept in this run: the current view attached to\n"
               "  the turn is the only image (`skills/memory/SKILL.md`)."),
    "flat": ("- There is no `tools/episodes.py` in this run: the record is `logs.txt`,\n"
             "  `episodes/` and `index.jsonl`, searched with `rg`/`grep` (`skills/memory/SKILL.md`)."),
    "unpushed": ("- The turn message carries no `[RECENT]`, `[MAP]`, `[EXPECTED]`/`[OBSERVED]` or\n"
                 "  `[WORKING]` in this run: what the last plans did is in `logs.txt` and\n"
                 "  `episodes/`, and your note is `mine/working.md` -- read them yourself."),
}


def ablate_harness_skill(text: str, *, images: bool = True, flat: bool = False,
                         pushed: bool = True) -> str:
    lines = (([] if images else [_HARNESS_THIS_RUN["images"]])
             + ([_HARNESS_THIS_RUN["flat"]] if flat else [])
             + ([] if pushed else [_HARNESS_THIS_RUN["unpushed"]]))
    if not lines:
        return text
    edits = [("# Harness\n", "# Harness\n\n## This run\n\n" + "\n".join(lines) + "\n")]
    if not pushed:
        edits.append(("(state, inventory, ledger, `[RECENT]`,\n`[MAP]`, `[OWN]`, the notes since your last plan)",
                      "(state, inventory, ledger, `[OWN]`,\nthe notes since your last plan)"))
    return _ablate(text, edits, "the harness skill")


#: The example scripts' comments that point at frames or the query tool.
_SCRIPT_EDITS = {
    ("where_was.py", "images"): [("with the frames to open.", "with the step and the life.")],
    ("where_was.py", "flat"): [(" -- the same thing `./tools/episodes.py --grep` does per episode, from the log side.",
                                ".")],
    ("ore_watch.py", "images"): [("-- tune them on the frames under episodes/ (the same picture, smaller) before trusting\n# them.",
                                  "-- tune them on frames you copy from `frame` before trusting\n# them.")],
}


def ablate_script(name: str, src: str, *, images: bool = True, flat: bool = False) -> str:
    edits = ((_SCRIPT_EDITS.get((name, "images"), []) if not images else [])
             + (_SCRIPT_EDITS.get((name, "flat"), []) if flat else []))
    return _ablate(src, edits, name) if edits else src


#: `--install-carried` (previous.PreviousLives.install_own): the carried lives' own
#: scripts are already in mine/, so the two places that tell the model to copy them say
#: so instead. (old, new) pairs, each old text occurring exactly once.
_COPY_MEMORY = ("copy the scripts worth keeping into `mine/procedures/` and\n"
                "`mine/reflexes/`, and only then plan.",
                "read the scripts installed for you in `mine/` ([INSTALLED] in the contract),\n"
                "keep, fix or retire each, and only then plan.")
_COPY_PROCEDURES = ("copy the ones whose assumptions still hold\n"
                    "into `mine/procedures/` UNDER THEIR OWN NAMES (they are not copied for you; every one of\n"
                    "the last five lives rewrote its staircase step from scratch under a new name).",
                    "the ones they wrote are\n"
                    "already installed in `mine/procedures/` UNDER THEIR OWN NAMES ([INSTALLED] in the\n"
                    "contract): keep the ones whose assumptions still hold, fix the rest, and retire one\n"
                    "with a leading underscore rather than writing a twin under a new name.")
assert PROCEDURES_SKILL.count(_COPY_PROCEDURES[0]) == 1, \
    "procedures skill text drifted from the install-carried paragraph"


def _installed(text: str, old_new: tuple[str, str]) -> str:
    old, new = old_new
    if text.count(old) != 1:
        raise ValueError("skill text drifted from the install-carried paragraph")
    return text.replace(old, new)


#: The skill texts were written for a harness with built-in procedures and shipped
#: procedure and reflex examples (each a hand-written skill); neither exists, so the
#: paragraphs that name them are rewritten.
#: (skill, old, new); each old text occurs exactly once in its skill.
_NO_PRIMITIVES_EDITS = (
    ("procedures",
     "how to compose the atoms into skills of the right grain",
     "how to build skills of the right grain from raw actions"),
    ("procedures",
     """The built-in set is the ATOMS (closed-loop aims and walks, the GUI cursor, one-call
craft, placements, the bucket, watch/pillar/eat/throw). Everything task-shaped you build
yourself as `mine/procedures/<name>.py` (the script contract is in the main contract).
This file says what a good one looks like.""",
     """This run has NO built-in procedures and ships no example procedure: every aim,
walk, dig, craft and fight is done with raw actions, or by a script of yours under
`mine/procedures/<name>.py` (the script contract and the closed loops are in
`references/own.md`). This file says what makes a script good, not which to write."""),
    ("procedures",
     "- A skill is 50-400 ticks of atoms that you would otherwise write out by hand every\n  turn: a staircase step, a tunnel segment with its torch, a GUI craft with its\n  verification, a bucket fill from a bank, a pour and a scoop at a pool.",
     "- A skill is 50-400 ticks of raw actions that you would otherwise write out by hand\n  every turn."),
    ("procedures",
     """- Compute targets from the state (your position, yaw, the hotbar) instead of asking the
  caller for coordinates; `skills/procedures/scripts/torch_wall.py` shows how.""",
     """- Compute targets from the state (your position, yaw, the hotbar) instead of asking the
  caller for coordinates.
- A plan-time script is blind once it starts; a closed loop (`LOOP = True`) reads the
  frame and the state every few ticks."""),
    ("procedures",
     """blaze rod. Write the phase skills for water/gravel/flint and for pour -> frame -> light
before you polish a staircase; those are the turns the budget rewards.""",
     "blaze rod."),
    ("procedures",
     """## Examples

`skills/procedures/scripts/stair_step.py` (one step of a staircase down along the
heading: foot block, head block, step in; guards on ground and pickaxe),
`skills/procedures/scripts/torch_wall.py` (a torch on the wall beside you, computed
from your pose), `skills/procedures/scripts/shaft_down.py` (straight down to a
target y in one call, ~20 ticks per level against a staircase's ~80) and
`skills/procedures/scripts/strip_segment.py` (a lit 1x2 tunnel, 4 blocks a call at
~45 ticks a block, every hold watched for ore) and
`skills/procedures/scripts/aim_speckles.py` (the answer to a sighting [NOTE]: crosshair
onto its pixel, mine the block, sweep the drop). Copy, rename, make them yours.

## Mining one block

A raw `{"attack": 1}` hold of 30 ticks. The runner cuts it the moment the block breaks
and refunds the rest (the [NOTE] says so), and the wall watcher samples every hold for
iron- and diamond-ore speckles: a sighting drops the rest of the plan with a [NOTE]
and the flag-time frame. `mine_ahead(n)` spends all n ticks whatever breaks -- it is
for continuous digging (a shaft), not for a block.

## A sighting outranks everything

`[NOTE] mining stopped: iron-ore-like (or diamond-ore-like) speckles on screen at (x, y)`
is the one event this life is waiting for, and it is perishable: the runner dropped the
rest of your plan so the view is still the flag-time view, and the next look or step
loses it. Your next plan is ONE call of `aim_speckles(x=<x>, y=<y>)` from
`skills/procedures/scripts/` (copy it into `mine/procedures/` in your first turn) --
before any look, any craft, any step of the schedule below. The life that found the
diamond did this within 20 steps of the [NOTE]; the lives that "finished the column
first" or went to craft something first never mined the ore. If the hold breaks
stone, the speckles were a block further in: hold again at the same aim.
""",
     """## Mining one block

A raw `{"attack": 1}` hold of 30 ticks. The runner cuts it the moment the block breaks
and refunds the rest (the [NOTE] says so). Nothing in the runner watches the walls for
ore in this run.
"""),
    ("reflexes",
     "the classes that killed earlier runs, the starters already installed, and how to keep or retire them",
     "how they run, an example, and how to keep or retire them"),
    ("reflexes",
     "reflex cannot be tried by hand -- write it from the class of danger, then refine it",
     "reflex cannot be tried by hand -- write it, then refine it"),
    ("reflexes",
     "for the reflexes whose answer is always the same (step back from lava).",
     "for the reflexes whose answer is always the same."),
    ("reflexes",
     REFLEXES_SKILL[REFLEXES_SKILL.index("## The classes, from what killed the earlier runs"):],
     """## The example

`skills/reflexes/scripts/ore_watch.py` is an example reflex: it reads `frame` and stops
the plan when diamond-ore speckles come into view below y 60. Nothing is installed for
you: `mine/reflexes/` is empty until you put a script there, and from then on it runs
every 4 ticks. Copy the example, change it, or leave it. At most 4 run, alphabetical;
to retire one, rename it with a leading underscore (`_name.py` stays off).
"""),
    ("harness",
     "built from the atoms, your own procedures and raw actions.",
     "built from raw actions and your own procedures (no built-in procedure exists in\nthis run)."),
    ("harness",
     "Does: execute plans, verify closed-loop atoms (aims, walks, GUI cursor), record",
     "Does: execute plans, measure the GUI cursor ([CURSOR]) and the grid ([GRID]), record"),
)

_NO_PRIMITIVES_EDITS += (
    ("procedures", PROCEDURES_SKILL[PROCEDURES_SKILL.index("\n## The budget, as a schedule"):],
     "\n"),
)

#: The one example script that ships beside the reflex skill (not installed). Raw keys
#: and the frame only; no harness code is imported.
REFLEX_EXAMPLES: dict[str, str] = {
    "ore_watch.py": '''"""ore_watch: diamond-ore speckles in the view below y 60 -- stop the plan and say where on screen."""
# Example reflex (harness-written, yours to copy, edit or ignore; nothing is installed for
# you). A procedure planned at turn time runs without looking, so ore that comes into
# view in the middle of it is gone by your next turn; a reflex sees `frame` every few
# ticks while the plan runs. This one reads the colour of diamond speckles on grey stone:
# cyan, with green and blue about equal and both well above red. Lapis, water and ice are
# bluer; a cyan that fills whole blocks (wool, prismarine) is a mass, where ore is a
# scatter of small dots. The numbers are a starting point measured on this game's frames
# -- tune them on the frames under episodes/ (the same picture, smaller) before trusting
# them. Iron is harder by colour alone: dim, warm-lit stone reads tan too, so the same
# test for iron fires on bare tunnel walls.
import json
import sys

import numpy as np
from PIL import Image

KINDS = ("diamond",)
MIN_PIXELS = 30          # speckle pixels for a sighting (at the frame's own size)
MAX_FILL = 0.35          # speckles cover a minority of their box: dots, not a mass
MAX_Y = 60               # only below this height


def bands(rgb: np.ndarray, kind: str = "diamond") -> np.ndarray:
    """The pixels whose colour is in the speckle band of `kind`."""
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    with np.errstate(divide="ignore", invalid="ignore"):
        br = (b - r) / np.maximum(b, 1.0)
        gr = (g - r) / np.maximum(g, 1.0)
        bg = (b - g) / np.maximum(b, 1.0)
        return ((br > 0.30) & (br < 0.80) & (gr > 0.36) & (gr < 0.80)
                & (np.abs(bg) <= 0.10) & (b > 48))


def look(path: str):
    """(kind, x, y, pixels) of an ore sighting in the picture, or None."""
    img = np.asarray(Image.open(path).convert("RGB"))
    body = img[: int(img.shape[0] * 0.82)]          # the hotbar and the hearts are not the world
    for kind in KINDS:
        m = bands(body, kind)
        n = int(m.sum())
        if n < MIN_PIXELS:
            continue
        ys, xs = np.nonzero(m)
        # the densest 64x64 window around the median, so two far-apart flecks do not add up
        cx, cy = int(np.median(xs)), int(np.median(ys))
        win = m[max(0, cy - 32):cy + 32, max(0, cx - 32):cx + 32]
        k = int(win.sum())
        if k < MIN_PIXELS:
            continue
        wy, wx = np.nonzero(win)
        box = (wy.max() - wy.min() + 1) * (wx.max() - wx.min() + 1)
        if k / box > MAX_FILL:
            continue
        return kind, cx, cy, k
    return None


if __name__ == "__main__":
    s = json.load(sys.stdin)
    pos = s.get("pos") or {}
    if not s.get("frame") or s.get("gui_open") or pos.get("y", 999) > MAX_Y:
        print("{}")
        sys.exit(0)
    hit = look(s["frame"])
    if hit is None:
        print("{}")
        sys.exit(0)
    kind, x, y, n = hit
    w, h = s.get("frame_size") or [None, None]
    print(json.dumps({"stop": True,
                      "note": f"{kind}-ore-like speckles at ({x}, {y}) of a {w}x{h} view, "
                              f"{n} px, while running {s.get('entry')}: the view is still "
                              f"the sighting view -- aim there before anything else"}))
''',
}

#: The contract paragraph (`--skills`), appended to the thin contract's tail.
SKILLS_NOTE = """\

**Skills.** `skills/<name>/SKILL.md` -- harness-written, immutable -- is the META layer
of this run: how to use your memory (`skills/memory`), what makes a script of the right
grain (`skills/procedures`), how reflexes run (`skills/reflexes`), how the loop and its
economics work and the do-not list (`skills/harness`). Read all four in your first turn.
Nothing is installed for you: `skills/reflexes/scripts/ore_watch.py` is an example you
may copy into `mine/reflexes/`, change or ignore, and `skills/memory/scripts/` holds
memory queries."""


SKILLS: dict[str, tuple[str, dict[str, str]]] = {
    "memory": (MEMORY_SKILL, EXAMPLE_MEMORY),
    "procedures": (PROCEDURES_SKILL, {}),
    "reflexes": (REFLEXES_SKILL, REFLEX_EXAMPLES),
    "harness": (HARNESS_SKILL, {}),
}


def write_skills(root: Path, carried_world: str = "same", installed: bool = False, *,
                 history_images: bool = True, flat_retrieval: bool = False,
                 pushed_memory: bool = True) -> list[str]:
    """Write `skills/` (once, like references/): the four SKILL.md and their example
    scripts (the memory queries and one reflex example). Nothing is installed under mine/:
    the model copies what it wants into mine/ itself. With `installed` the carried lives'
    own scripts were put in mine/ before this, and the memory and procedures skills say so
    instead of telling the model to copy them. `history_images`/`flat_retrieval` are the
    record ablations of the mfm arm: the texts say what the run keeps, and
    `death_sheet.py`, which tiles frames through the query tool, is left out where either
    is missing. Returns the paths written."""
    root = Path(root)
    written: list[str] = []
    for name, (text, scripts) in SKILLS.items():
        if name == "memory":
            text = memory_skill(carried_world)
            if installed:
                text = _installed(text, _COPY_MEMORY)
        elif name == "procedures" and installed:
            text = _installed(text, _COPY_PROCEDURES)
        for skill, old, new in _NO_PRIMITIVES_EDITS:
            if skill == name:
                if text.count(old) != 1:
                    raise ValueError(f"{name} skill text drifted from its no-primitives edit")
                text = text.replace(old, new)
        if name == "memory":
            text = ablate_memory_skill(text, images=history_images, flat=flat_retrieval,
                                       pushed=pushed_memory)
            if not history_images or flat_retrieval:
                scripts = {k: v for k, v in scripts.items() if k != "death_sheet.py"}
        elif name == "harness":
            text = ablate_harness_skill(text, images=history_images, flat=flat_retrieval,
                                        pushed=pushed_memory)
        scripts = {k: ablate_script(k, v, images=history_images, flat=flat_retrieval)
                   for k, v in scripts.items()}
        d = root / SKILLS_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        if not p.exists():
            p.write_text(text, encoding="utf-8")
            written.append(str(p.relative_to(root)))
        for fn, src in scripts.items():
            sp = d / "scripts" / fn
            sp.parent.mkdir(parents=True, exist_ok=True)
            if not sp.exists():
                sp.write_text(src, encoding="utf-8")
                written.append(str(sp.relative_to(root)))
    return written
