"""How often the model's own OBSERVED vs EXPECTED verdict says the world matched its plan.

    python match_rate.py --arm og14 --arm og19            # both default roots
    python match_rate.py --arm og14 --verbose             # + 5 unclear sentences to tune the rule
    python match_rate.py --arm og14 --json

The harness asks the model to open each briefing with one line `OBSERVED vs EXPECTED: ...`,
so one such line == one act turn that reported a verdict. The classifier is deliberately
shallow and is applied to the sentence AFTER the colon, first rule that fires wins:

  matched  sentence STARTS WITH Matched / Yes / As expected / Confirmed / Match
  failed   contains failed, mismatch, did not, didn't, not met, unexpected, or first word "no"
  partial  contains partial, partly, mostly, except
  unclear  everything else

Sentences that merely contain "matched" mid-clause ("Drops and crafting matched; ...") fall
to unclear ON PURPOSE -- the point of the unclear bucket, and of --verbose, is to show what
the prefix rule is missing before anyone reports a matched share as a number.
"""
import re, sys

from _kit import (base_parser, episode_dir, log_steps, print_table, read_lines, roots_of)

OVE_RE = re.compile(r"^\[PLAN\] OBSERVED vs EXPECTED:\s*(.*)")
MATCHED_PREFIX = ("matched", "yes", "as expected", "confirmed", "match")
FAILED_SUBSTR = ("failed", "mismatch", "did not", "didn't", "not met", "unexpected")
PARTIAL_SUBSTR = ("partial", "partly", "mostly", "except")
CLASSES = ("matched", "partial", "failed", "unclear")


def classify(sentence: str) -> str:
    s = sentence.strip().lower()
    if not s:
        return "unclear"
    if s.startswith(MATCHED_PREFIX):
        return "matched"
    if any(k in s for k in FAILED_SUBSTR) or re.match(r"^no\b", s):
        return "failed"
    if any(k in s for k in PARTIAL_SUBSTR):
        return "partial"
    return "unclear"


def scan(arm: str, roots) -> dict:
    ep = episode_dir(arm, roots)
    if not ep:
        return {}
    lines = read_lines(ep + "/memory/logs.txt")
    if not lines:
        return {}
    steps, last_step = log_steps(lines)
    counts = dict.fromkeys(CLASSES, 0)
    unclear = []
    for i, ln in enumerate(lines):
        m = OVE_RE.match(ln)
        if not m:
            continue
        kind = classify(m.group(1))
        counts[kind] += 1
        if kind == "unclear":
            unclear.append((steps[i], m.group(1).strip()))
    total = sum(counts.values())
    return {"arm": arm, "episode": ep, "verdicts": total, "steps": last_step,
            "counts": counts, "unclear_examples": unclear[:5],
            "matched_share": counts["matched"] / total if total else 0.0,
            "verdicts_per_1k_steps": 1000.0 * total / last_step if last_step else 0.0,
            "matched_per_1k_steps": 1000.0 * counts["matched"] / last_step if last_step else 0.0}


def main(argv=None) -> int:
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--verbose", action="store_true",
                   help="print up to 5 unclear sentences per arm")
    args = p.parse_args(argv)
    roots = roots_of(args)
    if not args.arm:
        p.error("give at least one --arm")

    results = [r for r in (scan(a, roots) for a in args.arm) if r]
    missing = [a for a in args.arm if not any(r["arm"] == a for r in results)]

    if args.json:
        import json
        print(json.dumps({"arms": results, "missing": missing}, indent=2))
        return 0

    headers = ["arm", "steps", "verdicts", "matched", "partial", "failed", "unclear",
               "matched%", "verdicts/1k", "matched/1k"]
    rows, tot = [], dict.fromkeys(CLASSES, 0)
    tot_steps = tot_v = 0
    for r in results:
        c = r["counts"]
        rows.append([r["arm"], r["steps"], r["verdicts"], c["matched"], c["partial"],
                     c["failed"], c["unclear"], "%.1f" % (100 * r["matched_share"]),
                     "%.1f" % r["verdicts_per_1k_steps"], "%.1f" % r["matched_per_1k_steps"]])
        for k in CLASSES:
            tot[k] += c[k]
        tot_steps += r["steps"]
        tot_v += r["verdicts"]
    if rows:
        rows.append(["TOTAL", tot_steps, tot_v, tot["matched"], tot["partial"], tot["failed"],
                     tot["unclear"], "%.1f" % (100 * tot["matched"] / tot_v if tot_v else 0),
                     "%.1f" % (1000.0 * tot_v / tot_steps if tot_steps else 0),
                     "%.1f" % (1000.0 * tot["matched"] / tot_steps if tot_steps else 0)])
        print_table(headers, rows)
    if missing:
        print("\nnot found: " + ", ".join(missing))

    if args.verbose:
        for r in results:
            print("\n-- %s: %d unclear, first 5 --" % (r["arm"], r["counts"]["unclear"]))
            for step, s in r["unclear_examples"]:
                print("   step %-7d %s" % (step, s[:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
