"""Harness-generated beliefs -- sites, hazards, coverage -- and their verification.

The belief graph was written only by the model, so the facts the harness knows best
reached it only when the model chose to write them down. The audit of 16 from-scratch
runs found placed furnaces re-found by trial ("the furnace is likely one block below
the failed aim"), a shaft fallen into twice at the same coordinates, and one tunnel
extended for 8,700 ticks with a single sighting. These helpers turn the harness's own
channels -- positioned stat events, the damage interrupt, the mining macros' own
"broke N, advanced X" reports -- into location/state nodes that live in the same graph
as the model's beliefs (greppable, dependable-on) and are rendered as their own block
in the act prompt, and they let the discipline mark a location node *visited* when the
player actually stands within reach of the coordinates it names.

Pure functions. The agent calls them per event; scripts/replay_nodes.py replays a
landed run's artefacts through them so a change here can be judged on old trajectories
before it costs a wave.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

SITE_ITEMS = ("furnace", "crafting_table")
#: A placement within this many blocks of an existing site of the same item is the
#: same site re-placed (the table is carried and re-placed at each new base).
SITE_MERGE_RADIUS = 4.0
#: Hits within this radius and this many steps of an earlier hit are one hazard.
HIT_MERGE_RADIUS = 4.0
HIT_MERGE_STEPS = 400
#: "Visited": the player stood within this many blocks (each axis) of the coordinates.
VISIT_RADIUS = 3.0

_COORD3 = re.compile(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)")
_COORD2 = re.compile(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)")


def norm_yaw(yaw: float) -> float:
    return ((float(yaw) + 180.0) % 360.0) - 180.0


def parse_coords(text: str) -> tuple[float, float | None, float] | None:
    """The first (x, y, z) or (x, z) coordinate group in a statement, or None."""
    m = _COORD3.search(text or "")
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    m = _COORD2.search(text or "")
    if m:
        return float(m.group(1)), None, float(m.group(2))
    return None


def near(pos: dict[str, float], coords: tuple[float, float | None, float],
         radius: float = VISIT_RADIUS) -> bool:
    x, y, z = coords
    if abs(pos["x"] - x) > radius or abs(pos["z"] - z) > radius:
        return False
    return y is None or abs(pos["y"] - y) <= radius


def _at(pos: dict[str, float]) -> str:
    return f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})"


def site_statement(item: str, pos: dict[str, float], step: int, times: int = 1) -> str:
    again = f" (placed {times} times here)" if times > 1 else ""
    return (f"Harness: a {item} was placed at step {step} within ~2 blocks of {_at(pos)}"
            f"{again} -- you stood there facing yaw {norm_yaw(pos.get('yaw', 0.0)):.0f}. "
            f"Open it with look_at + use_until_gui from within reach.")


def vein_statement(ore: str, pos: dict[str, float], step: int, count: int = 1) -> str:
    """`ore` is the block name without the deepslate_ prefix, e.g. iron_ore."""
    what = ore.replace("_ore", " ore")
    return (f"Harness: {what} mined at step {step} within ~3 blocks of {_at(pos)} "
            f"({count} block{'s' if count != 1 else ''} here so far); veins run 2-8 blocks "
            f"-- check every face of that hole before leaving.")


def retired_site_statement(statement: str, step: int) -> str:
    return f"{statement} PICKED UP again at step {step} -- no longer there."


def death_statement(pos: dict[str, float], step: int) -> str:
    return (f"Harness: you DIED at {_at(pos)} at step {step}; everything carried dropped "
            f"there and despawns ~6000 ticks later.")


def lava_statement(pos: dict[str, float], step: int, frac: float, count: int = 1) -> str:
    times = f" (seen {count} times)" if count > 1 else ""
    return (f"Harness: LAVA in view at step {step} from {_at(pos)} facing yaw "
            f"{norm_yaw(pos.get('yaw', 0.0)):.0f} ({100 * frac:.0f}% of the lower view)"
            f"{times} -- do not walk or dig toward it; seal a flow with cobblestone and "
            f"tunnel elsewhere.")


def hit_statement(pos: dict[str, float], step: int, damage: float, count: int = 1,
                  first_step: int | None = None, total: float | None = None) -> str:
    if count <= 1:
        return (f"Harness: took {damage:.0f} damage at {_at(pos)} at step {step} -- "
                f"something hurts you here (a monster, a drop, lava, or drowning).")
    return (f"Harness: took damage {count} times near {_at(pos)} (steps "
            f"{first_step}-{step}, {total:.0f} hp in total) -- something here keeps "
            f"hurting you; do not stand still in it.")


def coverage_statement(records: list[dict[str, Any]], last_ore_step: int | None,
                       sightings: int) -> str:
    since = (f"since the last iron ore (step {last_ore_step})" if last_ore_step
             else "with no iron ore mined yet")
    if not records:
        return f"Harness coverage {since}: no mining macro has finished."
    n = len(records)
    broken = sum(int(r["broken"]) for r in records)
    adv = sum(float(r["advanced"]) for r in records)
    by_y = Counter(int(round(float(r["y"]))) for r in records)
    by_h = Counter(int(round(norm_yaw(r["yaw"]) / 45.0) * 45) % 360 for r in records)
    ylist = ", ".join(f"y{y} x{c}" for y, c in sorted(by_y.items(), key=lambda kv: -kv[1])[:4])
    hlist = ", ".join(f"yaw {h} x{c}" for h, c in sorted(by_h.items(), key=lambda kv: -kv[1])[:4])
    last = records[-1]
    return (f"Harness coverage {since}: {n} mining macro(s), {broken} blocks broken, "
            f"{adv:.0f} blocks advanced; by level: {ylist}; headings: {hlist}; "
            f"ore-watcher sightings {sightings}. Last: {last['label']} at "
            f"y{float(last['y']):.0f} heading {norm_yaw(last['yaw']):.0f}, broke "
            f"{int(last['broken'])} / advanced {float(last['advanced']):.1f} "
            f"(step {last['step']}).")


def approach_line(rules_path: Path | str) -> str | None:
    """The `APPROACH:` verdict the induction pass pins at the top of rules.md."""
    p = Path(rules_path)
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip().lstrip("-*# ").strip()
        if not s:
            continue
        if s.upper().startswith("APPROACH:"):
            return s[:400]
        return None
    return None


def render_block(graph, pos: dict[str, float] | None, now_step: int,
                 visits: dict[str, int] | None = None, max_sites: int = 4,
                 max_hazards: int = 3) -> str:
    """The harness-facts block for the act prompt: live sites, nearby/recent hazards,
    the coverage line. Separate from the 12-slot view so the model's own nodes never
    crowd these out, and they never crowd the model's out."""
    visits = visits or {}
    nodes = graph.nodes

    def dist(node) -> float:
        """Chebyshev distance on every axis the statement names -- a furnace 1 block
        over and 32 blocks UP (kd20z's, read from y21) is 32 away, not 1."""
        c = parse_coords(node.statement)
        if not c or pos is None:
            return 1e9
        d = max(abs(pos["x"] - c[0]), abs(pos["z"] - c[2]))
        if c[1] is not None:
            d = max(d, abs(pos["y"] - c[1]))
        return d

    def tag(node) -> str:
        bits = []
        if node.id in visits:
            bits.append(f"visited at step {visits[node.id]}")
        frames = [e[len("frame: "):] for e in node.evidence if e.startswith("frame: ")]
        if frames:
            bits.append(f"frame: {frames[-1]}")
        d = dist(node)
        if d < 1e8:
            c = parse_coords(node.statement)
            dy = (pos["y"] - c[1]) if (c and c[1] is not None and pos) else 0.0
            updown = (f", {abs(dy):.0f} {'below' if dy > 0 else 'above'} you"
                      if abs(dy) >= 3.0 else "")
            bits.append(f"{d:.0f} blocks away{updown}")
        return f" [{', '.join(bits)}]" if bits else ""

    sites = sorted((n for n in nodes.values()
                    if n.id.startswith("site_") and n.status == "active"),
                   key=lambda n: -n.updated_step)[:max_sites]
    veins = sorted((n for n in nodes.values() if n.id.startswith("vein_")),
                   key=lambda n: (dist(n) > 30.0, -n.updated_step))[:max_sites]
    hazards = sorted((n for n in nodes.values() if n.id.startswith("hazard_")),
                     key=lambda n: (dist(n) > 30.0, -n.updated_step))[:max_hazards]
    cov = nodes.get("coverage_since_ore")
    lines = [f"- {n.statement}{tag(n)}" for n in sites]
    lines += [f"- {n.statement}{tag(n)}" for n in veins]
    lines += [f"- {n.statement}{tag(n)}" for n in hazards]
    if cov is not None:
        lines.append(f"- {cov.statement}")
    return "\n".join(lines)
