"""Run one arm over the eval split of a cua-lite gym benchmark (cua.bench.local.kicad).

Each task gets its own container through ``gym.make("<env_id>@<task_id>")`` on this
node; the loop feeds screenshots to the arm (``--agent``: ``direct``,
``CodexGuiAgent``; ``mfm``, ``MfmGuiAgent``) and executes its action batches until
terminate/max-steps, then the env's episode-end evaluator prices the trajectory in
[0, 1].

Must run under cua-lite's venv python (3.12) with this repo's root and ``CUA-KiCad``
importable (``mfm``, ``model_channel``, ``gym_codex``) -- ``scripts/run_kicad_arm.sh``
arranges both, plus the docker->podman shim and the image. Standalone example:

    cd <cua-lite>; .venv/bin/python <CUA-KiCad>/gym_codex/run_eval.py \
        --env-id cua.bench.local.kicad --out <dir>

Tasks run one at a time, in order. Results: one JSONL row per task (id, reward, steps,
terminated/truncated, wall time), plus per-task transcripts (codex prompts/replies) and
step screenshots under ``<out>/<task_id>/``. Rows are appended as tasks finish; a rerun
with the same --out skips ids already in the JSONL, so a requeued job continues instead
of restarting.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gym_codex.codex_gui_agent import CodexGuiAgent  # noqa: E402
from gym_codex.mfm_agent import DESIGN_EFFORT, MfmGuiAgent  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("gym_codex.run_eval")


def _eval_rows(gym, env_id: str, tasks: list[str] | None,
               exclude: list[str] | None = None) -> list[dict]:
    """Feasible eval rows (id + domain), filtered by --tasks / --exclude-tasks."""
    rows = []
    for task_id in gym.registry.task_ids(env_id, split="eval"):
        meta = gym.registry.task_metadata(env_id, task_id)
        others = (meta.others if meta else None) or {}
        if others.get("exclude_reason"):
            continue
        if tasks and task_id not in tasks:
            continue
        if exclude and task_id in exclude:
            continue
        rows.append({"task_id": task_id, "domain": others.get("domain")})
    return rows


def _order_rows(rows: list[dict], seed: int | None, out_dir: Path) -> list[dict]:
    """The order tasks run in, and its record.

    The registry lists eval tasks in sorted-id order and a run without a seed takes them
    that way, so for a carry arm "what the model remembers at task k" is one fixed prefix.
    `--task-order-seed N` permutes the selected rows with `random.Random(N)` -- the
    same seed gives the same order on any machine, so a resumed job continues the same
    sequence -- and `None` keeps the registry order. Either way the order is written to
    `<out>/task_order.json` and each row learns its position (`order_index`). A
    resumed run whose recorded seed differs is refused: the rows already in
    results.jsonl were produced under a different history.
    """
    rows = list(rows)
    if seed is not None:
        random.Random(seed).shuffle(rows)
    for i, row in enumerate(rows):
        row["order_index"] = i
    record = {"task_order_seed": seed, "task_ids": [r["task_id"] for r in rows]}
    path = out_dir / "task_order.json"
    if path.exists():
        prior = json.loads(path.read_text())
        if prior.get("task_order_seed") != seed:
            raise SystemExit(f"{path}: recorded task-order seed {prior.get('task_order_seed')!r} "
                             f"!= --task-order-seed {seed!r}; use a fresh --out")
    path.write_text(json.dumps(record, indent=1))
    return rows



#: Benchmark-standard step budgets. These mirror the envs' own configs (cua.bench
#: overrides) so driver loop and env budget can't drift apart.
_DEFAULT_BUDGETS = {
    "cua.bench.local.kicad": 200,      # reference KiCad eval budget
    "cua.bench.local.workflows": 100,  # cua-bench runners.py default
}
_FALLBACK_BUDGET = 30


def _make_kwargs(args) -> dict:
    kw = {"max_steps": args.max_steps,
          "step_timeout": 300.0, "reset_timeout": 1200.0}
    if args.env_id.startswith("cua.bench."):
        # cua.bench gates finish tools behind extra_tools (default []). Without
        # this, a model that finishes early burns the whole remaining budget on
        # refused terminates (measured: canary done at step 38, truncated at
        # 200). Upstream's qwen3_5 configs run with ["terminate"]; their gpt
        # configs run without — scores are computed identically either way.
        kw["extra_tools"] = ["terminate"]
    return kw


async def _make_env(gym, env_id: str, task_id: str, args):
    env = gym.make(f"{env_id}@{task_id}", **_make_kwargs(args))
    return env, await env.reset()


def _cli_kw(args) -> dict:
    """`{"cli": "claude"}` when the Claude Code channel is asked for, else nothing -- so
    the rows and the summary of a codex run carry no `cli` key."""
    return {"cli": "claude"} if getattr(args, "cli", "codex") == "claude" else {}


def _cli_error(args) -> str | None:
    """Why this `--cli claude` combination cannot run, or None."""
    if getattr(args, "cli", "codex") != "claude":
        return None
    if args.codex_base_url:
        return "--cli claude takes no --codex-base-url (an OpenAI-compatible endpoint)"
    return None


def _make_agent(args, task_dir: Path):
    """One agent per task: the same model channel and action contract, two memories."""
    if args.agent == "direct":
        return CodexGuiAgent(model=args.model, effort=args.effort, env_id=args.env_id,
                             transcript_dir=str(task_dir / "codex"), timeout=360,
                             base_url=args.codex_base_url, **_cli_kw(args))
    return MfmGuiAgent(workspace=task_dir / "workspace", model=args.model, effort=args.effort,
                       max_steps=args.max_steps, transcript_dir=task_dir / "codex",
                       base_url=args.codex_base_url, carry_dir=task_dir.parent / "carry",
                       task_id=task_dir.name, **_cli_kw(args))


#: cua.bench's KiCad grader only ever reads /home/cua/kicad_project (a .net there,
#: else the first .kicad_sch exported via kicad-cli). Its setup creates that
#: directory only while copying an initial project, so the 15 design-from-scratch
#: tasks start without it, launch KiCad with no project, and never name the path
#: in the instruction: every arm saved under ~/Documents, ~/<name>/ etc. and scored
#: 0.0 regardless of the schematic (all 15 tasks, all arms, Sep 2026). The fix
#: creates the directory through the task's own session (same user as setup's
#: file copies) and tells the agent where the deliverable goes.
_KICAD_PROJECT_DIR = "/home/cua/kicad_project"
_KICAD_PROJECT_HINT = (
    "Deliverable location: create and save your KiCad project inside the directory "
    f"{_KICAD_PROJECT_DIR}/ (it already exists). Only files saved there are evaluated."
)


async def _apply_kicad_project_hint(env, instruction: str) -> str:
    session = env.unwrapped._cb.session
    await session.run_command(f"mkdir -p '{_KICAD_PROJECT_DIR}'", check=False)
    return f"{instruction.rstrip()}\n\n{_KICAD_PROJECT_HINT}"


#: What the KiCad grader reads, saved beside the trajectory so a finished run can be
#: re-scored offline under any grader without another nine-hour rerun. The grader
#: exports the netlist inside the container and compares it there; nothing else of it
#: survived a run until now.
_GRADER_INPUT_SUFFIXES = (".kicad_sch", ".kicad_pro", ".net")


async def _read_back_netlist(env) -> tuple[str, str] | None:
    """The netlist the grader would score right now, and a token for "has it changed".

    Mirrors cua.bench's own candidate selection (`<task>/main.py`): a `.net` already in
    the project directory, else the first `.kicad_sch` exported with `kicad-cli`. The
    agent drives the GUI and cannot read the project it is building; this is that
    project read back to it, never the reference and never a score.

    Returns `(netlist_text, stamp)`, or None when nothing is saved yet. `stamp` is the
    newest mtime under the project dir, so the export runs only after a save.
    """
    session = env.unwrapped._cb.session
    stamp = await session.run_command(
        f"find '{_KICAD_PROJECT_DIR}' -type f \\( -name '*.kicad_sch' -o -name '*.net' \\) "
        f"-printf '%T@\\n' 2>/dev/null | sort -n | tail -1", check=False)
    stamp_s = (stamp.get("stdout") or "").strip()
    if not stamp_s:
        return None
    found = await session.run_command(
        f"find '{_KICAD_PROJECT_DIR}' -name '*.net' | head -1", check=False)
    net_path = (found.get("stdout") or "").strip()
    if not net_path:
        found = await session.run_command(
            f"find '{_KICAD_PROJECT_DIR}' -name '*.kicad_sch' | head -1", check=False)
        sch = (found.get("stdout") or "").strip()
        if not sch:
            return None
        net_path = "/tmp/kicad_readback.net"
        await session.run_command(
            f"kicad-cli sch export netlist '{sch}' -o '{net_path}'", check=False)
    out = await session.run_command(f"cat '{net_path}'", check=False)
    text = out.get("stdout") or ""
    return (text, stamp_s) if text.strip() else None


async def _save_grader_inputs(env, task_dir: Path) -> dict:
    session = env.unwrapped._cb.session
    saved: dict = {"files": [], "graded_net": None}
    dst = task_dir / "kicad_project"
    listing = await session.run_command(
        f"find '{_KICAD_PROJECT_DIR}' -type f 2>/dev/null", check=False)
    for remote in (listing.get("stdout") or "").splitlines():
        remote = remote.strip()
        if not remote or not remote.endswith(_GRADER_INPUT_SUFFIXES):
            continue
        rel = remote[len(_KICAD_PROJECT_DIR):].lstrip("/")
        try:
            data = await session.read_bytes(remote)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] could not read %s: %s", task_dir.name, remote, exc)
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        saved["files"].append(rel)
    # The netlist the grader would compare, produced the way the grader produces it:
    # a .net already in the project dir, else the first .kicad_sch exported by kicad-cli.
    nets = [f for f in saved["files"] if f.endswith(".net")]
    if nets:
        saved["graded_net"] = f"kicad_project/{nets[0]}"
    else:
        found = await session.run_command(
            f"find '{_KICAD_PROJECT_DIR}' -name '*.kicad_sch' | head -1", check=False)
        sch = (found.get("stdout") or "").strip()
        if sch:
            out_net = "/tmp/mfm_graded.net"
            await session.run_command(
                f"kicad-cli sch export netlist '{sch}' -o '{out_net}'", check=False)
            try:
                data = await session.read_bytes(out_net)
            except Exception:  # noqa: BLE001
                data = b""
            if data.strip():
                (task_dir / "graded.net").write_bytes(data)
                saved["graded_net"] = "graded.net"
    return saved


async def run_task(gym, row: dict, args, out_dir: Path) -> dict:
    task_id = row["task_id"]
    task_dir = out_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    agent = _make_agent(args, task_dir)
    t0 = time.time()
    result: dict = {"task_id": task_id, "domain": row["domain"], "model": args.model,
                    "effort": args.effort, "agent": args.agent, "reward": None,
                    "order_index": row.get("order_index"),
                    "endpoint": args.codex_base_url or "hosted",
                    "steps": 0, "terminated": False, "truncated": False, "error": None}
    result.update(_cli_kw(args))
    env = None
    steps: list[dict] = []
    try:
        env, obs = await _make_env(gym, args.env_id, task_id, args)
        instruction = obs.text or ""
        if args.env_id.endswith(".kicad"):
            instruction = await _apply_kicad_project_hint(env, instruction)
            result["instruction_hint"] = "kicad_project"
        screenshot = obs.image
        (task_dir / "instruction.txt").write_text(instruction, encoding="utf-8")
        if isinstance(agent, MfmGuiAgent):
            # A modify task starts from a project that already holds a schematic. The
            # design call cannot reach the container, so its netlist is read back here
            # and handed over before the first predict; a from-scratch task has no
            # project yet and seeds nothing. Never fatal: the design call then runs
            # blind to the existing circuit.
            try:
                back = await _read_back_netlist(env)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] initial netlist read-back failed: %s", task_id, exc)
                back = None
            result["design_seeded"] = bool(back) and agent.seed_design(back[0])
        step_error: str | None = None
        for step_idx in range(args.max_steps):
            if screenshot:
                (task_dir / f"step_{step_idx:02d}.png").write_bytes(screenshot)
            if not screenshot:
                logger.warning("[%s] no screenshot at step %d", task_id, step_idx)
            # codex exec is a blocking subprocess; keep the loop free for other tasks.
            # Retried with backoff: hosted codex intermittently returns transient
            # failures ("Selected model is at capacity", timeouts) that killed a
            # whole 85-step episode when raised straight through.
            for attempt, delay in enumerate((0, 30, 90, 180)):
                if delay:
                    logger.warning("[%s] codex retry %d in %ds", task_id, attempt, delay)
                    await asyncio.sleep(delay)
                try:
                    reply, calls, done = await asyncio.to_thread(
                        agent.predict, instruction, screenshot or b"",
                        step_idx, args.max_steps)
                    break
                except Exception as exc:  # noqa: BLE001
                    predict_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("[%s] codex call failed: %s", task_id, predict_error)
            else:
                step_error = f"codex unavailable after retries: {predict_error}"
                break
            steps.append({"step": step_idx, "reply": reply,
                          "calls": calls, "done": done})
            if not calls:            # unparseable turn: burn the step, feedback queued
                result["steps"] = step_idx + 1
                continue
            try:
                sr = await env.step(calls)
            except Exception as exc:  # noqa: BLE001 — env hiccup: stop acting, still evaluate
                step_error = f"{type(exc).__name__}: {exc}"
                logger.warning("[%s] step %d failed (%s); forcing terminate",
                               task_id, step_idx, step_error)
                break
            result["steps"] = step_idx + 1
            for r in sr.results:
                if r.images:
                    screenshot = r.images[-1]
                if r.error:
                    agent.add_feedback(f"env error: {r.error}")
            result["terminated"] = sr.terminated
            result["truncated"] = sr.truncated
            if sr.terminated or sr.truncated:
                result["reward"] = sr.reward
                break
        if not (result["terminated"] or result["truncated"]):
            # Step budget exhausted, every turn unparseable, or a mid-episode step
            # error: force the episode shut so the evaluator still prices the state.
            sr = await env.step([{"id": "call_final", "type": "function",
                                  "function": {"name": "terminate",
                                               "arguments": {"status": "failure",
                                                             "reason": step_error or "step budget exhausted"}}}])
            result["terminated"] = sr.terminated
            result["reward"] = sr.reward
            if step_error:
                result["error"] = f"step error (evaluated anyway): {step_error}"
        if args.env_id.endswith(".kicad"):
            try:
                result["grader_inputs"] = await _save_grader_inputs(env, task_dir)
            except Exception:  # noqa: BLE001 -- the score is already in hand
                logger.warning("[%s] saving the grader inputs failed", task_id, exc_info=True)
    except Exception as exc:  # noqa: BLE001 — one task's crash must not sink the batch
        logger.exception("[%s] failed", task_id)
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if steps:
            (task_dir / "trajectory.json").write_text(
                json.dumps(steps, indent=1, default=str), encoding="utf-8")
        if env is not None:
            try:
                await env.close()
            except Exception:
                logger.warning("[%s] env.close failed", task_id, exc_info=True)
    if hasattr(agent, "finish"):
        # A carry arm's episode-end work (publishing this task's record for the next
        # one) happens after the env is closed, so its cost is on the agent's clock
        # and not the container's.
        try:
            await asyncio.to_thread(agent.finish, result["reward"], result["error"])
        except Exception:  # noqa: BLE001 -- the score is already in hand
            logger.warning("[%s] agent finish failed", task_id, exc_info=True)
    result["wall_s"] = round(time.time() - t0, 1)
    if hasattr(agent, "audit"):
        try:
            result["audit"] = agent.audit()
        except Exception:  # noqa: BLE001 — the audit must not sink a scored task
            logger.warning("[%s] agent audit failed", task_id, exc_info=True)
    logger.info("[%s] reward=%s steps=%d wall=%.0fs error=%s",
                task_id, result["reward"], result["steps"], result["wall_s"], result["error"])
    return result


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-id", default="cua.bench.local.kicad",
                   help="cua-lite gym env id (the paper's runs: cua.bench.local.kicad)")
    p.add_argument("--tasks", default=None, help="comma-separated task ids")
    p.add_argument("--exclude-tasks", default=None,
                   help="comma-separated task ids to skip (a6414tw4: its reference is an "
                        "empty netlist, rewarding the submission of nothing)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--task-order-seed", type=int, default=None,
                   help="the seed of a run: shuffle the selected tasks with it (default: "
                        "the registry's sorted-id order). For an arm that carries memory "
                        "across tasks, what a task's memory holds depends on which tasks "
                        "came before it. Recorded in <out>/task_order.json; a resumed run "
                        "must pass the same seed.")
    p.add_argument("--model", default="gpt-6-astra")
    p.add_argument("--effort", default="high")
    p.add_argument("--agent", choices=("direct", "mfm"), default="mfm",
                   help="memory arm: direct (no persistent memory), mfm (MFM: the log "
                        "plus the episode store and a multi-batch plan queue, with the "
                        "finished tasks' records and a persistent notes/ carried into "
                        "each task's workspace under <out>/carry; gym_codex/mfm_agent.py)")
    p.add_argument("--cli", choices=("codex", "claude"), default="codex",
                   help="which CLI carries the model: codex "
                        "(default), or claude -- Anthropic models through Claude Code "
                        "(model_channel/claude_backend.py; the mfm arm under "
                        "CLAUDE_BIN=model_channel/claude_sandbox.sh). Rows and summary "
                        "carry `cli` only when it is claude.")
    p.add_argument("--codex-base-url", default=os.environ.get("CODEX_BASE_URL") or None,
                   help="OpenAI-compatible endpoint for codex instead of the account's "
                        "hosted models (e.g. https://openrouter.ai/api/v1; the sandbox "
                        "then needs CODEX_SANDBOX_ALLOW=<host>:443, LOCAL_API_KEY and "
                        "CODEX_SANDBOX_NO_AUTH=1, as PROVIDER=openrouter in "
                        "scripts/run_kicad_arm.sh sets them). "
                        "Default $CODEX_BASE_URL, else hosted.")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    args.max_steps = _DEFAULT_BUDGETS.get(args.env_id, _FALLBACK_BUDGET)
    if _cli_error(args):
        p.error(_cli_error(args))
    logger.info("env=%s budget=%d steps", args.env_id, args.max_steps)

    import lite.gym as gym  # after run_kicad_arm.sh has set up PATH/PODMAN_* for the shim

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    done_ids: set[str] = set()
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error") is None:
                done_ids.add(r["task_id"])

    rows = _eval_rows(gym, args.env_id,
                      args.tasks.split(",") if args.tasks else None,
                      args.exclude_tasks.split(",") if args.exclude_tasks else None)
    rows = _order_rows(rows, args.task_order_seed, out_dir)
    if args.limit:
        rows = rows[: args.limit]
    todo = [r for r in rows if r["task_id"] not in done_ids]
    if args.task_order_seed is not None:
        logger.info("task order (seed %d): %s", args.task_order_seed,
                    " ".join(r["task_id"] for r in rows))
    logger.info("%d tasks selected (%d already done, %d to run)",
                len(rows), len(rows) - len(todo), len(todo))

    # One task at a time, in order: the mfm arm carries memory from task to task, and
    # KiCad's per-task install fails under concurrent load.
    results = []
    for row in todo:
        res = await run_task(gym, row, args, out_dir)
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res) + "\n")
        results.append(res)

    all_rows = results + [json.loads(l) for l in results_path.read_text().splitlines()
                          if json.loads(l)["task_id"] in done_ids]
    scored = [r for r in all_rows if r.get("reward") is not None]
    mean = sum(r["reward"] for r in scored) / len(scored) if scored else float("nan")
    errors = [r for r in all_rows if r.get("error")]
    summary = {"n_selected": len(rows), "n_scored": len(scored),
               "n_errors": len(errors), "mean_reward": mean,
               "model": args.model, "effort": args.effort, "agent": args.agent,
               "endpoint": args.codex_base_url or "hosted",
               "max_steps": args.max_steps, "env_id": args.env_id,
               "task_order_seed": args.task_order_seed}
    summary.update(_cli_kw(args))
    if args.agent == "mfm":
        summary["design"] = {"design_turn": True, "design_effort": DESIGN_EFFORT,
                             "conventions": True}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    logger.info("SUMMARY %s", json.dumps(summary))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
