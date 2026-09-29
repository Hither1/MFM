"""MCU's side of the append-only episode log.

The writer itself (`mfm.memory.log.EpisodeLog`: sections, attachments, the plan and note
blocks, the window and stateless ablations, `publish`) moved to the shared `mfm`
package. What stays here is what is Minecraft: how a section is rendered from the
simulator state (`state_block`, the `[STATE]`/`[INV]`/`[HOTBAR]`/`[GUI]`/`[VITALS]`/
`[MOBS]`/`[GOALS]` lines), the milestone checklist, and the two section renderers the
agent uses (`initial_section`, `action_section`). `EpisodeLog` below keeps the original
MCU method signatures for any caller that still uses them; the agent itself calls the
shared writer with the rendered lines.

The markers are the ones `prompts.py` declares, and the section separator is the same
80-`=` rule PRO-LONG uses, because the log-window ablation splits on it.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from mfm.memory.log import SEPARATOR, prepare_workspace  # noqa: F401  (re-exported)
from mfm.memory.log import EpisodeLog as _SharedEpisodeLog

from prolong_mc._loguru_bridge import bridge_to_loguru

bridge_to_loguru()

# The log names its own frames, so the log decides which of them the agent may see.
_FRAME_RE = re.compile(r"^\[FRAME\] (\S+)", re.M)

# Written by the harness, not by the agent, and required for the turn to happen at all.
_HARNESS_FILES = {"logs.txt", "AGENTS.md"}


def _xz(pos: dict[str, Any] | None) -> tuple[float, float] | None:
    if not isinstance(pos, dict):
        return None
    x, z = pos.get("x"), pos.get("z")
    return (float(x), float(z)) if x is not None and z is not None else None


def state_line(pos: dict[str, Any] | None, prev: dict[str, Any] | None) -> str:
    """`[STATE] pos=(x, y, z) pitch=P yaw=Y moved=D` — the log's load-bearing line."""
    if not isinstance(pos, dict) or pos.get("x") is None:
        return "[STATE] unavailable"
    here, before = _xz(pos), _xz(prev)
    moved = math.dist(here, before) if here and before else 0.0
    return (
        f"[STATE] pos=({pos['x']:.2f}, {pos.get('y', 0.0):.2f}, {pos['z']:.2f}) "
        f"pitch={pos.get('pitch', 0.0):.0f} yaw={pos.get('yaw', 0.0):.0f} "
        f"moved={moved:.2f}"
    )


def _inventory_counts(info: dict[str, Any]) -> dict[str, int]:
    """`info['inventory']` aggregated to {item: total}.

    The wire shape is slot-keyed -- `{slot_id: {"type": name, "quantity": n}}` across 36
    slots -- so aggregating is required, not cosmetic: read as {item: count} it yields slot
    indices as item names. `air`/`none` are dropped because empty slots report as one of
    them, and a model shown the raw dict concludes it is carrying thirty air.
    """
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return {}
    out: dict[str, int] = {}
    for slot in inv.values():
        if not isinstance(slot, dict):
            continue
        name = str(slot.get("type") or "")
        if not name or name in ("air", "none"):
            continue
        try:
            qty = int(float(slot.get("quantity", 0)))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            out[name] = out.get(name, 0) + qty
    return out


def _hotbar(info: dict[str, Any]) -> str:
    """Slots 0-8, named by the key that selects them.

    The number matters, not just the contents: mining stone needs a pickaxe *selected*,
    and `hotbar.N` is how. The frame does show the hotbar, but reading item icons off it
    is exactly the visual inference this channel exists to replace.
    """
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return ""
    parts = []
    for slot in range(9):
        entry = inv.get(str(slot), inv.get(slot))
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("type") or "")
        if not name or name in ("air", "none"):
            continue
        try:
            qty = int(float(entry.get("quantity", 0)))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            parts.append(f"hotbar.{slot + 1}={name}x{qty}")
    return ", ".join(parts)


def _hotbar_slots(info: dict[str, Any]) -> dict[str, str]:
    """`_hotbar` as a dict, `{"1": "spruce_log x3", ...}`, for the episode store."""
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return {}
    out: dict[str, str] = {}
    for slot in range(9):
        entry = inv.get(str(slot), inv.get(slot))
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("type") or "")
        if not name or name in ("air", "none"):
            continue
        try:
            qty = int(float(entry.get("quantity", 0)))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            out[str(slot + 1)] = f"{name} x{qty}"
    return out


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def state_block(pos: dict[str, Any] | None, prev: dict[str, Any] | None,
                info: dict[str, Any] | None = None) -> str:
    """`state_line` plus the rest of the simulator state, as bracketed grep handles.

    Added for the MCU port. Upstream's benchmark hands the agent its materials and places
    the crafting table for it, so pose was the whole of the state that mattered; MCU's two
    long-horizon tasks start from nothing and gate 9 of 10 milestones behind the inventory
    GUI, where an agent that cannot read its own item counts is running open loop.

    It goes in the log rather than the turn prompt because that is PRO-LONG's mechanism:
    `build_turn_prompt` deliberately carries almost nothing and points at `logs.txt`. Every
    section carries the whole block so a `tail` is sufficient -- writing only the deltas
    would make the current inventory something the agent has to `grep` backwards for,
    which is a handicap the comparison arm does not have.

    Reads the simulator's own shapes, since that is what the green agent forwards. Every
    line is omitted when its field is absent, so a green agent that does not send the
    extended observation degrades to exactly the old single line.
    """
    lines = [state_line(pos, prev)]
    info = info or {}

    inv = _inventory_counts(info)
    if "inventory" in info:
        lines.append("[INV] " + (", ".join(f"{k} x{v}" for k, v in sorted(inv.items())) or "empty"))
        lines.append("[HOTBAR] " + (_hotbar(info) or "empty"))

    gui = info.get("isGuiOpen")
    mainhand = ((info.get("equipped_items") or {}).get("mainhand") or {}).get("type")
    if gui is not None or mainhand:
        bits = []
        if gui is not None:
            bits.append(f"open={bool(gui)}")
        if mainhand:
            bits.append(f"mainhand={mainhand}")
        lines.append(f"[GUI] {' '.join(bits)}")

    stats = info.get("location_stats") or {}
    bits = []
    for label, key, src in (("health", "health", info), ("food", "food_level", info),
                            ("light", "light_level", stats)):
        v = _num(src.get(key))
        if v is not None:
            bits.append(f"{label}={v:.0f}")
    if stats.get("can_see_sky") is not None:
        bits.append(f"sky={str(stats['can_see_sky']).lower() == 'true'}")
    if bits:
        lines.append(f"[VITALS] {' '.join(bits)}")

    mobs = info.get("mobs")
    if isinstance(mobs, list) and mobs:
        names: dict[str, int] = {}
        for m in mobs:
            n = str((m.get("name") or m.get("type") or "?") if isinstance(m, dict) else m)
            names[n] = names.get(n, 0) + 1
        top = sorted(names.items(), key=lambda kv: -kv[1])[:8]
        lines.append("[MOBS] " + ", ".join(f"{n}x{c}" for n, c in top))

    # Compact, because it is written into every section: how many of the ordered
    # milestones the environment has verified, and which one is next. The full checklist
    # with each milestone's event and objects is static task definition, so it is written
    # once into the INITIAL STATE section -- which `windowed_copy` always keeps -- rather
    # than repeated some thousands of times.
    spec = info.get("milestone_spec")
    if isinstance(spec, list) and spec:
        done = [m["identity"] for m in spec if m.get("done")]
        todo = [m for m in spec if not m.get("done")]
        nxt = (f"next: {todo[0]['identity']} ({todo[0].get('event')}: "
               f"{', '.join(todo[0].get('objects') or [])})") if todo else "ALL VERIFIED"
        got = f"done: {', '.join(done)}" if done else "done: none"
        lines.append(f"[GOALS] {len(done)}/{len(spec)} | {got} | {nxt}")

    return "\n".join(lines)


def milestone_checklist(spec: list | None) -> str:
    """The full ordered checklist, written once into the INITIAL STATE section.

    Showing the unmet ones is what stops the agent re-deriving the tech tree every turn,
    and naming each one's `event` is what tells it that `iron_ingot` is scored on a pickup
    rather than a craft. `[GOALS]` in every later section carries the progress against it.
    """
    if not spec:
        return ""
    out = ["[MILESTONES] the environment scores these, in order:"]
    for rule in spec:
        out.append(f"  [ ] {rule.get('identity')} <- {rule.get('event')}: "
                   f"{', '.join(rule.get('objects') or [])}")
    return "\n".join(out)


# -- section renderers ---------------------------------------------------------------

def initial_section(task_text: str, pos: dict | None, frame_name: str | None,
                    info: dict | None = None) -> tuple[str, list[str]]:
    """The INITIAL STATE section: task, the full milestone checklist (written once,
    which `windowed_copy` always keeps), the state block, the first frame."""
    lines = [f"Task: {task_text}"]
    checklist = milestone_checklist((info or {}).get("milestone_spec"))
    if checklist:
        lines.append(checklist)
    lines.append(state_block(pos, None, info))
    if frame_name:
        lines.append(f"[FRAME] {frame_name}")
    return "Action 0 | Step 0 | INITIAL STATE", lines


def action_section(
    *,
    action_num: int,
    step: int,
    entry_desc: str,
    pos: dict | None,
    prev_pos: dict | None,
    frame_name: str | None,
    milestone_note: str = "",
    plan_step: tuple[int, int] | None = None,
    verified: str | None = None,
    info: dict | None = None,
    subgoal: str = "",
) -> tuple[str, list[str]]:
    """One section per environment tick: (header, lines).

    The header carries what upstream's carries: the plan step this tick belongs to and,
    under the hint protocol, the environment's verification state -- upstream's
    `Score:`. Under the no-hint protocol `verified` is None and the field is absent. The
    subgoal goes in the header rather than a block so `grep '^Action'` yields the whole
    history of what the agent has been trying as one compact table.
    """
    header = f"Action {action_num} | Step {step}"
    if plan_step:
        header += f" | Plan Step {plan_step[0]}/{plan_step[1]}"
    if verified is not None:
        header += f" | Verified: {verified}"
    if subgoal:
        header += f" | Subgoal: {subgoal[:120]}"
    lines = [f"Tool Call: {entry_desc}", state_block(pos, prev_pos, info)]
    if frame_name:
        lines.append(f"[FRAME] {frame_name}")
    if milestone_note:
        lines.append(milestone_note)
    return header, lines


def make_log(record_dir: Path | str, stateless: bool = False) -> _SharedEpisodeLog:
    """The shared writer configured as MCU's log: FRAME attachments under `frames/`,
    and the plan repeated in every section until the next analysis replaces it."""
    return _SharedEpisodeLog(record_dir, attachment_markers=("FRAME",),
                             attachment_dirs=("frames",), stateless=stateless,
                             persistent_plan=True)


class EpisodeLog(_SharedEpisodeLog):
    """The original MCU interface over the shared writer, for callers that still use
    `save_frame` / `write_initial(task, pos, frame, info)` / `write_action(...)`."""

    def __init__(self, workspace: Path, stateless: bool = False):
        super().__init__(workspace, attachment_markers=("FRAME",), attachment_dirs=("frames",),
                         stateless=stateless, persistent_plan=True)
        self.workspace = self.record_dir
        self.frames_dir = self.record_dir / "frames"

    def save_frame(self, step: int, png_bytes: bytes) -> str:
        return self.save_attachment(f"frames/step_{step:04d}.png", png_bytes)

    def write_initial(self, task_text: str, pos: dict | None, frame_name: str | None,  # type: ignore[override]
                      info: dict | None = None) -> None:
        super().write_initial(*initial_section(task_text, pos, frame_name, info))

    def write_action(self, *, action_num: int, **kw: Any) -> None:
        title, lines = action_section(action_num=action_num, **kw)
        super().write_section(title, lines, plans_title=f"Action {action_num}")

    def publish(self, visible: Path, window: int | None, stateless: bool,  # type: ignore[override]
                current_frame: str | None = None) -> dict:
        return super().publish(visible, window, stateless, current=current_frame)
