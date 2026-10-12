"""How a failed codex turn is classified, for the memory arms' retry loops and log notes.

Not every default is the arm's failure, and neither the report nor the log the model
reads back as its own history should say it was. Three kinds are told apart:

  upstream content filter   the backend declined the request. A property of the task,
                            not of the approach; retried a bounded number of extra
                            times with the identical prompt (rephrasing to get past the
                            filter would answer a different task and be evasion rather
                            than measurement), and recorded as declined if it keeps
                            refusing.
  transient infrastructure  the backend shedding load ("at capacity"), the sandbox's
                            egress proxy failing to come up, a dropped socket. Extends
                            the budget with backoff, and if it never clears the turn is
                            handed to the driver as *unavailable* rather than scored as
                            a no-op step.
  the arm's own             a context overflow, or a turn that produced nothing usable.
                            Spends the budget and, when it is charged, is charged to
                            the method.
"""
from __future__ import annotations

from typing import Any, Optional

# Extra attempts an arm may spend on a turn the backend declined, on top of its normal
# retry budget. The refusal is drawn per call rather than per task -- the same item has
# been seen refused once and answered on the next attempt -- and it comes back in
# 30-80 s, so giving up after three costs a turn the arm would usually have made.
FILTER_RETRIES = 6

# Extra attempts, with exponential backoff, on a transient infrastructure error. A
# shedding window outlasts a no-backoff loop of three, which would score the turn as a
# default; the bound keeps a backend that is really down from being retried forever
# inside one turn -- past it the driver's own backoff-then-terminate path applies.
CAPACITY_RETRIES = 4


def default_reason_key(reason: Optional[str]) -> str:
    """Bucket one failed turn by cause, for every arm through one function."""
    text = (reason or "").lower()
    if "overflow" in text:
        return "context overflow"
    if "flagged for possible" in text or "content policy" in text:
        return "upstream content filter"
    if "codex_sandbox" in text:
        return "sandbox"
    if "at capacity" in text:
        return "capacity"
    if "disconnect" in text or "connection reset" in text or "broken pipe" in text:
        return "server/transport"
    if "timeout" in text:
        return "timeout"
    return "other"


def is_filter_refusal(reason: Any) -> bool:
    return default_reason_key(str(reason) if reason is not None else None) \
        == "upstream content filter"


def is_transient_infra(reason: Any) -> bool:
    """True when the failure is the infrastructure's -- nothing the model did, nothing it
    can correct -- and a retry after a wait is the right response."""
    return default_reason_key(str(reason) if reason is not None else None) \
        in ("sandbox", "capacity", "server/transport")
