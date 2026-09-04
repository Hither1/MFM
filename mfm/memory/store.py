"""The episode store: the log's history a second time, structured, one directory per
decision, written from the same call sites.

    episodes/
      ep_000042/
        observation/image.png     hard link to the frame the decision was made from
        observation/crops/        zoom outputs; append-only, the agent's
        state/state.json          structured state at the entry's first tick
        state/ticks.jsonl         one line per tick observed while the entry ran
        action.json               the entry, its place in the plan, the turn, the plan text
        outcome.json              what the entry changed, notes, tags (on close)
    index.jsonl                   one line per closed episode
    tools/episodes.py             the query CLI

An episode is one plan entry (MCU: `{"action", "repeat"}`; KiCad: one batch). It opens
when the entry's first tick is popped from the queue, takes a tick line for every
observation while it runs, and closes on the observation after its last tick -- or
early, as `flushed`, when the plan is dropped, or at the end of the episode. `ep_000000`
is the initial state, closed at once, with no action.

What is Minecraft or KiCad about the contents comes from the agent's hooks
(`episode_state`, `episode_action`, `episode_outcome`); the store knows only the layout.
Everything under `episodes/*/` except `observation/crops/` is harness-written and
immutable once closed; writes are atomic (`.tmp` + `replace`).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mfm.memory.sink import MemorySink

if TYPE_CHECKING:  # pragma: no cover
    from mfm.agent.base import MemoryAgent, Observation, Plan

logger = logging.getLogger(__name__)

_TOOL_SRC = Path(__file__).with_name("tools") / "episodes.py"


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


class EpisodeStore(MemorySink):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.dir = self.root / "episodes"
        self.index_path = self.root / "index.jsonl"
        self.dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(p.name for p in self.dir.glob("ep_*") if p.is_dir())
        self._next_id = (int(existing[-1][3:]) + 1) if existing else 0
        self._open: dict[str, Any] | None = None
        self._pending_notes: list[str] = []
        self._plan: dict[str, Any] = {}
        self.n_closed = 0
        self.tags: Counter[str] = Counter()
        self.closed: list[dict[str, Any]] = []
        self._write_tool()

    def _write_tool(self) -> None:
        dst = self.root / "tools" / "episodes.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copyfile(_TOOL_SRC, dst)
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # -- sink hooks -----------------------------------------------------------

    def prompt_note(self, agent: "MemoryAgent") -> str | None:
        return getattr(agent, "mfm_memory_note", None)

    def initial(self, agent: "MemoryAgent", obs: "Observation") -> None:
        state = agent.episode_state(obs)
        ep = self._new_episode(agent, obs, state, kind="initial")
        self._open = ep
        self._close(agent, flushed=False, last_step=obs.step)

    def observe(self, agent: "MemoryAgent", obs: "Observation") -> None:
        ep = self._open
        if ep is None:
            return
        state = agent.episode_state(obs)
        with (ep["dir"] / "state" / "ticks.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(state, sort_keys=True, default=str) + "\n")
        ep["last_state"] = state
        ep["last_step"] = obs.step
        ep["ticks_seen"] += 1
        if ep["ticks_seen"] >= ep["ticks"]:
            self._close(agent, flushed=False, last_step=obs.step)

    def plan(self, agent: "MemoryAgent", plan: "Plan") -> None:
        self._plan = {"turn": agent.codex.calls, "briefing": plan.briefing, "plan": plan.think}

    def act(self, agent: "MemoryAgent", item: dict[str, Any]) -> None:
        if item.get("tick", 1) != 1:
            return
        obs = agent._obs
        assert obs is not None
        if self._open is not None:
            # The previous entry did not run to its last tick: the plan was flushed.
            self._close(agent, flushed=True, last_step=obs.step)
        state = agent.episode_state(obs)
        ep = self._new_episode(agent, obs, state, kind="episode", item=item)
        self._open = ep

    def note(self, agent: "MemoryAgent", text: str) -> None:
        if self._open is not None:
            self._open["notes"].append(text)
        else:
            self._pending_notes.append(text)

    def close(self, agent: "MemoryAgent", **outcome: Any) -> None:
        if self._open is not None:
            self._close(agent, flushed=False, last_step=self._open["last_step"], extra=outcome)

    def publish(self, agent: "MemoryAgent", visible: Path, window: int | None,
                stateless: bool, current: str | None) -> None:
        """Mirror the log's ablation rule onto `episodes/`: everything under a full
        log, nothing under stateless or the no-log control, and under a window only
        the episodes whose last step is inside it (a window of N sections is N ticks
        in MCU and N turns in KiCad, and an episode's `last_step` is in those units)."""
        if Path(visible) == self.root:
            return
        vis_dir = Path(visible) / "episodes"
        if stateless or window == -1:
            shutil.rmtree(vis_dir, ignore_errors=True)
            (Path(visible) / "index.jsonl").unlink(missing_ok=True)
            return
        step_now = agent._obs.step if agent._obs is not None else 0
        keep = [r for r in self.closed
                if window is None or (r.get("last_step") or 0) >= step_now - window]
        keep_ids = {r["id"] for r in keep}
        for r in self.closed:
            src, dst = self.dir / r["id"], vis_dir / r["id"]
            if r["id"] in keep_ids:
                if not dst.exists():
                    for p in src.rglob("*"):
                        if p.is_file():
                            _link(p, dst / p.relative_to(src))
            elif dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
        (Path(visible) / "index.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in keep), encoding="utf-8")
        _link(self.root / "tools" / "episodes.py", Path(visible) / "tools" / "episodes.py")

    def audit(self, agent: "MemoryAgent") -> dict[str, Any]:
        return {"n": self.n_closed, "tags": dict(self.tags),
                "episodes_tool_calls": getattr(agent.codex, "episodes_tool_calls", None)}

    # -- mechanics ---------------------------------------------------------------

    def _new_episode(self, agent: "MemoryAgent", obs: "Observation", state: dict[str, Any],
                     *, kind: str, item: dict[str, Any] | None = None) -> dict[str, Any]:
        ep_id = f"ep_{self._next_id:06d}"
        self._next_id += 1
        d = self.dir / ep_id
        (d / "observation" / "crops").mkdir(parents=True, exist_ok=True)
        (d / "state").mkdir(parents=True, exist_ok=True)
        if obs.attachment and (self.root / obs.attachment).exists():
            _link(self.root / obs.attachment, d / "observation" / "image.png")
        _write_json(d / "state" / "state.json", state)
        ticks = 1
        entry = None
        action_kind = None
        if item is not None:
            ticks = int(item.get("ticks", 1))
            entry = item["entry"]
            action_kind = agent.episode_action_kind(item)
            action = {
                "turn": self._plan.get("turn"),
                "plan_index": item.get("entry_index"),
                "plan_total": item.get("entries_total"),
                "entry": agent.episode_action(item),
                "ticks": ticks,
                "first_step": obs.step,
            }
            if item.get("entry_index") == 1:
                action["briefing"] = self._plan.get("briefing", "")
                action["plan"] = self._plan.get("plan", "")
            _write_json(d / "action.json", action)
        notes = list(self._pending_notes)
        self._pending_notes.clear()
        return {"id": ep_id, "dir": d, "kind": kind, "entry": entry, "item": item,
                "action_kind": action_kind, "ticks": ticks, "ticks_seen": 0,
                "first_step": obs.step, "last_step": obs.step, "first_state": state,
                "last_state": state, "notes": notes,
                "image": (d / "observation" / "image.png").relative_to(self.root).as_posix()
                         if (d / "observation" / "image.png").exists() else None,
                "observation_hash": state.get("png_sha256")}

    def _close(self, agent: "MemoryAgent", *, flushed: bool, last_step: int,
               extra: dict[str, Any] | None = None) -> None:
        ep = self._open
        assert ep is not None
        self._open = None
        if ep["kind"] == "initial":
            outcome, tags, summary = {}, ["initial"], "initial state"
        else:
            outcome, tags, summary = agent.episode_outcome(
                ep["entry"], ep["first_state"], ep["last_state"], ep["notes"], flushed)
            tags = list(tags)
            if ep["notes"] and "note" not in tags:
                tags.append("note")
            if flushed:
                tags.append("flushed")
        record = {"last_step": last_step, **outcome, "notes": ep["notes"],
                  "flushed": flushed, "tags": tags, **(extra or {})}
        _write_json(ep["dir"] / "outcome.json", record)
        row = {"id": ep["id"], "kind": ep["kind"], "first_step": ep["first_step"],
               "last_step": last_step, "tags": tags, "summary": summary,
               "image": ep["image"], "path": ep["dir"].relative_to(self.root).as_posix(),
               "action_kind": ep["action_kind"],
               "observation_hash": ep["observation_hash"],
               **agent.episode_index_fields(ep["first_state"], ep["last_state"])}
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        self.closed.append(row)
        self.n_closed += 1
        self.tags.update(tags)
