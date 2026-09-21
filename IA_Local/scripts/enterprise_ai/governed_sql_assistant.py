from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from enterprise_agent_orchestrator import answer_enterprise_question_orchestrated
from enterprise_sql_gateway import EnterpriseSqlError, EnterpriseSqlExecutor


R10_24C2_GOVERNED_SQL_ASSISTANT_VERSION = "r10.24c2.1"

_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$"
)

_EXPLICIT_OBJECT = re.compile(
    r"\b[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*\b"
)

_COUNT_CUES = (
    "cuantos",
    "cuantas",
    "cantidad",
    "numero de",
    "total de",
    "total registros",
    "registros",
    "filas",
    "conteo",
    "count",
)

_CONNECTED_CUES = (
    "sql",
    "base de datos",
    "datos conectados",
    "fuente conectada",
    "informacion conectada",
)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text.lower()).strip()


def _safe_table(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text if _IDENTIFIER.fullmatch(text) else None


class GovernedSqlAssistantBridge:
    """Assistant bridge over the existing governed SQL execution authority."""

    def __init__(
        self,
        *,
        store: Any,
        provider_factory: Callable[[], Any],
    ) -> None:
        self.store = store
        self.provider_factory = provider_factory

    @staticmethod
    def _count_intent(question: str) -> bool:
        normalized = _norm(question)
        return any(cue in normalized for cue in _COUNT_CUES)

    def _profiles(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        for raw in self.store.list(scope):
            profile = dict(raw)

            if not profile.get("enabled", True):
                continue

            if not profile.get("read_only", False):
                continue

            if str(profile.get("status") or "ACTIVE").upper() not in {
                "ACTIVE",
                "READY",
            }:
                continue

            tables = [
                safe
                for safe in (
                    _safe_table(value)
                    for value in (profile.get("allowed_tables") or [])
                )
                if safe
            ]

            if not tables:
                continue

            profile["_assistant_allowed_tables"] = tables
            output.append(profile)

        return output

    @staticmethod
    def _candidates(
        profiles: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], str]]:
        return [
            (profile, table)
            for profile in profiles
            for table in profile.get("_assistant_allowed_tables", [])
        ]

    def _select(
        self,
        question: str,
        profiles: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
        normalized = _norm(question)
        candidates = self._candidates(profiles)

        allowed = {
            _norm(table): (profile, table)
            for profile, table in candidates
        }

        explicit = list(
            dict.fromkeys(
                _EXPLICIT_OBJECT.findall(normalized)
            )
        )

        if explicit:
            if any(item not in allowed for item in explicit):
                return None, None, "NOT_ALLOWED"

            if len(explicit) == 1:
                profile, table = allowed[explicit[0]]
                return profile, table, "MATCHED"

            return None, None, "AMBIGUOUS"

        short_matches = []

        for profile, table in candidates:
            short = _norm(table.split(".", 1)[1])

            if re.search(
                r"\b" + re.escape(short) + r"\b",
                normalized,
            ):
                short_matches.append((profile, table))

        unique = []
        seen = set()

        for profile, table in short_matches:
            key = (
                str(profile.get("connection_id") or ""),
                table.lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append((profile, table))

        if len(unique) == 1:
            return unique[0][0], unique[0][1], "MATCHED"

        if len(unique) > 1:
            return None, None, "AMBIGUOUS"

        if (
            len(candidates) == 1
            and any(cue in normalized for cue in _CONNECTED_CUES)
        ):
            return candidates[0][0], candidates[0][1], "MATCHED"

        return None, None, "NO_MATCH"

    @staticmethod
    def _requested_label(question: str) -> Optional[str]:
        match = re.search(
            r"\b([A-Za-z][A-Za-z0-9_]{2,50})"
            r"\s*=\s*<\s*(?:numero|número|number)\s*>",
            str(question or ""),
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return match.group(1).upper()

    @staticmethod
    def _result(
        *,
        answer: str,
        structured: bool,
        fast_path: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        elapsed_ms: float = 0.0,
        governance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "ok": True,
            "answer": answer,
            "sources": list(sources or []),
            "memory_candidate": None,
            "timings_ms": {
                "memory_ms": 0.0,
                "rag_ms": 0.0,
                "structured_ms": round(elapsed_ms, 2),
                "llm_ms": 0.0,
                "queue_ms": 0.0,
                "total_ms": round(elapsed_ms, 2),
            },
            "retrieval": {
                "memories": 0,
                "document_chunks": 0,
                "structured": bool(structured),
                "fast_path": fast_path,
                "generation_mode": "deterministic",
            },
            "governance": dict(governance or {}),
        }

    def resolve(
        self,
        *,
        scope: Dict[str, Any],
        question: str,
    ) -> Optional[Dict[str, Any]]:
        if not self._count_intent(question):
            return None

        started = time.perf_counter()

        try:
            profiles = self._profiles(scope)
        except EnterpriseSqlError:
            return None

        if not profiles:
            return None

        profile, table, state = self._select(
            question,
            profiles,
        )

        elapsed_ms = (time.perf_counter() - started) * 1000

        if state == "NO_MATCH":
            return None

        if state == "NOT_ALLOWED":
            return self._result(
                answer="La fuente solicitada no está autorizada para esta consulta.",
                structured=False,
                fast_path="governed_sql_blocked",
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced": True,
                    "fail_closed": True,
                },
            )

        if (
            state == "AMBIGUOUS"
            or profile is None
            or table is None
        ):
            return self._result(
                answer="Hay más de una fuente posible. Indica cuál deseas consultar.",
                structured=False,
                fast_path="governed_sql_ambiguous",
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced": True,
                    "fail_closed": True,
                },
            )

        connection_id = str(
            profile.get("connection_id") or ""
        ).strip()

        if not connection_id:
            return None

        schema, object_name = table.split(".", 1)

        query_plan = {
            "operation": "SELECT",
            "sql": (
                "SELECT COUNT_BIG(*) AS TOTAL_REGISTROS "
                f"FROM [{schema}].[{object_name}]"
            ),
            "parameters": [],
            "limit": 1,
            "timeout_seconds": int(
                profile.get("timeout_seconds") or 30
            ),
        }

        try:
            executor = EnterpriseSqlExecutor(
                self.store,
                self.provider_factory(),
            )

            routed = answer_enterprise_question_orchestrated(
                registry=None,
                knowledge_store=None,
                scope=scope,
                question=question,
                sql_context={
                    "connection_id": connection_id,
                    "query_plan": query_plan,
                },
                sql_executor=executor,
                sql_scope=scope,
            )

        except EnterpriseSqlError:
            elapsed_ms = (time.perf_counter() - started) * 1000

            return self._result(
                answer="No fue posible consultar los datos autorizados en este momento.",
                structured=False,
                fast_path="governed_sql_blocked",
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced": True,
                    "fail_closed": True,
                },
            )

        payload = dict(routed.get("answer") or {})
        rows = list(payload.get("rows") or [])

        if (
            not rows
            or not isinstance(rows[0], (list, tuple))
            or not rows[0]
        ):
            value = None
        else:
            value = rows[0][0]

        if value is None:
            answer = "La consulta se completó, pero no devolvió un total."
        else:
            requested = self._requested_label(question)
            answer = (
                f"{requested}={value}"
                if requested
                else f"Total de registros: {value}"
            )

        elapsed_ms = (time.perf_counter() - started) * 1000

        governance = dict(routed.get("governance") or {})
        governance.update(
            {
                "read_only": True,
                "allowlist_enforced": True,
                "fail_closed": True,
                "sql_execution_authority": "governed_executor",
            }
        )

        return self._result(
            answer=answer,
            structured=True,
            fast_path="governed_sql",
            sources=[
                {
                    "type": "connected_data",
                    "name": "Datos conectados",
                    "resource": object_name,
                    "read_only": True,
                }
            ],
            elapsed_ms=elapsed_ms,
            governance=governance,
        )
