"""Prompts for the BrowseComp-Plus port of PRO-LONG.

What is deliberately preserved from `MineExplorer:prolong_mc/prompts.py` is the
*mechanism*, since that is what the paper claims: one append-only log the agent parses
programmatically, a persistent workspace, the JSON-artifact contract, briefing-then-plan,
the instruction to keep plans short while testing a hypothesis, and the log-window
ablation wording.

What is preserved from `eval_direct_browsecomp_plus.py` is the *task framing*, verbatim.
Wording that differs between the arms is a confound, so the paragraph describing the
corpus, the tool, and the answer format is copied rather than rewritten, and
`selftest.py` asserts it has not drifted from the baseline's copy. Only the response
protocol differs -- Action/Action Input lines against a written `actions.json` -- because
that difference *is* the arm.
"""
from __future__ import annotations

# Verbatim from eval_direct_browsecomp_plus.SYSTEM_PROMPT's opening. Kept as a literal
# rather than imported because importing that module pulls in the corpus loader and the
# vLLM client; selftest.py does the import once and asserts the two agree.
TASK_FRAMING = """\
You are a research assistant answering a hard trivia question using ONLY a
fixed local document corpus -- you cannot browse the live web, and you
cannot answer from memory alone (the questions are deliberately obscure)."""

# The two sentences the stateless ablation changes, as template fields rather than as a
# post-hoc `.replace()`. MineExplorer's port rewrites the rendered prompt by string
# match, and this port's selftest caught that arrangement failing silently on a
# whitespace difference: the ablation flag was set, the enforcement bound in the
# filesystem, and the prompt still told the agent its workspace persisted. A field
# cannot half-apply.
LOG_CONTENTS_PERSISTENT = ("the searches issued, what each returned, and your own\n"
                           "prior analyses.")
LOG_CONTENTS_STATELESS = "the searches issued and what each returned."

WORKSPACE_PERSISTENT = """\
**Workspace**: `./` persists across calls. `actions.json` is cleared each call; other
files accumulate. Feel free to save notes, extracted candidate entities, or helper
scripts -- grepping `./docs/` with a script you wrote last turn is the intended way to
work here."""

WORKSPACE_STATELESS = """\
**Workspace**: `./` does NOT persist across calls -- notes, extracted entities and helper
scripts are gone once actions are submitted. Only `logs.txt` and the documents it names
carry over."""

SYSTEM_PROMPT = """\
You are a coding agent answering one hard trivia question by writing search plans.

{task_framing}

Your secondary objective is to use as few searches as possible.

**Question**: {question}

`./logs.txt` is the episode log: {log_contents} {log_window_desc} Every retrieved
document is also on disk in full under `./docs/`, and the log names its path -- so the
evidence stays complete whether or not you read the log end to end. Parse it
**programmatically**: grep what you have already pulled before searching for it
again.{cross_turn_hint}

**Tools**: Read, Write, Edit, Bash, Grep, Glob.

{workspace_section}

**Log markers**:
    [SEARCH] the query that was issued.
    [RESULT] how many documents came back, and their docids.
    [DOC] docs/<file> — one retrieved document. Anything quoted under this line in the
        log is a truncated snippet; the file at that path is the full text. Open the
        file whenever the snippet looks relevant or is absent. A [DOC] line marked
        "already retrieved" points at a file you were given on an earlier search.
    [PLAN] — your own plan from the previous call.
    [NOTE] — something the runner rejected or refused since the previous call.

**What you can rely on**:
- The corpus is fixed and offline. A document that is not in `./docs/` has not been
  retrieved yet; a fact that is in no retrieved document is not evidence.
- Search is BM25 over the full corpus, so it rewards distinctive rare terms (names,
  numbers, dates) and punishes long natural-language questions. Rephrase rather than
  repeat: re-issuing a query you already ran returns what is already on disk.
- You keep no separate memory: `logs.txt` and whatever you save in `./` are your memory.

**Response format**: a short briefing on what the evidence so far establishes and what
is still missing, then
[PLAN]
<2-3 sentence plan>

**Write `./actions.json`**, with either the searches to run next

    {{"actions": [{{"search": "<query>"}}, ...]}}

-- a list of 1-{action_cap} queries executed in order -- or, when the retrieved evidence
settles it, the final answer

    {{"answer": {{"explanation": "<your reasoning>",
                "exact_answer": "<succinct final answer>",
                "confidence": <0-100>}}}}

Prefer short lists (1-2 queries) while you are narrowing down, so you see what came back
before committing further. You have at most {step_cap} searches for this question in
total; when they run out you will be asked for an answer regardless, so leave yourself
room to write one. Answer only from the retrieved documents.
"""

FIRST_PROMPT = """\
{log_desc}

This is the first analysis. The log holds the question and nothing else yet. Work out
which distinctive terms would identify the answer in a fixed corpus, then write
./actions.json with your first searches.
"""

RESUME_PROMPT = """\
{log_desc}

{body}
"""

RESUME_BODY = """\
The most recent searches and their results are at the end of the log. What changed since
the last call -- which documents are new, whether they narrow the candidate set, which
of your open questions they close -- is the useful signal. Check ./ for anything you
saved previously, then either search again or write the answer.

Searches used so far: {used}/{step_cap}.
"""

RESUME_BODY_NO_HISTORY = """\
Compare the current state to your notes in the workspace. Focus on what the latest
results add and whether your previous plan made progress. Check ./ for anything you
saved previously, then either search again or write the answer.

Searches used so far: {used}/{step_cap}.
"""

FINAL_PROMPT = """\
{log_desc}

You are out of searches ({used}/{step_cap} used). Based on the documents in ./docs/ and
everything in the log, write ./actions.json now with the final answer only:

    {{"answer": {{"explanation": "...", "exact_answer": "...", "confidence": <0-100>}}}}

No further searches will be executed.
"""


def build_system_prompt(
    question: str,
    action_cap: int,
    step_cap: int,
    log_window: int | None,
    stateless: bool = False,
) -> str:
    """Render the system prompt. `log_window` follows PRO-LONG's convention:
    None = full log, 0 = latest section only, >0 = that many sections."""
    if log_window is None:
        log_window_desc = "It contains the full search history for this question."
    elif log_window == 0:
        log_window_desc = "It contains only the most recent search and its results."
    else:
        log_window_desc = f"It contains the last {log_window} search sections."

    multi_turn = log_window is None or (log_window or 0) > 0
    cross_turn_hint = (
        " Cross-turn parsing (diffing which docids a query added against the ones you "
        "already had, grepping every retrieved document at once for a candidate name) "
        "is tractable and is often the only way to notice a query returned nothing new."
    ) if multi_turn else ""

    return SYSTEM_PROMPT.format(
        task_framing=TASK_FRAMING,
        question=question,
        action_cap=action_cap,
        step_cap=step_cap,
        log_window_desc=log_window_desc,
        cross_turn_hint=cross_turn_hint,
        log_contents=LOG_CONTENTS_STATELESS if stateless else LOG_CONTENTS_PERSISTENT,
        workspace_section=WORKSPACE_STATELESS if stateless else WORKSPACE_PERSISTENT,
    )


def build_turn_prompt(
    is_first: bool,
    log_window: int | None,
    used: int,
    step_cap: int,
    out_of_budget: bool = False,
) -> str:
    if log_window is None:
        log_desc = "Read the full episode log at ./logs.txt"
    elif log_window == 0:
        log_desc = "Read ./logs.txt (latest search only; no history)."
    else:
        log_desc = f"Read ./logs.txt (last {log_window} searches)."

    if out_of_budget:
        return FINAL_PROMPT.format(log_desc=log_desc, used=used, step_cap=step_cap)
    if is_first:
        return FIRST_PROMPT.format(log_desc=log_desc)
    body = RESUME_BODY_NO_HISTORY if log_window == 0 else RESUME_BODY
    return RESUME_PROMPT.format(
        log_desc=log_desc, body=body.format(used=used, step_cap=step_cap)
    )
