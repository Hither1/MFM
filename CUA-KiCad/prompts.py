"""Prompt templates for the memory-guided MLLM search framework."""

import textwrap

# ---------------------------------------------------------------------------
# ARC-AGI game prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are playing a grid puzzle game. Discover the rules by trying actions and observing changes.
    Describe only what happens on the grid — colors, positions, movements. No real-world devices.
""")
# in the TOP-RIGHT area
# in the BOTTOM-LEFT area
INIT_USER_TEMPLATE = """\
{frame_text}

{action_checklist}

Look at the grid image. List each colored element you see (name its exact color and location).
Then write one hypothesis per element and per action, using this format:
    HYPOTHESIS: <one sentence about what this element does or what this action does>
    CONFIDENCE: <0.1–1.0>
    DEPENDS_ON: [H0, H3] <only if this hypothesis can't be true unless another hypothesis \
above it is also true — reference its [Hn] id(s). Omit this line if there's no dependency.>

Write your first action name on the last line.
"""

LOGIC_USER_TEMPLATE = """\
{memory_text}

{frame_text}
{undertested_text}
Look at the grid image. Answer briefly:
1) Any new visual element not in hypotheses above? If yes: HYPOTHESIS: <what> CONFIDENCE: <0-1> \
DEPENDS_ON: [Hn, ...] (only if it can't be true unless another hypothesis above is also true; \
omit otherwise). If no: "No new hypotheses."
2) For each WIN_CONDITION: is it MET or NOT MET in the image?
3) What is your immediate next goal?
"""

SPATIAL_USER_TEMPLATE = """\
{memory_text}

{frame_text}

Reasoning: {logic_text}

For each action, predict what the grid will look like after. Which action gives the best result?
"""

ACTIVE_REGION_USER_TEMPLATE_LEGACY = """\
Look at this grid image. Some puzzle screens have a legend, border decoration, \
or repeated HUD elements in one part of the image, separate from the actual \
group of clickable game blocks the player interacts with.

Identify where the real clickable blocks are (ignore legends/decorations \
elsewhere in the image): what part of the image are they in, and what color \
are they?

Answer in exactly this format:
ZONE: <top-left / top-center / top-right / center-left / center / center-right / bottom-left / bottom-center / bottom-right / whole image>
COLOR: <the color name of the clickable blocks, or "none" if there is no distinct group>
"""

# ft09-only variant: ft09 shows several visually identical quadrants where
# only one is active, so (unlike the legacy template above) it must ask for
# the active group's border/outline rather than its tile colors — tile color
# can't discriminate look-alike quadrants and isn't even stable once clicking
# toggles it. Kept as a per-game override (ACTIVE_REGION_TEMPLATE_BY_GAME)
# instead of changing the shared template, since that change previously
# regressed vc33's click calibration (it has no repeated-quadrant ambiguity
# and no border/outline to report, so asking it for BORDER instead of COLOR
# produced worse active-region detection and, downstream, much less reliable
# ACTION-phase formatting — confirmed comparing run 31049665 (COLOR, 0 failed
# coordinate parses) against run 31478333 (BORDER, 155/187 steps fell back to
# a blind (32, 32) guess).
ACTIVE_REGION_USER_TEMPLATE = """\
Look at this grid image. Some puzzle screens have a legend, border decoration, \
or repeated HUD elements in one part of the image, separate from the actual \
group of clickable game blocks the player interacts with. Some screens also \
show several visually similar groups of tiles (e.g. repeated quadrants) where \
only ONE is currently active/interactive — that active group is normally set \
apart by a distinct border or outline around it, not by its tile colors, since \
look-alike groups can share the same tile colors and a group's own tile colors \
can change during play.{toggle_note}

Identify the currently active group of clickable blocks (ignore legends, \
decorations, and any other inactive look-alike groups elsewhere in the \
image): what part of the image is it in, and what color is the border/\
outline around it?

Answer in exactly this format:
ZONE: <top-left / top-center / top-right / center-left / center / center-right / bottom-left / bottom-center / bottom-right / whole image>
BORDER: <the color name of the border/outline around the active group, or "none" if there is no distinct group>
"""

# Per-game overrides of ACTIVE_REGION_USER_TEMPLATE_LEGACY. Falls back to the
# legacy COLOR-based template for any game_id not listed here.
ACTIVE_REGION_TEMPLATE_BY_GAME: dict[str, str] = {
    "ft09": ACTIVE_REGION_USER_TEMPLATE,
}

# Appended to ACTIVE_REGION_USER_TEMPLATE's {toggle_note} slot for games with a
# known click-to-toggle tile mechanic, so the model doesn't mistake a tile's
# current color for a stable identifying feature of its group. Told directly
# for now rather than left for the agent to infer from exploration.
ACTIVE_REGION_TOGGLE_NOTES: dict[str, str] = {
    "ft09": (
        " In this game, clicking a tile in the active group toggles its "
        "color between red and blue."
    ),
}

ACTION_USER_TEMPLATE = """\
{memory_text}

{frame_text}
{predicted_image_note}
{exploration_note}{test_directive}{strategic_directive}Reasoning: {logic_text}
Spatial: {spatial_text}

{strategic_action_instruction}{final_instruction}
"""

# Used when a click/coordinate action (e.g. ACTION6) is available. Forces the
# model to ground its click in a named visual element before committing to
# coordinates, instead of guessing numbers straight from the prompt syntax.
ACTION_COORD_INSTRUCTION = """\
Choose one action. If it is a click/coordinate action (e.g. ACTION6), first name the \
specific colored element or tile you want to click (its color and location). If the \
grid has nested structure (e.g. quadrants, or a panel containing its own sub-grid), \
ALWAYS state which level a position word like "top-left" or "center" refers to — e.g. \
"the blue block in the top-left QUADRANT OF THE WHOLE GRID" vs. "the tile in the \
top-left OF THE ACTIVE PANEL'S OWN 3x3 GRID" vs. "the top-left sub-cell OF THE LEGEND \
PATTERN". The same word means different things at different levels, so never leave \
the level unstated. Then estimate its (x, y) grid coordinates (each 0-63) from the \
image. Keep the reasoning to one or two sentences, then end your reply with exactly \
one line in this form:
Action: ACTION6 {x} {y}
"""

ACTION_SIMPLE_INSTRUCTION = "Choose one action. Write ONLY the action name (e.g. ACTION1):"

# ft09-specific: the 8 clickable tiles are already enumerated above as
# ACTION_EFFECT hypotheses (with their row/col ranges), so the model doesn't
# need to re-derive the layout from the image — it just needs to apply the
# legend's per-position rule to pick which of those 8 regions to click.
ACTION_COORD_INSTRUCTION_FT09 = """\
Choose one action. The active quadrant's 8 clickable tiles are already listed above as \
ACTION_EFFECT hypotheses, each with its row/col range. Using the legend's per-position \
rule, pick the one tile that still needs to change color, then give its (x, y) \
coordinates (each 0-63) as the center of that tile's row/col range.

Start your reply with exactly this line:
Action: ACTION6 {x} {y}
Then, in one short sentence at most, name which tile you picked and why. Nothing else.
"""

# Per-game overrides of ACTION_COORD_INSTRUCTION. Falls back to the generic
# instruction for any game_id not listed here.
ACTION_COORD_INSTRUCTION_BY_GAME: dict[str, str] = {
    "ft09": ACTION_COORD_INSTRUCTION_FT09,
}

UPDATE_USER_TEMPLATE = """\
Action taken: {action_name}
Before: {prev_frame_text}
After: {new_frame_text}
{player_context}

{memory_text}
{level_note}
For each hypothesis, write one line:
  CONFIRM: [Hx] reason
  CONTRADICT: [Hx] reason
  IRRELEVANT: [Hx]
"""

# ft09-only variant: asks the model to record a DEPENDS_ON link from any newly
# observed effect back to the ACTION_EFFECT hypothesis of the action that
# revealed it, so the DAG frontier/test-directive logic has real prerequisite
# edges to work with instead of every hypothesis being a depends_on-less leaf.
# Kept as a per-game override (see ACTION_COORD_INSTRUCTION_BY_GAME) rather
# than changing UPDATE_USER_TEMPLATE globally.
UPDATE_USER_TEMPLATE_FT09 = """\
Action taken: {action_name}
Before: {prev_frame_text}
After: {new_frame_text}
{player_context}

{memory_text}
{level_note}
For each hypothesis, write one line:
  CONFIRM: [Hx] reason
  CONTRADICT: [Hx] reason
  IRRELEVANT: [Hx]

If {action_name} caused something new — a tile changed, a block moved, a gate opened, \
a rule you hadn't noticed before — that isn't covered by any hypothesis above, write:
  HYPOTHESIS: <what happened and why, one sentence>
  CONFIDENCE: <0.1-1.0>
  DEPENDS_ON: [Hn] <id(s) of the hypothesis/es this required to be true. This new effect \
was only just observed because {action_name} was taken — ALWAYS include the [Hn] id of the \
ACTION_EFFECT hypothesis for {action_name} (listed above) in this list, plus any other \
prerequisite hypothesis ids. Omit this line only if the effect truly has no action or \
prerequisite behind it.>
If nothing new happened, skip this.
"""

# Per-game overrides of UPDATE_USER_TEMPLATE. Falls back to the generic
# template for any game_id not listed here.
UPDATE_USER_TEMPLATE_BY_GAME: dict[str, str] = {
    "ft09": UPDATE_USER_TEMPLATE_FT09,
}


# Any win-condition hypothesis should be marked CONTRADICT (the condition was not enough to win).

_LEVEL_NOT_ADVANCED_NOTE = """\
LEVEL NOT COMPLETED. 
"""

PRUNE_USER_TEMPLATE = """\
The following hypotheses have low confidence and need attention:
{low_conf_list}

For each, either REWRITE it (New: <revised text>) or DROP it (<reason>).
Then continue with the current state (grid shown as image above).

{frame_text}
"""


FILL_SPATIAL_PROBE_TEMPLATE = """\
Describe every colored element you see in the grid image. For each element, state:
- Its exact color (e.g. red, blue, yellow)
- Its location (e.g. top-left, bottom edge, center) — if the grid is divided into \
quadrants/panels, or a panel contains its own sub-grid or legend, ALWAYS say which \
level the location is relative to: the whole grid, a specific quadrant/panel, or a \
sub-grid/legend nested inside one. Never write a bare "top-left" etc. when more than \
one level exists — say "top-left of the whole grid" or "top-left of the active \
panel's own grid", not just "top-left".
- Its shape (e.g. arrow, cross, bar, square)
"""

FILL_HYPOTHESES_TEMPLATE = """\
Already known:
{covered_list}
{description_section}
Look at the grid image. Find any visual element NOT listed above.
For each new element, write:
    HYPOTHESIS: <what this element is and what it does — use exact colors>
    CONFIDENCE: <0.1–1.0>
    DEPENDS_ON: [H0, H3] <only if this hypothesis can't be true unless another hypothesis \
above it is also true — reference its [Hn] id(s). Omit this line if there's no dependency.>

If everything is covered, write one hypothesis about game mechanics (how to win, penalties, etc.).
"""


# ---------------------------------------------------------------------------
# Seed hypotheses — oracle knowledge injected before the agent starts.
# Keyed by game ID.  Each entry: list of (text, confidence, type_str, depends_on_indices).
# type_str is one of: ACTION_EFFECT, WIN_CONDITION, COMPONENT_ROLE, CAUSAL_RULE.
# depends_on_indices is an optional list of 0-based indices into this same list,
# indicating which other seeds this hypothesis depends on.
# ---------------------------------------------------------------------------

SEED_HYPOTHESES: dict[str, list[tuple[str, float, str] | tuple[str, float, str, list[int]]]] = {
    "ls20": [
        (   # index 0
            "The orientation of the blue arrow at the bottom-left corner "
            "needs to be aligned with the direction of the blue "
            "arrow on the gate.",
            0.95,
            "WIN_CONDITION",
        ),
        (   # index 1
            "Stepping on the white '+' tile rotates the direction of the blue "
            "arrow at the bottom-left corner by 90 degrees.",
            0.95,
            "CAUSAL_RULE",
        ),
        (   # index 2 — depends on aligning arrow (0) and knowing '+' rotates (1)
            "After the orientation of the blue arrow at the bottom-left corner is "
            "aligned with the direction of the blue arrow on the gate, the agent "
            "should walk to the gate to complete the level.",
            0.95,
            "WIN_CONDITION",
            [0, 1, 3],
        ),
        (   # index 3
            "The blue arrow pattern (wherever it appears on the map — its "
            "position varies by level) is the gate: identify it by the blue "
            "arrow icon and by it being walkable/connected in the maze from "
            "the player, not by a fixed screen location.",
            0.95,
            "COMPONENT_ROLE",
        ),
        (   # index 4 — depends on knowing about '+' rotation (1)
            "When the yellow health bar is fully depleted, one life is lost (a red "
            "block turns gray), the health bar refills, and the blue arrow orientation "
            "at the bottom-left resets to its default direction. After a life loss the "
            "agent must step on the white '+' tile again to re-align the arrow before "
            "heading to the gate.",
            0.90,
            "CAUSAL_RULE",
            [1],
        ),
        (   # index 5
            "Light gray cells with grid-line overlay are walkable "
            "areas, while darker gray cells are walls or "
            "non-walkable areas.",
            0.95,
            "COMPONENT_ROLE",
        ),
    ],
    "vc33": [
        (   # index 0
            "There are TWO separate yellow blocks on the grid, not one player "
            "block: a small one embedded near/inside the black horizontal bar, "
            "and a larger one below it. Track each one's position independently "
            "rather than averaging them into a single 'player' position.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 1
            "The blue regions (wherever they appear on the map — their "
            "position varies by level; identify them by color/shape, not a "
            "fixed location) are a walk-to gate/goal — walking the player "
            "token onto a blue region completes the level or advances the "
            "objective.",
            0.45,
            "COMPONENT_ROLE",
        ),
        (   # index 2
            "The blue regions (wherever they appear on the map — their "
            "position varies by level; identify them by color/shape, not a "
            "fixed location) are a button/trigger, not a walkable gate — "
            "clicking on them (rather than walking onto them) changes other "
            "parts of the grid, such as moving/removing barriers or altering "
            "other tiles.",
            0.45,
            "COMPONENT_ROLE",
        ),
        (   # index 3 — depends on two-yellow-blocks (0)
            "Clicking cells (the exact trigger tile is unconfirmed — test the "
            "blue regions, the black bar, and other tiles separately) can shift "
            "the position of the smaller movable yellow block without moving "
            "the larger fixed one. Confirm which specific tile(s) reliably "
            "cause this shift by comparing exact grid coordinates before and "
            "after each click, not just a visual glance.",
            0.65,
            "CAUSAL_RULE",
            [0],
        ),
        (   # index 4 — depends on two-yellow-blocks (0) and the shift rule (3)
            "The win condition may be to move the movable yellow block until "
            "its column lines up with the column of the fixed yellow block "
            "(column alignment).",
            0.75,
            "WIN_CONDITION",
            [0, 3],
        ),
        (   # index 5
            "Black regions in vc33 are ALWAYS static walls/dividers separating "
            "adjacent tanks/columns — never a clickable button or pole, "
            "regardless of size, shape, or level. The lighter gray/white "
            "banded segments visible partway up some black bars are not "
            "decorative either: they are the exposed top of the wall-divider "
            "stack, showing through wherever the wall segment on top of it "
            "hasn't (yet) grown tall enough to cover it. Do not click black "
            "regions at all; only the blue regions are actionable.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 6 — depends on the wall identity (5)
            "A black wall segment retracts/settles passively once it is "
            "'flanked' — i.e. the wall mass on BOTH sides of it is level with "
            "it (no banded segment showing on either side) — as a side effect "
            "of clicking the blue buttons that changed that mass, never from "
            "clicking the wall itself. A grid change observed right after a "
            "click-calibration probe lands inside a black region should NOT "
            "be trusted as proof that black region is a trigger; the change "
            "is caused by something else (e.g. an adjacent blue click's "
            "effect propagating), not by that click landing on black.",
            0.85,
            "CAUSAL_RULE",
            [5],
        ),
        (   # index 7 — depends on the wall identity (5) and the passive-retraction rule (6)
            "Use blue-region clicks to raise or shift the platform mass on "
            "either side of a bar until its banded segment disappears (mass "
            "level with the wall on both sides) — this passively retracts "
            "the wall and re-levels the two neighboring platforms. Never "
            "click a black region to try to trigger this directly.",
            0.75,
            "CAUSAL_RULE",
            [5, 6],
        ),
        (   # index 8
            "Any small grey notch/peak visible at the top of a colored marker "
            "is baked into that marker's own fixed artwork and appears "
            "regardless of game state — it is NOT a dynamic 'this pole or "
            "button is actionable now' indicator. Do not use its presence, "
            "shape, or position as a signal for which click will work; "
            "confirm actionability only by clicking and checking for a real "
            "height/position change.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 9
            "The thin horizontal bar spanning the full width of row 0 at the "
            "very top of the screen (regardless of its color, e.g. pink or "
            "light magenta) is the step/life counter HUD, not a clickable "
            "trigger or button. It shrinks/redraws every time ANY action is "
            "taken, so a grid change observed right after a click-calibration "
            "probe lands there is just the counter ticking down, not evidence "
            "that region is interactive. Do not click it and do not treat it "
            "as a button hypothesis.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 10 — level-0-specific board geometry (confidence <0.8 so it
            # is dropped once the game advances past level 0; a different level's
            # layout can have a different number/arrangement of blue buttons)
            "On the 2-blue-button board (one movable yellow bar, one fixed "
            "yellow marker embedded in a black wall), the two blue click "
            "regions are stacked vertically — an UPPER blue button and a "
            "LOWER blue button near the wall — and each feeds a SEPARATE mass "
            "'tank' on its own (upper/lower) side. Clicking a button only "
            "adds mass to the tank on its own side; it does not affect the "
            "other side.",
            0.7,
            "COMPONENT_ROLE",
        ),
        (   # index 11 — depends on two-yellow-blocks (0) and the tank/button
            # layout (10); confirmed by direct play observation, not calibration
            "Confirmed in play: clicking the LOWER blue button adds mass to "
            "the lower tank, and as the lower tank's mass rises the movable "
            "yellow bar drifts CLOSER to the fixed yellow marker on the wall. "
            "Clicking the upper blue button instead fills the upper tank and "
            "does NOT produce this approach. When this 2-blue-button layout "
            "is present, repeatedly click the LOWER blue button to close the "
            "gap — do not alternate between the upper and lower buttons, and "
            "do not click black regions or the yellow markers themselves, "
            "since only the lower blue button makes measurable progress.",
            0.75,
            "CAUSAL_RULE",
            [0, 10],
        ),
    ],
    "ft09": [
        (   # index 0
            "The screen contains four 3x3 grids of colored tiles (red and blue) "
            "arranged in quadrants.",
            0.90,
            "COMPONENT_ROLE",
        ),
        (   # index 1
            "The grid with the dark border or highlight is the active workspace "
            "that the player interacts with.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 2
            "Clicking a tile in the active grid toggles its color between "
            "red and blue.",
            0.75,
            "CAUSAL_RULE",
        ),
        (   # index 3
            "Near the middle of each quadrant is a small legend tile: it has "
            "its own marker color at its center, and its body is a 3x3 "
            "pattern of white/blank vs gray/colored sub-cells. Each of the "
            "8 big tiles surrounding the legend in that quadrant lines up "
            "with one sub-cell of the legend in the SAME relative position "
            "(e.g. the tile above-left of the legend corresponds to the "
            "legend's own above-left sub-cell). This is a per-quadrant "
            "comparison, not a comparison between different quadrants.",
            0.80,
            "COMPONENT_ROLE",
        ),
        (   # index 4 — depends on active grid (1), toggling (2), marker role (3)
            "Per-tile decision rule, RED case: for each big tile around the "
            "legend whose corresponding legend sub-cell is white/blank, the "
            "tile should be RED — click it if it is currently blue, leave "
            "it if it is already red. Check each such tile individually.",
            0.80,
            "WIN_CONDITION",
            [1, 2, 3],
        ),
        (   # index 5 — depends on active grid (1), toggling (2), marker role (3)
            "Per-tile decision rule, BLUE case: for each big tile around the "
            "legend whose corresponding legend sub-cell is gray/colored "
            "(not blank), the tile should be BLUE — click it if it is "
            "currently red, leave it if it is already blue. Check each such "
            "tile individually. The quadrant is solved once all 8 tiles "
            "follow this rule together with the RED case above.",
            0.80,
            "WIN_CONDITION",
            [1, 2, 3],
        ),
    ],
}

# ---------------------------------------------------------------------------
# Level-specific seed hypotheses
# Injected when the agent advances to a particular level (0-indexed).
# Same tuple format as SEED_HYPOTHESES.
# Key: (game_id, level_index) where level_index is the levels_completed count
#      at the time of injection (e.g. level_index=1 means after first level).
# ---------------------------------------------------------------------------
LEVEL_SEED_HYPOTHESES: dict[
    tuple[str, int],
    list[tuple[str, float, str] | tuple[str, float, str, list[int]]],
] = {
    ("ls20", 1): [
        (   # index 0
            "Yellow ring tiles (a yellow circle or ring pattern followed by "
            "a row of 8 yellow cells) are energy recharge stations. Stepping "
            "on a yellow ring tile refills the yellow health bar. The agent "
            "should step on yellow ring tiles when energy is low to avoid "
            "losing a life.",
            0.90,
            "CAUSAL_RULE",
        ),
    ],
    ("ls20", 2): [
        (   # index 0
            "There is a multi-colored (patchwork/quilt-like) tile on the map. "
            "Stepping on it changes the COLOR of the blue arrow at the "
            "bottom-left corner (cycling it to a different color), separately "
            "from the '+' tile which rotates the arrow's ORIENTATION. Color "
            "and orientation are two independent properties of the same arrow.",
            0.85,
            "CAUSAL_RULE",
        ),
        (   # index 1 — depends on the color-changing tile (0)
            "The win condition now requires the blue arrow at the bottom-left "
            "corner to match the arrow on the gate in BOTH orientation AND "
            "color, not orientation alone — the agent may need to step on "
            "both the '+' tile (orientation) and the multi-colored tile "
            "(color) before the arrows fully match.",
            0.90,
            "WIN_CONDITION",
            [0],
        ),
        (   # index 2
            "There is a short white or light-gray bar tile embedded in the "
            "walkable maze area (distinct from the dark maze walls and from "
            "the yellow health bar in the HUD). Moving the player into or "
            "near this bar instantly pushes the player to the far end of the "
            "current walkable corridor, for free — this does not consume any "
            "energy from the yellow health bar and is not a life lost.",
            0.75,
            "COMPONENT_ROLE",
        ),
    ],
    ("vc33", 2): [
        (   # index 0
            "There is no player-controlled avatar; the only action is "
            "clicking screen coordinates. Level 3 has exactly three colored "
            "markers to align (green, purple, yellow), each a small capped "
            "block sitting on top of a column of black segments, and exactly "
            "one small colored goal tab of each matching color embedded in a "
            "wall elsewhere on the board.",
            0.9,
            "COMPONENT_ROLE",
        ),
        (   # index 1
            "The only directly-clickable elements in this level are 8 small "
            "blue squares scattered along the base of the columns. The black "
            "column segments beneath each colored marker are NOT themselves "
            "clickable in this level.",
            0.85,
            "COMPONENT_ROLE",
        ),
        (   # index 2 — depends on blue-button role (1)
            "Clicking one of the 8 blue squares transfers one unit of "
            "black-segment height between a fixed pair of adjacent columns "
            "(the pairing is set once at level start) — one column's stack "
            "grows while the other shrinks by the same amount, shifting "
            "whichever colored marker sits on top sideways by one column. "
            "Clicking the same blue button again keeps transferring height "
            "in the same direction until the source column is exhausted or "
            "the destination is full, after which further clicks on that "
            "button do nothing — check for an actual height/position change "
            "after each click rather than assuming it worked.",
            0.7,
            "CAUSAL_RULE",
            [1],
        ),
        (   # index 3 — depends on markers/tabs (0) and button transfer rule (2)
            "The level is won only once all three colored markers (green, "
            "purple, yellow) simultaneously sit in the column aligned with "
            "their own matching goal tab. Because a single blue-button click "
            "can shift more than one marker's effective column at once, plan "
            "a click sequence with all three colors in mind rather than "
            "solving one color in isolation and assuming the others are "
            "unaffected.",
            0.85,
            "WIN_CONDITION",
            [0, 2],
        ),
        (   # index 4 — corrects a misleading visual cue
            "Every colored marker has a small grey notch/peak at its top "
            "that is baked into its own fixed artwork and appears "
            "regardless of game state — it is NOT a dynamic 'this pole/"
            "button is actionable now' indicator. Do not use its presence, "
            "shape, or position as a signal for which click will work; "
            "confirm actionability only by clicking and checking for a real "
            "change in column height.",
            0.7,
            "COMPONENT_ROLE",
        ),
        (   # index 5
            "The level has a click budget of 75 actions before it fails "
            "(shown as the countdown bar at the top of the screen), and "
            "columns extend/settle downward (gravity points down this "
            "level) — favor click sequences that make measurable progress "
            "toward alignment over exploratory clicks once the budget is "
            "more than half spent.",
            0.9,
            "CAUSAL_RULE",
        ),
    ],
}
