"""The episode store: the log's history a second time, structured, one directory per
decision, written from the same call sites.

    episodes/
      ep_000042/
        observation/image.png     hard link to the frame the decision was made from
        state/state.json          structured state at the entry's first tick
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
Everything under `episodes/*/` is harness-written and immutable once closed; writes
are atomic (`.tmp` + `replace`). (An `observation/crops/` the model could write zoom
outputs into was part of the layout: 805 of them across every MCU and
KiCad run, all empty.)
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from mfm.memory import recall as R
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
    """`recall=True` (the KiCad MFM arms) adds to every row what the
    model said it saw (`perception`), meant (`intent`) and caused (`effect`, filled in
    from the next turn's perception), plus perceptual hashes of the frame the turn was
    decided on and the frame it closed on; and replaces the exact-hash "seen before"
    line with the transition recall of `mfm.memory.recall`. Off, the store is
    byte-identical to what the MCU ladder runs on."""

    def __init__(self, root: Path | str, *, recall: bool = False) -> None:
        self.root = Path(root)
        self.recall = recall
        self._dhash_at: dict[str, str | None] = {}
        self.dir = self.root / "episodes"
        self.index_path = self.root / "index.jsonl"
        self.dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(p.name for p in self.dir.glob("ep_*") if p.is_dir())
        self._next_id = (int(existing[-1][3:]) + 1) if existing else 0
        self._open: dict[str, Any] | None = None
        self._pending_notes: list[str] = []
        self._plan: dict[str, Any] = {}
        # The state computed for the current step, shared by `observe` and `act`: the
        # hooks that compute it keep per-tick state (the previous position for `moved`),
        # so computing it twice for one observation read moved=0.0 in every state.json.
        self._state_at: tuple[int, dict[str, Any]] | None = None
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

    def _state(self, agent: "MemoryAgent", obs: "Observation") -> dict[str, Any]:
        if self._state_at is None or self._state_at[0] != obs.step:
            self._state_at = (obs.step, agent.episode_state(obs))
        return self._state_at[1]

    def initial(self, agent: "MemoryAgent", obs: "Observation") -> None:
        state = self._state(agent, obs)
        ep = self._new_episode(agent, obs, state, kind="initial")
        self._open = ep
        self._close(agent, flushed=False, last_step=obs.step)

    def observe(self, agent: "MemoryAgent", obs: "Observation") -> None:
        ep = self._open
        if ep is None:
            return
        # The entry's running state is kept in memory for the outcome; a per-tick
        # `state/ticks.jsonl` was written (12k lines a run) and
        # nothing -- model, recall block, CLI -- ever read one.
        state = self._state(agent, obs)
        ep["last_state"] = state
        ep["last_step"] = obs.step
        ep["ticks_seen"] += 1
        if ep["ticks_seen"] >= ep["ticks"]:
            self._close(agent, flushed=False, last_step=obs.step, closing=obs.attachment)

    def refill(self, agent: "MemoryAgent", obs: "Observation") -> None:
        if self._open is not None:
            # Closed here, at the step the turn runs on, rather than when the next entry
            # opens: the ticks between (a failed turn's default actions) are not its.
            self._close(agent, flushed=True, last_step=obs.step, closing=obs.attachment)

    def plan(self, agent: "MemoryAgent", plan: "Plan") -> None:
        self._plan = {"turn": agent.codex.calls, "briefing": plan.briefing, "plan": plan.think}
        if self.recall:
            perception, intent = R.perception_and_intent(plan.think)
            self._plan["perception"], self._plan["intent"] = perception, intent
            self._link_effect(agent, perception)

    def _link_effect(self, agent: "MemoryAgent", perception: str) -> None:
        """The lossless link the index lacked: the episode that closed on the frame
        this turn was decided on gets this turn's perception as its `effect`."""
        obs = agent._obs
        if not perception or obs is None or not self.closed:
            return
        row = self.closed[-1]
        if row.get("kind") != "episode" or row.get("effect") or row.get("last_step") != obs.step:
            return
        row["effect"] = perception
        self._rewrite_index()

    def _rewrite_index(self) -> None:
        tmp = self.index_path.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n" for r in self.closed),
                       encoding="utf-8")
        os.replace(tmp, self.index_path)

    def _dhash(self, attachment: str | None) -> str | None:
        if not self.recall or not attachment or Path(attachment).is_absolute():
            return None
        if attachment not in self._dhash_at:
            self._dhash_at[attachment] = R.dhash_file(self.root / attachment)
            if len(self._dhash_at) > 64:
                for k in list(self._dhash_at)[:-32]:
                    del self._dhash_at[k]
        return self._dhash_at[attachment]

    def previous_row(self, obs: "Observation") -> dict[str, Any] | None:
        """The episode that just closed on this observation: the previous turn."""
        if not self.closed:
            return None
        row = self.closed[-1]
        if row.get("kind") == "episode" and row.get("last_step") == obs.step:
            return row
        return None

    def act(self, agent: "MemoryAgent", item: dict[str, Any]) -> None:
        if item.get("tick", 1) != 1:
            return
        obs = agent._obs
        assert obs is not None
        if self._open is not None:
            # The previous entry did not run to its last tick: the plan was flushed.
            self._close(agent, flushed=True, last_step=obs.step, closing=obs.attachment)
        state = self._state(agent, obs)
        ep = self._new_episode(agent, obs, state, kind="episode", item=item)
        self._open = ep

    def turn_note(self, agent: "MemoryAgent", obs: "Observation") -> str | None:
        """Within this task: the earlier turns that faced this exact screen, or (recall
        on) the earlier turns that repeated the previous turn's transition."""
        if self.recall:
            prev = self.previous_row(obs)
            rows = [r for r in self.closed if r is not prev]
            return R.recall_note(rows, prev, self._dhash(obs.attachment), "in this task")
        digest = (obs.state or {}).get("png_hash")
        if not digest:
            return None
        hits = [r for r in self.closed
                if r.get("observation_hash") == digest and r.get("kind") != "initial"
                and (r.get("first_step") or 0) < obs.step]
        if not hits:
            return None
        lines = [f"step {r.get('first_step')}: {r.get('action_kind') or '-'}"
                 + (f" -> {r['summary']}" if r.get("summary") else "")
                 + (f" [{','.join(r['tags'])}]" if r.get("tags") else "")
                 for r in hits[-3:]]
        return ("[SEEN BEFORE] this exact screen appeared earlier in this task: "
                + "; ".join(lines) + ".")

    def note(self, agent: "MemoryAgent", text: str) -> None:
        if self._open is not None:
            self._open["notes"].append(text)
        else:
            self._pending_notes.append(text)

    def close(self, agent: "MemoryAgent", *, tags: Iterable[str] = (), **outcome: Any) -> None:
        """`tags`: extra tags the adapter derives from what it alone can see (MCU: `broke`
        from the tick's block events -- an ore broken and not yet picked up changes no
        inventory, and one run refused the entry that broke it as "changed nothing")."""
        if self._open is not None:
            self._close(agent, flushed=False, last_step=self._open["last_step"], extra=outcome,
                        extra_tags=tuple(tags))

    def publish(self, agent: "MemoryAgent", visible: Path) -> None:
        """Mirror the record's episodes, index and tool into a view of it."""
        if Path(visible) == self.root:
            return
        vis_dir = Path(visible) / "episodes"
        for r in self.closed:
            src, dst = self.dir / r["id"], vis_dir / r["id"]
            if not dst.exists():
                for p in src.rglob("*"):
                    if p.is_file():
                        _link(p, dst / p.relative_to(src))
        (Path(visible) / "index.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in self.closed), encoding="utf-8")
        if (self.root / "tools" / "episodes.py").exists():
            _link(self.root / "tools" / "episodes.py", Path(visible) / "tools" / "episodes.py")

    def audit(self, agent: "MemoryAgent") -> dict[str, Any]:
        out = {"n": self.n_closed, "tags": dict(self.tags),
               "episodes_tool_calls": getattr(agent.codex, "episodes_tool_calls", None)}
        if self.recall:
            reps = R.repeated_transitions(self.closed)
            out["recall"] = {"effects_linked": sum(1 for r in self.closed if r.get("effect")),
                             "repeated_transitions": sum(c - 1 for c in reps.values() if c > 1)}
        return out

    # -- mechanics ---------------------------------------------------------------

    def _new_episode(self, agent: "MemoryAgent", obs: "Observation", state: dict[str, Any],
                     *, kind: str, item: dict[str, Any] | None = None) -> dict[str, Any]:
        ep_id = f"ep_{self._next_id:06d}"
        self._next_id += 1
        d = self.dir / ep_id
        (d / "observation").mkdir(parents=True, exist_ok=True)
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
                "observation_hash": state.get("png_sha256"),
                # The log-relative frame the episode opened on (what `publish` keys on);
                # an absolute path is a caller's scratch file, not a name in the log.
                "attachment": (obs.attachment if obs.attachment
                               and not Path(obs.attachment).is_absolute() else None),
                "perception": self._plan.get("perception") if (self.recall and item is not None) else None,
                "intent": self._plan.get("intent") if (self.recall and item is not None) else None,
                "dhash": self._dhash(obs.attachment) if item is not None else None}

    def _close(self, agent: "MemoryAgent", *, flushed: bool, last_step: int,
               extra: dict[str, Any] | None = None, closing: str | None = None,
               extra_tags: tuple[str, ...] = ()) -> None:
        """`closing`: the frame the episode closes on (the observation after its last
        tick), hashed as `next_dhash` under recall. `agent._obs` is not yet that
        observation when `observe` runs, which is why it is passed in."""
        ep = self._open
        assert ep is not None
        self._open = None
        if ep["kind"] == "initial":
            outcome, tags, summary = {}, ["initial"], "initial state"
        else:
            outcome, tags, summary = agent.episode_outcome(
                ep["entry"], ep["first_state"], ep["last_state"], ep["notes"], flushed)
            tags = list(tags)
            for t in extra_tags:
                if t not in tags:
                    tags.append(t)
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
               "attachment": ep["attachment"],
               **agent.episode_index_fields(ep["first_state"], ep["last_state"])}
        if self.recall:
            row.update({"perception": ep.get("perception"), "intent": ep.get("intent"),
                        "effect": None, "dhash": ep.get("dhash"),
                        "next_dhash": self._dhash(closing) if ep["kind"] == "episode" else None})
        # What the query tool asks of `outcome.json` most, kept in the row so `--grep`
        # and `--ores` read the index alone: opening every episode's outcome.json cost
        # ~40 ms a file on the shared storage, 85-120 s over a 2,800-episode life,
        # longer than a turn.
        if ep["notes"]:
            row["note"] = " ".join(str(ep["notes"][0]).split())[:220]
        events = (extra or {}).get("events") or outcome.get("events") or []
        row["events"] = [str(e) for e in events][:12]
        delta = outcome.get("inventory_delta")
        if isinstance(delta, dict) and delta:
            row["inventory_delta"] = dict(list(delta.items())[:12])
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        self.closed.append(row)
        self.n_closed += 1
        self.tags.update(tags)
