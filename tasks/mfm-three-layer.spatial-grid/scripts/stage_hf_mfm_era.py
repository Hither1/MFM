#!/usr/bin/env python3
"""Stage the mfm-era trajectories for the HF dataset Ced-Collab/MCUData.

Reads the run directories of both tracks READ-ONLY (MFM-grid/MCU, MFM-grid-merge-mcu,
MFM/MCU, the codex homes, the launcher logs) and writes

    MCU-AgentBeats/output/hf_staging/mfm-era/<group>/<arm>/
        provenance.json            run, task, flags, seeds, score, timeline, deaths, code identity
        trajectory/episode_001/    the agent workspace: memory/ (logs.txt, episodes/, index.jsonl,
                                   grid.jsonl, mine/, tools/, references/, skills/, AGENTS.md),
                                   codex_turns/ (per-turn prompt + codex events), attach/, report
                                   -- memory/previous/life_*/ (copies of OTHER runs) replaced by LINEAGE.json
        codex_sessions/            the codex rollouts, slimmed (compaction snapshots and base64 images out)
        launcher/                  launch/purple/green/wall logs, the toml, the evaluator result if any
        evaluator/                 episode_1.mp4 + milestone_tracking.json where the green wrote them
    mfm-era/lineage/og23_distill/  the distilled memory (GUIDE.md, procedures, reflex) + the distiller record
    mfm-era/agent-code/INDEX.md    every file the model wrote, across runs
    mfm-era/runs.csv, manifest.json, README.md

Text files are anonymised (paths, user name). PNG/MP4 untouched.
Usage: python3 stage_hf_mfm_era.py [--only ARM ...] [--skip-sessions] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

COLLAB = Path("/datapool/data3/storage/ruihan/data_share/jh/Collab")
STAGING = COLLAB / "MCU-AgentBeats/output/hf_staging"
OUT = STAGING / "mfm-era"
VARTMP = Path("/var/tmp/mcu-codex-ruihan")

GRID = COLLAB / "MFM-grid/MCU"            # live spatial-grid MCU worktree (og1-5, og10-15, og19-24)
MERGE = COLLAB / "MFM-grid-merge-mcu"     # spatial-grid-merge worktree (og6-9, og16-18)
DRAGON = COLLAB / "MFM/MCU"               # dragon-obsidian MCU worktree (ob*, obf*)
MFM_GRID = COLLAB / "MFM-grid"            # mfm package, branch spatial-grid
MFM_DRAGON = COLLAB / "MFM"               # mfm package, branch dragon-obsidian
HOMES = COLLAB / "codex-homes"

WORLD = "MCU-AgentBeats green agent (MineStudio), world seed 0, fixed spawn (-3009.5, 71, -5572.5)"

# ----------------------------------------------------------------------------------------------
# The runs. `green` is the evaluator's timestamped output dir (mp4 + milestone_tracking.json),
# known only where the green flushed it (matched by pid in the green log or by the milestone steps).
# ----------------------------------------------------------------------------------------------
RUNS = [
    # ---- full task: ender_dragon, 24,000 steps, from nothing ----
    dict(group="full-dragon", arm="obf2_mfm", mcu=DRAGON, mfm=MFM_DRAGON, home=None,
         green=DRAGON / "output/20260906_232108_34492",
         condition="carry (17 lives) + harness-pushed [KNOWN SITES]",
         headline="54.17 (13/24): the full-task record (previous best 45.83)"),
    dict(group="full-dragon", arm="obf1_mfm", mcu=DRAGON, mfm=MFM_DRAGON, home=None,
         green=DRAGON / "output/20260906_122347_28196",
         condition="carry (8 lives) + harness-pushed [KNOWN SITES]",
         headline="37.5 (9/24): the first full-task carry run; obf2's parent"),
    # ---- half task: ender_dragon_half, 60,000-step budget under a 10 h wall cap ----
    dict(group="half-dragon/carry", arm="og9_mfm", mcu=MERGE, mfm=MFM_GRID, home=HOMES / "og9_mfm", green=None,
         condition="carry (16 lives), thin contract, no pushed sites",
         headline="66.67 (16/24): the half-task record; obsidian at 8651, into the Nether at 17714"),
    dict(group="half-dragon/carry", arm="og8_mfm", mcu=MERGE, mfm=MFM_GRID, home=HOMES / "og8_mfm", green=None,
         condition="carry (15 lives), full contract, no pushed sites",
         headline="62.5 (15/24) with 3 deaths at the same lava pool: the repeat-death exemplar"),
    dict(group="half-dragon/carry", arm="og19_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og19_mfm", green=None,
         condition="carry (23 lives, the largest), thin + own + the digest note + the Nether lock",
         headline="58.33 (14/24): obsidian at 16933; mine/digest.md is the model's own digest of 23 lives"),
    dict(group="half-dragon/from-scratch", arm="og12_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og12_mfm",
         green=GRID / "output/20260907_075055_39608",
         condition="from scratch, full contract",
         headline="62.5 (15/24): the earliest obsidian on record (step 6134); into the Nether at 30305, died there"),
    dict(group="half-dragon/from-scratch", arm="og16_mfm", mcu=MERGE, mfm=MFM_GRID, home=VARTMP / "og16_mfm", green=None,
         condition="from scratch, thin contract, all guards of 2026-09-07",
         headline="62.5 (15/24) at 43.4k steps: the from-scratch control for og14/og17"),
    dict(group="half-dragon/self-harness", arm="og14_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og14_mfm", green=None,
         condition="from scratch, thin + atoms + own (the model writes its procedures)",
         headline="62.5 (15/24), 0 deaths: obsidian at 15505 from scratch; 7 own scripts called 177 times"),
    dict(group="half-dragon/self-harness", arm="og15_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og15_mfm", green=None,
         condition="og14's setting, seeded with og14's life alone",
         headline="62.5 (15/24), 0 deaths: obsidian at 13251; 9 own scripts called 346 times"),
    dict(group="half-dragon/self-harness", arm="og20_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og20_mfm", green=None,
         condition="og15 + own reflexes (mine/reflexes/*.py run every 4 ticks)",
         headline="54.17 (13/24), 0 deaths: 9 own scripts, 1 own reflex"),
    dict(group="half-dragon/self-harness", arm="og21_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og21_mfm", green=None,
         condition="og20 + no harness reflexes + the skill package (the three-layer self-harness arm)",
         headline="58.33 (14/24), 0 deaths: obsidian at 12845 with the runner's guards OFF; 4 own reflexes"),
    dict(group="half-dragon/self-harness", arm="og22_mfm", mcu=GRID, mfm=MFM_GRID, home=HOMES / "og22_mfm",
         green=GRID / "output/20260908_011038_49889",
         condition="og21's setting on gpt-5.6-sol xhigh (the model control)",
         headline="50.0 (12/24) at 9.4k steps when stopped; own reflexes fired 5 times"),
    dict(group="half-dragon/visual-only", arm="og17_mfm", mcu=MERGE, mfm=MFM_GRID, home=VARTMP / "og17_mfm", green=None,
         condition="visual-only: the frame alone, no state text, coordinate-free atoms, 640x360",
         headline="62.5 (15/24), 0 deaths: obsidian at 18259 from pixels alone; 1017 view_image calls"),
    dict(group="half-dragon/human-play", arm="og18_mfm", mcu=MERGE, mfm=MFM_GRID, home=HOMES / "og18_mfm", green=None,
         condition="human-play: frame + state text, GUI cursor primitives only, no procedures/references/reflexes/governor; the model invents its skills as scripts",
         headline="54.17 (13/24), 0 deaths: 24 own scripts called 356 times -- the largest agent-written toolkit"),
]

DISTILL_SRC = GRID / "output/og23_distill"

# Effort for runs whose codex home is gone and whose launcher did not log it.
EFFORT_FALLBACK = {
    "obf1_mfm": ("medium", "the purple default: run-arm.sh passes no --model/--reasoning-effort and the launch line carried none (WM_EXTRA is not logged); the codex home is gone"),
    "obf2_mfm": ("medium", "the purple default: run-arm.sh passes no --model/--reasoning-effort and the launch line carried none (WM_EXTRA is not logged); the codex home is gone"),
}

TEXT_EXT = {".json", ".jsonl", ".txt", ".md", ".py", ".log", ".toml", ".csv", ".html", ".yaml", ".yml", ".sh"}

# Longest first. Applied to every text file in the staged tree.
SUBS = [
    (str(COLLAB / "MFM-grid-merge-mcu"), "<MCU>"),
    (str(COLLAB / "MFM-grid/MCU"), "<MCU>"),
    (str(COLLAB / "MFM/MCU"), "<MCU>"),
    (str(COLLAB / "MCU-AgentBeats"), "<MCU-AgentBeats>"),
    (str(COLLAB / "codex-homes"), "<CODEX_HOMES>"),
    (str(VARTMP), "<CODEX_HOMES>"),
    (str(COLLAB / "MFM-grid"), "<MFM>"),
    (str(COLLAB / "MFM"), "<MFM>"),
    (str(COLLAB), "<COLLAB>"),
    ("/datapool/data2/home/ruihan", "<HOME>"),
    ("ced3ljhypc@gmail.com", "<EMAIL>"),
    ("ruihan", "user"),
]


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False).stdout.strip()


def git_tip_before(repo: Path, when: str) -> dict:
    """Newest commit of the checked-out branch at or before `when` (local time string)."""
    branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    line = sh(["git", "log", "-1", f"--before={when} +0800", "--format=%H%x09%ci%x09%s", branch], cwd=repo)
    if not line:
        return {"repo": repo.name, "branch": branch, "commit": None}
    sha, date, subject = line.split("\t", 2)
    return {"repo": str(repo.relative_to(COLLAB)), "branch": branch, "commit": sha, "commit_date": date,
            "subject": subject,
            "note": "the branch tip at launch time; the launcher does not record the sha, so this is an upper bound on the code the run loaded"}


def parse_flags(line: str) -> dict:
    m = re.search(r"World-model purple agent: (.*)$", line)
    if not m:
        return {}
    out = {}
    for tok in m.group(1).split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def count_deaths(logs: Path):
    deaths = []
    step = None
    with open(logs, errors="replace") as fh:
        for ln in fh:
            m = re.search(r"\| Step (\d+)", ln)
            if m:
                step = int(m.group(1))
            if "YOU DIED" in ln:
                pos = re.search(r"YOU DIED at \(([^)]*)\)", ln)
                deaths.append({"step_at_or_before": step, "pos": pos.group(1) if pos else None})
    return deaths


def rollout_effort(home: Path | None):
    if not home or not (home / "sessions").exists():
        return None, None
    for f in sorted((home / "sessions").rglob("rollout-*.jsonl")):
        txt = f.read_text(errors="replace")[:200000]
        m = re.search(r'"model":"([^"]+)"', txt)
        e = re.search(r'"reasoning_effort":"([^"]+)"', txt) or re.search(r'"effort":"([^"]+)"', txt)
        if m:
            return m.group(1), (e.group(1) if e else None)
    return None, None


def slim_rollouts(home: Path | None, dst: Path, stats: dict):
    if not home or not (home / "sessions").exists():
        stats["codex_sessions"] = "not available (the codex home was on the root disk and has been removed)"
        return
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted((home / "sessions").rglob("rollout-*.jsonl")):
        n += 1
        out = dst / f.name
        raw = slim = 0
        with open(f, errors="replace") as src, open(out, "w") as w:
            for line in src:
                raw += len(line)
                head = line[:200]
                if '"type":"compacted"' in head:
                    # multi-MB re-statements of the history above: stub them without parsing
                    ts = re.search(r'"timestamp":"([^"]+)"', head)
                    e = {"timestamp": ts.group(1) if ts else None, "type": "compacted",
                         "payload": {"omitted": True, "chars": len(line),
                                     "note": "compaction snapshot (a re-statement of the history above) dropped in the staged copy"}}
                    s_ = json.dumps(e)
                    slim += len(s_) + 1
                    w.write(s_ + "\n")
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                p = e.get("payload")
                if isinstance(p, dict):
                    c = p.get("content")
                    if isinstance(c, list):
                        for it in c:
                            if isinstance(it, dict) and it.get("type") == "input_image":
                                u = it.get("image_url", "")
                                it["image_url"] = f"<image omitted: {len(u)} chars base64; the frame is in trajectory/episode_001/attach or episodes/>"
                s = json.dumps(e)
                slim += len(s) + 1
                w.write(s + "\n")
        stats.setdefault("codex_sessions_files", []).append({"file": f.name, "raw_bytes": raw, "staged_bytes": slim})
    stats["codex_sessions"] = f"{n} rollout(s), compaction snapshots and base64 images removed"


def anonymise_tree(root: Path) -> dict:
    counts = {}
    files = 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
            continue
        try:
            txt = p.read_text(errors="surrogateescape")
        except Exception:
            continue
        new = txt
        for old, rep in SUBS:
            k = new.count(old)
            if k:
                counts[rep] = counts.get(rep, 0) + k
                new = new.replace(old, rep)
        if new != txt:
            files += 1
            p.write_text(new, errors="surrogateescape")
    return {"files_changed": files, "substitutions": counts}


def copy_trajectory(src_ep: Path, dst_ep: Path):
    """rsync the workspace, leaving out memory/previous/life_*/ (copies of other runs) and packing
    memory/episodes/ (1-2k directories of frame + state + outcome) into ONE uncompressed
    episodes.tar -- the HF repo has a file-count budget and PNGs do not compress."""
    dst_ep.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete", "--exclude", "/memory/previous/life_*/", "--exclude", "/memory/episodes/",
           str(src_ep) + "/", str(dst_ep) + "/"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"rsync failed for {src_ep}: {r.stderr}")
    if (dst_ep / "memory/episodes").exists():
        shutil.rmtree(dst_ep / "memory/episodes")
    tar = dst_ep / "memory/episodes.tar"
    if (src_ep / "memory/episodes").exists():
        r = subprocess.run(["tar", "-cf", str(tar), "-C", str(src_ep / "memory"), "episodes"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"tar failed for {src_ep}: {r.stderr}")


def du(path: Path):
    tot = 0
    n = 0
    for p in path.rglob("*"):
        if p.is_file():
            tot += p.stat().st_size
            n += 1
    return tot, n


def mine_listing(mem: Path):
    out = []
    mine = mem / "mine"
    if not mine.exists():
        return out
    for p in sorted(mine.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(mem))
            lines = None
            if p.suffix.lower() in TEXT_EXT:
                try:
                    lines = sum(1 for _ in open(p, errors="replace"))
                except Exception:
                    pass
            out.append({"path": rel, "bytes": p.stat().st_size, "lines": lines})
    return out


def stage_run(r: dict, args) -> dict:
    arm = r["arm"]
    mcu: Path = r["mcu"]
    src_run = mcu / "output" / arm
    src_ep = src_run / "episode_001"
    logs = mcu / "logs"
    dst = OUT / r["group"] / arm
    report = json.load(open(src_ep / "worldmodel_report.json"))
    ms = report["milestones"]
    achieved = ms.get("achieved", {})
    given = ms.get("given", [])
    earned = {k: v for k, v in achieved.items() if k not in given}
    remade = {k: v for k, v in achieved.items() if k in given}
    purple = logs / f"{arm}_purple.log"
    first = open(purple, errors="replace").readline().strip() if purple.exists() else ""
    start = first[:19] if first[:4].isdigit() else None
    flags = parse_flags(first)
    end = datetime.fromtimestamp((src_ep / "memory/logs.txt").stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    launch = logs / f"{arm}_launch.log"
    ltxt = launch.read_text(errors="replace") if launch.exists() else ""
    seeds = [re.sub(r"/episode_001/memory$", "", s).split("/output/")[-1] for s in re.findall(r"--seed-memory (\S+)", ltxt)]
    carried = re.search(r"\[previous\] (\d+) live\(s\) carried[^\n]*", open(purple, errors="replace").read()) if purple.exists() else None
    toml = logs / f"{arm}.toml"
    max_steps = None
    if toml.exists():
        m = re.search(r"max_steps\s*=\s*(\d+)", toml.read_text())
        max_steps = int(m.group(1)) if m else None
    deaths = count_deaths(src_ep / "memory/logs.txt")
    model, effort = rollout_effort(r["home"])
    model = model or flags.get("model")
    if effort:
        effort_source = "codex rollout (session_meta / turn_context)"
    elif (model or "").startswith("gpt-6"):
        effort, effort_source = "high", "README-mfm-arms.md: gpt-6-astra high for og10-og21 (the rollout is gone)"
    else:
        effort, effort_source = EFFORT_FALLBACK.get(arm, (None, "not recorded"))
    codex = report.get("codex", {})
    mfm = report.get("mfm", {})
    own = report.get("own")
    ended_by_green = bool(r["green"]) and (r["green"] / "kill_ender_dragon/milestone_tracking.json").exists()
    stop = "episode completed (the green agent wrote the final milestone_tracking.json)" if ended_by_green and "finished" in ltxt \
        else ("stopped from outside (Terminated in the launch log: the 10 h wall cap or the operator); the green flushed its record on shutdown" if ended_by_green
              else "stopped from outside (Terminated in the launch log: the 10 h wall cap or the operator); no evaluator video")

    if args.dry_run:
        print(f"[dry] {arm}: {ms['milestones_achieved']}/{ms['total_milestones']} steps={report['steps']} deaths={len(deaths)} model={model} {effort} seeds={len(seeds)} start={start}")
        return {}

    print(f"[stage] {arm} -> {dst.relative_to(STAGING)}", flush=True)
    copy_trajectory(src_ep, dst / "trajectory/episode_001")
    # lineage stub in place of the stripped previous/ lives
    prev = dst / "trajectory/episode_001/memory/previous"
    if seeds or prev.exists():
        prev.mkdir(parents=True, exist_ok=True)
        json.dump({
            "note": "memory/previous/life_<i>/ held hard-linked copies of these earlier runs' records (logs.txt, episodes/, index.jsonl, grid.jsonl, mine/), oldest first, deduplicated by content; the copies are left out of the staged trajectory. previous/index.jsonl (kept) is the merged index the model queried with tools/episodes.py --previous.",
            "seed_memory_args_in_order": seeds,
            "lives_carried": int(carried.group(1)) if carried else None,
            "purple_log_line": carried.group(0) if carried else None,
            "where_the_seeds_are": "og*/ob* lives: this dataset (mfm-era/ or earlier eras); hd*/kd*/dm*: MCU-AgentBeats worldmodel/logbook runs (relay-era/, claim-m-*)"
        }, open(prev / "LINEAGE.json", "w"), indent=1)
    # launcher logs
    ldir = dst / "launcher"
    ldir.mkdir(exist_ok=True)
    for suf in ("_launch.log", "_purple.log", "_green.log", "_client.log", "_wall.log", ".toml", "_result.json"):
        f = logs / f"{arm}{suf}"
        if f.exists():
            shutil.copy2(f, ldir / f.name)
    # evaluator
    if r["green"] and r["green"].exists():
        edir = dst / "evaluator"
        edir.mkdir(exist_ok=True)
        for f in r["green"].rglob("*"):
            if f.is_file() and f.suffix in (".mp4", ".json"):
                shutil.copy2(f, edir / f.name)
    # codex sessions
    stats = {}
    if not args.skip_sessions:
        slim_rollouts(r["home"], dst / "codex_sessions", stats)
    anon = anonymise_tree(dst)
    size, nfiles = du(dst)
    mem = dst / "trajectory/episode_001/memory"
    prov = {
        "run": arm,
        "group": r["group"],
        "task": ms.get("task"),
        "task_text": report.get("task"),
        "arm": "mfm (worldmodel chassis --memory mfm: the logbook protocol + the Multimodal Filesystem Memory episode store)",
        "condition": r["condition"],
        "headline": r["headline"],
        "score": round(100.0 * ms["milestones_achieved"] / ms["total_milestones"], 2),
        "milestones": f"{ms['milestones_achieved']}/{ms['total_milestones']}",
        "milestones_all": achieved,
        "milestones_beyond_the_kit": earned,
        "kit_milestones_re_made": remade if given else None,
        "kit_milestones_listed_as_given": given or None,
        "scoring_note": ("the evaluator credits only milestones triggered in this episode; the half task's 'first ten' are NOT pre-credited, "
                         "so a half-task score mixes re-made kit milestones with new progress -- compare arms by milestones_beyond_the_kit"
                         if given else "score = 100 * milestones / 24, environment-verified"),
        "steps_run": report.get("steps"),
        "max_steps": max_steps,
        "deaths": len(deaths),
        "death_list": deaths,
        "model": model,
        "reasoning_effort": effort,
        "effort_source": effort_source,
        "sessions": ("one codex conversation resumed across turns with compaction (--session-turns 0 --compact)"
                     if "compact and carry on" in ltxt else "cold start every turn (1-turn sessions)"),
        "flags": flags,
        "seed_memory_args": seeds,
        "lives_carried": int(carried.group(1)) if carried else 0,
        "codex": {k: codex.get(k) for k in ("calls", "view_image_calls", "episodes_tool_calls", "compactions", "tool_errors")},
        "mfm": {k: mfm.get(k) for k in ("n", "frames_written", "retrieval", "recalls")},
        "own": own,
        "agent_written_files": mine_listing(mem),
        "run_window_local": f"{start} -> {end} +0800",
        "ended": stop,
        "code_identity": {"mcu": git_tip_before(r["mcu"], start) if start else None,
                          "mfm_package": git_tip_before(r["mfm"], start) if start else None},
        "world": WORLD,
        "staged": {"bytes": size, "files": nfiles, "previous_lives_stripped": True,
                   "episodes_packed": "memory/episodes.tar (uncompressed; `tar -xf episodes.tar` inside memory/ restores episodes/ep_*/)",
                   **stats, "anonymisation": anon},
        "source": {"run_dir": str(src_run).replace(str(COLLAB), "<COLLAB>"), "codex_home": str(r["home"]).replace(str(COLLAB), "<COLLAB>") if r["home"] else None},
    }
    txt = json.dumps(prov, indent=1)
    for old_, rep in SUBS:          # the flags line carries the codex home path; anonymise the provenance too
        txt = txt.replace(old_, rep)
    (dst / "provenance.json").write_text(txt)
    return prov


def stage_distill(args):
    dst = OUT / "lineage/og23_distill"
    if args.dry_run:
        print("[dry] og23_distill"); return {}
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("distill_prompt.txt", "distill_report.json", "distill_events.jsonl", "distill_stderr.txt"):
        f = DISTILL_SRC / name
        if f.exists():
            shutil.copy2(f, dst / name)
    for sub in ("mine", "skills", "tools"):
        s = DISTILL_SRC / "memory" / sub
        if s.exists():
            shutil.copytree(s, dst / "memory" / sub, dirs_exist_ok=True)
    rep = json.load(open(DISTILL_SRC / "distill_report.json"))
    lin = {"note": "the distiller read these lives (memory/previous/life_*/, stripped here) and wrote memory/mine/",
           "report": rep}
    json.dump(lin, open(dst / "LINEAGE.json", "w"), indent=1)
    anon = anonymise_tree(dst)
    return {"run": "og23_distill", "group": "lineage", "staged": {"anonymisation": anon, **dict(zip(("bytes", "files"), du(dst)))}, "report": rep}


def write_runs_csv(provs):
    with open(OUT / "runs.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "task", "arm", "condition", "group", "max_steps", "steps_run", "score", "milestones", "deaths",
                    "model", "effort", "codex_calls", "view_image_calls", "episodes_tool_calls", "own_procedures", "own_calls",
                    "lives_carried", "milestones_beyond_kit_timeline", "run_window_local"])
        for p in provs:
            own = p.get("own") or {}
            w.writerow([p["run"], p["task"], "mfm", p["condition"], p["group"], p["max_steps"], p["steps_run"], p["score"],
                        p["milestones"], p["deaths"], p["model"], p["reasoning_effort"], p["codex"]["calls"],
                        p["codex"]["view_image_calls"], p["codex"]["episodes_tool_calls"], own.get("procedures"),
                        sum((own.get("calls") or {}).values()) if own else None, p["lives_carried"],
                        " ".join(f"{k}@{v}" for k, v in p["milestones_beyond_the_kit"].items()), p["run_window_local"]])


def append_stats(provs):
    """Append the era's rows to stats/runs.csv (the dataset scoreboard) in its column set."""
    f = STAGING / "stats/runs.csv"
    if not f.exists():
        return
    existing = {row.split(",")[0] for row in f.read_text().splitlines()[1:]}
    with open(f, "a", newline="") as fh:
        w = csv.writer(fh)
        for p in provs:
            if p["run"] in existing:
                continue
            task = "kill_ender_dragon" if p["task"] == "ender_dragon" else "ender_dragon_half"
            w.writerow([p["run"], task, "mfm", p["condition"], "mfm_era", p["max_steps"], p["score"], p["milestones"],
                        p["codex"]["calls"], " ".join(f"{k}@{v}" for k, v in p["milestones_all"].items())])


def scoreboard_rows():
    """Every scored og*/ob* mfm run of the two chains, staged or not, for stats/runs.csv."""
    f = STAGING / "stats/runs.csv"
    if not f.exists():
        return
    existing = {row.split(",")[0] for row in f.read_text().splitlines()[1:]}
    reports = sorted(GRID.glob("output/og*_mfm/episode_001/worldmodel_report.json")) + \
        sorted(MERGE.glob("output/og*_mfm/episode_001/worldmodel_report.json")) + \
        sorted(DRAGON.glob("output/ob*_mfm/episode_001/worldmodel_report.json"))
    staged = {r["arm"] for r in RUNS}
    with open(f, "a", newline="") as fh:
        w = csv.writer(fh)
        for rp in reports:
            arm = rp.parents[1].name
            if arm in existing or arm in staged or ".medium-abort" in arm or arm in ("og1_mfm", "og2_mfm"):  # og1/og2: aborted smoke arms
                continue
            d = json.load(open(rp))
            ms = d["milestones"]
            task = "kill_ender_dragon" if ms.get("task") == "ender_dragon" else "ender_dragon_half"
            mcu = rp.parents[3]
            # Reports of the first-generation half-task arms (og3/og4, ob1-ob5) pre-credited the kit at step 0;
            # only the evaluator's result.json holds their real count. Later reports (kit milestones "stay open",
            # every given milestone carries a real step) agree with the evaluator (checked on og12/og22).
            precredited = any(ms.get("achieved", {}).get(k) == 0 for k in ms.get("given", []))
            res = mcu / "logs" / f"{arm}_result.json"
            count, score = ms["milestones_achieved"], round(100.0 * ms["milestones_achieved"] / ms["total_milestones"], 2)
            if res.exists():
                try:
                    j = json.load(open(res))["results"][0]
                    score = j["total_score"]
                    count = int(round(j["task_metrics"]["kill_ender_dragon"]["sim_score"]))
                except Exception:
                    pass
            elif precredited:
                continue  # no trustworthy score for this arm
            launch = mcu / "logs" / f"{arm}_launch.log"
            seeds = len(re.findall(r"--seed-memory ", launch.read_text(errors="replace"))) if launch.exists() else 0
            purple = mcu / "logs" / f"{arm}_purple.log"
            flags = parse_flags(open(purple, errors="replace").readline()) if purple.exists() else {}
            cond = ("carry" if seeds else "from_scratch") + (" + pushed sites" if flags.get("sites") == "True" or arm.startswith("ob") else "") \
                + (" thin" if flags.get("thin") == "True" else "") + (" (not staged)")
            w.writerow([arm, task, "mfm", cond, "mfm_era", None, score, f"{count}/{ms['total_milestones']}",
                        d.get("codex", {}).get("calls"),
                        " ".join(f"{k}@{v}" for k, v in ms.get("achieved", {}).items() if v)])


def agent_code_index(provs, distill):
    lines = ["# Agent-written code and notes, across the mfm-era runs", "",
             "Everything under `memory/mine/` was written by the model during the run (`--own`, `--own-reflexes`, `--human-play`):",
             "`mine/procedures/<name>.py` are procedures the harness runs as subprocesses (state on stdin, a plan on stdout),",
             "`mine/reflexes/<name>.py` run every 4 ticks while a plan executes, `mine/notes.md` / `digest.md` / `working.md` are its notes,",
             "and the PNGs are crops it saved for itself. `skills/*/SKILL.md`, `references/*.md`, `tools/*.py` and `AGENTS.md` are",
             "harness-written (the contract), listed in the trajectory but not here. Call counts are the harness's (`own.calls` in",
             "`worldmodel_report.json`). The four starter reflexes of `--skills` (`lava_ahead`, `fell`, `hit`, `starving`) are harness",
             "examples installed under `mine/reflexes/` for the model to edit; they are marked.", ""]
    starters = {"lava_ahead.py", "fell.py", "hit.py", "starving.py"}
    for p in provs:
        files = p.get("agent_written_files") or []
        if not files:
            continue
        own = p.get("own") or {}
        calls = own.get("calls") or {}
        lines.append(f"## {p['run']} -- {p['condition']}")
        lines.append("")
        lines.append(f"`{p['group']}/{p['run']}/trajectory/episode_001/memory/mine/` -- {len(files)} files; own procedures called {sum(calls.values())} times"
                     + (f"; reflex fires {own.get('reflex_fires')}" if own.get("reflex_fires") else ""))
        lines.append("")
        lines.append("| file | lines | calls |")
        lines.append("| --- | --- | --- |")
        for f in files:
            name = Path(f["path"]).stem
            tag = ""
            if Path(f["path"]).name in starters and "reflexes/" in f["path"]:
                tag = " (starter reflex, harness example)"
            c = calls.get(name)
            lines.append(f"| `{f['path']}`{tag} | {f['lines'] if f['lines'] is not None else '-'} | {c if c is not None else ''} |")
        lines.append("")
    if distill:
        rep = distill.get("report", {})
        lines.append("## og23_distill -- the distilled memory (a separate distiller pass, not a play run)")
        lines.append("")
        lines.append(f"`lineage/og23_distill/memory/mine/`: `GUIDE.md`, `frames.md`, 17 procedures, `reflexes/known_hazards.py`, written by "
                     f"gpt-5.6-sol (xhigh) reading {rep.get('lives', '?')} earlier lives for {rep.get('seconds', rep.get('elapsed_s', '?'))} s "
                     "(`distill_prompt.txt` is the instruction, `distill_events.jsonl` the codex record). Seeded into og23/og24 via `--seed-mine`; "
                     "those two arms ran only ~45 min before every arm was stopped for API cost and are not staged.")
        lines.append("")
    (OUT / "agent-code").mkdir(exist_ok=True)
    (OUT / "agent-code/INDEX.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skip-sessions", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-distill", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    provs = []
    for r in RUNS:
        if args.only and r["arm"] not in args.only:
            continue
        p = stage_run(r, args)
        if p:
            provs.append(p)
    distill = {} if args.no_distill else stage_distill(args)
    if args.dry_run:
        return
    # merge with provenance already staged in earlier invocations (--only)
    allp = []
    for r in RUNS:
        f = OUT / r["group"] / r["arm"] / "provenance.json"
        if f.exists():
            allp.append(json.load(open(f)))
    write_runs_csv(allp)
    append_stats(allp)
    scoreboard_rows()
    agent_code_index(allp, distill or (json.load(open(OUT / "lineage/og23_distill/LINEAGE.json")) if (OUT / "lineage/og23_distill/LINEAGE.json").exists() else {}))
    tot, n = du(OUT)
    json.dump({
        "dataset_dir": "mfm-era",
        "staged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S +0800"),
        "runs": [{"run": p["run"], "group": p["group"], "score": p["score"], "milestones": p["milestones"], "steps": p["steps_run"],
                  "bytes": p["staged"]["bytes"], "files": p["staged"]["files"]} for p in allp],
        "bytes_total": tot, "files_total": n,
        "anonymisation": {"scope": "every text file (json/jsonl/txt/md/py/log/toml/csv) under mfm-era/",
                          "substitutions": ["MCU worktree checkout paths -> <MCU>", "MCU-AgentBeats checkout -> <MCU-AgentBeats>",
                                            "codex home roots -> <CODEX_HOMES>", "MFM package checkouts -> <MFM>", "the shared parent dir -> <COLLAB>",
                                            "user home -> <HOME>", "user e-mail -> <EMAIL>", "OS user name -> user"]},
        "left_out": ["memory/previous/life_*/ (hard-linked copies of other runs; LINEAGE.json names them)",
                     "codex rollouts' compaction snapshots and base64 frames (codex_sessions/*.jsonl are slimmed copies)",
                     "og1-og7, og10, og11, og13, og23, og24 and ob1-ob6, obf3 (earlier / shorter / superseded arms; the scoreboard rows are in the README)"],
    }, open(OUT / "manifest.json", "w"), indent=1)
    print(f"staged {len(allp)} runs, {tot/1e9:.2f} GB, {n} files -> {OUT}")


if __name__ == "__main__":
    main()
