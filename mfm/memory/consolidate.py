"""Consolidation: the episodic rows of finished tasks folded into a situation table.

An episode is one decision; a *situation* is what the model said it was looking at,
abstracted (`norm_text`). Over a run the same situations recur -- the settings
dialog, the symbol chooser, the library-setup dialog, a properties dialog -- and for
each the table keeps the actions taken there, how often, and what the model said each
one did. This is procedural memory distilled from the episodic record, written for the
model as `previous/situations.md` at task start, and rebuilt from the merged index at
every task boundary (so it is never stale and needs no separate state).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

_REF = re.compile(r"\b(?:r|c|d|u|j|sw|l|q|y|k|f|bt|tp|h)\d+[a-z]?\b")
_NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:k|u|µ|n|p|m|meg)?(?:ω|ohm|ohms|f|v|hz|a|w)?\b")
_QUOTES = re.compile(r"[\"'`“”‘’*]")
_NONALPHA = re.compile(r"[^a-z ]+")
_SENTENCE_END = re.compile(r"(?<=[.;!?])\s+")

#: Words a perception line spends on itself rather than on the screen.
_FILLER = {"the", "a", "an", "is", "are", "was", "were", "now", "still", "no", "not",
           "with", "and", "of", "in", "on", "as", "at", "to", "its", "it", "this",
           "that", "expected", "correctly", "feedback", "errors", "error", "reported",
           "appears", "appear", "shows", "showing", "open", "opened", "visible"}
KEY_WORDS = 8


def first_sentence(text: str | None) -> str:
    line = (text or "").strip().split("\n")[0]
    return _SENTENCE_END.split(line, 1)[0]


def norm_text(text: str | None, words: int = KEY_WORDS) -> str:
    """A perception line reduced to its situation: the first sentence, refs and numbers
    abstracted away, filler dropped, the first `words` content words."""
    s = first_sentence(text).lower()
    s = _QUOTES.sub("", s)
    s = _REF.sub(" ref ", s)
    s = _NUM.sub(" n ", s)
    s = _NONALPHA.sub(" ", s)
    toks = [t for t in s.split() if t not in _FILLER]
    return " ".join(toks[:words])


def norm_action(summary: str | None) -> str:
    """An action string reduced to its kind and keys: `click(697,830)` -> `click(n,n)`,
    `type("NE555P")` -> `type(text)`, `key(ctrl+s)` stays. Multi-action batches keep
    their sequence."""
    s = (summary or "").strip().lower()
    s = re.sub(r'type\("[^"]*"\)', "type(text)", s)
    s = re.sub(r"type\([^)]*\)", "type(text)", s)
    s = re.sub(r"\d+", "n", s)
    s = re.sub(r"\s+", "", s)
    return s


def situations(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group episode rows by situation, then by action; counts and example effects."""
    groups: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("kind") != "episode":
            continue
        key = norm_text(r.get("perception"))
        if not key:
            continue
        g = groups.setdefault(key, {"key": key, "example": r.get("perception"), "n": 0,
                                    "tasks": set(), "actions": {}})
        g["n"] += 1
        if r.get("task"):
            g["tasks"].add(r["task"])
        ak = norm_action(r.get("summary"))
        a = g["actions"].setdefault(ak, {"key": ak, "example": r.get("summary"), "n": 0,
                                         "effects": Counter(), "effect_examples": {},
                                         "unchanged": 0})
        a["n"] += 1
        if "screen_unchanged" in (r.get("tags") or []):
            a["unchanged"] += 1
        ek = norm_text(r.get("effect"))
        if ek:
            a["effects"][ek] += 1
            a["effect_examples"].setdefault(ek, r.get("effect"))
    out = []
    for g in groups.values():
        acts = sorted(g["actions"].values(), key=lambda a: -a["n"])
        out.append({"key": g["key"], "example": g["example"], "n": g["n"],
                    "tasks": sorted(g["tasks"]),
                    "actions": [{"key": a["key"], "example": a["example"], "n": a["n"],
                                 "unchanged": a["unchanged"],
                                 "effects": [{"example": a["effect_examples"][k], "n": c}
                                             for k, c in a["effects"].most_common(3)]}
                                for a in acts]})
    out.sort(key=lambda g: (-g["n"], g["key"]))
    return out


def _q(text: str | None, n: int = 120) -> str:
    t = " ".join((text or "").split())
    return f'"{t[:n - 3].rstrip()}..."' if len(t) > n else f'"{t}"'


def to_markdown(table: list[dict[str, Any]], *, limit: int = 40, min_n: int = 2) -> str:
    """The table for the model: situations seen at least `min_n` times, most frequent
    first, each with its actions and what they led to."""
    lines = ["# Situations from the finished tasks",
             "",
             "What you said you were looking at (abstracted), how many turns it took, "
             "and what each action there led to. Built by the harness from your own "
             "earlier turns.",
             ""]
    shown = 0
    for g in table:
        if g["n"] < min_n:
            continue
        if shown >= limit:
            break
        shown += 1
        tasks = f", {len(g['tasks'])} task(s)" if g["tasks"] else ""
        lines.append(f"## {_q(g['example'])}  ({g['n']} turns{tasks})")
        for a in g["actions"][:4]:
            eff = "; ".join(f"{_q(e['example'], 90)} x{e['n']}" for e in a["effects"]) or "(no effect recorded)"
            unchanged = f", screen unchanged {a['unchanged']}x" if a["unchanged"] else ""
            lines.append(f"- `{a['example']}` x{a['n']}{unchanged} -> {eff}")
        lines.append("")
    if shown == 0:
        lines.append("(no situation has recurred yet)")
    return "\n".join(lines).rstrip("\n") + "\n"
