"""The Codex backend moved to the shared `mfm` package (MFM repo root; `pip install -e`
there). This module *is* `mfm.backend.codex_turn`: the defaults there are this arm's,
so nothing is re-declared, and the module object is aliased rather than re-exported so
that `codex_backend.AUTO_COMPACT_TOKEN_LIMIT = ...` and friends in `selftest.py` patch
the one module the code actually reads.
"""
from __future__ import annotations

import sys as _sys

from mfm.backend import codex_turn as _shared

_sys.modules[__name__] = _shared
