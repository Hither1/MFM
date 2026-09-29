"""The log moved to the shared `mfm` package (MFM repo root; `pip install -e` there).
This module *is* `mfm.memory.log`, aliased so that `SEPARATOR`, `EpisodeLog` and
`prepare_workspace` keep their import path."""
from __future__ import annotations

import sys as _sys

from mfm.memory import log as _shared

_sys.modules[__name__] = _shared
