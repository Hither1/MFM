"""A live smoke test of the VISTA arm against the real codex app-server.

The offline tests drive everything through `tests/fake_appserver.py`; what only a real
run can show is that codex 0.153's model turn accepts the dynamic tools, issues
`item/tool/call`, and takes the steered image and the interrupted-turn inspection
visuals. This runs the KiCad adapter on a synthetic three-step "task" with tiny
screenshots -- a handful of model calls at low effort -- and prints the audit.

    CODEX_BIN=/path/to/codex \\
    python -m mfm.vista.smoke --out /var/tmp/vista-smoke-$USER [--model gpt-5.6-sol]

The workspace goes under /var/tmp (codex refuses helper binaries under /tmp); auth is
read through `$CODEX_EVAL_HOME/auth.json` (default ~/.codex-eval) the way the bare-binary
path of the other arms reads it. Spends the shared account's quota: run it on purpose.
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import time
from pathlib import Path


def _png(step: int, size=(640, 360)) -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, (30 + 40 * step, 60, 90))
    d = ImageDraw.Draw(im)
    d.rectangle((100 + 60 * step, 120, 220 + 60 * step, 200), fill=(220, 40, 40))
    d.text((20, 20), f"step {step}: the red box moved right", fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="a directory under /var/tmp")
    ap.add_argument("--model", default="gpt-5.6-sol")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait for each play")
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "CUA-KiCad"))
    from gym_codex.vista_agent import VistaGuiAgent

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    agent = VistaGuiAgent(workspace=out / "workspace", model=args.model, effort=args.effort,
                          max_steps=args.steps, transcript_dir=out / "codex", timeout=args.timeout,
                          thread_bytes=None, close_timeout=90)
    task = ("SMOKE TEST of the harness, not a real desktop: the screenshot shows a red box. "
            "On each step, call `play` with one click on the red box, then on the last step "
            "terminate with success. Before the first play, write one line to GUIDE.md, and "
            "after the first result, `inspect` turn 0 and turn 1 to compare them.")
    t0 = time.time()
    done = False
    for step in range(args.steps):
        reply, calls, done = agent.predict(task, _png(step), step, args.steps)
        print(f"step {step}: done={done} calls={json.dumps(calls)[:200]}\n  reply: {reply[:200]!r}")
        if done:
            break
    agent.finish(reward=1.0 if done else 0.0, error=None)
    audit = agent.audit()
    print(json.dumps(audit, indent=1, default=str))
    print(f"wall {time.time() - t0:.0f}s; transcripts under {out / 'codex'}")
    print("GUIDE.md:", (out / "workspace" / "GUIDE.md").read_text()[:300])
    ok = audit["vista"]["turns"] >= 1 and audit["vista"]["failure"] is None
    print("SMOKE", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
