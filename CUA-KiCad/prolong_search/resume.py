"""Continue a finished or crashed run in place, from its own checkpoint.

`n` used to be committed per run: the memory arms build their filesystem state over
the question sequence, so extending a comparison from n=100 to n=300 meant rerunning
the first 100 questions. But everything the next question actually depends on is
already on disk -- logs.txt, frames/, the world-model docs, hypotheses/graph.json --
and the checkpoint records which prefix of the sample list produced it. Resuming is
therefore: verify the checkpoint *is* a prefix of today's sample list, preload its
records, and hand the agent its counters back. What is deliberately not restored is
per-process audit state (parse failures, codex session lists): each invocation's
result.json reports its own, and the archived `result.json.n<K>` keeps the earlier
run's block, so the cumulative picture is the sum of the blocks rather than a
counter that pretends one process ran throughout.

The same mechanism is crash insurance: a 300-question hosted run that dies at
question 250 resumes from its checkpoint instead of burning twelve hours again.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_checkpoint_records(path: Path | str) -> list[dict]:
    """Parse the append-only checkpoint, tolerating exactly one torn final line.

    A crash mid-`write` can leave a partial last line; dropping it re-runs that one
    question, which for the memory arms means the workspace log may carry a duplicate
    section for it -- bounded, and better than refusing to resume. A torn line
    anywhere *else* means the file did not grow append-only, and no prefix of it can
    be trusted.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    records: list[dict] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                logger.warning(
                    "[resume] dropping a torn final checkpoint line (crash mid-write); "
                    "question %d re-runs and the workspace log may carry a duplicate "
                    "section for it", len(records))
                break
            raise SystemExit(
                f"[resume] {path} is corrupt at line {i + 1}, which is not the final "
                "line; an append-only file cannot look like this, refusing to guess")
    return records


def guard_stale_checkpoint(path: Path | str | None, resume: bool) -> None:
    """A non-empty checkpoint under a fresh run is a footgun, not a warning.

    Without this, relaunching in an old directory moves the workspace aside as
    `.crashed` but *appends* to the old checkpoint -- two runs interleaved in one
    file, unusable for either.
    """
    if resume or path is None:
        return
    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        raise SystemExit(
            f"{p} already holds records from an earlier run. Pass --resume to "
            "continue that run in place, or point --output at a fresh directory. "
            "Appending a second run to the same checkpoint would corrupt both.")


def verify_prefix(records: list[dict], samples: list[Any]) -> None:
    """The memory arms may only resume onto the exact sequence that built the memory."""
    if len(records) > len(samples):
        raise SystemExit(
            f"[resume] checkpoint holds {len(records)} records but only "
            f"{len(samples)} samples are selected; raise --limit (or drop --tasks "
            "filters) to at least the original run's selection")
    for i, rec in enumerate(records):
        s = samples[i]
        if (rec.get("key_question") != s.get("key_question")
                or rec.get("task") != s.get("task_str", "unknown")):
            raise SystemExit(
                f"[resume] checkpoint record {i} ({rec.get('key_question')!r}, "
                f"{rec.get('task')!r}) does not match sample {i} "
                f"({s.get('key_question')!r}, {s.get('task_str')!r}). The sample "
                "sequence differs from the original run (dataset order, --tasks or "
                "--split changed); a memory built on one sequence cannot be "
                "continued on another.")


def preload(records: list[dict]) -> tuple[list[dict], dict[str, list[bool]]]:
    """Rebuild (results, per_task) as the evaluator loop would have left them."""
    results: list[dict] = []
    per_task: dict[str, list[bool]] = {}
    for rec in records:
        results.append(rec)
        per_task.setdefault(rec.get("task", "unknown"), []).append(bool(rec.get("correct")))
    return results, per_task


def archive_prior_result(output_path: Path | str, k: int) -> Path | None:
    """Move the earlier run's result.json aside as `<name>.n<K>` before overwriting.

    The earlier block is evidence -- its audit counters and arm record describe the
    first K questions and are not reproduced by the resumed process.
    """
    p = Path(output_path)
    if not p.exists():
        return None
    dst = p.with_name(f"{p.name}.n{k}")
    n = 2
    while dst.exists():
        dst = p.with_name(f"{p.name}.n{k}.{n}")
        n += 1
    p.rename(dst)
    logger.info("[resume] archived the earlier result to %s", dst)
    return dst
