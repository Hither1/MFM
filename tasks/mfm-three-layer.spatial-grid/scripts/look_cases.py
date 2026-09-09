#!/usr/bin/env python3
"""Find and bundle the turns where the model LOOKED at a frame (view_image, a zoom crop,
a then-now sheet) -- the raw material for the "looking decided it" showcase.

    python look_cases.py list <MCU dir> <arm> [--min-score 2]
    python look_cases.py dump <MCU dir> <arm> <turn> [<turn> ...] --out <dir>

`list` prints one line per look turn: turn, step, what was looked at, the sentence the
model wrote after looking, what the next turn observed, and any milestone banked within
the next 5 turns. `dump` writes, per turn, a folder holding the complete exchange:

    prompt.txt               the turn message the harness sent (the frame was attached)
    transcript.md            every model message and command of the turn, in order, with
                             each command's output head
    frame_before_<step>.jpg  the exact 640x360 frame the model saw (hires record)
    frame_after_<step>.jpg   the frame at the next turn's step
    look_outputs/            the crop / sheet files the look produced, when still on disk
    plan.json                the actions.json the turn wrote (from the events)
    executed.log             the logs.txt segment the plan produced (entries, [STATE],
                             [EVENT], [NOTE]) up to the next turn
    next_turn.md             the next turn's OBSERVED vs EXPECTED and [PLAN]
    case.json                the same, structured

Written 2026-09-09; the fields to keep for the dataset are the user's call.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
from pathlib import Path

LOOK = re.compile(r"view_image|zoom\.py|then-now")
HEREDOC = re.compile(r"<<'?(\w+)'?\n.*?\n\1", re.S)   # apply_patch / cat bodies: text, not a look


def shell_part(cmd: str) -> str:
    """The command with heredoc bodies removed (a working.md that mentions then-now is
    not a look)."""
    return HEREDOC.sub("<<heredoc>>", cmd)


def is_look(it: dict) -> bool:
    return it.get("type") == "command_execution" and bool(LOOK.search(shell_part(it.get("command", ""))))
VISUAL_VERB = re.compile(r"confirm|match|shows|visible|see |saw|identif|reveal|recogni|close-up|crop|sheet|comparison|frame", re.I)


def turn_items(ep: Path, n: int) -> list[dict]:
    f = ep / "codex_turns" / f"turn_{n:04d}.events.jsonl"
    if not f.exists():
        return []
    ev = [json.loads(l) for l in open(f) if l.strip()]
    return [e["item"] for e in ev if e.get("type") == "item.completed"]


def turn_step(ep: Path, n: int) -> int | None:
    p = ep / "codex_turns" / f"turn_{n:04d}.prompt.txt"
    if not p.exists():
        return None
    m = re.search(r"Step (\d+)", p.read_text(errors="replace"))
    return int(m.group(1)) if m else None


def milestones(mcu: Path, arm: str) -> list[tuple[str, int]]:
    log = mcu / "logs" / f"{arm}_purple.log"
    if not log.exists():
        return []
    return [(m.group(1), int(m.group(2))) for m in
            re.finditer(r"\[milestone\] (\w+) at step (\d+)", log.read_text(errors="replace"))]


def look_turns(ep: Path) -> list[int]:
    out = []
    for f in sorted(glob.glob(str(ep / "codex_turns" / "turn_*.events.jsonl"))):
        n = int(Path(f).name[5:9])
        if any(is_look(it) for it in turn_items(ep, n)):
            out.append(n)
    return out


def look_summary(items: list[dict]) -> tuple[str, str]:
    """(what was looked at, the first visual sentence after the look)."""
    cmd, after = "", ""
    for i, it in enumerate(items):
        if is_look(it):
            c = shell_part(it["command"]).replace("\n", " ")
            m = re.search(r"(view_image \S+|zoom\.py [^;\"']+|episodes\.py[^;\"']*then-now[^;\"']*)", c)
            cmd = (m.group(1) if m else c)[:140]
            for later in items[i + 1:]:
                if later.get("type") == "agent_message":
                    sents = re.split(r"(?<=[.!?])\s+", later.get("text", "").replace("\n", " "))
                    hit = next((s for s in sents if VISUAL_VERB.search(s)), sents[0] if sents else "")
                    after = hit.strip()[:220]
                    break
            break
    return cmd, after


def observed_of(items: list[dict]) -> str:
    for it in items:
        if it.get("type") == "agent_message" and "OBSERVED vs EXPECTED" in it.get("text", ""):
            return it["text"].split("\n")[0][:240]
    return ""


def cmd_list(mcu: Path, arm: str, min_score: int) -> None:
    ep = mcu / "output" / arm / "episode_001"
    ms = milestones(mcu, arm)
    for n in look_turns(ep):
        items = turn_items(ep, n)
        step = turn_step(ep, n)
        nxt_step = turn_step(ep, n + 1)
        cmd, after = look_summary(items)
        nxt = observed_of(turn_items(ep, n + 1))
        banked = [name for name, s in ms if step is not None and nxt_step is not None
                  and step <= s <= (turn_step(ep, n + 6) or s)]
        score = (1 if after else 0) + (1 if banked else 0) + (1 if "then-now" in cmd or "zoom" in cmd else 0)
        if score < min_score:
            continue
        print(f"T{n:04d} step {step} score {score} | {cmd}\n   after: {after}\n   next: {nxt}"
              + (f"\n   banked within 5 turns: {banked}" if banked else ""))


def regen_then_now(ep: Path, c: str, step: int, d: Path) -> None:
    """Re-run the turn's `episodes.py ... --then-now` with the frame the model had, into
    the bundle (the model's own sheet went to then_now.png in memory/ and was overwritten)."""
    import shlex
    import subprocess
    inner = c
    if re.match(r"\S*bash -lc ", c):                       # codex wraps the cell: bash -lc '<script>'
        try:
            inner = shlex.split(c)[-1]
        except ValueError:
            inner = c.replace('\\"', '"').replace("\\'", "'")
    seg = next((s for s in re.split(r"\s*(?:;|&&|\|\|)\s*", inner) if "then-now" in s), None)
    if not seg:
        return
    try:
        argv = shlex.split(seg)
    except ValueError:
        return
    i = next((k for k, a in enumerate(argv) if a.endswith("episodes.py")), None)
    if i is None:
        return
    args = argv[i + 1:]
    for flag in ("--out", "--now", "--sheet"):
        while flag in args:
            k = args.index(flag)
            del args[k:k + 2]
    frame = (ep / "hires" / f"{step:07d}.jpg").resolve()      # the tool runs in memory/
    if not frame.exists():
        return
    (d / "look_outputs").mkdir(exist_ok=True)
    out = (d / "look_outputs" / "then_now_regenerated.png").resolve()
    try:
        subprocess.run(["python3", "tools/episodes.py", *args, "--now", str(frame), "--out", str(out)],
                       cwd=ep / "memory", capture_output=True, text=True, timeout=120)
    except Exception:
        return


def cmd_dump(mcu: Path, arm: str, turns: list[int], out: Path) -> None:
    ep = mcu / "output" / arm / "episode_001"
    log_text = (ep / "memory" / "logs.txt").read_text(errors="replace")
    for n in turns:
        items = turn_items(ep, n)
        step = turn_step(ep, n)
        nxt_step = turn_step(ep, n + 1)
        d = out / f"{arm}_turn{n:04d}_step{step}"
        d.mkdir(parents=True, exist_ok=True)
        prompt = ep / "codex_turns" / f"turn_{n:04d}.prompt.txt"
        if prompt.exists():
            shutil.copy(prompt, d / "prompt.txt")
        lines = [f"# {arm} turn {n} (step {step})\n"]
        plan = None
        for it in items:
            if it.get("type") == "agent_message":
                lines.append("## model\n\n" + it.get("text", "").strip() + "\n")
            elif it.get("type") == "command_execution":
                c = it.get("command", "")
                lines.append("## command (exit %s)\n\n```\n%s\n```\n" % (it.get("exit_code"), c.strip()))
                o = (it.get("aggregated_output") or "").strip()
                if o:
                    lines.append("output head:\n\n```\n" + o[:1500] + ("\n..." if len(o) > 1500 else "") + "\n```\n")
                m = re.search(r"actions\.json\n\+(\{.*?\})\n\*\*\* End Patch", c, re.S)
                if m:
                    try:
                        plan = json.loads(re.sub(r"^\+", "", m.group(1), flags=re.M))
                    except Exception:
                        plan = {"raw": m.group(1)}
                for p in re.findall(r"/tmp/[\w./-]+\.png", c):
                    if os.path.exists(p):
                        (d / "look_outputs").mkdir(exist_ok=True)
                        shutil.copy(p, d / "look_outputs" / Path(p).name)
                if is_look(it) and "then-now" in shell_part(c) and step is not None:
                    regen_then_now(ep, shell_part(c), step, d)
                    # the model's own sheet, if the file it named still exists (it may have overwritten it later)
                if is_look(it):
                    for own in set(re.findall(r"(mine/[\w./-]+\.png)", shell_part(c))):
                        src = ep / "memory" / own
                        if src.exists():
                            (d / "look_outputs").mkdir(exist_ok=True)
                            shutil.copy(src, d / "look_outputs" / ("model_sheet_" + Path(own).name))
            elif it.get("type") == "reasoning":
                lines.append("## reasoning\n\n" + (it.get("text") or "").strip()[:2000] + "\n")
        (d / "transcript.md").write_text("\n".join(lines))
        if plan is not None:
            (d / "plan.json").write_text(json.dumps(plan, indent=1))
        for label, s in (("before", step), ("after", nxt_step)):
            if s is not None:
                src = ep / "hires" / f"{s:07d}.jpg"
                if src.exists():
                    shutil.copy(src, d / f"frame_{label}_{s}.jpg")
        if step is not None and nxt_step is not None:
            seg = re.search(rf"^Action \d+ \| Step {step}\b.*?(?=^Action \d+ \| Step {nxt_step}\b|\Z)",
                            log_text, re.S | re.M)
            if seg:
                (d / "executed.log").write_text(seg.group(0))
        nxt_items = turn_items(ep, n + 1)
        nxt_msgs = [it.get("text", "").strip() for it in nxt_items if it.get("type") == "agent_message"]
        (d / "next_turn.md").write_text("\n\n".join(nxt_msgs))
        cmd, after = look_summary(items)
        (d / "case.json").write_text(json.dumps({
            "arm": arm, "turn": n, "step": step, "next_step": nxt_step, "look": cmd,
            "after_look": after, "next_observed": observed_of(nxt_items),
            "milestones": [m for m in milestones(mcu, arm) if step is not None and nxt_step is not None
                           and step <= m[1] <= nxt_step],
        }, indent=1))
        print("wrote", d)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("mcu"); l.add_argument("arm"); l.add_argument("--min-score", type=int, default=2)
    dmp = sub.add_parser("dump"); dmp.add_argument("mcu"); dmp.add_argument("arm"); dmp.add_argument("turns", type=int, nargs="+"); dmp.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "list":
        cmd_list(Path(a.mcu), a.arm, a.min_score)
    else:
        cmd_dump(Path(a.mcu), a.arm, a.turns, Path(a.out))


if __name__ == "__main__":
    main()
