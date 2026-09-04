"""Retrieval over the episode index: the same functions the workspace CLI exposes
(`mfm/memory/tools/episodes.py`), importable by the harness for a retrieval block."""
from mfm.memory.tools.episodes import (  # noqa: F401
    describe, grep, near, read_index, recent, same_action, same_observation, steps, tagged,
)
