"""The model's own procedures (`--own`): scripts it writes under `mine/procedures/`.

The self-harness arm: the procedure
library the contract shows is cut to the atoms (`procedures.ATOMS`, `--atoms`) and the
model rebuilds what it needs as scripts it keeps. A script at `mine/procedures/<name>.py`
is a procedure from the next turn on: the harness runs it in a subprocess with the state
on stdin and the call's `args` on the command line, and the PLAN it prints (the same JSON
shape as actions.json: built-in procedures and raw actions) is parsed with the same caps
and validator as the model's own plan. Depth one: an own procedure cannot call another.

Why a subprocess and not an import: the model's code must not run inside the purple
process (one exception, one infinite loop, one `os.chdir` would take the episode down),
and a script is what the model already writes and runs from its shell every turn, so the
interface is nothing new to it. What is NOT enforced here: network or filesystem
isolation beyond cwd and a minimal environment -- the model's shell (codex's bwrap
workspace-write sandbox) is the wall; this runs with the harness's own rights.

`mine/` itself persists across turns (memory.sweep_foreign keeps it with `--own`) and is
carried to the next life under `previous/life_<i>/mine/` like every other record.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

OWN_DIR = Path("mine") / "procedures"
TIMEOUT_S = 10.0
OUTPUT_CAP = 65536


@dataclass
class OwnProcedure:
    name: str
    path: Path
    doc: str = ""
    params: dict[str, str] = field(default_factory=dict)
    error: str | None = None       # a file the loader could not accept (why)
    loop: bool = False             # `own_live`: a closed loop (a top-level `LOOP = True`)


def _is_loop(src: str) -> bool:
    """True when the module has a top-level `LOOP = True` (see the closed-loop section)."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LOOP" for t in node.targets):
            try:
                return bool(ast.literal_eval(node.value))
            except (ValueError, SyntaxError):
                return False
    return False


def _first_doc_line(src: str) -> tuple[str, dict[str, str]]:
    """The first docstring line (the index entry) and, if the module defines a dict
    `PARAMS = {name: meaning}`, the parameters it advertises."""
    doc = ""
    params: dict[str, str] = {}
    tree = ast.parse(src)
    d = ast.get_docstring(tree) or ""
    doc = d.strip().splitlines()[0].strip() if d.strip() else ""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PARAMS" for t in node.targets):
            try:
                v = ast.literal_eval(node.value)
                if isinstance(v, dict):
                    params = {str(k): str(x) for k, x in v.items()}
            except (ValueError, SyntaxError):
                pass
    return doc, params


def scan(root: Path, builtins: set[str] | None = None,
         loops: bool = False) -> dict[str, OwnProcedure]:
    """The scripts under `<root>/mine/procedures/*.py`, by name. A file whose name is a
    built-in procedure, or that does not parse, is listed with its `error` (the [OWN]
    block shows it) and is not callable. `loops` (`own_live`): a script that declares
    `LOOP = True` is a closed loop; without it the line means nothing."""
    d = Path(root) / OWN_DIR
    out: dict[str, OwnProcedure] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.py")):
        name = p.stem
        if name.startswith("_"):
            continue
        proc = OwnProcedure(name=name, path=p)
        if not name.isidentifier():
            proc.error = "the file name must be a plain identifier (letters, digits, _)"
        elif builtins and name in builtins:
            proc.error = f"`{name}` is a built-in procedure; pick another name"
        else:
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
                proc.doc, proc.params = _first_doc_line(src)
                proc.loop = bool(loops) and _is_loop(src)
            except SyntaxError as e:
                proc.error = f"does not parse: line {e.lineno}: {e.msg}"
            except OSError as e:
                proc.error = f"unreadable: {e}"
        out[name] = proc
    return out


def run(proc: OwnProcedure, root: Path, state: dict[str, Any], args: dict[str, Any],
        timeout: float = TIMEOUT_S) -> tuple[str | None, str | None]:
    """Run the script; (stdout, None) on success, (None, why) on any failure. `why` is
    one line: the last non-empty stderr line, the timeout, or the exit code."""
    if proc.error:
        return None, proc.error
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "MCU_OWN_PROCEDURE": proc.name,
    }
    try:
        cp = subprocess.run(
            [sys.executable, str(proc.path), "--args", json.dumps(args)],
            input=json.dumps(state), capture_output=True, text=True, cwd=str(root),
            env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout:.0f} s (print the plan and exit)"
    except OSError as e:
        return None, f"could not run: {e}"
    if cp.returncode != 0:
        tail = [ln for ln in (cp.stderr or "").splitlines() if ln.strip()]
        if not tail:
            return None, f"exit code {cp.returncode} (nothing on stderr)"
        return None, f"exit code {cp.returncode}: {tail[-1].strip()[:300]}"
    out = cp.stdout or ""
    if len(out) > OUTPUT_CAP:
        return None, f"printed {len(out)} bytes; a plan is at most {OUTPUT_CAP}"
    if not out.strip():
        return None, "printed nothing (a plan is JSON on stdout)"
    logger.debug(f"[own] {proc.name}({args}) -> {len(out)} bytes")
    return out, None


#: mine/<RECORD_FILE>: what every own procedure DID, per entry, harness-measured from the
#: same ledger that scores milestones -- ticks, sword hits landed, kills, deaths, health
#: at start and end -- keyed by script name, each row tagged with the life that ran it.
#: Carried under previous/ with the rest of mine/, so a later life reads a carried
#: script's record instead of a bare "called 0x": one chain of three lives each RETIRED
#: the fight loop of the life before and wrote a new one, and the retired loop of life 1
#: had landed 6 hits in 167 ticks -- more than any script that replaced it.
RECORD_FILE = "scripts_record.json"
RECORD_ROWS = 40        # rows kept per script, newest last


def load_record(root: Path) -> dict[str, list[dict[str, Any]]]:
    path = Path(root) / "mine" / RECORD_FILE
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): [r for r in v if isinstance(r, dict)]
            for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}


def save_record(root: Path, record: dict[str, list[dict[str, Any]]]) -> None:
    path = Path(root) / "mine" / RECORD_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({k: v[-RECORD_ROWS:] for k, v in record.items()},
                                  indent=0, sort_keys=True))
        tmp.replace(path)
    except OSError as e:
        logger.warning(f"[own] could not write {path}: {e}")


def record_life(record: dict[str, list[dict[str, Any]]]) -> int:
    """The life number this life's rows get: one past the newest life in the record."""
    return 1 + max((int(r.get("life", 0)) for rows in record.values() for r in rows), default=0)


def scorecard(row: dict[str, Any]) -> str:
    """One row of the record as the note reads: `167 ticks, 6 sword hits, 0 kills,
    health 20->12, 0 deaths`."""
    h = row.get("health") or [None, None]
    hp = (f"health {h[0]:.0f}->{h[1]:.0f}" if h[0] is not None and h[1] is not None
          else "health unknown")
    return (f"{int(row.get('ticks', 0))} ticks, {int(row.get('hits', 0))} sword hits, "
            f"{int(row.get('kills', 0))} kills, {hp}, {int(row.get('deaths', 0))} deaths")


def record_line(rows: list[dict[str, Any]], this_life: int) -> str:
    """A script's record for the [OWN] index, one clause per life, totals over its
    entries: `record: life 1 (1 entry): 167 ticks, 6 sword hits, 0 kills, health 20->12,
    0 deaths | this life (2 entries): ...`."""
    by_life: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        by_life.setdefault(int(r.get("life", 0)), []).append(r)
    parts = []
    for life in sorted(by_life):
        rs = by_life[life]
        tot = {"ticks": sum(int(r.get("ticks", 0)) for r in rs),
               "hits": sum(int(r.get("hits", 0)) for r in rs),
               "kills": sum(int(r.get("kills", 0)) for r in rs),
               "deaths": sum(int(r.get("deaths", 0)) for r in rs)}
        hs = [r.get("health") for r in rs if r.get("health") and r["health"][0] is not None
              and r["health"][1] is not None]
        tot["health"] = [hs[0][0], hs[-1][1]] if hs else [None, None]
        who = "this life" if life >= this_life else f"life {life}"
        parts.append(f"{who} ({len(rs)} entr{'y' if len(rs) == 1 else 'ies'}): {scorecard(tot)}")
    return "record: " + " | ".join(parts) if parts else ""


def index_block(procs: dict[str, OwnProcedure], calls: dict[str, int],
                record: dict[str, list[dict[str, Any]]] | None = None,
                this_life: int = 1) -> str:
    """The [OWN] block of the turn prompt: every script under mine/procedures/, its
    index line, call count and record (what its entries did, by life) -- or why it
    cannot be called."""
    if not procs:
        return ""
    lines = ["[OWN] your own procedures (mine/procedures/*.py; call as "
             "{\"procedure\": \"<name>\", \"args\": {...}}):"]
    for name, p in procs.items():
        if p.error:
            lines.append(f"- `{name}` -- NOT callable: {p.error}")
            continue
        args = ", ".join(f"{k}=<{v}>" for k, v in p.params.items())
        n = calls.get(name, 0)
        rec = record_line((record or {}).get(name) or [], this_life)
        lines.append(f"- `{name}({args})` -- {p.doc or '(no docstring)'}"
                     f" [{'closed loop; ' if p.loop else ''}called {n}x"
                     + (f"; {rec}" if rec else "") + "]")
    return "\n".join(lines)


# -- closed-loop procedures and the live view (`own_live`) ---------------------------
#
# Why. An own procedure is expanded ONCE, at plan time, from the numbers of the turn; a
# reflex runs every 4 ticks on numbers and never sees a frame, and what it fires ends
# the plan. So nothing the model writes can look at the view while its plan runs, and
# nothing it writes can follow a thing that moves. The blaze probe showed it (pilot
# 50240421: three lives, 16 sword hits, 7 deaths, no kill): every aim was chosen at turn
# time and swung at where the mob had been, and the third life wrote a procedure whose
# only job was to find out whether a script can see mid-plan ("There is NO closed visual
# loop inside a plan"). The runner's own macros have that loop (`macros.tick`); this
# hands the same grain to the model's scripts. It is a capability, not a skill: no
# detector, no aim rule and no fight is written here.
LOOP_BUDGET = 200           # ticks a loop entry runs when its args give no `ticks`
LOOP_CALL_TICKS = 20        # ticks of actions ONE call may return
LOOP_ENTRY_CAP = 6          # entries ONE call may return
LOOP_TIMEOUT_S = 30.0       # seconds one call may take (a cold numpy import off NFS took 5+ on the first call of three lives)
#: Every call has the same limit since 2026-10-06: a 10 s limit on the later calls ended a
#: fight entry at call 14 on a busy node with 269 of 380 ticks unspent. The world waits
#: during a call, so the limit costs no tick.
LOOP_COLD_TIMEOUT_S = LOOP_TIMEOUT_S  # the FIRST call of an entry: a Python start on a loaded node took over 10 s twice in one life, and each cost a model turn; the world waits, so the limit costs no tick
LOOP_MEMO_CAP = 4096        # bytes of `memo` kept between calls
LOOP_NOTES = 6              # notes one loop entry may leave in the log
#: The live view, in the attach dir beside the workspace (never listed, never carried).
LIVE_FRAME = "live.png"


def parse_loop(out: str) -> tuple[dict[str, Any] | None, str | None]:
    """One call's stdout: `{"actions": [...], "again": bool, "memo": {...}, "note": str}`.
    (result, None), or (None, why). A missing `memo` keeps the previous one."""
    try:
        res = json.loads(out)
    except ValueError:
        return None, f"stdout is not JSON: {out.strip()[:120]!r}"
    if not isinstance(res, dict):
        return None, "stdout must be a JSON object"
    acts = res.get("actions", [])
    if not isinstance(acts, list):
        return None, "`actions` must be a list"
    memo = res.get("memo")
    if memo is not None:
        if not isinstance(memo, dict):
            return None, "`memo` must be a JSON object"
        if len(json.dumps(memo)) > LOOP_MEMO_CAP:
            return None, f"`memo` is over {LOOP_MEMO_CAP} bytes"
    note = str(res.get("note") or "").strip().splitlines()
    return {"actions": acts, "again": bool(res.get("again")), "memo": memo,
            "note": note[0][:400] if note else ""}, None


#: The contract's paragraph (appended when `own_live` is on).
LIVE_NOTE = """\
**Closed-loop procedures and the live view (this run).** Your scripts can SEE while your
plan runs. A procedure script with a top-level line `LOOP = True` is not expanded at
plan time: when its entry starts, and again each time the actions it returned have run,
the harness calls it with the state of THAT tick and `frame`, the path of a PNG of the
view at that tick, and runs what it returns -- a few ticks per call, for the entry's
budget. Your reflexes get the same `frame`. It is the one way to act on something that
moves or on what the view shows now; the contract is in `references/own.md`."""

#: references/own.md, after the reflex contract (`{w}`/`{h}`: the frame size of the run).
_LOOP_NOTE = """\
**Closed-loop procedures.** A script at `mine/procedures/<name>.py` with a top-level line
`LOOP = True` is a CLOSED LOOP. You call it like any procedure (`{"procedure": "<name>",
"args": {"ticks": 200, ...}}`), but the harness does not run it at plan time. When its
entry starts, and again each time the actions it last returned have finished, it is run
on the state of THAT tick:
- STDIN is the procedure state plus `frame` (the absolute path of a PNG of the current
  view at the engine's render size, larger than the {w}x{h} frames under `episodes/`;
  `frame_size` is its [width, height], so a detector you tune on the saved frames must
  scale its pixel numbers; it is overwritten at every call -- copy it if you want to
  keep one), `lava_frac`, `fire_frac`, `call` (0 on the first
  call), `ticks` (ticks this entry has used), `budget` (ticks it has left),
  `health_start` (your health when the entry started) and `memo` (the object you
  returned under `memo` on the previous call, `{}` on the first): your memory between
  calls;
- it prints ONE JSON object `{"actions": [...], "again": true, "memo": {...}, "note":
  "..."}`. `actions` (built-in procedures and raw actions, never an own procedure; at
  most 6 entries and 20 ticks per call, the rest is dropped) run at once. `again: true`
  asks to be called when they are done; `again: false`, or a call that returns nothing
  to run, ends the entry. `note` (optional, one line) reaches your next turn as `[LOOP
  <name>] ...`, at most 6 per entry: say what you saw when it changes, not at every call;
- the entry ends when `again` is false, when its budget is spent (`ticks` in the args,
  default 200, never more than the ticks your plan has left), when a call fails
  (non-zero exit, a call that takes over {warm} s, or bad JSON: one [NOTE] with the
  last error line), or
  when a reflex or a verified milestone drops the plan. The harness then writes one
  `[LOOP <name>] ended: ...` line with the calls and ticks it used. A hit you take does
  NOT drop a loop entry the way it drops an ordinary one: the loop sees `health` fall at
  its next call and decides for itself (below 6 health everything still stops);
- a call costs wall-clock (a Python start), not game ticks: the world waits while your
  script runs. Returning 2-6 ticks per call follows a thing that moves; returning 20
  walks a straight line. A raw camera turn is `{"action": {"camera": [dpitch, dyaw]},
  "repeat": 1}` in degrees, + pitch is down and + yaw is right.
What a loop is for: anything whose next action depends on what the view shows NOW -- a
target that moves, a walk that must stop at what it sees. Write the part that reads the
frame as a function you can also run on the saved frames under `episodes/` (the same
picture at {w}x{h}) and check it there before you put it in a loop.
**Your reflexes see the view too**: their STDIN gains `frame` and `frame_size`, the same
PNG, written at every reflex check (every 4 ticks)."""


def loop_note(frame_size: tuple[int, int]) -> str:
    return (_LOOP_NOTE.replace("{w}", str(int(frame_size[0])))
            .replace("{h}", str(int(frame_size[1])))
            .replace("{cold}", f"{LOOP_COLD_TIMEOUT_S:.0f}")
            .replace("{warm}", f"{LOOP_TIMEOUT_S:.0f}"))


#: The contract section (`--own`), kept in the thin contract (it sits before the first
#: moved heading).
MFM_OWN_NOTE = """\
**Your own files and procedures.** `mine/` is yours and PERSISTS: notes, scripts, data,
anything you write there survives the turn and is carried to your next life under
`previous/life_<i>/mine/`. A script at `mine/procedures/<name>.py` is a procedure from the
next turn on: call it as `{"procedure": "<name>", "args": {...}}` like a built-in. The
contract of such a script:
- the harness runs `python mine/procedures/<name>.py --args '<json of args>'` with the
  state on STDIN as JSON: `{"step", "max_steps", "pos": {"x","y","z","pitch","yaw"},
  "health", "food", "inventory": {item: count}, "hotbar": [{"slot","item","n"}],
  "gui_open", "dimension"}`;
- it prints ONE plan to stdout in exactly the actions.json shape,
  `{"actions": [{"procedure": ..., "args": {...}}, {"action": {...}, "repeat": N}]}`,
  built from the built-in procedures and raw actions (never another own procedure); the
  plan goes through the same caps and checks as yours;
- the first line of its docstring is its index entry, an optional `PARAMS = {"n": "how
  many"}` dict names its arguments; the `[OWN]` block of every turn lists your scripts
  with their call counts, or says why one cannot be called;
- a script that fails (non-zero exit, 10 s timeout, no JSON) costs one [NOTE] with the
  last error line and runs nothing; the rest of your plan still runs;
- it may read `logs.txt`, `grid.jsonl`, `episodes/` (`tools/episodes.py`) and your own
  `mine/` files to decide what to emit -- it sees the same numbers you do.
Write a procedure only after the same sequence has worked TWICE by hand, then call it by
name from then on; a script you never call again was a turn spent on nothing. Keep your
notes in `mine/notes.md` (what worked, coordinates, what each script assumes)."""

#: `--atoms`: the one line under the procedure index.
ATOMS_LINE = ("This run's procedure set is the ATOMS above: the task-shaped macros (a tree, "
              "a strip mine, a shaft, the obsidian, the portal, the Nether, the End) are "
              "not provided. Compose them from the atoms and raw actions; when a "
              "composition has worked twice, keep it as your own procedure.")


def atoms_line() -> str:
    """ATOMS_LINE for this run's arm: an arm without procedures of its own is not told
    to keep one."""
    from mcu_worldmodel import procedures as P
    return ATOMS_LINE if P.OWN else ATOMS_LINE.split("; when a composition")[0] + "."


#: `--atoms`, head of references/skills.md: its situations name the task-shaped macros.
ATOMS_REF_LINE = ("The macros this file names (harvest_tree, strip_mine, dig_down, make_obsidian, "
                  "build_portal_frame, light_portal, fight, travel, scan_around, aim_at_ore, ...) "
                  "are NOT built in this run: read each as a recipe -- the situation, the order of "
                  "steps, what to verify -- to compose from the atoms and your own scripts. The "
                  "wall watcher this file describes (a [NOTE] and the flag-time frame when "
                  "iron- or diamond-ore speckles cross the view) samples every raw "
                  "{\"attack\": 1} hold in this run and mine_ahead(n, ore_watch=true). A raw "
                  "hold is also cut the moment its block breaks, so a 30-tick hold per block "
                  "is the cheap, sighted way to mine; mine_ahead(n) spends all n ticks and "
                  "is for continuous digging (a shaft).")


def atoms_ref_line() -> str:
    """ATOMS_REF_LINE for this run's arm (see `atoms_line`)."""
    from mcu_worldmodel import procedures as P
    return (ATOMS_REF_LINE if P.OWN
            else ATOMS_REF_LINE.replace("from the atoms and your own scripts", "from the atoms"))


# -- the mfm-noprim arm: not even the atoms --------------------------------------------
#
# The arm with no hand-written skill of any grain: the procedure set is empty, no example
# script ships under skills/, and the runner's wall watcher is off. The model acts through
# the keys and through what it writes itself (procedures, closed loops, reflexes, all
# emitting raw actions). What it still gets is what every arm sees -- [STATE], [INV],
# [CURSOR], [GRID], the frame -- and the knowledge text, whose macro names are recipes.

#: The contract's procedure section, in place of the index.
NO_PRIMITIVES_LINE = (
    "This run has NO built-in procedures: no atom and no macro. Every entry is a raw "
    "action or one of your own procedures under `mine/procedures/`, and what your "
    "procedures, closed loops and reflexes return is raw actions too. Which scripts to "
    "write, if any, is yours to decide.")

#: Head of every reference file that names procedures (skills.md, survival.md, more.md).
NO_PRIMITIVES_REF_LINE = (
    "No procedure this file names exists in this run -- not `craft`, `cursor_to_slot`, "
    "`gui_click`, `look_abs`, `go_to`, `mine_ahead`, `place_at`, `use_at`, `eat`, "
    "`pillar_up`, nor any macro (harvest_tree, strip_mine, dig_down, scan_around, fight, "
    "...): this run has NO built-in procedures. Read each as a description of how a "
    "thing can be done, not as something you can call. Where it says the runner does something for you (a guard, a pillar, a "
    "stop at ore), it does not here: nothing watches your digging for ore, and nothing "
    "acts on a hit.")

#: The (old, new) rewrites that make the own/loop/reflex contracts true without built-ins;
#: each old text must occur in the contract it is applied to.
_NO_BUILTINS = (
    ("like a built-in", "beside the raw actions of your plan"),
    ('`{"actions": [{"procedure": ..., "args": {...}}, {"action": {...}, "repeat": N}]}`,\n'
     "  built from the built-in procedures and raw actions (never another own procedure)",
     '`{"actions": [{"action": {...}, "repeat": N}, ...]}`,\n'
     "  built from raw actions (this run has no built-in procedures; never another own procedure)"),
    ("(built-in procedures and raw actions, never an own procedure;",
     "(raw actions: this run has no built-in procedures, and never an own procedure;"),
    ("run, alphabetical; keep each under 50 ms -- read the state, not the logs. Reflexes\n"
     "worth writing FIRST, from what killed earlier runs: lava coming into the lower view\n"
     "while you walk or dig (stop, step back); a drop of 4+ blocks within a few ticks (stop,\n"
     "look before moving); health falling with no lava in view (a mob -- stop a dig or a\n"
     "sweep, pillar up or wall off); in the Nether, any walk with lava in view. ",
     "run, alphabetical; keep each under 50 ms -- read the state, not the logs. "),
    ("(optional: built-in procedures and raw actions,",
     "(optional: raw actions -- this run has no built-in procedures --"),
    ('"gui_open", "dimension"}`;',
     '"gui_open", "dimension", "slots": {"<slot 0-35>": [item, count]}, "cursor":\n'
     '  {"pos": [x, y] container px, "over": "<what [CURSOR] says is under it>"} or null}`;'),
)


def no_builtins(text: str) -> str:
    """`text` (references/own.md) with every mention of built-in procedures as something
    a script may emit taken out."""
    for old, new in _NO_BUILTINS:
        text = text.replace(old, new)
    return text


# -- reflexes (`--own-reflexes`) ------------------------------------------
#
# The model's tick layer. A procedure runs when the model calls it, between turns; what
# killed the runs happened INSIDE a plan, between one turn and the next (lava coming into
# view on a walk, a hole under a go_to, a mob at the back in a dig), where only the
# runner's guards act. A reflex script is the model's own guard: run every REFLEX_EVERY
# ticks on the live numbers, it may stop the plan, leave a note for the next turn and
# queue a short plan. Same subprocess contract as a procedure (state on stdin, JSON on
# stdout), so the model writes both the same way; quiet inside a screen and while a
# runner reflex (an escape) is in progress; a script that keeps failing is switched off
# until it is edited, so a broken reflex cannot cost a subprocess every 4 ticks all night.

REFLEX_DIR = Path("mine") / "reflexes"
REFLEX_EVERY = 4            # ticks between checks (the runner's own guards sample every 4th too)
REFLEX_TIMEOUT_S = 3.0
REFLEX_COOLDOWN = 40        # ticks a script stays quiet after it fired
REFLEX_MAX = 4              # scripts checked per tick, alphabetical
REFLEX_FAILS = 3            # consecutive failures that switch a script off until edited
REFLEX_ENTRY_CAP = 6        # a reflex's plan: entries
REFLEX_STEP_CAP = 120       # a reflex's plan: ticks


@dataclass
class OwnReflex:
    name: str
    path: Path
    doc: str = ""
    error: str | None = None
    mtime: float = 0.0


def scan_reflexes(root: Path) -> dict[str, OwnReflex]:
    """The scripts under `<root>/mine/reflexes/*.py`, by name; a file that does not
    parse is listed with its `error` (the [OWN] block shows it) and never run."""
    d = Path(root) / REFLEX_DIR
    out: dict[str, OwnReflex] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.py")):
        name = p.stem
        if name.startswith("_"):
            continue
        rx = OwnReflex(name=name, path=p)
        try:
            rx.mtime = p.stat().st_mtime
        except OSError:
            pass
        if not name.isidentifier():
            rx.error = "the file name must be a plain identifier (letters, digits, _)"
        else:
            try:
                rx.doc, _ = _first_doc_line(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as e:
                rx.error = f"does not parse: line {e.lineno}: {e.msg}"
            except OSError as e:
                rx.error = f"unreadable: {e}"
        out[name] = rx
    return out


def run_reflex(rx: OwnReflex, root: Path, state: dict[str, Any],
               timeout: float = REFLEX_TIMEOUT_S) -> tuple[dict[str, Any] | None, str | None]:
    """Run the script on the state; (None, None) when it stays quiet (nothing, `{}` or
    `{"fire": false}` on stdout), (result, None) when it fires (a JSON object with any
    of `stop`, `note`, `actions`), (None, why) on a failure."""
    if rx.error:
        return None, rx.error
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "MCU_OWN_REFLEX": rx.name,
    }
    try:
        cp = subprocess.run(
            [sys.executable, str(rx.path)], input=json.dumps(state), capture_output=True,
            text=True, cwd=str(root), env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout:.0f} s (a reflex reads the state and exits)"
    except OSError as e:
        return None, f"could not run: {e}"
    if cp.returncode != 0:
        tail = [ln for ln in (cp.stderr or "").splitlines() if ln.strip()]
        if not tail:
            return None, f"exit code {cp.returncode} (nothing on stderr)"
        return None, f"exit code {cp.returncode}: {tail[-1].strip()[:300]}"
    out = (cp.stdout or "").strip()
    if not out:
        return None, None
    if len(out) > OUTPUT_CAP:
        return None, f"printed {len(out)} bytes; a reflex prints one small JSON object"
    try:
        res = json.loads(out)
    except ValueError:
        return None, f"stdout is not JSON: {out[:120]!r}"
    if not isinstance(res, dict):
        return None, "stdout must be a JSON object"
    if not res or res.get("fire") is False:
        return None, None
    if not any(k in res for k in ("stop", "note", "actions")):
        return None, "a firing needs `stop`, `note` or `actions`"
    acts = res.get("actions")
    if acts is not None and not isinstance(acts, list):
        return None, "`actions` must be a list"
    return res, None


def reflex_block(reflexes: dict[str, OwnReflex], fires: dict[str, int],
                 off: dict[str, str]) -> str:
    """The reflex part of the [OWN] block: every script under mine/reflexes/, its index
    line and how often it fired, or why it is not running."""
    if not reflexes:
        return ""
    lines = ["[OWN] your own reflexes (mine/reflexes/*.py; run every "
             f"{REFLEX_EVERY} ticks while a plan executes):"]
    for name, rx in reflexes.items():
        if rx.error:
            lines.append(f"- `{name}` -- NOT running: {rx.error}")
        elif name in off:
            lines.append(f"- `{name}` -- switched OFF ({off[name]}); edit the file to run it again")
        else:
            lines.append(f"- `{name}` -- {rx.doc or '(no docstring)'} [fired {fires.get(name, 0)}x]")
    return "\n".join(lines)


#: The contract section (`--own-reflexes`), after MFM_OWN_NOTE. It names what to write
#: first: the four things that killed the earlier runs (the
#: self-harness arm may be TOLD what its harness is missing).
_REFLEX_NOTE = """\
**Your own reflexes.** A script at `mine/reflexes/<name>.py` is a REFLEX: the harness
runs it every 4 ticks WHILE YOUR PLAN EXECUTES (never inside a screen, never while the
runner's own escape is running), with the same STDIN state as a procedure plus
`lava_frac` (the share of the lower view that is lava, 0-1), `fire_frac` (the share
that is flame-coloured: a fire block or the burning overlay reads 5-15x `lava_frac`, a
lake 0.3-0.5x, the overlay over a pool 1.5-2.5x and a pool one block away 1.0-1.3x),
`hurt_100` (the health lost in the last 100 ticks, healing not counted: flames on screen
and `hurt_100` >= 1 is a burn), `in_lava` (true when your head is under lava: the view
is then a flat red that reads as neither of the two), `mainhand` (the item held), `health_prev` and
`pos_prev` (4 ticks ago), `entry` (the plan entry running: a procedure name or "raw"),
`atom` (inside one of your own procedures, the built-in or raw step it is running now;
otherwise the same as `entry`), `queue_len` and `runner_reflex`. It prints NOTHING (or `{}`) to stay quiet, and to
fire, ONE JSON object `{"stop": true, "note": "<why, one line>", "actions": [...]}`:
`stop` drops the rest of your plan, `note` reaches your next turn as `[REFLEX <name>]
...`, `actions` (optional: built-in procedures and raw actions, at most 6 entries and
120 ticks, never an own procedure) run at once through the same caps and checks. A
reflex that fired stays quiet for 40 ticks; one that fails (non-zero exit, 3 s
timeout, bad JSON) three times in a row is switched off until you edit it; at most 4
run, alphabetical; keep each under 50 ms -- read the state, not the logs. Reflexes
worth writing FIRST, from what killed earlier runs: lava coming into the lower view
while you walk or dig (stop, step back); a drop of 4+ blocks within a few ticks (stop,
look before moving); health falling with no lava in view (a mob -- stop a dig or a
sweep, pillar up or wall off); in the Nether, any walk with lava in view. {tail}
Write each firing down in mine/notes.md, keep the reflexes that saved you and delete
the ones that fired for nothing."""
_REFLEX_TAIL = {
    True: "The runner keeps its own guards for these; yours add what they miss, on the numbers you choose.",
    False: "The runner's guards are OFF in this run: your reflexes are the only tick layer.",
}
MFM_REFLEX_NOTE = _REFLEX_NOTE.replace("{tail}", _REFLEX_TAIL[True])


def reflex_note(harness_reflexes: bool) -> str:
    """The reflex contract with its last sentence true for this run (`--no-harness-reflexes`)."""
    return _REFLEX_NOTE.replace("{tail}", _REFLEX_TAIL[bool(harness_reflexes)])


#: `mine/working.md`: the model's own continuation note (VISTA's WORKING.md). Put in
#: front of it every turn ([WORKING]), it survives a context reset or compaction, so
#: the turn after one starts from the note, not from the log.
MFM_WORKING_NOTE = """\
**Working memory.** `mine/working.md` is yours and is put in front of you every turn
as `[WORKING]`: the plan you are on and why, its next visible prediction, the
contradictions you have not resolved, and the entries or frames you would re-open
(paths). It survives a context reset, so the turn after one starts from it instead of
from the log. Rewrite it when the plan changes, not every turn; keep it under 40
lines. `mine/GUIDE.md` is what is true of this world across
lives; `working.md` is what you are doing now."""
