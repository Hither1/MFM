"""The visual memory is for looking (2026-09-08): the mfm contract names `view_image` in its
tool line and says when to look back at a frame; the RECALL block cites each entry's frame;
the human contract names the tool; the logbook contract is unchanged."""
from __future__ import annotations


def test_mfm_tools_line_names_view_image():
    from mcu_worldmodel import prompts

    mfm = prompts._mfm_contract()
    assert "`view_image <png>` to LOOK at a frame" in mfm
    assert "zoom" not in mfm.split("**Tools**")[1].split("Write")[0]          # no zoom.py without --frames
    assert "a crop from `tools/zoom.py`" in prompts._mfm_contract(frames=True)
    assert "**Tools**: Read, Bash, Grep, Glob to read the log; Write" not in mfm
    assert "**Look back.**" in mfm and "--previous --near X Z" in mfm
    assert "The log knows where;\nthe frame knows what." in mfm
    logbook = prompts._LOGBOOK_CONTRACT
    assert "view_image" not in logbook and prompts._LOGBOOK_TOOLS_LINE in logbook
    thin, refs = prompts.thin_split(mfm)
    assert "`view_image <png>` to LOOK at a frame" in thin       # the tool line stays in the thin head


def test_retrieval_note_and_human_contract_point_at_frames():
    from mcu_worldmodel import prompts
    from mcu_worldmodel.episodes import MFM_RETRIEVAL_NOTE

    assert "carries its frame path" in MFM_RETRIEVAL_NOTE and "`view_image` that frame" in MFM_RETRIEVAL_NOTE
    h = prompts.human_contract(task_text="t", progress_block="", entry_cap=4, step_cap=40)
    assert "`view_image <png>`" in h and "**Look back.**" in h


def test_recall_block_cites_frames():
    from mfm.memory.retrieve import recall_block

    rows = [{"id": f"ep_{i:06d}", "image": f"episodes/ep_{i:06d}/observation/image.png",
             "kind": "episode", "action_kind": "dig_down", "first_step": 10 * i, "last_step": 10 * i + 5,
             "x": 100.0, "y": 60.0, "z": 100.0, "tags": ["stuck"], "summary": "[ACTION] dig_down(n=3) -> moved 0.0",
             "moved": 0.0, "inventory_delta": {}, "events": []} for i in range(1, 6)]
    rows.append({"id": "ep_000009", "image": "episodes/ep_000009/observation/image.png", "kind": "episode",
                 "action_kind": "craft", "first_step": 90, "last_step": 95, "x": 100.0, "y": 60.0, "z": 100.0,
                 "tags": ["inventory_changed", "milestone"], "summary": "[ACTION] craft(item=stick) milestone ['x']",
                 "moved": 0.0, "inventory_delta": {"stick": 4}, "events": []})
    block = recall_block(rows, pos=(100.0, 100.0), exclude_last=0, streak_min=3)
    assert block.startswith("[RECALL]")
    assert "(frame: episodes/ep_00000" in block
    assert block.rstrip().endswith("(one line not enough? `view_image` the cited frame: what that entry saw is what you will see there.)")
    assert "Frame: episodes/ep_00000" in block or "(frame: episodes/ep_00000" in block
