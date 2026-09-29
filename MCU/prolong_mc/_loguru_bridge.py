"""Route the shared `mfm` package's stdlib logging into loguru, which is what this
repo's launchers configure, so the backend's and the log's turn-by-turn messages still
reach the arm log. Idempotent."""
from __future__ import annotations

import logging


class _LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        from loguru import logger as _loguru
        level = record.levelname if record.levelname in (
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO"
        _loguru.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def bridge_to_loguru(name: str = "mfm") -> None:
    root = logging.getLogger(name)
    if not any(isinstance(h, _LoguruHandler) for h in root.handlers):
        root.addHandler(_LoguruHandler())
        root.setLevel(logging.INFO)
        root.propagate = False
