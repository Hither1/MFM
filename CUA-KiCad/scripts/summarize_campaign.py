#!/usr/bin/env python3
"""One table for a campaign's cells, from each cell's own `arm` block.

Scores are read next to what produced them, never next to a directory name: every
`result.json` here now carries an `arm` block (agent, channel, model, endpoint,
concurrency, limit), and PRO-LONG cells also carry the audit their score was bought
at. A cell whose `arm` disagrees with its directory is reported, not silently pooled.

    python scripts/summarize_campaign.py runs/qwen35_v1 [runs/qwen35_full ...]
"""
from __future__ import annotations

import argparse
import json
import math
import os

CELLS = ["bcp_default", "bcp_direct", "bcp_hypothesis", "bcp_prolong"]

# The no-memory arm answers to two directory names -- `run_cell.sh` writes
# `<bench>_default`, hand-launched campaigns have used `<bench>_direct` -- while its
# `arm` block always says `default`. Mapped rather than renamed, so the mismatch check
# below keeps catching a cell that really is running the wrong agent.
DIR_ALIASES = {"direct": "default"}

# Where each memory arm parks the audit its score was bought at.
AUDIT_KEYS = ("prolong", "prolong_totals", "worldmodel")


def _wilson_se(p: float, n: int) -> float:
    """Plain binomial se; n is small enough here that the normal interval is honest."""
    return math.sqrt(p * (1 - p) / n) if n else float("nan")


def _answered(rows: list[dict]) -> tuple[int, float] | None:
    """Accuracy over the questions the *method* answered.

    A defaulted question is not a wrong answer, it is an absent one: the backend
    refused it, or a stalled socket ate the turn. Scoring those as first-choice keeps
    the headline honest about the run, but reading only that number attributes an
    upstream failure to the arm. Both are table columns, side by side, never one
    instead of the other (decided 2026-08-27) -- the two are only interpretable
    together, and the gap between them is the size of what the infrastructure cost
    this cell. With no defaults the columns coincide.
    """
    kept = [r for r in rows if not r.get("defaulted")]
    if not kept:
        return None
    return len(kept), sum(bool(r.get("correct")) for r in kept) / len(kept)


def _prefix(run_dir: str, cell: str, at_n: int) -> tuple[int, float] | None:
    """Accuracy over the first `at_n` questions, from the checkpoint.

    A longer run of an arm whose memory is per question contains the shorter one
    exactly; so does a longer run of an arm whose memory spans the run, because the
    memory at question k was built from questions 0..k-1 either way. So an n=300 number
    stays readable after a run has been extended to the full benchmark, and there is no
    reason to run the short version separately.
    """
    base = os.path.join(run_dir, cell)
    cands = [os.path.join(base, "result.json.checkpoint.jsonl"),
             os.path.join(base, "result.checkpoint.jsonl")]
    path = next((c for c in cands if os.path.exists(c)), None)
    if not path:
        return None
    text = open(path).read()
    if text.lstrip().startswith("{") and '"results"' in text[:200]:
        try:
            rows = json.loads(text).get("results", [])
        except json.JSONDecodeError:
            return None
        rows = rows[:at_n]
    else:
        rows = []
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("index", r.get("dataset_index", 10**9)) < at_n:
                rows.append(r)
    if len(rows) < at_n:
        return None
    return len(rows), sum(bool(r.get("correct")) for r in rows) / len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--at-n", type=int, default=None,
                    help="Also report each cell's accuracy over its first N questions.")
    args = ap.parse_args()

    rows = []
    for run_dir in args.run_dirs:
        for cell in CELLS:
            path = os.path.join(run_dir, cell, "result.json")
            if not os.path.exists(path):
                continue
            d = json.load(open(path))
            arm = d.get("arm", {})
            n = d.get("n", 0)
            p = d.get("overall", 0.0)
            _bench, agent = cell.split("_", 1)
            agent = DIR_ALIASES.get(agent, agent)
            mismatch = ""
            if arm.get("agent") and arm["agent"] != agent:
                mismatch = f"  !! arm says agent={arm['agent']}"
            audit = next((d[k] for k in AUDIT_KEYS if isinstance(d.get(k), dict)), None)
            rows.append({
                "run": os.path.basename(run_dir.rstrip("/")),
                "cell": cell, "n": n, "acc": p, "se": _wilson_se(p, n),
                "channel": arm.get("channel", "?"),
                "model": arm.get("model", "?"),
                "conc": arm.get("concurrency", "?"),
                "prolong": audit,
                "defaulted": d.get("defaulted", 0),
                "by_reason": d.get("defaulted_by_reason", {}),
                "answered": _answered(d.get("results", [])),
                "mismatch": mismatch,
                "prefix": _prefix(run_dir, cell, args.at_n) if args.at_n else None,
            })

    if not rows:
        print("no result.json found")
        return

    at = f"{'@'+str(args.at_n):>13}" if args.at_n else ""
    print(f"{'run':<14}{'cell':<22}{'n':>5}{'raw':>12}{'answered':>15}{at}"
          f"{'channel':>10}{'conc':>6}  model")
    for r in rows:
        pre = ""
        if args.at_n:
            pre = (f"{100*r['prefix'][1]:>11.1f}% " if r["prefix"] else f"{'-':>13}")
        ans = (f"{100*r['answered'][1]:>9.1f}%/{r['answered'][0]:<4}"
               if r["answered"] else f"{'-':>15}")
        print(f"{r['run']:<14}{r['cell']:<22}{r['n']:>5}"
              f"{100*r['acc']:>8.1f}% ±{100*r['se']:<3.1f}{ans}{pre}"
              f"{r['channel']:>10}{str(r['conc']):>6}"
              f"  {r['model']}{r['mismatch']}")

    # What the arm did not answer, and why. Kept separate from the score because the
    # causes are not the same kind of thing: an upstream refusal belongs to the
    # question, a context overflow belongs to the arm at this n.
    if any(r["defaulted"] for r in rows):
        print("\nquestions the method never answered (scored as the first choice in raw):")
        for r in rows:
            if not r["defaulted"]:
                continue
            print(f"  {r['run']}/{r['cell']}: {r['defaulted']} of {r['n']} "
                  f"{r['by_reason'] or ''}")

    # The audit that qualifies a memory arm's score. `compactions` must be 0: a nonzero
    # count means codex compacted the conversation, and those episodes did not run the
    # architecture the arm claims to run. `timeouts_salvaged` is not a red line -- it is
    # the salvage path working -- but a large one says the backend stalled after the
    # work was done often enough to belong next to the score.
    for r in rows:
        a = r["prolong"]
        if not isinstance(a, dict):
            continue
        flags = [f"{k}={a[k]}" for k in
                 ("compactions", "overflow_resets", "session_resets", "timeout_resets",
                  "timeouts_salvaged", "parse_failures", "view_image_calls",
                  "image_attach_failures", "act_turns", "induction_turns",
                  "induction_silent", "harness_files_tampered",
                  "web_searches", "mcp_tool_calls", "subthreads")
                 if k in a]
        bad = a.get("compactions") or a.get("web_searches") or a.get("mcp_tool_calls") \
            or a.get("subthreads") or a.get("harness_files_tampered") \
            or a.get("image_attach_failures") or a.get("induction_silent")
        print(f"\n{r['run']}/{r['cell']} audit: " + "  ".join(flags)
              + ("   <-- INVESTIGATE" if bad else ""))
        disc = a.get("discipline")
        if isinstance(disc, dict) and any(disc.values()):
            print(f"{'':>{len(r['run']) + len(r['cell']) + 8}}discipline: "
                  + "  ".join(f"{k}={v}" for k, v in disc.items() if v))
        hyp = a.get("hypotheses")
        if isinstance(hyp, dict):
            print(f"{'':>{len(r['run']) + len(r['cell']) + 8}}beliefs: n={hyp.get('n')} "
                  f"{hyp.get('by_status', {})}")


if __name__ == "__main__":
    main()
