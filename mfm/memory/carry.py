"""Memory that outlives a task: the `carry` layer of PLAN_episodic_memory.md section 5.

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
point, and it is why this is a separate arm (`*-carry`) rather than a default.

Every arm on the carry rung gets the same carried material; what differs between
`prolong-carry` and `mfm-carry` is only what the MFM store adds on top (the merged index,
the query tool and the seen-before line), so the ladder isolates the structure from the
mere existence of carry-over.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mfm.memory.sink import MemorySink

if TYPE_CHECKING:  # pragma: no cover
    from mfm.agent.base import MemoryAgent, Observation

#: Files of a finished task's record that are that task's own machinery, not history.
_NOT_CARRIED = frozenset({"previous", "notes", "tools", "AGENTS.md", "actions.json",
                          "last_message.txt", "workspace.codexhome"})

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


def _link_tree(src: Path, dst: Path, skip: frozenset[str] = frozenset()) -> int:
    """Hard-link every file under `src` into `dst` (copy where linking fails)."""
    n = 0
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if rel.parts and rel.parts[0] in skip:
            continue
        if not p.is_file():
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


class CarrySink(MemorySink):
    def __init__(self, root: Path | str, task_id: str, record_dir: Path | str) -> None:
        self.root = Path(root)
        self.task_id = str(task_id)
        self.record = Path(record_dir)
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
                      "`notes/` holds nothing yet.")
        note = CARRY_NOTE.format(count=count)
        if any(s is not self and hasattr(s, "closed") for s in agent.sinks):
            note += "\n\n" + CARRY_STORE_NOTE
        return note

    def initial(self, agent: "MemoryAgent", obs: "Observation") -> None:
        self.seed()

    def seed(self) -> None:
        """Link the finished tasks' records in, copy the notes in, build the merged
        index. Idempotent."""
        if self._seeded:
            return
        self._seeded = True
        prev_dir = self.record / "previous"
        rows: list[dict[str, Any]] = []
        for m in self.prior():
            src = Path(m["record_dir"])
            if not src.exists():
                continue
            dst = prev_dir / m["task_id"]
            self.seeded += _link_tree(src, dst, skip=_NOT_CARRIED)
            idx = src / "index.jsonl"
            if idx.exists():
                for line in idx.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    r["task"] = m["task_id"]
                    for key in ("path", "image", "attachment"):
                        if r.get(key):
                            r[key] = f"previous/{m['task_id']}/{r[key]}"
                    rows.append(r)
        if rows:
            prev_dir.mkdir(parents=True, exist_ok=True)
            (prev_dir / "index.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        self.previous_rows = rows
        notes_in = self.record / "notes"
        notes_in.mkdir(exist_ok=True)
        for p in (self.root / "notes").rglob("*"):
            if p.is_file():
                target = notes_in / p.relative_to(self.root / "notes")
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(p, target)

    def turn_note(self, agent: "MemoryAgent", obs: "Observation") -> str | None:
        """The seen-before line across tasks: the model does not pull, so the harness
        pushes the one fact the store can establish for free."""
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
        if notes_in.exists():
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
        return {"previous_tasks": len(self.prior()), "files_linked": self.seeded,
                "previous_episodes": len(self.previous_rows),
                "notes_files": sum(1 for p in (self.root / "notes").rglob("*") if p.is_file())}
