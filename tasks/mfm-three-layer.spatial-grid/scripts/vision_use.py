"""What each arm looked at with view_image, from its codex rollouts (read-only).

    python vision_use.py og14_mfm og19_mfm ...        # names under $MCU_CODEX_ROOT (codex-homes/)

Per arm: the view_image calls found in the rollout's custom_tool_call lines, classified by
the path they were pointed at -- a zoom/crop of the current view (/tmp, zoom, crop), the
attached view or sheet (attach/), this life's episode frames (episodes/ep_), an earlier
life's frames (previous/), the model's own images (mine/). The harness's own counter
(codex_backend.scan_rollout: view_image_calls) counts calls in every format and runs higher;
this script answers the narrower question: did the arm ever look BACK.
"""
import collections, glob, os, re, sys

ROOT = os.environ.get("MCU_CODEX_ROOT",
                      "/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes")


def classify(p: str) -> str:
    if "previous/" in p: return "previous life frame"
    if "episodes/" in p: return "this life's episode frame"
    if "attach/" in p: return "attached view/sheet"
    if p.startswith("/tmp") or "zoom" in p or "crop" in p: return "zoom/crop of the current view"
    if "mine/" in p: return "mine/ image"
    return "other"


def scan(arm: str) -> tuple[int, collections.Counter]:
    n, kinds = 0, collections.Counter()
    for f in glob.glob(f"{ROOT}/{arm}/sessions/*/*/*/rollout-*.jsonl"):
        for ln in open(f, encoding="utf-8", errors="ignore"):
            if '"custom_tool_call"' not in ln or "view_image" not in ln:
                continue
            for m in re.finditer(r"view_image\((.*?)\)", ln):
                n += 1
                pm = re.search(r"[\w./-]+\.png", m.group(1).replace("\\", ""))
                kinds[classify(pm.group(0) if pm else m.group(1))] += 1
    return n, kinds


if __name__ == "__main__":
    for arm in sys.argv[1:]:
        n, kinds = scan(arm)
        print(f"{arm}: {n} view_image calls -- " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
