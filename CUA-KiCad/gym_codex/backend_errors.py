"""Moved to `mfm.backend.errors` (MFM repo root); this name is kept for the importers."""
from __future__ import annotations

import sys as _sys

from mfm.backend import errors as _shared

_sys.modules[__name__] = _shared
