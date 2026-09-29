"""The optional JSON channel an act or induction turn writes, and how it is applied.

`hypotheses_ops.json` is how the agent changes its beliefs: the harness owns
`hypotheses/graph.json`, the agent sends ops, and every failure is contained -- a
malformed op, an unknown field, a dependency that would close a cycle -- because a
belief-bookkeeping mistake costing the turn its answer would be a worse failure than
the mistake itself. The parse error is returned so the runner can put it in front of
the agent as a [NOTE]: an agent whose file silently never loaded will keep writing it
the same wrong way.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from worldmodel_search.discipline import Discipline
from worldmodel_search.hypotheses import CycleError, HypothesisGraph

logger = logging.getLogger(__name__)

OPS_NAME = "hypotheses_ops.json"


def read_ops(workspace: Path) -> dict[str, Any]:
    """Read and consume this turn's ops file.

    Consumed, not merely read: the file is a one-shot assertion about *this* turn, and
    clearing before the turn is not enough on its own -- if a turn dies between the
    clear and the write, ops from an earlier turn would sit there and be re-applied.
    Deleting on read makes that impossible regardless of how the turn ended.
    """
    out: dict[str, Any] = {"ops": None, "error": None}
    path = workspace / OPS_NAME
    if not path.exists():
        return out
    try:
        out["ops"] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        out["error"] = f"{OPS_NAME} did not parse: {exc}"
        logger.warning("[worldmodel] %s", out["error"])
    finally:
        path.unlink(missing_ok=True)
    return out


def apply_ops(
    graph: HypothesisGraph,
    discipline: Discipline,
    parsed: Optional[dict[str, Any]],
    step: int,
) -> tuple[list[str], list[str]]:
    """Fold one turn's ops into the graph, then let the warden run.

    Returns (touched ids, notes for the log). The warden runs even on a turn with no
    ops -- the rules are about the graph's standing state, not about this turn's edits.
    """
    notes: list[str] = []
    touched: list[str] = []
    if isinstance(parsed, dict):
        for op in parsed.get("hypotheses") or []:
            if not isinstance(op, dict) or not op.get("id"):
                continue
            hid = str(op["id"])
            ev = op.get("evidence")
            try:
                graph.add_or_update(
                    id=hid, statement=op.get("statement"),
                    confidence=op.get("confidence"), status=op.get("status"),
                    kind=op.get("kind"),
                    evidence=[ev] if isinstance(ev, str) and ev.strip()
                             else (ev if isinstance(ev, list) else None),
                    step=step,
                )
                touched.append(hid)
            except Exception as e:
                logger.warning("[worldmodel] bad hypothesis op %r: %s", hid, e)
                continue
            for parent in op.get("depends_on") or []:
                try:
                    graph.add_dependency(hid, str(parent), step=step)
                except CycleError as e:
                    notes.append(f"dependency rejected: {e}")
                except Exception as e:
                    logger.warning("[worldmodel] bad dependency %s->%s: %s",
                                   hid, parent, e)
        note = discipline.track_testing(parsed.get("testing"), step)
        if note:
            notes.append(note)
    discipline.enforce()
    return touched, notes
