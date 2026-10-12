"""Retrieval for action selection: what happened the last time the model was here.

The store's index is lossless at the file level and lossy at the index: a turn's row
carried the raw action string and the screenshot's exact hash, nothing of what the model
saw, meant, or caused. The exact hash matched twice in 24 KiCad tasks;
a whole-frame perceptual hash alone matched half of all frames and conflated the
update-check dialog with the library-setup dialog. What recurs reliably is the
*transition*: the model's one-line perception of a screen, the action it took there, and
the screen that followed. This module keys on that.

A row written with `EpisodeStore(recall=True)` carries

    perception   the first line of the turn's plan text: what the model said it saw
    intent       the rest of the plan text
    effect       the next turn's perception line: what the model said the action did
    dhash        64-bit difference hash of the frame the turn was decided on (hex)
    next_dhash   the same for the frame the episode closed on

`match` finds earlier rows that repeated the previous turn's transition: the same
action, and either a similar perception line with a compatible next frame, or frames
near-identical both before and after (the model paraphrases the same dialog
differently from task to task -- "an update prompt blocks the manager" / "the
update-check dialog" -- while the dialog's frame hashes to the same bits; a canvas,
conversely, hashes alike with one more part on it, which is what the text catches).
`render` turns the hits into the `[RECALL]` block pushed into the turn prompt. Pure
functions over index rows; PIL is optional (no hash, no image check).
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

_REF = re.compile(r"\b(?:r|c|d|u|j|sw|l|q|y|k|f|bt|tp|h)\d+[a-z]?\b")
_NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:k|u|µ|n|p|m|meg)?(?:ω|ohm|ohms|f|v|hz|a|w)?\b")
_QUOTES = re.compile(r"[\"'`“”‘’*]")
_NONALPHA = re.compile(r"[^a-z ]+")

#: Words a perception line spends on itself rather than on the screen.
_FILLER = {"the", "a", "an", "is", "are", "was", "were", "now", "still", "no", "not",
           "with", "and", "of", "in", "on", "as", "at", "to", "its", "it", "this",
           "that", "expected", "correctly", "feedback", "errors", "error", "reported",
           "appears", "appear", "shows", "showing", "open", "opened", "visible"}

#: How many bits two 64-bit difference hashes may differ by and still be "the same
#: screen" once the transition text has already matched. Whole-frame hashes of KiCad
#: dialogs over the same canvas differ by 0-3 bits; a different dialog by 8-20.
SAME_SCREEN_BITS = 8
#: Frames "near-identical" enough to stand in for the text: the situation frame and
#: the outcome frame must both be this close.
NEAR_SAME_BITS = 3
#: Jaccard similarity of the content words of two perception lines to count as the
#: same situation (with a compatible outcome frame).
SIMILAR_TEXT = 0.5
#: The image-only fallback (no transition match): near-identical frames only. Off by
#: default: replayed over a recorded KiCad mfm run, a 64-bit whole-frame hash within
#: 2 bits matched 64% of all turns (a canvas with one more part hashes like the canvas),
#: while the transition route fired on 9% and its suggested next action was the one the
#: model then took in 33 of 74 cases.
NEAR_EXACT_BITS = 2
SCREEN_FALLBACK = False
KEY_WORDS = 8


_SENTENCE_END = re.compile(r"(?<=[.;!?])\s+")


def first_sentence(text: str | None) -> str:
    line = (text or "").strip().split("\n")[0]
    return _SENTENCE_END.split(line, 1)[0]


def content_words(text: str | None) -> frozenset[str]:
    s = first_sentence(text).lower()
    s = _QUOTES.sub("", s)
    s = _REF.sub(" ref ", s)
    s = _NUM.sub(" n ", s)
    s = _NONALPHA.sub(" ", s)
    return frozenset(t for t in s.split() if t not in _FILLER)


def similarity(a: str | None, b: str | None) -> float:
    """Jaccard similarity of the content words of two perception lines."""
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


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


def perception_and_intent(think: str | None) -> tuple[str, str]:
    lines = [l.strip() for l in (think or "").strip().split("\n") if l.strip()]
    if not lines:
        return "", ""
    return lines[0][:300], " ".join(lines[1:])[:400]


# -- perceptual hash ---------------------------------------------------------------

def dhash_file(path: Path | str, size: int = 8) -> str | None:
    """Difference hash of an image as 16 hex chars, or None (no PIL, unreadable)."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return None
    try:
        im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    except Exception:  # noqa: BLE001
        return None
    px = list(im.getdata())
    w = size + 1
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * w + c] > px[r * w + c + 1] else 0)
    return f"{bits:016x}"


def hamming(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


# -- matching ------------------------------------------------------------------------

def transition_key(row: dict[str, Any]) -> tuple[str, str] | None:
    p = norm_text(row.get("perception"))
    a = norm_action(row.get("summary"))
    if not p or not a:
        return None
    return (p, a)


def successor(rows: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any] | None:
    """The episode that opened on the frame `row` closed on, in the same task."""
    task = row.get("task")
    for r in rows:
        if r.get("task") == task and r.get("kind") == "episode" \
                and r.get("first_step") == row.get("last_step") and r is not row:
            return r
    return None


def transition_score(prev: dict[str, Any], cur_dhash: str | None, r: dict[str, Any], *,
                     same_screen_bits: int = SAME_SCREEN_BITS) -> float | None:
    """How well earlier row `r` repeats `prev`'s transition into the current frame:
    None for no match, else a score (higher is better) for ranking."""
    if norm_action(r.get("summary")) != norm_action(prev.get("summary")) or not r.get("effect"):
        return None
    sim = similarity(prev.get("perception"), r.get("perception"))
    d_prev = hamming(prev.get("dhash"), r.get("dhash"))
    d_next = hamming(cur_dhash, r.get("next_dhash"))
    by_text = sim >= SIMILAR_TEXT and (d_next is None or d_next <= same_screen_bits)
    by_image = (d_prev is not None and d_prev <= NEAR_SAME_BITS
                and d_next is not None and d_next <= NEAR_SAME_BITS)
    if not (by_text or by_image):
        return None
    return sim * 10 - (d_prev or 0) - (d_next or 0)


def match(rows: Iterable[dict[str, Any]], prev: dict[str, Any] | None,
          cur_dhash: str | None, *, k: int = 3,
          same_screen_bits: int = SAME_SCREEN_BITS,
          screen_fallback: bool = SCREEN_FALLBACK) -> tuple[str, list[dict[str, Any]]]:
    """Earlier rows that repeat the previous turn's transition, best first.

    Returns ("transition", hits) when `prev`'s action recurs with a similar perception
    and a compatible next frame, or with near-identical frames before and after
    (`transition_score`); ("screen", hits) for the opt-in image-only fallback;
    ("", []) otherwise.
    """
    rows = [r for r in rows if r.get("kind") == "episode" and r is not prev]
    if prev is not None and prev.get("summary"):
        scored = []
        for i, r in enumerate(rows):
            sc = transition_score(prev, cur_dhash, r, same_screen_bits=same_screen_bits)
            if sc is not None:
                scored.append((sc, i, r))
        if scored:
            scored.sort(key=lambda t: (-t[0], -t[1]))       # best, then newest
            return "transition", [r for _, _, r in scored[:k]]
    if cur_dhash and screen_fallback:
        hits = []
        for r in rows:
            d = hamming(cur_dhash, r.get("dhash"))
            if d is not None and d <= NEAR_EXACT_BITS and r.get("effect"):
                hits.append(r)
        if hits:
            return "screen", hits[-k:][::-1]
    return "", []


def _where(row: dict[str, Any]) -> str:
    task = row.get("task")
    return (f"previous/{task} step {row.get('first_step')}" if task
            else f"step {row.get('first_step')}")


def _q(text: str | None, n: int = 110) -> str:
    t = " ".join((text or "").split())
    return f'"{t[:n - 3].rstrip()}..."' if len(t) > n else f'"{t}"'


def render(kind: str, hits: list[dict[str, Any]], all_rows: list[dict[str, Any]],
           scope: str) -> str | None:
    """The [RECALL] block: each hit as the chain it started, two steps ahead."""
    if not hits:
        return None
    lines = []
    for r in hits:
        chain = f"{_where(r)}: at {_q(r.get('perception'))} you did {r.get('summary')} -> {_q(r.get('effect'))}"
        nxt = successor(all_rows, r)
        if nxt is not None and nxt.get("summary"):
            chain += f"; then {nxt.get('summary')}"
            if nxt.get("effect"):
                chain += f" -> {_q(nxt.get('effect'))}"
        lines.append(chain)
    if kind == "transition":
        head = (f"[RECALL] the last turn's situation and action occurred before {scope} "
                f"({len(hits)} shown, best match first); what followed then:")
    else:
        head = f"[RECALL] a screen near-identical to this one occurred before {scope}:"
    return head + "\n" + "\n".join("  " + l for l in lines)


def recall_note(rows: list[dict[str, Any]], prev: dict[str, Any] | None,
                cur_dhash: str | None, scope: str, k: int = 3) -> str | None:
    kind, hits = match(rows, prev, cur_dhash, k=k)
    return render(kind, hits, rows, scope)


def repeated_transitions(rows: Iterable[dict[str, Any]]) -> Counter:
    """How often each (situation, action) recurs: the audit's view of what recall
    could have fired on."""
    return Counter(k for k in (transition_key(r) for r in rows if r.get("kind") == "episode") if k)
