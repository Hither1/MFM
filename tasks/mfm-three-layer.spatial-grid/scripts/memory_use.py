"""Did a life actually read its memory, and when -- from the codex rollouts (read-only).

    python memory_use.py of1_mfm of3r_mfm ...       # names under $MCU_CODEX_ROOT
    python memory_use.py of3r_mfm --json

Source: `<codex home>/<arm>/sessions/**/rollout-*.jsonl`. A TURN boundary is a user
message carrying an `input_image` (the attached view), so "turn 1" is the opening turn,
where reading the carried record is cheap and expected; "later" is every turn after it,
where reading it means the model went back for something. Tool calls are the
`custom_tool_call` records named `exec`: shell commands come from the
`tools.exec_command({cmd:"..."})` calls inside the call's input, image looks from the
`view_image(...)` calls in the same input. `compacted` records are context compactions.

Per life: turns; commands mentioning `previous/`, split turn 1 vs later; commands reading
`mine/digest.md` and `mine/notes.md` after turn 1; `view_image` calls in total and split
into this life's `episodes/` frames and `previous/` frames; uses of the `--then-now` and
`--previous` flags of the episodes tool; compactions.

When an arm has more than one rollout file, the LARGEST is used and the others are named
in a note; they are not merged, because turn numbering restarts in each file. Size, not
recency: of1_mfm and of2_mfm each have a 0.5 MB stub written after the 441 MB and 216 MB
rollouts that hold the actual life, so "the newest" would report a one-turn run.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import print_table                                            # noqa: E402

ROOT = os.environ.get("MCU_CODEX_ROOT",
                      "/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes")

CMD_RE = re.compile(r'cmd\s*:\s*"((?:[^"\\]|\\.)*)"')
VIEW_RE = re.compile(r'view_image\((?:\{[^{}]*?path\s*:\s*)?"((?:[^"\\]|\\.)*)"')


def _unescape(s):
    try:
        return json.loads('"' + s + '"')
    except ValueError:
        return s


def rollouts(arm):
    """Every rollout file of an arm, largest last."""
    files = glob.glob(os.path.join(ROOT, arm, "sessions", "*", "*", "*", "rollout-*.jsonl"))
    return sorted(files, key=lambda p: os.path.getsize(p))


def scan(path):
    """Walk one rollout in order, counting per turn."""
    out = {"turns": 0, "prev_cmd_t1": 0, "prev_cmd_later": 0, "digest_later": 0,
           "notes_later": 0, "view": 0, "view_episodes": 0, "view_previous": 0,
           "then_now": 0, "prev_flag": 0, "compactions": 0, "commands": 0}
    turn = 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for ln in fh:
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            kind = rec.get("type")
            if kind == "compacted":
                out["compactions"] += 1
                continue
            payload = rec.get("payload") or {}
            ptype = payload.get("type")
            if kind == "response_item" and ptype == "message" and payload.get("role") == "user":
                if any((c or {}).get("type") == "input_image"
                       for c in payload.get("content") or []):
                    turn += 1
                    out["turns"] = turn
                continue
            if kind != "response_item" or ptype != "custom_tool_call":
                continue
            src = str(payload.get("input") or "")
            for m in CMD_RE.finditer(src):
                cmd = _unescape(m.group(1))
                out["commands"] += 1
                if "previous/" in cmd:
                    out["prev_cmd_t1" if turn <= 1 else "prev_cmd_later"] += 1
                if turn > 1 and "mine/digest.md" in cmd:
                    out["digest_later"] += 1
                if turn > 1 and "mine/notes.md" in cmd:
                    out["notes_later"] += 1
                if "--then-now" in cmd:
                    out["then_now"] += 1
                if "--previous" in cmd:
                    out["prev_flag"] += 1
            for m in VIEW_RE.finditer(src):
                path_seen = _unescape(m.group(1))
                out["view"] += 1
                if "previous/" in path_seen:
                    out["view_previous"] += 1
                elif "episodes/" in path_seen:
                    out["view_episodes"] += 1
    return out


def main(argv=None):
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arm", nargs="+", help="codex home name, e.g. of3r_mfm")
    ap.add_argument("--root", default=ROOT, help="codex homes directory")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    ROOT = args.root

    rows, notes, data = [], [], {}
    for arm in args.arm:
        files = rollouts(arm)
        if not files:
            notes.append(f"{arm}: no rollout found under {ROOT}")
            continue
        if len(files) > 1:
            notes.append(
                f"{arm}: {len(files)} rollouts, using the largest "
                f"({os.path.basename(files[-1])}, {os.path.getsize(files[-1]) // 10**6} MB); "
                "ignored: " + ", ".join(f"{os.path.basename(f)} "
                                        f"({os.path.getsize(f) // 10**6} MB)" for f in files[:-1]))
        s = data[arm] = scan(files[-1])
        s["rollout"] = files[-1]
        rows.append([arm, s["turns"], s["commands"], s["prev_cmd_t1"], s["prev_cmd_later"],
                     s["digest_later"], s["notes_later"], s["view"], s["view_episodes"],
                     s["view_previous"], s["then_now"], s["prev_flag"], s["compactions"]])
    if args.json:
        print(json.dumps(data, indent=1))
    else:
        print_table(["life", "turns", "cmds", "prev/ t1", "prev/ later", "digest later",
                     "notes later", "view_image", "of episodes/", "of previous/",
                     "--then-now", "--previous", "compactions"], rows)
    for n in notes:
        print(n, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
