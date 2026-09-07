#!/usr/bin/env python3
"""Process-level judge over an arm's turns (arXiv 2606.00579, Table 8: an LLM judge
validated against hand labels). For a sample of turns it shows the model the turn's
prompt tail, the shell commands it ran, and the plan it wrote, and asks for ONE label:

  looked_when_needed   a frame was opened and the decision used it
  should_have_looked   the decision needed a frame (a remembered place, a surprise, a
                       hit, unwalked ground) and none was opened
  should_have_used_memory  the log/digest/GUIDE held the answer and the plan re-derived
                       or re-searched it
  re_tested_known      a fact the run had verified (GUI, recipe, position) was re-tested
  ok                   none of the above

Output: one JSON line per turn (arm, turn, label, reason, evidence) to --out; with
--labels <hand.jsonl> it reports agreement instead. Runs codex (CODEX_BIN, the API-key
wrapper) once per turn; sample with --every N. Read-only on the arm's files.

    python judge.py --arm og21 --every 5 --out analysis/judge_og21.jsonl
    python judge.py --arm og21 --labels analysis/judge_hand_og21.jsonl --out /tmp/j.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kit import ROOTS, episode_dir  # noqa: E402

LABELS = ("looked_when_needed", "should_have_looked", "should_have_used_memory",
          "re_tested_known", "stale_rederivation", "ok")
HDR = re.compile(r"^Action (\d+) \| Step (\d+)", re.M)

PROMPT = """\
You judge ONE turn of an agent playing Minecraft through a filesystem memory (a log, an
episode store with one frame per plan entry, earlier lives under previous/, its own
files under mine/). You see: the tail of the prompt it was given, the shell commands it
ran (view_image = it opened a frame), and the briefing and plan it wrote in reply. Pick
the ONE label that fits and cite the evidence in one sentence.

Labels, with the bar each must clear:
- ok: a plain continuation. The default. A matched or nearly matched EXPECT, a plan that
  moves on sensibly, a coordinate quoted from memory -- all ok. When in doubt, ok.
- looked_when_needed: the commands contain a view_image of an episode or previous frame
  (not a zoom of the current view) AND the plan uses what it showed.
- should_have_looked: NO such view_image, and one of these concrete triggers: (a) the
  plan's success depends on RECOGNISING a place -- re-opening a placed table/furnace,
  returning to a pour rim or a pool, arriving at a remembered site -- not merely walking
  in its direction; (b) OBSERVED vs EXPECTED disagree for a reason the OBSERVED numbers
  do not give (moved 0.0 with no note, a fall, an unexplained stop), and the plan repeats
  the attempt; (c) a hit or a death this turn; (d) the third failure of the same plan.
  A small numeric mismatch (one block short, one item fewer) with the plan adjusting is
  NOT a trigger.
- should_have_used_memory: the plan searches for, or re-derives from scratch, something
  the prompt or a file it could grep plainly holds -- a RECALL line, [WORKING], the
  digest/GUIDE -- e.g. exploring for water while RECALL cites the fill spot 6 blocks
  away; or the plan's MAIN step is an action type RECALL says has never changed anything.
  A RECALL streak line about a minor action (a `watch`, a one-tick `forward`) inside a
  longer plan does not count.
- re_tested_known: the plan's main step re-does something already credited or verified
  in [OBSERVED]/[RECALL]/[STATE] (re-crafting a banked item, re-checking a recipe or a
  GUI fact it already confirmed). Make sure the plan you judge is the NEW plan, not the
  one whose outcome [OBSERVED] reports.
- stale_rederivation: the briefing restates numbers the prompt already gave (position,
  inventory delta) and gets them wrong after grepping the log instead of reading the
  prompt -- the plan may still be fine.

Answer with one JSON object only:
{{"label": "<one of the labels>", "reason": "<one sentence with the evidence>"}}

=== PROMPT TAIL (last 3500 chars) ===
{prompt}
=== COMMANDS THIS TURN ===
{commands}
=== BRIEFING AND PLAN IT WROTE ===
{plan}
"""


def turns_of(mem: Path):
    ct = mem.parent / "codex_turns"
    for p in sorted(ct.glob("turn_*.prompt.txt")):
        n = int(p.stem.split("_")[1].split(".")[0])
        ev = ct / f"turn_{n:04d}.events.jsonl"
        yield n, p, ev


def commands_of(ev: Path) -> str:
    out = []
    try:
        for ln in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                j = json.loads(ln)
            except ValueError:
                continue
            s = json.dumps(j)
            for key in ("command", "cmd"):
                m = re.search(r'"%s":\s*"((?:[^"\\]|\\.)*)"' % key, s)
                if m:
                    out.append(m.group(1)[:200])
                    break
            if "view_image" in s and not any("view_image" in o for o in out[-1:]):
                m = re.search(r'"path":\s*"([^"]+)"', s)
                out.append("view_image " + (m.group(1) if m else "?"))
    except OSError:
        pass
    return "\n".join(out[-25:]) or "(none recorded)"


def plan_after(log: str, step: int) -> str:
    """The [PLAN]/EXPECT lines of the first action section at or after `step`."""
    ms = list(HDR.finditer(log))
    for i, m in enumerate(ms):
        if int(m.group(2)) > step:      # the section AT `step` closed the previous plan
            end = ms[i + 1].start() if i + 1 < len(ms) else len(log)
            sec = log[m.start():end]
            keep = [ln for ln in sec.splitlines() if ln.startswith(("[PLAN]", "EXPECT", "OBSERVED"))]
            return "\n".join(keep)[:1500] or sec[:800]
    return "(no plan found)"


def step_of(prompt: str) -> int:
    m = re.search(r"Step (\d+)/", prompt)
    return int(m.group(1)) if m else 0


def ask(text: str, model: str, effort: str, codex_home: Path | None) -> dict:
    codex = os.environ.get("CODEX_BIN", "codex")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "last.txt"
        args = [codex, "exec", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
                "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-o", str(out),
                "-c", 'sandbox_mode="read-only"', "-c", 'web_search="disabled"', "-"]
        env = os.environ.copy()
        if codex_home:
            env["CODEX_HOME"] = str(codex_home)
        subprocess.run(args, input=text, text=True, capture_output=True, cwd=td, env=env, timeout=600)
        try:
            ans = out.read_text(encoding="utf-8")
        except OSError:
            return {"label": "error", "reason": "no answer"}
    m = re.search(r"\{.*\}", ans, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except ValueError:
        j = {}
    if j.get("label") not in LABELS:
        return {"label": "error", "reason": ans.strip()[:200]}
    return j


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--every", type=int, default=5, help="judge every N-th turn")
    ap.add_argument("--start", type=int, default=2)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--model", default=os.environ.get("JUDGE_MODEL", "gpt-5.6-sol"))
    ap.add_argument("--effort", default=os.environ.get("JUDGE_EFFORT", "high"))
    ap.add_argument("--codex-home", default=os.environ.get("JUDGE_CODEX_HOME"))
    ap.add_argument("--labels", help="hand labels (jsonl: turn, label) -> agreement report")
    ap.add_argument("--dump", action="store_true",
                    help="write the judge inputs to --out (jsonl) instead of asking; for hand labelling")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ep = episode_dir(a.arm, a.root or ROOTS)
    if not ep:
        sys.exit(f"no such arm: {a.arm}")
    mem = Path(ep) / "memory"
    log = (mem / "logs.txt").read_text(encoding="utf-8", errors="replace")
    hand = {}
    if a.labels:
        for ln in Path(a.labels).read_text().splitlines():
            if ln.strip():
                j = json.loads(ln); hand[int(j["turn"])] = j["label"]
    rows = []
    n_done = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for n, p, ev in turns_of(mem):
            if n < a.start or (n - a.start) % a.every:
                continue
            if hand and n not in hand:
                continue
            prompt = p.read_text(encoding="utf-8", errors="replace")
            item = {"arm": a.arm, "turn": n, "step": step_of(prompt),
                    "prompt_tail": prompt[-3500:], "commands": commands_of(ev),
                    "plan": plan_after(log, step_of(prompt))}
            if a.dump:
                fo.write(json.dumps(item) + "\n"); n_done += 1
                if n_done >= a.limit: break
                continue
            text = PROMPT.format(labels=", ".join(LABELS), prompt=item["prompt_tail"],
                                 commands=item["commands"], plan=item["plan"])
            j = ask(text, a.model, a.effort, Path(a.codex_home) if a.codex_home else None)
            row = {"arm": a.arm, "turn": n, "step": item["step"], "label": j.get("label"),
                   "reason": j.get("reason", "")[:300]}
            if hand:
                row["hand"] = hand.get(n)
            rows.append(row); fo.write(json.dumps(row) + "\n"); fo.flush()
            n_done += 1
            if n_done >= a.limit:
                break
    if a.dump:
        print(f"dumped {n_done} judge inputs to {a.out}"); return 0
    from collections import Counter
    c = Counter(r["label"] for r in rows)
    print(f"{a.arm}: {len(rows)} turns judged: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    if hand:
        agree = sum(1 for r in rows if r.get("hand") == r["label"])
        print(f"agreement with hand labels: {agree}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
