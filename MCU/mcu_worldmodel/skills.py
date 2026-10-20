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
                                    previous lives, the guide, the workshop turn
    skills/procedures/SKILL.md      the skill layer: the phase ladder, the right grain,
                                    guards, reuse; scripts/stair_step.py, torch_wall.py, shaft_down.py, strip_segment.py, aim_speckles.py
    skills/reflexes/SKILL.md        the reflex layer: write before the event, the six
                                    classes; the examples and how to retire one
    skills/harness/SKILL.md         the loop, the economics of turns vs steps, what the
                                    runner does and does not do in this run, the do-not
                                    list from the earlier runs

and, as EXAMPLES under `skills/reflexes/scripts/` (nothing is installed under
`mine/reflexes/`: the model copies what it wants, edits it, and a leading
underscore in the file name keeps a copied script off):

    lava_ahead.py   lava in the lower view while a walk or a dig moves you, or at a look: stop; in it, climb out
    fell.py         2+ blocks down within four ticks (a free fall): stop, look before moving
    hit.py          3+ health lost with no lava in view: a mob -- stop, pillar up 2 with a block carried
    starving.py     the food bar below 18 (no natural healing): eats what you carry, else a note

With `--no-harness-reflexes` the runner's own guards, escapes, governor and nudges are off
(as in `--human-play`) and the reflexes the model copies or writes are the whole tick layer.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path("skills")

# -- the reflex examples (skills/reflexes/scripts/; the model copies them into mine/reflexes/) --

STARTER_REFLEXES: dict[str, str] = {
    "lava_ahead.py": '''"""lava_ahead: lava in the lower view (1.5% below y 40 or in the Nether, 4% above) while a walk or a dig moves you, or at a look -- stop; in it, climb out. Flames are not lava."""
# Example reflex (harness-written, yours to edit or retire): the runs that died in lava
# were all MOVING toward it -- a go_to, a mine_ahead, a raw walk -- with the orange already
# in the frame, or stepped into a pool the camera had never looked at (a tunnel whose
# floor was missing). Three cases:
#   moving with lava in view        -> stop, step back 6 ticks
#   a look_abs/watch shows lava     -> stop, no step: the plan was about to walk there
#                                      (strip_segment looks at the next floor before each
#                                      step); a look with nothing queued after it is quiet
#   in the lava (lava damage with   -> stop and climb: back and jump; place a block under
#   the screen orange)                 you if you carry one
# Standing at a pool or a fire on purpose (fill_bucket, use_at, use_held, place_at) is
# exempt: the plan is there by design. A walk covers ~0.9 blocks between two samples, so
# the threshold is low where lava is close (underground, the Nether): a pool three blocks
# ahead reads 2-3% of the lower view; the surface threshold is higher so a distant lake
# does not stop every walk.
# FLAMES ARE NOT LAVA. A fire block (a portal just lit, a burning tree) and the flames
# drawn over the view while you burn share lava's orange, but they are brighter and
# yellower: `fire_frac` runs 5-15x `lava_frac` on flames and 0.3-0.5x on a lake. One life
# lit its portal from inside and this reflex's old in-lava escape pulled it back into the
# fire, where it died with the frame half built; another, burning on a bank, had every
# walk stopped. So flames are left to the plan (walk out, pour water), and the escape
# runs on lava's DAMAGE: lava takes 4 health every 10 ticks, fire 1 every 20, so between
# two samples (4 ticks) only lava takes 3 or more.
# BURNING BESIDE LAVA is the case the colours cannot settle: the overlay over a pool reads
# 1.5-2.5x (two lives burned to death 35 blocks from a stronghold while this reflex took
# the overlay for lava ahead, stepped one back into the pocket and stopped the other's
# climb out, 65 samples in all), and a pool one block away with no fire reads 1.0-1.3x.
# What does settle it is that you are being hurt: flames on screen and health lost in the
# last 100 ticks (`hurt_100`) is a burn, and the plan that is walking out of it is left
# to run. Unhurt, the same picture still stops you.
import json, math, sys
s = json.load(sys.stdin)
MOVING = {"go_to", "mine_ahead", "collect_drops", "raw"}
LOOKING = {"look_abs", "look", "look_at", "watch"}
ON_PURPOSE = {"fill_bucket", "use_at", "use_held", "place_at"}
p, q = s.get("pos"), s.get("pos_prev")
moved = math.hypot(p["x"] - q["x"], p["z"] - q["z"]) if p and q else 0.0
deep = bool(p) and (p["y"] < 40.0 or s.get("dimension") == "the Nether")
thr = 0.015 if deep else 0.04
frac, fire = s["lava_frac"], s.get("fire_frac", 0.0)
entry = s.get("atom") or s.get("entry")      # the atom inside an own procedure
lost = s.get("health_prev", 20) - s.get("health", 20)
flames = fire >= 0.12 and fire > 2.0 * frac      # the overlay flickers down to ~0.14 between flames
burning = fire >= 0.05 and fire > frac and s.get("hurt_100", 0.0) >= 1.0      # 0.06-0.07 between flames
in_lava = bool(s.get("in_lava")) or (lost >= 3.0 and frac >= 0.2)     # head under: the view is flat red, frac ~0
if entry in ON_PURPOSE:
    pass
elif in_lava and p and not s.get("gui_open"):
    block = next((h for h in s.get("hotbar", []) if h.get("item") in ("cobblestone", "dirt", "netherrack", "stone", "gravel")), None)
    acts = ([{"procedure": "equip_hotbar", "args": {"slot": int(block["slot"]) + 1}}] if block else []) + \
           [{"action": {"back": 1, "jump": 1, **({"use": 1} if block else {})}, "repeat": 10}]
    print(json.dumps({"stop": True,
                      "note": "IN LAVA at (%.0f, %.1f, %.0f), health %.0f: climbing out -- back and jump%s. "
                              "Then seal the pool with blocks before any step toward it"
                              % (p["x"], p["y"], p["z"], s.get("health", 0), " placing %s under you" % block["item"] if block else ""),
                      "actions": acts}))
elif flames or burning:
    pass          # a fire block or the burning overlay: the plan walks out of it or pours water
elif frac >= thr and entry in MOVING and (moved >= 0.1 or entry == "mine_ahead"):
    print(json.dumps({"stop": True,
                      "note": "lava fills %d%% of the lower view during %s -- stepped back 6 ticks; "
                              "seal the flow with a block or go around, never through"
                              % (round(100 * frac), entry),
                      "actions": [{"action": {"back": 1}, "repeat": 6}]}))
elif frac >= thr and entry in LOOKING and s.get("queue_len", 0) > 1:      # something queued after the look
    print(json.dumps({"stop": True,
                      "note": "lava fills %d%% of the lower view at a %s -- the plan was about to step there; "
                              "stopped before the step. Seal it (place_at cobblestone on the lava) or turn"
                              % (round(100 * frac), entry)}))
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
    "hit.py": '''"""hit: 3+ health lost in four ticks with no lava or flames in view -- a mob; stop, decide, act."""
# Example reflex: monsters are reported on no channel; the health drop is the only sign.
# A plan standing still under hits (a dig, a sweep, a click) is how most deaths began.
# The stop hands you the turn at zero game-clock cost: wall the tunnel (place_at), pillar
# up two blocks (pillar_up), or fight with the sword selected -- your call, made now.
# With a block in the hotbar it pillars up two blocks at once (pillar_up, an atom): most
# mobs cannot reach you there, and the turn is yours to wall off or fight. Not during a
# place_at or a use_at: the pillar swaps the hand to the block and leaves a column in
# the middle of what you were building (a portal frame, a wall).
import json, sys
s = json.load(sys.stdin)
lost = s.get("health_prev", s["health"]) - s["health"]
if lost >= 3.0 and s["lava_frac"] < 0.01 and s.get("fire_frac", 0.0) < 0.2 and not s.get("in_lava"):
    block = next((h for h in s.get("hotbar", []) if h.get("item") in ("cobblestone", "dirt", "netherrack", "stone", "gravel")), None)
    pillar = bool(block) and not s.get("gui_open") and (s.get("atom") or s.get("entry")) not in ("pillar_up", "place_at", "use_at")
    print(json.dumps({"stop": True,
                      "note": "took %.0f damage (health %.0f/20) with no lava in view: a mob is at you. "
                              "Do not keep digging or clicking -- %s"
                              % (lost, s["health"], "pillared up 2 blocks; wall off or fight from there" if pillar
                                 else "wall off, pillar up, or fight now"),
                      **({"actions": [{"procedure": "pillar_up", "args": {"n": 2}}]} if pillar else {})}))
''',
    "starving.py": '''"""starving: the food bar below 18 -- no natural healing from here; eats what you carry, else a note."""
# Example reflex: health regenerates only with the food bar at 18+, and this engine drains
# about one point per 4000 steps, so a life that never eats spends its second half unable
# to heal. Fires only when the bar has just dropped a point: with food carried it runs `eat`
# (one turn); with none it notes the crossing below 18 once; at health 10.5 with nothing to
# eat it stops the plan once. Never every tick.
import json, sys
s = json.load(sys.stdin)
f, fp = s.get("food", 20), s.get("food_prev", 20)
h, hp = s.get("health", 20), s.get("health_prev", 20)
FOODS = ("cooked_beef", "cooked_porkchop", "cooked_mutton", "cooked_chicken", "steak",
         "golden_apple", "bread", "cooked_cod", "cooked_salmon", "baked_potato", "apple",
         "carrot", "melon_slice", "cookie", "beef", "porkchop", "mutton", "chicken",
         "potato", "beetroot", "sweet_berries")
inv = s.get("inventory") or {}
food = next((k for k in FOODS if inv.get(k, 0) > 0), None)
if f < 18 and f < fp and food and not s.get("gui_open") and (s.get("atom") or s.get("entry")) != "eat":
    print(json.dumps({"actions": [{"procedure": "eat", "args": {"item": food}}],
                      "note": "food %.0f/20 with %s carried: eating (no natural healing below 18)"
                              % (f, food)}))
elif f < 18 and fp >= 18 and (s.get("atom") or s.get("entry")) != "eat":
    print(json.dumps({"note": ("food %.0f/20: no natural healing from here; eat the %s once the GUI is closed"
                               % (f, food)) if food else
                              ("food %.0f/20 and nothing to eat: no natural healing from here. "
                               "Any animal in view is one kill of food" % f)}))
elif h <= 10.5 and hp > 10.5 and f < 18 and not food:
    print(json.dumps({"stop": True,
                      "note": "health %.0f/20, food %.0f/20, nothing to eat: you cannot heal until "
                              "you eat" % (h, f)}))
''',
}

# -- example procedures (skills/procedures/scripts/) ---------------------------------------

EXAMPLE_PROCEDURES: dict[str, str] = {
    "stair_step.py": '''"""stair_step: one step of a staircase DOWN along the heading -- foot block, head block, step in."""
# Example procedure (harness-written; copy it to mine/procedures/ and make it yours). The
# grain a skill should have: one phase step, ~120 ticks, composed of atoms, with guards on
# the pose that made it work. A model-written north_stair (55 calls) is the same shape.
# One block = one raw {"attack": 1} hold of 30 ticks: the runner cuts it the moment the block
# breaks (the leftover ticks are refunded, a [NOTE] says so) and the wall watcher samples it
# for iron/diamond speckles (a [NOTE], the flag-time frame, the rest of the plan dropped).
# mine_ahead(n) would spend all n ticks on a block that breaks in 15.
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
        {"action": {"attack": 1}, "repeat": 30},
        {"procedure": "look_abs", "args": {"pitch": 8, "yaw": yaw, "ticks": 8}},
        {"action": {"attack": 1}, "repeat": 30},
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
    "shaft_down.py": '''"""shaft_down: dig straight down toward a target y (default 13), one call of up to ~370 ticks -- the dig_down recipe, from atoms."""
# Example procedure (harness-written; copy it to mine/procedures/ and make it yours).
# Why it exists: a hand-built staircase costs ~80 ticks per level of depth -- two lives on
# this chassis spent 3,500-4,000 steps going from y 66 to y 23 that way and
# reached diamond depth with under 900 steps left. Holding attack at pitch 88 bores a 1x1
# shaft instead: the floor breaks, you drop one block, the crosshair is already on the next
# floor block. Measured break times on stone: ~17 ticks with a stone pickaxe, ~13 with iron,
# plus ~5 while you fall (mining is slow in the air).
# mine_ahead does not stop on y, so the tick count is computed here from the depth still to
# go and the pickaxe. Ores and granite take longer (you stop short: call again); dirt and
# gravel are a little quicker (you run slightly ahead) -- so the count is also capped so that
# even all-soft blocks cannot take you below y 12. Lava lakes sit at y <= 10: standing at
# y 13 keeps two blocks of stone between your floor and a lake, y 12 keeps one.
# ore_watch=True: the wall watcher samples the view (here, the shaft walls and floor) and
# stops the dig on speckles, exactly as it samples a raw attack hold. Your lava_ahead and fell reflexes, if installed, stop it on lava in the
# lower view or a real drop. The way back up is pillar_up(n) with the cobblestone the shaft
# gave you; the shaft itself cannot be walked up.
import json, math, sys
PARAMS = {"target_y": "depth to stop at (default 13; never below 12)",
          "pick": "hotbar slot 1-9 holding the pickaxe (default: the best pickaxe in the hotbar)"}
# ticks per level with each pickaxe: (planned on stone, fastest on soft blocks)
SPEED = {"diamond_pickaxe": (15, 12), "iron_pickaxe": (18, 15),
         "stone_pickaxe": (22, 19), "wooden_pickaxe": (32, 20)}
MINE_CAP = 370                     # leaves room for the equip and the two looks in 400
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
p = s["pos"]
if p is None or s["gui_open"]:
    raise SystemExit("no position yet, or a screen is open")
if abs(p["y"] - round(p["y"])) > 0.05:
    raise SystemExit("not standing on solid ground (y %.2f)" % p["y"])
fx, fz = p["x"] - math.floor(p["x"]), p["z"] - math.floor(p["z"])
if not (0.29 <= fx <= 0.71 and 0.29 <= fz <= 0.71):
    raise SystemExit("standing across a block edge (x fraction %.2f, z fraction %.2f): the block under "
                     "your centre would break and leave you standing on its neighbour. Get inside one "
                     "block first -- walk into a wall for 4 ticks (it stops you 0.3 from its face), then "
                     "strafe into the side wall the same way" % (fx, fz))
target = max(12, int(args.get("target_y", 13)))
y = int(round(p["y"]))
if y <= target:
    raise SystemExit("already at y %d, at or below the target y %d -- mine level from here" % (y, target))
picks = [h for h in s["hotbar"] if h.get("item") in SPEED]
if args.get("pick") is not None:
    picks = [h for h in picks if int(h["slot"]) + 1 == int(args["pick"])]
if not picks:
    raise SystemExit("no pickaxe in the hotbar" + (" at slot %s" % args["pick"] if args.get("pick") else ""))
best = min(picks, key=lambda h: SPEED[h["item"]][0])
plan_tpb, soft_tpb = SPEED[best["item"]]
ticks = min(MINE_CAP, (y - target) * plan_tpb, (y - 12) * soft_tpb)
plan = [{"procedure": "equip_hotbar", "args": {"slot": int(best["slot"]) + 1}},
        {"procedure": "look_abs", "args": {"pitch": 88, "yaw": None, "ticks": 8}},
        {"procedure": "mine_ahead", "args": {"n": int(ticks), "ore_watch": True}},
        {"procedure": "look_abs", "args": {"pitch": 10, "yaw": None, "ticks": 8}}]
print(json.dumps({"actions": plan}))
''',
    "strip_segment.py": '''"""strip_segment: a lit 1x2 tunnel along the heading, up to 4 blocks per call -- the strip_mine recipe, from atoms."""
# Example procedure (harness-written; copy it to mine/procedures/ and make it yours).
# Why it exists: the tunnels the last lives wrote cost ~85 ticks per block of advance and
# spent all of a 45-tick mine_ahead on blocks that break in 15. This one costs ~45 ticks a
# block with an iron pickaxe, ~52 with stone: per block, aim at the head block and hold
# attack 30 (cut at the break), aim at the foot block and hold attack 30, look at the floor
# of the opened column for 4 ticks (pitch 65: the one look that shows a missing floor, a
# pool below it, or lava in the cell -- your lava_ahead and fell reflexes stop the plan
# there, BEFORE the step; two lives walked into pools the camera had never looked at),
# then walk 6 ticks into the new column (the next face stops you 0.3 from itself, which is
# the stance the aims assume). Every hold is watched for ore speckles; a sighting drops the
# rest of the plan with a [NOTE] -- convert it, then call again.
# Mine at y 12 or 13: lava lakes sit at y <= 10, this never touches the floor, and at y 13
# two blocks of stone separate your floor from a lake. light=true
# puts a torch on the LEFT wall first (torch_wall's geometry); every other call keeps a
# tunnel lit. Two 40-block strips with no sighting = a cold site: 3 blocks sideways, strip
# back parallel -- the area of NEW wall is what finds ore.
import json, math, sys
PARAMS = {"blocks": "columns to advance, 1-4 (default 4)",
          "light": "true: a torch on the left wall before advancing (default false)",
          "yaw": "heading (default: the current yaw, snapped to 90)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
p = s["pos"]
if p is None or s["gui_open"]:
    raise SystemExit("no position yet, or a screen is open")
if abs(p["y"] - round(p["y"])) > 0.05:
    raise SystemExit("not standing on solid ground (y %.2f)" % p["y"])
yaw = float(args.get("yaw", round(p["yaw"] / 90.0) * 90.0))
blocks = max(1, min(4, int(args.get("blocks", 4))))
picks = [h for h in s["hotbar"] if "pickaxe" in str(h.get("item", ""))]
if not picks:
    raise SystemExit("no pickaxe in the hotbar")
rank = {"diamond_pickaxe": 0, "iron_pickaxe": 1, "stone_pickaxe": 2, "wooden_pickaxe": 3}
pick = min(picks, key=lambda h: rank.get(h["item"], 9))
# across the tunnel you must be centred, or the aims hit the side wall
ry = math.radians(yaw)
across = (p["x"] - math.floor(p["x"])) if abs(math.cos(ry)) > 0.5 else (p["z"] - math.floor(p["z"]))
if not 0.25 <= across <= 0.75:
    raise SystemExit("off the tunnel's centre line (fraction %.2f across): strafe into the side wall "
                     "for 4 ticks and back 2, or walk the next column first" % across)
plan = [{"procedure": "equip_hotbar", "args": {"slot": int(pick["slot"]) + 1}}]
if args.get("light"):
    torch = next((h for h in s["hotbar"] if h.get("item") == "torch"), None)
    if torch is None:
        raise SystemExit("light=true but no torches in the hotbar")
    sy = math.radians(yaw - 90.0)
    dx, dz = -math.sin(sy), math.cos(sy)
    bx, bz = math.floor(p["x"] + dx * 1.0), math.floor(p["z"] + dz * 1.0)
    face = {(0, 1): "north", (0, -1): "south", (1, 0): "west", (-1, 0): "east"}[(round(dx), round(dz))]
    plan += [{"procedure": "equip_hotbar", "args": {"slot": int(torch["slot"]) + 1}},
             {"procedure": "place_at", "args": {"x": bx, "y": math.floor(p["y"]) + 1, "z": bz,
                                                "item": "torch", "face": face}},
             {"procedure": "equip_hotbar", "args": {"slot": int(pick["slot"]) + 1}}]
for _ in range(blocks):
    plan += [{"procedure": "look_abs", "args": {"pitch": 8, "yaw": yaw, "ticks": 6}},
             {"action": {"attack": 1}, "repeat": 30},
             {"procedure": "look_abs", "args": {"pitch": 48, "yaw": yaw, "ticks": 6}},
             {"action": {"attack": 1}, "repeat": 30},
             {"procedure": "look_abs", "args": {"pitch": 65, "yaw": yaw, "ticks": 4}},
             {"procedure": "watch", "args": {"n": 4}},
             {"action": {"forward": 1}, "repeat": 6}]
plan.append({"procedure": "look_abs", "args": {"pitch": 8, "yaw": yaw, "ticks": 6}})
print(json.dumps({"actions": plan}))
''',
    "aim_speckles.py": '''"""aim_speckles: turn the crosshair onto the (x, y) pixel a 'mining stopped: ...-ore-like speckles' [NOTE] names, then mine that block and sweep its drop."""
# Example procedure (harness-written; copy it to mine/procedures/ and make it yours).
# Why it exists: the life that found the diamond did exactly this within 20 steps of the
# watcher's [NOTE] -- aim at the speckles, mine the block under the crosshair, walk to the
# drop. Lives that answered a sighting with "finish the column first" or "craft a sword
# first" never mined the ore at all: by the next turn the view had moved and the speckles
# were gone. So: a sighting [NOTE] outranks everything; call this from its (x, y) BEFORE any
# other look or step, while the view is still the flag-time view (the runner dropped the
# rest of the plan for exactly that).
# The frame the watcher reads is 640x360 with a 70-degree vertical field of view: the focal
# length is 180 / tan(35 deg) = 257 px, so an offset of d pixels from the centre (320, 180) is
# atan(d / 257) degrees -- 104 px right is 22 degrees of yaw, not the 17 a linear scale gives.
# Two 30-tick holds: ore takes longer than stone, and the hold is cut the moment the block
# breaks anyway. collect_drops then sweeps the drop; the milestone is the PICKUP, not the break.
import json, math, sys
PARAMS = {"x": "screen x from the [NOTE] (0-640)", "y": "screen y from the [NOTE] (0-360)",
          "pick": "hotbar slot 1-9 with the pickaxe (default: the best in the hotbar)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
if s.get("gui_open"):
    raise SystemExit("a screen is open: close_inventory first")
if "x" not in args or "y" not in args:
    raise SystemExit("pass x and y: the pixel the sighting [NOTE] names, e.g. (424, 145)")
x, y = float(args["x"]), float(args["y"])
if not (0 <= x <= 640 and 0 <= y <= 360):
    raise SystemExit("x must be 0-640 and y 0-360 (the [NOTE]'s frame)")
rank = {"diamond_pickaxe": 0, "iron_pickaxe": 1, "stone_pickaxe": 2, "wooden_pickaxe": 3}
picks = [h for h in s["hotbar"] if h.get("item") in rank]
if args.get("pick") is not None:
    picks = [h for h in picks if int(h["slot"]) + 1 == int(args["pick"])]
if not picks:
    raise SystemExit("no pickaxe in the hotbar (diamond ore needs IRON or better to drop a diamond)")
pick = min(picks, key=lambda h: rank[h["item"]])
F = 180.0 / math.tan(math.radians(35.0))               # 257 px
dpitch = round(math.degrees(math.atan((y - 180.0) / F)), 1)   # + is down, like the screen
dyaw = round(math.degrees(math.atan((x - 320.0) / F)), 1)     # + is right, like the screen
plan = [{"procedure": "equip_hotbar", "args": {"slot": int(pick["slot"]) + 1}},
        {"action": {"camera": [dpitch, dyaw]}, "repeat": 1},
        {"action": {"attack": 1}, "repeat": 30},
        {"action": {"attack": 1}, "repeat": 30},
        {"procedure": "collect_drops", "args": {"ticks": 48}}]
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

EXAMPLE_REFLEXES: dict[str, str] = {
    "known_hazards.py": '''"""known_hazards: moving to within 6 blocks of a place your guide marks as lava or a death -- stop, say which."""
# Example reflex (harness-written; copy to mine/reflexes/ to arm it). The hazard list is
# YOURS: every line of mine/GUIDE.md that names lava, a pour or a death
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
for fn in ("mine/GUIDE.md", "logs.txt"):
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

SKILLS: dict[str, tuple[str, dict[str, str]]] = {
    "memory": (MEMORY_SKILL, EXAMPLE_MEMORY),
    "procedures": (PROCEDURES_SKILL, EXAMPLE_PROCEDURES),
    "reflexes": (REFLEXES_SKILL, {**EXAMPLE_REFLEXES, **STARTER_REFLEXES}),
    "harness": (HARNESS_SKILL, {}),
}

#: The contract paragraph (`--skills`), appended to the thin contract's tail.
SKILLS_NOTE = """\

**Skills.** `skills/<name>/SKILL.md` -- harness-written, immutable -- is the META layer
of this run: how to use your memory (`skills/memory`), how to compose skills of the
right grain (`skills/procedures`), which reflexes to write and why (`skills/reflexes`),
how the loop and its economics work and the do-not list (`skills/harness`). Read all
four in your first turn; `scripts/` beside them are working examples to copy into
`mine/`. No reflex is installed for you: `mine/reflexes/` is empty until you copy one
from `skills/reflexes/scripts/` -- do that in your first turn."""


#: The mfm-noprim arm: the run ships no procedure or reflex example (each is a hand-written
#: skill) and has no built-in procedure, so the paragraphs that name them are rewritten.
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

#: The mfm-noprim arm: the one example script that ships beside the reflex skill (not
#: installed). Raw keys and the frame only; no harness code is imported.
NO_PRIMITIVES_REFLEX_EXAMPLES: dict[str, str] = {
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

#: The mfm-noprim arm, the contract paragraph in place of SKILLS_NOTE.
SKILLS_NOTE_NO_PRIMITIVES = """\

**Skills.** `skills/<name>/SKILL.md` -- harness-written, immutable -- is the META layer
of this run: how to use your memory (`skills/memory`), what makes a script of the right
grain (`skills/procedures`), how reflexes run (`skills/reflexes`), how the loop and its
economics work and the do-not list (`skills/harness`). Read all four in your first turn.
Nothing is installed for you: `skills/reflexes/scripts/ore_watch.py` is an example you
may copy into `mine/reflexes/`, change or ignore, and `skills/memory/scripts/` holds
memory queries."""


def write_skills(root: Path, primitives: bool = True) -> list[str]:
    """Write `skills/` (once, like references/): the four SKILL.md and their example
    scripts, the reflex examples included. Nothing is installed under mine/: the model
    copies the reflexes it wants into mine/reflexes/ itself. Without `primitives` (the
    mfm-noprim arm) only the memory examples are written and the SKILL.md texts say so.
    Returns the paths written."""
    root = Path(root)
    written: list[str] = []
    for name, (text, scripts) in SKILLS.items():
        if not primitives:
            for skill, old, new in _NO_PRIMITIVES_EDITS:
                if skill == name:
                    if text.count(old) != 1:
                        raise ValueError(f"{name} skill text drifted from its no-primitives edit")
                    text = text.replace(old, new)
            if name != "memory":
                scripts = NO_PRIMITIVES_REFLEX_EXAMPLES if name == "reflexes" else {}
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
