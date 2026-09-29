"""Local patches to the cached cua.bench KiCad tasks, applied in place and idempotent.

The dataset cache is not under version control (`lite/gym/envs/cua/.cache/datasets/`),
so the patches live here as code and are re-applied after any re-download:

    <cua-lite>/.venv/bin/python <CUA-KiCad>/gym_codex/patch_kicad_tasks.py [--cache DIR]

- 34877be3: the description asks for "LN271" infrared LEDs; the reference netlist's part
  is `LD271` (the Osram IR LED that exists in KiCad's library). A model that searches
  the chooser for LN271 finds nothing, so the task was unsolvable as written.
- a6414tw4 is NOT patched: its reference netlist is empty ("create an empty netlist
  file"), so the only scoring submission is none at all. Exclude it with
  `run_eval.py --exclude-tasks a6414tw4`.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

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

PATCHES = {
    "34877be3": [("two infrared LN271 LEDs", "two infrared LD271 LEDs")],
}


def apply(cache: Path) -> list[str]:
    done = []
    for task, edits in PATCHES.items():
        p = cache / task / "main.py"
        if not p.exists():
            done.append(f"{task}: missing")
            continue
        s = p.read_text(encoding="utf-8")
        changed = False
        for old, new in edits:
            if new in s:
                continue
            if old not in s:
                done.append(f"{task}: neither text found")
                break
            s = s.replace(old, new)
            changed = True
        if changed:
            p.write_text(s, encoding="utf-8")
            done.append(f"{task}: patched")
        else:
            done.append(f"{task}: already patched")
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args()
    for line in apply(args.cache):
        print(line)
