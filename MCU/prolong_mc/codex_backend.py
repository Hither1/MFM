"""MCU's Codex backend: `mfm.backend.codex_turn` under the MCU policy.

The implementation moved to the shared `mfm` package (MFM repo root; `pip install -e`
there). What this module keeps is the arm's *policy*: every knob on which the MCU copy
of `CodexTurn` behaved differently from the KiCad copy is pinned here to the MCU value
(`MCU_POLICY`), so `prolong_agent.py` constructs the class exactly as before and gets
the same argv, the same session lifecycle and the same audit keys. `tests/` in the MFM
repo pins all three against the pre-merge code.

Also bridges the shared module's stdlib logging into loguru, which is what this repo's
launchers configure, so the backend's turn-by-turn messages still reach the arm log.
"""
from __future__ import annotations

from mfm.backend.codex_turn import *  # noqa: F401,F403
from mfm.backend.codex_turn import (  # noqa: F401  (underscored names `import *` skips)
    MCU_POLICY, OVERFLOW_POLICY_MCU, _COMPACTION_RE, _SESSION_RE, _TOOL_ITEM_TYPES,
)
from mfm.backend.codex_turn import CodexTurn as _CodexTurn
from mfm.backend.codex_turn import _metadata_args as _base_metadata_args
from mfm.backend.codex_turn import is_overflow as _base_is_overflow


class CodexTurn(_CodexTurn):
    """The shared backend with MCU's defaults. Explicit keyword arguments still win."""

    def __init__(self, workspace, **kw) -> None:
        for key, value in MCU_POLICY.items():
            kw.setdefault(key, value)
        super().__init__(workspace, **kw)


def _metadata_args(context_window: int) -> list[str]:
    """MCU's two-flag form: the real window, no compaction-scope pin."""
    return _base_metadata_args(context_window, headroom=MCU_POLICY["window_headroom"],
                               scope=MCU_POLICY["compact_scope"])


def is_overflow(name: str, text: str) -> bool:
    return _base_is_overflow(name, text, OVERFLOW_POLICY_MCU)


from prolong_mc._loguru_bridge import bridge_to_loguru

bridge_to_loguru()
