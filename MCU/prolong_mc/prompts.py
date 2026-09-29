"""Prompts for the MineExplorer port of PRO-LONG.

Replaces `prolong_agent/agent/prompts.py`, which is ARC-AGI-3 specific in five ways:
a grid-puzzle framing, the ACTION1-7/RESET vocabulary, a 16-entry colour map, board
markers (`[INITIAL BOARD STATE]`, `[frame N/M]`, `[settled]`), and level/score
semantics. None of that survives contact with a 3D embodied task.

What is deliberately preserved is the *mechanism*, since that is what the paper
claims: one append-only log the agent parses programmatically, a persistent
workspace, the actions.json contract, briefing-then-plan, the instruction to keep
plans short while testing a hypothesis, and the log-window ablation wording.
"""

# Mirrors mc_agent/context.py's BASE_PROMPT as closely as the mechanism allows.
# Wording that differs between the two arms is a confound, so the action reference and
# the movement guidance below are kept near-verbatim from the baseline; only the
# `repeat` field (Minecraft actions are temporally extended and PRO-LONG submits plans,
# not single steps) and the key names are adapted. Key names follow ActionState, which
# is what the runner validates against. Key names are the baseline's wire spelling
# exactly -- `hotbar.1`..`hotbar.9`, `pickItem`, `swapHands` -- so both arms speak the
# same action vocabulary and go through the same validator.
ACTION_REFERENCE = """\
Each entry is `{{"action": {{...}}, "repeat": N}}` — the action dict is applied for N
consecutive environment ticks (1-{repeat_cap}). One tick of `forward` covers a fraction
of a block, so use `repeat` instead of listing the same action many times.

Available keys (omitted keys default to 0, so specify only what you want):
- "ESC": 0 or 1, press ESC to end the episode (usually 0)
- "attack": 0 or 1, attack/mine blocks
- "back": 0 or 1, move backward
- "camera": [pitch_delta, yaw_delta] in degrees (e.g. [0, 45] to look right, [-20, 0] to
  look up). **IMPORTANT**: this is a RELATIVE change added to your CURRENT camera angle,
  not an absolute target — repeating the same camera move across several steps keeps
  rotating further in that direction. Pitch is clamped to [-90 (straight up),
  90 (straight down)]; if you keep pushing pitch the same direction it sticks at the
  clamp and you will not be looking at anything useful. Trust the pitch value in the
  log's [STATE] lines over your own visual read.
- "drop": 0 or 1, drop current item
- "forward": 0 or 1, move forward
- "jump": 0 or 1, jump
- "left" / "right": 0 or 1, STRAFE sideways — these do NOT change your facing
- "sneak": 0 or 1, sneak/crouch
- "sprint": 0 or 1, sprint (MUCH FASTER movement — use this when exploring!)
- "use": 0 or 1, use item or place block
- "inventory": 0 or 1, open/close inventory
- "hotbar.1" to "hotbar.9": 0 or 1, select hotbar slots (at most one)
- "pickItem", "swapHands": 0 or 1

**Movement tips for efficient exploration:**
- **USE SPRINT!** Combine "forward": 1 with "sprint": 1 for FAST movement in open areas.
- **Turn, then move — don't do both in the same entry.** A camera yaw change and
  "forward" fire in the same in-game tick, so pairing a large yaw turn with "forward"
  turns your path into a tight loop instead of a straight line. Spend one entry turning
  (camera yaw only, forward=0), then several ticks moving straight (forward=1,
  camera=[0,0]) before turning again. Use the [STATE] lines — not your step count or
  visual impression — to confirm you are covering new ground.
- Use "jump": 1 with forward movement to clear obstacles and one-block rises.
- Use camera to look around before deciding where to move.

"""

SYSTEM_PROMPT = """\
You are a coding agent controlling a Minecraft player by writing action plans.

Your objective is to complete the task below. Your secondary objective is to use as
few environment steps as possible.

**Task**: {task_text}

`./logs.txt` is the episode log: action headers, the actions executed, the resulting
player state, and your own prior analyses. {log_window_desc} Parse it
**programmatically** — the log is long and numeric, and reading it by eye invites
exactly the errors this design exists to avoid.{cross_turn_hint}

**Tools**: Read, Write, Edit, Bash, Grep, Glob.

**Workspace**: `./` persists across calls. `actions.json` is cleared each call; other
files accumulate. Feel free to save notes, state, or helper functions.

**Log markers**:
    Action N | Step S | Plan Step i/T{verified_field} — one section per environment
        tick; `Plan Step` says which tick of your last plan this was.
    [STATE] pos=(x, y, z) pitch=P yaw=Y moved=D — the player state after an action.
        `moved` is the horizontal distance covered by that action. `moved=0.00`
        repeatedly means you are blocked by terrain, not that you are standing still
        by choice.
    [FRAME] frames/step_NNNN.png — the first-person view at that step. The newest
        one is attached directly to every call, so you always see the current view
        without asking; use the image viewer on the older paths when you want to
        compare against where you have already been.
    [PLAN] — your own analyses: the briefing you wrote at your last call appears
        once, and the plan you wrote appears in every section it governed.
    [NOTE] — something the runner rejected or refused since the previous action.{milestone_marker}

**What you can rely on**:
- Coordinates and facing in `[STATE]` are ground truth from the environment; your own
  visual read of a frame is not proof an action worked.
- `moved=0.00` repeatedly means you are blocked by terrain (a wall, a fence, a
  one-block ledge), or that you used `left`/`right`, which strafe without turning.
- {esc_policy}
- You keep no separate memory: `logs.txt` and whatever you save in `./` are your memory.

**Response format**: a strategic briefing, then
[PLAN]
<2-3 sentence action plan>

**Write `./actions.json`** with a JSON object
`{{"actions": [{{"action": {{"forward": 1}}, "repeat": 10}}, ...]}}` — a list of
1-{action_cap} entries executed in order, totalling at most {step_cap} environment
steps. Prefer short lists (1-2 entries) when testing a new hypothesis so you see the
result before committing further; scale up for movement you are confident about.

**Actions available**:
{actions_section}

The runner executes the list in order, then calls you again with the updated log.
"""

# The paper's control arm (upstream `--log-window -1`, `SYSTEM_PROMPT_INPROMPT`): the same
# coding agent, the same workspace and plan contract, but no log -- the current state
# travels in the prompt and nothing else is kept unless the agent writes it down. On
# MineExplorer "the board" is the [STATE] line plus the attached frame.
SYSTEM_PROMPT_NOLOG = """\
You are a coding agent controlling a Minecraft player by writing action plans.

Your objective is to complete the task below. Your secondary objective is to use as
few environment steps as possible.

**Task**: {task_text}

The current player state is injected directly into your prompt each call, together
with the current first-person view. Prior states, frames and analyses are not
preserved across calls unless you save them yourself to the workspace; if you want to
compare positions across calls, write them to a file first.

**Tools**: Read, Write, Edit, Bash, Grep, Glob.

**Workspace**: `./` persists across calls. `actions.json` is cleared each call; other
files accumulate. Feel free to save notes, state, or helper functions.

**Prompt markers** (on the user turn):
    [STATE] pos=(x, y, z) pitch=P yaw=Y moved=D — the player state now. `moved` is
        the horizontal distance covered by the last action; `moved=0.00` repeatedly
        means you are blocked by terrain, not that you are standing still by choice.
    Verified: yes/no — the environment's own verification of task completion, when
        the protocol provides it. This is the signal the ESC rule below refers to;
        nothing else counts as verification.

**What you can rely on**:
- Coordinates and facing in `[STATE]` are ground truth from the environment; your own
  visual read of a frame is not proof an action worked.
- {esc_policy}
- You keep no separate memory: whatever you save in `./` is your memory.

**Response format**: a strategic briefing, then
[PLAN]
<2-3 sentence action plan>

**Write `./actions.json`** with a JSON object
`{{"actions": [{{"action": {{"forward": 1}}, "repeat": 10}}, ...]}}` — a list of
1-{action_cap} entries executed in order, totalling at most {step_cap} environment
steps. Prefer short lists (1-2 entries) when testing a new hypothesis so you see the
result before committing further; scale up for movement you are confident about.

**Actions available**:
{actions_section}

The runner executes the list in order, then calls you again with the updated state.
"""


def _build_nolog_system_prompt(
    task_text: str, action_cap: int, step_cap: int, repeat_cap: int,
    stateless: bool, milestone_hint: bool,
) -> str:
    prompt = SYSTEM_PROMPT_NOLOG.format(
        esc_policy=ESC_POLICY,
        task_text=task_text,
        action_cap=action_cap,
        step_cap=step_cap,
        actions_section=(ACTION_REFERENCE.format(repeat_cap=repeat_cap)
                         + platform_block(platform_prompt)),
    )
    if not milestone_hint:
        prompt = prompt.replace(
            "    Verified: yes/no — the environment's own verification of task "
            "completion, when\n        the protocol provides it. This is the signal the "
            "ESC rule below refers to;\n        nothing else counts as verification.\n",
            "",
        )
    if stateless:
        prompt = prompt.replace(
            "**Workspace**: `./` persists across calls. `actions.json` is cleared each "
            "call; other files accumulate. Feel free to save notes, state, or helper "
            "functions.",
            "**Workspace**: `./` does not persist across calls (notes, state and helper "
            "functions are gone once actions are submitted).",
        ).replace(
            "- You keep no separate memory: whatever you save in `./` is your memory.\n",
            "",
        )
    return prompt


NOLOG_FIRST_PROMPT = """\
{state}
{attached}
This is the first analysis. Look at the frame, work out where you are and what the
task requires, then write ./actions.json with your first set of actions.
"""

NOLOG_RESUME_PROMPT = """\
{state}
{attached}
The state above is where the last plan left you. Check ./ for anything you saved
previously, compare, then write a new ./actions.json.
"""

FIRST_PROMPT = """\
{log_desc}
{attached}
This is the first analysis. Look at the initial frame, work out where you are and
what the task requires, then write ./actions.json with your first set of actions.
"""

RESUME_PROMPT = """\
{log_desc}
{attached}
{body}
"""

# The analyzer is handed the current view every turn, the way the baseline agent is
# handed its frame buffer every step. Saying so matters: told only about [FRAME]
# markers, the model treats pixels as something to go fetch, and v3 fetched none.
ATTACHED_NOTE = """
The image attached to this message is the player's CURRENT first-person view, taken
at the latest state in the log. Earlier frames are on disk at the [FRAME] paths if
you want to compare against them.
"""

ATTACHED_NOTE_NOLOG = """
The image attached to this message is the player's CURRENT first-person view, taken
at the state above. Earlier frames are not kept.
"""

RESUME_BODY = """\
The most recent actions and states are at the end of the log. What changed since the
last call — distance actually covered, whether facing changed, whether the view is
new — is the useful signal. Check ./ for anything you saved previously, then write a
new ./actions.json.
"""

RESUME_BODY_NO_HISTORY = """\
Compare the current state to your notes in the workspace. Focus on what changed and
whether your previous plan made progress. Check ./ for anything you saved previously.
Update your briefing and write a new ./actions.json.
"""


# Verbatim from the baseline's BASE_PROMPT, and unconditional there -- the paragraph
# is static, so under --no-milestone-hint the baseline still says "only ESC when the
# verified line says complete" while no such line exists, which is why its episodes
# run to the step limit. Splitting this by protocol (as a first version did) let the
# PRO-LONG arm press ESC at step 17 where the baseline ran past 200: an order of
# magnitude difference in episode length caused by prompt wording, not by memory.
ESC_POLICY = (
    "Only set ESC=1 when the environment has verified the task complete. Your own "
    "visual read of a frame is not proof the action worked (a door may look open, an "
    "item may look mined, an attack may look lethal, when it actually was not). If "
    "nothing says the task is verified complete, keep working even if you believe "
    "you just succeeded."
)



def platform_block(platform_prompt: str) -> str:
    """Frame the host benchmark's own agent contract for inclusion in the system prompt.

    MCU-AgentBeats sends every purple agent a control reference in `InitPayload.prompt`
    (`src/prompt.txt`): key semantics, the mutually-exclusive movement constraints, the
    camera sign convention, hotbar single-selection, and the GUI/cursor measurements. This
    port ignored that field entirely, so the arm ran on upstream MineExplorer's action
    documentation and never saw the host's -- which is the wrong thing to hold constant
    when the point of the comparison is the memory mechanism.

    The one conflict is the response format: the host document ends by asking for a single
    flat JSON action object, which is the right answer for a one-action-per-step agent and
    the wrong one here. It is reconciled explicitly rather than by hoping the model works
    it out, because a plan written in the host's shape does not parse.
    """
    text = (platform_prompt or "").strip()
    if not text:
        return ""
    # NB: the return value is substituted into SYSTEM_PROMPT as a *value* and is never
    # itself passed through `.format()`, so braces here are literal, not escaped.
    return (
        "\n\n---\n\n"
        "# The benchmark's own control reference\n\n"
        "The following is supplied by the environment you are running in and is "
        "authoritative for what the keys mean and how they behave. Where it describes a "
        "response format -- a single flat JSON object of keys -- that object is exactly "
        "what goes in the `action` field of ONE entry of your `actions.json`; you still "
        "answer with `{\"actions\": [{\"action\": {...}, \"repeat\": N}, ...]}` as "
        "described above, and you do not emit its bare form.\n\n"
        f"{text}\n"
    )

def _extra_knowledge() -> str:
    """An operator-supplied knowledge block, from the file named by
    PROLONG_EXTRA_KNOWLEDGE. The matched-knowledge control for the world-model
    comparison: the wm arm's prompt carries game/task constants and distilled
    strategy, so this hands the SAME text (harness-procedure references stripped)
    to the baseline -- the remaining delta is then architecture, not coaching.
    Empty (the default) leaves the baseline exactly as it always ran."""
    import os
    path = os.environ.get("PROLONG_EXTRA_KNOWLEDGE", "").strip()
    if not path:
        return ""
    try:
        text = open(path, encoding="utf-8").read().strip()
    except OSError:
        return ""
    return ("\n\n# Task knowledge (operator-supplied)\n\n" + text + "\n") if text else ""


def build_system_prompt(
    task_text: str,
    action_cap: int,
    step_cap: int,
    repeat_cap: int,
    log_window: int | None,
    stateless: bool = False,
    milestone_hint: bool = False,
    platform_prompt: str = "",
) -> str:
    """Render the system prompt. `log_window` follows PRO-LONG's convention:
    None = full log, 0 = latest state only, >0 = that many action sections,
    -1 = no log (the paper's No-Log control: current state in the prompt)."""
    if log_window == -1:
        return _build_nolog_system_prompt(
            task_text, action_cap, step_cap, repeat_cap, stateless, milestone_hint,
            platform_prompt,
        ) + _extra_knowledge()
    if log_window is None:
        log_window_desc = "It contains the full episode history."
    elif log_window == 0:
        log_window_desc = "It contains only the most recent state."
    else:
        log_window_desc = f"It contains the last {log_window} action sections."

    multi_turn = log_window is None or (log_window or 0) > 0
    cross_turn_hint = (
        " Cross-turn parsing (differencing positions hundreds of steps apart, "
        "grepping every [STATE] line for a coordinate range) is tractable and is "
        "often the only way to notice you have revisited somewhere."
    ) if multi_turn else ""

    # The baseline renders the environment's verification as its own context section
    # ("**Environment-verified task status:** ...", context.py:86-88) and only when the
    # hint protocol is on. PRO-LONG's equivalent channel is the log, so the marker is
    # documented on exactly the same condition -- otherwise one arm would be told a
    # verification signal exists while the other is not, which is the confound that
    # already cost one PRO-LONG run.
    milestone_marker = (
        "\n    [MILESTONE] — the environment's own verification of task completion, "
        "attached to\n        the action it was observed after. This is the signal the "
        "ESC rule below refers\n        to; nothing else counts as verification."
    ) if milestone_hint else ""

    # The header's `Verified:` field is upstream's `Score:` -- the same environment
    # verification the [MILESTONE] line reports on change, written into every section
    # so a `tail` sees it. Documented on the same condition as the marker.
    verified_field = " | Verified: yes/no" if milestone_hint else ""

    prompt = SYSTEM_PROMPT.format(
        esc_policy=ESC_POLICY,
        milestone_marker=milestone_marker,
        verified_field=verified_field,
        task_text=task_text,
        action_cap=action_cap,
        step_cap=step_cap,
        log_window_desc=log_window_desc,
        cross_turn_hint=cross_turn_hint,
        actions_section=(ACTION_REFERENCE.format(repeat_cap=repeat_cap)
                         + platform_block(platform_prompt)),
    )
    if stateless:
        prompt = prompt.replace(
            "**Workspace**: `./` persists across calls. `actions.json` is cleared each "
            "call; other files accumulate. Feel free to save notes, state, or helper "
            "functions.",
            "**Workspace**: `./` does not persist across calls (notes, state and helper "
            "functions are gone once actions are submitted) — only `logs.txt` carries over.",
        )
        prompt = prompt.replace(
            "the resulting\nplayer state, and your own prior analyses.",
            "and the resulting\nplayer state.",
        )
    return prompt + _extra_knowledge()


def build_turn_prompt(
    log_name: str, is_first: bool, log_window: int | None, frame_attached: bool = False,
    state_text: str = "",
) -> str:
    if log_window == -1:
        attached = ATTACHED_NOTE_NOLOG if frame_attached else ""
        tmpl = NOLOG_FIRST_PROMPT if is_first else NOLOG_RESUME_PROMPT
        return tmpl.format(state=state_text.strip() or "[STATE] unavailable", attached=attached)
    attached = ATTACHED_NOTE if frame_attached else ""
    disp = f"./{log_name}"
    if log_window is None:
        log_desc = f"Read the full episode log at {disp}"
    elif log_window == 0:
        log_desc = f"Read {disp} (current state only; no action history)."
    else:
        log_desc = f"Read {disp} (last {log_window} actions)."

    if is_first:
        return FIRST_PROMPT.format(log_desc=log_desc, attached=attached)
    body = RESUME_BODY_NO_HISTORY if log_window == 0 else RESUME_BODY
    return RESUME_PROMPT.format(log_desc=log_desc, attached=attached, body=body)
