"""The agent: one loop over one filesystem, shared by the four arms.

The runner steps the environment and hands every step to `observe`, which writes the
ground truth into the memory filesystem -- position, events, a frame -- and never asks
the model anything. When the action queue runs dry, `next_action` fires an **act
turn**: the model is given the current frame, the milestone checklist and the state
block, and writes `actions.json` (a list of raw actions and named procedures), which
refills the queue.

What differs between the arms is only how the past is served (`memory_mode`):

    direct    nothing: every turn is the present alone
    mfm       the log plus the episode store beside it (mcu_worldmodel/episodes.py),
              the carried lives under `previous/` (previous.py), and the agent's own
              notes, procedures and reflexes under `mine/` (own.py, skills.py)
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

#: The environment-outage retry wait. A module-level indirection so a test can
#: stub it out; a real arm waits through it.
RETRY_SLEEP = time.sleep
from PIL import Image

from mcu_worldmodel import gui, macros, macros_entity, prompts, vision
from mcu_worldmodel.actions import describe_entry, parse_actions
from mcu_worldmodel import own as _own
from mcu_worldmodel import procedures as _P
from mcu_worldmodel.claude_backend import ClaudeTurn
from mcu_worldmodel.codex_backend import CodexTurn
from mcu_worldmodel.cursor import CursorState
from mcu_worldmodel.episodes import EpisodeBridge
from mcu_worldmodel.governor import Governor, cell_of
from mcu_worldmodel import grid as grid_mod
from mcu_worldmodel.grid import Grid
from mcu_worldmodel.memory import MultimodalMemory, norm_yaw
from mcu_worldmodel.macros_world import norm_yaw_delta
from mcu_worldmodel.milestones import (
    MilestoneLedger, held_line, hotbar_line, inventory_counts, location, nearby_mobs,
    slot_is_empty, vitals,
)


def _first_empty_slot(info: dict) -> int | None:
    """The lowest empty MAIN-ROW slot id (9-35), falling back to the hotbar (0-8).

    Named in the close-refusal [NOTE]: one run burned ~19 refused closes in a row with
    logs stuck in the cursor because "put it back in a slot" never said which slot was
    free. Main rows first so stowing never silently displaces a selected tool."""
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return None
    for sid in list(range(9, 36)) + list(range(0, 9)):
        if slot_is_empty(inv.get(sid) or inv.get(str(sid))):
            return sid
    return None

def _empty_slot_count(info: dict) -> int | None:
    """How many of the 36 player slots are empty, or None when the shape is unknown.

    Rendered on the Inventory line: one run reached its furnace endgame with out=FULL
    and nowhere to stow, and nothing in the prompt had said fullness was approaching.
    `slot_is_empty` is the shared predicate: with the old "air"-only test this line
    read "0 slots free" on every turn of every live arm, from an empty inventory on."""
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return None
    n = 0
    for sid in range(36):
        entry = inv.get(sid) or inv.get(str(sid))
        if not isinstance(entry, dict):
            return None
        if slot_is_empty(entry):
            n += 1
    return n


RETRY_NUDGE = ('Your previous response did not produce a valid ./actions.json. Write one '
               'with the shape {"actions": [{"action": {...}, "repeat": N}]} or '
               '{"actions": [{"procedure": "name", "args": {...}}]}.')

# The direct arm's retry is the full prompt re-sent with this line appended: with no
# filesystem and a 1-turn session there is nothing for a bare nudge to lean on.
DIRECT_RETRY_LINE = (
    'Your previous reply carried no valid actions JSON. End this reply with ONE fenced '
    '```json block shaped {"actions": [{"action": {...}, "repeat": N}]} or '
    '{"actions": [{"procedure": "name", "args": {...}}]}.')

_FENCE_RE = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.DOTALL)


def extract_actions_block(message: str) -> str | None:
    """The direct arm's output channel: the LAST fenced block in the reply that parses
    as a JSON object with an "actions" key. Validation of the entries themselves stays
    where it always was, in parse_actions."""
    for block in reversed(_FENCE_RE.findall(message or "")):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "actions" in parsed:
            return block
    return None



def _is_attack_hold(a: dict) -> bool:
    """A pure raw attack hold: attack, no camera, no movement, no use, no hotbar."""
    if any(k.startswith("_") for k in a):
        return False
    if not a.get("attack"):
        return False
    cam = a.get("camera", [0, 0])
    try:
        if any(abs(float(c)) > 0.01 for c in cam):
            return False
    except (TypeError, ValueError):
        return False
    move = ("forward", "back", "left", "right", "jump", "sneak", "sprint",
            "use", "drop", "inventory")
    if any(a.get(k) for k in move):
        return False
    return not any(a.get(f"hotbar.{n}") for n in range(1, 10))


def _num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _cut_short_hint(atoms: bool) -> str:
    """The tail of the attack-hold cut-short note: names tools that exist in this run.
    Under --atoms the macros are withheld (procedures.ATOMS); the old hint named them
    241 times in one run to a model that could not call them.
    A raw attack hold is also never watched for ore: mine_ahead(ore_watch=true) is the
    one entry point to the wall watcher there (that life: 79 turns of raw holds, zero
    sightings, 9/10). Same shape as MCU main's 1ac1c7f."""
    if atoms:
        return ("To mine several blocks in a row queue one {\"attack\": 1} hold (repeat "
                "30) per block: each is cut the moment its block breaks, and the wall "
                "watcher samples every hold for ore speckles. mine_ahead(n) spends all n "
                "ticks -- use it only for continuous digging (a shaft).")
    return "To mine several blocks in a row use mine_forward/strip_mine/stair_down."


class WorldModelAgent:
    def __init__(
        self,
        *,
        workspace: str | Path,
        task_text: str,
        ledger: MilestoneLedger,
        model: str = "gpt-5.6-sol",
        reasoning_effort: str = "medium",
        base_url: str | None = None,
        codex_home: str | Path | None = None,
        transcript_dir: str | Path | None = None,
        # Which CLI carries the model: "codex" (GPT through the Codex CLI, every arm so
        # far) or "claude" (Anthropic models through Claude Code). `self.codex` stays the
        # attribute name either way: it is the model channel, and both Turn classes hold
        # the same contract (run / vision_audit / split_briefing).
        cli: str = "codex",
        entry_cap: int = 40,
        repeat_cap: int = 200,
        step_cap: int = 400,
        extended_actions: bool = False,
        # 5 for every arm: the arms must not differ in how many chances a turn gets
        # to produce a valid actions.json.
        analyzer_retries: int = 5,
        frame_size: tuple[int, int] = (640, 360),
        platform_prompt: str = "",
        max_steps: int = 6000,
        memory_mode: str = "mfm",
        # Codex lifecycle knobs handed through to CodexTurn; None keeps the
        # backend's environment fallback (the offline tests).
        session_max_turns: int | None = None,
        codex_timeout: int | None = None,
        # The mfm arm's retrieval block in the turn prompt. Only the mfm mode has a
        # store to compute it from.
        retrieval: bool = False,
        # The mfm arm's carried lives (mcu_worldmodel/previous.py): earlier runs' memory
        # dirs whose records go under previous/, for the model to read. Only the mfm
        # mode has the store to carry them with.
        previous_lives: list | None = None,
        expect: bool = False,
        frames: bool = False,
        thin: bool = False,
        atoms: bool = False,
        own: bool = False,
        own_reflexes: bool = False,
        harness_reflexes: bool = True,
        skills: bool = False,
        minimal: bool = False,
        event_sheet: bool = True,
        # `own_live` (mcu_worldmodel/own.py, the closed-loop section): a procedure
        # script that declares `LOOP = True` is run DURING the plan on the live state
        # and the live frame, and the reflexes get the frame too. Off: the shipped arm.
        own_live: bool = False,
        # `near_deaths`: name a death whose respawn is close to where it happened
        # (`_respawned_here`). Off: a death is named by its teleport alone, as shipped.
        near_deaths: bool = False,
    ) -> None:
        if memory_mode not in ("direct", "mfm"):
            raise ValueError(f"unknown memory_mode: {memory_mode!r}")
        if retrieval and memory_mode != "mfm":
            raise ValueError("retrieval needs memory_mode='mfm'")
        if previous_lives and memory_mode != "mfm":
            raise ValueError("previous_lives needs memory_mode='mfm'")
        if (expect or frames) and memory_mode != "mfm":
            raise ValueError("expect/frames need memory_mode='mfm'")
        # The MFM-layer options (parts of the mfm arm; the chassis is unchanged):
        # `expect` echoes the model's EXPECT line against the harness record next
        # turn; `frames` gives the arm zoom.py.
        self.expect, self.frames = bool(expect), bool(frames)
        # `thin` (any memory mode): the contract keeps the task, the memory protocol, the
        # response format, the action schema and the procedure index; the long sections
        # go to references/ (prompts.thin_split). The model reads them when it needs them.
        self.thin = bool(thin)
        # `atoms` (any mode): the procedure set the contract shows and `expand` accepts
        # is procedures.ATOMS; `own` (mfm): mine/ persists and mine/procedures/*.py
        # are procedures (mcu_worldmodel/own.py).
        #: `harness_reflexes=False`: no reflex, guard, governor or nudge acts for the
        #: model (the arm's own reflexes are the tick layer)
        self.reflexes = bool(harness_reflexes)
        #: `--skills` (mcu_worldmodel/skills.py): the meta-level skill package written
        #: into skills/ and the starter reflexes into mine/reflexes/
        self.skills = bool(skills)
        #: `--minimal` (prompts.MINIMAL_CONTRACT): the short contract; the rules go to
        #: references/ exactly as `--thin` writes them.
        self.minimal = bool(minimal)
        #: `--no-event-sheet` (mfm): no 2x2 sheet of this turn's event frames; the view alone.
        self.event_sheet = bool(event_sheet)
        self.atoms, self.own = bool(atoms), bool(own)
        if self.own and memory_mode != "mfm":
            raise ValueError("own needs memory_mode='mfm'")
        _P.set_visible(_P.ATOMS if self.atoms else None, own=self.own)
        self._own_procs: dict[str, Any] = {}
        self._own_calls: dict[str, int] = {}
        #: Running ledger counts an own entry's scorecard is cut from (own.RECORD_FILE).
        self._tally: dict[str, float] = {"hits": 0.0, "kills": 0.0}
        self._entry_tally0: dict[str, Any] | None = None
        self._own_record: dict[str, list[dict[str, Any]]] | None = None
        self._own_life_no: int = 1
        #: `--own-reflexes` (mcu_worldmodel/own.py): mine/reflexes/<name>.py scripts run
        #: every REFLEX_EVERY ticks on the live numbers and may stop the plan, note, and
        #: queue a short plan of their own -- the model's tick layer, beside the runner's.
        self.own_reflexes = bool(own_reflexes) and self.own
        if own_live and not (self.own and minimal):
            raise ValueError("own_live gives the model's own scripts the live view: it "
                             "needs the mfm arm (own, minimal)")
        self.own_live = bool(own_live)
        self.near_deaths = bool(near_deaths)
        #: closed loops run this life: name -> {"entries", "calls", "ticks"}
        self._own_loops: dict[str, dict[str, int]] = {}
        self._own_reflexes: dict[str, Any] = {}
        self._own_reflex_fires: dict[str, int] = {}
        self._own_reflex_last: dict[str, int] = {}
        self._own_reflex_fails: dict[str, int] = {}
        self._own_reflex_off: dict[str, tuple[str, float]] = {}
        self._own_reflex_prev: dict[str, Any] | None = None
        self._last_expect: str | None = None
        self._turn_outcomes: list[dict[str, Any]] = []
        self.retrieval = bool(retrieval)
        self.task_text = task_text
        self.ledger = ledger
        self.entry_cap, self.repeat_cap, self.step_cap = entry_cap, repeat_cap, step_cap
        # The arm axis, and the ONLY thing it is allowed to change: how the past is
        # served. Execution engine, perception, caps and knowledge are shared.
        # "direct" is the no-memory rung: no filesystem, no persistent thread, no
        # window -- every act turn is the present alone (the state block the memory
        # arms get, plus the current view), and its reply carries the actions JSON the
        # other arms write to a file.
        # "mfm": one append-only logs.txt the model greps, plus the Multimodal
        # Filesystem Memory beside the log -- one directory per plan entry (image,
        # state, action, outcome) and a query tool; the store is written from four
        # hook points (see mcu_worldmodel/episodes.py).
        self.memory_mode = memory_mode
        # True when mcu_worldmodel.craft_env has patched the spec, which is what makes
        # `drop` a real key rather than one `_process_action` silently skips.
        self.extended_actions = extended_actions
        self.analyzer_retries = analyzer_retries
        self.frame_size = frame_size
        #: Size of the last live frame written for an own script (`_live_frame`).
        self._live_size: tuple[int, int] = tuple(frame_size)
        # The host benchmark's control reference, as the green agent sent it.
        self.platform_prompt = platform_prompt
        # The episode's hard step budget. Surfaced in every turn header: an agent that
        # cannot see the deadline plans a two-visit endgame with 190 steps left
        # (one run) and loses milestones it was already carrying the materials for.
        self.max_steps = max_steps

        self.memory = MultimodalMemory(workspace, direct=memory_mode == "direct",
                                       episodes=memory_mode == "mfm",
                                       zoom_tool=self.frames, own=self.own)
        if self.own:
            (self.memory.root / _own.OWN_DIR).mkdir(parents=True, exist_ok=True)
        if self.own_reflexes:
            (self.memory.root / _own.REFLEX_DIR).mkdir(parents=True, exist_ok=True)

        # The direct arm sheds what it can of the tool surface: codex exec cannot shed
        # its exec cell, so it runs read-only -- the closest this CLI comes to a
        # toolless chat loop, with the residual asymmetry audited
        # (tool_errors / view_image_calls) rather than assumed away.
        codex_kwargs: dict[str, Any] = (
            {"sandbox_mode": "read-only"} if memory_mode == "direct" else {})
        if session_max_turns is not None:
            codex_kwargs["session_max_turns"] = int(session_max_turns)
        if codex_timeout is not None:
            codex_kwargs["timeout"] = int(codex_timeout)
        if cli == "claude":
            # The direct arm on claude sheds the tool surface entirely (`tools=()`),
            # which codex cannot do; the codex side runs read-only instead.
            claude_kwargs: dict[str, Any] = (
                {"tools": ()} if memory_mode == "direct" else {})
            if session_max_turns is not None:
                claude_kwargs["session_max_turns"] = int(session_max_turns)
            if codex_timeout is not None:
                claude_kwargs["timeout"] = int(codex_timeout)
            self.codex = ClaudeTurn(
                self.memory.root, model=model, reasoning_effort=reasoning_effort,
                base_url=base_url,
                config_dir=Path(codex_home) if codex_home else None,
                transcript_dir=Path(transcript_dir) if transcript_dir else None,
                **claude_kwargs,
            )
        elif cli == "codex":
            self.codex = CodexTurn(
                self.memory.root, model=model, reasoning_effort=reasoning_effort,
                base_url=base_url,
                codex_home=Path(codex_home) if codex_home else None,
                transcript_dir=Path(transcript_dir) if transcript_dir else None,
                **codex_kwargs,
            )
        else:
            raise ValueError(f"unknown cli: {cli!r} (codex|claude)")
        self.cli = cli
        self.episodes: EpisodeBridge | None = (
            EpisodeBridge(self.memory, self.codex, self.ledger, retrieval=self.retrieval)
            if memory_mode == "mfm" else None)
        if self.episodes is not None and previous_lives:
            self.episodes.seed_previous(list(previous_lives))
        if memory_mode == "direct" and self.codex.session_max_turns != 1:
            # A resumed thread is memory the harness would be serving for free; the
            # window above is the direct arm's ONLY sanctioned past. Forced here so a
            # launcher running the memory arms with longer sessions cannot quietly
            # hand the baseline a second past channel.
            logger.info(f"[agent] memory_mode=direct: forcing 1-turn codex sessions "
                        f"(was {self.codex.session_max_turns})")
            self.codex.session_max_turns = 1
        # The direct arm's only bookkeeping: replies that carried no actions block.
        self.direct_stats = {"reply_parse_failures": 0}
        # (action, plan-entry index). The index is what lets a log section be written when
        # an entry *finishes*, with the position it actually reached -- logging at planning
        # time instead made every [STATE] line read moved=0.00, which is precisely the
        # number the prompt tells the agent to trust over its own read of a frame.
        self.queue: deque[tuple[dict[str, Any], int]] = deque()
        self.plan: list[str] = []
        self.step = 0
        self.action_num = 0
        self._prev_pos: dict | None = None
        self._last_frame: str | None = None
        self._pending_events: list[str] = []
        self._plan_entries: list[dict[str, Any]] = []
        self._entry_index: int | None = None
        self._entry_start_pos: dict | None = None
        self.governor = Governor()
        # The runner's own cell map (grid.py): walked cells, the pose a screen
        # opened from, water/lava/hazard cells. Beside the log in every arm that
        # keeps one; the direct arm keeps it in memory only (no file, no prompt
        # surface -- its only past is the present).
        self.grid = Grid((self.memory.root / "grid.jsonl") if self.memory.log else None)
        # Frames at this turn's events (a hit, LAVA AHEAD, a stalled walk, a failed
        # re-open): tiled into one sheet and attached beside the current view.
        self._event_frames: list[tuple[int, str, Any]] = []
        # The last six finished entries, as the [RECENT] block renders them.
        self._recent_outcomes: deque = deque(maxlen=6)
        self._cur_pos: dict | None = None
        self._cur_info: dict | None = None    # the latest raw observation
        self._placed: dict[str, tuple[int, int, int]] = {}   # item -> block placed by place_and_open
        # The GUI cursor, held by the harness rather than by the agent. See cursor.py for
        # why: with a relative-only cursor the agent had to keep its position in the belief
        # graph (208 of 243 hypotheses were one-shot `state_cursor_*` bookkeeping) and had
        # to end its plan after every move in order to look, which is what made the median
        # plan two entries long.
        self.cursor = CursorState()
        # Where the last cursor servo verifiably landed, and a click awaiting its
        # next-tick verdict. Both belong to the current screen: cleared when it closes.
        self._servo_landed: tuple[float, float] | None = None
        self._pending_click: dict | None = None
        # Consecutive guard-stop streaks per procedure family, cleared whenever
        # verified progress lands. {label: [count, first_fail_step]}
        self._proc_fails: dict[str, list] = {}
        self._cur_inv: dict[str, int] = {}
        self._entry_start_inv: dict[str, int] = {}
        self._gui_open = False
        # (baseline-at-open, drops-already-noted, position text) pending a one-tick
        # recheck after a screen close -- see _sync_cursor.
        self._close_recheck: tuple[dict[str, int], dict[str, int], str] | None = None
        #: Which container the frame shows while a screen is open ('inventory', 'table',
        #: 'furnace' or None), read by vision.screen_kind every observe tick.
        self._screen: str | None = None
        self.turns = {"act": 0, "act_failed": 0}
        # Closed-loop bookkeeping. `_close_armed` is set by a `_allow_close` marker and
        # consumed by the next inventory toggle; `_vision_miss_streak` counts consecutive
        # GUI ticks where the arrow was not found in the frame (transition frames omit
        # it), which is when a servo is allowed to trust dead reckoning instead.
        self._close_armed = False
        self._vision_miss_streak = 0
        self._log_breaks = 0.0
        self._other_breaks = 0.0
        self._last_break_item = ""
        self._breaks_seen = 0.0
        self._empty_slot: int | None = None
        self._last_pov = None
        self._coal_seen = 0.0
        self._last_torch_nudge = -10 ** 9
        self._sword_nudged = False
        #: The frame before `_last_pov` -- what a motion detector diffs against.
        self._prev_pov = None
        self._last_ore_flag_step = -1000
        #: `--atoms`: the wall watcher's marker for raw attack holds (see next_action).
        self._raw_ore: dict[str, Any] = {}
        self._last_lava_step = -1000
        self._last_lava_action = -1          # the action the guard last stopped
        self._last_shaft: tuple[Any, int] = (None, -1)   # (cell, action) the shaft guard stopped
        self._fall: dict[str, float] | None = None       # the fall guard's descent record
        #: (step, x, z) of the last frame with water within reach (the dig refusal).
        self._last_water_seen: tuple[int, float, float] | None = None
        self._last_lava_frac = 0.0
        # Plans the lava guard stopped, per 3-block cell of the avatar's position: the
        # second stop at one place says so (two runs: three plans each dropped
        # at one 1% sliver, the model walking back to it every time).
        self._lava_stops: dict[tuple[int, int, int], dict[str, Any]] = {}   # 3-block cell -> {n, frac}
        self._pos_hist: deque = deque(maxlen=5)
        self._last_health: float | None = None
        # Hit reflex + event frames. `_hp_hist` holds (step, hp) over the last 100
        # ticks: a single-tick drop of >=3 (a mob hit, a fall) or a cumulative one
        # (drowning, burning, starvation at 1 hp a time) interrupts, once per 100
        # ticks for the slow kind. On a hit the runner turns the player to face where
        # it came from before the next act turn: `Nearby entities` is never on the
        # wire, so a miner was blind to the zombie behind it -- one run read five 4-hp
        # hits as "a short fall" and kept digging until it died.
        self._hp_hist: deque[tuple[int, float]] = deque()
        self._last_hit_step = -1000
        self._last_repeat_note = -1000
        self._reflex: dict[str, Any] | None = None
        #: The last capped bunker: {"step", "cell"} (see _in_hole).
        self._last_bunker: dict[str, Any] | None = None
        #: Where the avatar is: "the Overworld" until a portal wait confirms "the Nether"
        #: or "the End" (macros_nether._dimcheck_tick / macros_end._endcheck_tick); a
        #: death puts it back (respawn is in the Overworld). The End has no ground to run
        #: on -- the island's edge is the void (a staged scene on the merged tree:
        #: the flee reflex sprinted the avatar off the platform to y -272).
        self._dimension = "the Overworld"
        #: The Nether lock: every
        #: Nether visit on record (four visits, three lives) died within 400 steps of arriving,
        #: all by walking, sprinting or jumping off a ledge into the lava sea (y ~31): one run
        #: pressed forward+sprint+jump down a slope from y 36 to 28 with LAVA AHEAD in its
        #: notes; one run's go_to walked into a 13-block hole above the lake; another's explore
        #: walked down-slope to the lake's edge and fell in placing a bridge. A sneaking
        #: avatar cannot step off an edge, so here every plan action that moves gets sneak,
        #: loses sprint, and loses a jump taken while moving (a vertical pillar jump keeps
        #: it); the runner's own escape reflexes are not touched (`_nether_lock`). One
        #: NETHER LOCK note per visit says so. Sneaking does NOT hold an edge in this
        #: engine (measured: the position overhangs ~0.25 and falls), it
        #: walks at ~0.055 blocks a tick, a quarter of a walk -- so the lock buys the
        #: sampled guards four times the ticks per block, and the prevention itself is
        #: `_nether_descent_guard`: a plan entry that has walked the avatar a block DOWN
        #: with lava in the lower view is dropped on the spot.
        self._nether_lock_noted = False
        self._nether_lava = 0.0
        # Act turns since ground truth last moved (a milestone or any inventory change):
        # the turn prompt shows the count.
        self._stall_turns = 0
        self._progress_marker: tuple | None = None
        # Plan-repetition streak: token-set signature of the last plan text and how
        # many consecutive act turns stayed near-identical to it. One run issued seven
        # copies of "Collect the nearby log drops" in a row; the count makes that
        # visible as a fact the way _proc_fails does for guard stops.
        self._plan_sig: frozenset | None = None
        self._plan_repeat = 0
        self._plan_repeat_since = 0
        self.cursor_stats = {
            "anchored": 0, "missed": 0, "drift_sum": 0.0, "drift_max": 0.0,
            "servo_ok": 0, "servo_unverified": 0, "servo_gave_up": 0,
            "chop_early_stops": 0, "close_blocked": 0,
        }

    # -- system prompt ----------------------------------------------------

    def start(self, info: dict) -> None:
        # AGENTS.md is written once. Rewriting it mid-episode would change the agent's
        # standing instructions underneath it, and Codex only reads it at thread start.
        contract = self._act_prompt()
        if self.thin or self.minimal:
            # direct has no file tools: what the short contract moves out is dropped
            # for it, and the procedures keep their descriptions in place
            contract, refs = prompts.thin_split(
                contract, tools=self.memory_mode != "direct",
                safety="" if (self.reflexes or self.minimal) else prompts.THIN_SAFETY)
            if self.minimal:
                tail = (contract[contract.index("**References.**"):]
                        if "**References.**" in contract else "")
                if self.own:
                    from mcu_worldmodel import own as _own
                    refs["own.md"] = (_own.MFM_OWN_NOTE + "\n\n" + _own.MFM_WORKING_NOTE
                                      + (("\n\n" + _own.reflex_note(self.reflexes)) if self.own_reflexes else "")
                                      + (("\n\n" + _own.loop_note(self.frame_size)) if self.own_live else "")
                                      + "\n")
                    tail = tail.rstrip("\n") + ("\n- `references/own.md`: the contract for your own "
                                                "procedures, reflexes and working memory (stdin "
                                                "state, output shapes, caps)\n")
                contract = prompts.minimal_contract(
                    task_text=self.task_text, progress_block=self.ledger.progress_block(),
                    entry_cap=self.entry_cap, step_cap=self.step_cap, atoms=self.atoms,
                    frames=self.frames, harness_reflexes=self.reflexes,
                    previous=bool(getattr(self.episodes, "previous", None)),
                    references_tail=tail)
            if self.atoms and refs.get("skills.md"):
                # the situations reference names the task-shaped macros: say they are recipes here
                from mcu_worldmodel import own as _own
                refs["skills.md"] = _own.atoms_ref_line() + "\n\n" + refs["skills.md"]
            if refs:
                self.memory.write_references(refs)
        if self.skills:
            from mcu_worldmodel import skills as _skills
            written = _skills.write_skills(self.memory.root)
            logger.info(f"[agent] skills package: {len(written)} file(s) written")
            contract = contract.rstrip() + "\n" + _skills.SKILLS_NOTE + "\n"
        if self.own_live:
            contract = contract.rstrip() + "\n\n" + _own.LIVE_NOTE + "\n"
        self.codex.write_system_prompt(contract)
        if self.cli == "claude":
            # The skills and references were written naming codex's image tool; on this
            # channel the tool is Read (claude_backend.rename_image_tool). Rewritten in
            # place, once, before the first turn reads them.
            from mcu_worldmodel.claude_backend import rename_image_tool
            n = 0
            for sub in ("skills", "references"):
                d = self.memory.root / sub
                if not d.is_dir():
                    continue
                for f in sorted(d.rglob("*")):
                    if f.is_file() and f.suffix in (".md", ".py", ".txt"):
                        t = f.read_text(encoding="utf-8")
                        t2 = rename_image_tool(t)
                        if t2 != t:
                            f.write_text(t2, encoding="utf-8")
                            n += 1
            logger.info(f"[agent] claude channel: image tool renamed in {n} skill/reference file(s)")
        self.ledger.reset(info)
        pos = location(info)
        frame = self._save_frame(info, 0)
        self.memory.write_initial(self.task_text, pos, frame)
        if self.episodes:
            self.episodes.initial(info, 0, self._encode_pov(info.get("pov"), 0))
        self._prev_pos = pos
        self._cur_inv = inventory_counts(info)
        self._empty_slot = _first_empty_slot(info)
        self._entry_start_inv = dict(self._cur_inv)
        self._sync_cursor(info)

    def _act_prompt(self) -> str:
        return prompts.act_prompt(
            task_text=self.task_text,
            progress_block=((self.ledger.progress_line() + "\n"
                             + self.ledger.progress_block()) if self.ledger.cfg else ""),
            entry_cap=self.entry_cap, step_cap=self.step_cap,
            platform_prompt=self.platform_prompt,
            memory_mode=self.memory_mode,
            task_family=prompts.task_family(self.ledger.cfg),
            scored_by_milestones=bool(self.ledger.cfg),
            retrieval=self.retrieval,
            previous=bool(self.episodes is not None and self.episodes.previous is not None),
            expect=self.expect, frames=self.frames, own=self.own, atoms=self.atoms,
            own_reflexes=self.own_reflexes,
            harness_reflexes=self.reflexes,
        )

    # -- observation ------------------------------------------------------

    def _save_frame(self, info: dict, step: int) -> str | None:
        """Write the current view to disk at full render resolution.

        `info['pov']` and not `obs['image']`: MinecraftSim resizes the observation to
        `obs_size` (128x128 by default) for neural policies, but keeps the original
        640x360 render in info. A frame the agent is meant to *read* -- an inventory GUI,
        a distant ore vein, a mob at range -- does not survive 128x128, and downsampling
        here would throw away the only channel that carries what the numbers cannot.
        """
        data = self._encode_pov(info.get("pov"), step)
        if data is None:
            return None
        rel = self.memory.save_frame(step, data)
        self._last_frame = rel
        return rel

    def _encode_pov(self, pov, step: int, native: bool = False) -> bytes | None:
        """PNG-encode a pov array at the run's frame size (`native`: as it came), or
        None on any failure."""
        if pov is None:
            return None
        try:
            arr = np.asarray(pov)
            if arr.dtype != np.uint8:
                arr = arr.astype(np.uint8)
            img = Image.fromarray(arr)
            if not native and img.size != self.frame_size:
                img = img.resize(self.frame_size, Image.BILINEAR)
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"[agent] could not save frame at step {step}: {e}")
            return None

    def observe(self, info: dict, step: int) -> None:
        """Record one environment step. Ground truth only -- no model involved."""
        self.step = step
        fired = self.ledger.update(info, step)
        if fired:
            self._pending_events += [f"MILESTONE {f['identity']} verified" for f in fired]
            head0 = self.queue[0][0] if self.queue else None
            if (self.queue and not self._harvesting() and not self._gui_open
                    and macros.kind_of(head0) is None):
                # The milestone chain is ordered, so ground truth that one just fired
                # changes what the right next action is: after `mine_log` the move is to
                # craft, not to keep chopping. Without this the rest of a plan runs to the
                # end first -- up to `step_cap` (400) ticks of an intention the world has
                # already moved past. Dropped before the entry-done check below, so the
                # abandoned entry is still logged with the position it reached.
                # Exception: harvest_tree. Its first log IS the mine_log milestone, and
                # its whole point is the three logs after it; one run lost 400-500 steps of
                # hand-chopping to this drop on its very first call.
                # Exception: a screen is open. A craft_item milestone fires the moment
                # the output is lifted, and the entries behind that click (bank it,
                # close the screen) are what make the milestone bankable -- a staged scene
                # ended every craft milestone with the product riding
                # the cursor and a refused close.
                # Exception: a module macro (macros.TICKS) is at the head. Those are
                # goal-directed and end themselves (build_wall places its N blocks;
                # a use_item milestone fired by block 1 must not drop blocks 2-N).
                logger.info(f"[agent] milestone verified at step {step}: dropping "
                            f"{len(self.queue)} queued action(s) and re-planning")
                self.queue.clear()
        stats = self.ledger.stat_events(info)
        if stats:
            self._pending_events += [f"{s['event']} {s['item']} +{s['delta']:g}"
                                     for s in stats]
            for s in stats:
                if s["event"] == "craft_item" and self.cursor.is_open:
                    gone = self.cursor.crafted(str(s["item"]), int(round(s["delta"])))
                    if gone:
                        self.cursor_stats["craft_writeoffs"] = (
                            self.cursor_stats.get("craft_writeoffs", 0) + 1)
            # Running counts of blocks BROKEN, which is what a chop macro keys on. Wood
            # breaking proves the aim; anything else breaking names what the crosshair
            # is actually on -- one run spent 4,000 steps and 25 chop calls gaining one
            # log because every miss ran its full duration with the answer (leaves) in
            # the stat stream the whole time.
            for s in stats:
                # The sword's use statistic rises on a hit that lands (and on a block it
                # breaks); kills are the kill rule's own event. Cut per own entry below.
                if s["event"] == "use_item" and "sword" in str(s["item"]):
                    self._tally["hits"] += float(s["delta"])
                elif s["event"] == "kill_entity":
                    self._tally["kills"] += float(s["delta"])
            for s in stats:
                if s["event"] != "mine_block":
                    continue
                if "log" in s["item"]:
                    self._log_breaks += s["delta"]
                else:
                    self._other_breaks += s["delta"]
                    self._last_break_item = s["item"]
        pos = location(info)
        # Survival ground truth, checked before the position rolls over. One run died
        # twice -- at y=16 with the run's purpose in reach, then again jumping into its
        # own shaft after the drops -- and the only trace in its memory was its own
        # guess. A death is a position teleport to spawn with health restored; damage is
        # a health drop. Both void the running plan: whatever macro was executing, the
        # world has changed out from under it.
        hp_raw = info.get("health")
        hp = (float(hp_raw.item()) if isinstance(hp_raw, np.ndarray)
              else float(hp_raw) if hp_raw is not None else None)
        prev = self._cur_pos
        if prev and pos:
            jump = (abs(pos["x"] - prev["x"]) + abs(pos["y"] - prev["y"])
                    + abs(pos["z"] - prev["z"]))
            # A portal trip is a teleport too: the coordinates divide by 8 and the
            # height changes, health untouched. While an enter_portal wait (`_dimcheck`)
            # heads the queue the jump is the trip it is waiting for, not a death
            # (a staged scene: the first Nether arrival was logged as "YOU DIED"
            # and the queue -- with the marker that would have said "the Nether" --
            # was cleared).
            # The End portal's `_endcheck` (macros_end.enter_end) is the same wait.
            portal_wait = bool(self.queue) and any(
                k in self.queue[0][0] for k in ("_dimcheck", "_endcheck"))
            if jump > 15 and (hp is None or hp >= 19.0) and not portal_wait:
                self.cursor_stats["deaths"] = self.cursor_stats.get("deaths", 0) + 1
                self.grid.mark_hazard(step, prev, 20.0, "death")
                self.memory.add_note(
                    f"YOU DIED at ({prev['x']:.0f}, {prev['y']:.0f}, {prev['z']:.0f}) "
                    f"and respawned at ({pos['x']:.0f}, {pos['y']:.0f}, "
                    f"{pos['z']:.0f}). Everything you carried dropped at the death "
                    f"point and despawns after ~6000 ticks. Decide now: recover it "
                    f"(stair_down beside the site -- NEVER jump into an open shaft, "
                    f"that is how the second death happened) or rebuild from scratch."
                    + self._dying_during())
                self.queue.clear()
                # The world moved out from under the reflex and the damage window.
                self._reflex = None
                self._last_bunker = None
                self._hp_hist.clear()
                self._dimension = "the Overworld"
            elif (self.near_deaths and (hp is None or hp >= 19.0) and not portal_wait
                  and self._respawned_here(prev, pos, info)):
                # The same death, without the teleport that names it above: the avatar
                # died where it respawns (a fight at the spawn, a fall onto it). The
                # consequences are the same ones.
                self.cursor_stats["deaths"] = self.cursor_stats.get("deaths", 0) + 1
                self.cursor_stats["near_deaths"] = self.cursor_stats.get("near_deaths", 0) + 1
                self.grid.mark_hazard(step, prev, 20.0, "death")
                self.memory.add_note(
                    f"YOU DIED at ({prev['x']:.0f}, {prev['y']:.0f}, {prev['z']:.0f}) "
                    f"and respawned at ({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f}), "
                    f"{jump:.0f} block(s) from there. Everything you carried and wore "
                    f"dropped at the death point and despawns after ~6000 ticks; health "
                    f"and food are full again and the camera is back at pitch 0, yaw 0. "
                    f"What killed you is still where it was: look before you go back "
                    f"for the pile." + self._dying_during())
                self.queue.clear()
                self._reflex = None
                self._last_bunker = None
                self._hp_hist.clear()
                self._dimension = "the Overworld"
        if hp is not None:
            self._hp_hist.append((step, hp))
            while self._hp_hist and step - self._hp_hist[0][0] > 100:
                self._hp_hist.popleft()
        tick_drop = ((self._last_health - hp)
                     if (hp is not None and self._last_health is not None) else 0.0)
        slow_drop = ((self._hp_hist[0][1] - hp)
                     if (hp is not None and len(self._hp_hist) > 1) else 0.0)
        repeat_hit = (hp is not None and tick_drop >= 3.0
                      and step - self._last_hit_step <= 120)
        # A combat macro IS the response to the attacker (macros.COMBAT: fight,
        # face_entity, shoot_bow, block_with_shield, use_on_entity). Turning the avatar
        # 180 degrees away from the mob it is aiming at, and dropping the rest of the
        # plan, aborts the fight on the mob's FIRST swing -- so a combat head survives
        # a first hit the way a moving head survives a repeated one. Each of those
        # macros carries its own retreat rule; below CRITICAL_HP the pillar escape
        # below still wins, unchanged.
        combat_head = (macros.kind_of(self.queue[0][0]) in macros.COMBAT
                       if self.queue else False)
        # Under own_live a closed loop of the model's own at the head is its combat
        # macro: it reads its health and the frame at every call, and its reflexes are
        # its retreat rule. Treated as "a plan standing still", every fight entry of
        # three probe lives ended on the first hit it took (6.4 a hit on hard), and the
        # model replanned after each exchange. Below CRITICAL_HP the stop still wins.
        if self.own_live and self.queue and self._entry_is_loop(self.queue[0][1]):
            combat_head = True
        combat_hit = (combat_head and hp is not None
                      and (tick_drop >= 3.0 or slow_drop >= 3.0))
        if (repeat_hit or combat_hit) and (
                (self._head_is_movement() or combat_head) and hp > self.CRITICAL_HP):
            # Lava, fire, drowning, a mob that keeps swinging: the first hit already
            # interrupted the plan and turned the avatar. Interrupting AGAIN on every
            # damage tick cut one run's escape plan ("left + jump x80") to ten ticks
            # at a time, and each 180-degree turn made "left" the opposite direction --
            # it swam in circles in lava at 4 hp per interrupt. So a plan that MOVES
            # the avatar keeps running; the loss is logged (at most every 40 ticks)
            # and the hazard node keeps merging. A plan that mines, sweeps or clicks
            # in place while the hits keep coming is a different thing: one run took
            # 16 -> 14 -> 2 -> dead inside one stair_down at y28 (cave spiders), the
            # macro digging the whole time -- that plan is interrupted below like a
            # first hit, and so is anything once health is critical.
            self._last_hit_step = step
            self.cursor_stats["damage_repeats"] = (
                self.cursor_stats.get("damage_repeats", 0) + 1)
            if step - self._last_repeat_note >= 40:
                self._last_repeat_note = step
                where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos
                         else "an unknown position")
                self.memory.add_note(
                    f"still taking damage -- health {hp:.0f}/20 at {where}; the plan "
                    f"keeps running (get out of whatever is hurting you first).")
        elif hp is not None and (
                tick_drop >= 3.0
                or (slow_drop >= 3.0 and step - self._last_hit_step > 100)):
            was_repeat = repeat_hit
            prev_hit_step = self._last_hit_step
            self._last_hit_step = step
            self.grid.mark_hazard(step, pos, tick_drop if tick_drop >= 3.0 else slow_drop,
                                  "damage")
            self._keep_event_frame(step, "hit", info.get("pov"))
            self.cursor_stats["damage_interrupts"] = (
                self.cursor_stats.get("damage_interrupts", 0) + 1)
            if was_repeat:
                self.cursor_stats["damage_repeat_interrupts"] = (
                    self.cursor_stats.get("damage_repeat_interrupts", 0) + 1)
            kind = (f"took {tick_drop:.0f} damage" if tick_drop >= 3.0
                    else f"lost {slow_drop:.0f} health over the last 100 ticks")
            if was_repeat:
                kind = ("STILL under attack: " + kind
                        + (f" -- health {hp:.0f}/20 is CRITICAL, get out of reach "
                           f"(pillar up two blocks or wall the tunnel off with "
                           f"cobblestone) before anything else"
                           if hp <= self.CRITICAL_HP else
                           " while the plan stood still (mining/sweeping/clicking); "
                           "the runner stopped it -- deal with the attacker or move"))
            where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos
                     else "an unknown position")
            reflex = ""
            active = self._reflex.get("kind") if self._reflex else None
            # The frame of THIS observation (the `_last_pov` slot still holds the previous
            # one here); the End has no lava, so its frames are never read for it.
            frame = info.get("pov")
            frame = self._last_pov if frame is None else frame
            lava_now = fire_now = water_now = 0.0
            submerged = False
            if (pos and frame is not None and not info.get("isGuiOpen", False)
                    and self._dimension != "the End"):
                lava_now = vision.lava_fraction(np.asarray(frame))
                fire_now = vision.fire_fraction(np.asarray(frame))
                water_now = vision.water_view(np.asarray(frame), rows_from=0.30)[0]
                # Head under lava: neither detector above sees it (vision.lava_submerged).
                submerged = (vision.lava_submerged(np.asarray(frame))
                             >= vision.LAVA_SUBMERGED_MIN)
            # Lava's damage is exactly 4.0 every 10 ticks (a zombie on hard 4.5, an
            # arrow 2-5, fire 1, drowning 2): a 4.0 loss with any lava in view is lava
            # contact. Two runs took their first lava hit with under 15%
            # in the frame and got the bunker (dug INTO the pool) and the 180-degree
            # turn instead; both burned to death at the pool they had just found.
            # Inside the pool the frame is fog, not the lava texture (a staged scene: 2% at
            # the first hit while chest-deep in it), so the second sign is the ground:
            # the 4.0 loss while the avatar stands lower than the dry trail beside it.
            touch = (3.9 <= tick_drop <= 4.1 and self._dimension != "the End"
                     and bool(pos) and float(pos["y"]) < self.BUNKER_Y)
            sunk = False
            if touch and lava_now < self.LAVA_TOUCH_FRAC:
                home_cell = self._lava_home_cell(pos)
                sunk = home_cell is not None and home_cell[1] - float(pos["y"]) >= 0.4
            lava_hit = (submerged or lava_now >= self.LAVA_ESCAPE_FRAC
                        or fire_now >= vision.FIRE_FRAC_MIN
                        or (touch and (lava_now >= self.LAVA_TOUCH_FRAC or sunk)))
            # Drowning evidence is water: in the frame now, or seen by the guard lately
            # within reach of this spot -- the frame at the interrupt itself is often a
            # shaft wall (one run's two hit frames read no water from the flooded
            # shaft's floor). A fractional y alone is NOT evidence: every jump arc,
            # slab, soul-sand and falling tick has one (9% of all archived position
            # rows), and it outranked the pillar at 1 hp mid-jump (audit pass 17).
            seen = self._last_water_seen
            seen_d = (math.hypot(float(pos["x"]) - seen[1], float(pos["z"]) - seen[2])
                      if (pos and seen is not None) else None)
            recent_water = (seen_d is not None
                            and step - seen[0] <= self.DROWN_WATER_STEPS
                            and seen_d <= self.DIG_WATER_BLOCKS
                            and self._dimension != "the End")
            drown_hit = (not lava_hit and tick_drop < 3.0 and slow_drop >= 3.0
                         and (water_now >= self.DROWN_WATER_FRAC or recent_water))
            # A melee mob at arm's length: the second hit inside MELEE_CADENCE ticks,
            # underground and low. The knockback (a shove while the plan stood still)
            # says which way is away from it.
            # (a gap under 4 ticks is one blow's damage arriving in two observations --
            # an instant-damage effect on a staged scene read 20 -> 17 -> 13 on consecutive
            # ticks -- not a second swing: a zombie's cooldown is 20 ticks)
            melee_now = (bool(pos) and hp is not None and tick_drop >= 3.0
                         and 4 <= step - prev_hit_step <= self.MELEE_CADENCE
                         and float(pos["y"]) < self.BUNKER_Y and hp <= self.BUNKER_HP
                         and not lava_hit and not drown_hit
                         and self._dimension != "the End")
            away_yaw = None
            if melee_now and self._prev_pos is not None and not self._head_is_movement():
                kx = float(pos["x"]) - float(self._prev_pos["x"])
                kz = float(pos["z"]) - float(self._prev_pos["z"])
                if math.hypot(kx, kz) >= self.KNOCKBACK_MIN:
                    away_yaw = norm_yaw(math.degrees(math.atan2(-kx, kz)))
            # A bunker under way is NOT abandoned for further hits (a staged scene:
            # aborted at the second hit, the flee ran into the mining face, 20 -> 5 hp;
            # the dig takes 2-3 hits and the cap ends them for good).
            if active == "fightback":
                if hp <= self.CRITICAL_HP and not self._reflex.get("desperate"):
                    self._finish_fightback(self._reflex, "health critical, the run takes over")
                    active = None
                elif away_yaw is not None:
                    # the shove says where it stands now: face that way again
                    self._reflex["yaw"] = norm_yaw(away_yaw + 180.0)
                    self._reflex["phase"] = "turn"
            if (lava_hit or drown_hit) and active in ("bunker", "flee", "fightback"):
                # a dig that opened into lava or water, or a run that ended in it: the
                # escape takes over (one run burned while the runner dug beside it)
                if active == "bunker":
                    self._finish_bunker(self._reflex, "the dig met lava" if lava_hit
                                        else "the dig flooded")
                elif active == "fightback":
                    self._finish_fightback(self._reflex, "lava ahead" if lava_hit else "water ahead")
                else:
                    self._finish_flee(self._reflex, "lava ahead" if lava_hit else "water ahead")
                active = None
            if active == "pillar":
                reflex = " The runner is still pillaring you up."
            elif active == "bunker" and melee_now and self._weapon_slot(info) is not None:
                # One run (y 11 at the bottom of its own shaft): the zombie
                # that fell down the shaft was in the cell; the bunker dug two blocks
                # with it aboard and capped them both in -- 4.5 hp every 20 ticks,
                # dead at step 2603 with a diamond sword in the inventory. A melee hit
                # while the dig is under way means the mob is coming down with you.
                weapon = self._weapon_slot(info)
                shaft = self._in_shaft(self._reflex["cell"])
                self._finish_bunker(self._reflex, "a melee mob is coming down with you")
                face = norm_yaw((away_yaw + 180.0) if away_yaw is not None
                                else (float(pos["yaw"]) + 180.0))
                self._reflex = self._arm_fightback(pos, hp, face, weapon, desperate=shaft,
                                                   toward_center=True)
                self.cursor_stats["bunker_followed"] = (
                    self.cursor_stats.get("bunker_followed", 0) + 1)
                reflex = (f" Two hits {step - prev_hit_step} ticks apart while the runner "
                          f"dug the bunker: the melee mob is at arm's length and comes "
                          f"DOWN WITH you -- a hole holds you both (one life was capped in "
                          f"with a zombie and died). The bunker is abandoned; the runner "
                          f"is FIGHTING BACK with the {weapon[1]} (hotbar {weapon[0]}) "
                          f"for up to {self.FIGHTBACK_TICKS} ticks, turning the aim a "
                          f"quarter whenever the swings land nothing"
                          + (" -- you are at the bottom of your own shaft, there is "
                             "nowhere to run, so it fights to the end" if shaft else
                             f"; below {self.CRITICAL_HP:.0f} hp the run takes over")
                          + "; your next turn comes from where the fight ends. If the "
                          "hits have stopped, close the shaft over your head FIRST "
                          "(a block placed two above your feet against the wall): "
                          "that is the way it reached you"
                          + ".")
            elif active == "bunker":
                reflex = " The runner is still bunkering you (digging down, then capping)."
            elif active == "flee":
                reflex = " The runner is still sprinting you away."
            elif active == "fightback":
                reflex = " The runner is still fighting back (facing the shove, swinging)."
            elif active == "lava":
                reflex = " The runner is still getting you out of the lava (dousing, stepping back)."
            elif active == "drown":
                reflex = " The runner is still swimming you up (jump held)."
            elif pos and (not info.get("isGuiOpen", False) or self._in_hole(pos, step)):
                from mcu_worldmodel import macros_world as MW
                gui_open = bool(info.get("isGuiOpen", False))
                in_hole = self._in_hole(pos, step)
                melee = combat_head
                underground = float(pos["y"]) < self.BUNKER_Y
                # No bunker with lava or fire in view: the dig goes INTO the pool
                # (one run: "the dig met lava", dead 30 ticks later).
                bunker = (self._bunker_plan(info)
                          if (hp <= self.BUNKER_HP and underground
                              and lava_now < self.LAVA_TOUCH_FRAC
                              and fire_now < vision.FIRE_FRAC_MIN) else None)
                slot = self._pillar_slot(info) if hp <= self.CRITICAL_HP else None
                flee_due = (melee and hp <= self.CRITICAL_HP) or melee_now
                in_end = self._dimension == "the End"
                # Precedence: underground a melee attacker means run (a dig or a
                # pillar cannot finish under its swings), anything else means bunker;
                # on the surface the pillar is the answer to melee (out of reach, then
                # the view from the top) and the run is for when no block is at hand.
                # In the End none of them: a blind sprint or a knocked-over pillar ends
                # in the void, so the runner only turns to face the hit.
                if lava_hit:
                    self._reflex = self._arm_lava(info, pos, hp, max(lava_now, fire_now))
                    wb = self._reflex["wb"]
                    reflex = (" The frame shows "
                              + (f"lava filling {100 * lava_now:.0f}% of the lower view"
                                 if lava_now >= self.LAVA_ESCAPE_FRAC else
                                 f"flames over {100 * fire_now:.0f}% of the lower view: you "
                                 f"are BURNING")
                              + ": the damage is the LAVA (or the fire it lit), not "
                              "a mob -- digging or pillaring here would not help. The "
                              "runner is "
                              + (f"DOUSING you: water bucket (hotbar {wb}) poured at your "
                                 f"feet (it puts the fire out and turns the lava you touch "
                                 f"to obsidian/cobblestone), then "
                                 if wb else "")
                              + f"stepping you BACK for {self.LAVA_OUT_TICKS} ticks, away "
                              f"from where you were facing; your next turn comes from "
                              f"there" + ".")
                elif drown_hit:
                    self._reflex = self._arm_drown(pos, hp, water_now)
                    reflex = (" The loss was gradual and "
                              + (f"water fills {100 * water_now:.0f}% of the view"
                                 if water_now >= self.DROWN_WATER_FRAC else
                                 f"water was within reach {step - seen[0]} ticks ago, "
                                 f"{seen_d:.0f} block(s) from here (a shaft dug beside it "
                                 f"floods)")
                              + ": you are DROWNING, not under attack. The runner is holding "
                              f"jump to swim you UP for {self.DROWN_TICKS} ticks (the air comes "
                              f"back at the surface); your next turn comes from there"
                              + ".")
                elif in_end:
                    self.cursor_stats["end_turns"] = self.cursor_stats.get("end_turns", 0) + 1
                    self._reflex = {"yaw": norm_yaw(pos["yaw"] + 180.0),
                                    "remaining": 16}
                    reflex = (" The runner is turning you 180 degrees to face where "
                              "the hit came from -- in the End it never sprints or "
                              "pillars you (the island's edge is the void): stand your "
                              "ground, hit the dragon when it is in reach, break the "
                              "crystals that heal it, and eat when you can"
                              + ".")
                elif in_hole and self._weapon_slot(info) is not None:
                    # The cap is in place and the hit still came: whatever swung is in
                    # the hole (it dropped in as the floor went). Another bunker would
                    # take it two blocks deeper; a wall cannot go between; the sword
                    # (or the pickaxe) to the end, the screen shut first if one is up.
                    weapon = self._weapon_slot(info)
                    lb = self._last_bunker
                    face = norm_yaw((away_yaw + 180.0) if away_yaw is not None
                                    else (float(pos["yaw"]) + 180.0))
                    self._reflex = self._arm_fightback(pos, hp, face, weapon,
                                                       desperate=True, close_gui=gui_open,
                                                       toward_center=True)
                    self.cursor_stats["hole_fightbacks"] = (
                        self.cursor_stats.get("hole_fightbacks", 0) + 1)
                    reflex = (f" The hit reached you INSIDE the capped hole under "
                              f"({lb['cell'][0]}, {lb['cell'][1]}, {lb['cell'][2]}): the "
                              f"attacker is in it with you (it dropped in as the floor "
                              f"went) and no dig or wall gets you apart. The runner is "
                              + ("closing the screen (anything on the cursor drops) and "
                                 if gui_open else "")
                              + f"FIGHTING BACK with the {weapon[1]} (hotbar {weapon[0]}) "
                              f"to the end -- it dies in a few swings or you do; your "
                              f"next turn comes from where the fight ends"
                              + ".")
                elif gui_open:
                    pass        # a screen up: no other reflex (a mob does not wait for it)
                elif (underground and self._sword_slot(info) is not None
                        and self._in_shaft(MW.block_of(pos))):
                    # At the bottom of its own shaft the hit is from what came down it:
                    # it is IN the column, a dig takes it along and a cap seals it in
                    # (one run). With a sword in the hotbar the fight is the answer at the
                    # first hit, while the health is still there (s20: 4.5 hp a hit on
                    # hard, every 20 ticks; two hits later it is 12.5 -> a coin toss).
                    weapon = self._weapon_slot(info)
                    self._reflex = self._arm_fightback(pos, hp, float(pos["yaw"]), weapon,
                                                       desperate=True, toward_center=True)
                    self.cursor_stats["shaft_fightbacks"] = (
                        self.cursor_stats.get("shaft_fightbacks", 0) + 1)
                    reflex = (f" You stand at the bottom of your own shaft: whatever hit "
                              f"you came down it and is IN the cell with you -- a hole dug "
                              f"under you takes it along (one life was capped in with a zombie "
                              f"and died). The runner is FIGHTING BACK with the "
                              f"{weapon[1]} (hotbar {weapon[0]}) to the end, aimed at the "
                              f"middle of your cell; your next turn comes from where the "
                              f"fight ends. If the hits have stopped, close the shaft "
                              f"over your head FIRST (place_at two above your feet, "
                              f"against a wall side)"
                              + ".")
                elif bunker is not None and hp > self.CRITICAL_HP:
                    self._reflex = self._arm_bunker(bunker, pos)
                    reflex = (f" The runner is BUNKERING you: digging two blocks straight "
                              f"down with the {bunker[1]} (hotbar {bunker[0]}) and capping "
                              f"the hole with {bunker[3]} (hotbar {bunker[2]}) -- under a "
                              f"tunnel ceiling a pillar cannot place and a sprint ends at "
                              f"the mining face; a capped hole is out of every mob's reach "
                              f"and it is not abandoned for further hits; your next turn "
                              f"comes from inside it" + ".")
                elif melee_now and underground and self._pillar_slot(info) is not None:
                    # Measured on the relay runs and a staged scene: the blind
                    # fightback dealt 0 damage in 3 reflexes, the fight macro in a dark
                    # tunnel landed one swing for 15 taken, and the bunker was hit into
                    # 4 times out of 4. A zombie cannot break blocks: sprint away, then
                    # wall the tunnel (two blocks, feet and head) between it and you.
                    self._reflex = self._arm_flee(pos, away_yaw, seal=True)
                    reflex = (f" Two hits {step - prev_hit_step} ticks apart: a melee mob is "
                              f"at arm's length. The runner is "
                              + (f"turning you to yaw {away_yaw:.0f} (away from the shove) "
                                 if away_yaw is not None else "turning you around ")
                              + f"and SPRINTING you away for {self.FLEE_TICKS} ticks, then "
                              f"WALLING the tunnel behind you with two blocks -- a mob "
                              f"cannot break blocks; your next turn comes from behind "
                              f"the wall" + ".")
                elif (melee_now and underground and hp > self.CRITICAL_HP
                        and self._sword_slot(info) is not None):
                    # A one-wide tunnel is where the melee cadence is met, and a sprint
                    # there does not outrun a zombie (one run: 8 blocks up its
                    # own staircase, hit every 26 ticks, dead at 4 hp with a diamond sword
                    # in the hotbar). With a sword the answer is to face it and swing.
                    sword = self._sword_slot(info)
                    face = norm_yaw((away_yaw + 180.0) if away_yaw is not None
                                    else (float(pos["yaw"]) + 180.0))
                    self._reflex = self._arm_fightback(pos, hp, face, sword)
                    reflex = (f" Two hits {step - prev_hit_step} ticks apart: a melee mob is "
                              f"at arm's length, and you carry a {sword[1]} (hotbar {sword[0]}). "
                              f"The runner is turning you to yaw {face:.0f} ("
                              + ("where the shove came from" if away_yaw is not None
                                 else "behind you")
                              + f") and FIGHTING BACK with it for up to {self.FIGHTBACK_TICKS} "
                              f"ticks -- in a one-wide tunnel a sprint does not outrun a "
                              f"zombie, a sword kills one in a few swings; below "
                              f"{self.CRITICAL_HP:.0f} hp the run takes over; your next turn "
                              f"comes from where the fight ends"
                              + ".")
                elif (flee_due and (underground or slot is None)
                      and self._dimension != "the Nether"):
                    # (a blind 60-tick sprint in the Nether ends in the lava sea: there
                    # the bunker, the pillar or the turn below answer the hit instead)
                    self._reflex = self._arm_flee(pos, away_yaw)
                    reflex = ((f" Two hits {step - prev_hit_step} ticks apart: a melee mob "
                               f"is at arm's length." if melee_now else "")
                              + " The runner is "
                              + (f"turning you to yaw {away_yaw:.0f} (away from the shove) "
                                 if away_yaw is not None else "turning you around ")
                              + "and SPRINTING you away for 60 ticks -- a melee attacker "
                              "keeps hitting through a dig or a pillar, and a zombie cannot "
                              "keep up with a sprint; your next turn comes from where the "
                              "run ends" + ".")
                elif bunker is not None:
                    self._reflex = self._arm_bunker(bunker, pos)
                    reflex = (f" The runner is BUNKERING you: digging two blocks straight "
                              f"down with the {bunker[1]} (hotbar {bunker[0]}) and capping "
                              f"the hole with {bunker[3]} (hotbar {bunker[2]}) -- under a "
                              f"tunnel ceiling a pillar cannot place, a capped hole is out "
                              f"of every mob's reach; your next turn comes from inside it"
                              + ".")
                elif slot is not None:
                    # One run at 4/20 chose to fight the zombie with a stone pickaxe
                    # and died two turns later, the note above notwithstanding; the
                    # escape is the runner's now: two blocks straight up, out of a
                    # melee mob's reach, then the model gets the view from the top.
                    self._reflex = {"kind": "pillar", "slot": slot[0],
                                    "item": slot[1], "phase": "equip", "t": 0,
                                    "placed": 0, "target": 2, "tries": 0,
                                    "remaining": 90, "y0": float(pos["y"])}
                    self.cursor_stats["pillar_reflexes"] = (
                        self.cursor_stats.get("pillar_reflexes", 0) + 1)
                    reflex = (f" The runner is pillaring you up two blocks on "
                              f"{slot[1]} (hotbar {slot[0]}) -- out of a melee mob's "
                              f"reach; your next turn sees the view from the top: "
                              f"attack it from above or wall off, then continue"
                              + ".")
                else:
                    self._reflex = {"yaw": norm_yaw(pos["yaw"] + 180.0),
                                    "remaining": 16}
                    reflex = (" The runner is turning you 180 degrees to face where "
                              "the hit came from; your next turn sees the view after "
                              "the turn.")
                    if hp <= self.CRITICAL_HP:
                        reflex += (" (No placeable block in your hotbar, so the runner "
                                   "could not pillar you up: keep cobblestone there.)")
            if not getattr(self, "reflexes", True):
                # human-play / --no-harness-reflexes: the note stands, the runner does
                # not act -- and must not say it does
                reflex = (" The runner does not act in this run: the plan stopped, the "
                          "next move is yours.")
            if submerged:
                # Three lives of one chain swam in the Nether's lava sea while this note
                # said "STILL under attack ... pillar up two blocks": the frame from
                # inside lava shows no lava texture, so the loss was read as a mob's.
                self.cursor_stats["submerged_notes"] = (
                    self.cursor_stats.get("submerged_notes", 0) + 1)
                self.memory.add_note(
                    f"YOU ARE IN LAVA -- took {tick_drop:.0f} damage, health {hp:.0f}/20 at "
                    f"{where}: the view is lava's red from edge to edge, and lava takes 4 "
                    f"health every 10 ticks. No mob is here. The plan was interrupted."
                    f"{reflex}")
            else:
                self.memory.add_note(
                    f"{kind} -- health {hp:.0f}/20 at {where}. The plan was interrupted; "
                    f"find the danger (a monster behind you? a fall? lava? drowning or "
                    f"burning if the loss was gradual) before continuing.{reflex}")
            self.queue.clear()
        if not getattr(self, "reflexes", True):
            self._reflex = None             # human-play: the note stands, the runner does not act
        self._last_health = hp
        self._prev_pos = pos
        self._cur_pos = pos
        self._cur_info = info
        self.grid.observe(step, pos)
        self._prev_pov = self._last_pov
        self._last_pov = info.get("pov")
        self._lava_guard(step, pos)
        self._shaft_guard(step, pos)
        self._fall_guard(step, pos)
        self._nether_descent_guard(step, pos)
        self._water_guard(step, pos)
        self._cur_inv = inventory_counts(info)
        if self.own_reflexes:
            self._own_reflex_tick(step, info)
        if (self.reflexes and not self._sword_nudged and self.stat_now("craft_item", "stone_pickaxe") >= 1
                and not any(k.endswith("_sword") for k in self._cur_inv)):
            # Nine arms crafted no sword; the one that fought a zombie
            # with its pickaxe (one run, y 18) died. The doctrine line in the prompt
            # was not enough; the moment the table is open for the pickaxe is the moment.
            self._sword_nudged = True
            self.cursor_stats["sword_nudges"] = self.cursor_stats.get("sword_nudges", 0) + 1
            self.memory.add_note(
                "stone pickaxe done and no sword carried: a stone sword is 2 cobblestone "
                "+ 1 stick in the table (3x3) and kills a zombie in 4 hits where a pickaxe "
                "needs 7 -- craft it now, before going deep, and keep it in the hotbar.")
        coal = self.stat_now("mine_block", "coal_ore")
        if coal > self._coal_seen:
            self._coal_seen = coal
            if not self._cur_inv.get("torch") and step - self._last_torch_nudge > 3000:
                # Eight arms mined 0-10 coal each and crafted no torch;
                # their ore watch ran blind in unlit tunnels the whole night.
                self._last_torch_nudge = step
                self.cursor_stats["torch_nudges"] = self.cursor_stats.get("torch_nudges", 0) + 1
                self.memory.add_note(
                    "coal in hand and no torches carried: 1 coal + 1 stick = 4 torches "
                    "(a 2x2 recipe, the inventory screen; charcoal from a smelted log "
                    "works the same). The ore watch cannot see ore colours in an unlit "
                    "tunnel -- place a torch on a wall's side face every ~8 blocks as "
                    "you mine.")
        self._empty_slot = _first_empty_slot(info)
        self._sync_cursor(info)
        if self.episodes:
            self.episodes.observe(info, step)
        # The entry just executed is finished when the next queued action belongs to a
        # different entry (or the queue is empty). Cleared after logging so the entry is
        # written exactly once -- `next_action` logs the entries that finish between
        # observes (closed-loop markers) and must be able to tell these apart.
        if self._entry_index is not None:
            nxt = self.queue[0][1] if self.queue else None
            if nxt != self._entry_index:
                self._log_entry_done(self._entry_index)
                self._entry_index = None

    def _sync_cursor(self, info: dict) -> None:
        """Reconcile the tracked cursor with the screen the game says is open.

        `isGuiOpen` is the authority, not the harness's model of the `inventory` toggle:
        a screen can open without the agent pressing anything (right-clicking a crafting
        table) and close without it either. On the rising edge the cursor is placed at the
        measured opening position and the inventory baseline is taken, which is what makes
        `off_inventory` mean "since this screen opened" rather than "since the episode
        started".

        On the falling edge, anything still off-inventory has just hit the floor. That is
        written as a [NOTE] because it is the single most expensive GUI mistake this agent
        made -- it repeatedly dropped its materials and re-collected them, and from inside
        the episode there was nothing to say so.

        The close-tick diff alone is blind to WITHIN-inventory moves: an item riding the
        cursor between slots never leaves the inventory count, so an involuntary close
        (container auto-close out of reach) drops it with a zero diff -- one run lost its
        stone pickaxe exactly this way, silently, and burned its endgame on a recovery
        gamble built from inference. Hence the one-tick recheck below: the drop lands in
        the observation a tick later, and a loss with no matching gain (no craft output
        collected) gets its own [NOTE] with the position to sweep.
        """
        gui_open = bool(info.get("isGuiOpen", False))
        if gui_open:
            kind = vision.screen_kind(self._last_pov)
            if kind is not None:
                self._screen = kind
        if self._close_recheck is not None:
            base, noted, pos_txt = self._close_recheck
            self._close_recheck = None
            missing = {k: was - self._cur_inv.get(k, 0) - noted.get(k, 0)
                       for k, was in base.items()
                       if was - self._cur_inv.get(k, 0) - noted.get(k, 0) > 0}
            gained = any(self._cur_inv.get(k, 0) > base.get(k, 0) for k in self._cur_inv)
            if missing and not gained:
                txt = ", ".join(f"{k}x{v}" for k, v in sorted(missing.items()))
                self.memory.add_note(
                    f"after the screen closed, {txt} never made it back to the "
                    f"inventory -- it was riding the cursor and dropped {pos_txt}. "
                    f"Walk over that spot now to recover it.")
        if gui_open and not self._gui_open:
            self.cursor.opened(self._cur_inv)
        elif not gui_open and self._gui_open:
            base = dict(self.cursor.baseline or {})
            dropped = self.cursor.off_inventory(self._cur_inv)
            p = self._cur_pos
            if self._screen in macros.KEEPS_CONTENTS:
                # A furnace (or chest, brewing stand...) keeps its contents across a
                # close: what is "off-inventory" sits in it, not on the floor. Without
                # this every smelt ended with a note that sent the model sweeping the
                # floor.
                if dropped:
                    txt = ", ".join(f"{k}x{v}" for k, v in sorted(dropped.items()))
                    self.memory.add_note(
                        f"the {self._screen} screen closed with {txt} in the "
                        f"{self._screen} (it keeps its contents across a close) -- "
                        f"nothing is on the floor unless it was riding the cursor. "
                        f"Open it again to take things out.")
                self.cursor_stats["furnace_closes"] = (
                    self.cursor_stats.get("furnace_closes", 0) + 1)
            else:
                self._close_recheck = (base, dict(dropped),
                                       f"at ({p['x']:.0f}, {p['z']:.0f})" if p
                                       else "where you stood")
                if dropped:
                    txt = ", ".join(f"{k}x{v}" for k, v in sorted(dropped.items()))
                    self.memory.add_note(
                        f"the screen closed with {txt} not in any inventory slot. "
                        f"Anything that was in the cursor is now an item entity on the "
                        f"floor -- walk over it to pick it back up, and put items back "
                        f"in a slot before closing next time."
                    )
            self.cursor.closed()
            self._screen = None
        elif gui_open:
            self.cursor.off_inventory(self._cur_inv)   # refresh `current`
        self._gui_open = gui_open
        # Measure the pointer in the frame and overwrite the dead-reckoned position.
        # This is the drift fix: the sum of emitted deltas was 60 px wrong after one long
        # GUI session (see vision.py), and every absolute address computed from it missed.
        if gui_open:
            pov = info.get("pov")
            hit = vision.find_cursor(np.asarray(pov)) if pov is not None else None
            if hit is not None:
                ox, oy = gui.container_origin(*self.cursor.render)
                drift = self.cursor.anchor((hit[0] - ox, hit[1] - oy), self.step)
                st = self.cursor_stats
                st["anchored"] += 1
                st["drift_sum"] += drift
                st["drift_max"] = max(st["drift_max"], drift)
                self._vision_miss_streak = 0
            else:
                self.cursor_stats["missed"] += 1
                self._vision_miss_streak += 1

    # -- the act turn -----------------------------------------------------

    def next_action(self, info: dict) -> dict[str, Any]:
        """One env action. Fires a turn only when the queue is dry.

        A queue entry is either a plain env action or a closed-loop marker that resolves
        against the current tick's state: a `_servo` steers toward its target using the
        position `_sync_cursor` just measured from the frame, a `_chop` holds attack until
        wood lands, `_allow_close` arms one forced screen close. A marker stays at the
        head of the queue until it declares itself done, so the (action, entry) pairing
        and the entry-done log both keep working.
        """
        from mcu_worldmodel.procedures import act as mk_act, noop

        self._judge_pending_click()
        # Post-completion hold: every configured milestone is verified, so no model
        # turn can raise the score -- it can only spend wall-clock and calls (a
        # completed run idled ~30 s/turn, one step per call, for its last ~1000
        # steps). Coast to the horizon on no-ops instead. Keys only on the verified
        # events every memory mode already sees, so the whole ladder shares it.
        if self.ledger.cfg and len(self.ledger.achieved) == len(self.ledger.cfg):
            if "completion_hold" not in self.cursor_stats:
                logger.info(f"[agent] all {len(self.ledger.cfg)} milestones verified "
                            f"by step {self.step}: coasting on no-ops to episode end")
            self.cursor_stats["completion_hold"] = (
                self.cursor_stats.get("completion_hold", 0) + 1)
            return noop()
        if self._reflex is not None:
            action = self._reflex_tick(mk_act)
            if action is not None:
                return action
        # A raw attack-hold is cut the moment its block breaks. Markers already key on
        # the stat stream; plain steps popped blind ran a 100-tick attack 71 ticks past
        # the grass it was written for (one run, step 5242). Multi-block digs belong
        # to mine_forward/strip_mine, which re-aim between blocks.
        total_breaks = self._log_breaks + self._other_breaks
        if total_breaks > self._breaks_seen:
            self._cut_attack_hold()
        self._breaks_seen = total_breaks
        for _ in range(2):
            while self.queue:
                head, idx = self.queue[0]
                if idx != self._entry_index:
                    self._entry_index = idx
                    self._entry_start_pos = self._cur_pos
                    self._entry_start_inv = dict(self._cur_inv)
                    self._entry_tally0 = {"step": self.step, "hits": self._tally["hits"],
                                          "kills": self._tally["kills"],
                                          "deaths": self.cursor_stats.get("deaths", 0),
                                          "health": self._last_health}
                    if self.episodes and 0 <= idx < len(self._plan_entries):
                        self.episodes.open(
                            self._plan_entries[idx], idx, len(self._plan_entries), info,
                            self.step, self._encode_pov(info.get("pov"), self.step))
                if "_allow_close" in head:
                    self._close_armed = True
                    self.queue.popleft()
                    continue
                if "_ownloop" in head:
                    # A closed-loop own procedure (own.py, `own_live`): the script is
                    # run on THIS tick's state and frame, and what it returns goes in
                    # front of the marker under the same entry; the marker is back at
                    # the head when those have run. False: the loop is over.
                    if not self._own_loop_step(head["_ownloop"], idx, info):
                        self.queue.popleft()
                        nxt = self.queue[0][1] if self.queue else None
                        if nxt != idx:
                            self._log_entry_done(idx)
                            self._entry_index = None
                    continue
                _MARKERS = {"_servo": self._servo_tick, "_chop": self._chop_tick,
                            "_dig": self._dig_tick, "_use_gui": self._use_gui_tick,
                            "_opengui": self._opengui_tick,
                            "_closegui": self._closegui_tick,
                            "_click": self._click_tick,
                            "_goto": self._goto_tick, "_seq": self._seq_tick,
                            "_lookabs": self._lookabs_tick,
                            "_aimore": self._aimore_tick,
                            "_aimtree": self._aimtree_tick,
                            "_harvest": self._harvest_tick,
                            "_sweep": self._sweep_tick,
                            "_mfwd": self._mfwd_tick}
                kind = next((k for k in _MARKERS if k in head), None)
                ext = None if kind is not None else macros.kind_of(head)
                if kind is not None or ext is not None:
                    if kind is not None:
                        action = (self._servo_tick(head["_servo"]) if kind == "_servo"
                                  else _MARKERS[kind](head[kind], mk_act))
                    else:
                        # A marker owned by a macro module (see macros.py): same
                        # contract, dispatched by key without touching this table.
                        action = macros.TICKS[ext](self, head[ext], mk_act)
                    if action is None:
                        # A marker finishes *between* observes, so the entry-done log
                        # `observe` writes on a head change would never see it. Written
                        # here instead, with the same freshness -- observe ran this tick
                        # before this call did.
                        self.queue.popleft()
                        nxt = self.queue[0][1] if self.queue else None
                        if nxt != idx:
                            self._log_entry_done(idx)
                            self._entry_index = None
                        continue
                else:
                    # `--atoms`: a raw attack hold is the model's own mining step (the
                    # macros that carried the wall watcher are withheld), so the watcher
                    # samples it too. Same marker semantics as a macro: every 8th tick,
                    # one flag per 100 steps, the rest of the plan flushed with the
                    # [NOTE]. Three lives mined
                    # 12,000 steps each on raw holds with 0-3 sightings between them.
                    if self.atoms and _is_attack_hold(head) and self._ore_flag(self._raw_ore):
                        self.cursor_stats["raw_hold_flags"] = (
                            self.cursor_stats.get("raw_hold_flags", 0) + 1)
                    action, _ = self.queue.popleft()
                    action = self._guard_close(action, noop)
                # Advanced here, one tick at a time, against the projection that
                # `_act_turn` advanced entry by entry at planning time. `toggle=False`:
                # for the real cursor `isGuiOpen` decides whether a screen is up, and
                # `_sync_cursor` applies it. See `CursorState.apply`.
                action = self._nether_lock(action)
                self.cursor.apply(action, toggle=False)
                return action
            self._act_turn(info)
        # Two turns in a row produced nothing usable. A no-op costs one tick and the
        # next turn sees the [NOTE].
        self._entry_index = None
        return noop()

    def _grid_line(self) -> str:
        """The [GRID] line: which crafting/furnace slots visibly hold an item.

        Read from the frame at each slot's known screen position (vision.slot_occupied),
        because no observation channel covers container slots. Rows are reported for
        every screen's geometry at once -- the survival 2x2, a table's 3x3 and a
        furnace overlap in container space -- and the prompt tells the agent to read
        the row for the screen it actually opened.
        """
        if not self._gui_open or self._last_pov is None:
            return ""
        frame = np.asarray(self._last_pov)
        ox, oy = gui.container_origin(*self.cursor.render)

        def hit(tl: tuple[float, float]) -> bool:
            return vision.slot_occupied(frame, int(ox + tl[0]), int(oy + tl[1]))

        bits = []
        screen = self._screen
        if screen in (None, "inventory"):
            cells = [str(i) for i, tl in enumerate(gui.SURVIVAL_CRAFT_IN) if hit(tl)]
            out = hit(gui.SURVIVAL_CRAFT_OUT)
            if cells or out:
                bits.append(f"2x2 cells [{','.join(cells) or '-'}]"
                            + (" out=FULL" if out else ""))
        if screen in (None, "table"):
            cells = [str(i) for i, tl in enumerate(gui.TABLE_CRAFT_IN) if hit(tl)]
            out = hit(gui.TABLE_CRAFT_OUT)
            if cells or out:
                bits.append(f"3x3 cells [{','.join(cells) or '-'}]"
                            + (" out=FULL" if out else ""))
        if screen in (None, "furnace"):
            fparts = [name for name, tl in (("in", gui.FURNACE_IN),
                                            ("fuel", gui.FURNACE_FUEL),
                                            ("out", gui.FURNACE_OUT)) if hit(tl)]
            if fparts:
                bits.append(f"furnace [{','.join(fparts)}]")
        # The containers macros_container.py drives. A chest row is only emitted for a
        # chest screen the frame actually named: 27 (or 54) cell readings under an
        # unknown screen would bury the rows above rather than inform them.
        if screen in ("chest", "chest2"):
            cs = gui.chest_cells(screen)
            full = [str(i) for i, tl in enumerate(cs) if hit(tl)]
            bits.append(f"chest cells [{','.join(full) or '-'}] "
                        f"({len(full)} of {len(cs)} hold something)")
        if screen in (None, "brewing"):
            bparts = [n for n, tl in (("fuel", gui.BREW_FUEL),
                                      ("ingredient", gui.BREW_INGREDIENT)) if hit(tl)]
            bparts += [f"bottle{i}" for i, tl in enumerate(gui.BREW_BOTTLES) if hit(tl)]
            if bparts:
                bits.append(f"brewing [{','.join(bparts)}]")
        if screen in (None, "enchanting"):
            eparts = [n for n, tl in (("item", gui.ENCHANT_ITEM),
                                      ("lapis", gui.ENCHANT_LAPIS)) if hit(tl)]
            if eparts:
                bits.append(f"enchanting [{','.join(eparts)}]")
        if screen == "stonecutter":
            sparts = [n for n, tl in (("in", gui.CUT_IN), ("out", gui.CUT_OUT)) if hit(tl)]
            drawn = sum(1 for i in range(gui.CUT_COLS * gui.CUT_ROWS)
                        if hit((gui.CUT_RECIPE_ORIGIN[0] + gui.CUT_BUTTON_W * (i % gui.CUT_COLS),
                                gui.CUT_RECIPE_ORIGIN[1] + gui.CUT_BUTTON_H * (i // gui.CUT_COLS) + 1)))
            bits.append(f"stonecutter [{','.join(sparts) or '-'}], "
                        f"{drawn} recipe button{'s' if drawn != 1 else ''} offered")
        if screen == "anvil":
            aparts = [n for n, tl in (("base", gui.ANVIL_IN), ("material", gui.ANVIL_ADD),
                                      ("result", gui.ANVIL_OUT)) if hit(tl)]
            if aparts:
                bits.append(f"anvil [{','.join(aparts)}]")
        head = (f"[GRID] {screen} screen, occupied: " if screen
                else "[GRID] occupied (read only your open screen's row): ")
        return (head + ("; ".join(bits) if bits else "none") if bits or self._gui_open
                else "")

    def _guard_close(self, action: dict[str, Any], noop) -> dict[str, Any]:
        """Refuse an `inventory` toggle that would drop items on the floor.

        The single most expensive GUI mistake across every run: one run lost four of its
        five logs to two such closes and re-chopped for ~700 steps. The agent was told the
        rule and still hit it, because by the time the close executes the warning is three
        entries old. A rule the harness can check at the moment it matters should be
        enforced there; `close_inventory` with `force=true` is the deliberate override.
        """
        if not action.get("inventory") or not self.cursor.is_open:
            return action
        if not getattr(self, "reflexes", True):
            return action
        if self._close_armed:
            self._close_armed = False
            return action
        held = self.cursor.off_inventory(self._cur_inv)
        if not held:
            return action
        txt = ", ".join(f"{k}x{v}" for k, v in sorted(held.items()))
        if self._screen in macros.KEEPS_CONTENTS:
            # Furnace cells (and any container in macros.KEEPS_CONTENTS) keep their
            # contents: closing is lossless (bar a stack riding the cursor, which the
            # [CURSOR] line warns about). The refusal here cost every smelt a refused
            # close, a forced close and a false "on the floor" note (8-45 refusals
            # per landed z arm).
            self.cursor_stats["furnace_close_ok"] = (
                self.cursor_stats.get("furnace_close_ok", 0) + 1)
            return action
        self.cursor_stats["close_blocked"] += 1
        self.memory.add_note(
            f"close refused: {txt} is off-inventory (in the cursor or a crafting grid) "
            f"and would drop on the floor. stow_items(grid=..., cells=[...]) banks the "
            f"cursor stack and the [GRID]-occupied craft cells into empty slots, then "
            f"close again. A FURNACE keeps its in/fuel/out contents across a close -- "
            f"if the missing items sit in the furnace row, close_inventory with "
            f'force=true is lossless. Otherwise {{"procedure": "close_inventory", '
            f'"args": {{"force": true}}}} drops them deliberately.')
        return noop()

    def _note_failure(self, label: str) -> None:
        """One more consecutive guard-stop for this procedure family."""
        entry = self._proc_fails.setdefault(label, [0, self.step])
        entry[0] += 1

    def _flush_tail(self, note: str, stat: str) -> None:
        """Drop everything queued after the current head, with one note saying so.

        The same move the mining stall-stop makes, for the same reason: the diagnosis
        is only read at the NEXT act turn, and the queue gets there first. The head is
        kept so the dispatch loop's pop after a marker returns None stays valid."""
        head = self.queue[0] if self.queue else None
        dropped = len({idx for _, idx in list(self.queue)[1:]}) if head else 0
        if dropped:
            self.queue.clear()
            self.queue.append(head)
        self.cursor_stats[stat] = self.cursor_stats.get(stat, 0) + 1
        tail = (f" The rest of the plan ({dropped} entr{'y' if dropped == 1 else 'ies'})"
                f" was dropped so you can replan from what you actually see."
                if dropped else "")
        self.memory.add_note(note + tail)

    def _servo_tick(self, sv: dict[str, Any]) -> dict[str, Any] | None:
        """One tick of a closed-loop cursor move; None when the move is finished.

        Arrival is declared against a *measured* position (anchored this very tick), not
        against dead reckoning -- reckoning converges on its own belief by construction,
        which is precisely the failure this replaces. When the arrow has not been drawn
        for several frames running (transition ticks omit it), reckoning is accepted
        rather than deadlocking, and counted separately in the report.
        """
        from mcu_worldmodel.procedures import act as mk_act

        if not self.cursor.is_open:
            self._servo_landed = None
            self._note_failure("gui (screen closed)")
            self._flush_tail(
                f"cursor move to {sv['label']}: the screen closed mid-move; stopped. "
                f"If you did not close it, the game did: container screens auto-close "
                f"when you drift out of reach (~5 blocks). Stand ADJACENT to the block, "
                f"then use_at it again. If the cursor was carrying an "
                f"item, it dropped at your feet -- a follow-up [NOTE] will name "
                f"anything that went missing.", "gui_closed_flush")
            return None
        pos = self.cursor.pos
        ex, ey = sv["tx"] - pos[0], sv["ty"] - pos[1]
        measured = self.cursor.anchored_step == self.step
        if abs(ex) <= 2.0 and abs(ey) <= 2.0 and (measured
                                                  or self._vision_miss_streak >= 4):
            self.cursor_stats["servo_ok" if measured else "servo_unverified"] += 1
            self._servo_landed = (float(sv["tx"]), float(sv["ty"]))
            return None
        if sv["budget"] <= 0:
            self.cursor_stats["servo_gave_up"] += 1
            self._servo_landed = None
            self.memory.add_note(
                f"cursor move to {sv['label']} gave up at container "
                f"({pos[0]:.0f}, {pos[1]:.0f}), {(ex * ex + ey * ey) ** 0.5:.0f}px "
                f"short of its target. The pointer may be pinned at a screen edge.")
            return None
        sv["budget"] -= 1
        # 0.8 gain and a 60 px per-axis clamp. The gain damps the oscillation a wrong
        # scale constant causes (if the game really moves 6.7 px/degree, an undamped step
        # overshoots by 60% and rings); the clamp keeps one bad measurement from flinging
        # the pointer into a screen-edge clamp. Both numbers were set by the simulation
        # described at `procedures.SERVO_BUDGET`.
        step_x = max(-60.0, min(60.0, 0.8 * ex))
        step_y = max(-60.0, min(60.0, 0.8 * ey))
        return mk_act(camera=[step_y / gui.PX_PER_DEGREE, step_x / gui.PX_PER_DEGREE])

    def _click_tick(self, ck: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """A GUI click held against the screen it is about to touch.

        Two facts a human sees before pressing the button, checked the same way: the
        screen is still open, and the pointer is still where the last cursor move left
        it. One run step 5367: the servo landed on the cobble slot, the pointer was
        back at the container's opening position three ticks later, and the click --
        plus the 25 entries queued behind it -- ran anyway and built nothing."""
        if ck["t"] == 0 and ck.get("gui", True):
            if not self.cursor.is_open:
                self._servo_landed = None
                self._note_failure("gui (screen closed)")
                self._flush_tail(
                    f"gui_{'right_' if ck['btn'] == 'use' else ''}click: the screen is "
                    f"closed; not clicking. If you did not close it, the game did: "
                    f"container screens auto-close when you drift out of reach "
                    f"(~5 blocks). Stand ADJACENT to the block, then use_at it "
                    f"again.", "gui_closed_flush")
                return None
            if self._servo_landed is not None and self.cursor.pos is not None:
                px, py = self.cursor.pos
                lx, ly = self._servo_landed
                off = ((px - lx) ** 2 + (py - ly) ** 2) ** 0.5
                if off > 8.0:
                    self._servo_landed = None
                    self._note_failure("gui_click")
                    self._flush_tail(
                        f"click aborted: the cursor is at ({px:.0f}, {py:.0f}), "
                        f"{off:.0f}px away from ({lx:.0f}, {ly:.0f}) where the last "
                        f"cursor move landed -- it moved between the servo and the "
                        f"click. Run cursor_to_slot / cursor_to_cell again (check "
                        f"[CURSOR] over=) before clicking.", "click_pos_mismatch")
                    return None
        if ck["t"] == 0 and ck["btn"] == "attack" and ck.get("gui", True):
            # A left click made with an empty cursor over a player inventory slot is a
            # lift attempt. Remember what the screen shows BEFORE the press -- a
            # put-back click empties the cursor by succeeding, and a snapshot taken at
            # the release tick would read exactly like a lift that did nothing.
            over = self.cursor.over(self._screen)
            held = self.cursor.off_inventory(dict(self._cur_inv))
            # A quick-move (shift) changes which slot holds a stack, not the counts
            # the verdict compares, so it is never judged as "lifted nothing".
            if (not held and "slot" in over and not ck.get("probe")
                    and not ck.get("shift")):
                # Judged hold+3 ticks on: the inventory observation lagged a lift by
                # more than the old hold+1 in a staged scene -- a lifted
                # cobblestone stack was judged "lifted nothing", the queue cleared
                # and the forced close that followed threw the stack on the floor.
                self._pending_click = {"over": over, "inv": dict(self._cur_inv),
                                       "due": ck["hold"] + 3}
        if ck["t"] < ck["hold"]:
            ck["t"] += 1
            # `shift`: sneak held with the button is the GUI's quick-move (shift-click)
            # -- measured in the standalone sim: a stack jumps between
            # the hotbar and the main rows, a chest slot empties into the inventory,
            # a craft output crafts everything the grid holds and banks it. No stack
            # ever rides the cursor, so no bank click can miss.
            return mk_act(**{ck["btn"]: 1, **({"sneak": 1} if ck.get("shift") else {})})
        if ck["t"] == ck["hold"]:
            ck["t"] += 1
            return mk_act()
        return None

    def _judge_pending_click(self) -> None:
        """The lift attempt's verdict, one tick after the click finishes, from the same
        two channels the prompt teaches the model to check by hand ([CURSOR] holdings
        and [INV])."""
        pc = self._pending_click
        if pc is None:
            return
        pc["due"] -= 1
        if pc["due"] > 0:
            return
        self._pending_click = None
        if not self.cursor.is_open:
            return
        held = self.cursor.off_inventory(dict(self._cur_inv))
        if held or dict(self._cur_inv) != pc["inv"]:
            return
        # The frame is the direct evidence: a lifted stack vanishes from its slot on
        # the client at once, while the inventory observation can lag a lift by 5+
        # ticks (a staged scene: a 3-cobblestone lift right after a quick-move
        # craft was judged "lifted nothing" while the stack was already on the
        # cursor and being placed into the grid). A slot that renders EMPTY under
        # the pointer means the lift happened, whatever the counts say.
        m = re.search(r"slot (\d+)", str(pc.get("over", "")))
        if m and self._last_pov is not None:
            try:
                # A double chest draws the player rows 27 px lower: read the slot where
                # THIS screen draws it (gui.player_slot_topleft knows the shift).
                tl = gui.player_slot_topleft(int(m.group(1)), self._screen)
                ox, oy = gui.container_origin(*self.cursor.render)
                if not vision.slot_occupied(np.asarray(self._last_pov),
                                            int(ox + tl[0]), int(oy + tl[1])):
                    return
            except ValueError:
                pass
        dropped = len({idx for _, idx in self.queue})
        if dropped:
            self.queue.clear()
            self._entry_index = None
        self._note_failure("gui_click")
        self.cursor_stats["click_lifted_nothing"] = (
            self.cursor_stats.get("click_lifted_nothing", 0) + 1)
        self.memory.add_note(
            f"the gui_click over {pc['over']} lifted nothing: the cursor holds nothing "
            f"and the inventory did not change. The slot may be empty or the pointer "
            f"not on the stack -- land cursor_to_slot on it again before clicking."
            + (f" The rest of the plan ({dropped} entr{'y' if dropped == 1 else 'ies'})"
               f" was dropped so you can replan from what you actually see."
               if dropped else ""))

    def _chop_tick(self, ch: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of attack, ending early the moment wood actually breaks.

        Keyed on the `mine_block` statistic, not the inventory: the block breaking is the
        instant the aim is proven (the drop can take seconds to be walked over, or fall
        out of reach entirely), and one run ran a whole episode with zero early stops
        because it waited on the pickup. The inventory count is kept as a second trigger
        for the case where a drop from an earlier miss rolls in mid-chop.
        """
        if ch.get("base") is None:
            ch["base"] = {k: v for k, v in self._cur_inv.items() if "log" in k}
            ch["base_breaks"] = self._log_breaks
            ch["base_other"] = self._other_breaks
            ch["used"] = 0
        broken = self._log_breaks - ch["base_breaks"]
        if ch["until"]:
            gained = sum(v - ch["base"].get(k, 0)
                         for k, v in self._cur_inv.items()
                         if "log" in k and v > ch["base"].get(k, 0))
            if max(broken, gained) >= ch["until"]:
                self.cursor_stats["chop_early_stops"] += 1
                return None
        # Miss-fast: the stat stream names what is actually breaking. Two non-wood
        # breaks with no wood yet means the crosshair is on leaves/dirt; 75 ticks with
        # nothing breaking at all means out of range or aimed at sky. Ending the macro
        # there turns a 180-tick miss into a <=75-tick answer.
        if broken == 0:
            wrong = self._other_breaks - ch["base_other"]
            if wrong >= 2:
                self.cursor_stats["chop_wrong_target"] = (
                    self.cursor_stats.get("chop_wrong_target", 0) + 1)
                self.memory.add_note(
                    f"chop stopped early: breaking {self._last_break_item}, not wood. "
                    f"Re-aim at a trunk face (zoom the frame centre to check).")
                return None
            if ch["used"] >= 75:
                self.cursor_stats["chop_nothing_broke"] = (
                    self.cursor_stats.get("chop_nothing_broke", 0) + 1)
                self.memory.add_note(
                    "chop stopped early: 75 ticks and nothing broke -- the block is out "
                    "of reach or the crosshair is on sky. Get within ~3 blocks of the "
                    "trunk and centre a bark face before chopping again.")
                return None
        if ch["remaining"] <= 0:
            return None
        ch["remaining"] -= 1
        ch["used"] += 1
        return mk_act(attack=1)

    def _opengui_tick(self, og: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Press `inventory` until a screen is actually up (isGuiOpen), a few tries.

        The toggle is edge-triggered and the engine drops a press that lands within a
        tick or two of the previous screen change: a staged scene pressed E four
        ticks after a forced close and nothing opened, so the whole recipe queued
        behind it ran against a closed screen. The same check `use_until_gui` makes,
        for the one key that opens the survival inventory."""
        if self._gui_open:
            return None
        t = og["t"]
        og["t"] += 1
        if t % 3 == 0:
            if og["attempts"] <= 0:
                self.memory.add_note(
                    "open_inventory: the screen did not open after "
                    f"{og.get('tries', 0)} presses; try again next turn.")
                return None
            og["attempts"] -= 1
            og["tries"] = og.get("tries", 0) + 1
            return mk_act(inventory=1)
        return mk_act()

    def _closegui_tick(self, cg: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Press `inventory` until no screen is open, through the drop guard each time.

        A close is verified on `isGuiOpen`, not assumed from the press: right after a
        `use`-opened container the first E is swallowed (every container in the
        probe needed two), and a plan that believed the screen shut then
        walked away with a stack still on the cursor. `force` arms the guard for every
        press of this close, so a swallowed first press does not turn the second into
        a refusal.

        One observation without a screen is not a close either: an E sent the tick
        after `place_and_open` brought the table up read closed for one observation
        and the table was on screen again in the next. The close is done when two
        observations running show no screen; a screen that is back is pressed again."""
        if not self._gui_open:
            if not cg.get("tries") or cg.get("shut"):
                return None
            cg["shut"] = True
            return mk_act()
        if cg.pop("shut", False):
            cg["t"] = 0
        t = cg["t"]
        cg["t"] += 1
        if t % 3 == 0:
            if cg["attempts"] <= 0:
                self.memory.add_note(
                    f"close_inventory: the screen is still open after "
                    f"{cg.get('tries', 0)} presses; call it again.")
                return None
            cg["attempts"] -= 1
            cg["tries"] = cg.get("tries", 0) + 1
            if cg.get("force"):
                self._close_armed = True
            action = self._guard_close(mk_act(inventory=1), mk_act)
            if not action.get("inventory"):
                return None         # refused: the guard wrote its note
            return action
        return mk_act()

    def _use_gui_tick(self, ug: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Press use, give the screen two ticks to come up, check, repeat.

        `isGuiOpen` is the arbiter -- the press either opened a screen or it did not,
        and one run spent fifteen model-turn round trips discovering "did not" one
        plan at a time. Stops the moment the screen is up.
        """
        if self._gui_open:
            # One settle tick with the screen up: a click or an E sent on the very
            # tick the screen appeared was swallowed in the probes.
            if not ug.get("settled"):
                ug["settled"] = True
                return mk_act()
            self.cursor_stats["use_gui_opened"] = (
                self.cursor_stats.get("use_gui_opened", 0) + 1)
            opened_item = self._screen_item_for(ug)
            if opened_item:
                self.grid.mark_opened(self.step, opened_item, self._cur_pos)
                if ug.get("replay"):
                    self.cursor_stats["pose_reopens"] = (
                        self.cursor_stats.get("pose_reopens", 0) + 1)
            if ug.get("grace"):
                self.cursor_stats["use_gui_late_open"] = (
                    self.cursor_stats.get("use_gui_late_open", 0) + 1)
            return None
        item = ug.get("item")
        if item and not ug.get("aimed") and not ug.get("pose_done"):
            # First choice: replay the exact pose this screen last opened from
            # (grid.opened). The cell estimate below is the fallback.
            replay = self.grid.opened.get(str(item))
            if replay and replay.get("pose") and self._cur_pos:
                if ug.get("attempts0") is None:
                    ug["attempts0"] = ug["attempts"]
                act = self._pose_replay_tick(ug, replay["pose"], mk_act)
                if act is not None:
                    return act
                st = ug.get("replay") or {}
                if st.get("phase") == "done":
                    ug["aimed"] = True
                    ug["pose_done"] = "pressing"
                    return mk_act()
                ug["pose_done"] = "unreachable"
        if item and not ug.get("aimed"):
            # Aim at the block place_and_open put down (its estimate, see
            # _placecheck_tick) before the first press: two runs
            # pressed `use` at guessed angles 18 times between them and
            # opened nothing -- the runner knew where the table went, the model did not.
            at = self._placed.get(str(item))
            if at is None:
                self.memory.add_note(
                    f"use_until_gui(item={item!r}): this run has not placed a {item} "
                    f"with place_and_open, so there is no remembered spot -- look_at "
                    f"its coordinates yourself, then use_until_gui.")
                ug["aimed"] = True
            elif ug.get("aim") is None:
                from mcu_worldmodel.procedures import look_at
                from mcu_worldmodel.macros_world import EYE, REACH
                pos = self._cur_pos or {}
                dist = (math.dist((pos["x"], pos["y"] + EYE, pos["z"]),
                                  (at[0] + 0.5, at[1] + 0.5, at[2] + 0.5))
                        if pos else 0.0)
                if dist > REACH + 0.3:
                    # One run called use_until_gui(item="crafting_table")
                    # from 5, 16 and 18 blocks away: the camera turned toward the
                    # remembered table and eight presses opened nothing, seven times
                    # over. Out of reach is a walk, not a press.
                    self.cursor_stats["use_gui_far"] = (
                        self.cursor_stats.get("use_gui_far", 0) + 1)
                    self.memory.add_note(
                        f"use_until_gui(item={item!r}): the {item} this run placed is at "
                        f"({at[0]}, {at[1]}, {at[2]}), {dist:.1f} blocks from your eye -- "
                        f"out of reach (max {REACH}). go_to({at[0]}, {at[2]}, within=2) "
                        f"first, then use_until_gui(item={item!r}) again.")
                    return None
                aim, _ = look_at(self._cur_info or {}, at[0] + 0.5, at[1] + 0.5, at[2] + 0.5)
                ug["aim"] = [a for a in aim if a.get("camera")]
                ug["aim_note"] = at
            if ug.get("aim"):
                return ug["aim"].pop(0)
            if not ug.get("aimed"):
                ug["aimed"] = True
                self.cursor_stats["use_gui_aimed"] = self.cursor_stats.get("use_gui_aimed", 0) + 1
                return mk_act()          # one settle tick after the turn
        if ug["attempts"] <= 0:
            # The presses are spent: wait out the observation lag before the verdict
            # (GUI_LAG_TICKS); a screen that comes up meanwhile is a success above.
            ug["grace"] = ug.get("grace", 0) + 1
            if ug["grace"] <= self.GUI_LAG_TICKS:
                return mk_act()
            if ug.get("pose_done") == "pressing" and not ug.get("cell_tried"):
                # The replayed pose opened nothing (the block is gone, or the spot
                # was not reached exactly): one more round at the estimated cell.
                ug["cell_tried"] = True
                ug["pose_done"] = "failed"
                ug["aimed"] = False
                ug["attempts"] = int(ug.get("attempts0") or 4)
                ug["grace"] = 0
                return mk_act()
            at = ug.get("aim_note")
            self._keep_event_frame(self.step, "no screen", self._last_pov)
            self.memory.add_note(
                (f"use_until_gui(item={ug['item']!r}): aimed at the remembered {ug['item']} "
                 f"at ({at[0]}, {at[1]}, {at[2]}) and no screen opened -- the block may be "
                 f"gone (broken, or a death ago), or something stands between you and it; "
                 f"check the newest frame, and the selected hotbar item must not be a "
                 f"placeable block."
                 if at else
                 "use_until_gui: no screen opened. Either the crosshair is not on the "
                 "block (look_at it first) or the selected hotbar item is placeable and "
                 "placed a block instead -- select your pickaxe and retry."))
            return None
        t = ug["t"]
        ug["t"] += 1
        if t % 3 == 0:
            ug["attempts"] -= 1
            return mk_act(use=1)
        return mk_act()

    def _cut_attack_hold(self) -> None:
        """Refund the rest of a raw attack-hold entry once a block has broken.

        Only pure holds are cut -- attack with no movement, no use, no camera -- only
        while that entry is the one running, and only when at least 10 such ticks
        remain, so strip_mine's short bursts and attack-while-walking steps are
        untouched. The [NOTE] teaches the semantics back to the agent.
        """
        if not self.queue:
            return
        head, idx = self.queue[0]
        if idx != self._entry_index:
            return          # the break belongs to the entry that just finished

        _is_hold = _is_attack_hold
        if not _is_hold(head):
            return
        run = 0
        for a, i in self.queue:
            if i != idx or not _is_hold(a):
                break
            run += 1
        if run < 10:
            return
        for _ in range(run):
            self.queue.popleft()
        self.cursor_stats["attack_holds_cut"] = (
            self.cursor_stats.get("attack_holds_cut", 0) + 1)
        self.memory.add_note(
            f"attack-hold entry cut short at step {self.step}: a block broke "
            f"({self._last_break_item or 'log'}), {run} leftover attack ticks refunded. "
            + _cut_short_hint(self.atoms))

    #: Blocks the pillar reflex will stand on, best first. Gravel and sand fall.
    PILLAR_BLOCKS = ("cobblestone", "dirt", "stone", "andesite", "diorite", "granite",
                     "netherrack", "cobbled_deepslate", "oak_planks", "spruce_planks",
                     "birch_planks", "jungle_planks", "acacia_planks", "dark_oak_planks")

    def _pillar_slot(self, info: dict, min_qty: int = 2) -> tuple[int, str] | None:
        """(hotbar number 1-9, item) of the best-stocked placeable block in the HOTBAR.
        Main-inventory stacks would need the GUI, which a mob does not wait for. The
        pillar needs two blocks; the bunker's cap needs one (`min_qty`)."""
        best = None
        for item in self.PILLAR_BLOCKS:
            for slot, qty in gui.find_slots(info, item):
                if slot <= 8 and qty >= min_qty and (best is None or qty > best[2]):
                    best = (slot + 1, item, qty)
        return (best[0], best[1]) if best else None

    def _pillar_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of the pillar reflex: equip the block, look straight down, then
        jump-and-place until `target` blocks are under the feet (y measured, not
        assumed). Two failed attempts end it -- the model is told either way."""
        pos = self._cur_pos
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._finish_pillar(rf, "ran out of ticks")
            return None
        if rf["phase"] == "equip":
            rf["phase"] = "look"
            return mk_act(**{f"hotbar_{rf['slot']}": 1})
        if rf["phase"] == "look":
            dp = 90.0 - float(pos["pitch"])
            if dp > 3.0:
                return mk_act(camera=[min(30.0, dp), 0.0])
            rf["phase"] = "jump"
            rf["t"] = 0
            rf["y_jump"] = float(pos["y"])
        t = rf["t"]
        rf["t"] += 1
        if t < 10:
            return mk_act(jump=1, use=1 if t >= 3 else 0)
        if t < 16:
            return mk_act()
        if float(pos["y"]) >= rf["y_jump"] + 0.9:
            rf["placed"] += 1
            rf["tries"] = 0
        else:
            rf["tries"] += 1
        if rf["placed"] >= rf["target"]:
            self._finish_pillar(rf, None)
            return None
        if rf["tries"] >= 2:
            self._finish_pillar(rf, "the block did not place")
            return None
        rf["t"] = 0
        rf["y_jump"] = float(pos["y"])
        return mk_act()

    def _finish_pillar(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        y = f"{float(pos['y']):.0f}" if pos else "?"
        self.cursor_stats["pillar_blocks"] = (
            self.cursor_stats.get("pillar_blocks", 0) + int(rf.get("placed", 0)))
        if why is None or rf.get("placed", 0) >= 1:
            self.memory.add_note(
                f"the runner pillared you up {rf.get('placed', 0)} block(s) on "
                f"{rf.get('item')} to y {y}"
                + (f" ({why})" if why else "")
                + ": a melee mob cannot reach you here. Look down and attack it, or "
                "wall yourself off, before going back to the plan.")
        else:
            self.memory.add_note(
                f"the runner tried to pillar you up on {rf.get('item')} but {why} "
                f"(still at y {y}): get away from the attacker on foot NOW.")
        self._reflex = None

    def _bunker_plan(self, info: dict) -> tuple[int, str, int, str] | None:
        """(pickaxe hotbar number, pickaxe, block hotbar number, block) for the bunker
        reflex, or None when either is missing from the HOTBAR (a mob does not wait
        for the inventory screen). The floor of a mine is stone: no pickaxe, no hole."""
        pick = None
        for item in self.PICKAXES:
            for slot, _qty in gui.find_slots(info, item):
                if slot <= 8:
                    pick = (slot + 1, item)
                    break
            if pick:
                break
        block = self._pillar_slot(info, min_qty=1)
        if pick is None or block is None:
            return None
        return (pick[0], pick[1], block[0], block[1])

    def _arm_bunker(self, plan: tuple[int, str, int, str], pos: dict) -> dict[str, Any]:
        """The reflex state: the cell the avatar stands in is the cap cell (its floor
        becomes the two-block hole below it), and the cap is placed against a side
        wall of that cell -- a strip mine's walls run along the avatar's heading, so
        the faces across the heading come first."""
        from mcu_worldmodel import macros_world as MW
        cell = MW.block_of(pos)
        along_x = MW.axis_facing(float(pos["yaw"]))[0] != 0
        faces = (["north", "south", "west", "east"] if along_x
                 else ["west", "east", "north", "south"])
        self.cursor_stats["bunker_reflexes"] = self.cursor_stats.get("bunker_reflexes", 0) + 1
        return {"kind": "bunker", "pick": plan[0], "pick_item": plan[1], "slot": plan[2],
                "item": plan[3], "phase": "equip_pick", "t": 0, "remaining": 170,
                "cell": [int(v) for v in cell], "y0": float(pos["y"]),
                "last_y": float(pos["y"]), "stable": 0, "faces": faces, "cap": None,
                "dealt0": self.stat_now("custom", "damage_dealt")}

    def _bunker_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of the bunker reflex: equip the pickaxe, look straight down, hold
        attack until the measured y is two blocks lower and steady, equip the block,
        then place it in the cell the feet started in (the placement engine aims at a
        side wall's face and verifies through use_item). Every exit tells the model
        what state it is in."""
        from mcu_worldmodel import macros_world as MW
        pos = self._cur_pos
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._finish_bunker(rf, "ran out of ticks")
            return None
        if self._gui_open:
            self._finish_bunker(rf, "a screen is open")
            return None
        y = float(pos["y"])
        by = rf["cell"][1]
        ph = rf["phase"]
        if ph == "requip":
            self._finish_bunker(rf, None)
            return None
        if ph == "equip_pick":
            rf["phase"] = "look"
            return mk_act(**{f"hotbar_{rf['pick']}": 1})
        if ph == "look":
            dp = 90.0 - float(pos["pitch"])
            if dp > 3.0:
                return mk_act(camera=[min(30.0, dp), 0.0])
            rf["phase"], rf["t"], ph = "dig", 0, "dig"
        if ph == "dig":
            rf["t"] += 1
            if y < by - 3.5:
                self._finish_bunker(rf, "the floor opened into a cavity below")
                return None
            if self.stat_now("custom", "damage_dealt") > rf.get("dealt0", 0.0):
                # The pickaxe swung straight down and hit the MOB: it is in the cell
                # (fallen down the shaft), the crosshair is on it and the floor never
                # breaks under a held attack (one run "the floor did not break", a staged scene
                # "bunker_blocks 0/1"). Nothing to dig into: fight it now, aiming at
                # the cell's centre, with whatever the hotbar holds.
                weapon = self._weapon_slot(self._cur_info or {})
                shaft = self._in_shaft(rf["cell"])
                self._finish_bunker(rf, "the swings hit the mob, not the floor -- it is "
                                        "in the cell with you")
                self.cursor_stats["bunker_intercepted"] = (
                    self.cursor_stats.get("bunker_intercepted", 0) + 1)
                if weapon is None:
                    return None
                hp = self._last_health if self._last_health is not None else 0.0
                fb = self._arm_fightback(pos, hp, float(pos["yaw"]), weapon,
                                         desperate=shaft, toward_center=True)
                self.memory.add_note(
                    f"the runner is FIGHTING BACK with the {weapon[1]} (hotbar "
                    f"{weapon[0]}) instead, aimed at the middle of your cell (the mob is "
                    f"pushed to the far side of it), for up to {self.FIGHTBACK_TICKS} "
                    f"ticks" + (" -- to the end, there is nowhere to run at the bottom "
                                "of your own shaft" if shaft else
                                f"; below {self.CRITICAL_HP:.0f} hp the run takes over")
                    + "; your next turn comes from where the fight ends.")
                self._reflex = fb
                return self._fightback_tick(fb, mk_act)
            if y <= by - 2 + 0.05:
                rf["stable"] = rf["stable"] + 1 if abs(y - rf["last_y"]) < 0.01 else 0
                rf["last_y"] = y
                if rf["stable"] >= 2:
                    rf["phase"] = "equip_block"
                    return mk_act(**{f"hotbar_{rf['slot']}": 1})
                return mk_act()
            rf["last_y"] = y
            if rf["t"] >= 70 and y > by - 0.9:
                self._finish_bunker(rf, "the floor did not break")
                return None
            # A hit's knockback pushes the avatar off the cell, the swing lands on the
            # next floor block and the breaking progress resets: a zombie at the rim
            # kept the hole at zero blocks for 79 ticks (a staged scene). Walk back over the
            # cell while swinging; once a block down the walls hold the avatar.
            keys: dict[str, int] = {}
            dx = rf["cell"][0] + 0.5 - float(pos["x"])
            dz = rf["cell"][2] + 0.5 - float(pos["z"])
            if y > by - 0.9 and math.hypot(dx, dz) > 0.25:
                r = math.radians(float(pos["yaw"]))
                fwd = -dx * math.sin(r) + dz * math.cos(r)      # forward = (-sin, cos)
                rgt = -dx * math.cos(r) - dz * math.sin(r)      # right = (-cos, -sin)
                if fwd > 0.1:
                    keys["forward"] = 1
                elif fwd < -0.1:
                    keys["back"] = 1
                if rgt > 0.1:
                    keys["right"] = 1
                elif rgt < -0.1:
                    keys["left"] = 1
                rf["recentred"] = rf.get("recentred", 0) + 1
                self.cursor_stats["bunker_recentred"] = (
                    self.cursor_stats.get("bunker_recentred", 0) + 1)
            return mk_act(attack=1, **keys)
        if ph == "equip_block":
            rf["cap"] = MW.new_use_state(tuple(rf["cell"]), rf["item"], rf["faces"][0],
                                         "place", 1, "bunker cap", faces=list(rf["faces"]))
            rf["phase"] = "cap"
        status, action = MW.use_step(self, rf["cap"], mk_act)
        if status == "run":
            return action
        if status == "done":
            # The pickaxe back in hand: the dig-out the note recommends is a 20-tick
            # job with it and a 200-tick one with the block still selected (s8).
            rf["phase"] = "requip"
            return mk_act(**{f"hotbar_{rf['pick']}": 1})
        self._finish_bunker(rf, rf["cap"].get("note") or "the cap did not place")
        return None

    def _finish_bunker(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        y = f"{float(pos['y']):.0f}" if pos else "?"
        bx, by, bz = rf["cell"]
        dug = int(round(rf["y0"] - float(pos["y"]))) if pos else 0
        self.cursor_stats["bunker_blocks"] = self.cursor_stats.get("bunker_blocks", 0) + dug
        if why is None:
            self.cursor_stats["bunker_capped"] = self.cursor_stats.get("bunker_capped", 0) + 1
            self._last_bunker = {"step": int(self.step), "cell": tuple(int(v) for v in rf["cell"])}
            note = (f"the runner BUNKERED you: dug {dug} blocks down to y {y} and capped "
                    f"the hole with {rf['item']} at ({bx}, {by}, {bz}) -- nothing can reach "
                    f"you in here, and the {rf['pick_item']} is back in your hand. Let "
                    f"health come back (eat if the food bar is low), then dig out: "
                    f"look_abs(pitch=-90) + mine_ahead(n=60) breaks the cap, and "
                    f"pillar_up(2) climbs back to the tunnel floor at y {by}.")
        elif dug >= 2:
            note = (f"the runner dug you {dug} blocks down to y {y} but the cap did not "
                    f"place ({why}): you are in an open 1x1 hole below the tunnel floor -- "
                    f"place_at({bx}, {by}, {bz}, item=\"{rf['item']}\", face=...) seals it "
                    f"from here (name a side that is solid wall), or climb out and run.")
        else:
            note = (f"the runner tried to bunker you (dig two down, cap the hole) but {why} "
                    f"(still at y {y}): get away from the attacker on foot NOW.")
        self.memory.add_note(note)
        self._reflex = None

    def _water_slot(self, info: dict) -> int | None:
        """Hotbar number (1-9) of a water bucket, or None (a main-inventory one would need
        the GUI, which lava does not wait for)."""
        for slot, qty in gui.find_slots(info, "water_bucket"):
            if slot <= 8 and qty >= 1:
                return slot + 1
        return None

    def _arm_lava(self, info: dict, pos: dict, hp: float, frac: float) -> dict[str, Any]:
        self.cursor_stats["lava_reflexes"] = self.cursor_stats.get("lava_reflexes", 0) + 1
        # water evaporates in the Nether (public 1.16 mechanics): only the step back there
        wb = None if self._dimension == "the Nether" else self._water_slot(info)
        return {"kind": "lava", "phase": "equip" if wb else "out", "wb": wb, "t": 0,
                "remaining": 90, "x0": float(pos["x"]), "z0": float(pos["z"]),
                "y0": float(pos["y"]), "hp0": float(hp), "frac": float(frac),
                "base_use": self.stat_now("use_item", "water_bucket"),
                "base_bucket": int(self._cur_inv.get("bucket", 0)),
                "home": self._lava_home(pos)}

    def _lava_home(self, pos: dict) -> tuple[float, float] | None:
        """(x, z) of the centre of the cell the avatar walked most recently that is a
        block or more from here, not below it, and where it was never hurt: the dry
        ground it came from. A plain `back` step retreats INTO the pool once the avatar
        has turned (one run: the 180-degree turn at the first hit, then the
        runner's back-step; one run fell in facing the rim it had come from)."""
        c = self._lava_home_cell(pos)
        return (c[0] + 0.5, c[2] + 0.5) if c else None

    def _lava_home_cell(self, pos: dict) -> tuple[int, int, int] | None:
        hx, hz, hy = float(pos["x"]), float(pos["z"]), float(pos["y"])
        best = None
        for c, rec in self.grid.walked.items():
            if c in self.grid.hazard or c in self.grid.lava or c[1] < hy - 1.0:
                continue
            d = math.hypot(c[0] + 0.5 - hx, c[2] + 0.5 - hz)
            if d < 1.0 or d > 8.0:
                continue
            last = int(rec.get("last", 0))
            if best is None or last > best[0] or (last == best[0] and d < best[1]):
                best = (last, d, c)
        return tuple(best[2]) if best else None

    def _lava_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of the lava escape: select the water bucket, look straight down,
        pour it (one use), let the water spread for three ticks, walk BACKWARD with a
        jump for LAVA_OUT_TICKS (the lava the avatar met is in front of it), then level
        the view for the model's next frame."""
        pos = self._cur_pos
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._finish_lava(rf, "ran out of ticks")
            return None
        if self._gui_open:
            self._finish_lava(rf, "a screen is open")
            return None
        ph = rf["phase"]
        if ph == "equip":
            rf["phase"] = "look"
            return mk_act(**{f"hotbar_{rf['wb']}": 1})
        if ph == "look":
            dp = 90.0 - float(pos["pitch"])
            if dp > 3.0:
                return mk_act(camera=[min(30.0, dp), 0.0])
            rf["phase"] = "pour"
            return mk_act(use=1)
        if ph == "pour":
            rf["t"] += 1
            if rf["t"] < 3:
                return mk_act()
            rf["phase"], rf["t"], ph = "out", 0, "out"
        if ph == "out":
            rf["t"] += 1
            moved = math.hypot(float(pos["x"]) - rf["x0"], float(pos["z"]) - rf["z0"])
            # in lava the avatar crawls: keep going until it is a block away, up to
            # LAVA_OUT_MAX ticks (a staged scene: 14 ticks moved it 0.2 blocks; in another
            # it climbed out of the sunk cell in 14 ticks but stood on its
            # lip, half a block along -- a rise alone is not out)
            out = rf["t"] > self.LAVA_OUT_TICKS and moved >= 1.0
            home = rf.get("home")
            if home is not None and math.hypot(home[0] - float(pos["x"]),
                                               home[1] - float(pos["z"])) < 0.5:
                out = True                                  # back on the trail
            if not out and rf["t"] <= self.LAVA_OUT_MAX:
                if home is None:
                    return mk_act(back=1, jump=1)
                # Toward the ground it came from, the view levelled on the way, the
                # jump held (a swim up out of the pool, a hop onto its rim).
                dx, dz = home[0] - float(pos["x"]), home[1] - float(pos["z"])
                want = norm_yaw(math.degrees(math.atan2(-dx, dz)))
                dy = norm_yaw_delta(want, float(pos["yaw"]))
                dp = -float(pos["pitch"])
                cam = [max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))]
                if abs(dy) > 25.0:
                    return mk_act(camera=cam, jump=1)
                return mk_act(camera=cam, forward=1, sprint=1, jump=1)
            rf["phase"], rf["t"], ph = "level", 0, "level"
        if ph == "level":
            dp = 10.0 - float(pos["pitch"])
            rf["t"] += 1
            if abs(dp) > 4.0 and rf["t"] <= 4:
                return mk_act(camera=[max(-30.0, min(30.0, dp)), 0.0])
            self._finish_lava(rf, None)
            return None
        self._finish_lava(rf, "unknown phase")
        return None

    def _arm_drown(self, pos: dict, hp: float, water: float) -> dict[str, Any]:
        self.cursor_stats["drown_reflexes"] = self.cursor_stats.get("drown_reflexes", 0) + 1
        return {"kind": "drown", "t": 0, "remaining": self.DROWN_MAX + 2,
                "y0": float(pos["y"]), "hp0": float(hp), "water": float(water),
                "ys": [float(pos["y"])]}

    def _drown_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Hold jump: in water that is a swim up, and at the surface it keeps the head
        out. DROWN_TICKS at least, DROWN_MAX at most, done once 12 ticks gained under
        0.3 blocks (the surface, or dry land: a jump arc there repeats every ~12 ticks,
        so consecutive still ticks never happen -- audit pass 18; a swim from a deep
        flood keeps going, a fixed 0.8 blocks ended it short -- audit pass 17)."""
        pos = self._cur_pos
        rf["remaining"] -= 1
        rf["t"] += 1
        if pos is None or rf["remaining"] < 0:
            self._finish_drown(rf, "ran out of ticks")
            return None
        if self._gui_open:
            self._finish_drown(rf, "a screen is open")
            return None
        ys = rf.setdefault("ys", [])
        ys.append(float(pos["y"]))
        gained = ys[-1] - ys[-13] if len(ys) >= 13 else 1.0
        if rf["t"] > self.DROWN_TICKS and (gained < 0.3 or rf["t"] > self.DROWN_MAX):
            self._finish_drown(rf, None)
            return None
        return mk_act(jump=1)

    def _finish_drown(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        risen = (float(pos["y"]) - rf["y0"]) if pos else 0.0
        where = (f"({pos['x']:.0f}, {pos['y']:.1f}, {pos['z']:.0f})" if pos else "?")
        self.cursor_stats["drown_risen"] = (
            self.cursor_stats.get("drown_risen", 0) + int(max(0.0, risen)))
        self.memory.add_note(
            f"the runner swam you UP {risen:.1f} block(s) to {where} with jump held for "
            f"{rf['t']} ticks" + (f" ({why})" if why else "")
            + ". A gradual loss with water around you is DROWNING: water fills a shaft dug "
              "beside a pond or a stream. pillar_up places nothing while you swim; get onto "
              "a bank (walk at the wall with jump held -- it climbs one block), and start "
              "the next shaft 6+ blocks from any water. If the loss goes on with dry ground "
              "under you it is starvation (eat) or a mob behind you.")
        self._reflex = None

    def _water_guard(self, step: int, pos: dict | None) -> None:
        """Every 4 ticks: remember where the frame last showed water within reach (the
        lower-centre window a third full, or a quarter of the view), for the dig refusal."""
        if not getattr(self, "reflexes", True):
            return
        if step % 4 or self._gui_open or self._last_pov is None or pos is None:
            return
        arr = np.asarray(self._last_pov)
        if (vision.water_near(arr) >= vision.WATER_NEAR
                or vision.water_view(arr, rows_from=0.30)[0] >= self.DROWN_WATER_FRAC):
            self._last_water_seen = (step, float(pos["x"]), float(pos["z"]))
            self.grid.mark_water(step, float(pos["x"]), float(pos["z"]), float(pos["y"]))

    def _dig_water_refusal(self, label: str) -> str | None:
        """The note refusing a shaft beside water seen lately, or None."""
        seen = self._last_water_seen
        pos = self._cur_pos
        if seen is None or pos is None or self.step - seen[0] > self.DIG_WATER_STEPS:
            return None
        d = math.hypot(float(pos["x"]) - seen[1], float(pos["z"]) - seen[2])
        if d > self.DIG_WATER_BLOCKS:
            return None
        # The way out, as one call: one run spent steps 579-4113 beside the
        # pond it had filled the bucket at, refused here twice and swimming in circles.
        from mcu_worldmodel import macros_world as MW
        if d >= 0.5:
            ux, uz = (float(pos["x"]) - seen[1]) / d, (float(pos["z"]) - seen[2]) / d
        else:
            ux, uz = MW.facing(float(pos.get("yaw", 0.0)) + 180.0)
        away = self.DIG_WATER_BLOCKS + 2.0
        gx, gz = seen[1] + ux * away, seen[2] + uz * away
        return (f"{label} REFUSED: water was within reach {self.step - seen[0]} ticks ago, "
                f"{d:.0f} block(s) from here -- a shaft dug beside a pond or a stream FLOODS "
                f"(a flooded shaft has drowned the runner before). Walk "
                f"{self.DIG_WATER_BLOCKS:.0f}+ blocks away from the water's edge, look down "
                f"at dry ground, then dig: `go_to(x={gx:.1f}, z={gz:.1f}, within=1, "
                f"n=120)` is that far from it, straight away from the water.")

    def _finish_lava(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        moved = (math.hypot(float(pos["x"]) - rf["x0"], float(pos["z"]) - rf["z0"])
                 if pos else 0.0)
        poured = (rf["wb"] is not None
                  and (self.stat_now("use_item", "water_bucket") - rf["base_use"] >= 1
                       or int(self._cur_inv.get("bucket", 0)) > rf["base_bucket"]))
        if poured:
            self.cursor_stats["lava_doused"] = self.cursor_stats.get("lava_doused", 0) + 1
        self.cursor_stats["lava_escape_blocks"] = (
            self.cursor_stats.get("lava_escape_blocks", 0) + int(moved))
        hp = self._last_health
        where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos else "?")
        self.memory.add_note(
            "the runner "
            + ("DOUSED you (water bucket poured at your feet: the fire is out and the lava "
               "you touched is obsidian/cobblestone now; the empty bucket is back -- refill "
               "it with fill_bucket at the water you left, or pick it up with use_at) and "
               if poured else
               ("tried to pour the water bucket but nothing registered, then " if rf["wb"]
                else ("did not use a bucket (water evaporates in the Nether), so it only "
                      if self._dimension == "the Nether" else
                      "had no water bucket in your hotbar, so it only ")))
            + (f"walked you {moved:.1f} block(s) back toward the ground you came from, "
               f"({rf['home'][0]:.1f}, {rf['home'][1]:.1f}), now at {where}"
               if rf.get("home") is not None else
               f"stepped you back {moved:.1f} block(s) to {where}")
            + (f" ({why})" if why else "")
            + (f"; health {hp:.0f}/20." if hp is not None else ".")
            + " If you are still burning, get to water or wait it out on solid ground; "
              "do not walk back toward the orange light. Make obsidian from the pool's rim "
              "with make_obsidian(x, y, z), never from inside it.")
        self._reflex = None

    def _sword_slot(self, info: dict) -> tuple[int, str] | None:
        """(hotbar number 1-9, item) of the best sword in the HOTBAR, or None."""
        for item in self.SWORDS:
            for slot, qty in gui.find_slots(info, item):
                if slot <= 8 and qty >= 1:
                    return (slot + 1, item)
        return None

    def _weapon_slot(self, info: dict) -> tuple[int, str, int] | None:
        """(hotbar number, item, swing period) of the best melee weapon in the HOTBAR:
        a sword, else an axe, else a pickaxe. The bunker needs a pickaxe in the hotbar,
        so a fight that takes over from one always has something to swing."""
        sword = self._sword_slot(info)
        if sword is not None:
            return (sword[0], sword[1], self.WEAPON_PERIOD["sword"])
        for items, cls in ((self.AXES, "axe"), (self.PICKAXES, "pickaxe")):
            for item in items:
                for slot, qty in gui.find_slots(info, item):
                    if slot <= 8 and qty >= 1:
                        return (slot + 1, item, self.WEAPON_PERIOD[cls])
        return None

    def _in_hole(self, pos: dict | None, step: int) -> bool:
        """True while the avatar stands in the hole the last bunker capped (the same
        column, two blocks under the cap cell, within BUNKER_HOLE_STEPS of the cap):
        a hit taken there comes from something that is in the hole with it."""
        lb = self._last_bunker
        if lb is None or pos is None or step - lb["step"] > self.BUNKER_HOLE_STEPS:
            return False
        from mcu_worldmodel import macros_world as MW
        c = MW.block_of(pos)
        cx, cy, cz = lb["cell"]
        return (int(c[0]), int(c[2])) == (cx, cz) and float(pos["y"]) <= cy - 1.5

    def _shaft_cap_line(self) -> str:
        """The line after a dig_down: the shaft over the head is the way a mob gets
        into the cell (one run: a zombie down a 60-block shaft at y 11,
        dead with the bunker reflex and a diamond sword in the inventory)."""
        pos = self._cur_pos
        if pos is None:
            return ""
        from mcu_worldmodel import macros_world as MW
        bx, by, bz = MW.block_of(pos)
        return (f" The shaft over your head is open: a mob that drops down it lands IN "
                f"your cell, where no bunker or wall separates you (one life died so). Before "
                f"mining sideways close it -- place_at(x={int(bx)}, y={int(by) + 2}, "
                f"z={int(bz)}, item=\"cobblestone\", face=\"north\") (any side is "
                f"solid wall here) -- and keep the sword in the hotbar.")

    def _in_shaft(self, cell: tuple[int, int, int] | list[int]) -> bool:
        """The column over `cell` is open and walked: the avatar dug straight down to
        it (one run: walked (-3009, 12) then (-3009, 11), hit at 11)."""
        cx, cy, cz = (int(v) for v in cell)
        return any((cx, cy + k, cz) in self.grid.walked for k in (1, 2, 3))

    def _arm_fightback(self, pos: dict, hp: float, yaw: float,
                       weapon: tuple, desperate: bool = False,
                       close_gui: bool = False, toward_center: bool = False) -> dict[str, Any]:
        """`weapon` is (hotbar, item[, swing period]); `desperate` keeps swinging below
        CRITICAL_HP (nowhere to run: a shaft bottom, a capped hole); `close_gui`
        presses the screen shut first (the drop guard armed -- a mob does not wait);
        `toward_center` aims at the centre of the cell the avatar stands in: a mob in
        the same 1x1 column is pushed to the far side of it (a staged scene: the blind
        sweep at the shove's yaw landed one swing in 60 ticks)."""
        self.cursor_stats["fightback_reflexes"] = (
            self.cursor_stats.get("fightback_reflexes", 0) + 1)
        if toward_center:
            dx = math.floor(float(pos["x"])) + 0.5 - float(pos["x"])
            dz = math.floor(float(pos["z"])) + 0.5 - float(pos["z"])
            if math.hypot(dx, dz) >= 0.06:
                yaw = norm_yaw(math.degrees(math.atan2(-dx, dz)))
        period = int(weapon[2]) if len(weapon) > 2 else self.WEAPON_PERIOD["sword"]
        dealt0 = self.stat_now("custom", "damage_dealt")
        return {"kind": "fightback", "phase": "close" if close_gui else "equip",
                "yaw": float(yaw), "slot": weapon[0], "item": weapon[1], "t": 0,
                "period": period, "desperate": bool(desperate), "sweeps": 0,
                "center": bool(toward_center),
                "remaining": self.FIGHTBACK_TICKS + 40, "hp0": float(hp),
                "dealt0": dealt0, "dealt_chk": dealt0,
                "x0": float(pos["x"]), "z0": float(pos["z"])}

    def _fightback_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Equip the sword, face the attacker (the shove's origin, else behind), then
        swing: attack pulsed every other tick, a short step toward it every 24 ticks
        (a hit knocks the avatar back out of reach). The hit branch re-aims it on each
        further shove and hands over to the flee at CRITICAL_HP."""
        pos = self._cur_pos
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._finish_fightback(rf, "ran out of ticks")
            return None
        if rf["phase"] == "close":
            if not self._gui_open:
                rf["phase"] = "equip"
            else:
                rf["closes"] = rf.get("closes", 0) + 1
                if rf["closes"] > 9:
                    self._finish_fightback(rf, "the screen would not close")
                    return None
                if rf["closes"] % 3 == 1:
                    self._close_armed = True
                    return self._guard_close(mk_act(inventory=1), mk_act)
                return mk_act()
        if self._gui_open:
            self._finish_fightback(rf, "a screen is open")
            return None
        if rf["phase"] == "equip":
            rf["phase"] = "turn"
            return mk_act(**{f"hotbar_{rf['slot']}": 1})
        if rf["phase"] == "turn":
            dy = norm_yaw_delta(float(rf["yaw"]), float(pos["yaw"]))
            dp = -float(pos["pitch"])
            if abs(dy) > 5.0 or abs(dp) > 10.0:
                return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
            rf["phase"] = "fight"
        rf["t"] += 1
        if rf["t"] > self.FIGHTBACK_TICKS:
            self._finish_fightback(rf, None)
            return None
        hp = self._last_health
        if hp is not None and hp <= self.CRITICAL_HP and not rf.get("desperate"):
            # chip damage (fire, poison, a 2-damage mob) never reaches the hit branch
            self._finish_fightback(rf, "health critical")
            return None
        # Swings that land nothing for FIGHTBACK_SWEEP ticks: the mob is not where
        # the shove said. In the same 1x1 cell the two are pushed to opposite corners
        # (s20: avatar at (-.7, -.7) of the cell, the zombie diagonal), so the aim is
        # re-taken at the cell's centre from where the avatar stands NOW; with nothing
        # to go on, an eighth of a turn (a quarter left the diagonal 45 degrees off
        # four times running).
        if rf["t"] % self.FIGHTBACK_SWEEP == 0:
            dealt = self.stat_now("custom", "damage_dealt")
            if dealt <= rf.get("dealt_chk", rf["dealt0"]):
                new_yaw = None
                if rf.get("center"):
                    dx = math.floor(float(pos["x"])) + 0.5 - float(pos["x"])
                    dz = math.floor(float(pos["z"])) + 0.5 - float(pos["z"])
                    if math.hypot(dx, dz) >= 0.06:
                        cand = norm_yaw(math.degrees(math.atan2(-dx, dz)))
                        if abs(norm_yaw_delta(cand, float(rf["yaw"]))) > 3.0:
                            new_yaw = cand
                if new_yaw is None:
                    new_yaw = norm_yaw(float(rf["yaw"]) + 45.0)
                rf["yaw"] = new_yaw
                rf["phase"] = "turn"
                rf["sweeps"] = rf.get("sweeps", 0) + 1
                self.cursor_stats["fightback_sweeps"] = (
                    self.cursor_stats.get("fightback_sweeps", 0) + 1)
            rf["dealt_chk"] = dealt
        # one attack tick, then the weapon's charge: the fight macro's measured sword
        # cadence (RECOVER + 1 = 9) lands 5 hp a swing; every other tick landed 1.7
        # (audit pass 20); an axe or a pickaxe needs its full charge to be worth it.
        # The step toward the mob is for a tunnel: in a 1x1 cell it is a step into
        # the wall, and the auto-jump it starts lifts the eye over the mob's head
        # (s20: the avatar airborne at three of five probes).
        period = int(rf.get("period", macros_entity.RECOVER + 1))
        return mk_act(attack=1 if rf["t"] % period == 1 else 0,
                      forward=0 if rf.get("center") else (1 if rf["t"] % 24 < 4 else 0))

    def _finish_fightback(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        # custom.damage_dealt counts tenths of a heart-point (macros_entity divides by 10)
        dealt = max(0.0, self.stat_now("custom", "damage_dealt") - rf["dealt0"]) / 10.0
        hp = self._last_health
        where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos else "?")
        self.cursor_stats["fightback_damage"] = (
            self.cursor_stats.get("fightback_damage", 0) + int(dealt))
        self.memory.add_note(
            f"the runner fought back with the {rf['item']} for {rf['t']} ticks at {where}: "
            f"dealt {dealt:.1f} hp of damage, health {rf['hp0']:.0f} -> "
            f"{hp if hp is None else round(hp)}/20"
            + (f", the aim turned {rf['sweeps']} quarter(s) on empty swings"
               if rf.get("sweeps") else "")
            + (f" ({why})" if why else "")
            + ". If the hits have stopped the attacker is dead or out of reach -- pick up "
              "its drop and carry on; if they go on, wall the tunnel behind you with two "
              "cobblestone or sprint the way you came, and eat when the bar allows.")
        self._reflex = None

    def _arm_flee(self, pos: dict, away_yaw: float | None = None,
                  seal: bool = False) -> dict[str, Any]:
        self.cursor_stats["flee_reflexes"] = self.cursor_stats.get("flee_reflexes", 0) + 1
        yaw = (float(away_yaw) if away_yaw is not None
               else norm_yaw(float(pos["yaw"]) + 180.0))
        return {"kind": "flee", "phase": "turn", "yaw": yaw,
                "t": 0, "remaining": self.FLEE_TICKS + 30 + (self.SEAL_TICKS if seal else 0),
                "x0": float(pos["x"]), "z0": float(pos["z"]),
                "mark": (float(pos["x"]), float(pos["z"])), "seal": bool(seal)}

    def _flee_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Turn 180 degrees (levelling the view), then sprint-jump forward for
        FLEE_TICKS; a run that stops gaining ground (a wall, a dead end) ends early
        so the model can pick another way out."""
        pos = self._cur_pos
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._finish_flee(rf, "ran out of ticks")
            return None
        if rf["phase"] == "turn":
            dy = norm_yaw_delta(float(rf["yaw"]), float(pos["yaw"]))
            dp = -float(pos["pitch"])
            if abs(dy) > 5.0 or abs(dp) > 10.0:
                return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
            rf["phase"], rf["t"] = "run", 0
        rf["t"] += 1
        if rf["t"] % 20 == 0:
            mx, mz = rf["mark"]
            if math.hypot(float(pos["x"]) - mx, float(pos["z"]) - mz) < 1.0:
                self._finish_flee(rf, "the way is blocked")
                return None
            rf["mark"] = (float(pos["x"]), float(pos["z"]))
        if rf["t"] > self.FLEE_TICKS:
            if rf.get("seal") and self._arm_seal(rf):
                return mk_act()
            self._finish_flee(rf, None)
            return None
        return mk_act(forward=1, sprint=1, jump=1)

    def _arm_seal(self, rf: dict[str, Any]) -> bool:
        """After the run: wall the passage behind (the way the attacker comes) with a
        block at feet level and one on top of it. Needs a placeable block in the hotbar
        and 3+ blocks of run; the targets are the cell one block back along the run
        and the cell above it."""
        from mcu_worldmodel import macros_world as MW

        pos = self._cur_pos
        slot = self._pillar_slot(self._cur_info or {}, min_qty=2)
        if pos is None or slot is None:
            return False
        ran = math.hypot(float(pos["x"]) - rf["x0"], float(pos["z"]) - rf["z0"])
        if ran < 3.0:
            return False
        back = norm_yaw(float(rf["yaw"]) + 180.0)
        dx, dz = MW.axis_facing(back)          # tunnels run along an axis
        fx, fz = math.floor(float(pos["x"])) + dx, math.floor(float(pos["z"])) + dz
        fy = math.floor(float(pos["y"]))
        rf.update({"phase": "seal_equip", "slot": slot[0], "item": slot[1],
                   "feet": (fx, fy, fz), "head": (fx, fy + 1, fz), "seal_t": 0,
                   "base_n": int(self._cur_inv.get(slot[1], 0)), "tries": 0})
        return True

    def _seal_tick(self, rf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """The seal: block selected, turn to face the way back, click the floor's top
        (the feet cell fills), click the new block's top (the head cell fills); the
        inventory says whether both went down. One retry."""
        from mcu_worldmodel import macros_world as MW

        pos = self._cur_pos
        rf["seal_t"] += 1
        placed = rf["base_n"] - int(self._cur_inv.get(rf["item"], 0))
        if rf["seal_t"] > self.SEAL_TICKS:
            self._finish_seal(rf, placed, "out of ticks")
            return None
        ph = rf["phase"]
        if ph == "seal_equip":
            rf["phase"] = "seal_feet"
            return mk_act(**{f"hotbar_{rf['slot']}": 1})
        if ph in ("seal_feet", "seal_head"):
            target = rf["feet"] if ph == "seal_feet" else rf["head"]
            pitch, yaw, dist = MW.angles_to(pos, MW.aim_point(target, "below", 0.5))
            dp = pitch - float(pos["pitch"])
            dy = norm_yaw_delta(yaw, float(pos["yaw"]))
            if abs(dp) > 2.0 or abs(dy) > 2.0:
                return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
            rf["phase"] = "seal_wait_feet" if ph == "seal_feet" else "seal_wait_head"
            rf["wait"] = 0
            return mk_act(use=1)
        if ph in ("seal_wait_feet", "seal_wait_head"):
            rf["wait"] += 1
            want = 1 if ph == "seal_wait_feet" else 2
            if placed >= want:
                if want == 1:
                    rf["phase"] = "seal_head"
                    return mk_act()
                self._finish_seal(rf, placed, None)
                return None
            if rf["wait"] >= 4:
                rf["tries"] += 1
                if rf["tries"] > 3:
                    self._finish_seal(rf, placed, "the blocks would not go down")
                    return None
                rf["phase"] = "seal_feet" if want == 1 else "seal_head"
            return mk_act()
        self._finish_seal(rf, placed, "lost the thread")
        return None

    def _finish_seal(self, rf: dict[str, Any], placed: int, why: str | None) -> None:
        pos = self._cur_pos
        where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos else "?")
        ran = (math.hypot(float(pos["x"]) - rf["x0"], float(pos["z"]) - rf["z0"])
               if pos else 0.0)
        self.cursor_stats["seal_reflexes"] = self.cursor_stats.get("seal_reflexes", 0) + 1
        self.cursor_stats["seal_blocks"] = self.cursor_stats.get("seal_blocks", 0) + int(placed)
        fx, fy, fz = rf["feet"]
        if placed >= 2:
            self.memory.add_note(
                f"the runner sprinted you {ran:.0f} blocks from the attacker and WALLED the "
                f"passage behind you with two {rf['item']} at ({fx}, {fy}, {fz}) and above; "
                f"you stand at {where} facing the wall. A mob cannot break it: turn away "
                f"and dig on in another direction, eat if the bar is low; do not open "
                f"that wall.")
        else:
            self.memory.add_note(
                f"the runner sprinted you {ran:.0f} blocks from the attacker and tried to "
                f"wall the passage behind you at ({fx}, {fy}, {fz}), but only {placed} "
                f"block(s) went down" + (f" ({why})" if why else "")
                + f"; you stand at {where}. Finish the wall NOW (place_at the open cell, "
                f"face=\"below\") or keep sprinting.")
        self._reflex = None

    def _finish_flee(self, rf: dict[str, Any], why: str | None) -> None:
        pos = self._cur_pos
        ran = (math.hypot(float(pos["x"]) - rf["x0"], float(pos["z"]) - rf["z0"])
               if pos else 0.0)
        self.cursor_stats["flee_blocks"] = self.cursor_stats.get("flee_blocks", 0) + int(ran)
        where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos else "?")
        if why is None or (ran >= 4.0 and why not in ("lava ahead", "water ahead")):
            self.memory.add_note(
                f"the runner turned you around and sprinted {ran:.0f} blocks away from the "
                f"attacker, to {where}" + (f" ({why})" if why else "") + ". Keep the "
                "distance: sprint on (travel), or wall the tunnel behind you with two "
                "blocks, and eat if the food bar is low -- do not turn back to fight "
                "under 10 health.")
        else:
            self.memory.add_note(
                f"the runner tried to sprint you away from the attacker but {why} after "
                f"{ran:.0f} blocks (now at {where}): find another way out NOW -- dig "
                f"sideways, or wall the attacker off with two blocks.")
        self._reflex = None

    def _reflex_tick(self, mk_act) -> dict[str, Any] | None:
        """One tick of the hit reflex: turn to the yaw the hit came from, then hand the
        turn to the model. Outside the plan queue (there is no entry to log) and armed
        only with no screen open (the camera does nothing in a GUI)."""
        rf = self._reflex
        pos = self._cur_pos
        if rf is None:
            return None
        if rf.get("kind") == "pillar":
            return self._pillar_tick(rf, mk_act)
        if rf.get("kind") == "bunker":
            return self._bunker_tick(rf, mk_act)
        if rf.get("kind") == "flee" and str(rf.get("phase", "")).startswith("seal"):
            return self._seal_tick(rf, mk_act)
        if rf.get("kind") == "flee":
            return self._flee_tick(rf, mk_act)
        if rf.get("kind") == "fightback":
            return self._fightback_tick(rf, mk_act)
        if rf.get("kind") == "lava":
            return self._lava_tick(rf, mk_act)
        if rf.get("kind") == "drown":
            return self._drown_tick(rf, mk_act)
        rf["remaining"] -= 1
        if pos is None or rf["remaining"] < 0:
            self._reflex = None
            return None
        dy = (float(rf["yaw"]) - pos["yaw"] + 180.0) % 360.0 - 180.0
        if abs(dy) <= 3.0:
            self._reflex = None
            return None
        return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])

    def _lookabs_tick(self, la: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of steering the camera to an ABSOLUTE (pitch, yaw), from truth.

        `look()` is relative and correct only when the entry pose is known:
        `stair_down`'s opening `look(pitch=38)` entered at pitch 25 dug its staircase
        at 63, and entered at pitch 90 clamped into digging straight down -- the exact
        shaft the macro exists to avoid (one run). Absolute aim needs the measured
        [STATE] angles, which exist only at run time, hence a marker.
        """
        pos = self._cur_pos
        if la["remaining"] <= 0:
            if pos is not None:
                self.memory.add_note(
                    f"look_abs ran out of ticks at pitch {pos['pitch']:.0f} yaw "
                    f"{norm_yaw(pos['yaw']):.0f} (target {la.get('pitch')}, "
                    f"{la.get('yaw')}).")
            return None
        la["remaining"] -= 1
        if pos is None:
            return mk_act()     # first tick of an episode: wait for ground truth
        dp = (float(la["pitch"]) - pos["pitch"]) if la.get("pitch") is not None else 0.0
        dy = ((float(la["yaw"]) - pos["yaw"] + 180.0) % 360.0 - 180.0
              ) if la.get("yaw") is not None else 0.0
        if abs(dp) <= 2.0 and abs(dy) <= 2.0:
            return None
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])

    def _aimore_tick(self, ao: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of steering the crosshair onto the iron-ore speckle cluster.

        The missing link the flag->conversion gap exposed: four runs had
        the sentinel stop a macro on a genuine sighting, and none converted, because the
        NOTE hands over a SCREEN pixel while `look_at` wants a WORLD coordinate. This
        closes the loop in screen space directly: re-detect the cluster in each tick's
        frame, steer the camera toward its centroid, declare done when centred. The
        constants are per-tick gains against a moving detection, so exact FOV mapping is
        unnecessary -- 0.14 deg/px horizontal and 0.19 vertical are the 640x360 defaults,
        damped by 0.8 and clamped.
        """
        from mcu_worldmodel import vision

        if ao["remaining"] <= 0:
            self.memory.add_note(
                "aim_at_ore ran out of ticks before centring; the speckles may be "
                "occluded now. zoom the newest frame to re-locate them.")
            return None
        ao["remaining"] -= 1
        frame = self._last_pov
        found = vision.find_ore(frame) if frame is not None else None
        hit = found[1] if found else None
        if hit is None:
            ao["miss"] = ao.get("miss", 0) + 1
            if ao.get("walk", 0) and ao["miss"] >= 3:
                # Lost WHILE closing in: within ~2 blocks the speckles outgrow the
                # detector's blob and density caps and the face reads as solid (both
                # ore faces in a staged scene) -- the crosshair still points at it.
                self.cursor_stats["ore_aimed"] = self.cursor_stats.get("ore_aimed", 0) + 1
                self.memory.add_note(
                    f"aim_at_ore: walked {ao['walk']} ticks up to the speckles; they are "
                    f"too close for the detector now (a face within ~2 blocks reads as "
                    f"solid) and the crosshair holds on them. mine_ahead(n=120) takes it.")
                return None
            if ao["miss"] >= 6:
                self.memory.add_note(
                    "aim_at_ore: the speckle cluster is no longer detected (6 frames). "
                    "It may be out of view or was a false positive -- zoom the newest "
                    "frame; if the wall shows plain stone, resume mining.")
                return None
            return mk_act()             # hold still; the next frame may re-detect
        ao["miss"] = 0
        h, w = frame.shape[0], frame.shape[1]
        ex, ey = hit[0] - w / 2.0, hit[1] - h / 2.0
        # +pitch looks down (screen-down error is positive ey); +yaw turns right.
        dp = max(-20.0, min(20.0, ey * 0.19 * 0.8))
        dy = max(-20.0, min(20.0, ex * 0.14 * 0.8))
        if abs(ex) <= 10.0 and abs(ey) <= 10.0:
            # Centred -- but centred on WHAT distance? The sentinel fires on a face up
            # to ~6 blocks off (a staged scene: 320 px at 5 blocks) and arm's
            # reach is 4.5, so mine_ahead from the flag spot swung 120 ticks at air.
            # Close the distance first: walk at the cluster, re-centring as it grows,
            # until the wall stops the walk (the face is now in reach), the cluster
            # fills the view, or the walk budget is spent. No position -> no walk.
            pos = self._cur_pos
            if pos is not None and ao.get("walking"):
                lx, lz = ao["last_xz"]
                moved = math.hypot(float(pos["x"]) - lx, float(pos["z"]) - lz)
                ao["stuck"] = ao.get("stuck", 0) + 1 if moved < 0.02 else 0
            close = (pos is None or hit[2] >= self.AIM_NEAR_PX
                     or ao.get("walk", 0) >= self.AIM_WALK_TICKS or ao.get("stuck", 0) >= 3)
            if not close:
                ao["walk"] = ao.get("walk", 0) + 1
                ao["walking"], ao["last_xz"] = True, (float(pos["x"]), float(pos["z"]))
                return mk_act(forward=1, camera=[dp, dy])
            self.cursor_stats["ore_aimed"] = self.cursor_stats.get("ore_aimed", 0) + 1
            walked = ao.get("walk", 0)
            why = ("the wall stopped the walk" if ao.get("stuck", 0) >= 3
                   else "the speckles fill the view" if hit[2] >= self.AIM_NEAR_PX
                   else "walk budget spent" if walked else "")
            self.memory.add_note(
                f"aim_at_ore: crosshair centred on the speckles ({hit[2]} px cluster, "
                f"{abs(ex):.0f}/{abs(ey):.0f} px off"
                + (f"; walked {walked} ticks toward them, {why}" if walked else "")
                + "). Mine what you are aiming at now -- mine_ahead(n=120) takes it.")
            return None
        ao["walking"] = False
        return mk_act(camera=[dp, dy])

    def _aimtree_tick(self, at: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of steering the crosshair onto the most trunk-like bark column.

        The wood-phase counterpart of `_aimore_tick`, against `vision.find_tree_trunk`:
        wood-phase aim variance is the largest cross-task loss source (1,900-3,000
        steps in four runs), and every one of those losses was an aiming
        problem, not a finding problem -- leaves were on screen the whole time. Same
        gains, damping and stop rules as the ore servo.
        """
        from mcu_worldmodel import vision

        if at["remaining"] <= 0:
            self.memory.add_note(
                "aim_at_tree ran out of ticks before centring; the trunk may be "
                "occluded by leaves. Walk a few blocks and try again.")
            return None
        at["remaining"] -= 1
        frame = self._last_pov
        hit = vision.find_tree_trunk(np.asarray(frame)) if frame is not None else None
        if hit is None:
            at["miss"] = at.get("miss", 0) + 1
            if at["miss"] >= 6:
                self.memory.add_note(
                    "aim_at_tree: no trunk detected (6 frames). Turn toward visible "
                    "LEAVES and retry -- a tree's leaves mark where its trunk stands; "
                    "in a treeless view, travel toward the nearest leaf mass first.")
                return None
            return mk_act()             # hold still; the next frame may re-detect
        at["miss"] = 0
        h, w = frame.shape[0], frame.shape[1]
        ex, ey = hit[0] - w / 2.0, hit[1] - h / 2.0
        if abs(ex) <= 10.0 and abs(ey) <= 10.0:
            self.cursor_stats["tree_aimed"] = (
                self.cursor_stats.get("tree_aimed", 0) + 1)
            self.memory.add_note(
                f"aim_at_tree: crosshair centred on the trunk ({hit[2]} px of bark, "
                f"{abs(ex):.0f}/{abs(ey):.0f} px off). chop_tree now -- and if chops "
                f"miss, the trunk is out of reach: walk 2-3 blocks forward while "
                f"centred and chop again.")
            return None
        dp = max(-20.0, min(20.0, ey * 0.19 * 0.8))
        dy = max(-20.0, min(20.0, ex * 0.14 * 0.8))
        return mk_act(camera=[dp, dy])

    def _harvesting(self) -> bool:
        """True while the queue's head is a running harvest_tree marker."""
        if not self.queue:
            return False
        head = self.queue[0][0]
        return isinstance(head, dict) and "_harvest" in head

    def _harvest_tick(self, hv: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of `harvest_tree`: aim, walk until the trunk blocks you, chop until
        the stat stream says a log broke, sweep the drop, repeat (mcu_worldmodel.harvest).
        The state lives in the marker dict, so the queue stays serialisable."""
        from mcu_worldmodel import harvest

        frame = self._last_pov
        inv_logs = sum(int(v) for k, v in self._cur_inv.items() if "log" in k)
        action, note = harvest.tick(
            hv, np.asarray(frame) if frame is not None else None, self._cur_pos,
            self._log_breaks, self._other_breaks, inv_logs, self._gui_open)
        if note:
            self.memory.add_note(note)
        if action is None:
            self.cursor_stats["harvest_runs"] = self.cursor_stats.get("harvest_runs", 0) + 1
            self.cursor_stats["harvest_logs"] = (
                self.cursor_stats.get("harvest_logs", 0)
                + max(0, inv_logs - int(hv.get("base_inv") or 0)))
            return None
        kw = dict(action)
        if "camera" in kw:
            kw["camera"] = [float(kw["camera"][0]), float(kw["camera"][1])]
        return mk_act(**kw)

    def _goto_tick(self, gt: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of walking toward a world (x, z), heading recomputed from truth.

        Turn-then-move: a large heading error is corrected standing still (a yaw change
        plus forward curves the path into an arc -- the repo's own movement doctrine),
        and only small corrections ride along with the walk. Three ticks without
        horizontal progress while trying to walk reads as a wall or a drop, and stopping
        with a [NOTE] there beats walking into it for the rest of the entry.
        """
        import math

        pos = self._cur_pos
        if not pos:
            # No position yet (first tick of an episode): wait, don't declare arrival.
            if gt["remaining"] <= 0:
                return None
            gt["remaining"] -= 1
            return mk_act()
        # A detour (see the stall branch below) walks the waypoints first, each
        # within 0.7 of its centre, then the target itself.
        via = gt.get("via") or []
        if via:
            # Reached any waypoint (a corner cut counts): drop it and those before it.
            near = [i for i, (wx, wz) in enumerate(via)
                    if math.hypot(wx - pos["x"], wz - pos["z"]) <= 0.7]
            if near:
                del via[:near[-1] + 1]
                gt["stuck"] = 0
        tx, tz = (via[0] if via else (gt["x"], gt["z"]))
        dx, dz = tx - pos["x"], tz - pos["z"]
        dist = math.hypot(dx, dz)
        if not via and dist <= gt["within"]:
            self.cursor_stats["goto_arrived"] = (
                self.cursor_stats.get("goto_arrived", 0) + 1)
            if gt.get("detoured"):
                self.cursor_stats["goto_detour_arrived"] = (
                    self.cursor_stats.get("goto_detour_arrived", 0) + 1)
            return None
        if gt["remaining"] <= 0:
            short = math.hypot(gt["x"] - pos["x"], gt["z"] - pos["z"])
            self.memory.add_note(
                f"go_to ({gt['x']:.1f}, {gt['z']:.1f}) ran out of ticks at "
                f"({pos['x']:.1f}, {pos['z']:.1f}), {short:.1f} blocks short.")
            return None
        last = gt.get("last")
        moved = (math.hypot(pos["x"] - last[0], pos["z"] - last[1])
                 if last is not None else None)
        gt["last"] = (pos["x"], pos["z"])
        yaw_target = math.degrees(math.atan2(-dx, dz))
        dyaw = ((yaw_target - pos["yaw"] + 180.0) % 360.0) - 180.0
        gt["remaining"] -= 1
        if abs(dyaw) > 20.0:
            gt["stuck"] = 0
            return mk_act(camera=[0.0, max(-30.0, min(30.0, dyaw))])
        if moved is not None and moved < 0.03:
            gt["stuck"] += 1
            if gt["stuck"] >= 3:
                return self._goto_stalled(gt, pos, mk_act)
        else:
            gt["stuck"] = 0
        if gt.get("sneak"):
            # Sneaking, the game does not let the avatar step off a block edge: no jump
            # and no sprint, which would carry it over.
            return mk_act(forward=1, sneak=1, camera=[0.0, max(-8.0, min(8.0, dyaw))])
        return mk_act(forward=1, jump=1, sprint=1,
                      camera=[0.0, max(-8.0, min(8.0, dyaw))])

    def _goto_stalled(self, gt: dict[str, Any], pos: dict[str, float], mk_act
                      ) -> dict[str, Any] | None:
        """Three ticks without progress: record the cell ahead as blocked, then
        detour ONCE over cells this life has walked (grid.detour) when that ends
        nearer the target; otherwise stop with the note. Measured before this:
        30-50% of blocked targets were never reached, and the ground between was
        usually the avatar's own trail."""
        short = math.hypot(gt["x"] - pos["x"], gt["z"] - pos["z"])
        if gt.get("sneak"):
            # An edge or a wall: the walk does not know which, and a detour or a pit
            # climb would leave the sneak that is holding it back from the drop.
            self._keep_event_frame(self.step, "blocked", self._last_pov)
            self.memory.add_note(
                f"go_to ({gt['x']:.1f}, {gt['z']:.1f}) with sneak stopped at "
                f"({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}), {short:.1f} blocks "
                f"short: a block edge with a drop of a block or more ahead (sneak does "
                f"not step off one), or a wall or a step up (sneak does not jump). Look "
                f"down over it before choosing.")
            return None
        self.grid.mark_blocked(self.step, pos)
        if not gt.get("detoured"):
            path = self.grid.detour(pos, gt["x"], gt["z"])
            if path:
                gt["detoured"] = True
                gt["via"] = [(c[0] + 0.5, c[2] + 0.5) for c in path]
                gt["stuck"] = 0
                gt["remaining"] += min(160, 6 * len(path))
                end = path[-1]
                self.cursor_stats["goto_detours"] = (
                    self.cursor_stats.get("goto_detours", 0) + 1)
                self._keep_event_frame(self.step, "blocked", self._last_pov)
                self.memory.add_note(
                    f"go_to ({gt['x']:.1f}, {gt['z']:.1f}) stalled at "
                    f"({pos['x']:.1f}, {pos['z']:.1f}), {short:.1f} blocks short -- the "
                    f"runner is detouring over {len(path)} cells you walked earlier, "
                    f"ending at ({end[0]}, {end[1]}, {end[2]}), then trying the target "
                    f"again from there.")
                return mk_act()
        # No detour, or the detour stalled as well: standing in a hole below the trail?
        if not gt.get("pit_climbed"):
            up = self.grid.above(pos)
            if up is not None and self._queue_pit_climb(gt, pos, up):
                return None
        self._keep_event_frame(self.step, "blocked", self._last_pov)
        self.memory.add_note(
            f"go_to ({gt['x']:.1f}, {gt['z']:.1f}) is blocked at "
            f"({pos['x']:.1f}, {pos['z']:.1f}), {short:.1f} blocks short -- a "
            f"wall, pit or tree is in the way"
            + (" (the detour over walked cells stalled too)" if gt.get("detoured")
               else " and no walked cell lies nearer the target")
            + ". Clear it (mine_forward toward it) or pick a target you have walked.")
        return None

    def _queue_pit_climb(self, gt: dict[str, Any], pos: dict[str, float],
                         up: tuple) -> bool:
        """The stalled walk stands `rise` blocks below a cell it walked within 6 blocks:
        a hole (a fall, a shaft, a ravine floor) the walk cannot climb. Queue
        `pillar_up(rise)` and the same go_to once more behind the stalled one, so the
        next try starts at the rim. False (with a note) when no block can be placed.
        One run sat 700 steps at y 63-64 under its y 69 trail re-issuing go_to."""
        from mcu_worldmodel import macros_world
        from mcu_worldmodel.procedures import go_to
        cell, rise = up
        n = int(max(2, min(6, rise)))
        acts, msg = macros_world.pillar_up(self.cursor, self._cur_info, n=n)
        if not acts:
            self.memory.add_note(
                f"You stand {rise} blocks below the cell ({cell[0]}, {cell[1]}, {cell[2]}) "
                f"you walked earlier: a hole the walk cannot climb. {msg} Dig a stair "
                f"up (stair_up) or get {n} blocks to pillar_up({n}).")
            return False
        gt["pit_climbed"] = True
        again = go_to(x=gt["x"], z=gt["z"], within=gt["within"], n=160)[0]
        again["_goto"]["pit_climbed"] = True
        idx = self.queue[0][1] if self.queue else 0
        at = 1 if self.queue else 0
        for e in acts + [again]:
            self.queue.insert(at, (e, idx))
            at += 1
        self.cursor_stats["pit_climbs"] = self.cursor_stats.get("pit_climbs", 0) + 1
        self._keep_event_frame(self.step, "hole", self._last_pov)
        self.memory.add_note(
            f"go_to ({gt['x']:.1f}, {gt['z']:.1f}) stalled at ({pos['x']:.1f}, "
            f"{pos['z']:.1f}): you stand {rise} blocks below the cell ({cell[0]}, "
            f"{cell[1]}, {cell[2]}) you walked earlier -- a hole the walk cannot climb. "
            f"The runner queued pillar_up({n}) and the same go_to again from the top.")
        return True

    def _keep_event_frame(self, step: int, label: str, pov) -> None:
        """Keep the view at an event for this turn's sheet (the last three)."""
        if pov is None or self.memory_mode == "direct" or not getattr(self, "event_sheet", True):
            return
        try:
            arr = np.array(pov, copy=True)
        except Exception:
            return
        self._event_frames.append((int(step), str(label), arr))
        del self._event_frames[:-3]

    def _event_sheet(self, info: dict) -> Path | None:
        """A 2x2 sheet: the current view, then the frames at this turn's events,
        each labelled -- so the frame that carries the evidence is in front of the
        model on the turn it matters (mfm looked at past frames in 2-18% of turns)."""
        if (not self._event_frames or self.memory_mode == "direct"
                or not getattr(self, "event_sheet", True)):
            self._event_frames = []
            return None
        try:
            from PIL import ImageDraw
            tiles = [(self.step, "now", info.get("pov"))] + list(self._event_frames)
            w, h = self.frame_size[0] // 2, self.frame_size[1] // 2
            sheet = Image.new("RGB", (2 * w, 2 * h), (24, 24, 24))
            draw = ImageDraw.Draw(sheet)
            for i, (step, label, pov) in enumerate(tiles[:4]):
                if pov is None:
                    continue
                arr = np.asarray(pov)
                if arr.dtype != np.uint8:
                    arr = arr.astype(np.uint8)
                im = Image.fromarray(arr).resize((w, h), Image.BILINEAR)
                x, y = (i % 2) * w, (i // 2) * h
                sheet.paste(im, (x, y))
                text = f"{label} step {step}"
                draw.rectangle([x, y, x + 8 + 7 * len(text), y + 14], fill=(0, 0, 0))
                draw.text((x + 4, y + 1), text, fill=(255, 220, 120))
            path = self.memory.attach_dir / "events.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            sheet.save(path, format="PNG")
            self.cursor_stats["event_sheets"] = self.cursor_stats.get("event_sheets", 0) + 1
            self._sheet_labels = [f"{l} (step {s})" for s, l, _ in tiles[1:4]]
        except Exception as e:
            logger.warning(f"[agent] event sheet failed: {e}")
            path = None
        self._event_frames = []
        return path

    def _pose_replay_tick(self, ug: dict[str, Any], pose: dict[str, float], mk_act
                          ) -> dict[str, Any] | None:
        """Walk to the recorded standing spot (sneaking the last block), turn to the
        recorded pitch/yaw, then let the presses run. None when done or given up.
        The estimated cell was one block off in one run (~10k steps) and another (4 failed
        re-opens by step 1073); the pose that opened the screen is exact."""
        pos = self._cur_pos
        st = ug.setdefault("replay", {"phase": "walk", "t": 0, "stuck": 0, "last": None})
        st["t"] += 1
        if pos is None or st["t"] > 140:
            return None
        if st["phase"] == "walk":
            dx, dz = pose["x"] - pos["x"], pose["z"] - pos["z"]
            d = math.hypot(dx, dz)
            if d <= 0.35:
                st["phase"] = "turn"
                return mk_act()
            yaw_target = math.degrees(math.atan2(-dx, dz))
            dyaw = ((yaw_target - pos["yaw"] + 180.0) % 360.0) - 180.0
            last = st.get("last")
            moved = (math.hypot(pos["x"] - last[0], pos["z"] - last[1])
                     if last is not None else None)
            st["last"] = (pos["x"], pos["z"])
            if abs(dyaw) > 20.0:
                return mk_act(camera=[0.0, max(-30.0, min(30.0, dyaw))])
            if moved is not None and moved < 0.02:
                st["stuck"] += 1
                if st["stuck"] >= 8:
                    return None
            else:
                st["stuck"] = 0
            return mk_act(forward=1, sneak=1 if d < 1.2 else 0,
                          camera=[0.0, max(-8.0, min(8.0, dyaw))])
        if st["phase"] == "turn":
            dp = float(pose["pitch"]) - float(pos["pitch"])
            dy = norm_yaw_delta(float(pose["yaw"]), float(pos["yaw"]))
            if abs(dp) > 1.5 or abs(dy) > 1.5:
                return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
            st["phase"] = "done"
        return None

    def _screen_item_for(self, ug: dict[str, Any]) -> str | None:
        """The table/furnace a use_until_gui is opening: its `item`, or the kind the
        `_screen_need` marker queued behind it expects."""
        if ug.get("item"):
            return str(ug["item"])
        for head, _ in list(self.queue)[:3]:
            need = head.get("_screen_need") if isinstance(head, dict) else None
            if need:
                return {"table": "crafting_table", "furnace": "furnace"}.get(
                    str(need.get("kind")))
        return None

    def _queue_water_escape(self, idx: int) -> None:
        """After a water refusal: walk the avatar along its own trail to the nearest
        walked cell 8+ blocks from every water cell, as one go_to queued right behind
        the refused dig. The pond trap cost a median 612 steps per half run."""
        path = self.grid.escape_from_water(self._cur_pos, self.DIG_WATER_BLOCKS + 2.0)
        if not path:
            return
        from mcu_worldmodel.procedures import go_to
        end = path[-1]
        entry = go_to(x=end[0] + 0.5, z=end[2] + 0.5, within=0.8,
                      n=min(300, 40 + 8 * len(path)))[0]
        entry["_goto"]["via"] = [(c[0] + 0.5, c[2] + 0.5) for c in path[:-1]]
        entry["_goto"]["detoured"] = True
        self.queue.insert(1 if self.queue else 0, (entry, idx))
        self.cursor_stats["water_escapes"] = self.cursor_stats.get("water_escapes", 0) + 1
        self.memory.add_note(
            f"The runner is walking you {len(path)} cells along your own trail to "
            f"({end[0]}, {end[1]}, {end[2]}), {self.DIG_WATER_BLOCKS + 2.0:.0f}+ blocks from "
            f"every water cell it knows; dig_down from there.")

    #: collect_drops walk cycle: out-and-back on both axes, 80 ticks per lap. The
    #: forward leg comes first and is the long one because the drops a sweep is
    #: called for lie AHEAD (the trunk or the face just worked), and an empty sweep
    #: ends at SWEEP_EMPTY_CAP: with 8/16 those 24 ticks were 1.7 blocks out and 3.5
    #: back, ending further from the drops than they began (one run: three
    #: logs 3 blocks ahead, "picked up nothing"); 12/24 is 2.6 blocks out and back
    #: to the start.
    _SWEEP_CYCLE = (("forward", 12), ("back", 24), ("forward", 12),
                    ("left", 8), ("right", 16), ("left", 8))
    _SWEEP_LAP = 80

    #: Ticks an empty collect_drops sweep runs before giving up (see _sweep_tick).
    SWEEP_EMPTY_CAP = 24
    #: aim_at_ore's closing walk (see _aimore_tick): a centred cluster smaller than
    #: this (px) is walked at, for at most this many ticks. Measured: 320 px at 5
    #: blocks, 481 at 4 (diamond); a face within two blocks is thousands.
    AIM_NEAR_PX = 1500
    AIM_WALK_TICKS = 30
    #: Ticks use_until_gui waits after its last press before calling the screen
    #: absent. `isGuiOpen` reports a screen late under server load: one run (step
    #: 11775, ten arms on the node) got "no screen opened" from a two-press call and
    #: its next block showed the furnace screen OPEN -- the last take of its run.
    GUI_LAG_TICKS = 20
    #: Mean brightness (0-255) of the lower-central view below which a mining macro
    #: ran in the dark. Measured: an unlit stage tunnel reads 11-16, a
    #: torch-lit one 41-91, one run's y=11 strip mine 18. The colour ore watch sees
    #: nothing in the dark (a probe: n=0 on dark frames), and no arm
    #: of that cohort crafted a torch while five of them mined 1-10 coal.
    DARK_TUNNEL_LUM = 30.0
    #: Health at or below which a repeated hit always interrupts the plan.
    CRITICAL_HP = 6.0
    #: Underground (below BUNKER_Y), a hit at or below BUNKER_HP makes the runner dig
    #: two blocks down and cap the hole instead of pillaring: a pillar needs headroom
    #: to jump into, and under a tunnel ceiling the block never places. One run (twice)
    #: and one run died at y 14-28 in the iron search, each after "tried
    #: to pillar you up ... but the block did not place". The threshold is above
    #: CRITICAL_HP because the dig itself takes ~40 ticks under fire: one run
    #: (y 44) armed it at 8 hp against 4-damage hits every ~25 ticks and
    #: died at 4 hp with the hole one block deep -- the dig plus the cap needs 47+
    #: ticks, three hits of margin, so it starts at 14.
    BUNKER_HP = 17.5        # any hit of 3+ underground (was 14: the second hit came too late)
    TORCH_EVERY = 8.0       # blocks of level tunnel between torches
    TORCH_MAX_Y = 50.0      # torches only underground
    BUNKER_Y = 50.0
    #: A second hit within this many ticks of the first is a melee mob at arm's length
    #: (a zombie swings every 20-25 ticks; arrows come 40+ apart): under it a dig
    #: cannot finish (two runs and a staged scene: the zombie followed the avatar into
    #: the hole), so the runner sprints instead -- along the knockback when the plan
    #: stood still (the shove points away from the attacker), else the 180 turn.
    MELEE_CADENCE = 30
    KNOCKBACK_MIN = 0.2
    #: With a sword in the hotbar the melee cadence is answered by facing the attacker
    #: and swinging, not by the sprint: one run (y 25) fled up its own
    #: one-wide staircase at 12 hp, was hit every 26 ticks for 8 blocks and died at 4
    #: with a diamond sword in hand. A diamond sword kills a zombie in three swings.
    FIGHTBACK_TICKS = 80
    SWORDS = ("diamond_sword", "iron_sword", "stone_sword", "golden_sword", "wooden_sword")
    #: After the swords: an axe (9 damage since Java 1.9) outhits every pickaxe. The
    #: swing period per class is a full charge (the sword's is the measured cadence).
    AXES = ("netherite_axe", "diamond_axe", "iron_axe", "stone_axe", "golden_axe",
            "wooden_axe")
    WEAPON_PERIOD = {"sword": 9, "axe": 20, "pickaxe": 17}
    #: Ticks of swings that land nothing before the fightback turns its aim a quarter.
    FIGHTBACK_SWEEP = 16
    #: A hit inside a capped hole this many ticks after the cap is from something IN it.
    BUNKER_HOLE_STEPS = 600
    #: A hit while this share of the lower view is lava-coloured is the lava (or the
    #: fire it lit), not a mob: one run burned 13 -> 9 -> 4 -> dead standing
    #: in a lava pool with a water bucket in its hotbar while the runner dug a bunker
    #: beside it. vision.lava_fraction on the corpus: the seven LAVA AHEAD
    #: frames (lakes, not yet burning) 0.011-0.099, one run's in-lava frames 0.21 and 0.07,
    #: three runs' lava-death frames 0.17-0.47, <= 0.002 without lava. 0.15 is the
    #: standing-in-it band (a lake ahead at the bridge level, 0.10, is not it: a blaze's or
    #: a ghast's hit taken on a ledge above a lava sea must go to the fight or the flee, not
    #: to a blind step back -- audit pass 15). Flames count too (vision.fire_fraction): in a
    #: lava cell at eye level no lava shows, only the fire, and the flames are what arm the
    #: reflex there (a staged scene).
    LAVA_ESCAPE_FRAC = 0.15
    #: Any lava in view at all (the vision floor is 1%): with a 4.0 loss it is contact.
    LAVA_TOUCH_FRAC = 0.02
    #: Markers the lava guard never interrupts: the deliberate approaches to lava
    #: (find_lava's search, make_obsidian's standoff / pour / scoop / check, the
    #: obsidian mining at the pool) carry their own stops and notes.
    LAVA_GUARD_EXEMPT = ("_findlava", "_backoff", "_scoop", "_obsidiancheck", "_mineobs")
    #: The shaft guard looks this far ahead of the feet (the hitbox is 0.6 wide, a walk
    #: covers 0.2 a tick and slides ~0.25 after the key is released).
    SHAFT_LOOKAHEAD = 1.0
    #: ... and at most this far along the motion (a sprint-jump carries ~4 blocks).
    SHAFT_LOOKAHEAD_MAX = 5.0
    #: An unplanned drop of this many blocks (free fall: one tick faster than FALL_VMAX)
    #: stops the plan on landing (agent._fall_guard).
    FALL_MIN_DROP = 4.0
    FALL_VMAX = 0.5
    LAVA_OUT_TICKS = 14
    LAVA_OUT_MAX = 40
    #: A gradual loss with water around the avatar is drowning: one run dug a
    #: shaft one block from a pond (the guard read the water at 0.30-0.32 of the view at
    #: the dig's start), the shaft flooded at y 60, the avatar lost 4 then 9 health per
    #: 100 ticks with its hit frames showing only the shaft's dirt, tried pillar_up (no
    #: block places while swimming) and died 416 ticks after the last water reading. The
    #: response is to hold jump: a swim up to the surface, where the air comes back.
    #: "Water around" is the frame now or the guard's reading within DROWN_WATER_STEPS
    #: ticks and DIG_WATER_BLOCKS of the spot.
    DROWN_WATER_FRAC = 0.25
    DROWN_WATER_STEPS = 600
    DROWN_TICKS = 40
    DROWN_MAX = 100
    #: dig_down / stair_down are refused within this many blocks of water seen in the last
    #: DIG_WATER_STEPS ticks (the shaft floods; one run's ran a block from the pond it had
    #: just tried to fill the bucket at).
    DIG_WATER_BLOCKS = 6.0
    DIG_WATER_STEPS = 200
    #: A melee attacker keeps hitting through a dig or a pillar: one run (y 18)
    #: fought a zombie from 16 hp, was bunkered at 4 and died inside the dig;
    #: a staged scene saw a zombie follow the avatar into the hole. Melee is read off
    #: the plan: a combat head means the model is toe to toe with a mob it can see
    #: (the hit cadence was tried and misread a slow zombie as arrows, in a staged scene).
    #: The escape is a sprint: a zombie walks at ~4.3 blocks/s, a sprint-jump runs ~7.
    FLEE_TICKS = 60
    SEAL_TICKS = 40         # the wall behind after the run: turn, two clicks, a retry
    #: Below this share of the lower view a lava sighting is a SLIVER -- a fall down a
    #: wall or one source in a cave face, most often flowing lava (cobblestone after a
    #: pour) -- not the lake the obsidian needs (30%+ in every lake sighting on record).
    #: two runs (3%) and one run (1%) poured on slivers and mined stone. Same threshold as
    #: previous.LAKE_FRAC.
    LAVA_SLIVER_FRAC = 0.08
    #: Pickaxes the bunker digs with, best first (the floor of a mine is stone).
    PICKAXES = ("netherite_pickaxe", "diamond_pickaxe", "iron_pickaxe", "stone_pickaxe",
                "golden_pickaxe", "wooden_pickaxe")
    #: Markers / raw keys that move the avatar: a plan whose head is one of these is
    #: an escape (or a walk) and survives repeated hits; anything else stands still.
    _MOVING_MARKERS = ("_goto", "_servo")
    _MOVING_KEYS = ("forward", "back", "left", "right", "jump", "sprint")

    def _head_is_movement(self) -> bool:
        """True when the queued plan's head moves the avatar (see the repeat-hit rule):
        a walk (go_to / a position servo) or raw movement keys -- one run's lava
        escape was "left + jump x80". The mining cycles (`_mfwd`: stair_down and
        strip_mine) are NOT movement here: they stand at a face most of the time, and
        one run died inside one with the hits arriving every few seconds."""
        if not self.queue:
            return False
        head = self.queue[0][0]
        if any(k in head for k in self._MOVING_MARKERS) or any(
                k in head for k in macros.MOVING):
            return True
        if any(k in head for k in ("_dig", "_chop", "_harvest", "_sweep", "_aimore",
                                   "_aimtree", "_click", "_use_gui", "_lookabs",
                                   "_seq", "_mfwd")):
            return False
        return any(head.get(k) for k in self._MOVING_KEYS)

    def _sweep_tick(self, sw: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of a pickup sweep; done the moment the inventory total rises.

        Exists because mined drops kept being left on the ground: one run chopped two
        logs by step 518 and reached step 600 with an empty hotbar, then spent seven
        near-identical turns hunting them; its endgame lost two iron ores the same way.
        Pickup is proximity-triggered, so the fix is to *walk the area*, keyed on the
        one signal that cannot lie -- the inventory count."""
        if self._gui_open:
            self.cursor_stats["sweep_gui_stops"] = (
                self.cursor_stats.get("sweep_gui_stops", 0) + 1)
            self.memory.add_note(
                "collect_drops stopped at once: a SCREEN is open, and movement does "
                "nothing in the world while it is. Close it, then sweep.")
            return None
        if "base" not in sw:
            sw["base"] = sum(self._cur_inv.values())
            sw["start"] = self.step
        gained = sum(self._cur_inv.values()) - sw["base"]
        if gained > 0:
            self.cursor_stats["sweep_collected"] = (
                self.cursor_stats.get("sweep_collected", 0) + 1)
            self.memory.add_note(
                f"collect_drops: the inventory rose by {gained} item"
                f"{'s' if gained != 1 else ''} after "
                f"{self.step - sw['start']} tick(s); stopping the sweep.")
            return None
        if sw["i"] >= min(sw["t"], self.SWEEP_EMPTY_CAP):
            # Across the 24 landed z arms, collect_drops was called 22-65 times a run
            # and 87% of its ticks (26,152 of 29,934) gained nothing; a sweep that
            # does pay off does so within ~12-25 ticks. So an empty sweep ends at
            # the cap, whatever budget was asked for.
            self.cursor_stats["sweep_empty"] = (
                self.cursor_stats.get("sweep_empty", 0) + 1)
            self.memory.add_note(
                f"collect_drops: swept {sw['i']} ticks and picked up nothing, so it "
                f"stopped early -- there is no drop within reach of this spot. Blocks "
                f"you mine while standing next to them are picked up by themselves; "
                f"sweep only for a drop you walked away from, standing ON the spot "
                f"that was mined (drops can sit down the hole or behind the trunk).")
            return None
        pos, key = sw["i"] % self._SWEEP_LAP, "forward"
        for k, n in self._SWEEP_CYCLE:
            if pos < n:
                key = k
                break
            pos -= n
        sw["i"] += 1
        return mk_act(**{key: 1})

    def _ore_flag(self, marker: dict[str, Any]) -> bool:
        """True when the current frame shows an iron- or diamond-ore candidate worth
        stopping for.

        Sampled every 8th tick of a mining marker, never while a GUI is up, and rate
        limited to one flag per 100 steps -- resuming the same tunnel with the same
        speckles still on screen must not re-stop the macro instantly.
        """
        marker["t"] = marker.get("t", 0) + 1
        if marker["t"] % 8 or self._gui_open or self._last_pov is None:
            return False
        frame = np.asarray(self._last_pov)
        if frame.ndim == 3 and frame.shape[0] >= 3 and frame.shape[1] >= 4:
            h, w = frame.shape[:2]
            marker["lum_sum"] = (marker.get("lum_sum", 0.0)
                                 + float(frame[h // 3:, w // 4:3 * w // 4].mean()))
            marker["lum_n"] = marker.get("lum_n", 0) + 1
        if self.step - self._last_ore_flag_step < 100:
            return False
        found = vision.find_ore(frame)
        if found is None:
            return False
        kind, hit = found
        self._last_ore_flag_step = self.step
        self.cursor_stats["ore_flagged"] = self.cursor_stats.get("ore_flagged", 0) + 1
        if kind == "diamond":
            self.cursor_stats["ore_flagged_diamond"] = (
                self.cursor_stats.get("ore_flagged_diamond", 0) + 1)
        # Flush the rest of the plan, exactly as the damage interrupt does. Hardening,
        # not a bug fix: the trajectory audit found every live flag happened
        # to sit in the plan's LAST entry (models put the open-ended mining entry last),
        # so the act turn arrived within 0-2 steps anyway. The flush guarantees that
        # alignment for mid-plan flags too. The executing marker stays at the head --
        # it is about to return None and next_action pops it.
        head = self.queue[0] if self.queue else None
        dropped = len({idx for _, idx in list(self.queue)[1:]}) if head else 0
        if dropped:
            self.queue.clear()
            self.queue.append(head)
            self.cursor_stats["ore_flush_dropped"] = (
                self.cursor_stats.get("ore_flush_dropped", 0) + dropped)
        self.memory.add_note(
            f"mining stopped: {kind}-ore-like speckles on screen at ({hit[0]}, {hit[1]}), "
            f"{hit[2]} px. The rest of the plan "
            f"({dropped} entr{'y' if dropped == 1 else 'ies'}) was dropped so you can "
            + ("act while the speckles are still in view: zoom the frame, look_abs "
               "(or look_at) onto the speckles, then {\"attack\": 1} holds (repeat 30, "
               "each cut when its block breaks) to dig out exactly what you are aiming "
               "at. The watcher rests 100 steps after a flag, so the next holds push "
               "through." if self.atoms else
               "act while the speckles are still in view: aim_at_ore (centres the "
               "crosshair), then mine_ahead(n=120) to dig out exactly what you are "
               "aiming at. Pass ore_watch=false to push through instead."))
        return True

    def _seq_tick(self, sq: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """Play out a fixed mining sequence, watching the walls for ore candidates."""
        if "base_breaks" not in sq:
            sq["base_breaks"] = self._log_breaks + self._other_breaks
        if sq["ore"] and self._ore_flag(sq):
            return None
        if sq.get("until_item"):
            # mine_until: the swings stop the moment the named item lands in the
            # inventory (flint out of gravel, a drop that needs the block below it
            # broken), measured from the count at the first tick of THIS marker.
            have = int(self._cur_inv.get(str(sq["until_item"]), 0))
            if sq.get("base_n") is None:
                sq["base_n"] = have
            gained = have - int(sq["base_n"])
            if gained >= max(1, int(sq.get("until_n", 1))):
                self.cursor_stats["mine_until_hits"] = (
                    self.cursor_stats.get("mine_until_hits", 0) + 1)
                self.memory.add_note(
                    f"{sq.get('label', 'mine_until')}: stopped early -- "
                    f"{sq['until_item']} +{gained} in the inventory after {sq['i']} "
                    f"ticks.")
                return None
        if sq["i"] >= len(sq["steps"]):
            # The same accounting the displacement cycle gives: a labelled sequence
            # (mine_ahead) says what its swings actually produced, so an aimed dig
            # that broke nothing is visible at the next act turn, not just in stats.
            if sq.get("label"):
                broke = int(self._log_breaks + self._other_breaks - sq["base_breaks"])
                self.memory.add_note(
                    f"{sq['label']}: finished {sq['i']} ticks, broke {broke} "
                    f"block{'s' if broke != 1 else ''}"
                    + ("." if broke else " -- the aim may be off or the block out of "
                       "reach; zoom the newest frame before swinging again."))
            return None
        action = sq["steps"][sq["i"]]
        sq["i"] += 1
        return action

    def _mfwd_tick(self, mf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of displacement-verified tunnelling: foot block, eye block, walk in.

        The census: 58-97% of mining entries ended with <0.5 blocks of
        movement -- the old macros held attack at eye level (or walked 2 ticks into an
        unbroken wall) and the avatar dug in place while the iron search scanned no new
        rock. Both endgame models independently re-derived the working cycle in their
        world models (ked_final1: "pitch28 mine ~100, forward+jump 40, pitch0 mine
        ~100"; one run: "check coordinates rather than assuming advance"). This marker
        is that discovery promoted into mechanism, closed on the two signals that
        matter: the break stat (did the face open?) and [STATE] position (did we move?).
        Two consecutive cycles that break blocks without gaining ground stop the entry
        with a diagnosis instead of spending the rest of the budget in place.
        """
        if self._gui_open:
            # With a screen up, attack/movement do nothing in the world: one run
            # spent 4x158 ticks swinging at a crafting menu before this check existed.
            # One tick, an honest note, and the model can close the screen properly.
            self.cursor_stats["mine_gui_stops"] = (
                self.cursor_stats.get("mine_gui_stops", 0) + 1)
            self.memory.add_note(
                f"{mf['label']} stopped at once: a SCREEN is open, and mining ticks do "
                f"nothing in the world while it is. Stow any off-inventory stacks, "
                f"close the screen (close_inventory), then mine.")
            return None
        if mf["ore"] and self._ore_flag(mf):
            return None
        pos = self._cur_pos
        if pos is None:
            return mk_act()             # first tick of an episode: wait for ground truth
        if mf["start"] is None and mf["label"] == "stair_down":
            refusal = self._dig_water_refusal("stair_down")
            if refusal:
                self._note_failure("stair_down")
                self._flush_tail(refusal, "dig_water_refusals")
                return None
        if mf["start"] is None:
            mf["start"] = (pos["x"], pos["y"], pos["z"])
        breaks = self._log_breaks + self._other_breaks
        if mf["base_breaks"] is None:
            mf["base_breaks"] = breaks
            if mf["down_by"] is None:
                mf["phase"], mf["phase_t"] = "close", 0

        def _finish(reason: str) -> None:
            desc = mf["start"][1] - pos["y"]
            self.memory.add_note(
                f"{mf['label']}: broke {mf['broken']} blocks, advanced "
                f"{mf['advanced']:.1f} blocks in {mf['used']} ticks"
                + (f", descended {desc:.1f}" if mf["down_by"] is not None else "")
                + (f" (plus {mf['closed']:.1f} blocks walked up to the face first)"
                   if mf.get("closed", 0.0) >= 0.3 else "")
                + (f", {mf['torches']} torch(es) planted on the way"
                   if mf.get("torches") else "")
                + (f". {reason}" if reason else ".")
                + self._dark_line(mf))

        if mf["down_by"] is not None and mf["start"][1] - pos["y"] >= mf["down_by"]:
            self.cursor_stats["mine_reached_depth"] = (
                self.cursor_stats.get("mine_reached_depth", 0) + 1)
            _finish("Target depth reached.")
            return None
        if mf["budget"] <= 0:
            _finish("Mostly digging in place -- the passage is not opening; re-aim or "
                    "change heading." if mf["broken"] >= 3 and mf["advanced"] < 1.0
                    else "")
            return None
        mf["budget"] -= 1
        mf["used"] += 1
        if mf["down_by"] is not None:
            # A staircase that is not going down is the one thing its cycle cannot
            # see from breaks and advance alone: one run ran stair_downs that broke 4-13
            # blocks, advanced 2-5, and descended 0.0 to their full tick budgets, on
            # both arms. ~32 ticks buys a block of depth when the carve works, so 96
            # ticks with less than one block of descent means it is not working.
            if mf.get("desc_used") is None:
                mf["desc_used"], mf["desc_y"] = mf["used"], pos["y"]
            elif mf["used"] - mf["desc_used"] >= 96:
                if mf["desc_y"] - pos["y"] < 1.0:
                    # Escalate before giving up. A failing carve cycle runs ~97
                    # ticks, so this checkpoint always fires one tick before the
                    # first cycle-end bump could: two runs ended with every arm at
                    # min_y>=50 and stair_steepened=0 across all six -- the
                    # steepening ladder was dead code behind this abort.
                    if mf.get("p_lo_bump", 0.0) < 14.0:
                        mf["p_lo_bump"] = min(14.0, mf.get("p_lo_bump", 0.0) + 5.0)
                        self.cursor_stats["stair_steepened"] = (
                            self.cursor_stats.get("stair_steepened", 0) + 1)
                        self.memory.add_note(
                            f"{mf['label']}: no depth gained in the last "
                            f"{mf['used'] - mf['desc_used']} ticks -- steepening "
                            f"the cut to {mf['p_lo'] + mf['p_lo_bump']:.0f} deg "
                            f"and continuing this entry.")
                        mf["desc_used"], mf["desc_y"] = mf["used"], pos["y"]
                    else:
                        self._note_failure(mf["label"])
                        self._flush_tail(
                            f"{mf['label']}: broke {mf['broken']} blocks, advanced "
                            f"{mf['advanced']:.1f} in {mf['used']} ticks, descended "
                            f"{mf['start'][1] - pos['y']:.1f}. STOPPED EARLY: no "
                            f"depth in the last {mf['used'] - mf['desc_used']} ticks "
                            f"even at the steepest cut "
                            f"({mf['p_lo'] + mf['p_lo_bump']:.0f} deg). This ground "
                            f"is not taking a staircase here -- move a few blocks "
                            f"and start a fresh stair_down on different footing.",
                            "stair_no_descent_stops")
                        return None
                else:
                    mf["desc_used"], mf["desc_y"] = mf["used"], pos["y"]

        def _enter(phase: str) -> None:
            mf["phase"] = phase
            mf["phase_t"] = 0
            mf["base_breaks"] = breaks
            mf["adv_from"] = (pos["x"], pos["z"]) if phase == "adv" else None
            if phase == "foot":
                mf["cycle_y"] = pos["y"]

        ph = mf["phase"]
        if ph == "torch":
            act = self._torch_step(mf, mk_act)
            if act is not None:
                return act
            _enter("close")
            return mk_act()
        if ph == "close":
            # Walk up to the face first. The foot carve at p_lo assumes the face is
            # adjacent: from 2.3+ blocks the pitch-35 ray lands on the FLOOR of the
            # cell before it, and the walk-in then hops into that hole -- y 11 -> 10 at
            # the third cycle, "did not move" for the rest (a probe;
            # one run stalled the same way three times at y 12, each
            # strip_mine resumed from 2+ blocks behind its face). Blocked = no ground
            # gained on a tick; an open passage is walked for up to 40 ticks before
            # the carve. The walk is reported apart from `advanced` (tunnelled
            # distance): folded in, it muted the "digging in place" diagnosis for an
            # entry that started behind its face (audit pass 19).
            mf["phase_t"] += 1
            prev = mf.get("close_from")
            mf["close_from"] = (pos["x"], pos["z"])
            if prev is not None:
                step_d = math.hypot(pos["x"] - prev[0], pos["z"] - prev[1])
                mf["close_gain"] = mf.get("close_gain", 0.0) + step_d
                if (mf["phase_t"] >= 3 and step_d < 0.03) or mf["phase_t"] > 40:
                    mf["closed"] = mf.get("closed", 0.0) + mf["close_gain"]
                    mf["close_gain"] = 0.0
                    mf["close_from"] = None
                    _enter("foot")
                    return mk_act()
            return mk_act(forward=1)
        if ph in ("foot", "eye"):
            mf["phase_t"] += 1
            # The stair carve is aim-geometry-sensitive: at the stock 48 the ray can
            # land on the same-level floor block instead of the one-below step, and the
            # avatar then advances without dropping -- every stair failure of
            # two runs read "broke 3, advanced 1.0, descended 0.0". Each cycle
            # that completes without descending steepens the next foot carve by 5
            # degrees (up to +14); a cycle that actually drops resets the bump.
            target = (mf["p_lo"] + mf.get("p_lo_bump", 0.0) if ph == "foot"
                      else mf["p_hi"])
            dp = target - pos["pitch"]
            # Align first; but if [STATE] pitch is not converging (stale wire truth),
            # mine at the current aim rather than spinning the camera forever.
            if abs(dp) > 4.0 and mf["phase_t"] <= 12:
                return mk_act(camera=[max(-20.0, min(20.0, dp)), 0.0])
            if breaks > mf["base_breaks"] + 0.5:
                mf["broken"] += 1
                _enter("eye" if ph == "foot" else "adv")
                return mk_act()
            if mf["phase_t"] > 34:      # nothing broke: air, or out of reach -- move on
                _enter("eye" if ph == "foot" else "adv")
                return mk_act()
            return mk_act(attack=1)
        # ph == "adv": both faces had their chance; walk into the opening.
        if mf["adv_from"] is None:
            mf["adv_from"] = (pos["x"], pos["z"])
        gained = ((pos["x"] - mf["adv_from"][0]) ** 2
                  + (pos["z"] - mf["adv_from"][1]) ** 2) ** 0.5
        mf["phase_t"] += 1
        if gained >= 0.9:
            mf["advanced"] += gained
            mf["stall"] = 0
            self.cursor_stats["mine_cycles"] = (
                self.cursor_stats.get("mine_cycles", 0) + 1)
            if mf["down_by"] is not None and mf.get("cycle_y") is not None:
                if mf["cycle_y"] - pos["y"] < 0.8:
                    mf["p_lo_bump"] = min(14.0, mf.get("p_lo_bump", 0.0) + 5.0)
                    self.cursor_stats["stair_steepened"] = (
                        self.cursor_stats.get("stair_steepened", 0) + 1)
                # A cycle that descended KEEPS its bump: one run's live entries showed
                # the first fix's reset-on-success re-failing every other cycle at the
                # stock pitch ("193 ticks, descended 1.0" -- one earned drop per
                # entry, then the 96-tick checkpoint fired before the bump was earned
                # again). The angle that worked on this terrain stays for the entry.
            if mf["down_by"] is None and self._torch_due(mf, pos):
                return mk_act()
            _enter("foot" if mf["down_by"] is not None else "close")
            return mk_act()
        if mf["phase_t"] > 8:
            mf["advanced"] += gained
            mf["stall"] += 1
            if mf["stall"] >= 2:
                self._note_failure(mf["label"])
                self.cursor_stats["mine_stall_stops"] = (
                    self.cursor_stats.get("mine_stall_stops", 0) + 1)
                # Flush the queued rest of the plan, as the ore flag does: one run
                # ran three identical doomed stair_downs back to back because the
                # diagnosis note is only read at the NEXT act turn, and the queue got
                # there first.
                head = self.queue[0] if self.queue else None
                dropped = len({idx for _, idx in list(self.queue)[1:]}) if head else 0
                if dropped:
                    self.queue.clear()
                    self.queue.append(head)
                    self.cursor_stats["stall_flush_dropped"] = (
                        self.cursor_stats.get("stall_flush_dropped", 0) + dropped)
                tail = (f" The rest of the plan ({dropped} "
                        f"entr{'y' if dropped == 1 else 'ies'}) was dropped so you can "
                        f"replan from what you actually see." if dropped else "")
                if mf["broken"] == 0:
                    _finish("STOPPED EARLY: nothing broke and the avatar did not move. "
                            "The swings are hitting nothing breakable -- the face may "
                            "be out of reach, unbreakable with this tool, or the view "
                            "mis-aimed. Reposition or look_abs before mining again."
                            + tail)
                else:
                    alt = ("pick a different heading" if mf["label"] == "stair_down"
                           else "pick a different heading, or stair_down")
                    _finish(f"STOPPED EARLY: two cycles broke blocks but the avatar "
                            f"did not move. The passage is not opening -- re-aim with "
                            f"look_abs or {alt}; do not repeat the same call.{tail}")
                return None
            _enter("foot" if mf["down_by"] is not None else "close")
            return mk_act()
        return mk_act(forward=1, jump=1 if mf["jump"] else 0)

    def _torch_due(self, mf: dict[str, Any], pos: dict[str, float]) -> bool:
        """Arm the torch phase of a level tunnel when another TORCH_EVERY blocks have
        been tunnelled underground and a torch is in the hotbar. Three runs
        carried 8+ torches through 11 stretches the ore watch reported
        as DARK and placed none; two of them were killed by mobs in those tunnels."""
        from mcu_worldmodel import macros_world as MW

        if float(pos.get("y", 99.0)) >= self.TORCH_MAX_Y:
            return False
        if mf["advanced"] - float(mf.get("torch_adv", 0.0)) < self.TORCH_EVERY:
            return False
        info = self._cur_info or {}
        slots = [sl for sl, _ in gui.find_slots(info, "torch") if 0 <= int(sl) <= 8]
        if not slots:
            return False
        mf["torch_adv"] = mf["advanced"]
        held = ((info.get("equipped_items") or {}).get("mainhand") or {}).get("type")
        back = None
        if isinstance(held, str) and held not in ("none", "air"):
            back = next((int(sl) for sl, _ in gui.find_slots(info, held)
                         if 0 <= int(sl) <= 8), None)
        yaw = math.radians(float(pos["yaw"]))
        behind = (math.floor(pos["x"] + 1.1 * math.sin(yaw)), math.floor(pos["y"]),
                  math.floor(pos["z"] - 1.1 * math.cos(yaw)))
        mf["torch"] = {"step": "select", "slot": int(slots[0]), "back": back,
                       "yaw0": float(pos["yaw"]), "t": 0,
                       "use": MW.new_use_state(behind, "torch", "below", "place", 1,
                                               f"{mf['label']} torch")}
        mf["phase"], mf["phase_t"] = "torch", 0
        return True

    def _torch_step(self, mf: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of the torch phase: select the torch, plant it on the floor of the
        cell just tunnelled through (behind the avatar), take the tool back, face the
        heading again. None when the phase is over."""
        from mcu_worldmodel import macros_world as MW

        tp = mf["torch"]
        pos = self._cur_pos or {}
        tp["t"] += 1
        if tp["t"] > 60:
            tp["step"] = "done"
        if tp["step"] == "select":
            tp["step"] = "place"
            return mk_act(**{f"hotbar_{tp['slot'] + 1}": 1})
        if tp["step"] == "place":
            status, action = MW.use_step(self, tp["use"], mk_act)
            if status == "run":
                return action
            if status == "done":
                mf["torches"] = mf.get("torches", 0) + 1
                self.cursor_stats["torches_placed"] = (
                    self.cursor_stats.get("torches_placed", 0) + 1)
            else:
                self.cursor_stats["torch_misses"] = (
                    self.cursor_stats.get("torch_misses", 0) + 1)
            tp["step"] = "restore"
            return mk_act()
        if tp["step"] == "restore":
            tp["step"] = "turn"
            if tp["back"] is not None:
                return mk_act(**{f"hotbar_{tp['back'] + 1}": 1})
            return mk_act()
        if tp["step"] == "turn":
            if pos.get("yaw") is None:
                return None
            dy = MW.norm_yaw_delta(tp["yaw0"], float(pos["yaw"]))
            if abs(dy) <= 3.0 or tp["t"] > 55:
                return None
            return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
        return None

    def _dig_tick(self, dg: dict[str, Any], mk_act) -> dict[str, Any] | None:
        """One tick of digging, ending when the target depth is reached.

        Reports what it did on every exit, and stops early when nothing is happening:
        One run ran three dig_downs for 600+ ticks that broke zero blocks and moved
        zero y, and the model repeated the call because no note ever said so --
        `_mine_cycle` had the self-report and the stall stop, `_dig` had neither."""
        if self._gui_open:
            self.cursor_stats["mine_gui_stops"] = (
                self.cursor_stats.get("mine_gui_stops", 0) + 1)
            self.memory.add_note(
                "dig_down stopped at once: a SCREEN is open, and mining ticks do "
                "nothing in the world while it is. Stow any off-inventory stacks, "
                "close the screen (close_inventory), then mine.")
            return None
        if self._ore_flag(dg):
            return None
        if not dg.get("used"):
            refusal = self._dig_water_refusal("dig_down")
            if refusal:
                self._note_failure("dig_down")
                self._flush_tail(refusal, "dig_water_refusals")
                self._keep_event_frame(self.step, "water", self._last_pov)
                self._queue_water_escape(self.queue[0][1] if self.queue else 0)
                return None
        y = (self._cur_pos or {}).get("y")
        breaks = self._log_breaks + self._other_breaks
        if dg.get("start_y") is None and y is not None:
            dg["start_y"] = float(y)
        if dg.get("base_breaks") is None:
            dg["base_breaks"] = breaks
        broken = int(breaks - dg["base_breaks"])
        used = dg.get("used", 0)
        desc = (dg["start_y"] - y) if (y is not None
                                       and dg.get("start_y") is not None) else 0.0

        def _finish(reason: str = "") -> None:
            self.memory.add_note(
                f"dig_down: broke {broken} blocks, descended {desc:.1f} in {used} "
                f"ticks." + (f" {reason}" if reason else "") + self._dark_line(dg))

        if dg["until_y"] is not None and y is not None and y <= dg["until_y"]:
            self.cursor_stats["dig_reached_depth"] = (
                self.cursor_stats.get("dig_reached_depth", 0) + 1)
            _finish("Target depth reached." + self._shaft_cap_line())
            return None
        if dg["remaining"] <= 0:
            _finish()
            return None
        if used >= 60 and broken == 0 and desc < 0.5:
            self._note_failure("dig_down")
            self._flush_tail(
                f"dig_down: broke 0 blocks, descended 0.0 in {used} ticks. STOPPED "
                f"EARLY: nothing broke and y did not change. The swings are hitting "
                f"nothing breakable -- the face may be out of reach, unbreakable with "
                f"this tool, or the view mis-aimed. Reposition, re-equip or look_abs "
                f"before digging again.", "dig_stall_stops")
            return None
        # Breaking-but-not-descending is the case the zero-break guard misses:
        # One run's one deep commit read "broke 4 blocks, descended 0.0 in 390
        # ticks" -- the whole budget burned carving a wall beside the shaft, and
        # the only report came at the end. Same windowing as the stair.
        if y is not None:
            if dg.get("win_used") is None:
                dg["win_used"], dg["win_y"] = used, float(y)
            elif used - dg["win_used"] >= 96:
                if dg["win_y"] - y < 1.0:
                    self._note_failure("dig_down")
                    self._flush_tail(
                        f"dig_down: broke {broken} blocks, descended {desc:.1f} in "
                        f"{used} ticks. STOPPED EARLY: blocks are breaking but the "
                        f"last {used - dg['win_used']} ticks gained no depth -- the "
                        f"swings are carving a wall, not the column under your feet. "
                        f"Step onto the shaft centre and aim straight down "
                        f"(look_abs pitch=90) before digging again.",
                        "dig_no_descent_stops")
                    return None
                dg["win_used"], dg["win_y"] = used, float(y)
        dg["remaining"] -= 1
        dg["used"] = used + 1
        # Stay over the column: the swings carve the block under the crosshair, and an
        # avatar standing on a cell's edge (a knockback, a diagonal approach) breaks the
        # neighbour instead and never descends -- three runs each burned
        # 96-tick windows "breaking but no depth". Walk back over the cell centre while
        # swinging, the bunker's own rule.
        keys: dict[str, int] = {}
        pos = self._cur_pos
        if pos is not None:
            if dg.get("cx") is None:
                dg["cx"], dg["cz"] = math.floor(float(pos["x"])) + 0.5, math.floor(float(pos["z"])) + 0.5
            dx = dg["cx"] - float(pos["x"])
            dz = dg["cz"] - float(pos["z"])
            if math.hypot(dx, dz) > 0.25:
                r = math.radians(float(pos["yaw"]))
                fwd = -dx * math.sin(r) + dz * math.cos(r)
                rgt = -dx * math.cos(r) - dz * math.sin(r)
                if fwd > 0.1:
                    keys["forward"] = 1
                elif fwd < -0.1:
                    keys["back"] = 1
                if rgt > 0.1:
                    keys["right"] = 1
                elif rgt < -0.1:
                    keys["left"] = 1
                if keys:
                    self.cursor_stats["dig_recentred"] = self.cursor_stats.get("dig_recentred", 0) + 1
        return mk_act(attack=1, **keys)

    def _respawned_here(self, prev: dict, pos: dict, info: dict) -> bool:
        """A respawn seen without a teleport (`near_deaths`). Measured on this engine
        (a staged fall onto the spawn, every tick written down): the health never reads
        the death -- it is 20 the tick before and 20 the tick after -- and the position
        may not move at all. What does change, in the one tick of the respawn: every
        carried stack is gone, the camera is back at exactly pitch 0, yaw 0, and the
        death screen that was up the tick before is closed. Any TWO of the three is a
        death; one alone is not (the last block placed empties an inventory, a look can
        end on 0/0, a screen closes when you close it)."""
        try:
            zero = abs(float(pos["pitch"])) < 1e-6 and abs(float(pos["yaw"])) < 1e-6
            turned = (abs(float(prev["pitch"]) - float(pos["pitch"])) > 0.5
                      or abs(float(prev["yaw"]) - float(pos["yaw"])) > 0.5)
        except (KeyError, TypeError, ValueError):
            zero = turned = False
        pose_reset = zero and turned
        wiped = (sum(self._cur_inv.values()) > 0
                 and sum(inventory_counts(info).values()) == 0)
        screen_gone = bool(self._gui_open) and not bool(info.get("isGuiOpen", False))
        return int(pose_reset) + int(wiped) + int(screen_gone) >= 2

    def _kills(self) -> dict[str, float]:
        """The kill_entity bucket of the last observe: mob -> count, kills only."""
        return {str(k): float(v) for k, v in
                ((self.ledger._prev or {}).get("kill_entity") or {}).items()
                if _num(v) and float(v) > 0}

    def stat_now(self, event: str, obj: str) -> float:
        """The cumulative statistic as of the last observe (the ledger's copy of the
        last info). Macro ticks compare it against a baseline to verify a craft, a
        placement or a smelt output without trusting the frame."""
        from mcu_worldmodel.milestones import _stat
        return _stat(self.ledger._prev or {}, event, obj)

    def _act_turn(self, info: dict) -> None:

        self.turns["act"] += 1
        # Stall detection: ground truth is "moving" when a milestone fired or any
        # inventory count changed since the last act turn.
        marker = (len(self.ledger.achieved), tuple(sorted(self._cur_inv.items())))
        if marker != self._progress_marker:
            self._progress_marker = marker
            self._stall_turns = 0
            self._proc_fails.clear()
            self._plan_repeat = 0
            self._plan_sig = None
        else:
            self._stall_turns += 1
        if self.memory_mode == "direct":
            # No feedback channel: the harness notes the last batch raised are logged
            # for the operator and dropped, never served to the model.
            dropped = self.memory.take_notes()
            if dropped:
                logger.info(f"[agent] direct: {len(dropped)} harness note(s) not "
                            f"served: {dropped[:3]}")
        if self.episodes:
            # An entry still open here did not finish (its queue was cleared without
            # a log section); closed as flushed at this step, so the ticks a turn's
            # failure costs are not written to it.
            self.episodes.flush(self.step)
        frame = self._save_frame(info, self.step)
        sheet = self._event_sheet(info)
        prompt = self._turn_prompt(info, sheet=sheet is not None)
        self._turn_outcomes = []
        # The current view, plus the sheet of this turn's event frames when there
        # were any (never for the direct arm: its only past is the present).
        images = [self.memory.root / frame] if frame else []
        if sheet is not None:
            images.append(sheet)

        before = self.memory.snapshot_harness_files()
        if self.memory_mode == "direct":
            self._direct_act_turn(prompt, images, before, info)
            return
        result = {"ok": False}
        for attempt in range(self.analyzer_retries):
            result = self.codex.run(prompt if attempt == 0 else RETRY_NUDGE, images)
            if result.get("ok"):
                break
            logger.warning(f"[agent] act turn attempt {attempt+1} produced no actions.json")
            # A contentless failure is usually the environment (binary swapped out
            # mid-upgrade, auth blip, quota gate), not the model: retrying hot once burned
            # a run's whole 4,000-call ceiling in minutes. Escalating waits
            # cap the burn while an outage lasts; 600 s step_timeout dwarfs the 62 s max.
            if attempt + 1 < self.analyzer_retries:
                RETRY_SLEEP(min(30, 2 ** (attempt + 1)))
        tampered = self.memory.assert_harness_files_intact(before)
        for t in tampered:
            self.memory.add_note(f"harness-owned file was modified and is not yours to "
                                 f"write: {t}")

        briefing, plan_text = self.codex.split_briefing(result.get("message", ""))
        if self.expect:
            m = re.search(r"^\s*EXPECT:\s*(.+?)\s*$", result.get("message", "") or "", re.M)
            self._last_expect = m.group(1)[:300] if m else None
            self.cursor_stats["expect_lines"] = (
                self.cursor_stats.get("expect_lines", 0) + (1 if m else 0))
        self.memory.set_plan(plan_text, briefing)
        if self.episodes:
            self.episodes.plan(self.codex.calls, briefing, plan_text)
        self.plan = [ln.strip("-* ").strip()
                     for ln in plan_text.splitlines() if ln.strip()][:5]
        self._update_plan_streak(plan_text)

        self.memory.sweep_foreign()

        if not result.get("ok"):
            self.turns["act_failed"] += 1
            self.memory.add_note("no valid actions.json this turn; one no-op was executed")
            return
        plan = parse_actions(result["actions_json"], entry_cap=self.entry_cap,
                            repeat_cap=self.repeat_cap, step_cap=self.step_cap,
                            allow_optional=self.extended_actions, info=info,
                            cursor=self.cursor.copy(), **self._own_kwargs(info))
        for n in plan.notes:
            self.memory.add_note(n)
        self._enqueue(plan)

    def _enqueue(self, plan) -> None:
        """Rebuild the (action, entry index) pairing that parse_actions flattened away.

        The governor's veto is ALL-OR-NOTHING on the plan: dropping one entry out
        of a composite (the aim before a mine) corrupts the plan instead of saving
        its steps, and entry-wise refusal storms burned 2 model calls per sim step
        in one run. A plan runs untouched unless EVERY entry is a known-null at this
        cell; then the whole plan is dropped, one no-op is queued so the world
        still advances, and a single note names what was refused."""
        from mcu_worldmodel.procedures import noop

        self._plan_entries = list(plan.entries)
        # A reflex's "REFLEX_EVERY ticks ago" starts with this plan: the sample of the
        # previous plan's last check is damage the model has already read and answered
        # (one life's burst rule fired on it at the first tick of a new plan, and threw
        # the plan away before it had moved).
        self._own_reflex_prev = None
        here = cell_of(self._cur_pos)
        verdicts = ([self.governor.check(entry.get("procedure", "raw"), here, self.step)
                     for entry in plan.entries] if self.reflexes
                    else [None] * len(plan.entries))
        if plan.entries and all(v is not None for v in verdicts):
            labels = ", ".join(e.get("procedure", "raw") for e in plan.entries)
            self.memory.add_note(
                f"governor: REFUSED this whole plan ({labels}) -- every entry in it "
                f"has already finished repeatedly at this spot changing nothing. One "
                f"no-op ran instead. Move, change tools, or work a different target "
                f"before re-proposing any of these here.")
            self.cursor_stats["governor_plan_drops"] = (
                self.cursor_stats.get("governor_plan_drops", 0) + 1)
            self._plan_entries = []
            self.queue.append((noop(), 0))
            return
        stall = (self.governor.check_plan(plan.entries, here, self.step, self._gui_open)
                 if self.reflexes else "")
        if stall:
            hint = self._stall_hint()
            self.memory.add_note(stall + ((" " + hint) if hint else ""))
            self.cursor_stats["governor_plan_stalls"] = (
                self.cursor_stats.get("governor_plan_stalls", 0) + 1)
            self._plan_entries = []
            self.queue.append((noop(), 0))
            return
        pairs: list[tuple[dict[str, Any], int]] = []
        cursor = 0
        for i, entry in enumerate(plan.entries):
            n = (entry.get("items", entry["steps"]) if "procedure" in entry
                 else entry["repeat"])
            for _ in range(n):
                if cursor < len(plan.steps):
                    pairs.append((plan.steps[cursor], i))
                    cursor += 1
        self.queue.extend(pairs)
        self._entry_index = None

    # -- the direct arm's turn --------------------------------------------

    def _direct_act_turn(self, prompt: str, images: list[Path],
                         before: dict[str, int], info: dict) -> None:
        """One act turn on the no-memory contract: no files -- the reply carries the
        actions JSON; a reply without one is retried with a nudge, then costs the turn."""
        message, actions_json = "", None
        for attempt in range(self.analyzer_retries):
            p = prompt if attempt == 0 else prompt + "\n\n" + DIRECT_RETRY_LINE
            result = self.codex.run(p, images, expect_actions=False)
            message = result.get("message") or ""
            actions_json = extract_actions_block(message)
            if actions_json:
                break
            self.direct_stats["reply_parse_failures"] += 1
            if not message and attempt + 1 < self.analyzer_retries:
                # Same environment-outage guard as the file-based act turn: an EMPTY
                # reply is the backend failing, not the model misformatting.
                RETRY_SLEEP(min(30, 2 ** (attempt + 1)))
            logger.warning(f"[agent] act turn attempt {attempt+1} carried no actions "
                           f"JSON in the reply")
        for t in self.memory.assert_harness_files_intact(before):
            self.memory.add_note(f"harness-owned file was modified and is not yours to "
                                 f"write: {t}")
        self.memory.sweep_foreign()
        if not actions_json:
            self.turns["act_failed"] += 1
            self.memory.add_note("your reply carried no valid actions JSON this turn; "
                                 "one no-op was executed")
            return
        _, plan_text = self.codex.split_briefing(message)
        self.plan = [ln.strip("-* ").strip()
                     for ln in plan_text.splitlines() if ln.strip()][:5]
        self._update_plan_streak(plan_text)
        plan = parse_actions(actions_json, entry_cap=self.entry_cap,
                            repeat_cap=self.repeat_cap, step_cap=self.step_cap,
                            allow_optional=self.extended_actions, info=info,
                            cursor=self.cursor.copy(), **self._own_kwargs(info))
        for n in plan.notes:
            self.memory.add_note(n)
        self._enqueue(plan)

    def _update_plan_streak(self, plan_text: str) -> None:
        """Near-identical successive plans, counted as a fact. Token-set Jaccard at
        0.8: rephrasings of the same plan land ~0.85-1.0, an actually-new plan
        ~0.2-0.5. The streak resets whenever ground truth moves (_act_turn's
        progress marker), so the notice can only describe a loop that is also
        producing nothing."""
        import re as _re

        sig = frozenset(w for w in _re.findall(r"[a-z_]+", plan_text.lower())
                        if len(w) > 2)
        prev, self._plan_sig = self._plan_sig, sig
        if prev and sig and len(sig & prev) / max(1, len(sig | prev)) >= 0.8:
            if self._plan_repeat == 0:
                self._plan_repeat_since = self.step
            self._plan_repeat += 1
        else:
            self._plan_repeat = 0

    def _expect_block(self) -> str:
        """[EXPECTED] (the model's own EXPECT line from last turn) against [OBSERVED]
        (what the harness recorded for that plan's entries). VISTA's protocol, in
        harness form: the mismatch is stated, not re-derived from the log."""
        if not self._turn_outcomes and self._last_expect is None:
            return ""                       # the first turn: nothing to compare yet
        exp = self._last_expect or "(your last briefing had no `EXPECT:` line)"
        obs = []
        for r in self._turn_outcomes[-6:]:
            bits = [f"moved {r['moved']:.1f}"]
            if abs(r["descended"]) >= 0.5:
                bits.append(f"descended {r['descended']:.1f}")
            if r["inv"]:
                bits.append(f"inv {r['inv']}")
            if r["events"]:
                bits.append("events " + "; ".join(r["events"][:3]))
            if r["note"]:
                bits.append(f"note: {r['note'][:100]}")
            if r.get("frame"):
                bits.append(f"frame: {r['frame']}")
            obs.append(f"  {r['label']}: " + ", ".join(bits))
        observed = "\n".join(obs) if obs else "  (no entry of that plan finished)"
        return (f"[EXPECTED] {exp}\n[OBSERVED] by the harness for that plan (each entry "
                f"with the frame it started from):\n{observed}\n"
                "Begin your briefing with one line `OBSERVED vs EXPECTED: ...` -- do they "
                "match, what differs, and what the VIEW shows that differs (the attached "
                "frame against the entry's frame: one visible change, or that nothing "
                "visible changed); end it with `EXPECT: ...` for this plan, including what "
                "the view should show.")

    WORKING_CAP = 1500

    def _working_block(self) -> str:
        """`mine/working.md`, the model's own continuation note, put in front of it every
        turn (VISTA's WORKING.md: the compaction checkpoint it must write before its
        context is cut). Own arms only; absent when the file is."""
        if not getattr(self, "own", False):
            return ""
        p = self.memory.root / "mine" / "working.md"
        try:
            text = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""
        if not text:
            return ""
        if len(text) > self.WORKING_CAP:
            text = text[:self.WORKING_CAP].rstrip() + f"\n  [... {len(text) - self.WORKING_CAP} more chars: Read mine/working.md]"
        return "[WORKING] mine/working.md -- your continuation note, as you last wrote it:\n" + text

    def _stall_hint(self) -> str:
        """Where the map says a stalled plan could go: the placed table/furnace with
        a walked route, else the farthest walked cell within 12 blocks."""
        pos = self._cur_pos
        here = cell_of(pos)
        if here is None:
            return ""
        from mcu_worldmodel.grid import cell_of as gcell, xz_dist
        hc = gcell(pos)
        if hc is None:
            return ""
        for item, rec in sorted(self.grid.placed.items()):
            cell = rec.get("cell")
            if cell and xz_dist(hc, tuple(cell)) > 2.0:
                rt = self.grid.route(pos, tuple(cell))
                if rt:
                    return (f"The map: your {item} is {xz_dist(hc, tuple(cell)):.0f} blocks "
                            f"away with a walked route of {len(rt)} cells -- "
                            f"`use_at` on its cell opens it.")
        far = None
        for c in self.grid.walked:
            d = xz_dist(hc, c)
            if 5.0 <= d <= 12.0 and abs(c[1] - hc[1]) <= 3 and (far is None or d > far[1]):
                far = (c, d)
        if far:
            c = far[0]
            return (f"The map: you walked cell {c}, {far[1]:.0f} blocks from here -- "
                    f"`go_to(x={c[0] + 0.5}, z={c[2] + 0.5}, within=1)` is a known walk.")
        return ""

    def _recent_block(self) -> str:
        """The last six finished entries as one objective line each (the harness's
        own record, so the turn does not start with a grep of the log)."""
        if not self._recent_outcomes:
            return ""
        lines = []
        for r in self._recent_outcomes:
            bits = [f"moved {r['moved']:.1f}"]
            if abs(r["descended"]) >= 0.5:
                bits.append(f"descended {r['descended']:.1f}")
            if r["inv"]:
                bits.append(f"inv {r['inv']}")
            if r["events"]:
                bits.append("events " + "; ".join(r["events"][:3]))
            if r["note"]:
                bits.append(f"note: {r['note']}")
            lines.append(f"- step {r['step']} {r['label']}: " + ", ".join(bits))
        return "[RECENT] the last entries that finished, from the harness's record:\n" + "\n".join(lines)

    # -- the model's own procedures (`--own`, mcu_worldmodel/own.py) ----------------

    def _scan_own(self) -> None:
        if self.own:
            self._own_procs = (_own.scan(self.memory.root, set(_P.REGISTRY), loops=True)
                               if self.own_live else
                               _own.scan(self.memory.root, set(_P.REGISTRY)))
            if self._own_record is None:
                # Once per life: the record `mine/` starts with, and this life's
                # number in it.
                self._own_record = _own.load_record(self.memory.root)
                self._own_life_no = _own.record_life(self._own_record)

    def _own_scorecard(self, entry: dict[str, Any]) -> None:
        """An own procedure's entry just ended: one `[OWN <name>]` note with what it did
        (ticks, sword hits, kills, health, deaths -- the ledger's numbers over the entry),
        and the same row appended to mine/scripts_record.json, which travels with the
        script to later lives and shows in the [OWN] index. Measurement, not a skill."""
        if not (self.own and isinstance(entry, dict) and entry.get("own")):
            return
        t0 = self._entry_tally0
        if not t0:
            return
        name = str(entry.get("procedure") or "")
        row = {"life": self._own_life_no, "step": int(t0["step"]),
               "ticks": max(0, int(self.step) - int(t0["step"])),
               "hits": int(round(self._tally["hits"] - float(t0["hits"]))),
               "kills": int(round(self._tally["kills"] - float(t0["kills"]))),
               "deaths": int(self.cursor_stats.get("deaths", 0)) - int(t0["deaths"]),
               "health": [t0["health"], self._last_health]}
        if self._own_record is None:
            self._own_record = {}
        self._own_record.setdefault(name, []).append(row)
        _own.save_record(self.memory.root, self._own_record)
        self.memory.add_note(f"[OWN {name}] this entry: {_own.scorecard(row)}.")
        self._entry_tally0 = None

    def _dying_during(self) -> str:
        """The tail of a YOU DIED note: the plan entry that was running."""
        idx = self._entry_index
        if idx is None or not (0 <= idx < len(self._plan_entries)):
            return ""
        desc = describe_entry(self._plan_entries[idx]).replace("[ACTION] ", "", 1)
        desc = desc.split(" -> ", 1)[0].strip()
        return f" You were running `{desc}` when it happened."

    def _own_state(self, info: dict) -> dict[str, Any]:
        """What an own script gets on stdin: the same numbers the turn message shows."""
        from mcu_worldmodel.episodes import _hotbar
        pos = location(info)

        def _f(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
        return {
            "step": self.step, "max_steps": self.max_steps,
            "pos": ({k: _f(pos.get(k)) for k in ("x", "y", "z", "pitch", "yaw")}
                    if pos else None),
            "health": _f(info.get("health")), "food": _f(info.get("food_level")),
            "inventory": inventory_counts(info), "hotbar": _hotbar(info),
            "mainhand": ((info.get("equipped_items") or {}).get("mainhand") or {}).get("type"),
            "gui_open": bool(info.get("isGuiOpen", False)),
            "dimension": getattr(self, "_dimension", None),
        }

    def _own_kwargs(self, info: dict) -> dict[str, Any]:
        """parse_actions' own-procedure hooks; empty without `--own` or scripts."""
        if not self.own:
            return {}
        self._scan_own()
        if not self._own_procs:
            return {}
        state = self._own_state(info)

        def _run(name: str, args: dict[str, Any]):
            proc = self._own_procs.get(name)
            if proc is None:
                return None, "no such script"
            out, err = _own.run(proc, self.memory.root, state, args)
            key = "own_calls" if err is None else "own_failures"
            self.cursor_stats[key] = self.cursor_stats.get(key, 0) + 1
            if err is None:
                self._own_calls[name] = self._own_calls.get(name, 0) + 1
            return out, err
        loops = {n for n, p in self._own_procs.items() if p.loop and not p.error}
        return {"own_expand": _run, "own_names": set(self._own_procs),
                **({"own_loops": loops} if loops else {})}

    # -- closed-loop own procedures and the live view (`own_live`, own.py) ----------

    def _entry_is_loop(self, idx) -> bool:
        """True when plan entry `idx` is one of the model's closed loops."""
        return (isinstance(idx, int) and 0 <= idx < len(self._plan_entries)
                and bool(self._plan_entries[idx].get("loop")))

    def _live_frame(self, info: dict) -> str | None:
        """Write the current view where an own script can read it; its path, or None.
        The PNG is at the engine's render size (an episode keeps the smaller copy: at
        320x180 an enderman's eyes were a 5-pixel pair and every rangefinder three lives
        wrote failed on it); `_live_size` says what was written. In the attach dir
        beside the workspace: overwritten at every call, never listed, never carried."""
        pov = self._last_pov if self._last_pov is not None else info.get("pov")
        data = self._encode_pov(pov, self.step, native=True)
        if data is None:
            return None
        try:
            h, w = np.asarray(pov).shape[:2]
            self._live_size = (int(w), int(h))
        except Exception:
            pass
        path = self.memory.attach_dir / _own.LIVE_FRAME
        try:
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        except OSError as e:
            logger.warning(f"[agent] could not write the live frame at step {self.step}: {e}")
            return None
        return str(path)

    def _loop_note(self, st: dict[str, Any], name: str, text: str) -> None:
        """One `[LOOP <name>]` line, at most LOOP_NOTES per entry, never twice in a row."""
        text = str(text).strip()
        if not text or text == st.get("last_note"):
            return
        st["last_note"] = text
        st["notes"] = int(st.get("notes", 0)) + 1
        if st["notes"] <= _own.LOOP_NOTES:
            self.memory.add_note(f"[LOOP {name}] {text}"
                                 + (" (further notes of this entry are dropped)"
                                    if st["notes"] == _own.LOOP_NOTES else ""))

    def _own_loop_step(self, st: dict[str, Any], idx: int, info: dict) -> bool:
        """The loop marker is at the head of the queue: run the script on this tick's
        state and put what it returns in front of the marker, under the same entry.
        True: there is something to run and the marker stays behind it. False: the loop
        is over (the caller pops the marker); one `[LOOP <name>] ended` line says why."""
        name = str(st.get("name"))
        if "start" not in st:
            self._scan_own()
            try:
                hp0 = float(info.get("health"))
            except (TypeError, ValueError):
                hp0 = 0.0
            st.update(start=self.step, calls=0, memo={}, notes=0, health_start=hp0)
            self._own_calls[name] = self._own_calls.get(name, 0) + 1
            self.cursor_stats["own_calls"] = self.cursor_stats.get("own_calls", 0) + 1
            self._own_loops.setdefault(name, {"entries": 0, "calls": 0, "ticks": 0})["entries"] += 1
        rec = self._own_loops.setdefault(name, {"entries": 0, "calls": 0, "ticks": 0})
        used = self.step - int(st["start"])
        left = int(st["budget"]) - used
        # counted at every arrival, so a loop a milestone or a reflex drops mid-way has
        # its ticks on the record up to its last call
        rec["ticks"] += used - int(st.get("counted", 0))
        st["counted"] = used

        def end(why: str) -> bool:
            self.memory.add_note(f"[LOOP {name}] ended: {why} ({st['calls']} call(s), "
                                 f"{used} of {st['budget']} ticks).")
            return False

        if st.get("end"):
            return end(st["end"])
        if left <= 0:
            return end("its budget is spent")
        proc = self._own_procs.get(name)
        if proc is None or proc.error or not proc.loop:
            return end(f"mine/procedures/{name}.py is gone or no longer a loop")
        # What the last call returned finished without a tick (a look_abs already within
        # its 2 degrees, a go_to already there) and the marker is back on the tick of
        # that call. The script would get the same state and return the same thing, and
        # the budget counts ticks, so nothing would ever end it: `next_action` never
        # returned, the green side timed the step out and the worker thread kept the
        # purple lock for the rest of the life. One idle tick first, so every call
        # costs at least one and the budget ends the entry.
        if st.get("called_at") == self.step:
            if not st.get("idled"):
                st["idled"] = True
                self.memory.add_note(f"[LOOP {name}] call {int(st['calls']) - 1} returned only "
                                     f"steps that were already done, so no tick ran; an idle "
                                     f"tick runs before the next call each time this happens.")
            self.cursor_stats["own_loop_idle"] = self.cursor_stats.get("own_loop_idle", 0) + 1
            self.queue.appendleft((_P.noop(), idx))
            return True
        st["called_at"] = self.step
        state = self._own_state(info)
        frame = self._last_pov
        live = self._live_frame(info)
        state.update(
            frame=live, frame_size=list(self._live_size),
            lava_frac=(round(float(vision.lava_fraction(np.asarray(frame))), 4)
                       if frame is not None else 0.0),
            fire_frac=(round(float(vision.fire_fraction(np.asarray(frame))), 4)
                       if frame is not None else 0.0),
            call=int(st["calls"]), ticks=used, budget=left,
            health_start=st["health_start"], memo=st["memo"])
        # The first call of an entry pays a cold Python start (two lives lost a turn
        # each to one that took over 10 s on a loaded node); the world waits meanwhile,
        # so the longer limit costs no tick.
        out, err = _own.run(proc, self.memory.root, state, dict(st.get("args") or {}),
                            timeout=(_own.LOOP_COLD_TIMEOUT_S if int(st["calls"]) == 0
                                     else _own.LOOP_TIMEOUT_S))
        k = int(st["calls"])
        st["calls"] = k + 1
        rec["calls"] += 1
        self.cursor_stats["own_loop_calls"] = self.cursor_stats.get("own_loop_calls", 0) + 1
        res = None
        if err is None:
            res, err = _own.parse_loop(out or "")
        if err is not None:
            self.cursor_stats["own_failures"] = self.cursor_stats.get("own_failures", 0) + 1
            return end(f"call {k} FAILED, nothing ran: {err}")
        if res["memo"] is not None:
            st["memo"] = res["memo"]
        if res["note"]:
            self._loop_note(st, name, res["note"])
        plan = parse_actions(json.dumps({"actions": res["actions"]}),
                             entry_cap=_own.LOOP_ENTRY_CAP, repeat_cap=self.repeat_cap,
                             step_cap=min(_own.LOOP_CALL_TICKS, left),
                             allow_optional=self.extended_actions, info=info,
                             cursor=self.cursor.copy(), own_names=set(self._own_procs),
                             _depth=1)
        for n in plan.notes:
            self._loop_note(st, name, n)
        if not plan.steps:
            return end("it was done" if not res["again"]
                       else f"call {k} returned nothing to run")
        if not res["again"]:
            st["end"] = "it was done"
        self.queue.extendleft(reversed([(s, idx) for s in plan.steps]))
        return True

    # -- the model's own reflexes (`--own-reflexes`, mcu_worldmodel/own.py) ----------

    def _scan_own_reflexes(self) -> None:
        """mine/reflexes/*.py, and the switched-off ones back on when their file changed."""
        self._own_reflexes = _own.scan_reflexes(self.memory.root)
        for name, (why, mtime) in list(self._own_reflex_off.items()):
            rx = self._own_reflexes.get(name)
            if rx is None or rx.mtime != mtime:
                del self._own_reflex_off[name]
                self._own_reflex_fails.pop(name, None)

    def _own_reflex_state(self, info: dict) -> dict[str, Any]:
        """The procedure state plus what a reflex is for: the lower-view lava share now,
        the numbers REFLEX_EVERY ticks ago, the entry running, the runner's own reflex."""
        st = self._own_state(info)
        frame = self._last_pov
        st["lava_frac"] = (round(float(vision.lava_fraction(np.asarray(frame))), 4)
                           if frame is not None else 0.0)
        # Flames (a fire block, the burning overlay) share lava's orange; their own,
        # brighter band lets a reflex tell a lit portal or a burn from a pool.
        st["fire_frac"] = (round(float(vision.fire_fraction(np.asarray(frame))), 4)
                           if frame is not None else 0.0)
        # The health lost over `_hp_hist`'s 100 ticks, every drop counted and no healing
        # taken off (a fed avatar heals faster than fire burns, so the net can read 0
        # while it burns): with flames on screen it is what tells a burn from lava ahead.
        hist = [h for _, h in self._hp_hist]
        st["hurt_100"] = round(sum(max(0.0, a - b) for a, b in zip(hist, hist[1:])), 2)
        # Head under lava: the view is lava's fog, which reads as neither of the two.
        st["in_lava"] = bool(frame is not None and vision.lava_submerged(np.asarray(frame))
                             >= vision.LAVA_SUBMERGED_MIN)
        prev = self._own_reflex_prev
        st["health_prev"] = prev["health"] if prev else st["health"]
        st["food_prev"] = prev.get("food", st["food"]) if prev else st["food"]
        st["pos_prev"] = prev["pos"] if prev else st["pos"]
        idx = self._entry_index
        entry = (self._plan_entries[idx]
                 if idx is not None and 0 <= idx < len(self._plan_entries) else None)
        st["entry"] = (entry.get("procedure", "raw") if isinstance(entry, dict) else None)
        # Inside one of the model's own procedures the entry is the script's name; the
        # atom it is running now is found from how many of its items are still queued
        # (the scripted strip of one check walked into a lava floor with its lava
        # reflex keyed on `entry`, which never read "watch" or "look_abs" there).
        st["atom"] = st["entry"]
        if isinstance(entry, dict) and entry.get("atoms"):
            left = sum(1 for _, j in self.queue if j == idx)
            done = max(0, int(entry.get("items", 0)) - left)
            for atom, items in entry["atoms"]:
                if done < int(items):
                    st["atom"] = atom
                    break
                done -= int(items)
        st["queue_len"] = len(self.queue)
        st["runner_reflex"] = self._reflex.get("kind", "turn") if self._reflex else None
        if self.own_live:
            st["frame"] = self._live_frame(info)
            st["frame_size"] = list(self._live_size)
        return st

    def _own_reflex_tick(self, step: int, info: dict) -> None:
        """Every REFLEX_EVERY ticks: run the model's reflex scripts on the live state;
        the first that fires stops the plan (if it says so), leaves its note, and queues
        its plan through the ordinary parser and governor. Quiet inside a screen and
        while a runner reflex (an escape) is in progress; a script that fails
        REFLEX_FAILS times in a row is off until the file changes."""
        if step % _own.REFLEX_EVERY or self._gui_open or self._cur_pos is None:
            return
        if self._reflex is not None:
            return
        self._scan_own_reflexes()
        live = [(n, rx) for n, rx in sorted(self._own_reflexes.items())
                if not rx.error and n not in self._own_reflex_off][:_own.REFLEX_MAX]
        if not live:
            self._own_reflex_prev = None
            return
        state = self._own_reflex_state(info)
        self._own_reflex_prev = {"health": state["health"], "food": state["food"],
                                 "pos": state["pos"]}
        for name, rx in live:
            if step - self._own_reflex_last.get(name, -10**9) < _own.REFLEX_COOLDOWN:
                continue
            res, err = _own.run_reflex(rx, self.memory.root, state)
            self.cursor_stats["own_reflex_runs"] = self.cursor_stats.get("own_reflex_runs", 0) + 1
            if err is not None:
                n = self._own_reflex_fails.get(name, 0) + 1
                self._own_reflex_fails[name] = n
                self.cursor_stats["own_reflex_failures"] = (
                    self.cursor_stats.get("own_reflex_failures", 0) + 1)
                if n >= _own.REFLEX_FAILS:
                    self._own_reflex_off[name] = (err, rx.mtime)
                    self.memory.add_note(
                        f"[REFLEX {name}] switched OFF after {n} failures in a row ({err}); "
                        f"edit mine/reflexes/{name}.py to run it again.")
                continue
            self._own_reflex_fails.pop(name, None)
            if res is None:
                continue
            self._own_reflex_last[name] = step
            self._own_reflex_fires[name] = self._own_reflex_fires.get(name, 0) + 1
            self.cursor_stats["own_reflex_fires"] = self.cursor_stats.get("own_reflex_fires", 0) + 1
            self._own_reflex_fire(name, res, info)
            return

    def _own_reflex_fire(self, name: str, res: dict[str, Any], info: dict) -> None:
        stop = bool(res.get("stop")) or bool(res.get("actions"))
        dropped = len(self.queue)
        if stop:
            self.queue.clear()
        note = str(res.get("note") or "fired").strip().splitlines()[0][:400]
        self.memory.add_note(
            f"[REFLEX {name}] {note}"
            + (f" -- the runner dropped the rest of your plan ({dropped} action(s))"
               if stop and dropped else "")
            + (" and is running the reflex's own actions" if res.get("actions") else "") + ".")
        acts = res.get("actions")
        if not acts:
            return
        plan = parse_actions(json.dumps({"actions": acts}), entry_cap=_own.REFLEX_ENTRY_CAP,
                             repeat_cap=self.repeat_cap, step_cap=_own.REFLEX_STEP_CAP,
                             allow_optional=self.extended_actions, info=info,
                             cursor=self.cursor.copy(), own_names=set(self._own_procs))
        for n in plan.notes:
            self.memory.add_note(f"[REFLEX {name}] {n}")
        if plan.steps:
            self._enqueue(plan)

    def _turn_prompt(self, info: dict, sheet: bool = False) -> str:
        """The per-turn user message. The standing instructions live in AGENTS.md; this
        carries only what changed -- which is what makes a resumed thread cheap."""
        inv = inventory_counts(info)
        inv_line = ", ".join(f"{k}x{v}" for k, v in sorted(inv.items())[:24]) or "empty"
        free = _empty_slot_count(info)
        free_txt = "?" if free is None else str(free)
        pos = location(info)
        pos_line = (f"pos=({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}) "
                    f"pitch={pos['pitch']:.0f} yaw={norm_yaw(pos['yaw']):.0f}") if pos else "unknown"
        # The shared half: the PRESENT. Every memory mode gets the same rendered state,
        # stall counter included -- what differs below is only how the PAST is served
        # (compiled model + graph view vs "grep the log" vs nothing at all for the
        # direct arm), which is the claim-M axis and nothing else.
        budget_part = (
            f"Step {self.step}/{self.max_steps} -- "
            f"{max(0, self.max_steps - self.step)} steps remain. "
            f"{self.ledger.progress_line()}\n"
        )
        # Shown to the planner: goal_furnace burned 2,400 steps (one run) while nothing
        # said out loud that nothing had changed. Identical in the memory arms.
        stall_part = (
            f"Act turns since anything verifiably changed (milestone or inventory): "
            f"{self._stall_turns}.\n\n"
        )
        state_part = (
            (f"Milestones:\n{self.ledger.progress_block()}\n\n" if self.ledger.cfg else "")
            + f"[STATE] {pos_line}\n"
            f"Vitals: {vitals(info)}\n"
            f"Inventory ({free_txt} slots free): {inv_line}\n"
            # The hotbar separately from the inventory: selecting a tool needs the slot
            # NUMBER, and "I have a pickaxe somewhere" does not tell the agent what to press.
            f"Hotbar: {hotbar_line(info)}\n"
            f"Held: {held_line(info)}\n"
            f"Nearby entities: {nearby_mobs(info)}\n"
            f"GUI open: {bool(info.get('isGuiOpen', False))}\n"
            # Where the cursor is, held by the harness. This is what removes the need for
            # per-turn cursor bookkeeping and what makes an absolute cursor address
            # meaningful -- see cursor.py.
            f"{self.cursor.line(inv)}\n"
            f"{(self._grid_line() + chr(10)) if self._grid_line() else ''}\n"
        )
        head = budget_part + stall_part + state_part
        if self.memory_mode != "direct":
            recent = self._recent_block()
            map_block = self.grid.summary(pos, self.step)
            head += ((recent + "\n\n") if recent else "") + (
                "[MAP] what the runner knows for certain from this life's own positions "
                "and events (exact unless marked a sighting):\n" + map_block + "\n\n"
                if map_block else "")
            if self.own:
                self._scan_own()
                own_block = _own.index_block(self._own_procs, self._own_calls,
                                             self._own_record, self._own_life_no)
                if self.own_reflexes:
                    self._scan_own_reflexes()
                    rx_block = _own.reflex_block(self._own_reflexes, self._own_reflex_fires,
                                                 {k: v[0] for k, v in self._own_reflex_off.items()})
                    own_block = "\n".join(b for b in (own_block, rx_block) if b)
                head += (own_block + "\n\n") if own_block else ""
            if sheet:
                labels = ", ".join(getattr(self, "_sheet_labels", []) or [])
                head += ("Attached second image: a 2x2 sheet -- top-left the current view, "
                         "then the frames at this turn's events"
                         + (f" ({labels})" if labels else "") + ".\n\n")
        if self.memory_mode == "direct":
            return head + (
                "The current view is attached.\n"
                "Reply with your briefing, [PLAN], then ONE fenced ```json block "
                '{"actions": [...]} -- the LAST fenced JSON block is executed.'
            )
        if self.memory_mode == "mfm":
            # The retrieval block (mfm arm, `--retrieval` only): between the present
            # and the pointer to the log, absent when there is nothing to recall.
            recall = self.episodes.recall(info) if self.episodes else ""
            expect = self._expect_block() if self.expect else ""
            working = self._working_block()
            return head + (expect + "\n\n" if expect else "") + (working + "\n\n" if working else "") + (recall + "\n\n" if recall else "") + (
                "Your memory is `./logs.txt` -- grep it for anything before this call: "
                "earlier plans, [STATE] history, [EVENT] lines, your own notes.\n"
                + "`./tools/episodes.py` queries the same history as episodes, by step, "
                  "place, tag or text, with their frames; `view_image` opens a frame.\n"
                + "The current view is attached.\n"
                "Write ./actions.json."
            )
        raise ValueError(f"no turn prompt for memory_mode={self.memory_mode!r}")

    def _log_entry_done(self, index: int) -> None:
        """Write one log section for a plan entry that has just finished executing.

        `moved` is measured from where the entry started to where it ended, so the number
        answers the question the agent actually asks of it: did that do anything? A
        repeated `moved=0.00` is the signature of being blocked by terrain, and it is only
        informative if the two positions are genuinely from before and after.
        """
        if not (0 <= index < len(self._plan_entries)):
            return
        self._own_scorecard(self._plan_entries[index])
        self.action_num += 1
        first_note = (self.memory._pending_notes[0][:150] if self.memory._pending_notes
                      else "")
        if self.episodes:
            # Closed before the section is written, with the notes it is about to carry.
            self.episodes.close_entry(events=list(self._pending_events),
                                      notes=list(self.memory._pending_notes))
        # The frame the entry started from, for [OBSERVED] (VISTA's observe step made
        # concrete: a mismatch has a one-step look). Several runs opened an earlier episode's
        # frame 32 times in 850k steps; the compare line never pointed at one.
        ep_frame = None
        if self.episodes:
            closed = getattr(self.episodes.store, "closed", None)
            if closed:
                ep_frame = closed[-1].get("image") or None
        # The direct arm has no log: write_action no-ops there, and the batch's facts
        # are not served back to the model at all. The governor tail below still runs
        # in every arm -- enforcement is substrate, not memory.
        self.memory.write_action(
            action_num=self.action_num, step=self.step,
            entry_desc=describe_entry(self._plan_entries[index]),
            pos=self._cur_pos, prev_pos=self._entry_start_pos,
            frame=self._last_frame,
            plan_step=f"{index + 1}/{len(self._plan_entries)}",
            verified=f"{len(self.ledger.achieved)}/{len(self.ledger.cfg)} verified",
            events=self._pending_events,
            # `write_action` has always accepted these two and nothing ever passed them,
            # so `logs.txt` carried no [INV] and no [GUI] line at all -- 0 of each across
            # 194 logged entries in the diamond run -- while the prompt told the agent
            # that [INV] was the ground truth for what a click did. Grepping the log for
            # whether a click landed was therefore impossible, so every GUI step had to be
            # re-tested by hand and the result parked in a `state_*` hypothesis.
            inventory_delta=self._inventory_delta(),
            gui_open=self._gui_open,
            # The measured cursor line, so a grep over the log can reconstruct where the
            # pointer was when a click ran. One run's turns grepped for [CURSOR] three
            # turns running and found nothing: the line existed only in the prompt. The
            # [GRID] occupancy rides along for the same reason.
            cursor_line=(self.cursor.line(self._cur_inv, self._screen)
                         + (("\n" + self._grid_line()) if self._grid_line() else "")
                         ) if self._gui_open else "",
        )
        entry = self._plan_entries[index]
        sp, cp = self._entry_start_pos, self._cur_pos
        moved = (((cp["x"] - sp["x"]) ** 2 + (cp["z"] - sp["z"]) ** 2) ** 0.5
                 if (sp and cp) else 0.0)
        descended = (sp["y"] - cp["y"]) if (sp and cp) else 0.0
        outcome = {
            "step": self.step, "label": describe_entry(entry).replace("[ACTION] ", "")[:60],
            "moved": moved, "descended": descended, "inv": self._inventory_delta()[:80],
            "events": list(self._pending_events), "note": first_note, "frame": ep_frame}
        self._recent_outcomes.append(outcome)
        self._turn_outcomes.append(outcome)
        nudge = self.governor.note_entry(
            label=entry.get("procedure", "raw"),
            cell=cell_of(sp) or cell_of(cp), step=self.step,
            events=len(self._pending_events), moved=moved, descended=descended,
            inv_changed=bool(self._inventory_delta()),
            item_types=set(self._cur_inv.keys()),
            milestones=len(self.ledger.achieved))
        if not self.reflexes:
            nudge = None
        if nudge:
            self.memory.add_note(nudge)
            self.cursor_stats["governor_nudges"] = (
                self.cursor_stats.get("governor_nudges", 0) + 1)
        self._pending_events = []

    def _inventory_delta(self) -> str:
        """What the finished entry changed in the inventory, as a signed list.

        Empty when nothing moved -- and an empty [INV] line after a click is itself the
        finding, so `write_action` renders the line only when there is a change and the
        absence is read as "that click did nothing".
        """
        bits = []
        for item in sorted(set(self._entry_start_inv) | set(self._cur_inv)):
            d = self._cur_inv.get(item, 0) - self._entry_start_inv.get(item, 0)
            if d:
                bits.append(f"{item} {d:+d}")
        return ", ".join(bits)

    NETHER_MOVE_KEYS = ("forward", "back", "left", "right")

    def _nether_lock(self, action: dict[str, Any]) -> dict[str, Any]:
        """The Nether lock on one plan action (see `_nether_lock_noted`): a moving action
        gets sneak and loses sprint; a jump taken while moving is dropped (a vertical
        jump -- pillar_up's -- keeps it). Plan actions only: the reflex ticks (the lava
        escape's sprint out of a pool, the fightback) return before this. Nothing with a
        screen open (sneak + a click is the GUI's quick-move), nothing outside the
        Nether, nothing without the runner's reflexes (`--human-play`)."""
        if self._dimension != "the Nether":
            self._nether_lock_noted = False
            return action
        if not getattr(self, "reflexes", True) or self._gui_open or not isinstance(action, dict):
            return action
        moving = any(action.get(k) for k in self.NETHER_MOVE_KEYS)
        if not moving and not action.get("sprint"):
            return action
        a = dict(action)
        a["sprint"] = 0
        if moving:
            a["sneak"] = 1
            if a.get("jump"):
                a["jump"] = 0
                self.cursor_stats["nether_lock_jumps"] = (
                    self.cursor_stats.get("nether_lock_jumps", 0) + 1)
        self.cursor_stats["nether_lock_ticks"] = self.cursor_stats.get("nether_lock_ticks", 0) + 1
        if not self._nether_lock_noted:
            self._nether_lock_noted = True
            self.memory.add_note(
                "NETHER LOCK: from here on the runner holds sneak on every step you take "
                "(a quarter of the walking speed), never sprints, and drops a jump taken "
                "while moving; and a plan entry that walks you a block DOWN with lava in "
                "the lower view is dropped on the spot (NETHER DESCENT). Every Nether visit "
                "on record died within 400 steps of arriving, walking, sprinting or jumping "
                "down a slope or off a ledge into the lava sea at y ~31. A one-block rise is "
                "tunnelled (explore_nether does that itself) or pillared; the way DOWN is dug "
                "(stair_down), never walked or jumped; lava is crossed with bridge_forward. "
                "A blaze or a fortress sighting still ends the walk with its note.")
        return a

    #: Entries whose descent is deliberate and dug or bridged, not walked.
    NETHER_DESCENT_OK = frozenset({"stair_down", "dig_down", "bridge_forward", "find_lava",
                                   "make_obsidian", "mine_obsidian", "enter_portal",
                                   "pillar_down"})
    NETHER_DESCENT_MIN = 0.9

    def _nether_descent_guard(self, step: int, pos: dict[str, float] | None) -> None:
        """The Nether's walked descent (with `_nether_lock`): every 4th tick the lower
        view's lava share is sampled, and a plan entry that has taken the avatar
        NETHER_DESCENT_MIN+ blocks below where it started, with lava in that view, is
        dropped with a NETHER DESCENT note. One run (30472-30505): forward+
        sprint+jump down a slope from y 36 to 28 into the sea, one raw entry after
        another, LAVA AHEAD already in its notes; one run (17893-17976): the explore walk
        went 4 blocks down-slope to the lake's edge and fell in. Dug descents
        (NETHER_DESCENT_OK) and the runner's own escapes are exempt."""
        if pos is None or self._dimension != "the Nether" or not getattr(self, "reflexes", True):
            return
        if step % 4 or self._gui_open:
            return
        if self._last_pov is not None:
            self._nether_lava = float(vision.lava_fraction(np.asarray(self._last_pov)))
        if not self.queue or self._entry_start_pos is None:
            return
        if self._reflex is not None and self._reflex.get("kind") in ("lava", "flee", "fightback",
                                                                     "bunker", "pillar", "drown"):
            return
        idx = self._entry_index
        entry = (self._plan_entries[idx]
                 if idx is not None and 0 <= idx < len(self._plan_entries) else None)
        name = entry.get("procedure", "raw") if isinstance(entry, dict) else "raw"
        if name in self.NETHER_DESCENT_OK:
            return
        drop = float(self._entry_start_pos["y"]) - float(pos["y"])
        if drop < self.NETHER_DESCENT_MIN or self._nether_lava < vision.LAVA_FRAC_MIN:
            return
        self.cursor_stats["nether_descents"] = self.cursor_stats.get("nether_descents", 0) + 1
        dropped_n = len(self.queue)
        self.queue.clear()
        self.memory.add_note(
            f"NETHER DESCENT: this entry ({name}) walked you {drop:.0f} block(s) DOWN to "
            f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f}) with lava filling "
            f"{100 * self._nether_lava:.0f}% of the lower view -- the slope ends in the lava "
            f"sea. The runner dropped the rest of your plan ({dropped_n} action(s)). Go back "
            f"UP the way you came, or dig the way down (stair_down) if down is where you must "
            f"go; never walk or jump down toward lava.")

    def _lava_guard(self, step: int, pos: dict[str, float] | None) -> None:
        """Stop the plan when lava fills the lower view while the avatar moves underground.

        One run stood at a lava lake's edge with the lake filling the frame, planned a
        go_to across it and died; two runs met lava at y 6-13 too.
        Sampled every 4th tick, only below y 40, only when the avatar covered >= 0.15
        blocks (or dropped >= 0.5) since the previous sample -- a table or a torch seen
        standing still is never an alarm, and the colour band excludes both anyway.
        Re-fires after 150 ticks, or after 40 when the lava got 1.5x bigger.

        `find_lava` is exempt: that macro is a deliberate search FOR lava with the same
        reading, a stricter stop (it halts at least 2 blocks short and backs off if the
        geometry says nearer) and its own frame and note. The guard runs in `observe`,
        one tick ahead of the marker's own tick, so without the exemption it would clear
        the queue -- and the macro -- on the very frame the search was run to get.
        """
        if pos is not None:
            self._pos_hist.append((step, pos["x"], pos["y"], pos["z"]))
        if not getattr(self, "reflexes", True):
            return
        if step % 4 or self._gui_open or self._last_pov is None or pos is None:
            return
        if self.queue and macros.kind_of(self.queue[0][0]) in self.LAVA_GUARD_EXEMPT:
            return
        if pos["y"] > 40.0 or len(self._pos_hist) < 2:
            return
        prev = self._pos_hist[0]
        moved = math.hypot(pos["x"] - prev[1], pos["z"] - prev[3])
        dropped = prev[2] - pos["y"]
        if moved < 0.15 and dropped < 0.5:
            return
        frac = vision.lava_fraction(np.asarray(self._last_pov))
        if frac < vision.LAVA_FRAC_MIN:
            return
        # The cooldown holds within the plan entry the guard stopped: action_num advances
        # when that entry closes (the queue is cleared), so the model's next entry -- the
        # first of its next plan included -- is checked afresh. One run:
        # stopped at 27% during Action 617 (mine_obsidian, action_num 616); the next
        # plan's FIRST entry, go_to west (Action 618, action_num 617), crossed the cell
        # it had just mined the obsidian out of 30 ticks later and it burned to death
        # with 5 obsidian -- inside the `<= last + 1` window this line used to allow.
        since = step - self._last_lava_step
        same_action = self.action_num <= self._last_lava_action
        if (since < 150 and same_action
                and not (since >= 40 and frac >= 1.5 * self._last_lava_frac)):
            return
        self._last_lava_step, self._last_lava_frac = step, frac
        self._last_lava_action = int(self.action_num)
        self.cursor_stats["lava_flagged"] = self.cursor_stats.get("lava_flagged", 0) + 1
        self._keep_event_frame(step, "lava", self._last_pov)
        dropped_n = len(self.queue)
        self.queue.clear()
        if self._reflex is not None and self._reflex.get("kind") == "flee":
            # A sprint runs blind for 60 ticks: the reflex tick comes before the
            # queue, so dropping the plan alone would not stop it (audit pass 8).
            self._finish_flee(self._reflex, "lava ahead")
        elif self._reflex is not None and self._reflex.get("kind") == "fightback":
            self._finish_fightback(self._reflex, "lava ahead")     # it steps in too (pass 20)
        self.memory.add_note(
            f"LAVA AHEAD: {100 * frac:.0f}% of the lower view is lava at "
            f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f}) facing yaw "
            f"{pos['yaw']:.0f}. The runner dropped the rest of your plan ({dropped_n} "
            f"action(s)) before you walked or dug into it"
            + ". " + self._lava_advice(pos) + self._lava_repeat_clause(pos, frac))

    def _queue_head_action(self) -> dict[str, Any]:
        """The raw action dict at the head of the queue (a marker entry's keys included),
        or {} when the queue is empty."""
        if not self.queue:
            return {}
        head = self.queue[0]
        act = head[0] if isinstance(head, (tuple, list)) and head else head
        return act if isinstance(act, dict) else {}

    def _shaft_guard(self, step: int, pos: dict[str, float] | None) -> None:
        """Stop the plan before the avatar steps into its own open shaft.

        One run (step 19286): after a stair_down at y 67 it ran
        mine_forward north, broke through into the y 9..67 shaft it had dug at steps
        3955-4663 one block away, walked into the column and fell 58 blocks -- dead, the
        kit lost, 6k steps of rebuilding; one run jumped into its own shaft after the
        drops. Both shafts were on the map as walked columns (grid.drop_ahead). The
        cells ahead are taken along the motion of the last tick -- as far as a jump at
        that speed carries (a staged scene: the go_to servo sprint-jumps at 0.35 a tick and a
        1-block lookahead fired in mid-air over the hole) -- and, when the queued action
        holds `forward`/`back`, along the facing too (the first moving tick after a wall
        breaks starts 0.3 blocks from the edge). No sneak exemption: in the simulator
        sneak + forward walked off the edge (s23). Same drop-the-plan shape as the lava
        guard; one stop per column and plan entry (action_num advances when the stopped
        entry closes, so the model's NEXT plan is checked afresh -- the lava guard's `+ 1`
        window would let a re-issued walk through); nothing to stop when no plan and no
        moving reflex is running (momentum alone cannot be cancelled).
        """
        if pos is None or self._gui_open or len(self._pos_hist) < 2:
            return
        if not getattr(self, "reflexes", True):
            return
        reflex_moves = (self._reflex is not None
                        and self._reflex.get("kind") in ("flee", "fightback"))
        if not self.queue and not reflex_moves:
            return
        here = grid_mod.cell_of(pos)
        if here is None:
            return
        act = self._queue_head_action()
        cands: list[tuple[float, tuple[int, int, int]]] = []
        prev = self._pos_hist[-2]
        dx, dz = float(pos["x"]) - prev[1], float(pos["z"]) - prev[3]
        sp = math.hypot(dx, dz)
        if sp > 1.0:
            return                                  # a teleport, not a walk
        if sp >= 0.08:
            look = min(self.SHAFT_LOOKAHEAD_MAX, max(self.SHAFT_LOOKAHEAD, sp * 14.0))
            d = self.SHAFT_LOOKAHEAD
            while d <= look + 1e-9:
                cands.append((d, (int(math.floor(pos["x"] + dx / sp * d)), here[1],
                                  int(math.floor(pos["z"] + dz / sp * d)))))
                d += 0.5
        if act.get("forward"):
            for d in (self.SHAFT_LOOKAHEAD, 2.0):
                c = grid_mod._ahead(pos, d)
                if c is not None:
                    cands.append((d, c))
        if act.get("back"):
            c = grid_mod._ahead(pos, -self.SHAFT_LOOKAHEAD)
            if c is not None:
                cands.append((1.0, c))
        seen: set[tuple[int, int, int]] = {here}
        for _, c in sorted(cands):
            if c in seen:
                continue
            seen.add(c)
            d = self.grid.drop_ahead(c)
            if d is None:
                continue
            col = (c[0], c[2])
            if col == self._last_shaft[0] and self.action_num <= self._last_shaft[1]:
                return                              # once per column and entry
            self._last_shaft = (col, int(self.action_num))
            self.cursor_stats["shaft_stops"] = self.cursor_stats.get("shaft_stops", 0) + 1
            dropped_n = len(self.queue)
            self.queue.clear()
            if self._reflex is not None and self._reflex.get("kind") == "flee":
                self._finish_flee(self._reflex, "shaft ahead")
            elif self._reflex is not None and self._reflex.get("kind") == "fightback":
                self._finish_fightback(self._reflex, "shaft ahead")
            hurt = max(0, d["drop"] - 3)
            self.grid.mark_hazard(step, {"x": c[0] + 0.5, "y": float(c[1]), "z": c[2] + 0.5},
                                  0.0, f"your open shaft ({d['drop']}-block drop)")
            self.memory.add_note(
                f"SHAFT AHEAD: the cell ahead ({c[0]}, {c[1]}, {c[2]}) is the open column "
                f"of your own shaft, walked from y {d['top']} down to y {d['bottom']} "
                f"(steps {d['dug']}-{d['reached']}): one more step falls {d['drop']} "
                f"blocks ({hurt} hp{', FATAL' if hurt >= 20 else ''}). The runner dropped "
                f"the rest of your plan ({dropped_n} action(s)) at ({pos['x']:.1f}, "
                f"{pos['y']:.0f}, {pos['z']:.1f}). The shaft is one block wide: step aside "
                f"one block and go around it, or descend beside it with stair_down. "
                f"Sneaking does NOT hold you at an edge here. NEVER walk or jump into an "
                f"open shaft.")
            return

    def _fall_guard(self, step: int, pos: dict[str, float] | None) -> None:
        """Stop the plan when the avatar lands after a fall it did not plan.

        One run (18768-18818, the Nether): a go_to dropped 13 blocks into a
        hole; the plan went on (the stall branch queued pillar_up(2) toward a mid-air
        cell), the model pressed forward+jump+use and fell 9 more, a mob followed it
        down, dead with the kit. One run (26888): mine_forward into a cliff, a 20-block fall
        into lava. A descent that is walked (a stair, dig_down, a jump down one block, a
        swim) never exceeds FALL_VMAX in one tick; free fall does after ~1.7 blocks. On
        landing (two still ticks) after a drop of FALL_MIN_DROP+ blocks the queue is
        cleared and the note says where the avatar is and how to get out: the model's
        next move must come from a look, not from the plan that fell.
        """
        if pos is None or not getattr(self, "reflexes", True):
            return
        y = float(pos["y"])
        f = self._fall
        if f is None:
            self._fall = {"top": y, "prev": y, "still": 0, "vmax": 0.0}
            return
        prev = f["prev"]
        f["prev"] = y
        dy = prev - y
        if dy > 0.01:                                   # descending
            f["still"] = 0
            f["vmax"] = max(f["vmax"], dy)
            return
        if y > f["top"] + 0.01 or dy < -0.01:           # rising: a jump, a climb, a teleport
            f.update(top=y, still=0, vmax=0.0)
            return
        f["still"] += 1
        if f["still"] != 2:
            return
        drop = f["top"] - y
        vmax = f["vmax"]
        f.update(top=y, vmax=0.0)
        if drop < self.FALL_MIN_DROP or vmax < self.FALL_VMAX or self._gui_open:
            return
        if not self.queue and not (self._reflex is not None
                                   and self._reflex.get("kind") in ("flee", "fightback")):
            return
        self.cursor_stats["fall_stops"] = self.cursor_stats.get("fall_stops", 0) + 1
        dropped_n = len(self.queue)
        self.queue.clear()
        if self._reflex is not None and self._reflex.get("kind") == "flee":
            self._finish_flee(self._reflex, "fell")
        elif self._reflex is not None and self._reflex.get("kind") == "fightback":
            self._finish_fightback(self._reflex, "fell")
        nether = "Nether" in str(self._dimension or "")
        self.memory.add_note(
            f"FELL {drop:.0f} blocks to ({pos['x']:.0f}, {y:.0f}, {pos['z']:.0f}) -- a drop "
            f"the plan did not see. The runner dropped the rest of it ({dropped_n} "
            f"action(s)). You are at the bottom of a hole, a cliff or a ravine: LOOK before "
            f"you move (look_abs(pitch=20) at four yaws), then go back up the way the map "
            f"knows -- pillar_up beside the wall you fell down, or stair_up -- never by "
            f"jumping onward from here."
            + (" In the Nether every ledge ends in lava: walk, never sprint or jump blind."
               if nether else ""))

    def _lava_repeat_clause(self, pos: dict[str, float], frac: float = 0.0) -> str:
        """"" the first time the guard stops a plan at this spot. From the second stop
        within the same 3-block cell: REPEAT (the count and the instruction to leave --
        the same sliver in a wall does not grow into a lake), UNLESS the sighting GREW
        since the last stop here while the avatar carries the water bucket and the
        obsidian milestone is open: then it is approaching the pool the advice above
        told it to approach, and the clause says so instead of sending it away.
        One run: stops at 5764 (2%) and 5820 (4%) at (-2998, 12, -5554),
        the second carried REPEAT ("tunnel away ... do not target this spot again"); the
        model obeyed, searched 7.6k steps for another pool and found one at 13358.
        One run made its obsidian at 6134 from the SAME pool ((-2996, 11, -5553), five
        sliver stops there) by ignoring the clause."""
        cell = (int(math.floor(pos["x"] / 3)), int(math.floor(pos["y"] / 3)),
                int(math.floor(pos["z"] / 3)))
        rec = self._lava_stops.get(cell) or {"n": 0, "frac": 0.0}
        n, prev = int(rec["n"]) + 1, float(rec["frac"])
        self._lava_stops[cell] = {"n": n, "frac": max(prev, float(frac))}
        if n < 2:
            return ""
        if (float(frac) > prev + 0.015 and self._cur_inv.get("water_bucket", 0)
                and self._obsidian_unmet()):
            self.cursor_stats["lava_closer"] = self.cursor_stats.get("lava_closer", 0) + 1
            return (f" CLOSER: stop {n} within 3 blocks of here, and the sighting GREW from "
                    f"{100 * prev:.0f}% to {100 * frac:.0f}%: you are approaching the lava "
                    "the obsidian needs, not looping on a sliver in a wall. Keep coming "
                    "the way the advice above says -- look down, 2-3 blocks at a time -- "
                    "until a note names the pool; do not turn away from it.")
        self.cursor_stats["lava_repeat_stops"] = self.cursor_stats.get("lava_repeat_stops", 0) + 1
        return (f" REPEAT: this is the {n}{'nd' if n == 2 else 'rd' if n == 3 else 'th'} plan "
                "the same lava has stopped within 3 blocks of here. It will not become "
                "a lake by being approached again: tunnel away from it on another "
                "bearing or another level, and do not target this spot again.")

    def _obsidian_unmet(self) -> bool:
        """True when a configured milestone about obsidian is still unverified."""
        for rule in self.ledger.cfg or []:
            if "obsidian" in str(rule.get("identity", "")):
                return rule["identity"] not in self.ledger.achieved
        return False

    def _lava_advice(self, pos: dict[str, float]) -> str:
        """What to DO about the lava that just stopped the plan.

        With a water bucket in the pack and the obsidian milestone still open, this lava
        is not only a hazard: it is the one ingredient the chain needs, and the frame the
        guard just read is enough to name the rim block to pour on
        (macros_nether.lava_cells). Fifteen second-half arms carried the bucket to y <= 15
        and none ever poured. Without the bucket, or with obsidian already banked, the
        old avoid-it text stands.
        """
        avoid = ("Do not re-issue the same walk: seal a flow with cobblestone, turn away, "
                 "tunnel elsewhere -- lava ends a run in seconds.")
        if not self._cur_inv.get("water_bucket", 0) or not self._obsidian_unmet():
            return avoid
        from mcu_worldmodel import macros_nether as MN
        cells = None
        frac = 0.0
        if self._last_pov is not None:
            frac, cx, bottom, top = vision.lava_view(np.asarray(self._last_pov))
            if frac:
                cells = MN.lava_cells(pos, cx, bottom, top=top,
                                      min_dist=MN.FIND_MIN_DIST)
        if cells is not None and frac < self.LAVA_SLIVER_FRAC:
            # A sliver: on the map as lava, NOT on record for the no-argument pour.
            self.grid.mark_lava(self.step, cells["pool"], cells["rim"], frac)
            self.cursor_stats["lava_slivers"] = self.cursor_stats.get("lava_slivers", 0) + 1
            return (f"Only {100 * frac:.0f}% of the lower view is lava: a SLIVER -- a fall "
                    "down a wall or one source in a cave face, most often FLOWING lava, "
                    "which water turns to cobblestone, not obsidian (three lives poured on "
                    "a 1-3% sighting and mined stone). Its cells are NOT on record for "
                    "`make_obsidian()`: do not pour on it. It marks the direction: with "
                    "the guard on, look_abs(pitch=25) and step 2-3 blocks toward it, and "
                    f"pour only when a sighting reads {100 * self.LAVA_SLIVER_FRAC:.0f}%+ "
                    "and this note names the pool -- or turn away and `find_lava()` on.")
        if cells is None:
            return ("THIS IS THE LAVA THE OBSIDIAN NEEDS and you carry the water_bucket. "
                    "Do not walk into it -- lava ends a run in seconds -- but do not "
                    "leave it either: look down (look_abs(pitch=25)) so the pool is in "
                    "the lower view, then find_lava() from here names the rim cell to "
                    "pour on.")
        MN.remember_lava(cells, self.step, pos, "guard")
        self.grid.mark_lava(self.step, cells["pool"], cells["rim"], frac)
        return ("THIS IS THE LAVA THE OBSIDIAN NEEDS and you carry the water_bucket. "
                + MN.lava_sentence(cells)
                + " These cells are on record: `make_obsidian()` and then `mine_obsidian()` "
                  "with NO arguments use them exactly. Do not walk into it and do not walk "
                  "around it -- pour from where you stand; lava ends a run in seconds.")

    def _dark_line(self, marker: dict[str, Any]) -> str:
        """The sentence a mining macro's finish note carries when the ore watch sampled
        a dark view throughout: the stretch was mined blind, and the model has to know
        that the silence of the sentinel meant nothing."""
        n = int(marker.get("lum_n", 0))
        if n < 3:
            return ""
        mean = float(marker.get("lum_sum", 0.0)) / n
        if mean >= self.DARK_TUNNEL_LUM:
            return ""
        self.cursor_stats["mine_dark"] = self.cursor_stats.get("mine_dark", 0) + 1
        return (f" The view was DARK throughout (mean brightness {mean:.0f}/255): the ore "
                f"watch cannot see ore colours in the dark, so this stretch was mined "
                f"blind. Light the tunnel before mining on -- torches (1 coal + 1 stick = "
                f"4, a 2x2 recipe) on a wall's side face every ~8 blocks; with no coal, a "
                f"log smelted in the furnace is charcoal and works the same.")

    # -- reporting --------------------------------------------------------

    def report(self) -> dict[str, Any]:
        return {
            "task": self.task_text,
            "memory_mode": self.memory_mode,
            **({"direct": dict(self.direct_stats)} if self.memory_mode == "direct"
               else {}),
            # Files the model left in the workspace that the
            # contract does not keep, removed at the end of the turn they appeared in.
            "foreign_files_swept": self.memory.swept,
            "grid": self.grid.audit(),
            "watchdog": {"plan_stalls": self.governor.plan_stalls},
            # the game's kill counters as of the last observe, when there is one (the
            # endgame skill probes read them; nothing of this reaches the model, and a
            # life without a kill reports exactly what it did before)
            **({"combat": {"kills": self._kills()}} if self._kills() else {}),
            "thin": self.thin,
            **({"atoms": True} if self.atoms else {}),
            **({"own_live": True, "own_loops": {k: dict(v) for k, v in self._own_loops.items()}}
               if self.own_live else {}),
            **({"near_deaths": True} if self.near_deaths else {}),
            **({"skills": True} if self.skills else {}),
            **({"harness_reflexes": False} if not self.reflexes else {}),
            **({"minimal": True} if self.minimal else {}),
            **({"own": {"procedures": len(self._own_procs),
                        "calls": dict(self._own_calls),
                        **({"reflexes": len(self._own_reflexes),
                            "reflex_fires": dict(self._own_reflex_fires)}
                           if self.own_reflexes else {})}} if self.own else {}),
            **({"mfm_options": {"expect": self.expect, "frames": self.frames,
                                "event_sheet": self.event_sheet}}
               if self.memory_mode == "mfm" else {}),
            "steps": self.step,
            "turns": dict(self.turns),
            "milestones": self.ledger.summary(),
            "cursor": {
                **{k: round(v, 1) if isinstance(v, float) else v
                   for k, v in self.cursor_stats.items()},
                "drift_mean": round(self.cursor_stats["drift_sum"]
                                    / max(1, self.cursor_stats["anchored"]), 2),
            },
            "codex": {"calls": self.codex.calls, **self.codex.vision_audit()},
            **({"mfm": self.episodes.audit()} if self.episodes else {}),
        }

    def save_report(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.report(), indent=2), encoding="utf-8")
