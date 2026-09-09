"""`goal_image:` -- the target designated by a picture the agent itself took.

MrSteve's Long-Navigation ends with an image goal; our port swapped it for a text
designator so the prompt contract would be identical across arms. That was right for
comparing memory ARCHITECTURES and wrong for comparing memory MODALITIES: a phrase can
be answered from a phrase, so a text-only memory could win the text variant outright.
`recall_long_navigation_image` restores the picture. See mcu_worldmodel/goalimage.py.
"""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def GoalImage():
    from mcu_worldmodel.goalimage import GoalImage
    return GoalImage


def _spec(**kw):
    d = {"step": 300, "window": 3000, "every": 200, "milestone": "return_to_fire_pit"}
    d.update(kw)
    return d


def _view(seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, size=(24, 32, 3), dtype=np.uint8)


def _flat():
    return np.full((24, 32, 3), 140, dtype=np.uint8)


class _Ledger:
    def __init__(self, achieved=None, live=True):
        self.achieved = achieved or {}
        self._live = live

    def eligible(self, ident):
        return self._live


# -- capture ---------------------------------------------------------------------------


def test_nothing_is_captured_before_the_window(GoalImage, tmp_path):
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(299, _view())
    assert g.captured_at is None
    assert not g.path.exists()


def test_a_flat_frame_is_rejected(GoalImage, tmp_path):
    """The agent looks wherever it was already looking; a cue of the sky measures
    nothing, so a frame with almost no variation is not kept."""
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _flat())
    assert g.captured_at is None
    assert g.flat_rejects == 1


def test_the_window_keeps_retrying_past_a_flat_frame(GoalImage, tmp_path):
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _flat())          # sky
    g.maybe_capture(301, _view())          # then something with detail
    assert g.captured_at == 301
    assert g.path.exists()


def test_capture_stops_at_the_end_of_the_window(GoalImage, tmp_path):
    """The window must close before the landmark is removed and the agent teleported
    away, or the cue would show somewhere else entirely."""
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(3301, _view())
    assert g.captured_at is None


def test_a_later_good_frame_replaces_an_earlier_one_on_the_cadence(GoalImage, tmp_path):
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _view(1))
    assert g.captured_at == 300
    g.maybe_capture(301, _view(2))         # off-cadence: ignored
    assert g.captured_at == 300
    g.maybe_capture(500, _view(3))         # on the `every`=200 cadence
    assert g.captured_at == 500


# -- serving ---------------------------------------------------------------------------


def test_the_cue_is_withheld_until_its_milestone_opens(GoalImage, tmp_path):
    """21,500 steps of prologue with no goal is the point: showing the picture early
    would turn incidental encoding into a search task."""
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _view())
    assert g.serve(_Ledger(live=False)) is None
    assert g.serve(_Ledger(live=True)) == g.path


def test_the_cue_stops_once_the_goal_is_scored(GoalImage, tmp_path):
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _view())
    assert g.serve(_Ledger(achieved={"return_to_fire_pit": 21800})) is None


def test_nothing_is_served_when_no_frame_was_ever_captured(GoalImage, tmp_path):
    g = GoalImage(_spec(), tmp_path)
    assert g.serve(_Ledger()) is None


def test_the_note_names_no_landmark(GoalImage):
    """If the prose said "fire" or "burning", the picture would be decoration and a
    text-only memory could answer without it."""
    note = GoalImage.NOTE.lower()
    assert "picture" in note
    for leak in ("fire", "burning", "netherrack", "pond", "tower", "pumpkin", "gold"):
        assert leak not in note


def test_the_audit_records_which_frame_became_the_cue(GoalImage, tmp_path):
    """A run whose cue was a bad picture has to be discardable on the evidence."""
    g = GoalImage(_spec(), tmp_path)
    g.maybe_capture(300, _flat())
    g.maybe_capture(301, _view())
    g.serve(_Ledger())
    a = g.audit()
    assert a["captured_at"] == 301 and a["flat_rejects"] == 1 and a["served"] == 1
    assert a["milestone"] == "return_to_fire_pit"


# -- the task pair ---------------------------------------------------------------------


def test_the_image_variant_differs_from_its_twin_only_in_how_the_goal_is_named():
    import sys
    sys.path[:0] = ["MCU", "MCU/src"]
    from util import load_goal_image, load_scheduled_commands, load_world_spec
    from task_milestones import load_milestone_cfg

    a, b = "recall_long_navigation", "recall_long_navigation_image"
    assert load_scheduled_commands(a) == load_scheduled_commands(b)
    assert load_world_spec(a) == load_world_spec(b)
    assert not load_goal_image(a) and load_goal_image(b)

    ca, cb = load_milestone_cfg(a), load_milestone_cfg(b)
    assert [r["identity"] for r in ca] == [r["identity"] for r in cb]
    assert ca[0]["not_before"] == cb[0]["not_before"]
    assert ca[0]["target"] == cb[0]["target"] and ca[0]["radius"] == cb[0]["radius"]
    # ...and the text designator is gone, or the picture would not be load-bearing.
    assert "burning" in ca[0]["describe"]
    assert "burning" not in cb[0]["describe"]


def test_the_cue_window_closes_before_the_landmark_is_removed():
    """The picture must show the fire; the fire is filled over at step 3700."""
    import sys
    sys.path[:0] = ["MCU", "MCU/src"]
    from util import load_goal_image, load_scheduled_commands
    spec = load_goal_image("recall_long_navigation_image")
    removal = min(s["step"] for s in load_scheduled_commands("recall_long_navigation_image")
                  if any("grass_block" in c or "minecraft:air" in c for c in s["commands"]))
    assert spec["step"] + spec["window"] < removal
