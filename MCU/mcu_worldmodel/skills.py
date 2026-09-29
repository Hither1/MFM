"""`--skills`: the three-layer skill package the self-harness arm reads and owns.

The user's direction (2026-09-08 00:xx, after og14/og18/og19/og20): the model writes its
own harness -- the memory it keeps, the skills it composes, the reflexes that guard its
plans -- and the harness's part is META-level guidance per layer plus example code, packed
the way wz1119/Codex-Minecraft-Gameplay packs its play instructions: a `SKILL.md` per
skill with the doctrine, `scripts/` beside it with working examples. Nothing here is a
fact about this world (no coordinates, no sites -- the carry-only rule of 2026-09-07);
everything here is about how to play, how to remember, what to protect against.

What is written into the workspace, once per life, harness-owned and immutable:

    skills/memory/SKILL.md          using the multimodal memory: log, episodes, frames,
                                    previous lives, the digest, the workshop turn
    skills/procedures/SKILL.md      the skill layer: the phase ladder, the right grain,
                                    guards, reuse; scripts/stair_step.py, torch_wall.py
    skills/reflexes/SKILL.md        the reflex layer: write before the event, the six
                                    classes; the examples and how to retire one
    skills/harness/SKILL.md         the loop, the economics of turns vs steps, what the
                                    runner does and does not do in this run, the do-not
                                    list from the earlier runs
    skills/minecraft/SKILL.md       the game rules this 1.16-style world follows: tools,
                                    ore depths, hunger, water/lava, the portal, the Nether,
                                    endermen, the stronghold, the End (rules, no places)
    skills/mining/SKILL.md          the search doctrine for ore never seen: branch mining
                                    at the right y, spacing, torches, reading the face,
                                    when to change y, asking the memory where you looked

Since 2026-09-09 the skills are also codex-NATIVE: `.agents/skills/<name>` in the
workspace links each `skills/<name>` (and each `mine/skills/<name>` the model writes),
so codex lists them in the session's `## Skills` catalog with their `description:` and
triggers the one a turn's situation matches (codex 0.147 reads `$CODEX_HOME/skills` and
the workspace `.agents/skills`, verified 2026-09-09 under `--ignore-user-config`). With
`--session-turns 1` every turn is a fresh session, so the catalog is what survives.

and, as EXAMPLES under `skills/reflexes/scripts/` (nothing is installed under
`mine/reflexes/` since 2026-09-08: the model copies what it wants, edits it, and a leading
underscore in the file name keeps a copied script off):

    lava_ahead.py   lava in the lower view while a walk or a dig moves you: stop, step back
    fell.py         2+ blocks down within four ticks (a free fall): stop, look before moving
    hit.py          3+ health lost with no lava in view: source unknown -- stop, look, act
    burning.py      health falling with orange/fire in the view and no walk: on fire or in
                    lava -- stop; water at your feet or step back
    drowning.py     health falling with water over the view and no lava: under water --
                    stop; swim up or dig out
    starving.py     the food bar crossing below 18 (no natural healing): a note

With `--no-harness-reflexes` the runner's own guards, escapes, governor and nudges are off
(as in `--human-play`) and the reflexes the model copies or writes are the whole tick layer.
"""
from __future__ import annotations

import os
from pathlib import Path

SKILLS_DIR = Path("skills")

# -- the reflex examples (skills/reflexes/scripts/; the model copies them into mine/reflexes/) --

STARTER_REFLEXES: dict[str, str] = {
    "lava_ahead.py": '''"""lava_ahead: lava in the lower view (1.5% below y 40 or in the Nether, 4% above) while a walk or a dig moves you -- stop, step back."""
# Example reflex (harness-written, yours to edit or retire): a lava death is a MOVE
# toward it -- a go_to, a mine_ahead, a raw walk -- with the orange already in the frame. Standing at a pool on purpose (fill_bucket, use_held, place_at, watch) is
# not a walk, so those entries are exempt. A walk covers ~0.9 blocks between two samples,
# so the threshold is low where lava is close (underground, the Nether): a pool three
# blocks ahead reads 2-3% of the lower view; the surface threshold is higher so a distant
# lake does not stop every walk. Fire (flames on the screen after a burn) reads as lava
# too: leave the lava first, then this quiets.
import json, math, sys
s = json.load(sys.stdin)
MOVING = {"go_to", "mine_ahead", "collect_drops", "raw"}
p, q = s.get("pos"), s.get("pos_prev")
moved = math.hypot(p["x"] - q["x"], p["z"] - q["z"]) if p and q else 0.0
deep = bool(p) and (p["y"] < 40.0 or s.get("dimension") == "the Nether")
thr = 0.015 if deep else 0.04
if s["lava_frac"] >= thr and s.get("entry") in MOVING and (moved >= 0.1 or s.get("entry") == "mine_ahead"):
    print(json.dumps({"stop": True,
                      "note": "lava fills %d%% of the lower view during %s -- stepped back 6 ticks; "
                              "seal the flow with a block or go around, never through"
                              % (round(100 * s["lava_frac"]), s["entry"]),
                      "actions": [{"action": {"back": 1}, "repeat": 6}]}))
''',
    "fell.py": '''"""fell: 2+ blocks down within four ticks (a free fall of 3+) -- a drop the plan did not see; stop and look."""
# Example reflex: a hole under a walk, a ledge, a shaft. The plan that fell is wrong
# about the ground; the next move must come from a look, not from the rest of it. A
# walked staircase never drops more than a block in four ticks; free fall does after
# ~9 ticks (3+ blocks), whichever four-tick window the sample lands in.
import json, sys
s = json.load(sys.stdin)
p, q = s.get("pos"), s.get("pos_prev")
if p and q and q["y"] - p["y"] >= 2.0:
    print(json.dumps({"stop": True,
                      "note": "dropping %.1f blocks in four ticks, a fall, now at (%.0f, %.0f, %.0f) -- "
                              "look at four yaws before moving; go back up the way you came "
                              "(pillar_up, a stair), never onward"
                              % (q["y"] - p["y"], p["x"], p["y"], p["z"])}))
''',
    "hit.py": '''"""hit: 3+ health lost in four ticks with no lava in view -- the source is UNKNOWN (a mob behind you, an arrow, a fall, fire, water); stop, look, act."""
# Example reflex: monsters are reported on no channel; the health drop is the only sign,
# and it does not say what hit you; a note that assumes "a mob" is wrong when you are
# burning. The stop hands you the turn at
# zero game-clock cost: view the frame of the entry that took the hit (`[RECALL]` and the
# outcome cite it), then act on what you SEE: wall the tunnel or fight (a mob), step back
# and pour water at your feet (fire), swim up or dig out (water), look before moving (a
# fall). A plan standing still under hits (a dig, a sweep, a click) is how a death begins.
import json, sys
s = json.load(sys.stdin)
lost = s.get("health_prev", s["health"]) - s["health"]
if lost >= 3.0 and s["lava_frac"] < 0.01:
    print(json.dumps({"stop": True,
                      "note": "took %.0f damage (health %.0f/20) with no lava in view -- source unknown: "
                              "a mob, an arrow, a fall, fire or water. Look at the frame of this entry "
                              "before the next plan; do not keep digging or clicking"
                              % (lost, s["health"])}))
''',
    "burning.py": '''"""burning: health falling while orange (lava or flames) fills part of the view and you are NOT walking -- you are on fire or standing in lava; stop, water at your feet or back out."""
# Example reflex: standing IN lava or fire rather than walking into it: a pour that
# missed, a cap that broke, a fire lit by the flint. `lava_ahead` is silent
# then (no walk), `hit` says "a mob". The frame knows: `fire_frac` (flames drawn over
# the view) and `lava_frac` (orange in the lower view). No automatic step back: a
# blind step can go back INTO the lava you were climbing out of.
# Your move, now: use_at the block under your feet with water_bucket, or step the way
# you came, or pillar up one block out of the pool.
import json, math, sys
s = json.load(sys.stdin)
lost = s.get("health_prev", s["health"]) - s["health"]
p, q = s.get("pos"), s.get("pos_prev")
moved = math.hypot(p["x"] - q["x"], p["z"] - q["z"]) if p and q else 0.0
orange = max(s.get("lava_frac", 0.0), s.get("fire_frac", 0.0))
if lost >= 1.0 and orange >= 0.01 and moved < 0.5:
    bucket = any(h.get("item") == "water_bucket" for h in s.get("hotbar", []))
    print(json.dumps({"stop": True,
                      "note": "losing health (%.0f/20) with fire or lava in the view and no walk: you are "
                              "BURNING or standing in lava. %s Do not dig, do not click, do not wait."
                              % (s["health"],
                                 "Pour the water bucket at your feet (use_at water_bucket on the block "
                                 "below you), then step back the way you came." if bucket else
                                 "Step back the way you came, or pillar up one block out of it.")}))
''',
    "drowning.py": '''"""drowning: health falling with water filling the view and no lava -- you are under water; stop, swim up (hold jump) or dig sideways out."""
# Example reflex: a flooded shaft drowns a plan that keeps digging; the runner's note
# says "drowning reduced health" and does nothing about it.
# `water_frac` is the share of the view that reads as water (the frame is blue-tinted
# under the surface). Drowning takes 2 health a second once the air is gone; there is
# time for exactly one right move.
import json, sys
s = json.load(sys.stdin)
lost = s.get("health_prev", s["health"]) - s["health"]
if lost >= 1.0 and s.get("water_frac", 0.0) >= 0.30 and s["lava_frac"] < 0.01:
    print(json.dumps({"stop": True,
                      "note": "losing health (%.0f/20) under water: DROWNING. Hold jump to swim up, or "
                              "mine sideways into the wall and step in; nothing else until you breathe"
                              % s["health"],
                      "actions": [{"action": {"jump": 1}, "repeat": 20}]}))
''',
    "starving.py": '''"""starving: the food bar crossing below 18 -- no natural healing from here; a note. A STOP when health is low with no healing, or food is nearly gone."""
# Example reflex: health regenerates only with the food bar at 18+; a life at 2/20 with
# food 17 never heals, and the Nether with no food is a death with every tool. The note
# fires once at the
# crossing; the stop fires when the situation has become a decision -- health at or below
# 10 with no healing, or food at or below 6 -- and hands you the turn. Your call what to do.
import json, sys
s = json.load(sys.stdin)
f, fp = s.get("food", 20), s.get("food_prev", 20)
h = s.get("health", 20)
if (h <= 10 and f < 18 and s.get("health_prev", h) > 10) or (f <= 6 and fp > 6):
    print(json.dumps({"stop": True,
                      "note": "health %.0f/20 with food %.0f/20: you cannot heal from here. Eat if you carry "
                              "food; if not, this plan is over -- food first (animals, berries, fish), "
                              "then the rest" % (h, f)}))
elif fp >= 18 and f < 18:
    print(json.dumps({"note": "food %.0f/20: no natural healing below 18. Eat (the eat atom) if you carry "
                              "food; if not, food before the next descent -- animals, berries, fish"
                              % f}))
''',
}

# -- example procedures (skills/procedures/scripts/) ---------------------------------------

EXAMPLE_PROCEDURES: dict[str, str] = {
    "stair_step.py": '''"""stair_step: one step of a staircase DOWN along the heading -- foot block, head block, step in."""
# Example procedure (harness-written; copy it to mine/procedures/ and make it yours). The
# grain a skill should have: one phase step, ~120 ticks, composed of atoms, with guards on
# the pose that made it work.
import json, math, sys
PARAMS = {"yaw": "heading to dig along (default: the current yaw, snapped to 90)",
          "pick": "hotbar slot 1-9 holding the pickaxe (default: the first pickaxe found)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
p = s["pos"]
if p is None or s["gui_open"]:
    raise SystemExit("no position yet, or a screen is open")
if abs(p["y"] - round(p["y"])) > 0.05:
    raise SystemExit("not standing on solid ground (y %.2f)" % p["y"])
yaw = float(args.get("yaw", round(p["yaw"] / 90.0) * 90.0))
pick = args.get("pick")
if pick is None:
    hb = next((h for h in s["hotbar"] if "pickaxe" in str(h.get("item", ""))), None)
    if hb is None:
        raise SystemExit("no pickaxe in the hotbar")
    pick = int(hb["slot"]) + 1
plan = [{"procedure": "equip_hotbar", "args": {"slot": int(pick)}},
        {"procedure": "look_abs", "args": {"pitch": 47, "yaw": yaw, "ticks": 12}},
        {"procedure": "mine_ahead", "args": {"n": 40, "ore_watch": False}},
        {"procedure": "look_abs", "args": {"pitch": 8, "yaw": yaw, "ticks": 8}},
        {"procedure": "mine_ahead", "args": {"n": 40, "ore_watch": False}},
        {"procedure": "look_abs", "args": {"pitch": 60, "yaw": yaw, "ticks": 8}},
        {"action": {"forward": 1}, "repeat": 4},
        {"procedure": "watch", "args": {"n": 8}}]
print(json.dumps({"actions": plan}))
''',
    "torch_wall.py": '''"""torch_wall: place a torch on the wall beside you (computed from your pose), then look back along the heading."""
# Example procedure: a skill that COMPUTES its target from the state instead of asking
# for coordinates. The torch goes on the side face of the wall block to your left.
import json, math, sys
PARAMS = {"side": "'left' (default) or 'right'", "slot": "hotbar slot 1-9 with torches (default: found)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
p = s["pos"]
if p is None or s["gui_open"]:
    raise SystemExit("no position yet, or a screen is open")
slot = args.get("slot")
if slot is None:
    hb = next((h for h in s["hotbar"] if h.get("item") == "torch"), None)
    if hb is None:
        raise SystemExit("no torches in the hotbar")
    slot = int(hb["slot"]) + 1
yaw = round(p["yaw"] / 90.0) * 90.0
side = -90.0 if args.get("side", "left") == "left" else 90.0
sy = math.radians(yaw + side)
dx, dz = -math.sin(sy), math.cos(sy)          # the unit vector toward that side
bx, bz = math.floor(p["x"] + dx * 1.0), math.floor(p["z"] + dz * 1.0)
by = math.floor(p["y"]) + 1                   # the wall block at eye level's floor
face = {(0, 1): "north", (0, -1): "south", (1, 0): "west", (-1, 0): "east"}[(round(dx), round(dz))]
plan = [{"procedure": "equip_hotbar", "args": {"slot": int(slot)}},
        {"procedure": "place_at", "args": {"x": bx, "y": by, "z": bz, "item": "torch", "face": face}},
        {"procedure": "look_abs", "args": {"pitch": 8, "yaw": yaw, "ticks": 8}}]
print(json.dumps({"actions": plan}))
''',
}

# -- example memory script (skills/memory/scripts/) ----------------------------------------

EXAMPLE_MEMORY: dict[str, str] = {
    "death_sheet.py": '''"""death_sheet: the frames of the last 60 steps before the last death in logs.txt, tiled, with the notes that preceded it."""
# Example (harness-written; copy and adapt). Usage:
#   python skills/memory/scripts/death_sheet.py [death.png]
# Finds the last "YOU DIED" in logs.txt, prints the [NOTE]/[EVENT] lines of the 60 steps
# before it (the cause is usually in them: "took 4 damage", "LAVA AHEAD", "DOUSED"), and
# tiles the episode frames of that span into one image for view_image. Then write the
# one-line verdict into mine/digest.md yourself.
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
print(f"view_image {out}, then one line in mine/digest.md: step, place, cause, what you refuse next time")
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

EXAMPLE_REFLEXES: dict[str, str] = {
    "known_hazards.py": '''"""known_hazards: moving to within 6 blocks of a place your digest marks as lava or a death -- stop, say which."""
# Example reflex (harness-written; copy to mine/reflexes/ to arm it). The hazard list is
# YOURS: every line of mine/digest.md or mine/GUIDE.md that names lava, a pour or a death
# and carries a coordinate "(x, y, z)" or "(x, z)" counts. Same-life deaths are in
# logs.txt too ("YOU DIED at (x, y, z)"), so the list grows as you play. Fires only while
# you MOVE toward one (pos changed since the last sample), never while you stand and work
# at it on purpose (a pour, a bucket fill).
import json, re, sys
st = json.load(sys.stdin)
pos, prev = st.get("pos"), st.get("pos_prev")
if not pos or not prev:
    sys.exit(0)
if abs(pos["x"] - prev["x"]) + abs(pos["z"] - prev["z"]) < 0.3:
    sys.exit(0)                                   # standing still: not a walk
KEY = re.compile(r"lava|died|death|pour|obsidian", re.I)
XYZ = re.compile(r"\\((-?\\d+(?:\\.\\d+)?),\\s*(-?\\d+(?:\\.\\d+)?)(?:,\\s*(-?\\d+(?:\\.\\d+)?))?\\)")
spots = []
for fn in ("mine/digest.md", "mine/GUIDE.md", "logs.txt"):
    try:
        for ln in open(fn, encoding="utf-8", errors="ignore"):
            if fn == "logs.txt" and "YOU DIED" not in ln:
                continue
            if fn != "logs.txt" and not KEY.search(ln):
                continue
            for m in XYZ.finditer(ln):
                a, b, c = m.groups()
                x, z = (float(a), float(c)) if c is not None else (float(a), float(b))
                spots.append((x, z, ln.strip()[:90]))
    except OSError:
        pass
for x, z, why in spots:
    d = ((pos["x"] - x) ** 2 + (pos["z"] - z) ** 2) ** 0.5
    if d <= 6.0:
        print(json.dumps({"stop": True,
                          "note": f"known hazard {d:.1f} blocks away at ({x:.0f}, {z:.0f}): {why}"}))
        break
''',
}

# -- the SKILL.md texts --------------------------------------------------------------------

MEMORY_SKILL = """\
---
name: memory
description: Use on the first turn of a life that has previous/ (the workshop turn), after a death, after a hit you cannot explain, before walking to a remembered place, and when a plan has failed twice -- how to query the log, the episodes and their frames and the earlier lives, and what to write into mine/.
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
  `mine/` (its notes, digest and scripts). `./tools/episodes.py --previous ...` queries
  them all; `grep -n 'LAVA AHEAD\\|YOU DIED\\|obsidian' previous/life_*/logs.txt` is the
  fastest map of what they found and what killed them. The world resets between lives:
  terrain, water, lava and ore are where they were; nothing built or dropped survives;
  their step numbers are theirs.
- `mine/`: yours. `mine/notes.md` (what worked, what each script assumes),
  `mine/digest.md` (what you took from the earlier lives), `mine/procedures/`,
  `mine/reflexes/`, any data or images you save. Carried whole to your next life.

## The workshop turn

The first turn of a life with `previous/` is a WORKSHOP, not a play turn: read the
lives' digests, notes and death lines, run the query tool over them, write or update
`mine/digest.md` (verified places with coordinates and the life/step they come from,
what each life died of and where, which scripts and reflexes earned their keep and
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
and when a plan failed twice for a reason you cannot name. Look before the walk, not
after the stall.

## Working memory

`mine/working.md` is put in front of you every turn as `[WORKING]` and survives a
context reset: the plan you are on and why, its next visible prediction, the
contradictions you have not resolved, the entries and frames you would re-open (paths).
Rewrite it when the plan changes, under 40 lines. `mine/digest.md` / `mine/GUIDE.md`
is what is true of this world across lives; `working.md` is what you are doing now.

## Death forensics

After `YOU DIED`, before you rebuild anything: `./tools/episodes.py --steps <death-60>
<death> --sheet death.png --q "what killed me"`, view it, and write one line into
`mine/digest.md` (or `GUIDE.md`): step, place, cause, what you will refuse next time.
The frame tells a burn from a mob: flames over the lower view, orange at the feet. A
place written down as lava or a death is worth nothing until a reflex refuses to walk
into it. `skills/memory/scripts/death_sheet.py` does the tiling for the last death in
the log.

## Record every firing and every death

A reflex that fired, a fall, a hit, a death: one line in `mine/notes.md` with the step,
the place, the cause and what you changed. That line is what your next life reads
first. `skills/memory/scripts/where_was.py <keyword> [--previous]` is an example of a
memory query written as a script.
"""

PROCEDURES_SKILL = """\
---
name: procedures
description: Use before writing or calling a script of your own under mine/procedures/ -- the grain of a good skill, its guards, computing targets from the state, reusing the earlier lives' scripts under their own names, and when NOT to write one.
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
phase step, not one block and not the whole phase.

## The right grain

- A skill is 50-400 ticks of atoms that you would otherwise write out by hand every
  turn: a staircase step, a tunnel segment with its torch, a GUI craft with its
  verification, a bucket fill from a bank, a pour and a scoop at a pool.
- One-block scripts (break one stone, walk one block) are not skills: they cost a turn
  each to call and a turn each to check; a library of them moves a block at a time all
  night.
- Every script guards the pose it was tested from: heading, stable y, the tool in the
  hotbar, a screen closed. Raise SystemExit with the reason when a guard fails -- the
  note tells you what to fix, and nothing runs.
- Compute targets from the state (your position, yaw, the hotbar) instead of asking the
  caller for coordinates; `skills/procedures/scripts/torch_wall.py` shows how.
- Write a skill after the same sequence worked TWICE by hand; call it by name from then
  on. A script you never call again was a turn spent on nothing.

## Where the budget goes

The wooden and stone phases are short and the iron pickaxe is a few thousand steps; the
first diamond is the first long search. After the diamond tools the long stretches are
water, gravel, flint and the bucket, then obsidian -> frame -> a lit portal, then the
Nether without a blaze rod. Write the phase skills for water/gravel/flint and for pour ->
frame -> light before you polish a staircase; those are the turns the budget rewards.

## Reuse before rewrite

Your earlier lives' scripts are under `previous/life_<i>/mine/procedures/`. Read their
docstrings and notes in the workshop turn; copy the ones whose assumptions still hold
into `mine/procedures/` UNDER THEIR OWN NAMES (they are not copied for you; a rewrite
under a new name loses its call history). A script that failed in an earlier life has the
failure in that life's notes -- fix the assumption, do not rerun it.

## Examples

`skills/procedures/scripts/stair_step.py` (one step of a staircase down along the
heading: foot block, head block, step in; guards on ground and pickaxe) and
`skills/procedures/scripts/torch_wall.py` (a torch on the wall beside you, computed
from your pose). Copy, rename, make them yours.
"""

REFLEXES_SKILL = """\
---
name: reflexes
description: Use in the first turn of a life and after any reflex firing, fall, hit, burn or death -- the tick-level guards you write under mine/reflexes/, the classes of danger, the examples to copy, and how to keep or retire them.
---

# Reflexes

A procedure runs when you call it, between turns. What kills a life happens INSIDE a
plan, between one turn and the next: lava coming into view on a walk, a hole
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

## The classes

1. Lava in the lower view while a walk or a dig moves you.
2. A drop of 3+ blocks in a few ticks (holes, ledges, your own old shaft).
3. Health falling with no lava in view -- THREE different things, three different
   escapes: a mob you cannot see (wall off or fight), water over your head (swim up or
   dig out), fire on you or lava under you after a pour or a cap broke (water at your
   feet, step back the way you came). The frame at the hit tells which; do not assume
   a mob.
4. In the Nether, any walk with lava in view: every ledge ends in the lava sea at
   y ~31; sneak, never sprint, never jump while moving, dig the way down.
5. The food bar below 18: no natural healing.
6. Your only water bucket: pouring it as an elevator leaves you empty at the lava.
7. A walk toward a place where you, or an earlier life, died or saw lava. The cheapest
   reflex there is: read the hazard
   lines from `mine/digest.md`/`mine/GUIDE.md`, stop the plan when you come within 6
   blocks of one while moving. `skills/reflexes/scripts/known_hazards.py` is the example
   -- copy it into `mine/reflexes/` once your digest has coordinates in it.

## The examples

Under `skills/reflexes/scripts/`: `lava_ahead.py`, `fell.py`, `hit.py`, `burning.py`,
`drowning.py`, `starving.py` (classes 1, 2, 3, 3, 3, 5) and `known_hazards.py` (class 7).
The state a reflex reads carries `lava_frac`, `fire_frac` and `water_frac` (shares of
the view), `health`/`food`/`pos` and their `_prev`, the `entry` running, the hotbar. Nothing is installed for you:
`mine/reflexes/` is empty until you copy a script into it (`cp
skills/reflexes/scripts/lava_ahead.py mine/reflexes/`), and from then on it runs every 4
ticks. Decide in your first turn which to copy, edit their thresholds, write the Nether
one (class 4) before you go there. At most 4 run, alphabetical; to retire one, rename it
with a leading underscore (`_hit.py` stays off).
"""

HARNESS_SKILL = """\
---
name: harness
description: Use when you are unsure what the runner does for you, why a plan ended early, or how to spend turns against steps -- the loop, what is and is not guarded, the economics, and the do-not list.
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
that say "the runner did X for you" in `references/survival.md` describe the guarded mode;
here those are your reflexes' jobs.

## Economics

A turn costs about a minute of wall clock; a game step costs almost nothing. The run
ends at a step budget AND a wall-clock cap, and a life that checks after every block
hits the wall clock first. So:
plans that run long between turns beat plans that check after every block; a script
that saves a turn pays for itself on its second call; a workshop turn that writes a
skill you call twenty times is the best turn of the life.

## Do-not list

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


MINECRAFT_SKILL = """\
---
name: minecraft
description: Use when a stage of the task begins or a game rule is in doubt -- which tool mines what, where each ore generates, hunger and healing, water and lava, obsidian and the portal frame, the Nether and blazes, endermen and eyes of ender, the stronghold and the End. Rules of this 1.16-style world; it holds no places.
---

# Minecraft: the rules this world follows

Generation is 1.16-style: bedrock at y 0-4, sea level y 63, caves and ravines, lava lakes
underground with their surface at y 10 and on the surface. These are RULES, not places:
where things are in this seed is in your record and your earlier lives' logs, nowhere else.

## Tools and blocks
- Wood: punch a log (60-100 ticks). Planks -> sticks -> crafting table -> wooden pickaxe.
- Stone needs a wooden pickaxe or better; iron ore and lapis a STONE pickaxe or better;
  gold, diamond, redstone, emerald an IRON pickaxe or better; obsidian a DIAMOND pickaxe
  only (~190 ticks a block). A block mined with a lesser tool breaks and drops NOTHING.
- Furnace = 8 cobblestone; smelt iron ore with coal, charcoal (smelted logs), planks or
  logs. Iron pickaxe = 3 ingots + 2 sticks; bucket = 3 ingots; flint and steel = 1 ingot
  + 1 flint; shield = 6 planks + 1 ingot.
- Gravel lies in riverbeds and lake shores, on beaches, on cave floors and in pockets
  underground; it drops flint about 1 time in 10: dig it (shovel or hand), re-place, re-dig.
  The nearest water's edge beats a remembered gravel pocket far away.
- Torches = coal or charcoal + stick (4 a craft). Light stops monster spawns nearby.

## Ore depths (block y)
coal 5-128 (anywhere in stone); iron 1-63, most between 5 and 54; gold 0-31; redstone
0-15; lapis 0-30; diamond 1-15, best between 5 and 12. Standing with your feet at y 11
puts the lava-lake surface at your floor: lava shows as orange floor AHEAD, never above.

## Hunger and healing
- Food bar 20. Natural healing only at 18 or more; below 6 no sprint; at 0 you take damage.
  Health you cannot regain is the real cost of hunger.
- Food: cows, pigs, sheep, chickens (sword; raw meat, and the furnace doubles its value),
  sweet berries, apples from oak leaves, bread from wheat. Food is cheap on the surface and
  unobtainable underground: get it before the first descent, eat when the bar drops below 18.

## Water and lava
- Fill the bucket at STILL water (a source block). Pour, then scoop it back: the bucket
  refills from the pool you made.
- Water poured onto a lava SOURCE block makes obsidian; onto flowing lava, cobblestone.
  Obsidian from a pour stays until you mine it. A lava lake is source blocks: its edge is
  where a pour makes obsidian you can reach and mine with the diamond pickaxe.
- On fire or standing in lava: pour water on the block at your feet (use_at with
  water_bucket) or step back the way you came. Water is your fire extinguisher. In the
  Nether water evaporates -- there is none.
- Under water your air lasts ~15 s, then 2 damage a second: swim up (hold jump) or dig
  sideways into the wall and step in.

## The portal
- Frame: obsidian, 4 wide x 5 tall, corners optional -> 10 blocks; the INSIDE is 2 wide x
  3 tall of AIR, upright. Light it with flint and steel used on the inner face of a bottom
  frame block. One wrong or missing frame block, or any block inside, and it will not light.
- A frame is geometry, and geometry is checked by looking, not by counting placements:
  before igniting, look at the whole frame from a few blocks away and see 4x5 with a 2x3
  hole. Write the portal's coordinates into mine/digest.md -- it is the way home.

## The Nether
- Go in healthy and fed, with the portal noted; when health runs low there, the portal is
  the way to heal, not another step forward. A death there loses every tool to a place
  you cannot walk back to.
- Netherrack is everywhere: mine one block and pick it up (a milestone). The exit portal
  stands on a random ledge: note its position at once.
- The lava sea is at y ~31 with lava falls above it: sneak, never sprint, never jump while
  moving, bridge with cobblestone, dig down rather than walk down.
- A fortress is dark red nether brick, bridges and corridors; blazes spawn in it (spawners
  and open brick areas). Blazes fly, shoot fire, drop 0-1 blaze rod each: sword from behind
  cover or a bow; keep health above 12 there, their fire hurts.
- Ghasts (white, floating) shoot fireballs; break line of sight or hit the ball back.
  Zombified piglins are neutral until you hit one.

## Endermen, eyes, the stronghold
- Endermen: tall, black, purple eyes; spawn in the dark (overworld night, Nether warped
  forests) and everywhere in the End; looking at their eyes angers them; they teleport.
  A carved pumpkin worn on the head stops them taking offence. Fight one from under a
  2-block ceiling so it cannot reach you. Drop 0-1 ender pearl.
- 1 blaze rod -> 2 blaze powder; blaze powder + ender pearl -> eye of ender. A thrown eye
  flies toward the nearest stronghold and is used up (about 1 in 5 shatters): carry spares.
  When it climbs, the stronghold is far that way; when it sinks, it is under you.
- The stronghold is stone brick; its portal room holds 12 frames around a lava pit, some
  already filled, with a silverfish spawner nearby. An eye is placed by using it on a frame.

## Deaths, beds and the way back
- Dying sends you to your respawn point with nothing; what you carried lies where you fell
  for about five minutes (6,000 ticks). The respawn point is the world spawn until a BED
  changes it: a bed (3 wool + 3 planks; wool from sheep, which are also food) placed and
  slept in makes that spot your respawn. A bed at the mine or at the portal turns a death
  into a walk back instead of a new life; every death so far was a new life. Sleeping also
  skips the night, when monsters spawn on the surface.
- Falls of more than three blocks hurt, landing in water does not. Creepers hiss before
  they explode: back away. Skeletons shoot: break their line of sight. Spiders climb walls.
  Zombies burn in daylight. Armour halves what hits you (an iron chestplate is 8 ingots);
  a shield held up blocks arrows and fireballs.

## The Nether, in more detail
- Distance: one block there is eight in the Overworld. The portal you arrived through is the
  way home; a portal built far from it comes out somewhere else.
- Piglins attack anyone not wearing a piece of GOLD armour (golden boots = 4 gold ingots;
  gold ore is common there); zombified piglins are neutral until hit; hoglins charge;
  wither skeletons in the fortress hit hard; magma cubes bounce; soul sand slows you.
- Blazes hover, spit fire in bursts of three and drop 0-1 rod: fight from cover with a
  shield up, strike when they come down, keep health high. Fire keeps burning after the
  hit and there is no water there: step out of it and wait, and do not fight while burning.
- Ghast fireballs can be knocked back; a ghast's fire breaks netherrack around you.

## Bows, arrows, armour
- Bow = 3 sticks + 3 string (string from spiders at night, or cobwebs); arrow = flint +
  stick + feather (feathers from chickens). Both are the safe way to break end crystals,
  and the sword-free way to hurt what flies.

## The End, in more detail
- The void: falling off the island loses everything, for good. The arrival platform is
  obsidian near x 100, z 0 and may stand off the island: bridge with blocks. End stone is
  the pale ground (mine one and pick it up: a milestone).
- The dragon heals only while crystals stand. They sit on the obsidian pillars, some inside
  iron cages: break the bars first, then the crystal from a distance (bow) or from the
  pillar top behind a block -- the explosion hurts. The dragon perches on the bedrock
  fountain in the centre: hit its head. Its breath lingers as purple smoke; its wings knock
  you into the air: stay low, keep blocks, food and health.
"""

MINING_SKILL = """\
---
name: mining
description: Use when the next milestone needs an ore you have never seen (iron, diamond) and no life recorded a place for it -- how a search differs from a dig, where ore generates, how to expose many blocks per step, how to read a face before breaking it, when to change depth or direction, and how to ask your memory where you already looked. Principles and game facts, not a recipe.
---

# Mining: finding ore is a search, not a dig

Cutting one or two cells at a time and looking at each face is a dig, not a search, and
the slowest road to a first diamond there is. A search exposes many blocks per step; a
dig exposes two. How you search is your call; what follows is what any experienced
player knows.

## Where ore is (game facts)
- Diamond generates at block y 1-15, most between 5 and 12. Iron at y 1-63, gold 0-31,
  redstone 0-15, lapis 0-30, coal anywhere in stone. Underground lava lakes have their
  surface at y 10: standing with your feet at y 11 puts them at floor level, visible as
  orange ahead rather than opening under you.
- Exposed rock shows ore for free: cliff faces, ravine walls and cave walls near the surface
  are where iron is usually first seen. A cave at y <= 16 exposes hundreds of blocks per
  hundred steps; a tunnel exposes a handful. Caves bring mobs and holes with them.

## Principles
- Expose, then look, then break. A face you have not looked at is a block you are breaking
  blind. At 320x180 an ore is a speckled block: coal black specks, iron beige/tan, gold
  yellow, redstone red, lapis deep blue, diamond pale cyan. When a texture is unclear,
  `view_image` the frame or `tools/zoom.py` a crop before mining it: a block mined with
  the wrong pickaxe drops nothing, and orange means lava.
- Cover volume, not distance. Parallel tunnels a couple of blocks apart expose every block
  between them; one long tunnel exposes only its own walls. Whatever pattern you choose,
  know how much stone it has shown you and at which depth.
- Evidence decides depth and heading. Ore is where you have not yet looked: many blocks of
  bare stone at one depth and one heading is a reason to change one of them, not to
  continue.
- Make plans that do a segment and check once, not a block and check every time: a plan
  entry that changes nothing is a turn spent for nothing. A staircase you can walk back up
  beats a shaft you cannot climb.
- Budget before you go down: light for the way back, blocks to bridge or wall, a spare
  tool, food, the water bucket. The way back is part of the plan, not an afterthought.

## Asking your memory where you looked
`./tools/episodes.py --y-profile` shows the steps you spent per y band; `--ores` lists every
ore you saw or mined with its frame; `--previous` adds the earlier lives. One digest line per
branch ("branch W from (x, z) at y 11, 30 blocks, no ore") is what your next life needs; a
record without it is a list of steps.

## Stalls
A long plan that moved you nowhere, or several plans in a row that changed nothing, is a
stall, not persistence; the `[RECALL]` block names it. Change the target, the tool or the
place, and say what is different.
"""

SKILLS: dict[str, tuple[str, dict[str, str]]] = {
    "memory": (MEMORY_SKILL, EXAMPLE_MEMORY),
    "procedures": (PROCEDURES_SKILL, EXAMPLE_PROCEDURES),
    "reflexes": (REFLEXES_SKILL, {**EXAMPLE_REFLEXES, **STARTER_REFLEXES}),
    "harness": (HARNESS_SKILL, {}),
    "minecraft": (MINECRAFT_SKILL, {}),
    "mining": (MINING_SKILL, {}),
}

#: The contract paragraph (`--skills`), appended to the thin contract's tail.
SKILLS_NOTE = """\

**Skills.** The `## Skills` catalog of your session lists `skills/<name>` (harness-written,
immutable: `memory`, `procedures`, `reflexes`, `harness`, `minecraft`, `mining`) and
`mine/skills/<name>` (yours). A situation that matches a skill's description triggers it:
read its SKILL.md that turn and do what it says. `scripts/` beside each are working
examples to copy into `mine/`. No reflex is installed for you: `mine/reflexes/` is empty
until you copy one from `skills/reflexes/scripts/` -- do that in your first turn."""

#: Codex's workspace skill root (codex 0.147 lists `$CODEX_HOME/skills` and `<cwd>/.agents/skills`).
CATALOG_DIR = Path(".agents") / "skills"
#: The model's own skills: `mine/skills/<name>/SKILL.md`, carried with mine/ to the next life.
OWN_SKILLS_DIR = Path("mine") / "skills"


def sync_skill_catalog(root: Path) -> list[str]:
    """Make `.agents/skills/<name>` point at every `skills/<name>` (harness) and every
    `mine/skills/<name>` that holds a SKILL.md (the model's own), and drop dangling links.
    Relative symlinks, so the workspace moves whole. Called after write_skills and at the
    start of every turn (a skill the model wrote this turn is in the catalog next turn --
    with `--session-turns 1` that is the next session). Returns the names linked."""
    root = Path(root)
    cat = root / CATALOG_DIR
    cat.mkdir(parents=True, exist_ok=True)
    wanted: dict[str, Path] = {}
    for base in (root / SKILLS_DIR, root / OWN_SKILLS_DIR):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "SKILL.md").is_file() and d.name not in wanted:
                wanted[d.name] = Path("..") / ".." / base.relative_to(root) / d.name
    for link in cat.iterdir():
        if link.is_symlink() and (link.name not in wanted or not link.exists()):
            link.unlink()
    for name, target in wanted.items():
        link = cat / name
        if link.is_symlink():
            if os.readlink(link) == str(target):
                continue
            link.unlink()
        elif link.exists():
            continue                    # a real directory the model made: leave it
        link.symlink_to(target, target_is_directory=True)
    return sorted(wanted)


def write_skills(root: Path) -> list[str]:
    """Write `skills/` (once, like references/): the four SKILL.md and their example
    scripts, the reflex examples included. Nothing is installed under mine/: the model
    copies the reflexes it wants into mine/reflexes/ itself. Returns the paths written."""
    root = Path(root)
    written: list[str] = []
    for name, (text, scripts) in SKILLS.items():
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
    sync_skill_catalog(root)
    return written
