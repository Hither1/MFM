#!/usr/bin/env python3
"""Stage the carry-only chain's head-to-head pair for the HF dataset Ced-Collab/MCUData:

    carry-only-era/gen2/of3r_mfm/    gen-2 contract, MCU b2f8c832 -- 16/24, the carry-only record
    carry-only-era/gen3b/of3g_mfm/   gen-3b contract, MCU cf86f15a -- a snapshot while it runs

Each run gets what stage_hf_mfm_era.py stages (provenance.json, trajectory/, codex_sessions/,
launcher/) plus

    trajectory/episode_001/hires.tar   the 640x360 per-step JPEG record where the run kept one
    profile.txt                        scripts/turn_profile.py over the run (cells per turn by kind,
                                       steps per turn, memory file sizes)
    harness-code/mcu/                  mcu_worldmodel/ and the arm scripts at the run's MCU commit
    harness-code/mfm/                  the mfm package and the launch scripts at the run's MFM commit

and the era gets diff-gen2-to-gen3b/ (the code diffs between the two commits and the diff of the
two contracts as the models received them), runs.csv, README.md, manifest.json.

Written 2026-09-10 on the user's request for a head-to-head comparison. Reuses the mfm-era
staging module (same anonymisation, same rollout slimming, same trajectory layout).
Usage: python3 stage_hf_carry_only_era.py [--skip-sessions] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_hf_mfm_era as M  # noqa: E402

ERA = "carry-only-era"
M.OUT = M.STAGING / ERA
OUT = M.OUT
HERE = Path(__file__).resolve().parent

RUNS = [
    dict(group="gen2", arm="of3r_mfm", mcu=M.GRID, mfm=M.MFM_GRID, home=M.HOMES / "of3r_mfm",
         green=M.GRID / "output/20260908_191331_50558",
         condition="carry-only (seed: of3_mfm's record; no harness-pushed facts), gen-2 contract, "
                   "one codex thread compacted (--session-turns 0 --compact), frames 320x180, nyu plan",
         headline="16/24 at 41.6k steps / 13 h -- the carry-only record (diamonds at step 17921, "
                  "obsidian 32685, netherrack 41584; one death in the Nether)",
         generation="gen 2",
         reflog="live MCU worktree HEAD at b2f8c832 from 2026-09-08 17:09:28 to 2026-09-09 02:08:32 "
                "(git reflog show spatial-grid); the run launched 2026-09-08 19:13"),
    dict(group="gen3b", arm="of3g_mfm", mcu=M.GRID, mfm=M.MFM_GRID, home=M.HOMES / "of3g_mfm",
         green=M.GRID / "output/20260909_213843_9095",
         condition="carry-only (seed: of3r_mfm's record, which carries of3_mfm), gen-3b contract "
                   "(codex-native skills, thread-persists sentence, digest as 20 facts, open-loop pace "
                   "rule), one codex thread compacted, frames 640x360, OpenRouter",
         headline="running: 9/24 at step 4420 (+56 min, earlier than gen 2's +1h07), then a "
                  "3.5-hour surface preparation before the first descent",
         generation="gen 3b",
         reflog="live MCU worktree HEAD at cf86f15a from 2026-09-09 21:26:13 (git reflog show "
                "spatial-grid); the run launched 2026-09-09 21:38"),
]

MCU_PATHS = ["mcu_worldmodel", "scripts/run-arm.sh", "scripts/launch-og.sh", "scripts/codex-openrouter.sh",
             "scripts/codex-home.sh", "scripts/stop_arm.py", "scripts/watchdog.sh"]
MFM_PATHS = ["mfm", "tasks/mfm-three-layer.spatial-grid/scripts/launch_ofr.sh",
             "tasks/mfm-three-layer.spatial-grid/scripts/chain_ofr.sh",
             "tasks/mfm-three-layer.spatial-grid/scripts/launch_g3.sh"]


def git_archive(repo: Path, sha: str, paths: list[str], dst: Path) -> list[str]:
    """Extract `paths` of `repo` at `sha` into dst (paths missing at that commit are skipped)."""
    dst.mkdir(parents=True, exist_ok=True)
    present = []
    for p in paths:
        if subprocess.run(["git", "cat-file", "-e", f"{sha}:{p}"], cwd=repo, capture_output=True).returncode == 0:
            present.append(p)
    ar = subprocess.run(["git", "archive", "--format=tar", sha, *present], cwd=repo, capture_output=True)
    if ar.returncode != 0:
        raise SystemExit(f"git archive failed in {repo}: {ar.stderr.decode(errors='replace')}")
    subprocess.run(["tar", "-x", "-C", str(dst)], input=ar.stdout, check=True)
    return present


def wall_timeline(purple: Path) -> tuple[str | None, list[dict]]:
    """Milestones with the wall minutes since the first codex turn."""
    txt = purple.read_text(errors="replace")
    t0m = re.search(r"^(\S+ \S+) \| INFO .*\[codex\] turn 1 ", txt, re.M)
    if not t0m:
        return None, []
    t0 = datetime.strptime(t0m.group(1), "%Y-%m-%d %H:%M:%S.%f")
    out = []
    for m in re.finditer(r"^(\S+ \S+) \| SUCCESS .*\[milestone\] (\w+) at step (\d+) \((\d+)/24\)", txt, re.M):
        t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
        out.append({"milestone": m.group(2), "step": int(m.group(3)), "n": int(m.group(4)),
                    "wall_min": round((t - t0).total_seconds() / 60, 1)})
    return t0m.group(1), out


def profile(arm: str) -> str:
    r = subprocess.run([sys.executable, str(HERE / "turn_profile.py"), str(M.GRID), arm],
                       capture_output=True, text=True)
    return r.stdout + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else "")


def copy_trajectory_snapshot(src_ep: Path, dst_ep: Path):
    """The module's copy_trajectory, tolerant of a running arm: tar's exit 1 ("file changed as we
    read it") is the episode store growing under the snapshot, not a failure."""
    dst_ep.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete", "--exclude", "/memory/previous/life_*/", "--exclude", "/memory/episodes/",
           str(src_ep) + "/", str(dst_ep) + "/"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 23, 24):       # 23/24: files vanished or changed during the copy
        raise SystemExit(f"rsync failed for {src_ep}: {r.stderr}")
    if (dst_ep / "memory/episodes").exists():
        shutil.rmtree(dst_ep / "memory/episodes")
    tar = dst_ep / "memory/episodes.tar"
    if (src_ep / "memory/episodes").exists():
        r = subprocess.run(["tar", "--warning=no-file-changed", "-cf", str(tar), "-C", str(src_ep / "memory"), "episodes"],
                           capture_output=True, text=True)
        if r.returncode not in (0, 1):
            raise SystemExit(f"tar failed for {src_ep}: {r.stderr}")


M.copy_trajectory = copy_trajectory_snapshot


def stage(r: dict, args) -> dict | None:
    prov = M.stage_run(r, args)
    if not prov:
        return None
    arm = r["arm"]
    dst = OUT / r["group"] / arm
    ep = dst / "trajectory/episode_001"
    # hires: one 640x360 JPEG per step -- packed, PNG/JPEG do not compress and the repo has a file budget
    hires = ep / "hires"
    if hires.is_dir():
        n = sum(1 for _ in hires.iterdir())
        subprocess.run(["tar", "-cf", str(ep / "hires.tar"), "-C", str(ep), "hires"], check=True)
        shutil.rmtree(hires)
        prov["staged"]["hires_packed"] = f"trajectory/episode_001/hires.tar ({n} files; `tar -xf hires.tar` inside episode_001/ restores hires/<step>.jpg)"
    # the run's own wall clock
    t0, tl = wall_timeline(M.GRID / "logs" / f"{arm}_purple.log")
    prov["first_codex_turn_local"] = t0
    prov["milestone_timeline_wall"] = tl
    # a snapshot of a running arm
    purple = (M.GRID / "logs" / f"{arm}_purple.log").read_text(errors="replace")
    pidfile = M.GRID / "logs" / f"{arm}_launch.pid"
    alive = False
    if pidfile.exists():
        try:
            alive = subprocess.run(["ps", "-p", pidfile.read_text().split()[0]], capture_output=True).returncode == 0
        except Exception:
            alive = False
    steps = re.findall(r"\[adapter\] step (\d+)", purple)
    turns = len(re.findall(r"\[codex\] turn \d+ model", purple))
    prov["snapshot"] = {"run_in_progress_at_staging": alive, "staged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S +0800"),
                        "last_step_in_purple_log": int(steps[-1]) if steps else None, "codex_turns": turns}
    if alive:
        prov["ended"] = "still running at staging time (this is a snapshot; the final record is re-staged when the run ends)"
    # generation, code identity verified by the reflog
    prov["generation"] = r["generation"]
    prov["code_identity"]["verified_by"] = r["reflog"]
    # the harness code at the run's commits
    hc = dst / "harness-code"
    mcu_sha = prov["code_identity"]["mcu"]["commit"]
    mfm_sha = prov["code_identity"]["mfm_package"]["commit"]
    got_mcu = git_archive(r["mcu"], mcu_sha, MCU_PATHS, hc / "mcu")
    got_mfm = git_archive(r["mfm"], mfm_sha, MFM_PATHS, hc / "mfm")
    (hc / "INDEX.md").write_text(
        f"# harness code of {arm}\n\n"
        f"- `mcu/` -- MCU-AgentBeats (spatial-grid branch) at `{mcu_sha}`: {', '.join(got_mcu)}\n"
        f"- `mfm/` -- the mfm package repo (spatial-grid branch) at `{mfm_sha}`: {', '.join(got_mfm)}\n\n"
        "`mcu_worldmodel/prompts.py` holds the contract template (`MINIMAL_CONTRACT`), `agent.py` the turn loop and the\n"
        "memory blocks, `skills.py` the codex-native skills catalog, `codex_backend.py` the codex exec wrapper;\n"
        "`mfm/memory/` is the episode store and retrieval ([RECALL]). The contract as this run received it is\n"
        "`trajectory/episode_001/memory/AGENTS.md`.\n")
    M.anonymise_tree(hc)
    prov["staged"]["harness_code"] = {"mcu": got_mcu, "mfm": got_mfm}
    (dst / "profile.txt").write_text(profile(arm))
    size, nfiles = M.du(dst)
    prov["staged"]["bytes"], prov["staged"]["files"] = size, nfiles
    txt = json.dumps(prov, indent=1)
    for old_, rep in M.SUBS:
        txt = txt.replace(old_, rep)
    (dst / "provenance.json").write_text(txt)
    return json.loads(txt)


def diffs(provs: list[dict]) -> None:
    a, b = provs[0], provs[1]
    d = OUT / "diff-gen2-to-gen3b"
    d.mkdir(exist_ok=True)
    for repo, key, paths, name in ((M.GRID, "mcu", ["mcu_worldmodel", "scripts"], "mcu.patch"),
                                   (M.MFM_GRID, "mfm_package", ["mfm"], "mfm.patch")):
        s0, s1 = a["code_identity"][key]["commit"], b["code_identity"][key]["commit"]
        r = subprocess.run(["git", "diff", s0, s1, "--", *paths], cwd=repo, capture_output=True, text=True)
        (d / name).write_text(f"# git diff {s0[:8]}..{s1[:8]} -- {' '.join(paths)} ({repo.name})\n" + r.stdout)
    c0 = OUT / a["group"] / a["run"] / "trajectory/episode_001/memory/AGENTS.md"
    c1 = OUT / b["group"] / b["run"] / "trajectory/episode_001/memory/AGENTS.md"
    r = subprocess.run(["diff", "-u", str(c0), str(c1)], capture_output=True, text=True)
    (d / "contract.diff").write_text(f"# the contract as received: {a['run']} (gen 2) -> {b['run']} (gen 3b)\n" + r.stdout)
    M.anonymise_tree(d)
    (d / "README.md").write_text(
        "# gen 2 -> gen 3b: what changed in the harness\n\n"
        f"- `mcu.patch`: `mcu_worldmodel/` and `scripts/` between MCU `{a['code_identity']['mcu']['commit'][:8]}` "
        f"({a['run']}) and `{b['code_identity']['mcu']['commit'][:8]}` ({b['run']})\n"
        f"- `mfm.patch`: the mfm package between `{a['code_identity']['mfm_package']['commit'][:8]}` and "
        f"`{b['code_identity']['mfm_package']['commit'][:8]}` (retrieval: RECALL streak threshold, ignored kinds)\n"
        "- `contract.diff`: the two `AGENTS.md` files as the models received them (the contract template rendered "
        "for each run: one-thread persistence sentence, digest discipline, the Routines / Rules of play / Improve "
        "yourself sections, the codex-native skills pointer)\n")


def readme(provs: list[dict]) -> None:
    a, b = provs[0], provs[1]

    def tl(p):
        return {m["milestone"]: m for m in p["milestone_timeline_wall"]}

    ta, tb = tl(a), tl(b)
    names = [m["milestone"] for m in a["milestone_timeline_wall"]]
    for m in b["milestone_timeline_wall"]:
        if m["milestone"] not in names:
            names.append(m["milestone"])
    rows = []
    for n in names:
        x, y = ta.get(n), tb.get(n)
        rows.append(f"| {n} | " + (f"{x['n']}/24 @{x['step']} (+{x['wall_min']:.0f} min)" if x else "--") + " | "
                    + (f"{y['n']}/24 @{y['step']} (+{y['wall_min']:.0f} min)" if y else "--") + " |")
    snap = b["snapshot"]
    txt = f"""# carry-only era: gen 2 against gen 3b, head to head ({datetime.now():%Y-%m-%d})

Two lives of the **mfm arm** in the same world (seed 0, fixed spawn), same model (`{a['model']}`, effort
{a['reasoning_effort']}), same task (`ender_dragon`, 100,000 steps under a 12-13 h wall), same lineage
(gen 3b's seed is gen 2's record, which carried the life before it), **no harness-pushed facts in
either** -- the harness puts nothing from earlier lives in front of the model; reading `previous/` is
the model's act. What differs is the harness code and the contract:

| | `{a['run']}` (gen 2) | `{b['run']}` (gen 3b) |
|---|---|---|
| MCU commit | `{a['code_identity']['mcu']['commit'][:8]}` | `{b['code_identity']['mcu']['commit'][:8]}` |
| mfm package commit | `{a['code_identity']['mfm_package']['commit'][:8]}` | `{b['code_identity']['mfm_package']['commit'][:8]}` |
| contract | gen 2 (`memory/AGENTS.md`) | gen 3b: codex-native skills, "the thread persists", digest = 20 facts, open-loop pace rule |
| frames | 320x180 | 640x360 (+ `hires.tar`, the per-step record) |
| provider | nyu plan | OpenRouter |
| result | **{a['milestones']}** at {a['steps_run']} steps | **{b['milestones']}** at step {snap['last_step_in_purple_log']} ({'still running' if snap['run_in_progress_at_staging'] else 'ended'}; snapshot {snap['staged_at']}) |
| deaths | {a['deaths']} | {b['deaths']} |

Milestones by step and by wall time since the first codex turn:

| milestone | gen 2 | gen 3b |
|---|---|---|
""" + "\n".join(rows) + f"""

The gen-3b snapshot was taken while the run was in progress (turn {snap['codex_turns']}); its
`trajectory/`, `codex_sessions/` and `launcher/` are complete up to that moment. `profile.txt` in each
run directory is the per-turn behaviour profile (`turn_profile.py`): exec cells per turn by kind
(skill reads, frame looks, episode queries, previous-life reads), steps per plan entry and per turn,
turn interval, the sizes of `mine/digest.md`, `mine/working.md`, `mine/notes.md`.

## Layout

```
carry-only-era/
  gen2/{a['run']}/  gen3b/{b['run']}/
    provenance.json            run, flags, seeds, score, milestone timeline (steps and wall minutes),
                               deaths, code identity (commit + the worktree reflog that verifies it),
                               snapshot state, staged sizes
    profile.txt                turn_profile.py over the run
    trajectory/episode_001/    memory/ (logs.txt, index.jsonl, episodes.tar, mine/, tools/, references/,
                               skills/, AGENTS.md -- the contract as received), codex_turns/ (per-turn
                               prompt + codex events), attach/, worldmodel_report.json; hires.tar (gen 3b)
                               memory/previous/LINEAGE.json names the stripped seed lives
    codex_sessions/            the codex rollouts, slimmed (compaction snapshots and base64 frames out)
    launcher/                  launch/purple/green/client/wall logs, the toml
    harness-code/              mcu_worldmodel/ + arm scripts and the mfm package at the run's commits
  diff-gen2-to-gen3b/          mcu.patch, mfm.patch, contract.diff
  runs.csv, manifest.json
```

Text files are anonymised as in `mfm-era/` (paths -> `<MCU>`, `<MFM>`, `<CODEX_HOMES>`, `<HOME>`; user
name -> `user`). Neither run has an evaluator video: gen 2 was wall-stopped, gen 3b is running.
"""
    (OUT / "README.md").write_text(txt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sessions", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="re-stage these arms; the others are read back from their provenance.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    provs = []
    for r in RUNS:
        if args.only and r["arm"] not in args.only:
            f = OUT / r["group"] / r["arm"] / "provenance.json"
            if f.exists():
                provs.append(json.load(open(f)))
            continue
        p = stage(r, args)
        if p:
            provs.append(p)
    if args.dry_run:
        return
    diffs(provs)
    M.write_runs_csv(provs)
    stats = M.STAGING / "stats/runs.csv"
    if stats.exists():
        existing = {row.split(",")[0] for row in stats.read_text().splitlines()[1:]}
        with open(stats, "a", newline="") as fh:
            w = csv.writer(fh)
            for p in provs:
                if p["run"] not in existing:
                    w.writerow([p["run"], "kill_ender_dragon", "mfm", p["condition"], "carry_only_era", p["max_steps"], p["score"],
                                p["milestones"], p["codex"]["calls"], " ".join(f"{k}@{v}" for k, v in p["milestones_all"].items())])
    readme(provs)
    tot, n = M.du(OUT)
    json.dump({"dataset_dir": ERA, "staged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S +0800"),
               "runs": [{"run": p["run"], "group": p["group"], "generation": p["generation"], "score": p["score"],
                         "milestones": p["milestones"], "steps": p["steps_run"], "snapshot": p["snapshot"],
                         "bytes": p["staged"]["bytes"], "files": p["staged"]["files"]} for p in provs],
               "bytes_total": tot, "files_total": n,
               "left_out": ["memory/previous/life_*/ (copies of the seed lives; LINEAGE.json names them)",
                            "codex rollouts' compaction snapshots and base64 frames"]},
              open(OUT / "manifest.json", "w"), indent=1)
    print(f"staged {len(provs)} runs, {tot/1e9:.2f} GB, {n} files -> {OUT}")


if __name__ == "__main__":
    main()
