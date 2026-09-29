"""The distiller pass: between two lives, the model reads the earlier lives' records and
writes what the next life starts from -- `mine/GUIDE.md`, the scripts worth keeping under
their names, candidate reflexes, a frame index. A separate pass with no game running.

Why a separate pass (arXiv 2606.00579, Finding 4): skills distilled from raw execution
traces by a separate agent scored 76.7 on OmniGAIA against 73.0 for the agent revising
its own guide from pass/fail feedback and 70.5 for human-written skills; the gap widened
on the hard split. Our own carry arms (og15, og19-og22) digested previous/ at life
start, in play turns, and transferred coordinates only: every life rewrote its
staircase step under a new name, no life opened an earlier life's frame more than three
times (analysis/SYNTHESIS.md C).

The harness assembles the workspace (previous/ linked the way a life sees it, the query
tool, the skills package for the example shapes) and runs codex once with the prompt
below. It writes no fact of its own: the MFM carry-only protocol holds -- what reaches
the next life is what the model wrote from the records.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcu_worldmodel.codex_backend import SAFE_CODEX_FLAGS, effort_for
from mcu_worldmodel.previous import PreviousLives

DEFAULT_MINUTES = 40

DISTILL_PROMPT = """\
You are the agent that played these lives, between two of them; no game is running.

`previous/life_<i>/` (oldest first) holds each earlier life's complete record in THIS
SAME WORLD (same seed, same spawn; the world resets between lives -- terrain, water,
lava and ore stay, nothing built or dropped survives): `logs.txt` ([STATE]/[EVENT]/
[NOTE]/[PLAN] lines under `Action N | Step S` headers), `episodes/` with `index.jsonl`
and one frame per plan entry (`observation/image.png`), and its `mine/` (notes, digest,
scripts). `./tools/episodes.py --previous --grep <text> | --near X Z | --tag damage |
--steps A B [--sheet out.png]` queries all lives at once; `view_image <png>` opens a
frame; Read, Grep, Bash, Write as usual. Nothing has been summarised for you.

Write, under `mine/` (carried whole into the next life, which reads it on its first turn):

1. `mine/GUIDE.md` -- what is TRUE of this world and of how these lives went. Every line
   cites life and step (`life3 step 8675`) and, where a frame shows it, the frame path.
   Sections: verified places with coordinates (spawn, table, water, gravel, iron,
   diamond, lava pools, the pour rim, obsidian, portal, Nether landing) and the
   life/step/frame that verified each; every death -- step, place, cause, the rule you
   draw (open the frames of the last 60 steps before it: flames over the lower view are
   a burn, not a mob); the phase ladder (kit -> iron -> water/bucket -> lava -> obsidian
   -> portal -> Nether -> blaze -> pearls -> eyes -> stronghold -> End) with the steps
   each life spent per phase and what it spent them on; which scripts earned their keep
   (count `[ACTION] <name>(` in the logs and read what followed) and which assumptions
   broke; what the next life should do differently in its first 2,000 steps. Under 200
   lines. Facts you can cite, not advice you cannot.
2. `mine/procedures/` -- copy the scripts worth keeping UNDER THEIR ORIGINAL NAMES with a
   header comment (which life, how many calls, what worked, what failed); fix an
   assumption only where a life's notes say it broke. A script never called twice does
   not come along.
3. `mine/reflexes/` -- candidate reflexes for the next life, from the deaths: at least
   the hazard list (lava, pour and death coordinates) in a form a reflex reads;
   `skills/reflexes/scripts/known_hazards.py` shows the shape (stdin JSON state with
   `pos`/`pos_prev`, stdout `{{"stop": true, "note": "..."}}`); small and quiet.
4. `mine/frames.md` -- the frames worth opening before going somewhere: one line per
   place or milestone, `previous/life_<i>/episodes/ep_x/observation/image.png -- what it
   shows`. LOOK at each with view_image before listing it; fog or a GUI is not a landmark.

Budget: about {minutes} minutes of wall clock. Write GUIDE.md first and keep it current
as you read, so a cut still leaves something. Do not invent a coordinate; do not copy
one you did not find in a log.
"""


def _tool_source() -> Path:
    """`tools/episodes.py` as the lives had it (the mfm package's copy)."""
    try:
        import mfm.memory.tools.episodes as ep  # type: ignore
        return Path(ep.__file__)
    except ImportError:
        pass
    root = os.environ.get("MFM_ROOT")
    cands = [Path(root) if root else None, Path(__file__).resolve().parents[2]]
    for c in cands:
        if c and (c / "mfm" / "memory" / "tools" / "episodes.py").exists():
            return c / "mfm" / "memory" / "tools" / "episodes.py"
    raise SystemExit("cannot find mfm/memory/tools/episodes.py: set MFM_ROOT or PYTHONPATH")


def build_workspace(out: Path, seeds: list[Path]) -> Path:
    """`out/memory/` with previous/ (the seeds' lives, linked as a life sees them), the
    query tool, the skills package (examples only, no starters) and an empty mine/."""
    mem = Path(out) / "memory"
    if mem.exists():
        raise SystemExit(f"{mem} exists; pick a fresh --out")
    mem.mkdir(parents=True)
    PreviousLives(mem).seed([Path(s) for s in seeds])
    tools = mem / "tools"
    tools.mkdir()
    shutil.copy2(_tool_source(), tools / "episodes.py")
    (tools / "episodes.py").chmod(0o755)
    from mcu_worldmodel import skills as _skills
    _skills.write_skills(mem)                    # the examples only; mine/ stays empty
    (mem / "mine").mkdir()
    return mem


def _args(codex_bin: str, model: str, effort: str, out: Path) -> list[str]:
    """codex exec, the way codex_backend runs a turn (no images, no resume)."""
    return [
        codex_bin, "exec", "--json", "--skip-git-repo-check", "--ignore-user-config",
        "--ignore-rules",
        "-m", model,
        "-c", f'model_reasoning_effort="{effort_for(None, effort)}"',
        "-o", str(Path(out).resolve() / "last_message.txt"),   # cwd is memory/, so absolute
        "-c", 'sandbox_mode="workspace-write"',
        *SAFE_CODEX_FLAGS,
        "-",
    ]


def audit(mem: Path) -> dict[str, Any]:
    mine = mem / "mine"
    files = sorted(str(p.relative_to(mem)) for p in mine.rglob("*") if p.is_file())
    guide = mine / "GUIDE.md"
    return {
        "files": files,
        "guide_lines": len(guide.read_text(encoding="utf-8", errors="replace").splitlines())
        if guide.exists() else 0,
        "procedures": sorted(p.name for p in (mine / "procedures").glob("*.py")) if (mine / "procedures").exists() else [],
        "reflexes": sorted(p.name for p in (mine / "reflexes").glob("*.py")) if (mine / "reflexes").exists() else [],
        "frames_md_lines": len((mine / "frames.md").read_text(encoding="utf-8", errors="replace").splitlines())
        if (mine / "frames.md").exists() else 0,
    }


def run(out: Path, seeds: list[Path], *, model: str, effort: str, codex_home: Path | None,
        codex_bin: str | None = None, minutes: int = DEFAULT_MINUTES) -> dict[str, Any]:
    out = Path(out)
    mem = build_workspace(out, seeds)
    prompt = DISTILL_PROMPT.format(minutes=minutes)
    (out / "distill_prompt.txt").write_text(prompt, encoding="utf-8")
    codex_bin = codex_bin or os.environ.get("CODEX_BIN", "codex")
    env = os.environ.copy()
    if codex_home:
        Path(codex_home).mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(codex_home)
    t0 = time.time()
    with (out / "distill_events.jsonl").open("w", encoding="utf-8") as ev, \
            (out / "distill_stderr.txt").open("w", encoding="utf-8") as er:
        try:
            cp = subprocess.run(_args(codex_bin, model, effort, out), input=prompt, text=True,
                                stdout=ev, stderr=er, cwd=str(mem), env=env,
                                timeout=minutes * 60 + 600)
            rc, why = cp.returncode, ""
        except subprocess.TimeoutExpired:
            rc, why = -1, f"timed out after {minutes} min + 10"
    report = {
        "out": str(out), "memory": str(mem), "seeds": [str(s) for s in seeds],
        "model": model, "effort": effort, "codex_home": str(codex_home) if codex_home else None,
        "returncode": rc, "why": why, "seconds": round(time.time() - t0),
        "lives": len(list((mem / "previous").glob("life_*"))),
        **audit(mem),
    }
    (out / "distill_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="fresh directory; memory/ is built inside it")
    ap.add_argument("--seed-memory", action="append", required=True,
                    help="an earlier life's episode_001/memory (repeat; oldest first)")
    ap.add_argument("--model", default="gpt-5.6-sol")
    ap.add_argument("--reasoning-effort", default="xhigh")
    ap.add_argument("--codex-home", default=None)
    ap.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    ap.add_argument("--build-only", action="store_true", help="assemble the workspace, run nothing")
    a = ap.parse_args(argv)
    if a.build_only:
        mem = build_workspace(Path(a.out), [Path(s) for s in a.seed_memory])
        print(json.dumps({"memory": str(mem), "lives": len(list((mem / 'previous').glob('life_*')))}))
        return 0
    rep = run(Path(a.out), [Path(s) for s in a.seed_memory], model=a.model,
              effort=a.reasoning_effort,
              codex_home=Path(a.codex_home) if a.codex_home else None, minutes=a.minutes)
    print(json.dumps(rep, indent=2))
    return 0 if rep["returncode"] == 0 and rep["guide_lines"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
