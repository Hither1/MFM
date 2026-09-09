"""`--text-only`: the memory keeps its rows and loses its pictures.

The mirror of `--visual-only` (mcu_worldmodel/visual.py), and the reason it exists: it
is the only single-variable contrast in this codebase for "is a multimodal memory better
than a single-modality one". Everything else that differs between the arms -- logbook vs
mfm, vista vs arc -- changes the memory protocol as well as its modality, so a gap
between them attributes to five things at once.

What must stay TRUE of the pair (baseline mfm vs mfm --text-only), and is what these
tests hold: the current view is still attached to every turn, the [STATE]/[INV] text is
unchanged, the rows and tools are the same. The ablation is what the MEMORY holds, not
what the agent perceives now -- otherwise it would be a perception experiment.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def prompts():
    from mcu_worldmodel import prompts
    return prompts


def _prompt(prompts, **kw):
    return prompts.act_prompt(
        task_text="t", progress_block="p", entry_cap=40, step_cap=400,
        memory_mode="mfm", scored_by_milestones=True,
        graph_summary="", plan_summary="", discipline_summary="", **kw)


def test_text_only_withdraws_the_stored_frames_from_the_contract(prompts):
    base, txt = _prompt(prompts), _prompt(prompts, text_only=True)
    # The baseline tells the model each episode holds the view it started from...
    assert "`observation/image.png` (the view the entry started from)" in base
    assert "--sheet" in base
    # ...and text-only must not, because `_observation` links no image into an episode.
    assert "`observation/image.png` (the view the entry started from)" not in txt
    assert "--sheet" not in txt
    assert "memory holds no pictures" in txt


def test_text_only_changes_the_memory_paragraph_and_nothing_else(prompts):
    """A contrast is single-variable only if one paragraph moves."""
    import difflib
    base, txt = _prompt(prompts), _prompt(prompts, text_only=True)
    changed = [l for l in difflib.unified_diff(base.split("\n"), txt.split("\n"),
                                               lineterm="", n=0)
               if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    assert changed, "text_only did nothing"
    # Every moved line belongs to the episodes paragraph; nothing about the current
    # view, the state text, the action reference or the scoring line may move.
    for line in changed:
        body = line[1:].lower()
        assert not any(leak in body for leak in
                       ("[state]", "[inv]", "hotbar", "milestone", "procedure",
                        "watch(", "camera")), f"text_only moved a non-memory line: {line}"


def test_the_only_image_mention_left_is_the_denial(prompts):
    """A dangling reference would send the model at a file that is not there."""
    txt = _prompt(prompts, text_only=True)
    hits = [l for l in txt.split("\n") if "image.png" in l]
    assert len(hits) == 1
    assert "there is no `observation/image.png`" in hits[0]


def test_frames_tooling_is_suppressed_because_it_has_nothing_to_read(prompts):
    """`--frames` is tools/zoom.py over stored frames; with none stored it is a trap."""
    with_frames = _prompt(prompts, frames=True)
    assert "zoom.py" in with_frames
    assert "zoom.py" not in _prompt(prompts, frames=True, text_only=True)


def test_text_only_needs_mfm_and_excludes_visual_only():
    """A memory that is neither text nor frames is no memory at all."""
    from mcu_worldmodel.agent import WorldModelAgent
    import inspect
    sig = inspect.signature(WorldModelAgent.__init__)
    assert "text_only" in sig.parameters
    src = inspect.getsource(WorldModelAgent.__init__)
    assert 'raise ValueError("text_only needs memory_mode=\'mfm\'")' in src
    assert 'raise ValueError("text_only and visual_only are exclusive")' in src


def test_the_store_links_no_image_when_text_only():
    """The choke point: `_observation` is the one place a frame enters an episode."""
    import inspect
    from mcu_worldmodel.episodes import EpisodeBridge
    src = inspect.getsource(EpisodeBridge._observation)
    assert 'if png and not getattr(self, "text_only", False):' in src
    # ...and the current view is a different file, so it survives (memory.py writes
    # attach/frame.png; the store's scratch is attach/episode_frame.png).
    assert "episode_frame.png" in inspect.getsource(EpisodeBridge.__init__)
