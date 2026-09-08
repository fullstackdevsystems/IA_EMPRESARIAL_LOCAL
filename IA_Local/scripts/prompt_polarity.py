from __future__ import annotations

import re
from typing import Any


_NEGATED_ACTION_RE = re.compile(
    r"\b(?:no\s+|do\s+not\s+)"
    r"(?:"
    r"invent(?:es|e|ar)|"
    r"us(?:es|e|ar)|"
    r"incluy(?:as|a|e|es|ir)|"
    r"calcul(?:es|e|ar)|"
    r"gener(?:es|e|ar)|"
    r"muestr(?:es|e|ar)|"
    r"consider(?:es|e|ar)|"
    r"asum(?:as|e|ir)|"
    r"invent|use|include|calculate|generate|show|assume"
    r")\b"
    r"[^.;\n]*",
    flags=re.IGNORECASE,
)


_POSITIVE_PIVOT_RE = re.compile(
    r"\b(?:"
    r"pero\s+si|"
    r"pero|"
    r"excepto|"
    r"salvo|"
    r"however|"
    r"but|"
    r"except"
    r")\b",
    flags=re.IGNORECASE,
)


def positive_request_text(value: Any) -> str:
    """Remove explicit negated-action clauses before intent extraction.

    Example:
        "No inventes costos, presupuesto ni fletes."
    must constrain the plan, not request those metrics.
    """

    text = str(
        value
        or ""
    )

    def replace_clause(match):
        clause = match.group(0)

        pivot = _POSITIVE_PIVOT_RE.search(
            clause
        )

        if pivot:
            return clause[
                pivot.start():
            ]

        return " "

    return _NEGATED_ACTION_RE.sub(
        replace_clause,
        text,
    )
