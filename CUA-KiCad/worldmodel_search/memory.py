"""The multimodal filesystem that is the world-model arm's memory.

Layout, on top of the PRO-LONG workspace this arm shares with the prolong arm
(`prolong_search.log.EpisodeLog` writes `logs.txt` and `frames/` in exactly the prolong
format, so the two arms' traces are directly comparable):

    logs.txt            append-only: one section per question -- [QUESTION], [CHOICES],
                        [FRAME] paths, then [ANSWER] and the carried note. Grepped,
                        never read whole. Harness-written.
    frames/             every question's images, full resolution, addressed by the
                        [FRAME] paths. This is the store the textual world model
                        indexes: pixels are hard to search, paths are not.
    world_model/        the compiled documents the induction pass rewrites and every
                        act turn reads. Agent-written.
    hypotheses/         graph.json -- the belief DAG, mirrored to disk every turn --
                        plus one .md per node (a projection, for grepping).
                        Harness-written from the agent's ops.
    events/events.jsonl only under --outcome-feedback: one line per graded question.
                        Harness-written; the agent cannot write here, which is what
                        lets the discipline use it as an arbiter.
    notes/ (and ./)     the agent's to organise.

Who writes what is enforced, not conventional: `assert_harness_files_intact` fails
loudly if the agent shrinks a harness-owned file, because an agent that can rewrite its
own record can make any claim check out.

The document set is upstream's five -- spatial, semantic, dynamics, procedural, causal
-- with each category re-grounded from an embodied world to a question world; the
taxonomy itself is kept because it is the architecture, not a Minecraft detail. Each is
seeded so the first act turn reads a real file rather than inventing a layout (ad-hoc
layouts diverge, and induction then cannot merge two stretches' knowledge), and each
seed states the indexing contract: entries cite Q ids and [FRAME] paths, because a
textual entry that points at pixels is what makes the image store addressable at all.

`tools/zoom.py` is the other half of that contract, ported from upstream: the frames
are addressable (every log section carries its [FRAME] path) but not *inspectable* --
microscopy detail lives below what a whole frame shows, and upstream measured an agent
spending its last 1,700 steps failing to read textures a crop would have resolved. The
tool dereferences a frame pointer at pixel level: crop a region, magnify it, view the
result.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories the agent may write. Anything else under the root is the harness's.
AGENT_OWNED = ("world_model", "notes")
HARNESS_OWNED_FILES = ("logs.txt", "AGENTS.md", "events/events.jsonl")


class WorldModelWorkspace:
    """Owns the world-model directory tree beside the episode log, and the harness's
    half of what is written into it."""

    #: The five documents, upstream's taxonomy re-grounded for a question world.
    #: Rewritten whole by induction turns, read (truncated per document) by every
    #: act turn.
    WORLD_MODEL_DOCS = {
        "spatial": ("Where things are, within and across this run's images: subcellular "
                    "localisation, what appears next to what, layout patterns of the "
                    "recurring specimens. Cite [FRAME] paths and Q ids."),
        "semantic": ("What things are: imaging modalities, stains and markers, "
                     "structures and morphologies, and what each indicates or affords. "
                     "Cite exemplar frames."),
        "dynamics": ("How the biology responds: processes over time, what a treatment "
                     "or perturbation changes, what varies between conditions -- the "
                     "constants experiment_proposal questions turn on."),
        "procedural": ("Recipes that worked for answering each task type (perception, "
                       "hypothesis_gen, experiment_proposal), with preconditions; "
                       "approaches that failed belong here too, marked as failed, with "
                       "what went wrong. Ends with the `## Strategy check` the "
                       "induction pass maintains."),
        "causal": ("Why things happen: mechanisms, dependencies, what must be true "
                   "before what -- the cause-and-effect chains hypothesis_gen "
                   "questions live on."),
    }

    def __init__(self, root: str | Path, *, outcome_feedback: bool = False,
                 docs: dict[str, str] | None = None) -> None:
        # Absolute, always: the Codex backend runs with cwd == this root and resolves
        # every path against it.
        self.root = Path(root).resolve()
        # The taxonomy is the arm's; the grounding is the benchmark's. A port to
        # another world (the KiCad GUI episode) passes its own five blurbs; the
        # set above stays the default.
        if docs is not None:
            self.WORLD_MODEL_DOCS = dict(docs)
        self.world_model_dir = self.root / "world_model"
        self.graph_path = self.root / "hypotheses" / "graph.json"
        self.events_path = self.root / "events" / "events.jsonl"
        self.outcome_feedback = outcome_feedback

        for d in ("world_model", "hypotheses", "notes", "tools"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self._write_tools()
        if outcome_feedback:
            # Created only under the feedback variant: an empty events channel on the
            # default arm would describe a signal that does not exist.
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_path.touch()

    def _write_tools(self) -> None:
        """Executable helpers the agent can run against its own visual memory.

        Ported from upstream's `_write_tools`. The shebang is `/usr/bin/env python`
        rather than this interpreter's absolute path, because inside the sandbox
        wrapper's namespace the runner's python does not exist -- PATH there resolves
        to `sandbox_bin/python`. PIL may be missing in that environment too, so the
        script fails with a sentence instead of a traceback.
        """
        zoom = self.root / "tools" / "zoom.py"
        if zoom.exists():
            return
        zoom.write_text('''#!/usr/bin/env python
"""Crop a frame region and magnify it, for reading detail a full image hides.

    ./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]

x,y = top-left of the region in the image's own pixels; the crop is scaled 4x
nearest-neighbour (pixel-accurate, no smoothing) into out.png (default ./zoom.png).
Then open the result with view_image. Compare two frames by zooming the same region
in both and viewing them in sequence.
"""
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("zoom.py needs PIL, which this environment does not have; "
             "fall back to view_image on the full frame.")

frame, x, y, w, h = sys.argv[1], *map(int, sys.argv[2:6])
out = sys.argv[6] if len(sys.argv) > 6 else "zoom.png"
img = Image.open(frame).convert("RGB")
x = max(0, min(img.width - 1, x)); y = max(0, min(img.height - 1, y))
w = max(1, min(img.width - x, w)); h = max(1, min(img.height - y, h))
img.crop((x, y, x + w, y + h)).resize((w * 4, h * 4), Image.NEAREST).save(out)
print(f"wrote {out}: {w}x{h} region at ({x},{y}) of {img.width}x{img.height}, 4x")
''', encoding="utf-8")
        zoom.chmod(0o755)

    # -- the structured world model ---------------------------------------

    def seed_world_model(self) -> None:
        for name, blurb in self.WORLD_MODEL_DOCS.items():
            p = self.world_model_dir / f"{name}.md"
            if p.exists():
                continue
            p.write_text(
                f"# {name.capitalize()}\n\n_{blurb}_\n\n"
                "> Nothing induced yet. This file is rewritten by the induction pass "
                "from `logs.txt`, `hypotheses/` and the frames the log names.\n",
                encoding="utf-8",
            )

    def world_model_summary(self, per_doc_chars: int = 1500,
                            exclude: tuple[str, ...] = ()) -> str:
        """The world model as it goes into an act turn's prompt.

        Truncated per document rather than in total: a `knowledge.md` that induction
        has grown large must not be able to push `strategies.md` out of the prompt
        entirely, because the act turn needs all of them. Induction is told the budget,
        so growth past it is a signal the document needs compacting, not a silent loss.

        `exclude` names documents to withhold from THIS prompt. It does not change what
        induction compiles -- the document is still written, still on disk, and still
        read by every turn that does not exclude it -- so the memory is intact and only
        one turn's view of it is narrowed. Used by the procedural ablation; see
        the procedural ablation flag of the evaluator that drives it.
        """
        parts = []
        for name in self.WORLD_MODEL_DOCS:
            if name in exclude:
                continue
            p = self.world_model_dir / f"{name}.md"
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8").strip()
            if len(text) > per_doc_chars:
                text = text[:per_doc_chars] + f"\n... [truncated; read {p.name} in full]"
            parts.append(text)
        return "\n\n".join(parts)

    def doc_stamps(self) -> dict[Path, tuple[int, int]]:
        """Modification stamps for the induction tripwire: an induction pass that
        rewrote none of the documents looks exactly like one that worked, unless the
        stamps say otherwise. (mtime, size) rather than mtime alone: this tree lives
        on NFS whose timestamps quantize to whole seconds, so a rewrite landing in
        the stamp's own second would otherwise pass unseen."""
        return {p: (p.stat().st_mtime_ns, p.stat().st_size)
                for p in sorted(self.world_model_dir.glob("*.md"))}

    def docs_touched(self, before: dict[Path, tuple[int, int]]) -> int:
        touched = sum(1 for p, t in before.items()
                      if not p.exists()
                      or (p.stat().st_mtime_ns, p.stat().st_size) != t)
        touched += sum(1 for p in self.world_model_dir.glob("*.md") if p not in before)
        return touched

    # -- the ground-truth outcome channel (--outcome-feedback only) --------

    def append_outcome(self, q_idx: int, task: str, correct: bool) -> None:
        """Ground truth only. Everything here comes from the evaluator's grading, never
        from the model, which is what lets `discipline.apply_outcome` treat it as an
        arbiter. A no-op unless the run was started with outcome feedback on."""
        if not self.outcome_feedback:
            return
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"q": q_idx, "task": task,
                                "outcome": "correct" if correct else "incorrect"},
                               separators=(",", ":")) + "\n")

    # -- integrity ---------------------------------------------------------

    def snapshot_harness_files(self) -> dict[str, int]:
        return {
            rel: (self.root / rel).stat().st_size
            for rel in HARNESS_OWNED_FILES if (self.root / rel).exists()
        }

    def assert_harness_files_intact(self, before: dict[str, int]) -> list[str]:
        """Harness files only ever grow. A shrink means the agent rewrote the record it
        is supposed to be reasoning from, which invalidates every claim checked against
        it -- so this is reported, not silently repaired."""
        bad = []
        for rel, size in before.items():
            now = (self.root / rel).stat().st_size if (self.root / rel).exists() else 0
            if now < size:
                bad.append(f"{rel}: {size} -> {now} bytes")
        if bad:
            logger.error("[worldmodel] agent modified harness-owned files: %s", bad)
        return bad

    # -- reporting ---------------------------------------------------------

    def doc_sizes(self) -> dict[str, int]:
        return {p.name: p.stat().st_size
                for p in sorted(self.world_model_dir.glob("*.md"))}

    def audit(self) -> dict[str, Any]:
        return {
            "world_model_docs": self.doc_sizes(),
            "outcome_feedback": self.outcome_feedback,
        }
