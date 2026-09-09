"""The KiCad eval loop's offline-rescoring support: grader inputs are saved per task
and the dataset patches are idempotent."""
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KICAD = Path(__file__).resolve().parents[1] / "CUA-KiCad"
sys.path.insert(0, str(KICAD))

run_eval = pytest.importorskip("gym_codex.run_eval")
patch_tasks = importlib.import_module("gym_codex.patch_kicad_tasks")


class FakeSession:
    """Stands in for the cua computer session: a dict of remote files and a command log."""

    def __init__(self, files: dict[str, bytes]):
        self.files = dict(files)
        self.commands: list[str] = []

    async def run_command(self, cmd: str, check=False):
        self.commands.append(cmd)
        root = run_eval._KICAD_PROJECT_DIR
        if cmd.startswith(f"find '{root}' -type f"):
            return {"stdout": "\n".join(sorted(self.files)) + "\n"}
        if "-name '*.kicad_sch'" in cmd:
            sch = sorted(f for f in self.files if f.endswith(".kicad_sch"))
            return {"stdout": (sch[0] + "\n") if sch else ""}
        if cmd.startswith("kicad-cli sch export netlist"):
            out = cmd.split("-o '")[1].rstrip("'")
            self.files[out] = b"(export (version \"E\") (components))"
            return {"stdout": ""}
        return {"stdout": ""}

    async def read_bytes(self, path: str) -> bytes:
        return self.files[path]


def _env(session):
    return SimpleNamespace(unwrapped=SimpleNamespace(_cb=SimpleNamespace(session=session)))


def test_grader_inputs_saved_and_netlist_exported(tmp_path):
    root = run_eval._KICAD_PROJECT_DIR
    session = FakeSession({
        f"{root}/blink/blink.kicad_sch": b"(kicad_sch)",
        f"{root}/blink/blink.kicad_pro": b"{}",
        f"{root}/blink/blink-backups/x.zip": b"zip",   # not a grader input
    })
    saved = asyncio.run(run_eval._save_grader_inputs(_env(session), tmp_path))
    assert sorted(saved["files"]) == ["blink/blink.kicad_pro", "blink/blink.kicad_sch"]
    assert (tmp_path / "kicad_project/blink/blink.kicad_sch").read_bytes() == b"(kicad_sch)"
    assert not (tmp_path / "kicad_project/blink/blink-backups").exists()
    assert saved["graded_net"] == "graded.net"
    assert (tmp_path / "graded.net").read_bytes().startswith(b"(export")
    assert any(c.startswith(f"kicad-cli sch export netlist '{root}/blink/blink.kicad_sch'")
               for c in session.commands)


def test_existing_netlist_is_the_graded_one(tmp_path):
    root = run_eval._KICAD_PROJECT_DIR
    session = FakeSession({f"{root}/a.net": b"(export)", f"{root}/a.kicad_sch": b"(sch)"})
    saved = asyncio.run(run_eval._save_grader_inputs(_env(session), tmp_path))
    assert saved["graded_net"] == "kicad_project/a.net"
    assert not any(c.startswith("kicad-cli") for c in session.commands)


def test_unreadable_file_is_skipped_not_fatal(tmp_path):
    root = run_eval._KICAD_PROJECT_DIR

    class Flaky(FakeSession):
        async def read_bytes(self, path):
            if path.endswith(".kicad_pro"):
                raise OSError("gone")
            return await super().read_bytes(path)

    session = Flaky({f"{root}/p.kicad_pro": b"{}", f"{root}/p.kicad_sch": b"(sch)"})
    saved = asyncio.run(run_eval._save_grader_inputs(_env(session), tmp_path))
    assert saved["files"] == ["p.kicad_sch"]


def test_exclude_tasks_filters_rows():
    class Reg:
        def task_ids(self, env_id, split):
            return ["a", "b", "c"]

        def task_metadata(self, env_id, task_id):
            return SimpleNamespace(others={"domain": "kicad", "feasible": True})

    gym = SimpleNamespace(registry=Reg())
    ids = [r["task_id"] for r in run_eval._eval_rows(gym, "cua.bench.local.kicad", None, None, ["b"])]
    assert ids == ["a", "c"]


def test_task_patch_is_idempotent(tmp_path):
    (tmp_path / "34877be3").mkdir()
    (tmp_path / "34877be3/main.py").write_text('desc = "two infrared LN271 LEDs"\n')
    assert patch_tasks.apply(tmp_path) == ["34877be3: patched"]
    assert "LD271" in (tmp_path / "34877be3/main.py").read_text()
    assert patch_tasks.apply(tmp_path) == ["34877be3: already patched"]


# -- the verification gate (--netlist-verify) -----------------------------------------

def _hold_args(**over):
    base = dict(netlist_verify=True)
    base.update(over)
    return SimpleNamespace(**base)


def _terminate(status="success"):
    return [{"id": "c1", "type": "function",
             "function": {"name": "terminate", "arguments": {"status": status}}}]


def test_first_success_terminate_is_held_once():
    args = _hold_args()
    assert run_eval._hold_terminate(args, True, _terminate(), 0, False)
    # ...and only once: the second one ends the episode.
    assert not run_eval._hold_terminate(args, True, _terminate(), 1, False)


def test_hold_repeats_only_when_the_first_found_nothing_saved():
    args = _hold_args()
    assert run_eval._hold_terminate(args, True, _terminate(), 1, True)
    assert not run_eval._hold_terminate(args, True, _terminate(), 2, True)


def test_giving_up_and_ordinary_batches_are_never_held():
    args = _hold_args()
    assert not run_eval._hold_terminate(args, True, _terminate("failure"), 0, False)
    click = [{"id": "c1", "type": "function",
              "function": {"name": "click", "arguments": {"x": 1, "y": 2}}}]
    assert not run_eval._hold_terminate(args, False, click, 0, False)
    assert not run_eval._hold_terminate(args, True, [], 0, False)


def test_the_gate_is_off_by_default():
    assert not run_eval._hold_terminate(_hold_args(netlist_verify=False), True,
                                        _terminate(), 0, False)


def test_verify_note_only_reaches_the_prompt_when_the_flag_is_on(tmp_path):
    from gym_codex.mfm_prompts import NETLIST_NOTE, NETLIST_VERIFY_NOTE
    from gym_codex.prolong_agent import ProlongGuiAgent

    def prompt(**kw):
        a = ProlongGuiAgent.__new__(ProlongGuiAgent)
        a.max_steps, a.log_only = 200, False
        a.netlist, a.netlist_verify = kw.get("netlist", False), kw.get("netlist_verify", False)
        return a.system_prompt()

    base = prompt()
    assert NETLIST_NOTE not in base and NETLIST_VERIFY_NOTE not in base
    assert NETLIST_VERIFY_NOTE not in prompt(netlist=True)
    both = prompt(netlist=True, netlist_verify=True)
    assert NETLIST_NOTE in both and NETLIST_VERIFY_NOTE in both


def test_verify_implies_the_read_back():
    """Without the per-step refresh the gate hands the model its netlist once, after it
    has already decided it is done -- which is how kicad_mfmverify_pilot ran."""
    args = SimpleNamespace(netlist_verify=True, netlist_readback=False)
    run_eval._apply_implications(args)
    assert args.netlist_readback is True
    off = SimpleNamespace(netlist_verify=False, netlist_readback=False)
    run_eval._apply_implications(off)
    assert off.netlist_readback is False
