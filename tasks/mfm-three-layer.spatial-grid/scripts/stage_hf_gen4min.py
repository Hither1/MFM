#!/usr/bin/env python3
"""Stage of3m_mfm -- gen 4 min, the third life of the carry-only chain -- for Ced-Collab/MCUData.

    carry-only-era/gen4min/of3m_mfm/         the run (as gen2/ and gen3b/ are staged) + vision_use.json
    carry-only-era/look-cases/gen4min_of3m_mfm/   every milestone-tied look turn + the named episodes
    carry-only-era/diff-gen2-to-gen4min/     mcu.patch, mfm.patch, contract.diff, the rendered contract diff
    look_examples_of3m/                      curated cases: where a remembered frame decided the action
    carry-only-era/README.md, manifest.json, runs.csv; stats/runs.csv; the top-level README box

Reuses stage_hf_mfm_era (anonymisation, rollout slimming, trajectory layout) and
stage_hf_carry_only_era (hires packing, wall timeline, harness-code archive) and look_cases
(the per-turn bundles). New here: `vision_use.json` -- the model's view_image calls read from
the codex rollout (codex --json never emits them, so codex_turns/ has none), each assigned to
its turn by timestamp and classified by what was looked at (a previous life's frame, this
life's episode, a crop, a sheet the model wrote).

Written 2026-09-11. Usage: python3 stage_hf_gen4min.py [--skip-sessions] [--dry-run] [--no-trajectory]
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_hf_mfm_era as M  # noqa: E402
import stage_hf_carry_only_era as C  # noqa: E402  (sets M.OUT = STAGING / carry-only-era, snapshot-tolerant copy)
import look_cases as L  # noqa: E402

OUT = M.OUT                       # .../hf_staging/carry-only-era
EXAMPLES = M.STAGING / "look_examples_of3m"
MCU_MIN = M.COLLAB / "MFM-grid-min-mcu"   # MCU worktree, branch gen4-min
MFM_MIN = M.COLLAB / "MFM-grid-min"       # mfm package worktree, branch gen4-min
MFM_GRID = M.MFM_GRID                     # launch_g4.sh / status_g4.sh live on spatial-grid
# longest first, ahead of the module's "<COLLAB>/MFM-grid" entry
M.SUBS.insert(0, (str(MCU_MIN), "<MCU>"))
M.SUBS.insert(1, (str(MFM_MIN), "<MFM>"))
M.TEXT_EXT |= {".patch", ".diff"}          # the diff dirs are text too (the module's set lacked them)

RUN = dict(
    group="gen4min", arm="of3m_mfm", mcu=MCU_MIN, mfm=MFM_MIN, home=M.HOMES / "of3m_mfm", green=None,
    condition="carry-only (seed: of3r_mfm's record, which carries of3_mfm -- two lives under previous/; no harness-pushed "
              "facts), gen-4 min = the gen-2 code + three model-facing edits (the starving example eats carried food below "
              "18, the hunger line in Safety, then-now once on arrival at a remembered place + the episode id beside each "
              "digest place), one codex thread compacted (--session-turns 0 --compact), frames 320x180, per-step 640x360 "
              "hires record, OpenRouter",
    headline="16/24 at 49.4k steps / 14 h, 0 deaths -- ties the carry-only record (of3r), the 16th milestone at +7 h 50 after the "
             "first codex turn instead of +11 h 17: iron pickaxe at step 5293 (+56 min vs +67), flint_and_steel 9995 (+2 h 10 vs "
             "+6 h 41), diamond 18110 (+4 h 07 vs +4 h 02), obsidian 30994 (+6 h 43 vs +7 h 40), netherrack 35204; then 14k steps "
             "in the Nether bridging over lava without finding a fortress",
    generation="gen 4 min",
    reflog="gen4-min branched from b2f8c832 at 2026-09-10 04:59:56, last commit 1c697dd8 at 05:35:42 (git reflog show gen4-min "
           "in MFM-grid-min-mcu); the mfm package worktree MFM-grid-min at a87aa8d (05:35:43; its next commit 8651823 landed "
           "10:18, after the launch, renaming the image tool for the Claude channel only); launch_g4.sh checks "
           "merge-base --is-ancestor bfd31b31 and a clean mcu_worldmodel/ + scripts/; the run launched 2026-09-10 06:00:43",
)

MCU_PATHS = ["mcu_worldmodel", "scripts/run-arm.sh", "scripts/launch-og.sh", "scripts/codex-openrouter.sh",
             "scripts/codex-home.sh", "scripts/stop_arm.py", "scripts/watchdog.sh"]
MFM_PATHS = ["mfm"]
LAUNCHER_PATHS = ["tasks/mfm-three-layer.spatial-grid/scripts/launch_g4.sh",
                  "tasks/mfm-three-layer.spatial-grid/scripts/status_g4.sh",
                  "tasks/mfm-three-layer.spatial-grid/analysis/gen4_plan_2026-09-10.md",
                  "tasks/mfm-three-layer.spatial-grid/analysis/gen4_contract_diff_min.txt"]

# Look turns dumped beside the milestone-tied ones (score 3 in look_cases): the named episodes of the run.
SPECIAL_TURNS = [62, 67, 69, 70, 71, 72, 241, 247, 271, 272, 280, 281, 285, 286, 287, 289, 290, 310, 434, 435, 436]


# ------------------------------------------------------------------------------------------------
# vision use: view_image from the rollout, then-now / zoom from the codex_turns events
# ------------------------------------------------------------------------------------------------
def turn_starts_utc(purple: Path) -> tuple[list[datetime], list[int]]:
    ts, ns = [], []
    for m in re.finditer(r"^(\S+ \S+) \| INFO .*\[codex\] turn (\d+) model", purple.read_text(errors="replace"), re.M):
        ts.append(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f") - timedelta(hours=8))
        ns.append(int(m.group(2)))
    return ts, ns


def classify(path: str) -> str:
    if "/previous/life_1/" in path:
        return "previous_life_1_frame"
    if "/previous/life_2/" in path:
        return "previous_life_2_frame"
    if "/memory/episodes/ep_" in path or re.search(r"(^|/)episodes/ep_\d+/", path):
        return "own_episode_frame"
    if "then_now" in path:
        return "then_now_sheet"
    if "/memory/mine/" in path or path.startswith("mine/"):
        return "own_sheet_or_crop_in_mine"
    if path.startswith("/tmp/") or "/tmp/" in path:
        return "tmp_crop"
    if "attach/frame.png" in path:
        return "current_frame"
    if "/hires/" in path:
        return "hires_frame"
    return "other"


def vision_use(r: dict, ep: Path) -> dict:
    purple = r["mcu"] / "logs" / f"{r['arm']}_purple.log"
    starts, nums = turn_starts_utc(purple)
    steps = {n: L.turn_step(ep, n) for n in nums}
    views = []
    rollouts = sorted((r["home"] / "sessions").rglob("rollout-*.jsonl"))
    for f in rollouts:
        with open(f, errors="replace") as fh:
            for line in fh:
                if '"type":"response_item"' not in line[:200] or '"name":"view_image"' not in line[:900]:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                p = e.get("payload", {})
                if p.get("type") != "function_call" or p.get("name") != "view_image":
                    continue
                try:
                    path = json.loads(p.get("arguments", "{}")).get("path", "")
                except Exception:
                    path = p.get("arguments", "")
                t = datetime.strptime(e["timestamp"][:23], "%Y-%m-%dT%H:%M:%S.%f")
                k = bisect.bisect_right(starts, t) - 1
                turn = nums[k] if k >= 0 else None
                views.append({"turn": turn, "step": steps.get(turn), "path": path, "kind": classify(path),
                              "utc": e["timestamp"]})
    by_kind: dict[str, int] = {}
    for v in views:
        by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
    per_turn: dict[int, dict] = {}
    for v in views:
        d = per_turn.setdefault(v["turn"], {"turn": v["turn"], "step": v["step"], "calls": 0, "kinds": {}, "paths": []})
        d["calls"] += 1
        d["kinds"][v["kind"]] = d["kinds"].get(v["kind"], 0) + 1
        d["paths"].append(v["path"])
    distinct = {v["path"] for v in views}
    prev_distinct = {v["path"] for v in views if v["kind"].startswith("previous_")}
    # then-now and zoom from the per-turn events (command cells)
    then_now, zooms = [], []
    for n in L.look_turns(ep):
        for it in L.turn_items(ep, n):
            if not L.is_look(it):
                continue
            c = L.shell_part(it.get("command", ""))
            for m in re.finditer(r"--then-now\s+(\S+)", c):
                tgt = m.group(1).strip("'\"\\")
                then_now.append({"turn": n, "step": L.turn_step(ep, n), "target": tgt,
                                 "source": "previous_life" if tgt.startswith("previous/") else "this_life"})
            if "zoom.py" in c and not c.strip().startswith("sed") and "zoom.py " in c:
                zooms.append({"turn": n, "step": L.turn_step(ep, n)})
    tn_targets = {t["target"] for t in then_now}
    tn_prev = {t["target"] for t in then_now if t["source"] == "previous_life"}
    out = {
        "note": ("view_image is a codex tool call; `codex exec --json` does not emit it, so codex_turns/*.events.jsonl carry none. "
                 "These calls are read from the codex rollout (function_call items named view_image) and assigned to turns by "
                 "timestamp against the purple log's turn starts. worldmodel_report.json's codex.view_image_calls (3902) counts "
                 "text mentions, not calls. then-now and zoom cells come from the per-turn events."),
        "rollouts_scanned": [f.name for f in rollouts],
        "view_image": {"calls": len(views), "by_kind": by_kind, "distinct_frames": len(distinct),
                       "distinct_previous_life_frames": len(prev_distinct),
                       "turns_with_a_view": len(per_turn),
                       "per_turn": [per_turn[k] for k in sorted(per_turn, key=lambda x: (x is None, x))],
                       "calls_list": views},
        "then_now": {"calls": len(then_now), "distinct_targets": len(tn_targets), "distinct_previous_life_targets": len(tn_prev),
                     "previous_life_calls": sum(1 for t in then_now if t["source"] == "previous_life"),
                     "this_life_calls": sum(1 for t in then_now if t["source"] == "this_life"),
                     "calls_list": then_now},
        "zoom": {"turns_with_a_zoom": len({z["turn"] for z in zooms})},
    }
    return out


# ------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------
def stage_run(r: dict, args) -> dict | None:
    prov = M.stage_run(r, args)         # trajectory (previous/ stripped, episodes.tar), launcher, slimmed sessions, provenance
    if not prov:
        return None
    arm = r["arm"]
    mcu = r["mcu"]
    dst = OUT / r["group"] / arm
    ep = dst / "trajectory/episode_001"
    src_ep = mcu / "output" / arm / "episode_001"
    hires = ep / "hires"
    if hires.is_dir():
        n = sum(1 for _ in hires.iterdir())
        subprocess.run(["tar", "-cf", str(ep / "hires.tar"), "-C", str(ep), "hires"], check=True)
        shutil.rmtree(hires)
        prov["staged"]["hires_packed"] = (f"trajectory/episode_001/hires.tar ({n} files, 640x360 JPEG per step; "
                                          "`tar -xf hires.tar` inside episode_001/ restores hires/<step>.jpg)")
    t0, tl = C.wall_timeline(mcu / "logs" / f"{arm}_purple.log")
    prov["first_codex_turn_local"] = t0
    prov["milestone_timeline_wall"] = tl
    purple = (mcu / "logs" / f"{arm}_purple.log").read_text(errors="replace")
    steps = re.findall(r"\[adapter\] step (\d+)", purple)
    prov["snapshot"] = {"run_in_progress_at_staging": False, "staged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S +0800"),
                        "last_step_in_purple_log": int(steps[-1]) if steps else None,
                        "codex_turns": len(re.findall(r"\[codex\] turn \d+ model", purple))}
    prov["ended"] = ("stopped by the 14 h wall watchdog at 2026-09-10 20:00 (logs/of3m_mfm_wall.log: 13 pids, 3 SIGKILL) "
                     "mid-turn 476; no evaluator video (the green was killed before it flushed)")
    prov["generation"] = r["generation"]
    prov["code_identity"]["verified_by"] = r["reflog"]
    prov["code_identity"]["launcher_repo"] = M.git_tip_before(MFM_GRID, prov["run_window_local"][:19])
    prov["deaths_note"] = ("count = YOU DIED notes in logs.txt. The single note (step 35121) is a harness false positive: the "
                           "portal was entered with raw `forward` + `watch` rather than enter_portal, so no dimension check "
                           "headed the queue and the 5631-block coordinate jump at full health was logged as a death at the "
                           "portal (agent.py:702). Health, inventory and the next frame show no death; the model dismissed the "
                           "note in its next turn (look-cases turn 289). Real deaths: 0.")
    prov["real_deaths"] = 0
    prov["you_died_notes_in_log"] = prov["deaths"]
    prov["deaths"] = 0                    # the CSV / README column: real deaths
    # vision use
    vu = vision_use(r, src_ep)
    txt = json.dumps(vu, indent=1)
    for old_, rep in M.SUBS:
        txt = txt.replace(old_, rep)
    (dst / "vision_use.json").write_text(txt)
    prov["vision_use"] = {"file": "vision_use.json",
                          "view_image_calls": vu["view_image"]["calls"], "view_image_by_kind": vu["view_image"]["by_kind"],
                          "distinct_frames_viewed": vu["view_image"]["distinct_frames"],
                          "distinct_previous_life_frames_viewed": vu["view_image"]["distinct_previous_life_frames"],
                          "then_now_calls": vu["then_now"]["calls"], "then_now_previous_life_calls": vu["then_now"]["previous_life_calls"],
                          "then_now_distinct_targets": vu["then_now"]["distinct_targets"],
                          "then_now_distinct_previous_life_targets": vu["then_now"]["distinct_previous_life_targets"]}
    # harness code at the run's commits
    hc = dst / "harness-code"
    mcu_sha = prov["code_identity"]["mcu"]["commit"]
    mfm_sha = prov["code_identity"]["mfm_package"]["commit"]
    got_mcu = C.git_archive(r["mcu"], mcu_sha, MCU_PATHS, hc / "mcu")
    got_mfm = C.git_archive(r["mfm"], mfm_sha, MFM_PATHS, hc / "mfm")
    l_sha = prov["code_identity"]["launcher_repo"]["commit"]
    got_l = C.git_archive(MFM_GRID, l_sha, LAUNCHER_PATHS, hc / "launcher")
    (hc / "INDEX.md").write_text(
        f"# harness code of {arm}\n\n"
        f"- `mcu/` -- MCU-AgentBeats, branch gen4-min, at `{mcu_sha}`: {', '.join(got_mcu)}\n"
        f"- `mfm/` -- the mfm package repo, branch gen4-min, at `{mfm_sha}`: {', '.join(got_mfm)}\n"
        f"- `launcher/` -- the mfm package repo, branch spatial-grid, at `{l_sha}`: {', '.join(got_l)} "
        "(launch_g4.sh is the launch line -- `bash launch_g4.sh min`; gen4_plan_2026-09-10.md section 11 defines the minimal "
        "gen 4; gen4_contract_diff_min.txt is the rendered contract against gen 2's, byte-checked before the launch)\n\n"
        "`mcu_worldmodel/prompts.py` holds the contract template (`minimal_contract`), `agent.py` the turn loop and the memory\n"
        "blocks, `skills.py` the skills catalog and the starter reflexes (the gen-4 `starving.py` example), `codex_backend.py`\n"
        "the codex exec wrapper; `mfm/memory/` is the episode store and retrieval ([RECALL]). The contract as this run\n"
        "received it is `trajectory/episode_001/memory/AGENTS.md`.\n")
    M.anonymise_tree(hc)
    prov["staged"]["harness_code"] = {"mcu": got_mcu, "mfm": got_mfm, "launcher": got_l}
    (dst / "profile.txt").write_text(profile(mcu, arm))
    size, nfiles = M.du(dst)
    prov["staged"]["bytes"], prov["staged"]["files"] = size, nfiles
    txt = json.dumps(prov, indent=1)
    for old_, rep in M.SUBS:
        txt = txt.replace(old_, rep)
    (dst / "provenance.json").write_text(txt)
    return json.loads(txt)


def profile(mcu: Path, arm: str) -> str:
    r = subprocess.run([sys.executable, str(HERE / "turn_profile.py"), str(mcu), arm], capture_output=True, text=True)
    return r.stdout + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else "")


# ------------------------------------------------------------------------------------------------
# look cases
# ------------------------------------------------------------------------------------------------
def scored_turns(mcu: Path, arm: str) -> list[dict]:
    ep = mcu / "output" / arm / "episode_001"
    ms = L.milestones(mcu, arm)
    rows = []
    for n in L.look_turns(ep):
        items = L.turn_items(ep, n)
        step = L.turn_step(ep, n)
        nxt_step = L.turn_step(ep, n + 1)
        cmd, after = L.look_summary(items)
        banked = [name for name, s in ms if step is not None and nxt_step is not None
                  and step <= s <= (L.turn_step(ep, n + 6) or s)]
        score = (1 if after else 0) + (1 if banked else 0) + (1 if "then-now" in cmd or "zoom" in cmd else 0)
        rows.append({"turn": n, "step": step, "look": cmd, "after": after, "next": L.observed_of(L.turn_items(ep, n + 1)),
                     "banked": banked, "score": score})
    return rows


def dump_look_cases(r: dict, rows: list[dict], args) -> tuple[Path, list[int]]:
    mcu, arm = r["mcu"], r["arm"]
    turns = sorted({x["turn"] for x in rows if x["score"] >= 3} | set(SPECIAL_TURNS))
    out = OUT / "look-cases" / f"{r['group']}_{arm}"
    if args.dry_run:
        print(f"[dry] look-cases: {len(turns)} turns -> {out}")
        return out, turns
    if out.exists():
        shutil.rmtree(out)
    L.cmd_dump(mcu, arm, turns, out)
    M.anonymise_tree(out)
    return out, turns


def look_cases_readme_section(r: dict, rows: list[dict], turns: list[int], vu: dict) -> str:
    by = {x["turn"]: x for x in rows}

    def tgt(look: str) -> str:
        m = re.search(r"--then-now\s+(\S+)", look)
        if m:
            t = m.group(1).strip("'\"\\")
            t = re.sub(r"/observation/image\.png$", "", t)
            return t.replace("previous/life_2/episodes/", "life_2 ").replace("previous/life_1/episodes/", "life_1 ").replace("episodes/", "own ")
        if "zoom" in look:
            return "zoom crop"
        return look[:40]

    def row(n: int) -> str:
        x = by.get(n)
        if not x:
            return ""
        s = (x["after"] or "").replace("|", "/").replace("[PLAN] ", "")
        return f"| {n} | {x['step']} | {tgt(x['look'])} | {s[:150]} | {', '.join(x['banked']) or '--'} |"

    prev = [n for n in turns if by.get(n) and "then-now previous/" in by[n]["look"]]
    own = [n for n in turns if by.get(n) and "then-now" in by[n]["look"] and n not in prev]
    other = [n for n in turns if n not in prev and n not in own]
    vi = vu["view_image"]
    tn = vu["then_now"]
    lines = [
        f"## gen 4 min (`of3m_mfm`): {len(rows)} look turns in 475; {len(turns)} dumped",
        "",
        f"This life looked far more than gen 2 did: {vi['calls']} `view_image` calls ({vi['by_kind'].get('previous_life_2_frame', 0)} of "
        f"life_2's frames, {vi['by_kind'].get('previous_life_1_frame', 0)} of life_1's, {vi['by_kind'].get('own_episode_frame', 0)} of its own "
        f"episodes, the rest crops and sheets), {tn['calls']} then-now sheets ({tn['previous_life_calls']} against a previous life's "
        f"frame, {tn['distinct_previous_life_targets']} distinct targets). The counts are in `../gen4min/of3m_mfm/vision_use.json` "
        "(view_image is read from the codex rollout; the per-turn events never carry it). Dumped: every look turn with a milestone "
        "banked within five turns (look_cases.py score 3) plus the run's named episodes (the first descent, the lava-frontier "
        "compare sheets, the portal repair and transit, the Nether arrival, the piglin hit).",
        "",
        "**Across lives** -- a then-now against a frame of life_2 (of3r) or life_1 (of3), the multimodal carry:",
        "",
        "| turn | step | recorded frame | the model's sentence after looking | banked within 5 turns |",
        "|---|---|---|---|---|",
    ] + [row(n) for n in prev] + [
        "",
        "**This life's own record** -- a then-now against one of this life's episodes:",
        "",
        "| turn | step | frame | sentence | banked within 5 turns |",
        "|---|---|---|---|---|",
    ] + [row(n) for n in own] + [
        "",
        "**Crops and other looks:**",
        "",
        "| turn | step | look | sentence | banked within 5 turns |",
        "|---|---|---|---|---|",
    ] + [row(n) for n in other] + [
        "",
        "Reading guide: turns 19-27 are the iron chain (life_2's approach frames ep_000219..316 compared one by one until "
        "\"the position matches; I'll open the cell beside iron\" and the ore was mined at the predicted spot, step 4231); "
        "turns 71-72 open the deep staircase where life_2's ep_000530 shows its entrance (\"no old tunnel remains\": the "
        "excavation did not persist, the place did); turns 138-147 walk the tunnel to life_2's diamond vein by its frames "
        "(ep_000849..877, 953) and bank diamond at 18110; turns 241 and 247 are the two compare sheets the model wrote at the "
        "lava frontier (`mine/lava_approach_compare.png`, `mine/lava_arrival_compare.png`, against life_2 ep_001691/1696) "
        "before pouring the bucket; turn 289 is the portal transit the harness logged as a death and the model dismissed from "
        "the frame and its vitals; turn 290 is the Nether arrival compared with life_2's arrival frame ep_002519, six blocks "
        "from where life_2 died; turns 434-436 are the retreat after the piglin hit, footing confirmed on its own bridge frames "
        "with the shield up (the starving reflex ate the last porkchop in the middle of it).",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------
# curated examples: look_examples_of3m/
# ------------------------------------------------------------------------------------------------
EXAMPLE_SPECS = [
    dict(name="01_workshop_reads_two_lives_frames", turn=1,
         title="The workshop turn: three frames of life_2 viewed before the first step",
         summary=("Turn 1 is the workshop turn: nothing about the two earlier lives is put in front of the model; it reads "
                  "`previous/` itself. Among its first acts it `view_image`d three frames of life_2 (of3r): ep_000007 (the "
                  "spawn spruce trunk from ground level), ep_002597 (the piglin that killed life_2 in the Nether) and "
                  "ep_000952 (the exposed diamond wall at (-3096, 11, -5546)). The digest it then wrote cites each: the trunk "
                  "approach, `DIAMONDS ... ep_000952 viewed: exposed diamond wall, more ore right/above`, and `Life_2 DIED41983 "
                  "in Nether ... ep_002597 viewed. Ordinary sword-wielding Piglin ... low health/no gold armor`."),
         outcome=("The digest's diamond line took this life to life_2's vein (diamond at step 18110 against 17931 in life_2, "
                  "with the flint-and-steel already banked -- life_2 found it 10,000 steps after the diamonds); the piglin line "
                  "is why it entered the Nether at 20/20 with a shield and sneaked."),
         prev_frames=["previous/life_2/episodes/ep_000007/observation/image.png",
                      "previous/life_2/episodes/ep_002597/observation/image.png",
                      "previous/life_2/episodes/ep_000952/observation/image.png"],
         extra_text_files=["mine/digest.md"], viewed_from_rollout=True),
    dict(name="02_spawn_trunk_then_now", turn=2,
         title="Step 153: then-now against life_2's first-log frame, then the same angles",
         summary=("On the first play turn the model ran `--then-now previous/life_2/episodes/ep_000007` and planned to \"mine "
                  "the stump and two overhead logs using the previously successful angles\"."),
         outcome="mine_log at step 153, crafting_table 587, wooden_pickaxe 677 (life_2: 153 / 559 / 699)."),
    dict(name="03_iron_approach_frame_by_frame", turn=22,
         title="Steps 3656-4231: life_2's iron approach compared frame by frame until the ore is under the pickaxe",
         summary=("Turns 19-23 each ran a then-now against the next frame of life_2's walk to its shallow iron "
                  "(ep_000219, 226, 233, 255, 267). Turn 21: \"I'll compare it with the recorded iron approach\"; turn 22 "
                  "(step 4097): \"The position matches; I'll open the cell beside iron.\""),
         outcome=("mine_iron_ore verified at step 4231 at the predicted position, the furnace opened where recorded; "
                  "iron_pickaxe at 5293 (+56 min after the first codex turn; life_2 needed +67). Turn 26 later read the furnace frame: \"the ingots "
                  "occupy slot 34, not requested slot 15\" and fixed the pickup."),
         also_turns=[21, 26]),
    dict(name="04_stair_entrance_place_persists_excavation_does_not", turn=71,
         title="Step 10422: life_2's staircase entrance found from its frame; the tunnel itself is gone",
         summary=("The digest says the deep staircase of life_2 started at (-3012.8, 68, -5553.7), ep_000530, and that none of "
                  "the excavation exists in a new life. Turn 70 looked down at the recorded digging approach: \"intact grass "
                  "between spruce trunks; no old tunnel remains\". Turns 71 and 72 ran then-now against ep_000530 and cut the "
                  "first steps at the same place."),
         outcome="The staircase reached Y65 in turn 72; the descent led to life_2's diamond vein (turns 138-147).",
         also_turns=[70, 72]),
    dict(name="05_diamond_vein_by_life2_frames", turn=143,
         title="Steps 17375-18110: the tunnel walked to life_2's diamond wall by its frames",
         summary=("Turns 138-143 compared the tunnel face against life_2's ep_000849, 856, 868, 869, 876, 877 -- \"I also rechecked "
                  "the diamond frame: the ore is in the north-side wall near x-3096, so we should inspect there rather than "
                  "continue past it\" (turn 140). Turn 143 mined \"one block at the remembered north-wall diamond vein\"."),
         outcome="mine_diamond_ore at 18100, diamond 18110, diamond_pickaxe 18295, diamond_sword 18490 (life_2: 17921 / 17931 / 18155 / 18403).",
         also_turns=[140, 144]),
    dict(name="06_lava_frontier_compare_sheets", turn=247,
         title="Steps 30070-30359: two compare sheets the model wrote at the lava frontier before pouring",
         summary=("Approaching life_1's lava lake (the digest: `LAVA HAZARD: life_1 lake frontier (-3217,11,-5576.3) ... "
                  "dangerous floor Y10`), the model ran then-now against life_2's ep_001691 and ep_001696 with `--out` into its "
                  "own files `mine/lava_approach_compare.png` and `mine/lava_arrival_compare.png`: \"The heights match, but the "
                  "exposed tunnel geometry differs\" (turn 241). Turn 247 poured the bucket over the right-hand lava."),
         outcome="mine_obsidian at step 30994 (+6 h 43; life_2 +7 h 40), no lava damage; the portal frame was then built and lit.",
         also_turns=[241], model_sheets=["mine/lava_approach_compare.png", "mine/lava_arrival_compare.png"],
         prev_frames=["previous/life_2/episodes/ep_001691/observation/image.png",
                      "previous/life_2/episodes/ep_001696/observation/image.png"]),
    dict(name="07_false_death_dismissed_from_the_frame", turn=289,
         title="Step 35121: the harness logged a death at the portal; the frame and the vitals said otherwise",
         summary=("The portal was entered with raw `forward` + `watch`, so no dimension check headed the queue and the "
                  "5631-block coordinate jump was logged `YOU DIED at (-3211,11,-5578) and respawned at (-403,42,-696)`. "
                  "The model's next OBSERVED: \"Coordinates and retained inventory match Nether arrival, but the view is blank "
                  "blue-gray rather than terrain. The death note conflicts with full health and unchanged gear; I'll wait for the "
                  "scene to load.\""),
         outcome=("Nothing was lost; `cursor.deaths=1` in worldmodel_report.json is this note (see provenance.json deaths_note). "
                  "A harness fix is pending (require a health drop or a dimension check before calling a jump a death).")),
    dict(name="08_nether_arrival_vs_life2_arrival", turn=290,
         title="Step 35121: the Nether arrival compared with life_2's arrival frame, six blocks from where life_2 died",
         summary=("Turn 290 ran then-now against life_2's Nether arrival frame ep_002519 (\"Confirm solid ground before moving or "
                  "mining\"); the digest carried life_2's death spot (-408, 43, -704) and its cause. The model collected one "
                  "netherrack after a short sneak and kept the shield and sneak discipline for the next 14,000 steps."),
         outcome="netherrack at step 35204 (16/24, +7 h 50; life_2 banked it at +11 h 17 and died 400 steps later). 0 deaths.",
         prev_frames=["previous/life_2/episodes/ep_002519/observation/image.png",
                      "previous/life_2/episodes/ep_002597/observation/image.png"]),
    dict(name="09_piglin_hit_retreat_on_own_bridge_frames", turn=434,
         title="Steps 42264-42533: after the first hit of the life, the retreat is checked against its own bridge frames",
         summary=("At step 42264 a piglin struck (health 8.6); the model's own `hit` reflex dropped the plan. Turns 434-436 "
                  "backed along the cobblestone bridge with the shield raised, running then-now against its own episodes "
                  "ep_002617, ep_002612 and ep_002591 to confirm the footing behind it; in the middle the starving reflex ate the "
                  "last porkchop (\"Health rose to 12, but the shield is now unequipped; the view clearly shows the piglin beside the "
                  "bridge\")."),
         outcome="Health 8.6 -> 12 -> 15; a two-block pillar for separation; no further damage to the end of the run.",
         also_turns=[435, 436]),
]


def turn_texts(ep: Path, n: int) -> tuple[list[str], list[str]]:
    """(look commands, model messages) of a turn."""
    cmds, msgs = [], []
    for it in L.turn_items(ep, n):
        if it.get("type") == "command_execution" and L.is_look(it):
            cmds.append(it.get("command", "").strip())
        elif it.get("type") == "agent_message":
            msgs.append(it.get("text", "").strip())
    return cmds, msgs


def regen_sheet(ep: Path, look_cmd: str, step: int, out: Path) -> bool:
    """Re-run the turn's then-now with the frame the model had (look_cases.regen_then_now writes into a
    look_outputs/ subdir; this variant names the file)."""
    tmp = out.parent / "_regen"
    tmp.mkdir(exist_ok=True)
    L.regen_then_now(ep, look_cmd, step, tmp)
    f = tmp / "look_outputs" / "then_now_regenerated.png"
    ok = f.exists()
    if ok:
        shutil.move(str(f), str(out))
    shutil.rmtree(tmp, ignore_errors=True)
    return ok


def stage_examples(r: dict, rows: list[dict], vu: dict, args) -> list[dict]:
    mcu, arm = r["mcu"], r["arm"]
    ep = mcu / "output" / arm / "episode_001"
    mem = ep / "memory"
    if args.dry_run:
        print(f"[dry] look_examples_of3m: {len(EXAMPLE_SPECS)} cases")
        return []
    if EXAMPLES.exists():
        shutil.rmtree(EXAMPLES)
    EXAMPLES.mkdir(parents=True)
    ms = L.milestones(mcu, arm)
    index = []
    for spec in EXAMPLE_SPECS:
        d = EXAMPLES / spec["name"]
        d.mkdir()
        n = spec["turn"]
        step = L.turn_step(ep, n)
        turns = [n] + spec.get("also_turns", [])
        files = []
        # the frames the model saw at the start of each named turn
        for t in turns:
            s = L.turn_step(ep, t)
            src = ep / "hires" / f"{s:07d}.jpg" if s is not None else None
            if src and src.exists():
                name = f"frame_640x360_turn{t:04d}_step{s}.jpg"
                shutil.copy(src, d / name)
                files.append(name)
        # the previous life's frames it compared against
        for pf in spec.get("prev_frames", []):
            src = mem / pf
            if src.exists():
                m = re.search(r"previous/(life_\d)/episodes/(ep_\d+)", pf)
                name = f"previous_{m.group(1)}_{m.group(2)}.png" if m else Path(pf).name
                shutil.copy(src, d / name)
                files.append(name)
        # the model's own sheets
        for sf in spec.get("model_sheets", []):
            src = mem / sf
            if src.exists():
                name = "model_sheet_" + Path(sf).name
                shutil.copy(src, d / name)
                files.append(name)
        for tf in spec.get("extra_text_files", []):
            src = mem / tf
            if src.exists():
                shutil.copy(src, d / Path(tf).name)
                files.append(Path(tf).name)
        # the exchange, per named turn: look command(s), what it said, the next turn's OBSERVED; regenerate the then-now
        body = []
        for t in turns:
            cmds, msgs = turn_texts(ep, t)
            s = L.turn_step(ep, t)
            body.append(f"### turn {t} (step {s})\n")
            if cmds:
                body.append("The model's command(s):\n")
                for c in cmds:
                    body.append("```\n" + c[:1500] + ("\n..." if len(c) > 1500 else "") + "\n```\n")
                    if "--then-now" in L.shell_part(c) and s is not None:
                        out = d / f"then_now_regenerated_turn{t:04d}_step{s}.png"
                        if regen_sheet(ep, L.shell_part(c), s, out):
                            files.append(out.name)
            if msgs:
                body.append("What it said after looking:\n")
                for mtxt in msgs:
                    body.append(mtxt[:2500] + ("\n..." if len(mtxt) > 2500 else "") + "\n")
            nxt = L.observed_of(L.turn_items(ep, t + 1))
            if nxt:
                body.append("The next turn's OBSERVED vs EXPECTED:\n\n" + nxt + "\n")
        if spec.get("viewed_from_rollout"):
            pt = next((x for x in vu["view_image"]["per_turn"] if x["turn"] == n), None)
            if pt:
                body.append(f"`view_image` calls in this turn (from the codex rollout): {pt['calls']}\n")
                for p in pt["paths"]:
                    body.append("- `" + re.sub(r"^.*/episode_001/memory/", "", p) + "`")
                body.append("")
        banked = [f"{m} @ {s}" for m, s in ms if step is not None and step <= s <= (L.turn_step(ep, n + 6) or s)]
        readme = (f"# {spec['name']} -- {arm} turn {n}, step {step}\n\n**{spec['title']}**\n\n{spec['summary']}\n\n"
                  f"## Outcome\n\n{spec['outcome']}\n\n"
                  + (f"Milestones verified within five turns: {', '.join(banked)}.\n\n" if banked else "")
                  + "## Files\n\n" + "\n".join(f"- `{f}`" for f in sorted(set(files)))
                  + "\n\n`frame_640x360_turn<T>_step<S>.jpg` = the exact wire frame at the step the turn started from (the hires "
                  "record; the model's attached frame was the 320x180 downscale of it); `previous_life_<i>_ep_<N>.png` = the "
                  "earlier life's frame it compared against or viewed; `model_sheet_*.png` = a sheet the model wrote into "
                  "`mine/`; `then_now_regenerated_*.png` = the turn's then-now re-run with the same frame (the model's own "
                  "`then_now.png` was overwritten by later turns).\n\n## The exchange\n\n" + "\n".join(body))
        (d / "README.md").write_text(readme)
        index.append({"name": spec["name"], "turn": n, "step": step, "title": spec["title"], "banked": banked})
    M.anonymise_tree(EXAMPLES)
    rows_md = "\n".join(f"| `{x['name']}` | {x['turn']} | {x['step']} | {x['title']} | {', '.join(x['banked']) or '--'} |" for x in index)
    vi, tn = vu["view_image"], vu["then_now"]
    (EXAMPLES / "README.md").write_text(f"""# Look examples from of3m_mfm (MFM gen 4 min, gpt-6-astra high, 2026-09-10)

Nine episodes from the third life of the carry-only `ender_dragon` chain (of3 -> of3r -> of3m; 16/24 in 14 h, 0 deaths,
tying the record of3r set in 13 h, ahead of it on the wall clock at every milestone but the diamond quartet) in which a remembered frame -- a previous life's
or this life's own, viewed with `view_image` or laid beside the current view by `tools/episodes.py --then-now` -- decided
the next action. Nothing from the earlier lives was put in front of the model by the harness: their records sit under
`previous/life_1/` (of3, 10/24) and `previous/life_2/` (of3r, 16/24) and reading them was the model's act, starting with
the workshop turn.

| example | turn | step | what happened | verified within 5 turns |
|---|---|---|---|---|
{rows_md}

Across the whole life: {vi['calls']} `view_image` calls ({vi['by_kind'].get('previous_life_2_frame', 0)} of life_2's frames,
{vi['by_kind'].get('previous_life_1_frame', 0)} of life_1's, {vi['by_kind'].get('own_episode_frame', 0)} of its own episodes),
{tn['calls']} then-now sheets ({tn['previous_life_calls']} against a previous life's frame, {tn['distinct_previous_life_targets']}
distinct previous-life targets) -- `carry-only-era/gen4min/of3m_mfm/vision_use.json`. Every look turn with a milestone banked
within five turns is dumped in full (prompt, transcript, frames before/after, executed log) under
`carry-only-era/look-cases/gen4min_of3m_mfm/`; the run itself (trajectory, per-step hires record, slimmed codex rollouts,
launcher logs, harness code at the commit) is `carry-only-era/gen4min/of3m_mfm/`.

Source: `<MCU>/output/of3m_mfm/episode_001` (codex_turns/turn_NNNN.events.jsonl, memory/logs.txt, hires/, the codex rollout
for the view_image calls). Text anonymised as elsewhere in this dataset.
""")
    return index


# ------------------------------------------------------------------------------------------------
# diffs, README, manifest
# ------------------------------------------------------------------------------------------------
def diffs(gen2: dict, gen4: dict) -> None:
    d = OUT / "diff-gen2-to-gen4min"
    d.mkdir(exist_ok=True)
    s0, s1 = gen2["code_identity"]["mcu"]["commit"], gen4["code_identity"]["mcu"]["commit"]
    r = subprocess.run(["git", "diff", s0, s1, "--", "mcu_worldmodel", "scripts"], cwd=MCU_MIN, capture_output=True, text=True)
    (d / "mcu.patch").write_text(f"# git diff {s0[:8]}..{s1[:8]} -- mcu_worldmodel scripts (MCU-AgentBeats, branch gen4-min)\n" + r.stdout)
    m0, m1 = gen2["code_identity"]["mfm_package"]["commit"], gen4["code_identity"]["mfm_package"]["commit"]
    r = subprocess.run(["git", "diff", m0, m1, "--", "mfm"], cwd=MFM_MIN, capture_output=True, text=True)
    (d / "mfm.patch").write_text(f"# git diff {m0[:8]}..{m1[:8]} -- mfm (the mfm package repo, branch gen4-min)\n" + r.stdout)
    c0 = OUT / gen2["group"] / gen2["run"] / "trajectory/episode_001/memory/AGENTS.md"
    c1 = OUT / gen4["group"] / gen4["run"] / "trajectory/episode_001/memory/AGENTS.md"
    r = subprocess.run(["diff", "-u", str(c0), str(c1)], capture_output=True, text=True)
    (d / "contract.diff").write_text(f"# the contract as received: {gen2['run']} (gen 2) -> {gen4['run']} (gen 4 min)\n" + r.stdout)
    src = MFM_GRID / "tasks/mfm-three-layer.spatial-grid/analysis/gen4_contract_diff_min.txt"
    if src.exists():
        shutil.copy(src, d / "gen4_contract_diff_min.txt")
    M.anonymise_tree(d)
    (d / "README.md").write_text(
        "# gen 2 -> gen 4 min: what changed in the harness\n\n"
        "Gen 4 min is gen 2's code (MCU `b2f8c832`, mfm `ede1627`) plus three model-facing edits and two invisible ones "
        "(`gen4_plan_2026-09-10.md` section 11 in `../gen4min/of3m_mfm/harness-code/launcher/`):\n\n"
        "1. the `starving.py` starter reflex eats what is carried when the food bar drops a point below 18 (a note once when "
        "nothing is carried; a stop once at health 10.5) -- `skills.py`;\n"
        "2. one hunger line in the contract's Safety paragraph (natural healing needs food 18+, the bar falls about a point per "
        "4000 steps, a life's deficit is one animal) -- `prompts.py`;\n"
        "3. \"view_image a frame before you walk to a remembered place **and, on arrival, `--then-now <that episode>` once**\" in "
        "the Memory paragraph, and the workshop paragraph asks for the episode id beside each digest place -- `prompts.py`, "
        "`skills.py`;\n"
        "4. invisible: the adapter keeps every 640x360 wire frame under `hires/` (the model still gets 320x180), the OpenRouter "
        "route (auth by command, a proxy wrapper), and `episodes.py --then-now` accepting an episode directory (a gen-3b error).\n\n"
        f"- `mcu.patch`: `mcu_worldmodel/` and `scripts/` between MCU `{s0[:8]}` ({gen2['run']}) and `{s1[:8]}` ({gen4['run']})\n"
        f"- `mfm.patch`: the mfm package between `{m0[:8]}` and `{m1[:8]}`\n"
        "- `contract.diff`: the two `AGENTS.md` files as the models received them\n"
        "- `gen4_contract_diff_min.txt`: the same diff rendered offline before the launch, with `skills/memory/SKILL.md` and the "
        "starving example, byte-checked against of3r's files\n\n"
        "None of gen 3b's doctrine (codex-native skills, the thread-persists sentence, the 20-fact digest, the open-loop pace "
        "rule) is in gen 4 min; `../diff-gen2-to-gen3b/` holds that branch.\n")


def readme(provs: list[dict]) -> None:
    a, b, c = provs   # gen2, gen3b, gen4min

    def tl(p):
        return {m["milestone"]: m for m in p["milestone_timeline_wall"]}

    ta, tb, tc = tl(a), tl(b), tl(c)
    names = []
    for p in (a, b, c):
        for m in p["milestone_timeline_wall"]:
            if m["milestone"] not in names:
                names.append(m["milestone"])
    order = a["milestones_all"].keys()
    names = sorted(names, key=lambda n: list(order).index(n) if n in order else 99)

    def cell(x):
        return f"{x['n']}/24 @{x['step']} (+{x['wall_min']:.0f} min)" if x else "--"

    rows = [f"| {n} | {cell(ta.get(n))} | {cell(tb.get(n))} | {cell(tc.get(n))} |" for n in names]
    vu = c["vision_use"]
    txt = f"""# carry-only era: gen 2, gen 3b and gen 4 min, head to head (updated {datetime.now():%Y-%m-%d})

Three lives of the **mfm arm** in the same world (seed 0, fixed spawn), same model (`gpt-6-astra`, effort high), same
task (`ender_dragon`, 100,000 steps under a 13-14 h wall), same lineage (gen 2's seed is of3's record; gen 3b's and gen 4
min's seed is gen 2's record, which carries of3 -- so both later lives read two earlier lives under `previous/`),
**no harness-pushed facts in any of them** -- the harness puts nothing from earlier lives in front of the model; reading
`previous/` is the model's act. What differs is the harness code and the contract:

| | `{a['run']}` (gen 2) | `{b['run']}` (gen 3b) | `{c['run']}` (gen 4 min) |
|---|---|---|---|
| MCU commit | `{a['code_identity']['mcu']['commit'][:8]}` | `{b['code_identity']['mcu']['commit'][:8]}` | `{c['code_identity']['mcu']['commit'][:8]}` (branch gen4-min) |
| mfm package commit | `{a['code_identity']['mfm_package']['commit'][:8]}` | `{b['code_identity']['mfm_package']['commit'][:8]}` | `{c['code_identity']['mfm_package']['commit'][:8]}` (branch gen4-min) |
| contract | gen 2 (`memory/AGENTS.md`) | gen 3b: codex-native skills, "the thread persists", digest = 20 facts, open-loop pace rule | gen 2 + three edits: the starving reflex eats carried food below 18, the hunger line, then-now once on arrival + episode ids in the digest (`diff-gen2-to-gen4min/`) |
| frames | 320x180 | 640x360 (+ `hires.tar`) | 320x180 (+ `hires.tar`, the 640x360 per-step record) |
| provider | nyu plan | OpenRouter | OpenRouter |
| result | **16/24** at {a['steps_run']} steps, 13 h | **9/24** at step {b['steps_run']} (stopped by the operator at 5 h 25) | **16/24** at {c['steps_run']} steps, 14 h (the 16th at +7 h 50) |
| deaths | {a['deaths']} (a piglin in the Nether) | {b['deaths']} | 0 (`deaths=1` in the report is a false portal-transit note, see `provenance.json`) |
| view_image / then-now | 3 look turns in 520, no previous-life frame viewed | 29 look turns, 5 across-life then-nows | {vu['view_image_calls']} view_image calls ({vu['distinct_previous_life_frames_viewed']} distinct previous-life frames), {vu['then_now_calls']} then-nows ({vu['then_now_previous_life_calls']} against a previous life) |

Milestones by step and by wall time since the first codex turn:

| milestone | gen 2 | gen 3b | gen 4 min |
|---|---|---|---|
""" + "\n".join(rows) + f"""

Gen 4 min was ahead of gen 2 on the wall clock at every milestone but the diamond quartet, which it banked within five
minutes of gen 2's times (iron pickaxe +56 vs +67 min, flint and steel +2 h 10 vs +6 h 41, diamond +4 h 07 vs +4 h 02,
obsidian +6 h 43 vs +7 h 40, netherrack +7 h 50 vs +11 h 17), and then spent 14,300 steps in the Nether bridging
over lava one support at a time, mostly north and west of the spot where gen 2 died, without reaching a fortress. Its
across-life looks are the difference in kind: the iron approach compared frame by frame against life_2's episodes until
the ore was under the pickaxe, the deep staircase opened where life_2's entrance frame shows it, the tunnel walked to
life_2's diamond wall by its frames, two compare sheets of its own at the lava frontier, the Nether arrival checked against
life_2's arrival frame six blocks from life_2's death spot (`look-cases/gen4min_of3m_mfm/`, `../look_examples_of3m/`,
`gen4min/of3m_mfm/vision_use.json`).

The gen-3b record is final: the run was stopped by the operator at 03:10 (turn 193, step 21,600, 9/24, at y=11 about 20
blocks from the digest's recorded diamond site). `profile.txt` in each run directory is the per-turn behaviour profile
(`turn_profile.py`): exec cells per turn by kind (skill reads, frame looks, episode queries, previous-life reads), steps
per plan entry and per turn, turn interval, the sizes of `mine/digest.md`, `mine/working.md`, `mine/notes.md`.

## Layout

```
carry-only-era/
  gen2/{a['run']}/  gen3b/{b['run']}/  gen4min/{c['run']}/
    provenance.json            run, flags, seeds, score, milestone timeline (steps and wall minutes),
                               deaths, code identity (commit + the worktree reflog that verifies it),
                               snapshot state, staged sizes
    profile.txt                turn_profile.py over the run
    vision_use.json            (gen 4 min) every view_image call from the codex rollout, by turn and by what
                               was viewed; every then-now and zoom cell from the per-turn events
    trajectory/episode_001/    memory/ (logs.txt, index.jsonl, episodes.tar, mine/, tools/, references/,
                               skills/, AGENTS.md -- the contract as received), codex_turns/ (per-turn
                               prompt + codex events), attach/, worldmodel_report.json; hires.tar (gen 3b, gen 4 min)
                               memory/previous/LINEAGE.json names the stripped seed lives
    codex_sessions/            the codex rollouts, slimmed (compaction snapshots and base64 frames out)
    launcher/                  launch/purple/green/client/wall logs, the toml
    harness-code/              mcu_worldmodel/ + arm scripts and the mfm package at the run's commits
                               (gen 4 min: + launcher/ with launch_g4.sh and the gen-4 plan)
  look-cases/                  one directory per look turn: prompt, transcript, frames before/after, the
                               sheet or crop, the executed log (README.md lists them per generation)
  diff-gen2-to-gen3b/          mcu.patch, mfm.patch, contract.diff
  diff-gen2-to-gen4min/        mcu.patch, mfm.patch, contract.diff, gen4_contract_diff_min.txt
  runs.csv, manifest.json
```

Text files are anonymised as in `mfm-era/` (paths -> `<MCU>`, `<MFM>`, `<CODEX_HOMES>`, `<HOME>`; user name -> `user`).
No run has an evaluator video: all three were stopped from outside (the wall watchdog or the operator).
"""
    (OUT / "README.md").write_text(txt)


def top_readme_box(c: dict) -> None:
    f = M.STAGING / "README.md"
    txt = f.read_text()
    if "of3m_mfm" in txt:
        return
    vu = c["vision_use"]
    box = (f"> **{datetime.now():%Y-%m-%d} — gen 4 min joins the carry-only chain; `look_examples_of3m/` is new.**\n"
           f"> `of3m_mfm` (gen 4 min = gen 2's code plus three model-facing edits, MCU `{c['code_identity']['mcu']['commit'][:8]}`,\n"
           "> branch gen4-min), the third life of the of3 -> of3r -> of3m chain, seeded with of3r's record and nothing pushed:\n"
           f"> **16/24 at {c['steps_run']} steps / 14 h with 0 deaths, tying the carry-only record and ahead of gen 2 at every**\n"
           "> **milestone but the diamond quartet** (iron pickaxe +56 vs +67 min after the first codex turn, flint and steel\n"
           "> +2 h 10 vs +6 h 41, diamond +4 h 07 vs +4 h 02, obsidian +6 h 43 vs +7 h 40, netherrack +7 h 50 vs +11 h 17), then\n"
           "> 14k steps bridging the Nether. The multimodal carry is visible for the first time at\n"
           f"> scale: {vu['view_image_calls']} `view_image` calls ({vu['distinct_previous_life_frames_viewed']} distinct frames of the\n"
           f"> earlier lives), {vu['then_now_calls']} then-now sheets ({vu['then_now_previous_life_calls']} against a previous life's\n"
           "> frame) — the iron approach matched frame by frame to life_2's episodes, the staircase and the diamond vein\n"
           "> found from life_2's frames, the Nether arrival checked against life_2's arrival six blocks from its death.\n"
           "> `carry-only-era/gen4min/of3m_mfm/` (trajectory, 49,570-frame hires record, slimmed rollouts, `vision_use.json`,\n"
           "> harness code), `carry-only-era/look-cases/gen4min_of3m_mfm/` (every milestone-tied look turn in full),\n"
           "> `look_examples_of3m/` (nine curated cases with the frames), `carry-only-era/diff-gen2-to-gen4min/`; the\n"
           "> three-generation table is in `carry-only-era/README.md`.\n\n")
    anchor = "# MCU long-horizon trajectories — dragon / diamond\n\n"
    assert anchor in txt
    f.write_text(txt.replace(anchor, anchor + box, 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sessions", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-trajectory", action="store_true", help="reuse the staged run (provenance.json) and redo cases/docs only")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    r = RUN
    dst = OUT / r["group"] / r["arm"]
    if args.no_trajectory and (dst / "provenance.json").exists():
        prov = json.load(open(dst / "provenance.json"))
        vu = json.load(open(dst / "vision_use.json"))
    else:
        prov = stage_run(r, args)
        if not prov:
            return
        vu = json.load(open(dst / "vision_use.json"))
    rows = scored_turns(r["mcu"], r["arm"])
    out, turns = dump_look_cases(r, rows, args)
    stage_examples(r, rows, vu, args)
    if args.dry_run:
        return
    # look-cases README: the gen 4 section goes in before gen 3b's
    lc = OUT / "look-cases/README.md"
    txt = lc.read_text()
    txt = re.sub(r"## gen 4 min .*?(?=## gen 3b)", "", txt, flags=re.S)
    txt = txt.replace("selection below is every look\nturn of the two runs", "selection below is every look\nturn of the three runs")
    marker = "## gen 3b"
    txt = txt.replace(marker, look_cases_readme_section(r, rows, turns, vu) + marker, 1)
    lc.write_text(txt)
    provs = []
    for g, a in (("gen2", "of3r_mfm"), ("gen3b", "of3g_mfm")):
        provs.append(json.load(open(OUT / g / a / "provenance.json")))
    provs.append(prov)
    diffs(provs[0], prov)
    M.write_runs_csv(provs)
    stats = M.STAGING / "stats/runs.csv"
    if stats.exists():
        existing = {row.split(",")[0] for row in stats.read_text().splitlines()[1:]}
        with open(stats, "a", newline="") as fh:
            w = csv.writer(fh)
            if prov["run"] not in existing:
                w.writerow([prov["run"], "kill_ender_dragon", "mfm", prov["condition"], "carry_only_era", prov["max_steps"], prov["score"],
                            prov["milestones"], prov["codex"]["calls"], " ".join(f"{k}@{v}" for k, v in prov["milestones_all"].items())])
    readme(provs)
    top_readme_box(prov)
    tot, n = M.du(OUT)
    ex_tot, ex_n = M.du(EXAMPLES)
    json.dump({"dataset_dir": "carry-only-era", "staged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S +0800"),
               "runs": [{"run": p["run"], "group": p["group"], "generation": p["generation"], "score": p["score"],
                         "milestones": p["milestones"], "steps": p["steps_run"], "snapshot": p["snapshot"],
                         "bytes": p["staged"]["bytes"], "files": p["staged"]["files"]} for p in provs],
               "look_cases": {"gen2_of3r_mfm": 3, "gen3b_of3g_mfm": 19, f"{r['group']}_{r['arm']}": len(turns)},
               "companion": {"look_examples_of3m": {"cases": len(EXAMPLE_SPECS), "bytes": ex_tot, "files": ex_n}},
               "bytes_total": tot, "files_total": n,
               "left_out": ["memory/previous/life_*/ (copies of the seed lives; LINEAGE.json names them)",
                            "codex rollouts' compaction snapshots and base64 frames"]},
              open(OUT / "manifest.json", "w"), indent=1)
    print(f"staged {prov['run']}: {prov['staged']['bytes']/1e9:.2f} GB {prov['staged']['files']} files; look-cases {len(turns)} turns; "
          f"examples {ex_n} files; era total {tot/1e9:.2f} GB {n} files")


if __name__ == "__main__":
    main()
