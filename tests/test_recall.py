"""Recall and consolidation: the effect link, the transition match, the [RECALL] block
pushed into the turn prompt within and across tasks, and the situation table."""
from __future__ import annotations

import json
from pathlib import Path

import test_pins_replay as R
from mfm.memory import recall as rc
from mfm.memory.consolidate import situations, to_markdown


# -- pure functions ---------------------------------------------------------------

def test_norm_text_abstracts_refs_numbers_and_filler():
    a = rc.norm_text("R2’s properties are open as expected, no feedback errors.")
    b = rc.norm_text("C4's properties are open; no feedback errors were reported.")
    assert a == b == "ref properties"
    assert rc.norm_text("The symbol chooser is open with its search field focused.") == \
        rc.norm_text("The symbol chooser is now open, with its search field focused; no errors appear.")
    assert rc.norm_text("") == ""


def test_norm_action_keeps_keys_and_drops_coordinates_and_typed_text():
    assert rc.norm_action("click(697,830); mouse_move(550,440)") == "click(n,n);mouse_move(n,n)"
    assert rc.norm_action('type("NE555P")') == rc.norm_action('type("LM358")') == "type(text)"
    assert rc.norm_action("key(ctrl+s)") != rc.norm_action("key(a)")


def test_dhash_and_hamming(tmp_path):
    from PIL import Image
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (64, 64), (255, 255, 255)).save(a)
    im = Image.new("L", (64, 64))
    for x in range(64):                       # a falling gradient: every neighbour differs
        for y in range(64):
            im.putpixel((x, y), 255 - x * 4)
    im.save(b)
    ha, hb = rc.dhash_file(a), rc.dhash_file(b)
    assert len(ha) == 16 and rc.hamming(ha, ha) == 0
    assert rc.hamming(ha, hb) is not None and rc.hamming(ha, hb) > rc.SAME_SCREEN_BITS
    assert rc.dhash_file(tmp_path / "missing.png") is None
    assert rc.hamming(None, ha) is None


def _row(i, task, perception, summary, effect, dhash="0" * 16, next_dhash="0" * 16):
    return {"id": f"ep_{i:06d}", "kind": "episode", "task": task, "first_step": i,
            "last_step": i + 1, "perception": perception, "summary": summary,
            "effect": effect, "dhash": dhash, "next_dhash": next_dhash, "tags": []}


def test_match_prefers_the_transition_and_checks_the_next_frame():
    rows = [_row(1, "A", "The symbol chooser is open.", 'type("R")', "Results list R.", next_dhash="0" * 16),
            _row(2, "A", "Results list R.", "click(300,400)", "R placed on canvas."),
            _row(1, "B", "The symbol chooser is open.", 'type("C")', "Results list C.", next_dhash="f" * 16)]
    prev = {"kind": "episode", "perception": "The symbol chooser is open.", "summary": 'type("LED")'}
    kind, hits = rc.match(rows, prev, cur_dhash="0" * 16)
    assert kind == "transition" and [r["task"] for r in hits] == ["A"]      # B's next frame differs
    kind, hits = rc.match(rows, prev, cur_dhash=None)
    assert kind == "transition" and [r["task"] for r in hits] == ["B", "A"]  # no image check: both, newest first
    note = rc.render(kind, hits, rows, "in an earlier task")
    assert note.startswith("[RECALL]") and 'previous/A step 1: at "The symbol chooser is open." you did type("R")' in note
    assert '-> "Results list R."; then click(300,400) -> "R placed on canvas."' in note
    # Image-only fallback when the transition is new.
    kind, hits = rc.match(rows, {"kind": "episode", "perception": "Never seen", "summary": "key(x)"}, "0" * 16)
    assert kind == "screen" and len(hits) == 3
    assert rc.match(rows, None, "f" * 15 + "0") == ("", [])


def test_situations_table_and_markdown():
    rows = [_row(1, "A", "The symbol chooser is open.", 'type("R")', "The results list shows the part."),
            _row(1, "B", "The symbol chooser is open, as expected.", 'type("C")', "The results list shows the part, as expected."),
            _row(2, "B", "R1's value reads 1k.", "click(758,789)", "Dialog closed.")]
    rows[1]["tags"] = ["screen_unchanged"]
    table = situations(rows)
    assert table[0]["key"] == "symbol chooser" and table[0]["n"] == 2 and table[0]["tasks"] == ["A", "B"]
    act = table[0]["actions"][0]
    assert act["key"] == "type(text)" and act["n"] == 2 and act["unchanged"] == 1
    assert {e["n"] for e in act["effects"]} == {2}          # both effects normalize alike
    md = to_markdown(table)
    assert '## "The symbol chooser is open."  (2 turns, 2 task(s))' in md
    assert "`type(\"R\")` x2, screen unchanged 1x ->" in md
    assert "value reads" not in md                            # seen once: below min_n


# -- through the KiCad MFM arms ---------------------------------------------------

def _agent(tmp_path: Path, kind: str, task: str, monkeypatch, **extra):
    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    task_dir = tmp_path / "out" / task
    kw = dict(workspace=task_dir / "workspace", model="gpt-5.6-sol", effort="low",
              max_steps=12, transcript_dir=None, codex_home=str(tmp_path / "home"),
              session_turns=None, base_url=None)
    if kind.endswith("-carry"):
        kw.update(carry_dir=tmp_path / "out" / "carry", task_id=task)
    return memory_agents.make_agent(kind, **kw, **extra), task_dir / "workspace"


def _drive(agent, fake_codex, script, frames):
    """`script`: (batch, message) per call; `frames`: bytes per step (a repeated frame
    means the same screen)."""
    for batch, message in script:
        fake_codex.reply(batch, message)
    outputs = []
    for step, png in enumerate(frames):
        message, calls, done = agent.predict("Place two resistors.", png, step, len(frames))
        outputs.append((message, calls, done))
        if done:
            break
    return outputs


def _png(k: int) -> bytes:
    """A real PNG (the store hashes it), distinct per k: seeded noise, so two frames
    differ by ~half their hash bits and a repeated k is the same bytes."""
    import random
    from io import BytesIO
    from PIL import Image
    rnd = random.Random(k)
    im = Image.new("L", (32, 32))
    im.putdata([rnd.randrange(256) for _ in range(32 * 32)])
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


CLICK = {"actions": [{"action": "click", "coordinate": [100, 100]}]}
TYPE_R = {"actions": [{"action": "type", "text": "R"}]}
TYPE_C = {"actions": [{"action": "type", "text": "C"}]}
KEY_A = {"actions": [{"action": "key", "keys": ["a"]}]}
END = {"terminate": {"status": "success", "reason": "done"}}

SCRIPT_A = [
    (KEY_A, "The blank schematic is open.\n[PLAN]\nOpen the chooser."),
    (TYPE_R, "The symbol chooser is open with its search field focused.\n[PLAN]\nSearch R."),
    (CLICK, "The results list shows Device:R.\n[PLAN]\nPlace it."),
    (KEY_A, "R1 sits on the canvas.\n[PLAN]\nOpen the chooser again."),
    (TYPE_C, "The symbol chooser is open with its search field focused.\n[PLAN]\nSearch C."),
    (END, "The results list shows Device:C.\n[PLAN]\nDone."),
]
FRAMES_A = [_png(0), _png(1), _png(2), _png(3), _png(1), _png(2)]


def test_recall_within_a_task_links_effects_and_pushes_the_chain(tmp_path, fake_codex, monkeypatch):
    agent, ws = _agent(tmp_path, "mfm", "A", monkeypatch)
    _drive(agent, fake_codex, SCRIPT_A, FRAMES_A)
    agent.finish(1.0, None)
    rows = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines() if l]
    eps = [r for r in rows if r["kind"] == "episode"]
    assert [r["perception"] for r in eps][:3] == ["The blank schematic is open.",
                                                  "The symbol chooser is open with its search field focused.",
                                                  "The results list shows Device:R."]
    assert [r["effect"] for r in eps][:3] == ["The symbol chooser is open with its search field focused.",
                                              "The results list shows Device:R.", "R1 sits on the canvas."]
    assert all(r["dhash"] and r["next_dhash"] for r in eps[:4])
    assert eps[0]["intent"] == "Open the chooser."
    # Turn 5 (screen = the chooser again, after key(a) at "R1 sits on the canvas"): no
    # earlier transition matches ("blank schematic" != "R1 sits"), but the frame is the
    # chooser frame of turn 2 -> the image fallback. Turn 6: "chooser + type" recurred
    # (turn 2 -> results), and the frame matches -> the transition chain.
    prompts = [c["prompt"] for c in json.loads(R._dump_calls(fake_codex, tmp_path))]
    assert "[RECALL]" not in prompts[1]
    assert "[RECALL] a screen near-identical to this one occurred before in this task" in prompts[4]
    assert "[RECALL] the last turn's situation and action occurred before in this task" in prompts[5]
    assert 'step 2: at "The symbol chooser is open with its search field focused." you did type("R") -> "The results list shows Device:R."; then click(100,100) -> "R1 sits on the canvas."' in prompts[5]
    audit = agent.audit()["mfm"]
    assert audit["recall"] == {"effects_linked": 5, "repeated_transitions": 1}
    assert "RECALL" in (ws / "AGENTS.md").read_text()


def test_recall_across_tasks_and_the_situation_table(tmp_path, fake_codex, monkeypatch):
    a, ws_a = _agent(tmp_path, "mfm-carry", "A", monkeypatch)
    _drive(a, fake_codex, SCRIPT_A, FRAMES_A)
    a.finish(1.0, None)
    script_b = [
        (KEY_A, "The blank schematic is open.\n[PLAN]\nOpen the chooser."),
        (TYPE_R, "The symbol chooser is open with its search field focused.\n[PLAN]\nSearch R."),
        (END, "The results list shows Device:R.\n[PLAN]\nDone."),
    ]
    b, ws_b = _agent(tmp_path, "mfm-carry", "B", monkeypatch)
    _drive(b, fake_codex, script_b, [_png(0), _png(1), _png(2)])
    prompts = [c["prompt"] for c in json.loads(R._dump_calls(fake_codex, tmp_path))]
    # Call 8 = task B's second turn: the chooser after key(a) at the blank schematic,
    # exactly task A's first transition.
    assert "[RECALL] the last turn's situation and action occurred before in an earlier task" in prompts[7]
    assert 'previous/A step 1: at "The blank schematic is open." you did key(a) -> "The symbol chooser is open with its search field focused."; then type("R") -> "The results list shows Device:R."' in prompts[7]
    sit = (ws_b / "previous" / "situations.md").read_text()
    assert sit.startswith("# Situations from the finished tasks")
    assert '## "The symbol chooser is open with its search field focused."  (2 turns, 1 task(s))' in sit
    assert "situations.md" in (ws_b / "AGENTS.md").read_text()
    b.finish(0.0, None)
    assert b.audit()["carry"]["situations"] == 1
    merged = [json.loads(l) for l in (ws_b / "previous" / "index.jsonl").read_text().splitlines() if l]
    assert all(r.get("effect") for r in merged if r["kind"] == "episode" and r["first_step"] < 6)
