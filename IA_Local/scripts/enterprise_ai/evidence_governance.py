"""Governed evidence-shaping boundaries for R10.25D.

This module never performs business calculations.  It only shapes already
executed evidence before that evidence is materialized into LLM context.
"""

from __future__ import annotations

import copy
from typing import Any


LARGE_EVIDENCE_CONTRACT = "r10.25d2"


def govern_large_evidence(evidence_rows: Any, *, max_rows: int = 2000):
    """Deterministically bound already-executed row evidence.

    Source evidence is never mutated.  Ordering is preserved.  This function
    has no authority to calculate metrics, classify findings, rank findings,
    or let an LLM decide which rows survive.
    """
    try:
        limit = int(max_rows)
    except (TypeError, ValueError):
        limit = 2000

    if limit <= 0:
        limit = 1

    if evidence_rows is None:
        source_rows = []
    elif hasattr(evidence_rows, "to_dict"):
        source_rows = evidence_rows.to_dict(orient="records")
    else:
        source_rows = list(evidence_rows)

    total_rows = len(source_rows)
    retained = copy.deepcopy(source_rows[:limit])

    return {
        "contract": LARGE_EVIDENCE_CONTRACT,
        "rows": retained,
        "total_rows": total_rows,
        "returned_rows": len(retained),
        "truncated": total_rows > len(retained),
        "source": "executed_results",
        "authority": "governed_large_data_evidence",
        "llm_truncation_authority": False,
    }
