"""Parse and validate the JSON artifact a PRO-LONG turn produces.

Mirrors `MineExplorer:prolong_mc/actions.py` in shape -- accept the documented object,
cap the length, skip and warn on anything unrecognised -- with the action vocabulary of
each benchmark in place of Minecraft's.

Two rules are carried over from that file because both were bought with a debugging
session. Nothing is silently substituted: a malformed entry is dropped *and logged*, so
an agent mistake stays visible instead of turning into an invisible wasted step. And the
caps truncate rather than reject, so one over-long plan costs the entries past the cap
and not the whole turn.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _load(raw_text: str) -> Optional[dict[str, Any]]:
    """Parse the artifact, tolerating the fenced block a model sometimes writes anyway."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("[plans] artifact is not valid JSON: %s", exc)
        return None
    if not isinstance(obj, dict):
        logger.warning("[plans] expected a JSON object, got %s", type(obj).__name__)
        return None
    return obj


# ---------------------------------------------------------------------------
# BrowseComp-Plus: a list of searches, or the terminal answer
# ---------------------------------------------------------------------------

class SearchPlan:
    """One validated turn: the queries to run, or the answer that ends the episode."""

    def __init__(
        self,
        queries: Optional[list[str]] = None,
        answer: Optional[dict[str, Any]] = None,
    ) -> None:
        self.queries = queries or []
        self.answer = answer

    def __bool__(self) -> bool:
        return bool(self.queries) or self.answer is not None


def parse_search_plan(
    raw_text: str,
    *,
    action_cap: int = 4,
    step_budget: int = 30,
    query_max_chars: int = 400,
) -> SearchPlan:
    """Return the validated plan. A falsy plan means the turn produced nothing usable.

    `step_budget` is what is *left* of the episode's search allowance, not the total, so
    a plan is truncated against the real remaining budget rather than against a constant
    that stopped being true several turns ago.
    """
    obj = _load(raw_text)
    if obj is None:
        return SearchPlan()

    # The answer is terminal, so it wins outright. A turn that writes both is answering
    # and hedging at once; taking the answer and logging the rest is the reading that
    # cannot lose an answer the agent had already committed to.
    answer = obj.get("answer")
    if isinstance(answer, dict) and str(answer.get("exact_answer", "")).strip():
        if obj.get("actions"):
            logger.warning("[plans] artifact carries both an answer and searches; "
                           "taking the answer and dropping %d search(es)",
                           len(obj["actions"]) if isinstance(obj["actions"], list) else 1)
        return SearchPlan(answer={
            "explanation":  str(answer.get("explanation", "")).strip(),
            "exact_answer": str(answer["exact_answer"]).strip(),
            "confidence":   answer.get("confidence"),
        })
    if isinstance(answer, str) and answer.strip():
        # Forgiving on shape, strict on the field that decides grading.
        return SearchPlan(answer={"explanation": "", "exact_answer": answer.strip(),
                                  "confidence": None})

    entries = obj.get("actions")
    if not isinstance(entries, list):
        logger.warning("[plans] expected a list under 'actions', got %s",
                       type(entries).__name__)
        return SearchPlan()

    queries: list[str] = []
    for entry in entries[:action_cap]:
        if isinstance(entry, str):
            query = entry
        elif isinstance(entry, dict):
            query = entry.get("search") or entry.get("query") or ""
        else:
            logger.warning("[plans] skipping unrecognised entry: %r", entry)
            continue
        query = str(query).strip()
        if not query:
            logger.warning("[plans] skipping entry with an empty query: %r", entry)
            continue
        if len(query) > query_max_chars:
            logger.warning("[plans] truncating a %d-char query to %d",
                           len(query), query_max_chars)
            query = query[:query_max_chars]
        if len(queries) >= step_budget:
            logger.warning("[plans] search budget exhausted; dropping remaining entries")
            break
        queries.append(query)

    if len(entries) > action_cap:
        logger.warning("[plans] %d entries submitted; only the first %d are executed",
                       len(entries), action_cap)
    return SearchPlan(queries=queries)
