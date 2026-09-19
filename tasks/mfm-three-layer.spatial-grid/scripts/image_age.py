#!/usr/bin/env python3
"""Historical-image retrieval in an MFM life: how often the model opened a PAST frame,
and how old it was (read-only; the measure the "without historical images" ablation is
judged against).

    python image_age.py <run dir> [<run dir> ...]        # e.g. $MCU_ROOT/output/g4_mfm_gpt6_diamond_v7
    python image_age.py <run dir> --json

Source: the codex rollouts under `<run>/codex_sessions/**/rollout-*.jsonl` (every
`function_call` named view_image, and view_image calls inside code-mode exec cells), the
turn's step from the last "Step N/M" turn header seen before the call, and the episode
index (`episode_001/memory/index.jsonl`, plus `previous/index.jsonl`) for the step a
frame was taken at. Each call is classified by its path:

    current      the attached view (attach/frame.png) or a crop of it (zoom, crop, /tmp)
    episode      this life's episodes/ep_*/observation/image.png   -> age = turn step - frame step
    previous     an earlier life's frame under previous/            (age is across lives: not computed)
    sheet        a --sheet / --then-now composite (then_now.png, sheet, death.png)
    hires        the hires/ record beside the workspace (should be 0: it is not the model's)
    other        anything else

Ages are in game steps. Under --no-history-images the episode/previous/hires rows must
read 0; under the full arm they are the "did it look back, and how far" numbers.
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys
from collections import Counter

STEP_RE = re.compile(r"Step (\d+)/\d+")
PATH_RE = re.compile(r"[\w./\-]+\.(?:png|jpe?g)")
EP_RE = re.compile(r"(?:^|/)(ep_\d{6})/observation/image\.png$")


def classify(path: str) -> str:
    p = path
    if "/hires/" in p or p.startswith("hires/"):
        return "hires"
    if "previous/" in p:
        return "previous"
    if EP_RE.search(p):
        return "episode"
    if re.search(r"then_now|sheet|death\.png|contact", p):
        return "sheet"
    if p.endswith("attach/frame.png") or p.startswith("/tmp") or re.search(r"zoom|crop", p):
        return "current"
    return "other"


def index_steps(mem: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for name in ("index.jsonl", "previous/index.jsonl"):
        f = os.path.join(mem, name)
        if not os.path.exists(f):
            continue
        for ln in open(f, encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("id") and r.get("first_step") is not None:
                out.setdefault(r["path"] if name.startswith("previous") else r["id"], int(r["first_step"]))
    return out


def scan(run: str) -> dict:
    mem = os.path.join(run, "episode_001", "memory")
    steps = index_steps(mem)
    files = sorted(glob.glob(os.path.join(run, "codex_sessions", "**", "rollout-*.jsonl"), recursive=True))
    kinds: Counter = Counter()
    ages: list[int] = []
    step_now = 0
    calls = 0
    for f in files:
        for ln in open(f, encoding="utf-8", errors="ignore"):
            if "Step " in ln and '"input_image"' in ln or ("Step " in ln and '"role": "user"' in ln):
                m = STEP_RE.search(ln)
                if m:
                    step_now = int(m.group(1))
            if "view_image" not in ln:
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            p = e.get("payload", e)
            t = p.get("type", "")
            if t == "function_call" and p.get("name") == "view_image":
                paths = PATH_RE.findall(str(p.get("arguments") or ""))
            elif t == "custom_tool_call":
                s = str(p.get("input") or "")
                paths = [m for m in PATH_RE.findall(s) if s.find(m) >= 0 and "view_image" in s[max(0, s.find(m) - 120):s.find(m)]]
            else:
                continue
            for path in paths:
                calls += 1
                k = classify(path)
                kinds[k] += 1
                if k == "episode":
                    m = EP_RE.search(path)
                    fs = steps.get(m.group(1)) if m else None
                    if fs is not None and step_now >= fs:
                        ages.append(step_now - fs)
    def q(v, f):
        return round(f(v)) if v else None
    return {"run": os.path.basename(run.rstrip("/")), "rollouts": len(files), "view_image_calls": calls,
            "by_kind": dict(kinds),
            "episode_frame_age_steps": {"n": len(ages), "median": q(ages, statistics.median),
                                        "p90": (sorted(ages)[int(0.9 * (len(ages) - 1))] if ages else None),
                                        "max": max(ages) if ages else None,
                                        "buckets": {"<=100": sum(a <= 100 for a in ages),
                                                    "101-1000": sum(100 < a <= 1000 for a in ages),
                                                    ">1000": sum(a > 1000 for a in ages)}}}


def main(argv: list[str]) -> int:
    runs = [a for a in argv if not a.startswith("--")]
    if not runs:
        print(__doc__)
        return 2
    rows = [scan(r) for r in runs]
    if "--json" in argv:
        print(json.dumps(rows, indent=1))
        return 0
    print(f"{'run':40} {'calls':>6} {'current':>8} {'episode':>8} {'previous':>9} {'sheet':>6} {'hires':>6} {'other':>6}  age median/p90/max (n)")
    for r in rows:
        k, a = r["by_kind"], r["episode_frame_age_steps"]
        print(f"{r['run']:40} {r['view_image_calls']:>6} {k.get('current', 0):>8} {k.get('episode', 0):>8} "
              f"{k.get('previous', 0):>9} {k.get('sheet', 0):>6} {k.get('hires', 0):>6} {k.get('other', 0):>6}  "
              f"{a['median']}/{a['p90']}/{a['max']} ({a['n']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
