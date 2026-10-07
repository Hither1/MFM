#!/usr/bin/env python3
"""Which milestones each skill-reuse probe task (coal_torches_vein, iron_shield_vein)
shares with the diamond task and which are its own, read from the task configs.

    python scripts/plot_probe_milestones.py [--out figures/probe_milestones]

The diamond task's milestones are the columns, in config order. Two milestones are the
same one when their `objects` overlap (the identities differ: `mine_cobblestone` there,
`cobblestone` here). A shared milestone whose event or object list differs from the
diamond task's is marked with a dagger.

The probes start from a kit (`/give` in `custom_init_commands`): a diamond milestone
whose item is in the kit is drawn as handed over, not scored. They also start with a
vein of their ore placed underground (`fill` in `custom_init_commands`) and named in
the task text: the milestone that mines it is marked with a double dagger.
Writes probe_milestones.pdf and a PNG preview.
"""
import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "MCU" / "MCU_benchmark" / "task_configs" / "tasks"
OUT = ROOT / "figures" / "probe_milestones"

SOURCE = "mine_diamond_from_scratch"
PROBES = ["coal_torches_vein", "iron_shield_vein"]
NAMES = {SOURCE: "Diamond", "coal_torches_vein": "Coal torches",
         "iron_shield_vein": "Iron shield"}
# Tile text by identity; a shared milestone takes the diamond task's identity.
LABELS = {
    "mine_log": "log", "crafting_table": "crafting\ntable", "wooden_pickaxe": "wooden\npickaxe",
    "mine_cobblestone": "cobble-\nstone", "stone_pickaxe": "stone\npickaxe",
    "mine_iron_ore": "iron\nore", "furnace": "furnace", "iron_ingot": "iron\ningot",
    "iron_pickaxe": "iron\npickaxe", "diamond": "diamond", "mine_coal_ore": "coal\nore",
    "torch": "torch", "shield": "shield",
}

INK, INK2, MUTED, RULE, EMPTY = "#0b0b0b", "#52514e", "#898781", "#c3c2b7", "#dddcd5"
SHARED, SHARED_FILL = "#2a78d6", "#cde2fb"
OWN, OWN_FILL = "#eb6834", "#fbdccf"
GIVEN, GIVEN_FILL = "#a3a29a", "#eeede8"

# Inches.
PITCH, TILE_W, TILE_H, ROW_GAP = 0.49, 0.45, 0.36, 0.08
LEFT, ZONE_GAP, MARGIN = 1.02, 0.20, 0.06
LEGEND_LINE, NOTE_LINE = 0.17, 0.15
CHAR = 0.056        # a 6.5 pt character, for breaking the legend before the figure exists

_GIVE = re.compile(r"^/give \S+ minecraft:(\w+)")
_FILL = re.compile(r"\bfill\b.*\bminecraft:(\w+)")


def config(task):
    return yaml.safe_load((TASKS / task / f"{task}.yaml").read_text())


def milestones(task):
    return config(task)["milestone_reward_cfg"]


def kit(task):
    """The items the task hands over at the start."""
    return {m.group(1) for c in config(task).get("custom_init_commands") or []
            if (m := _GIVE.match(c))}


def placed(task):
    """The blocks the task places in the world at the start."""
    return {m.group(1) for c in config(task).get("custom_init_commands") or []
            if (m := _FILL.search(c))}


def compare(source, probe):
    """({source index: probe milestone}, [probe milestones the source lacks])."""
    shared, own = {}, []
    for m in probe:
        hit = [i for i, s in enumerate(source) if set(s["objects"]) & set(m["objects"])]
        if hit:
            shared[hit[0]] = m
        else:
            own.append(m)
    return shared, own


def same_rule(a, b):
    return a["event"] == b["event"] and set(a["objects"]) == set(b["objects"])


def label(identity):
    return LABELS.get(identity, identity.replace("_", "\n", 1))


def tile(ax, x, y, text=None, edge=EMPTY, fill="none", dagger=False, vein=False, ink=INK,
         w=TILE_W, h=TILE_H, lw=0.8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.045",
                                facecolor=fill, edgecolor=edge, linewidth=lw))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.5,
                color=ink, linespacing=0.95)
    if dagger:
        ax.text(x + w - 0.03, y + h - 0.025, "†", ha="right", va="top", fontsize=6, color=INK2)
    if vein:
        ax.text(x + 0.03, y + h - 0.025, "‡", ha="left", va="top", fontsize=6, color=INK2)


def row_label(ax, y, task, note):
    ax.text(MARGIN, y + TILE_H / 2 + 0.065, NAMES.get(task, task), ha="left", va="center",
            fontsize=8, fontweight="bold", color=INK)
    ax.text(MARGIN, y + TILE_H / 2 - 0.075, note, ha="left", va="center", fontsize=6.5, color=MUTED)


def legend_lines(entries, width):
    """The legend entries broken into lines that fit the figure."""
    lines, x = [[]], MARGIN
    for e in entries:
        w = 0.22 + len(e[3]) * CHAR + 0.22
        if lines[-1] and x + w - 0.22 > width - MARGIN:
            lines.append([])
            x = MARGIN
        lines[-1].append(e)
        x += w
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    source = milestones(SOURCE)
    rows = []
    for task in PROBES:
        shared, own = compare(source, milestones(task))
        given = {i for i, s in enumerate(source) if i not in shared and set(s["objects"]) & kit(task)}
        rows.append((task, shared, own, given, placed(task)))
    daggers = any(not same_rule(source[i], m) for _, shared, *_ in rows for i, m in shared.items())
    veins = any(set(m["objects"]) & ore for _, shared, own, _, ore in rows
                for m in [*shared.values(), *own])
    kits = any(given for *_, given, _ in rows)

    own_x = LEFT + len(source) * PITCH + ZONE_GAP
    width = own_x + max(len(own) for _, _, own, *_ in rows) * PITCH - (PITCH - TILE_W) + MARGIN
    entries = [(SHARED, SHARED_FILL, 0.8, "shared with Diamond"),
               (OWN, OWN_FILL, 0.8, "new in this task")]
    if kits:
        entries.append((GIVEN, GIVEN_FILL, 0.8, "handed over at the start, not scored"))
    entries.append((EMPTY, "none", 0.5, "Diamond milestone the task does not score"))
    legend = legend_lines(entries, width)
    notes = []
    if daggers:
        notes.append("†  same item, scored on a different game event or block list than in Diamond")
    if veins:
        notes.append("‡  a vein of this ore is placed underground at the start; the task text gives "
                     "its coordinates")
    foot = 0.31 + (len(legend) - 1) * LEGEND_LINE + len(notes) * NOTE_LINE
    height = 0.05 + 0.20 + TILE_H + 0.16 + len(rows) * (TILE_H + ROW_GAP) - ROW_GAP + 0.12 + foot

    plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42})
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, width), ylim=(0, height), aspect="equal")
    ax.axis("off")

    y = height - 0.05 - 0.10
    ax.text(LEFT, y, "Milestones of the Diamond task", ha="left", va="center", fontsize=7, color=INK2)
    ax.text(own_x, y, "Not in Diamond", ha="left", va="center", fontsize=7, color=INK2)

    y -= 0.10 + TILE_H
    row_label(ax, y, SOURCE, f"{len(source)} milestones")
    for i, s in enumerate(source):
        tile(ax, LEFT + i * PITCH, y, label(s["identity"]), SHARED, SHARED_FILL)

    y -= 0.08
    ax.plot([MARGIN, width - MARGIN], [y, y], color=RULE, linewidth=0.5, solid_capstyle="butt")
    y += 0.08 - 0.16 + ROW_GAP

    for task, shared, own, given, ore in rows:
        y -= TILE_H + ROW_GAP
        row_label(ax, y, task, f"{len(shared)} shared · {len(own)} new")
        for i, s in enumerate(source):
            if i in shared:
                tile(ax, LEFT + i * PITCH, y, label(s["identity"]), SHARED, SHARED_FILL,
                     dagger=not same_rule(s, shared[i]),
                     vein=bool(set(shared[i]["objects"]) & ore))
            elif i in given:
                tile(ax, LEFT + i * PITCH, y, label(s["identity"]), GIVEN, GIVEN_FILL, ink=INK2)
            else:
                tile(ax, LEFT + i * PITCH, y, lw=0.5)
        for j, m in enumerate(own):
            tile(ax, own_x + j * PITCH, y, label(m["identity"]), OWN, OWN_FILL,
                 vein=bool(set(m["objects"]) & ore))

    y -= 0.12 + 0.11
    for line in legend:
        x = MARGIN
        for edge, fill, lw, text in line:
            tile(ax, x, y - 0.055, edge=edge, fill=fill, w=0.17, h=0.11, lw=lw)
            t = ax.text(x + 0.22, y, text, ha="left", va="center", fontsize=6.5, color=INK2)
            x = t.get_window_extent(fig.canvas.get_renderer()).x1 / fig.dpi + 0.22
        y -= LEGEND_LINE
    y += LEGEND_LINE
    for k, note in enumerate(notes, start=1):
        ax.text(MARGIN, y - 0.02 - k * NOTE_LINE, note, ha="left", va="center", fontsize=6.5,
                color=INK2)

    args.out.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out / "probe_milestones.pdf")
    fig.savefig(args.out / "probe_milestones.png", dpi=300)
    print(f"{width:.2f} x {height:.2f} in -> {args.out / 'probe_milestones.pdf'}")
    for task, shared, own, given, ore in rows:
        changed = [m["identity"] for i, m in shared.items() if not same_rule(source[i], m)]
        print(f"{task}: {len(shared)} shared, new {[m['identity'] for m in own]}, "
              f"rule differs {changed}, handed over {[source[i]['identity'] for i in sorted(given)]}, "
              f"placed {sorted(ore)}")


if __name__ == "__main__":
    main()
