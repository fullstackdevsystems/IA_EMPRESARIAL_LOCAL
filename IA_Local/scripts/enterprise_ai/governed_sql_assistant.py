from __future__ import annotations

import ast
import re
import time
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from enterprise_agent_orchestrator import answer_enterprise_question_orchestrated
from enterprise_sql_gateway import EnterpriseSqlError, EnterpriseSqlExecutor


R10_24C2_GOVERNED_SQL_ASSISTANT_VERSION = "r10.24c2.1"
R10_30_GOVERNED_ROW_FILTER_VERSION = "r10.30-row-filter-v1"

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

    @staticmethod
    def _top_products_intent(
        question: str,
    ) -> bool:
        normalized = _norm(question)

        product_cue = any(
            cue in normalized
            for cue in (
                "producto",
                "productos",
                "articulo",
                "articulos",
            )
        )

        ranking_cue = any(
            cue in normalized
            for cue in (
                "mas vendido",
                "mas vendidos",
                "vendido mas",
                "vendidos mas",
                "vendieron mas",
                "se vendieron mas",
                "se han vendido mas",
                "top producto",
                "top productos",
                "productos top",
                "mayor venta",
                "mayores ventas",
                "mayor importe",
                "mayores importes",
            )
        )

        return (
            product_cue
            and ranking_cue
        )

    @staticmethod
    def _top_products_metric(
        question: str,
    ) -> str:
        normalized = _norm(question)

        if any(
            cue in normalized
            for cue in (
                "importe",
                "monto",
                "facturacion",
                "facturado",
                "ingreso",
                "ingresos",
                "valor vendido",
            )
        ):
            return "importe"

        return "cantidad"

    @staticmethod
    def _metadata_column_map(
        item: Dict[str, Any],
    ) -> Dict[str, str]:
        output: Dict[str, str] = {}

        for raw in (
            item.get("columns")
            or []
        ):
            name = str(
                raw.get("name") or ""
            ).strip()

            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                name,
            ):
                continue

            output[_norm(name)] = name

        return output

    @classmethod
    def _top_products_objects(
        cls,
        objects: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        product_candidates = []
        detail_candidates = []
        sales_candidates = []

        for item in objects:
            schema = str(
                item.get("schema") or ""
            ).strip()

            name = str(
                item.get("name") or ""
            ).strip()

            if not _safe_table(
                f"{schema}.{name}"
            ):
                continue

            columns = (
                cls._metadata_column_map(
                    item
                )
            )

            if {
                "productoid",
                "nombre",
            }.issubset(columns):
                product_candidates.append(
                    (item, columns)
                )

            if {
                "ventaid",
                "productoid",
                "cantidad",
                "importe",
            }.issubset(columns):
                detail_candidates.append(
                    (item, columns)
                )

            if {
                "ventaid",
                "estatus",
            }.issubset(columns):
                sales_candidates.append(
                    (item, columns)
                )

        valid = []

        for (
            product_item,
            product_columns,
        ) in product_candidates:

            for (
                detail_item,
                detail_columns,
            ) in detail_candidates:

                for (
                    sales_item,
                    sales_columns,
                ) in sales_candidates:

                    names = {
                        _norm(
                            f"{product_item.get('schema')}."
                            f"{product_item.get('name')}"
                        ),
                        _norm(
                            f"{detail_item.get('schema')}."
                            f"{detail_item.get('name')}"
                        ),
                        _norm(
                            f"{sales_item.get('schema')}."
                            f"{sales_item.get('name')}"
                        ),
                    }

                    if len(names) != 3:
                        continue

                    valid.append(
                        {
                            "product":
                                product_item,
                            "product_columns":
                                product_columns,
                            "detail":
                                detail_item,
                            "detail_columns":
                                detail_columns,
                            "sales":
                                sales_item,
                            "sales_columns":
                                sales_columns,
                        }
                    )

        if len(valid) != 1:
            return None

        return valid[0]


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

    @staticmethod
    def _sales_validity_bindings(
        analytic_bindings: Optional[
            List[Dict[str, Any]]
        ],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        for raw in (
            analytic_bindings
            or []
        ):
            binding = dict(
                raw or {}
            )

            if (
                str(
                    binding.get(
                        "rule_type"
                    )
                    or ""
                ).strip().lower()
                != "row_filter"
            ):
                continue

            target = (
                _norm(
                    binding.get(
                        "target"
                    )
                )
                .replace(
                    " ",
                    "_",
                )
            )

            if target != "sales_valid":
                continue

            rule = dict(
                binding.get("rule")
                or {}
            )

            if (
                str(
                    rule.get("status")
                    or ""
                ).upper()
                != "VALIDADO"
            ):
                continue

            if not rule.get(
                "active",
                True,
            ):
                continue

            output.append(
                {
                    **binding,
                    "rule": rule,
                }
            )

        return output

    @classmethod
    def _compile_sales_row_filters(
        cls,
        analytic_bindings: Optional[
            List[Dict[str, Any]]
        ],
        sales_columns: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        bindings = (
            cls._sales_validity_bindings(
                analytic_bindings
            )
        )

        if not bindings:
            return None

        parameters: List[Any] = []
        sql_parts: List[str] = []
        rules: List[Dict[str, Any]] = []

        operator_sql = {
            ast.Eq: "=",
            ast.NotEq: "<>",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Lt: "<",
            ast.LtE: "<=",
        }

        def compile_node(
            node: ast.AST,
        ) -> str:
            if isinstance(
                node,
                ast.BoolOp,
            ):
                if isinstance(
                    node.op,
                    ast.And,
                ):
                    joiner = " AND "
                elif isinstance(
                    node.op,
                    ast.Or,
                ):
                    joiner = " OR "
                else:
                    raise ValueError(
                        "BOOLEAN_OPERATOR_NOT_ALLOWED"
                    )

                if not node.values:
                    raise ValueError(
                        "EMPTY_BOOLEAN_RULE"
                    )

                return (
                    "("
                    + joiner.join(
                        compile_node(value)
                        for value
                        in node.values
                    )
                    + ")"
                )

            if isinstance(
                node,
                ast.Compare,
            ):
                if (
                    len(node.ops) != 1
                    or len(
                        node.comparators
                    ) != 1
                ):
                    raise ValueError(
                        "CHAINED_COMPARISON_NOT_ALLOWED"
                    )

                if not isinstance(
                    node.left,
                    ast.Name,
                ):
                    raise ValueError(
                        "FILTER_LEFT_SIDE_MUST_BE_COLUMN"
                    )

                right = (
                    node.comparators[0]
                )

                if not isinstance(
                    right,
                    ast.Constant,
                ):
                    raise ValueError(
                        "FILTER_RIGHT_SIDE_MUST_BE_LITERAL"
                    )

                column = (
                    sales_columns.get(
                        _norm(
                            node.left.id
                        )
                    )
                )

                if not column:
                    raise ValueError(
                        "FILTER_COLUMN_NOT_IN_GOVERNED_SALES_OBJECT"
                    )

                op_type = type(
                    node.ops[0]
                )

                if op_type not in operator_sql:
                    raise ValueError(
                        "COMPARISON_OPERATOR_NOT_ALLOWED"
                    )

                operator = (
                    operator_sql[
                        op_type
                    ]
                )

                value = right.value

                if value is None:
                    if op_type is ast.Eq:
                        return (
                            f"v.[{column}] "
                            "IS NULL"
                        )

                    if op_type is ast.NotEq:
                        return (
                            f"v.[{column}] "
                            "IS NOT NULL"
                        )

                    raise ValueError(
                        "NULL_OPERATOR_NOT_ALLOWED"
                    )

                if not isinstance(
                    value,
                    (
                        str,
                        int,
                        float,
                        bool,
                    ),
                ):
                    raise ValueError(
                        "FILTER_LITERAL_TYPE_NOT_ALLOWED"
                    )

                parameters.append(
                    value
                )

                return (
                    f"v.[{column}] "
                    f"{operator} ?"
                )

            raise ValueError(
                "RULE_AST_NOT_TRANSLATABLE_TO_SQL"
            )

        for binding in bindings:
            rule = dict(
                binding.get("rule")
                or {}
            )

            expression = str(
                rule.get("expression")
                or ""
            ).strip()

            if not expression:
                raise ValueError(
                    "EMPTY_VALIDATED_ROW_FILTER"
                )

            try:
                tree = ast.parse(
                    expression,
                    mode="eval",
                )
            except SyntaxError as exc:
                raise ValueError(
                    "INVALID_VALIDATED_ROW_FILTER"
                ) from exc

            sql_parts.append(
                compile_node(
                    tree.body
                )
            )

            rules.append(
                {
                    "rule_id":
                        rule.get("id"),
                    "name":
                        rule.get("name"),
                    "version":
                        rule.get("version"),
                    "target":
                        binding.get(
                            "target"
                        ),
                    "priority":
                        binding.get(
                            "priority"
                        ),
                    "expression":
                        expression,
                    "source_type":
                        rule.get(
                            "source_type"
                        ),
                    "source_ref":
                        rule.get(
                            "source_ref"
                        ),
                }
            )

        return {
            "sql": (
                "("
                + ") AND (".join(
                    sql_parts
                )
                + ")"
            ),
            "parameters":
                parameters,
            "rules":
                rules,
            "compiler":
                R10_30_GOVERNED_ROW_FILTER_VERSION,
        }

    def _business_semantics_blocked(
        self,
        *,
        started: float,
        reason: str,
    ) -> Dict[str, Any]:
        return self._result(
            answer=(
                "La consulta requiere una "
                "regla empresarial VALIDADA "
                "para determinar qué ventas "
                "son válidas antes de calcular "
                "el ranking."
            ),
            structured=False,
            fast_path=(
                "governed_sql_blocked"
            ),
            elapsed_ms=(
                (
                    time.perf_counter()
                    - started
                )
                * 1000
            ),
            governance={
                "read_only": True,
                "allowlist_enforced":
                    True,
                "fail_closed": True,
                "business_semantics_required":
                    True,
                "business_row_filter_applied":
                    False,
                "reason":
                    reason,
                "llm_sql_generation":
                    False,
            },
        )

    def resolve(
        self,
        *,
        scope: Dict[str, Any],
        question: str,
        analytic_bindings: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> Optional[Dict[str, Any]]:
        top_products_intent = (
            self._top_products_intent(
                question
            )
        )

        count_intent = (
            self._count_intent(
                question
            )
        )

        if (
            not top_products_intent
            and not count_intent
        ):
            return None

        started = time.perf_counter()

        try:
            profiles = self._profiles(
                scope
            )
        except EnterpriseSqlError:
            return None

        if not profiles:
            return None

        profile = None
        table = None
        state = "NO_MATCH"
        executor = None
        top_context = None
        governed_filter = {
            "sql": "",
            "parameters": [],
            "rules": [],
            "compiler": None,
        }

        if top_products_intent:
            matches = []

            for candidate_profile in profiles:
                connection_id = str(
                    candidate_profile.get(
                        "connection_id"
                    )
                    or ""
                ).strip()

                if not connection_id:
                    continue

                try:
                    candidate_executor = (
                        EnterpriseSqlExecutor(
                            self.store,
                            self.provider_factory(),
                        )
                    )

                    discovery = (
                        candidate_executor.discover(
                            scope,
                            connection_id,
                        )
                    )
                except EnterpriseSqlError:
                    continue

                relational = (
                    self._top_products_objects(
                        list(
                            discovery.get(
                                "objects"
                            )
                            or []
                        )
                    )
                )

                if relational is None:
                    continue

                matches.append(
                    (
                        candidate_profile,
                        candidate_executor,
                        relational,
                    )
                )

            if len(matches) == 1:
                (
                    profile,
                    executor,
                    top_context,
                ) = matches[0]

                state = "MATCHED"

            elif len(matches) > 1:
                state = "AMBIGUOUS"

            else:
                return None

        else:
            (
                profile,
                table,
                state,
            ) = self._select(
                question,
                profiles,
            )

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000

        if state == "NO_MATCH":
            return None

        if state == "NOT_ALLOWED":
            return self._result(
                answer=(
                    "La fuente solicitada "
                    "no está autorizada "
                    "para esta consulta."
                ),
                structured=False,
                fast_path=(
                    "governed_sql_blocked"
                ),
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced":
                        True,
                    "fail_closed": True,
                },
            )

        if (
            state == "AMBIGUOUS"
            or profile is None
        ):
            return self._result(
                answer=(
                    "Hay más de una fuente "
                    "posible. Indica cuál "
                    "deseas consultar."
                ),
                structured=False,
                fast_path=(
                    "governed_sql_ambiguous"
                ),
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced":
                        True,
                    "fail_closed": True,
                },
            )

        connection_id = str(
            profile.get(
                "connection_id"
            )
            or ""
        ).strip()

        if not connection_id:
            return None

        resource = ""
        analytic_kind = "count"

        if top_products_intent:
            if (
                executor is None
                or top_context is None
            ):
                return None

            product_item = (
                top_context["product"]
            )

            product_columns = (
                top_context[
                    "product_columns"
                ]
            )

            detail_item = (
                top_context["detail"]
            )

            detail_columns = (
                top_context[
                    "detail_columns"
                ]
            )

            sales_item = (
                top_context["sales"]
            )

            sales_columns = (
                top_context[
                    "sales_columns"
                ]
            )

            product_schema = str(
                product_item.get(
                    "schema"
                )
                or ""
            )

            product_table = str(
                product_item.get(
                    "name"
                )
                or ""
            )

            detail_schema = str(
                detail_item.get(
                    "schema"
                )
                or ""
            )

            detail_table = str(
                detail_item.get(
                    "name"
                )
                or ""
            )

            sales_schema = str(
                sales_item.get(
                    "schema"
                )
                or ""
            )

            sales_table = str(
                sales_item.get(
                    "name"
                )
                or ""
            )

            product_id = (
                product_columns[
                    "productoid"
                ]
            )

            product_name = (
                product_columns[
                    "nombre"
                ]
            )

            detail_product_id = (
                detail_columns[
                    "productoid"
                ]
            )

            quantity = (
                detail_columns[
                    "cantidad"
                ]
            )

            amount = (
                detail_columns[
                    "importe"
                ]
            )

            detail_sale_id = (
                detail_columns[
                    "ventaid"
                ]
            )

            sales_sale_id = (
                sales_columns[
                    "ventaid"
                ]
            )

            metric = (
                self._top_products_metric(
                    question
                )
            )

            order_expression = (
                f"SUM(d.[{amount}])"
                if metric == "importe"
                else
                f"SUM(d.[{quantity}])"
            )

            if analytic_bindings is not None:
                try:
                    compiled_filter = (
                        self._compile_sales_row_filters(
                            analytic_bindings,
                            sales_columns,
                        )
                    )
                except ValueError as exc:
                    return self._business_semantics_blocked(
                        started=started,
                        reason=str(exc),
                    )

                if compiled_filter is None:
                    return self._business_semantics_blocked(
                        started=started,
                        reason=(
                            "NO_VALIDATED_SALES_VALID_ROW_FILTER"
                        ),
                    )

                governed_filter = (
                    compiled_filter
                )

            filter_clause = (
                (
                    "WHERE "
                    + str(
                        governed_filter.get(
                            "sql"
                        )
                        or ""
                    )
                    + " "
                )
                if governed_filter.get(
                    "sql"
                )
                else ""
            )

            query_plan = {
                "operation": "SELECT",
                "sql": (
                    "SELECT TOP (10) "
                    f"p.[{product_name}] "
                    "AS [Producto], "
                    f"SUM(d.[{quantity}]) "
                    "AS [CantidadVendida], "
                    f"SUM(d.[{amount}]) "
                    "AS [ImporteVendido] "
                    f"FROM "
                    f"[{detail_schema}]"
                    f".[{detail_table}] "
                    "AS d "
                    f"JOIN "
                    f"[{product_schema}]"
                    f".[{product_table}] "
                    "AS p "
                    f"ON p.[{product_id}] "
                    f"= "
                    f"d.[{detail_product_id}] "
                    f"JOIN "
                    f"[{sales_schema}]"
                    f".[{sales_table}] "
                    "AS v "
                    f"ON v.[{sales_sale_id}] "
                    f"= "
                    f"d.[{detail_sale_id}] "
                    f"{filter_clause}"
                    f"GROUP BY "
                    f"p.[{product_id}], "
                    f"p.[{product_name}] "
                    f"ORDER BY "
                    f"{order_expression} "
                    "DESC, "
                    f"p.[{product_name}] "
                    "ASC"
                ),
                "parameters": list(
                    governed_filter.get(
                        "parameters"
                    )
                    or []
                ),
                "limit": 10,
                "timeout_seconds": int(
                    profile.get(
                        "timeout_seconds"
                    )
                    or 30
                ),
            }

            resource = (
                f"{detail_schema}."
                f"{detail_table},"
                f"{product_schema}."
                f"{product_table},"
                f"{sales_schema}."
                f"{sales_table}"
            )

            analytic_kind = (
                "top_products_by_importe"
                if metric == "importe"
                else
                "top_products_by_cantidad"
            )

        else:
            if table is None:
                return self._result(
                    answer=(
                        "Hay más de una fuente "
                        "posible. Indica cuál "
                        "deseas consultar."
                    ),
                    structured=False,
                    fast_path=(
                        "governed_sql_ambiguous"
                    ),
                    elapsed_ms=elapsed_ms,
                    governance={
                        "read_only": True,
                        "allowlist_enforced":
                            True,
                        "fail_closed": True,
                    },
                )

            (
                schema,
                object_name,
            ) = table.split(
                ".",
                1,
            )

            query_plan = {
                "operation": "SELECT",
                "sql": (
                    "SELECT COUNT_BIG(*) "
                    "AS TOTAL_REGISTROS "
                    f"FROM [{schema}]"
                    f".[{object_name}]"
                ),
                "parameters": [],
                "limit": 1,
                "timeout_seconds": int(
                    profile.get(
                        "timeout_seconds"
                    )
                    or 30
                ),
            }

            resource = object_name

        try:
            if executor is None:
                executor = (
                    EnterpriseSqlExecutor(
                        self.store,
                        self.provider_factory(),
                    )
                )

            routed = (
                answer_enterprise_question_orchestrated(
                    registry=None,
                    knowledge_store=None,
                    scope=scope,
                    question=question,
                    sql_context={
                        "connection_id":
                            connection_id,
                        "query_plan":
                            query_plan,
                    },
                    sql_executor=executor,
                    sql_scope=scope,
                )
            )

        except EnterpriseSqlError:
            elapsed_ms = (
                time.perf_counter()
                - started
            ) * 1000

            return self._result(
                answer=(
                    "No fue posible "
                    "consultar los datos "
                    "autorizados en este "
                    "momento."
                ),
                structured=False,
                fast_path=(
                    "governed_sql_blocked"
                ),
                elapsed_ms=elapsed_ms,
                governance={
                    "read_only": True,
                    "allowlist_enforced":
                        True,
                    "fail_closed": True,
                },
            )

        payload = dict(
            routed.get("answer") or {}
        )

        rows = list(
            payload.get("rows") or []
        )

        if top_products_intent:

            if not rows:
                answer = (
                    "No se encontraron "
                    "ventas para construir "
                    "el ranking de productos."
                )

            else:
                metric = (
                    self._top_products_metric(
                        question
                    )
                )

                heading = (
                    "Productos con mayor "
                    "importe vendido:"
                    if metric == "importe"
                    else
                    "Productos más vendidos "
                    "por cantidad:"
                )

                output = [heading]

                for index, row in enumerate(
                    rows[:10],
                    start=1,
                ):
                    if not isinstance(
                        row,
                        (list, tuple),
                    ):
                        continue

                    product = (
                        str(row[0])
                        if len(row) > 0
                        else ""
                    )

                    quantity_value = (
                        row[1]
                        if len(row) > 1
                        else None
                    )

                    amount_value = (
                        row[2]
                        if len(row) > 2
                        else None
                    )

                    detail = (
                        f"{index}. {product}"
                    )

                    if (
                        quantity_value
                        is not None
                    ):
                        detail += (
                            f": "
                            f"{quantity_value} "
                            "unidades"
                        )

                    if (
                        amount_value
                        is not None
                    ):
                        detail += (
                            f"; importe "
                            f"{amount_value}"
                        )

                    output.append(
                        detail
                    )

                answer = "\n".join(
                    output
                )

        else:
            if (
                not rows
                or not isinstance(
                    rows[0],
                    (list, tuple),
                )
                or not rows[0]
            ):
                value = None
            else:
                value = rows[0][0]

            if value is None:
                answer = (
                    "La consulta se "
                    "completó, pero no "
                    "devolvió un total."
                )

            else:
                requested = (
                    self._requested_label(
                        question
                    )
                )

                answer = (
                    f"{requested}={value}"
                    if requested
                    else
                    f"Total de registros: "
                    f"{value}"
                )

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000

        governance = dict(
            routed.get(
                "governance"
            )
            or {}
        )

        governance.update(
            {
                "read_only": True,
                "allowlist_enforced":
                    True,
                "fail_closed": True,
                "sql_execution_authority":
                    "governed_executor",
                "analytic_kind":
                    analytic_kind,
                "llm_sql_generation":
                    False,
                "llm_computational_authority":
                    False,
            }
        )

        if top_products_intent:
            applied_rules = list(
                governed_filter.get(
                    "rules"
                )
                or []
            )

            governance.update(
                {
                    "business_row_filter_applied":
                        bool(
                            applied_rules
                        ),
                    "business_semantics_authority":
                        (
                            "validated_analytic_row_filter"
                            if applied_rules
                            else
                            "legacy_direct_bridge"
                        ),
                    "business_row_filters":
                        applied_rules,
                    "sql_rule_compiler":
                        governed_filter.get(
                            "compiler"
                        ),
                }
            )

        return self._result(
            answer=answer,
            structured=True,
            fast_path="governed_sql",
            sources=[
                {
                    "type":
                        "connected_data",
                    "name":
                        "Datos conectados",
                    "resource":
                        resource,
                    "read_only":
                        True,
                }
            ],
            elapsed_ms=elapsed_ms,
            governance=governance,
        )
