"""Memory that outlives a task: the `carry` layer.

A run of the KiCad benchmark is 25 tasks in one application, each in a fresh workspace,
and the measured runs spent a median of 7 turns per task on the same preamble (dismiss
the first-run and update dialogs, create the project, find the save directory) and
relearned the same GUI lessons 25 times. Nothing in a per-task workspace can help with
that. This sink makes the finished tasks' records part of the next task's workspace:

    previous/<task_id>/       the complete record of every task finished before this one,
                              oldest first: logs.txt, frames/, episodes/, index.jsonl, and
                              whatever the model wrote there. Hard links, so no copies.
    previous/index.jsonl      one index over every episode of the finished tasks (paths
                              rewritten to previous/<task_id>/...), for the query tool's
                              --previous flag. Only when the tasks kept a store.
    notes/                    the model's own directory, copied in at task start and back
                              out at task end, so what it writes there persists.
    <carry root>/manifest.json  the tasks in order, with their record dirs and rewards.

The bwrap sandbox binds the task's workspace and nothing outside it, which is why the
carried material is linked and copied *into* the workspace rather than reached through
a symlink out of it. Single-writer: the tasks of a run execute in order at concurrency 1,
and `seed` and `register` are called by consecutive tasks. The protocol consequence --
task order is part of the arm and later tasks may benefit from earlier ones -- is the
point, and it is why this is a separate arm (`mfm-carry`) rather than a default.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mfm.memory import recall as R
from mfm.memory.consolidate import situations, to_markdown
from mfm.memory.sink import MemorySink
from mfm.memory.store import EpisodeStore

if TYPE_CHECKING:  # pragma: no cover
    from mfm.agent.base import MemoryAgent, Observation

#: Files of a finished task's record that are that task's own machinery, not history.
_NOT_CARRIED = frozenset({"previous", "notes", "tools", "AGENTS.md", "actions.json",
                          "last_message.txt", "workspace.codexhome"})

#: Under `consolidation=False`, the only parts of a finished task that are carried: the
#: record the harness wrote (the log with the model's briefings in it, the episodes,
#: their index and the screenshots), none of the files the model wrote for itself.
_RECORD_ONLY = frozenset({"logs.txt", "episodes", "index.jsonl", "frames"})

#: Image files, as the "without historical images" ablation sees them.
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"})

CARRY_NOTE = """\
This is one task of a sequence in the same application. `previous/<task>/` holds the \
complete record of every task finished before this one, oldest first: its `logs.txt`, \
the screenshots that log names (under `previous/<task>/frames/`), and whatever that task \
wrote in its workspace. They were different tasks, but the same program: the same \
dialogs, shortcuts, symbol chooser, wiring behaviour and save location. Grep them for \
how you did a thing before, before working it out again. `notes/` is yours and persists \
across tasks: read what is in `notes/` first, and before you finish write down what \
worked and what cost steps (recipes, stable coordinates, mistakes to avoid). \
{count}"""

CARRY_STORE_NOTE = """\
`previous/index.jsonl` indexes every episode of the finished tasks; \
`./tools/episodes.py --previous ...` queries it with the same flags, and \
`./tools/episodes.py --same-screen frames/<step>.png` (add `--previous` to search the \
earlier tasks) lists the turns that faced that exact screen and what they did next."""

CARRY_OUTCOMES_NOTE = """\
`previous/outcomes.md` is what the evaluator scored each finished task, with the task \
text: the mean of three exact comparisons of your saved netlist against a reference \
(the components with their values and library parts, the nets as sets of pins, and the \
net names), so 1.00 is all three and 0.00 is none. You are not told which check failed \
or what the reference held, and this task's score does not exist yet. It is the only \
outside word on whether what you believed at the end was true: a task you finished \
confident and scored 0.00 on means the belief was wrong, not that the task was hard. \
Read it with `notes/` before the first action, and when you write notes at the end, \
write down what the scores support and mark what you are only assuming."""

CARRY_RECALL_NOTE = """\
`previous/situations.md` is the finished tasks' turns folded by what you said you were \
looking at: for each recurring situation, the actions taken there, how often, and what \
each led to. Read it before the first action. When the situation and action of your \
last turn occurred in an earlier task, the turn prompt carries a `[RECALL]` block with \
what followed then, two steps ahead: if it matches what you intend, queue those steps \
as one plan instead of rediscovering them one screenshot at a time."""


def _edit(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"carry note drifted; cannot ablate: {old[:60]!r}"
    return text.replace(old, new)


def carry_note(*, images: bool = True, consolidation: bool = True) -> str:
    """CARRY_NOTE for this run's ablations (the full arm's when both are on); `{count}`
    stays a placeholder for `prompt_note`."""
    text = CARRY_NOTE
    if not images:
        text = _edit(text, "its `logs.txt`, the screenshots that log names (under "
                           "`previous/<task>/frames/`), and whatever",
                     "its `logs.txt` (no screenshot of an earlier task is kept in this run), "
                     "and whatever")
    if not consolidation:
        text = _edit(text, "and whatever that task wrote in its workspace.",
                     "and its episodes -- the record only: what that task wrote in its "
                     "workspace is not carried in this run.")
        text = _edit(text, "`notes/` is yours and persists across tasks: read what is in "
                           "`notes/` first, and before you finish write down what worked and "
                           "what cost steps (recipes, stable coordinates, mistakes to avoid). ",
                     "`notes/` does NOT persist across tasks in this run: every task starts "
                     "with it empty, and nothing you write in this task reaches the next one "
                     "except through this task's log. ")
    return text


def carry_outcomes_note(*, consolidation: bool = True) -> str:
    if consolidation:
        return CARRY_OUTCOMES_NOTE
    return _edit(CARRY_OUTCOMES_NOTE,
                 "Read it with `notes/` before the first action, and when you write notes at "
                 "the end, write down what the scores support and mark what you are only "
                 "assuming.", "Read it before the first action.")


#: Under flat retrieval: the merged index without the query tool.
CARRY_STORE_NOTE_FLAT = """\
`previous/index.jsonl` indexes every episode of the finished tasks, one JSON line each \
with its task and the same fields as `index.jsonl`; there is no query tool in this run: \
grep it the way you grep the logs."""

#: CARRY_RECALL_NOTE in its two parts: the situation table (consolidation) and the
#: [RECALL] block (structured retrieval). Each ablation removes its own part.
_SITUATIONS_PART, _RECALL_PART = CARRY_RECALL_NOTE.split("Read it before the first action. ")
_SITUATIONS_PART += "Read it before the first action."
assert CARRY_RECALL_NOTE == _SITUATIONS_PART + " " + _RECALL_PART


def carry_recall_note(*, push: bool = True, consolidation: bool = True) -> str:
    if push and consolidation:
        return CARRY_RECALL_NOTE
    if consolidation:
        return _SITUATIONS_PART
    if push:
        return _RECALL_PART[0].upper() + _RECALL_PART[1:]
    return ""


@dataclass(frozen=True)
class CarriedRecord:
    """One finished record to carry over: where it is now, what it is called under
    `previous/`, and the fields stamped on every index row it contributes.

    The two benchmarks name their records differently -- KiCad carries the tasks of one
    run (`previous/<task_id>/`, rows tagged `task`), MCU carries earlier runs of the same
    world (`previous/life_<i>/`, rows tagged `life`) -- and that naming is the protocol,
    so it is the caller's to decide and this layer's to respect.
    """
    name: str
    source: Path
    tag: dict[str, Any] = field(default_factory=dict)


@dataclass
class CarrySeed:
    """What seeding produced: the merged index rows and how much was linked."""
    rows: list[dict[str, Any]] = field(default_factory=list)
    linked: int = 0
    names: list[str] = field(default_factory=list)


#: Index-row fields that name a file inside the record; rewritten to the carried path so
#: `./tools/episodes.py --previous` and the recall block resolve them from the workspace.
_PATH_FIELDS = ("path", "image", "attachment")


def link_record(src: Path, dst: Path, *, skip: frozenset[str] = frozenset(),
                skip_hidden: bool = False, keep: frozenset[str] | None = None,
                images: bool = True) -> int:
    """Hard-link every file under `src` into `dst` (copy where linking fails).

    `skip` names top-level entries of the record that are its machinery rather than its
    history; `skip_hidden` drops top-level dotfiles as well (MCU's rule). Both apply at
    the top level only: a name of the record's own, deeper in, is history. `keep`, when
    given, is the only top-level names linked; `images=False` links no image file.
    Returns the number of files placed.
    """
    n = 0
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if rel.parts and (rel.parts[0] in skip
                          or (keep is not None and rel.parts[0] not in keep)
                          or (skip_hidden and rel.parts[0].startswith("."))):
            continue
        if not p.is_file():
            continue
        if not images and p.suffix.lower() in IMAGE_SUFFIXES:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        try:
            os.link(p, target)
        except OSError:
            shutil.copyfile(p, target)
        n += 1
    return n


def seed_previous(prev_dir: Path, records: "list[CarriedRecord]", *,
                  skip: frozenset[str] = frozenset(), skip_hidden: bool = False,
                  write_index: bool = True, keep: frozenset[str] | None = None,
                  images: bool = True) -> CarrySeed:
    """Link the finished records under `prev_dir` and merge their episode indexes.

    One `previous/index.jsonl` over every carried episode, each row stamped with its
    record's `tag` and its file fields rewritten to `previous/<name>/...`. This is the
    whole of what the carry layer does that both benchmarks do identically; what each
    reads OUT of the carried material -- MCU's verified sites and corridors, KiCad's
    outcome table and situation table -- is the caller's, and stays in its adapter.
    """
    seed = CarrySeed()
    for rec in records:
        if not rec.source.exists():
            continue
        seed.linked += link_record(rec.source, prev_dir / rec.name,
                                   skip=skip, skip_hidden=skip_hidden, keep=keep,
                                   images=images)
        seed.names.append(rec.name)
        idx = rec.source / "index.jsonl"
        if not idx.exists():
            continue
        for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            row.update(rec.tag)
            for key in _PATH_FIELDS:
                if row.get(key):
                    row[key] = f"previous/{rec.name}/{row[key]}"
            if not images:
                row["image"] = None                  # the frame was not carried
            seed.rows.append(row)
    if seed.rows and write_index:
        prev_dir.mkdir(parents=True, exist_ok=True)
        (prev_dir / "index.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in seed.rows),
            encoding="utf-8")
    return seed


class CarrySink(MemorySink):
    def __init__(self, root: Path | str, task_id: str, record_dir: Path | str,
                 outcomes: bool = False, images: bool = True, push: bool = True,
                 consolidation: bool = True, tool: bool | None = None) -> None:
        self.root = Path(root)
        self.task_id = str(task_id)
        self.record = Path(record_dir)
        # The outcome signal (`--carry-outcomes`): the finished tasks' scores, written
        # into the workspace as `previous/outcomes.md`. Off by default, because it is a
        # protocol decision and not a memory mechanism: without it the carried notes are
        # the model's own belief about what worked, never checked against anything.
        self.outcomes = bool(outcomes)
        # The KiCad ablations, one each, the same three switches as the store's:
        # `images=False` carries no screenshot of an earlier task; `push=False` puts no
        # [RECALL] / [SEEN BEFORE] line into a turn; `consolidation=False` carries only
        # the harness's record of an earlier task (_RECORD_ONLY), no `notes/` and no
        # situation table.
        self.images, self.push, self.consolidation = bool(images), bool(push), bool(consolidation)
        # Whether the store's query tool is there (the note on the carried index names
        # it); by default the push and the tool go together, as flat retrieval removes both.
        self.tool = self.push if tool is None else bool(tool)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "notes").mkdir(exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.seeded = 0            # files linked into previous/
        self.previous_rows: list[dict[str, Any]] = []
        self._seeded = False
        self._published = False

    # -- the manifest -----------------------------------------------------------------

    def manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def prior(self) -> list[dict[str, Any]]:
        return [m for m in self.manifest() if m.get("task_id") != self.task_id]

    # -- sink hooks -------------------------------------------------------------------

    def prompt_note(self, agent: "MemoryAgent") -> str | None:
        n = len(self.prior())
        count = (f"{n} task(s) are recorded under `previous/` now." if n
                 else "This is the first task of the sequence: `previous/` is empty and "
                      "`notes/` holds nothing yet." if self.consolidation
                 else "This is the first task of the sequence: `previous/` is empty.")
        note = carry_note(images=self.images, consolidation=self.consolidation).format(count=count)
        if self.outcomes and n:
            note += "\n\n" + carry_outcomes_note(consolidation=self.consolidation)
        store = self._store(agent)
        if store is not None:
            note += "\n\n" + (CARRY_STORE_NOTE if self.tool else CARRY_STORE_NOTE_FLAT)
            if store.recall:
                recall = carry_recall_note(push=self.push, consolidation=self.consolidation)
                if recall:
                    note += "\n\n" + recall
        return note

    @staticmethod
    def _store(agent: "MemoryAgent") -> EpisodeStore | None:
        return next((s for s in agent.sinks if isinstance(s, EpisodeStore)), None)

    def initial(self, agent: "MemoryAgent", obs: "Observation") -> None:
        self.seed()

    def seed(self) -> None:
        """Link the finished tasks' records in, copy the notes in, build the merged
        index. Idempotent."""
        if self._seeded:
            return
        self._seeded = True
        prev_dir = self.record / "previous"
        # One task of a run per carried record, named by its task id (`seed_previous`
        # links them and merges their indexes; the situation table below is this
        # benchmark's own reading of the merged rows).
        seed = seed_previous(
            prev_dir,
            [CarriedRecord(name=m["task_id"], source=Path(m["record_dir"]),
                           tag={"task": m["task_id"]})
             for m in self.prior()],
            skip=_NOT_CARRIED, keep=None if self.consolidation else _RECORD_ONLY,
            images=self.images)
        self.seeded += seed.linked
        rows = seed.rows
        if self.consolidation and rows and any(r.get("perception") for r in rows):
            # Consolidation: the episodic rows folded into the situation table.
            (prev_dir / "situations.md").write_text(to_markdown(situations(rows)),
                                                    encoding="utf-8")
        self.previous_rows = rows
        if self.outcomes:
            self._write_outcomes(prev_dir)
        notes_in = self.record / "notes"
        notes_in.mkdir(exist_ok=True)
        if not self.consolidation:
            return                                   # notes/ starts empty in every task
        for p in (self.root / "notes").rglob("*"):
            if p.is_file():
                target = notes_in / p.relative_to(self.root / "notes")
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(p, target)

    def _write_outcomes(self, prev_dir: Path) -> None:
        """`previous/outcomes.md`: each finished task's score with its task text.

        The score is the manifest's, recorded by `register` when that task closed. The
        task text is read back out of the carried log's `[TASK]` line, so a row says
        what was asked as well as what it came to.
        """
        prior = self.prior()
        if not prior:
            return
        lines = ["# How the finished tasks scored", "",
                 "The evaluator's score for each task finished before this one, oldest "
                 "first. 1.00 is every check matched; 0.00 is none of them. Which check "
                 "failed, and what the reference held, are not shown.", ""]
        for m in prior:
            task = ""
            log = prev_dir / m["task_id"] / "logs.txt"
            if log.exists():
                for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("[TASK]"):
                        task = line[len("[TASK]"):].strip()
                        break
            reward = m.get("reward")
            score = "not scored" if reward is None else f"{float(reward):.2f}"
            lines.append(f"## {m['task_id']} -- {score}")
            if m.get("error"):
                lines.append(f"(the run errored: {m['error']})")
            if task:
                lines.append(task)
            lines.append("")
        prev_dir.mkdir(parents=True, exist_ok=True)
        (prev_dir / "outcomes.md").write_text("\n".join(lines), encoding="utf-8")

    def turn_note(self, agent: "MemoryAgent", obs: "Observation") -> str | None:
        """Across tasks: the model does not pull, so the harness pushes. With the
        store's recall on, the earlier tasks' turns that repeated the previous turn's
        transition (mfm.memory.recall); otherwise the exact-hash seen-before line."""
        if not self.push:
            return None
        store = self._store(agent)
        if store is not None and store.recall:
            if not self.previous_rows:
                return None
            prev = store.previous_row(obs)
            return R.recall_note(self.previous_rows, prev, store._dhash(obs.attachment),
                                 "in an earlier task")
        digest = (obs.state or {}).get("png_hash")
        if not digest or not self.previous_rows:
            return None
        hits = [r for r in self.previous_rows
                if r.get("observation_hash") == digest and r.get("kind") != "initial"]
        if not hits:
            return None
        lines = [f"previous/{r['task']} step {r.get('first_step')}: {r.get('action_kind') or '-'}"
                 + (f" -> {r['summary']}" if r.get("summary") else "")
                 + (f" [{','.join(r['tags'])}]" if r.get("tags") else "")
                 for r in hits[-3:]]
        return ("[SEEN BEFORE] this exact screen appeared in earlier tasks: "
                + "; ".join(lines) + ".")

    def close(self, agent: "MemoryAgent", **outcome: Any) -> None:
        self.register(reward=outcome.get("reward"), error=outcome.get("error"))

    def register(self, reward: Any = None, error: Any = None) -> None:
        """Register this task in the manifest and copy its notes back out. Idempotent.
        (Not `publish`: that name is the sink protocol's ablation-view hook.)"""
        if self._published:
            return
        self._published = True
        notes_out = self.root / "notes"
        notes_in = self.record / "notes"
        if notes_in.exists() and self.consolidation:
            for p in notes_in.rglob("*"):
                if p.is_file():
                    target = notes_out / p.relative_to(notes_in)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(p, target)
        rows = [m for m in self.manifest() if m.get("task_id") != self.task_id]
        rows.append({"task_id": self.task_id, "record_dir": str(self.record),
                     "reward": reward, "error": error})
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        os.replace(tmp, self.manifest_path)

    def audit(self) -> dict[str, Any]:
        out = {"previous_tasks": len(self.prior()), "files_linked": self.seeded,
               "previous_episodes": len(self.previous_rows),
               "notes_files": sum(1 for p in (self.root / "notes").rglob("*") if p.is_file())}
        if self.consolidation and any(r.get("perception") for r in self.previous_rows):
            out["situations"] = sum(1 for g in situations(self.previous_rows) if g["n"] >= 2)
        if self.outcomes:
            # Only when the arm has it: the audit keys of an arm that does not carry
            # outcomes must not move (tests/test_carry.py pins them).
            out["outcomes"] = True
        ablations = ([] if self.images else ["no_history_images"]) \
            + ([] if self.push else ["flat_retrieval" if not self.tool else "no_recall"]) \
            + ([] if self.consolidation else ["no_consolidation"])
        if ablations:
            out["ablations"] = ablations
        return out
