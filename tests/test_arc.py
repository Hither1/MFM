"""The arc-code arm, offline: the actuator's parsing on its own, then the MCU chassis in
`--memory arc` driven the way its harness drives it, with `tests/fake_arc_agent.py`
playing a script through `./act` in place of codex.

What is pinned: the rendered brief (AGENTS.md), what every `./act` call printed back
(the sections, the status block, the refusals), and the chassis's own record
(`logs.txt`) -- so a change to the port shows as a diff. The other arms' pins are
untouched: every arc path in the chassis is gated on `self.arc`.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

import numpy as np
import pytest

from conftest import ROOT, check_pin

FAKE_AGENT = ROOT / "tests" / "fake_arc_agent.py"


def _norm(text: str, tmp: Path) -> str:
    """Pin what the model was handed, not when. The chassis ticks while the fake agent
    runs its shell commands, so every tick number in a reply is a race with it; the
    sections, their order, the fields and the wording are not."""
    text = text.replace(str(tmp), "<tmp>")
    subs = (
        # The no-op line says how long the environment waited for the batch: pure
        # timing, and it survives JSON escaping, so both forms go.
        (r"\(the environment ran \d+ no-op tick\(s\) waiting for this batch\)(\\n|\n)?", ""),
        (r"\d+\.\d+s", "<s>"),
        (r"\b\d+\.\d+\b", "<f>"),                       # positions, moved
        (r"step \d+/\d+", "step <s>/<max>"),
        (r"\(\d+ ticks left\)", "(<n> ticks left)"),
        (r"(?<!Plan )\bStep \d+", "Step <s>"),      # not "Plan Step 1/2", which is content
        (r"in \d+ ticks", "in <t> ticks"),
        (r"-> \d+ ticks", "-> <t> ticks"),
        (r"frames/step_\d+", "frames/step_<s>"),
        (r"stall_turns \d+", "stall_turns <n>"),
        (r"\(step \d+\)", "(step <s>)"),
        (r"at step \d+", "at step <s>"),
        (r"\d+ leftover attack ticks", "<n> leftover attack ticks"),
    )
    for pattern, into in subs:
        text = re.sub(pattern, into, text, flags=re.M)
    return text


# -- the actuator on its own ----------------------------------------------------------

def test_act_parses_entries():
    from mfm.arc.act import ActError, parse_do, parse_entry
    assert parse_entry("dig_down(n=4)") == {"procedure": "dig_down", "args": {"n": 4}}
    assert parse_entry('craft(item=stick)') == {"procedure": "craft", "args": {"item": "stick"}}
    assert parse_entry('craft(item="stick")') == parse_entry("craft(item=stick)")
    assert parse_entry("look_at(pos=[1, 2, 3], ticks=20)") == {
        "procedure": "look_at", "args": {"pos": [1, 2, 3], "ticks": 20}}
    assert parse_entry('{"action": {"forward": 1}, "repeat": 5}') == {"action": {"forward": 1}, "repeat": 5}
    assert parse_entry("noop()") == {"procedure": "noop", "args": {}}
    with pytest.raises(ActError):
        parse_entry("nonsense")
    with pytest.raises(ActError):
        parse_entry("dig_down(4)")
    with pytest.raises(ActError):
        parse_entry("[1, 2]")
    req = parse_do(["dig_down(n=4)", "--plan", "down we go", '{"action": {"jump": 1}, "repeat": 2}'])
    assert req == {"actions": [{"procedure": "dig_down", "args": {"n": 4}},
                               {"action": {"jump": 1}, "repeat": 2}], "plan": "down we go"}
    with pytest.raises(ActError):
        parse_do(["--plan", "nothing to do"])


def test_act_reads_a_batch_file(tmp_path: Path):
    from mfm.arc.act import parse_do
    f = tmp_path / "plan.json"
    f.write_text(json.dumps({"actions": [{"procedure": "dig_down", "args": {"n": 1}}]}))
    req = parse_do(["--file", str(f), "look_abs(pitch=0,yaw=90)"])
    assert [e["procedure"] for e in req["actions"]] == ["dig_down", "look_abs"]


# -- the MCU chassis in arc mode -------------------------------------------------------

@pytest.fixture
def fake_agent(tmp_path: Path):
    FAKE_AGENT.chmod(FAKE_AGENT.stat().st_mode | stat.S_IEXEC)
    script = tmp_path / "fake_arc.jsonl"
    calls = tmp_path / "fake_arc_calls.jsonl"
    script.write_text("")
    calls.write_text("")
    os.environ["FAKE_ARC_SCRIPT"] = str(script)
    os.environ["FAKE_ARC_CALLS"] = str(calls)

    class Handle:
        def session(self, *commands: str, message: str = "") -> None:
            with script.open("a") as f:
                f.write(json.dumps({"commands": list(commands), "message": message}) + "\n")

        def recorded(self) -> list[dict]:
            return [json.loads(l) for l in calls.read_text().splitlines() if l.strip()]

    yield Handle()
    for k in ("FAKE_ARC_SCRIPT", "FAKE_ARC_CALLS"):
        os.environ.pop(k, None)


def _pov(step: int) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % 360, :, 1] = 255
    return frame


def drive_arc_chassis(root: Path, fake, steps: int = 400, **options):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "iron_pickaxe",
            "objects": ["iron_pickaxe"], "reward": 1.0, "max_reward_times": 1}]
    opts = {"codex_bin": str(FAKE_AGENT), "max_sessions": 4, "relaunch_delay": 0.1,
            "close_timeout": 5, "poll": 0.05, **options}
    agent = WorldModelAgent(workspace=root / "ws", task_text="get a log, a table, an iron pickaxe",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=10,
                            step_cap=200, memory_mode="arc", platform_prompt="HOST REFERENCE",
                            codex_home=root / "home", codex_timeout=1, arc_options=opts)
    ws = root / "ws"
    # Session 1: orient, a one-entry batch with a plan, a two-entry batch whose attack
    # hold is cut short by a break (the drain inside `next_action`), three refusals --
    # the shim's, the harness's parser's, a procedure refused against the state -- a
    # note file, the view, a look at it, the log read with grep; then the model stops.
    fake.session(
        "./act status",
        'touch fire_log; ./act do \'{"action": {"forward": 1}, "repeat": 30}\''
        ' --plan "walk north; I expect a log to land"',
        './act do "dig_down(n=4)" --plan "I expect to dig four blocks down."',
        'touch chop; ./act do \'{"action": {"forward": 1}, "repeat": 5}\' \'{"action": {"attack": 1}, "repeat": 40}\''
        ' --plan "walk five, then hold attack"',
        "./act do nonsense",
        './act do \'{"bogus": 1}\'',
        './act do "craft(item=stone_pickaxe)"',
        'printf "Trees are north.\\n" > notes.md; ls',
        "./act view",
        "view $(./act view)",
        'grep -c "^Action" logs.txt',
        message="Stopping here.")
    # Session 2 (resumed): the note survived; a batch a milestone cuts short -- the
    # marker file makes the test's world verify crafting_table on the next tick -- then
    # one more batch, the status; then the model stops again.
    fake.session(
        "cat notes.md",
        'touch fire_table; ./act do \'{"action": {"forward": 1}, "repeat": 20}\' '
        '\'{"action": {"forward": 1}, "repeat": 20}\' \'{"action": {"forward": 1}, "repeat": 20}\' '
        '\'{"action": {"forward": 1}, "repeat": 20}\' --plan "walk on; a milestone will cut this"',
        './act do \'{"action": {"forward": 1}, "repeat": 30}\' --plan "walk on"',
        "./act status",
        message="Stopping again.")
    # Session 3 (resumed): one last batch, then the script is exhausted and the fake
    # holds until the episode's close kills it.
    fake.session('./act do \'{"action": {"forward": 1}, "repeat": 40}\' --plan "the last walk"',
                 message="Done.")

    # The world the chassis observes, driven by marker files the script touches rather
    # than by tick number: each is consumed on the first observe that sees it, so the
    # run has exactly one log break (the mine_log milestone), one dirt break (which cuts
    # the attack hold) and one craft, whichever ticks they land on. The dirt is a
    # DIFFERENT block on purpose: a second oak_log would re-fire the milestone, and a
    # verified milestone drops the queue before the hold can be cut. Health is constant,
    # so no reflex fires.
    logs, dirt, crafted = 0, 0, False

    def world() -> dict:
        inv = {"oak_log": 1 + logs}
        if crafted:
            inv["crafting_table"] = 1
        broke = {k: v for k, v in (("oak_log", logs), ("dirt", dirt)) if v}
        return fake_info(inventory=inv, mine_block=broke,
                         craft_item={"crafting_table": 1} if crafted else {})

    info = world()
    info["pov"] = _pov(0)
    agent.start(info)
    actions = []
    for step in range(1, steps + 1):
        actions.append(agent.next_action(info))
        for marker in ("fire_log", "chop", "fire_table"):
            path = ws / marker
            if not path.exists():
                continue
            head, head_idx = agent.queue[0] if agent.queue else (None, None)
            # `fire_log` and `fire_table` are the milestones that verify mid-batch, so
            # they wait for a batch to be running. Both land inside a RAW entry: a
            # procedure has phases, and cutting one at whichever phase the clock reached
            # is a race.
            if marker == "fire_log" and head is None:
                continue
            # `chop` is the block that breaks while the attack hold is the RUNNING entry:
            # `_cut_attack_hold` refuses a break whose entry has already finished
            # (`idx != self._entry_index`), which is every tick before the chassis has
            # popped one of the hold's own actions. `fire_table` is the milestone that
            # verifies mid-batch, so it waits for a batch to be running.
            if marker == "chop" and not (head and head.get("attack")
                                         and head_idx == agent._entry_index):
                continue
            if marker == "fire_table" and head is None:
                continue
            path.unlink()
            if marker == "fire_table":
                crafted = True
            elif marker == "chop":
                dirt += 1
            else:
                logs += 1
        info = world()
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["location_stats"]["ypos"] = np.array(64.0 - (step // 20))
        info["pov"] = _pov(step)
        agent.observe(info, step)
    agent.arc.finish()
    return agent, actions


def test_chassis_arc_mode(tmp_path: Path, fake_agent):
    agent, actions = drive_arc_chassis(tmp_path, fake_agent)
    ws = agent.memory.root
    rec = fake_agent.recorded()
    assert [r["session"] for r in rec] == [0, 1, 2, 3]       # three played, one held
    assert rec[3].get("held") and rec[3]["prompt"].startswith("A previous session")
    assert rec[0]["prompt"].startswith("Read AGENTS.md")
    assert rec[0]["cwd"] == str(ws)
    s1 = {r["cmd"]: r for r in rec[0]["results"]}
    s2 = {r["cmd"]: r for r in rec[1]["results"]}

    # The status block: the budget, the milestones, the present.
    status = s1["./act status"]["out"]
    assert status.startswith("step ") and "milestones 0/3 verified" in status
    assert "inventory: oak_logx1" in status and "position: pos=(" in status
    assert "view: frames/step_0000.png" in status
    # A batch: the section it produced, verbatim, then upstream's summary lines.
    walk = [r for r in rec[0]["results"] if "fire_log" in r["cmd"]][0]
    assert walk["rc"] == 0 and "MILESTONE mine_log verified" in walk["out"]
    assert "[INV] oak_log +1" in walk["out"] and "Action 1 | Step " in walk["out"]
    dig = [r for r in rec[0]["results"] if "dig_down" in r["cmd"]][0]
    assert dig["rc"] == 0
    assert "[PLAN] I expect to dig four blocks down." in dig["out"]
    assert "[ACTION] dig_down(n=4)" in dig["out"] and "[FRAME] frames/step_" in dig["out"]
    assert re.search(r"ran 1/1 entries in \d+ ticks", dig["out"])
    assert "log: logs.txt (through Action 2)" in dig["out"]
    # The attack hold, cut short inside next_action, still answered with its refund note.
    hold = [r for r in rec[0]["results"] if '"attack": 1' in r["cmd"]][0]
    assert hold["rc"] == 0 and "ran 2/2 entries" in hold["out"]
    assert "attack-hold entry cut short" in hold["out"] and "[ACTION] {\"attack\":1} x40" in hold["out"]
    assert "[EVENT] mine_block dirt +1" in hold["out"]
    # Three refusals, three reasons, no ticks spent: the shim's parser, the harness's
    # parser (an entry that is neither), a procedure refused against the state.
    assert s1["./act do nonsense"]["rc"] == 1 and "neither" in s1["./act do nonsense"]["out"]
    bogus = [r for r in rec[0]["results"] if "bogus" in r["cmd"]][0]
    assert bogus["rc"] == 1 and "neither `procedure` nor `action`" in bogus["out"]
    craft = [r for r in rec[0]["results"] if "stone_pickaxe" in r["cmd"]][0]
    assert craft["rc"] == 1 and "cobblestone" in craft["out"]
    assert agent.arc.refused_batches == 2
    # The model's files persist (upstream's memory is the workspace): the note written
    # in session 1 is read back in session 2, and nothing was swept.
    assert s2["cat notes.md"]["out"] == "Trees are north.\n"
    assert (ws / "notes.md").exists() and agent.memory.swept == 0
    # The view: a frame on disk, named by the section, looked at once.
    view = s1["./act view"]["out"].strip()
    assert view.startswith("frames/step_") and (ws / view).exists()
    assert [r for r in rec[0]["results"] if r["cmd"].startswith("view ")][0]["rc"] == 0
    assert s1['grep -c "^Action" logs.txt']["out"].strip() == "5"       # initial + 4 sections
    # The batch a milestone cut short: the section that verified it, the drop count.
    cut = [r for r in rec[1]["results"] if "fire_table" in r["cmd"]][0]
    assert cut["rc"] == 0 and "MILESTONE crafting_table verified" in cut["out"]
    assert "stopped early: a milestone verified, 3 entries dropped" in cut["out"]
    assert re.search(r"ran 1/4 entries", cut["out"])
    assert agent.arc.entries_dropped == 3
    assert "milestones 2/3 verified" in s2["./act status"]["out"]

    # The chassis's own record: one section per applied entry, each naming its frame.
    log = (ws / "logs.txt").read_text()
    # A refusal's reasons went back to the model, not into the next section's [NOTE]s.
    assert "neither `procedure`" not in log and "need 3x cobblestone" not in log
    sections = log.count("\nAction ")
    assert sections - 1 == agent.arc.entries_applied == log.count("[FRAME] frames/step_") - 1
    assert "[PLAN] walk five, then hold attack" in log
    assert sorted((ws / "frames").iterdir())
    # The audit: three sessions that exited, a fourth held and killed at the close.
    audit = agent.report()["arc"]
    assert audit["agent"] == "codex" and audit["sessions"] == 4
    assert audit["session_exits"][:3] == [0, 0, 0] and audit["failure"] is None
    assert not audit["sessions_exhausted"]
    # `view $(./act view)` runs `./act view` a second time inside the fake's expansion.
    assert audit["act_calls"] == {"status": 2, "do": 8, "view": 2}
    assert audit["stream"]["image_views"] == 1 and audit["stream"]["commands"] >= 12
    assert audit["batches_applied"] == 6 and audit["decisions"] == 8
    assert audit["channel"]["plays"] == audit["channel"]["deliveries"] == 8
    assert agent.report()["codex"]["view_image_calls"] == 1
    assert not agent.arc.loop.alive and not agent.arc.mailbox.alive
    # The brief: the same bytes for either CLI; the log format, the actuator, arc-code's
    # method; no plan file, no tool of ours.
    brief = (ws / "AGENTS.md").read_text()
    assert brief == (ws / "CLAUDE.md").read_text()
    assert "./act do" in brief and "## Playing well" in brief and "notes.md" in brief
    assert "actions.json" not in brief and "zoom.py" not in brief and "Write to create" not in brief
    assert (ws / "act").stat().st_mode & stat.S_IXUSR
    check_pin("arc_mcu_agents.md", _norm(brief, tmp_path))
    check_pin("arc_mcu_calls.json", _norm(json.dumps(
        [{"session": r["session"], "prompt": r["prompt"],
          "results": [{"cmd": x["cmd"], "rc": x["rc"], "out": x["out"]} for x in r["results"]]}
         for r in rec], indent=1), tmp_path))
    check_pin("arc_mcu_logs.txt", _norm(log, tmp_path))


def test_arc_options_reach_the_agent():
    """`--memory arc` and its options parse; `--arc-*` without the mode is refused."""
    import importlib.util
    import subprocess
    import sys
    if importlib.util.find_spec("a2a") is None:
        pytest.skip("worldmodel_purple_agent.py imports a2a, which this interpreter lacks")
    purple = ROOT / "MCU" / "worldmodel_purple_agent.py"
    out = subprocess.run([sys.executable, str(purple), "--help"], capture_output=True, text=True,
                         cwd=str(ROOT / "MCU"))
    assert "arc" in out.stdout and "--arc-agent" in out.stdout and "--arc-max-sessions" in out.stdout
    bad = subprocess.run([sys.executable, str(purple), "--memory", "logbook", "--arc-agent", "claude",
                          "--workspace", "/tmp/x"], capture_output=True, text=True, cwd=str(ROOT / "MCU"))
    assert bad.returncode != 0 and "--arc-* options need --memory arc" in bad.stderr
