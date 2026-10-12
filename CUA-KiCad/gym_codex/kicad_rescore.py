"""A relaxed KiCad netlist score, reported beside the official one, never instead of it.

The official grader (cua_bench.netlist_compare) is the mean of three exact-set checks:
components as (ref prefix, value, library part), nets as sets of (ref, pin), and net
names including KiCad's auto-generated ones (`Net-(D1-K)`, `unconnected-(U1-CONT-Pad5)`).
A from-scratch design cannot reproduce the reference's symbol variant (`R` vs `R_US`),
its reference numbering, or the auto-names that depend on both, so no design-from-scratch
task had ever been solved by any arm. This score keeps the three checks and relaxes each
to what the task description can actually determine:

    components  (ref prefix, value, part family) -- the family strips symbol-style
                suffixes (_US, _Small, _Filled, ...), so `R_US` and `R` are one part.
    nets        the multiset of nets, each net the multiset of (component class, pin),
                where a class is (ref prefix, part family) -- topology up to renumbering
                of same-kind components. Values are the components check's business:
                the official nets check keys on (ref, pin) and never sees a value, so a
                wrong capacitor value must cost one check here too, not two.
    net names   the user's own labels only (auto-generated names dropped). When the
                reference has no user label at all (most from-scratch tasks), this check
                is not applicable and the score is the mean of the other two: the
                auto-names only restate the topology the nets check already scores, and a
                check that is true of every submission would hand out a third of the
                score for nothing.

Two further allowances are reported beside `relaxed`, each on its own so its
contribution is visible rather than blended into one number:

    +values     two values that denote the same electrical quantity are one value.
                `4.7u`/`4.7uF`, `1k1`/`1.1k`, `1000u`/`1000uF`, `470`/`470_ohm`,
                `.01u`/`0.01u` are the measured disagreements; the reference picks a
                convention the task description never states. Values that do not parse
                as a quantity (`LED_SELF_FLASHING`, `PUSH_TO_ON`) are still compared
                exactly -- this relaxes notation, not identity.
    +connectors reference components with a `J` designator are dropped from both sides,
                with their pins, when the instruction never mentions a connector. Four
                from-scratch references require a connector (`Conn_01x02_Pin`,
                `Power_Input`) that their instruction does not ask for in any wording,
                which no agent can supply. Dropping from both sides keeps it symmetric:
                an agent that adds a connector anyway gains nothing.

`spec` applies both. Each level keeps the three checks and the official score untouched.

Usage:
    kicad_rescore.py --task-dir <out>/<task_id> [--reference <task cache dir>]
    kicad_rescore.py --run-dir <out>            # score every task dir under a run
    kicad_rescore.py --self-test          # every reference must score 1.0 against itself
Reads `graded.net` or `kicad_project/*.net` (saved by run_eval) and prints raw and relaxed.
"""
from __future__ import annotations

import argparse
import os
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from cua_bench.netlist_compare import (  # the official parser and scorer
    _component_key, compare_kicad_netlists, parse_kicad_netlist,
)

def _default_cache() -> Path:
    """The cua-bench KiCad dataset cache: $CUA_BENCH_KICAD_CACHE, else the one inside a
    cua-lite checkout beside this repo (a standalone clone) or beside the MFM checkout that
    holds this repo as a submodule."""
    env = os.environ.get("CUA_BENCH_KICAD_CACHE")
    if env:
        return Path(env)
    rel = Path("cua-lite/lite/gym/envs/cua/.cache/datasets/cua-bench-kicad")
    here = Path(__file__).resolve()
    for root in here.parents[2:4]:
        if (root / rel).is_dir():
            return root / rel
    return here.parents[2] / rel


DEFAULT_CACHE = _default_cache()

_STYLE_SUFFIXES = ("_US", "_Small", "_Filled", "_Polarized_US", "_Pin", "_Socket")
_AUTO_NET = re.compile(r"^(Net-\(|unconnected-\()")


def part_family(part: str | None) -> str:
    p = (part or "").strip()
    changed = True
    while changed and p:
        changed = False
        for suf in _STYLE_SUFFIXES:
            if p.endswith(suf) and len(p) > len(suf):
                p = p[: -len(suf)]
                changed = True
    return p


#: Words any of which makes a connector part of the task description. Matched against
#: the instruction the agent was actually given (`instruction.txt` beside the run).
_CONNECTOR_WORDS = re.compile(
    r"connector|jack|header|terminal|screw|plug|socket|\bconn\b|input pin|two-pin|2-pin",
    re.I)

#: SI multipliers as they appear in KiCad values. `u` and the micro sign are one thing.
_MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "\u00b5": 1e-6, "\u03bc": 1e-6, "m": 1e-3,
         "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
#: Unit letters that carry no information once the designator is known: a capacitor's
#: `F`, a resistor's ohm in its several spellings. `R` is both a multiplier-position
#: marker (`4R7`) and a unit, and is handled by the RKM branch.
_UNIT = re.compile(r"(?:F|f|H|h|ohms?|OHMS?|\u03a9|\u2126)$")
#: `4u7`, `1k1`, `4R7`: the multiplier stands where the decimal point would.
_RKM = re.compile(r"^(\d+)([pnu\u00b5\u03bcmkKMGR])(\d+)$")
#: `4.7uF`, `.01u`, `470`, `10k`.
_PLAIN = re.compile(r"^(\d*\.?\d+)\s*([pnu\u00b5\u03bcmkKMG]?)$")


def value_quantity(value: str | None) -> float | None:
    """The numeric quantity a KiCad value denotes, or None if it is not one.

    Returns a plain float so `4.7u`, `4.7uF` and `4u7` compare equal while
    `LED_SELF_FLASHING` and `PUSH_TO_ON` stay incomparable and are matched as text.
    """
    v = (value or "").strip()
    if not v:
        return None
    v = _UNIT.sub("", v).strip()
    m = _RKM.match(v)
    if m:
        whole, mult, frac = m.groups()
        if mult == "R":                      # 4R7 == 4.7 ohm, no multiplier
            return float(f"{whole}.{frac}")
        return float(f"{whole}.{frac}") * _MULT[mult]
    m = _PLAIN.match(v)
    if m:
        num, mult = m.groups()
        return float(num) * _MULT[mult]
    return None


def normalize_value(value: str | None) -> str:
    """`value` as a canonical string when it denotes a quantity, else unchanged."""
    q = value_quantity(value)
    return value if q is None else f"{q:.9g}"


def relaxed_component_key(c: dict[str, Any], *, value_norm: bool = False) -> tuple[str, str, str]:
    prefix, value, part = _component_key(c)
    if value_norm:
        value = normalize_value(value)
    return (prefix, value, part_family(part))


def drop_refs(parsed: dict[str, Any], refs: set[str]) -> dict[str, Any]:
    """The parse with `refs` gone: their components, their pins, and any net left with
    fewer than two nodes (a net that only ever joined the dropped part to itself)."""
    if not refs:
        return parsed
    comps = [c for c in parsed["components"] if c.get("ref") not in refs]
    nets = []
    for net in parsed["nets"]:
        kept = tuple((r, pin) for r, pin in net if r not in refs)
        if len(kept) >= 2:
            nets.append(kept)
    return {**parsed, "components": comps, "nets": nets}


#: A connector designator: `J1`, `JP2`.
_CONNECTOR_REF = re.compile(r"^JP?\d+$")


def relaxed_checks(candidate: str, reference: str, *, value_norm: bool = False,
                   drop_connectors: bool = False) -> dict[str, bool | None]:
    """The three relaxed checks; `None` marks a check that does not apply.

    `value_norm` compares values as quantities where they are quantities;
    `drop_connectors` removes `J`-designated parts from both sides (the caller decides
    whether the instruction asked for one).
    """
    ref, cand = parse_kicad_netlist(reference), parse_kicad_netlist(candidate)
    if drop_connectors:
        refs = {c["ref"] for parsed in (ref, cand) for c in parsed["components"]
                if _CONNECTOR_REF.match(c.get("ref") or "")}
        ref, cand = drop_refs(ref, refs), drop_refs(cand, refs)
    key = lambda c: relaxed_component_key(c, value_norm=value_norm)  # noqa: E731
    rk = sorted(key(c) for c in ref["components"])
    ck = sorted(key(c) for c in cand["components"])
    comps_ok = rk == ck

    def classes(parsed):
        return {c["ref"]: (k[0], k[2]) for c in parsed["components"]
                for k in (key(c),)}

    def canon(parsed):
        cls = classes(parsed)
        nets = []
        for net in parsed["nets"]:
            nodes = tuple(sorted((cls.get(ref, ("?", ref)), str(pin)) for ref, pin in net))
            nets.append(nodes)
        return Counter(nets)

    nets_ok = canon(ref) == canon(cand)
    ref_names = {n for n in ref.get("net_names", []) if not _AUTO_NET.match(n)}
    cand_names = {n for n in cand.get("net_names", []) if not _AUTO_NET.match(n)}
    names_ok = (ref_names == cand_names) if ref_names else None
    return {"components": comps_ok, "nets": nets_ok, "net_names": names_ok}


def relaxed_score(candidate: str, reference: str, **kw: Any) -> float:
    checks = [v for v in relaxed_checks(candidate, reference, **kw).values() if v is not None]
    return sum(1.0 if v else 0.0 for v in checks) / len(checks)


def instruction_names_connector(task_dir: Path) -> bool:
    """Whether the instruction the agent was given mentions a connector at all.

    Read from the run's own `instruction.txt` (what the agent saw, hint included), so a
    task whose reference needs an unasked-for connector is identified from the record
    rather than from a hand-kept list.
    """
    p = task_dir / "instruction.txt"
    if not p.exists():
        return True                      # unknown: assume it was asked for, relax nothing
    return bool(_CONNECTOR_WORDS.search(p.read_text(encoding="utf-8", errors="replace")))


def score_task_dir(task_dir: Path, cache: Path = DEFAULT_CACHE) -> dict[str, Any]:
    task_id = task_dir.name
    ref_path = cache / task_id / "reference.net"
    reference = ref_path.read_text(encoding="utf-8", errors="replace")
    candidate_path = task_dir / "graded.net"
    if not candidate_path.exists():
        nets = sorted((task_dir / "kicad_project").rglob("*.net")) if (task_dir / "kicad_project").exists() else []
        candidate_path = nets[0] if nets else None
    if candidate_path is None:
        return {"task_id": task_id, "raw": 0.0, "relaxed": 0.0, "values": 0.0,
                "connectors": 0.0, "spec": 0.0, "connector_unasked": False,
                "candidate": None, "relaxed_checks": None, "spec_checks": None}
    candidate = candidate_path.read_text(encoding="utf-8", errors="replace")
    # The connector allowance applies only where the instruction never asked for one;
    # everywhere else `+connectors` is `relaxed` and `spec` is `+values`, by construction.
    unasked = not instruction_names_connector(task_dir)
    lv = lambda **kw: relaxed_score(candidate, reference, **kw)   # noqa: E731
    return {"task_id": task_id,
            "raw": compare_kicad_netlists(candidate, reference, verbose=False),
            "relaxed": lv(),
            "values": lv(value_norm=True),
            "connectors": lv(drop_connectors=unasked),
            "spec": lv(value_norm=True, drop_connectors=unasked),
            "connector_unasked": unasked,
            "relaxed_checks": relaxed_checks(candidate, reference),
            "spec_checks": relaxed_checks(candidate, reference, value_norm=True,
                                          drop_connectors=unasked),
            "candidate": str(candidate_path.relative_to(task_dir))}


#: `4.7uF` -> `4u7`, `10k` -> `10K`: the same quantity in a notation the reference did
#: not choose. Only touches values that parse as quantities, so text values are left be.
def _renotate(text: str) -> str:
    def sub(m):
        raw = m.group(1)
        q = value_quantity(raw)
        if q is None:
            return m.group(0)
        for mult, scale in (("k", 1e3), ("u", 1e-6), ("n", 1e-9), ("", 1.0)):
            if scale <= q < scale * 1000:
                # Decompose off the rounded decimal string, not off the float:
                # 1e-7/1e-9 is 99.99999999999999, and int() of it is 99.
                text = f"{q / scale:.6f}".rstrip("0").rstrip(".")
                whole, _, frac = text.partition(".")
                rkm = f"{whole}{mult or 'R'}{frac}" if frac else f"{whole}{mult}"
                return m.group(0).replace(raw, rkm)
        return m.group(0)
    return re.sub(r'\(value "([^"]*)"\)', sub, text)


def self_test(cache: Path) -> int:
    bad = 0
    for t in sorted(cache.iterdir()):
        ref = t / "reference.net"
        if not ref.exists():
            continue
        text = ref.read_text(encoding="utf-8", errors="replace")
        s = relaxed_score(text, text)
        spec_self = relaxed_score(text, text, value_norm=True, drop_connectors=True)
        # A variant-renamed, renumbered copy of the reference must also score 1.0.
        mutated = re.sub(r'\(part "(R|C|LED)_US"\)', r'(part "\1")', text)
        m = relaxed_score(mutated, text)
        raw_m = compare_kicad_netlists(mutated, text, verbose=False)
        # The same reference in another value notation: `+values` must still be 1.0.
        v = relaxed_score(_renotate(text), text, value_norm=True)
        ok = (s == 1.0 and m == 1.0 and spec_self == 1.0 and v == 1.0)
        flag = "" if ok else "  <-- FAIL"
        bad += bool(flag)
        print(f"{t.name}: self={s:.2f} spec_self={spec_self:.2f} style-variant={m:.2f} "
              f"raw={raw_m:.2f} renotated+values={v:.2f}{flag}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task-dir", type=Path, nargs="*", default=[])
    ap.add_argument("--run-dir", type=Path, help="score every task dir under a run")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return 1 if self_test(args.cache) else 0
    dirs = list(args.task_dir)
    if args.run_dir:
        dirs += [d for d in sorted(args.run_dir.iterdir()) if (d / "trajectory.json").exists()]
    rows = [score_task_dir(d, args.cache) for d in dirs]
    levels = ("raw", "relaxed", "values", "connectors", "spec")
    for r in rows:
        print(json.dumps(r) if args.json else
              f"{r['task_id']}  " + "  ".join(f"{k}={r[k]:.2f}" for k in levels) +
              f"  {r['spec_checks']}  candidate={r['candidate']}")
    if rows and not args.json:
        print("mean  " + "  ".join(f"{k}={sum(r[k] for r in rows)/len(rows):.3f}"
                                   for k in levels) + f"  n={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
