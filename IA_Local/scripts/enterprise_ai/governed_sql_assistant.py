from __future__ import annotations

import ast
import re
import time
import unicodedata
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from enterprise_agent_orchestrator import answer_enterprise_question_orchestrated
from enterprise_sql_gateway import EnterpriseSqlError, EnterpriseSqlExecutor


R10_24C2_GOVERNED_SQL_ASSISTANT_VERSION = "r10.24c2.1"
R10_30_GOVERNED_ROW_FILTER_VERSION = "r10.30-row-filter-v1"
R10_31_SEMANTIC_ANALYTICS_VERSION = "r10.31-semantic-plan-v1"
R10_32_SALES_DETAIL_VERSION = "r10.32-sales-detail-v1"
R10_33_SALES_DETAIL_PAGINATION_VERSION = (
    "r10.33-sales-detail-pagination-v1"
)

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


class SemanticAnalyticsPlan:
    """Governed semantic plan. It contains no SQL."""

    def __init__(
        self,
        *,
        domain: str,
        entity: str,
        operation: str,
        metric: str,
        direction: str,
        limit: int = 10,
        period: Optional[
            Dict[str, Any]
        ] = None,
    ) -> None:
        self.domain = domain
        self.entity = entity
        self.operation = operation
        self.metric = metric
        self.direction = direction
        self.limit = int(limit)
        self.period = (
            dict(period)
            if period is not None
            else None
        )

    def as_dict(self) -> Dict[str, Any]:
        output = {
            "version":
                R10_31_SEMANTIC_ANALYTICS_VERSION,
            "domain":
                self.domain,
            "entity":
                self.entity,
            "operation":
                self.operation,
            "metric":
                self.metric,
            "direction":
                self.direction,
            "limit":
                self.limit,
        }

        if self.period is not None:
            output["period"] = dict(
                self.period
            )

        return output


class SemanticAnalyticsPlanner:
    """Constrained natural-language to business-plan mapper."""

    @staticmethod
    def plan(
        question: str,
    ) -> Optional[SemanticAnalyticsPlan]:
        normalized = _norm(
            question
        )

        seller_cue = any(
            cue in normalized
            for cue in (
                "persona",
                "vendedor",
                "vendedora",
                "vendedores",
                "vendedoras",
                "quien",
                "quienes",
            )
        )

        sales_cue = any(
            cue in normalized
            for cue in (
                "vendido",
                "vendio",
                "vendieron",
                "vende",
                "venden",
                "ventas",
            )
        )

        ranking_cue = any(
            cue in normalized
            for cue in (
                "mas vendido",
                "vendido mas",
                "vendio mas",
                "vendieron mas",
                "vende mas",
                "venden mas",
                "mas ventas",
                "mayor venta",
                "mayores ventas",
                "mejor vendedor",
                "mejor vendedora",
            )
        )

        if (
            seller_cue
            and sales_cue
            and ranking_cue
        ):
            cardinality = (
                _ranking_cardinality_hint(
                    question
                )
            )

            if (
                cardinality is not None
                and (
                    cardinality < 1
                    or cardinality > 50
                )
            ):
                return None

            return SemanticAnalyticsPlan(
                domain="sales",
                entity="seller",
                operation="ranking",
                metric="sales_amount",
                direction="desc",
                limit=(
                    cardinality
                    if cardinality is not None
                    else 10
                ),
            )

        return None


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text.lower()).strip()



def _sales_detail_explicit_limit(
    question: str,
) -> Tuple[bool, Optional[int]]:
    """Return explicit sales-detail limit and validity."""

    normalized = _norm(
        question
    )

    match = re.search(
        r"\b(\d{1,9})\s+ventas?"
        r"(?:\s+detalladas?)?\b",
        normalized,
    )

    if match is None:
        return (
            False,
            None,
        )

    value = int(
        match.group(1)
    )

    if value < 1 or value > 500:
        return (
            True,
            None,
        )

    return (
        True,
        value,
    )


def _sales_detail_page_request(
    question: str,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Parse an explicit terminal governed sales-detail page suffix."""

    raw = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()

    normalized = _norm(
        raw
    )

    page_cue_present = bool(
        re.search(
            r"\bpagina\b",
            normalized,
        )
    )

    if not page_cue_present:
        return (
            False,
            None,
            raw,
        )

    match = re.search(
        r"(?:^|\s)p[áa]gina\s+(\d{1,9})\s*$",
        raw,
        flags=re.IGNORECASE,
    )

    if match is None:
        return (
            True,
            None,
            None,
        )

    page = int(
        match.group(1)
    )

    if page < 1 or page > 1000:
        return (
            True,
            None,
            None,
        )

    base_question = (
        raw[
            :match.start()
        ]
        .strip()
    )

    if not base_question:
        return (
            True,
            None,
            None,
        )

    return (
        True,
        page,
        base_question,
    )


def _sales_detail_period_payload(
    question: str,
) -> Optional[Dict[str, Any]]:
    """Parse deterministic bounded sales-detail periods."""

    normalized = _norm(
        question
    )

    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    month_pattern = (
        r"\b("
        + "|".join(
            months.keys()
        )
        + r")"
        + r"(?:\s+de)?\s+"
        + r"((?:19|20)\d{2})\b"
    )

    match = re.search(
        month_pattern,
        normalized,
    )

    if match is not None:
        return {
            "kind": "month",
            "year": int(
                match.group(2)
            ),
            "month": months[
                match.group(1)
            ],
        }

    range_match = re.search(
        (
            r"\b(?:del|desde)\s+"
            r"(\d{4}-\d{2}-\d{2})\s+"
            r"(?:al|hasta)\s+"
            r"(\d{4}-\d{2}-\d{2})\b"
        ),
        normalized,
    )

    if range_match is not None:
        return {
            "kind": "range",
            "start":
                range_match.group(1),
            "end":
                range_match.group(2),
        }

    today = date.today()

    if "este mes" in normalized:
        return {
            "kind": "month",
            "year": today.year,
            "month": today.month,
        }

    if (
        "mes pasado" in normalized
        or "mes anterior" in normalized
    ):
        first_this_month = date(
            today.year,
            today.month,
            1,
        )

        previous_day = (
            first_this_month
            - timedelta(days=1)
        )

        return {
            "kind": "month",
            "year":
                previous_day.year,
            "month":
                previous_day.month,
        }

    if (
        "este ano" in normalized
    ):
        return {
            "kind": "year",
            "year": today.year,
        }

    if (
        "ano pasado" in normalized
        or "ano anterior" in normalized
    ):
        return {
            "kind": "year",
            "year": today.year - 1,
        }

    year_match = re.search(
        r"\b((?:19|20)\d{2})\b",
        normalized,
    )

    if year_match is not None:
        return {
            "kind": "year",
            "year": int(
                year_match.group(1)
            ),
        }

    return None


def _sales_detail_seller(
    question: str,
) -> Tuple[bool, Optional[str]]:
    """Extract an exact parameterized seller value when present."""

    raw = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()

    patterns = (
        (
            r"\bventas?"
            r"(?:\s+detalladas?)?"
            r"\s+de\s+(.+)$"
        ),
        (
            r"\b(?:que\s+)?productos?"
            r"\s+vend(?:io|ió)\s+(.+)$"
        ),
        (
            r"\bproductos?\s+que\s+"
            r"vend(?:io|ió)\s+(.+)$"
        ),
    )

    match = None

    for pattern in patterns:
        match = re.search(
            pattern,
            raw,
            flags=re.IGNORECASE,
        )

        if match is not None:
            break

    if match is None:
        return (
            False,
            None,
        )

    candidate = (
        match.group(1)
        .strip()
        .strip(" .,:")
    )

    month_suffix = (
        r"\s+de\s+"
        r"(?:enero|febrero|marzo|abril|mayo|junio|"
        r"julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"(?:\s+de)?\s+(?:19|20)\d{2}\s*$"
    )

    candidate = re.sub(
        month_suffix,
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()

    relative_suffix = (
        r"\s+(?:de\s+)?"
        r"(?:este mes|mes pasado|mes anterior|"
        r"este a(?:ñ|n)o|a(?:ñ|n)o pasado|a(?:ñ|n)o anterior)"
        r"\s*$"
    )

    candidate = re.sub(
        relative_suffix,
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()

    normalized_candidate = _norm(
        candidate
    )

    period_only = (
        normalized_candidate
        in {
            "este mes",
            "mes pasado",
            "mes anterior",
            "este ano",
            "ano pasado",
            "ano anterior",
        }
        or bool(
            re.fullmatch(
                r"(?:19|20)\d{2}",
                normalized_candidate,
            )
        )
        or bool(
            re.fullmatch(
                (
                    r"(?:enero|febrero|marzo|abril|mayo|junio|"
                    r"julio|agosto|septiembre|octubre|noviembre|diciembre)"
                    r"(?:\s+de)?\s+(?:19|20)\d{2}"
                ),
                normalized_candidate,
            )
        )
    )

    if period_only:
        return (
            False,
            None,
        )

    if not candidate:
        return (
            False,
            None,
        )

    unsafe_tokens = (
        "--",
        "/*",
        "*/",
        ";",
        "=",
        "\x00",
    )

    if any(
        token in candidate
        for token in unsafe_tokens
    ):
        return (
            True,
            None,
        )

    if len(candidate) > 80:
        return (
            True,
            None,
        )

    if re.fullmatch(
        (
            r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]"
            r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'\-]{0,79}"
        ),
        candidate,
    ) is None:
        return (
            True,
            None,
        )

    return (
        True,
        candidate,
    )


def _sales_detail_mode(
    question: str,
) -> Optional[str]:
    """Choose deterministic sale-header or line-item mode."""

    normalized = _norm(
        question
    )

    sales_cue = bool(
        re.search(
            r"\bventas?\b",
            normalized,
        )
    )

    product_by_seller = bool(
        re.search(
            (
                r"\b(?:que\s+)?productos?"
                r"\s+vendio\b"
            ),
            normalized,
        )
        or re.search(
            (
                r"\bproductos?\s+que\s+"
                r"vendio\b"
            ),
            normalized,
        )
    )

    explicit_detail = any(
        cue in normalized
        for cue in (
            "ventas detalladas",
            "venta detallada",
            "detalle de ventas",
        )
    )

    explicit_line_fields = (
        sales_cue
        and "cliente" in normalized
        and "producto" in normalized
        and (
            "cantidad" in normalized
            or "importe" in normalized
        )
    )

    if (
        product_by_seller
        or explicit_detail
        or explicit_line_fields
    ):
        return "line_item"

    if not sales_cue:
        return None

    simple_list = any(
        cue in normalized
        for cue in (
            "lista de ventas",
            "lista las ventas",
            "listar ventas",
        )
    )

    action_list = bool(
        re.search(
            (
                r"\b(?:dame|muestrame|pasame)"
                r"\s+(?:las\s+)?"
                r"(?:\d+\s+)?ventas?\b"
            ),
            normalized,
        )
    )

    (
        seller_requested,
        _,
    ) = _sales_detail_seller(
        question
    )

    period_requested = (
        _sales_detail_period_payload(
            question
        )
        is not None
    )

    (
        limit_requested,
        _,
    ) = _sales_detail_explicit_limit(
        question
    )

    if (
        simple_list
        or action_list
        or seller_requested
        or period_requested
        or limit_requested
    ):
        return "sale"

    return None


def _sales_detail_intent(
    question: str,
) -> bool:
    """Recognize deterministic governed sales-list requests."""

    return (
        _sales_detail_mode(
            question
        )
        is not None
    )


def _ranking_cardinality_hint(
    question: str,
) -> Optional[int]:
    normalized = _norm(question)

    if not normalized:
        return None

    ranking_entity = (
        r"(?:vendedor(?:es)?|vendedora(?:s)?|persona(?:s)?|"
        r"cliente(?:s)?|sucursal(?:es)?|sede(?:s)?|tienda(?:s)?|"
        r"producto(?:s)?|articulo(?:s)?)"
    )

    singular_entity = (
        r"(?:vendedor|vendedora|persona|cliente|sucursal|"
        r"sede|tienda|producto|articulo)"
    )

    explicit_patterns = (
        r"\btop\s+(\d{1,3})\b",
        r"\b(?:los|las)\s+(\d{1,3})\s+"
        + ranking_entity
        + r"\b",
        r"\b(\d{1,3})\s+"
        + ranking_entity
        + r"\b",
    )

    for pattern in explicit_patterns:
        match = re.search(
            pattern,
            normalized,
        )

        if match:
            return int(
                match.group(1)
            )

    singular_subject = (
        re.search(
            (
                r"\b(?:que|cual)\s+"
                + singular_entity
                + r"\b"
            ),
            normalized,
        )
        or re.search(
            (
                r"\bcual\s+es\s+(?:el|la)\s+"
                + singular_entity
                + r"\b"
            ),
            normalized,
        )
    )

    singular_superlative = re.search(
        r"\b(?:el|la)\s+(?:mayor|menor|mejor|peor)\b",
        normalized,
    )

    singular_comparative = re.search(
        r"\b(?:mas|menos)\b",
        normalized,
    )

    if singular_subject and (
        singular_superlative
        or singular_comparative
    ):
        return 1

    return None


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
        semantic_plan_resolver: Optional[
            Callable[
                [str],
                Optional[Dict[str, Any]],
            ]
        ] = None,
    ) -> None:
        self.store = store
        self.provider_factory = provider_factory
        self.semantic_plan_resolver = (
            semantic_plan_resolver
        )

    @staticmethod
    def _validated_period(
        payload: Any,
    ) -> Optional[Dict[str, str]]:
        if not isinstance(
            payload,
            dict,
        ):
            return None

        kind = str(
            payload.get("kind")
            or ""
        ).strip().lower()

        try:
            if kind == "month":
                if set(payload.keys()) != {
                    "kind",
                    "year",
                    "month",
                }:
                    return None

                year = payload.get(
                    "year"
                )

                month = payload.get(
                    "month"
                )

                if (
                    isinstance(year, bool)
                    or isinstance(month, bool)
                    or not isinstance(year, int)
                    or not isinstance(month, int)
                ):
                    return None

                if (
                    year < 1900
                    or year > 9998
                    or month < 1
                    or month > 12
                ):
                    return None

                start = date(
                    year,
                    month,
                    1,
                )

                if month == 12:
                    end = date(
                        year + 1,
                        1,
                        1,
                    )
                else:
                    end = date(
                        year,
                        month + 1,
                        1,
                    )

            elif kind == "year":
                if set(payload.keys()) != {
                    "kind",
                    "year",
                }:
                    return None

                year = payload.get(
                    "year"
                )

                if (
                    isinstance(year, bool)
                    or not isinstance(year, int)
                    or year < 1900
                    or year > 9998
                ):
                    return None

                start = date(
                    year,
                    1,
                    1,
                )

                end = date(
                    year + 1,
                    1,
                    1,
                )

            elif kind == "range":
                if set(payload.keys()) != {
                    "kind",
                    "start",
                    "end",
                }:
                    return None

                start = date.fromisoformat(
                    str(
                        payload.get(
                            "start"
                        )
                        or ""
                    )
                )

                inclusive_end = (
                    date.fromisoformat(
                        str(
                            payload.get(
                                "end"
                            )
                            or ""
                        )
                    )
                )

                if inclusive_end < start:
                    return None

                end = (
                    inclusive_end
                    + timedelta(days=1)
                )

            else:
                return None

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        return {
            "kind":
                kind,
            "start":
                start.isoformat(),
            "end_exclusive":
                end.isoformat(),
        }

    @staticmethod
    def _time_period_hint(
        question: str,
    ) -> bool:
        normalized = _norm(
            question
        )

        if re.search(
            r"\b(?:19|20)\d{2}\b",
            normalized,
        ):
            return True

        if re.search(
            r"\b\d{4}-\d{2}-\d{2}\b",
            normalized,
        ):
            return True

        month_names = (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )

        month_pattern = (
            r"\b(?:"
            + "|".join(
                month_names
            )
            + r")\b"
        )

        if re.search(
            month_pattern,
            normalized,
        ):
            return True

        relative_period_cues = (
            "este mes",
            "mes pasado",
            "mes anterior",
            "este ano",
            "ano pasado",
            "ano anterior",
            "este trimestre",
            "trimestre pasado",
            "esta semana",
            "semana pasada",
            "semana anterior",
            "hoy",
            "ayer",
            "periodo",
        )

        return any(
            cue in normalized
            for cue in relative_period_cues
        )

    @staticmethod
    def _validated_external_semantic_plan(
        payload: Any,
        question: str = "",
    ) -> Optional[SemanticAnalyticsPlan]:
        if not isinstance(
            payload,
            dict,
        ):
            return None

        # limit is a bounded presentation parameter, not
        # semantic or SQL authority. A local model may omit it.
        # Recover cardinality only from explicit ranking counts
        # or an unambiguous singular ranking request.
        question_limit = (
            _ranking_cardinality_hint(
                question
            )
        )

        if "limit" not in payload:
            payload = dict(payload)
            payload["limit"] = (
                question_limit
                if question_limit is not None
                else 10
            )

        required_keys = {
            "domain",
            "entity",
            "operation",
            "metric",
            "direction",
            "limit",
        }

        supported_present = (
            "supported"
            in payload
        )

        if supported_present:
            supported_value = (
                payload.get(
                    "supported"
                )
            )

            if supported_value is not True:
                return None

        payload_keys = set(
            payload.keys()
        )

        payload_keys.discard(
            "supported"
        )

        allowed_without_period = (
            required_keys
        )

        allowed_with_period = (
            required_keys
            | {
                "period",
            }
        )

        if payload_keys not in {
            frozenset(
                allowed_without_period
            ),
            frozenset(
                allowed_with_period
            ),
        }:
            return None

        domain = str(
            payload.get("domain")
            or ""
        ).strip().lower()

        entity = str(
            payload.get("entity")
            or ""
        ).strip().lower()

        operation = str(
            payload.get("operation")
            or ""
        ).strip().lower()

        metric = str(
            payload.get("metric")
            or ""
        ).strip().lower()

        direction = str(
            payload.get("direction")
            or ""
        ).strip().lower()

        limit = payload.get(
            "limit"
        )

        if isinstance(
            limit,
            bool,
        ):
            return None

        if not isinstance(
            limit,
            int,
        ):
            return None

        if limit < 1 or limit > 50:
            return None

        if question_limit is not None:
            if (
                question_limit < 1
                or question_limit > 50
            ):
                return None

            limit = question_limit

        supported_metrics = {
            "seller": {
                "sales_amount",
                "transaction_count",
            },
            "customer": {
                "sales_amount",
                "transaction_count",
            },
            "branch": {
                "sales_amount",
                "transaction_count",
            },
            "product": {
                "sales_amount",
                "quantity",
            },
        }

        supported = (
            domain == "sales"
            and operation == "ranking"
            and entity in supported_metrics
            and metric
            in supported_metrics[entity]
            and direction in {
                "asc",
                "desc",
            }
        )

        if not supported:
            return None

        period = None

        if "period" in payload:
            period = (
                GovernedSqlAssistantBridge
                ._validated_period(
                    payload.get(
                        "period"
                    )
                )
            )

            if period is None:
                return None

        return SemanticAnalyticsPlan(
            domain=domain,
            entity=entity,
            operation=operation,
            metric=metric,
            direction=direction,
            limit=limit,
            period=period,
        )

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
    def _sales_header_objects(
        cls,
        objects: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Resolve only the metadata required for sale-header mode."""

        sales_candidates = []
        customer_candidates = []

        for item in objects:
            schema = str(
                item.get("schema")
                or ""
            ).strip()

            name = str(
                item.get("name")
                or ""
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
                "ventaid",
                "folio",
                "clienteid",
                "fechaventa",
                "vendedor",
                "sucursal",
                "estatus",
                "subtotal",
                "iva",
                "total",
            }.issubset(columns):
                sales_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "clienteid",
                "nombre",
            }.issubset(columns):
                customer_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

        if (
            len(sales_candidates) != 1
            or len(customer_candidates) != 1
        ):
            return None

        sales_item, sales_columns = (
            sales_candidates[0]
        )

        customer_item, customer_columns = (
            customer_candidates[0]
        )

        names = {
            _norm(
                f"{sales_item.get('schema')}."
                f"{sales_item.get('name')}"
            ),
            _norm(
                f"{customer_item.get('schema')}."
                f"{customer_item.get('name')}"
            ),
        }

        if len(names) != 2:
            return None

        return {
            "sales":
                sales_item,
            "sales_columns":
                sales_columns,
            "customer":
                customer_item,
            "customer_columns":
                customer_columns,
        }


    @classmethod
    def _sales_detail_objects(
        cls,
        objects: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        sales_candidates = []
        customer_candidates = []
        detail_candidates = []
        product_candidates = []

        for item in objects:
            schema = str(
                item.get("schema")
                or ""
            ).strip()

            name = str(
                item.get("name")
                or ""
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
                "ventaid",
                "folio",
                "clienteid",
                "fechaventa",
                "vendedor",
                "sucursal",
                "estatus",
                "subtotal",
                "iva",
                "total",
            }.issubset(columns):
                sales_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "clienteid",
                "nombre",
            }.issubset(columns):
                customer_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "detalleventaid",
                "ventaid",
                "productoid",
                "cantidad",
                "preciounitario",
                "importe",
            }.issubset(columns):
                detail_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "productoid",
                "nombre",
            }.issubset(columns):
                product_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

        if (
            len(sales_candidates) != 1
            or len(customer_candidates) != 1
            or len(detail_candidates) != 1
            or len(product_candidates) != 1
        ):
            return None

        sales_item, sales_columns = (
            sales_candidates[0]
        )

        customer_item, customer_columns = (
            customer_candidates[0]
        )

        detail_item, detail_columns = (
            detail_candidates[0]
        )

        product_item, product_columns = (
            product_candidates[0]
        )

        names = {
            _norm(
                f"{sales_item.get('schema')}."
                f"{sales_item.get('name')}"
            ),
            _norm(
                f"{customer_item.get('schema')}."
                f"{customer_item.get('name')}"
            ),
            _norm(
                f"{detail_item.get('schema')}."
                f"{detail_item.get('name')}"
            ),
            _norm(
                f"{product_item.get('schema')}."
                f"{product_item.get('name')}"
            ),
        }

        if len(names) != 4:
            return None

        return {
            "sales":
                sales_item,
            "sales_columns":
                sales_columns,
            "customer":
                customer_item,
            "customer_columns":
                customer_columns,
            "detail":
                detail_item,
            "detail_columns":
                detail_columns,
            "product":
                product_item,
            "product_columns":
                product_columns,
        }


    @classmethod
    def _semantic_analytics_objects(
        cls,
        objects: List[Dict[str, Any]],
        entity: str,
    ) -> Optional[Dict[str, Any]]:
        sales_candidates = []
        customer_candidates = []
        product_candidates = []
        detail_candidates = []

        for item in objects:
            schema = str(
                item.get("schema")
                or ""
            ).strip()

            name = str(
                item.get("name")
                or ""
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
                "ventaid",
                "estatus",
                "total",
                "clienteid",
                "vendedor",
                "sucursal",
            }.issubset(columns):
                sales_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "clienteid",
                "nombre",
            }.issubset(columns):
                customer_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "productoid",
                "nombre",
            }.issubset(columns):
                product_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

            if {
                "ventaid",
                "productoid",
                "cantidad",
                "importe",
            }.issubset(columns):
                detail_candidates.append(
                    (
                        item,
                        columns,
                    )
                )

        if len(sales_candidates) != 1:
            return None

        sales_item, sales_columns = (
            sales_candidates[0]
        )

        if entity in {
            "seller",
            "branch",
        }:
            return {
                "sales":
                    sales_item,
                "sales_columns":
                    sales_columns,
            }

        if entity == "customer":
            if len(customer_candidates) != 1:
                return None

            customer_item, customer_columns = (
                customer_candidates[0]
            )

            return {
                "sales":
                    sales_item,
                "sales_columns":
                    sales_columns,
                "customer":
                    customer_item,
                "customer_columns":
                    customer_columns,
            }

        if entity == "product":
            if (
                len(product_candidates) != 1
                or len(detail_candidates) != 1
            ):
                return None

            product_item, product_columns = (
                product_candidates[0]
            )

            detail_item, detail_columns = (
                detail_candidates[0]
            )

            return {
                "sales":
                    sales_item,
                "sales_columns":
                    sales_columns,
                "product":
                    product_item,
                "product_columns":
                    product_columns,
                "detail":
                    detail_item,
                "detail_columns":
                    detail_columns,
            }

        return None

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
                "el análisis."
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
        semantic_plan = (
            SemanticAnalyticsPlanner.plan(
                question
            )
        )

        semantic_plan_source = (
            "deterministic"
            if semantic_plan is not None
            else None
        )

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

        (
            detail_page_requested,
            detail_page,
            detail_page_question,
        ) = _sales_detail_page_request(
            question
        )

        detail_parse_question = (
            detail_page_question
            if detail_page_question
            is not None
            else question
        )

        sales_detail_mode = (
            _sales_detail_mode(
                detail_parse_question
            )
        )

        sales_detail_intent = (
            sales_detail_mode
            is not None
        )

        (
            detail_limit_requested,
            detail_limit,
        ) = _sales_detail_explicit_limit(
            detail_parse_question
        )

        if not detail_limit_requested:
            detail_limit = 100

        (
            detail_seller_requested,
            detail_seller,
        ) = _sales_detail_seller(
            detail_parse_question
        )

        detail_period_payload = (
            _sales_detail_period_payload(
                detail_parse_question
            )
        )

        detail_period = None

        if detail_period_payload is not None:
            detail_period = (
                self._validated_period(
                    detail_period_payload
                )
            )

        temporal_hint = (
            self._time_period_hint(
                detail_parse_question
            )
        )

        semantic_enrichment_required = (
            temporal_hint
            and (
                semantic_plan is not None
                or top_products_intent
                or count_intent
            )
        )

        if (
            semantic_enrichment_required
            and not callable(
                self.semantic_plan_resolver
            )
        ):
            return None

        should_resolve_semantics = (
            callable(
                self.semantic_plan_resolver
            )
            and (
                semantic_enrichment_required
                or (
                    semantic_plan is None
                    and not top_products_intent
                    and not count_intent
                    and not sales_detail_intent
                )
            )
        )

        if should_resolve_semantics:
            try:
                proposed_plan = (
                    self.semantic_plan_resolver(
                        question
                    )
                )
            except Exception:
                return None

            resolved_plan = (
                self._validated_external_semantic_plan(
                    proposed_plan,
                    question,
                )
            )

            if resolved_plan is None:
                return None

            if (
                semantic_enrichment_required
                and resolved_plan.period
                is None
            ):
                return None

            semantic_plan = (
                resolved_plan
            )

            semantic_plan_source = (
                "llm_structured"
            )

        semantic_ranking_intent = (
            semantic_plan is not None
            and semantic_plan.domain == "sales"
            and semantic_plan.operation == "ranking"
            and semantic_plan.entity in {
                "seller",
                "customer",
                "branch",
                "product",
            }
            and semantic_plan.metric in {
                "sales_amount",
                "transaction_count",
                "quantity",
            }
            and semantic_plan.direction in {
                "asc",
                "desc",
            }
        )

        if (
            not semantic_ranking_intent
            and not top_products_intent
            and not count_intent
            and not sales_detail_intent
        ):
            return None

        started = time.perf_counter()

        def detail_blocked(
            reason: str,
            message: str,
        ) -> Dict[str, Any]:
            return self._result(
                answer=message,
                structured=False,
                fast_path="governed_sql_blocked",
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
                    "fail_closed":
                        True,
                    "reason": reason,
                    "llm_sql_generation":
                        False,
                    "llm_computational_authority":
                        False,
                },
            )

        if sales_detail_intent:
            if (
                detail_page_requested
                and detail_page is None
            ):
                return detail_blocked(
                    "SALES_DETAIL_PAGE_INVALID",
                    (
                        "La página solicitada para el detalle "
                        "de ventas no es válida. Debe ser un "
                        "número entre 1 y 1000 colocado al "
                        "final de la solicitud."
                    ),
                )

            if (
                detail_limit_requested
                and detail_limit is None
            ):
                return detail_blocked(
                    "SALES_DETAIL_LIMIT_INVALID",
                    (
                        "El límite solicitado para el detalle "
                        "de ventas no es válido. Debe estar "
                        "entre 1 y 500."
                    ),
                )

            if (
                detail_seller_requested
                and detail_seller is None
            ):
                return detail_blocked(
                    "SALES_DETAIL_SELLER_INVALID",
                    (
                        "El vendedor solicitado no pasó la "
                        "validación gobernada."
                    ),
                )

            if (
                temporal_hint
                and detail_period_payload
                is None
            ):
                return detail_blocked(
                    "SALES_DETAIL_PERIOD_UNSUPPORTED",
                    (
                        "El periodo solicitado fue reconocido, "
                        "pero no pudo normalizarse de forma "
                        "gobernada."
                    ),
                )

            if (
                detail_period_payload
                is not None
                and detail_period is None
            ):
                return detail_blocked(
                    "SALES_DETAIL_PERIOD_INVALID",
                    (
                        "El periodo solicitado no pasó la "
                        "validación gobernada."
                    ),
                )

        try:
            profiles = self._profiles(
                scope
            )
        except EnterpriseSqlError:
            if sales_detail_intent:
                return detail_blocked(
                    "SALES_DETAIL_PROFILE_DISCOVERY_FAILED",
                    (
                        "La solicitud de detalle de ventas "
                        "no pudo acceder a una fuente SQL "
                        "gobernada."
                    ),
                )

            return None

        if not profiles:
            if sales_detail_intent:
                return detail_blocked(
                    "SALES_DETAIL_SQL_PROFILE_NOT_AVAILABLE",
                    (
                        "La solicitud de detalle de ventas "
                        "requiere una fuente SQL gobernada "
                        "disponible."
                    ),
                )

            return None

        profile = None
        table = None
        state = "NO_MATCH"
        executor = None
        semantic_context = None
        top_context = None
        detail_context = None
        governed_filter = {
            "sql": "",
            "parameters": [],
            "rules": [],
            "compiler": None,
        }

        if sales_detail_intent:
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

                discovered_objects = list(
                    discovery.get(
                        "objects"
                    )
                    or []
                )

                if sales_detail_mode == "sale":
                    relational = (
                        self._sales_header_objects(
                            discovered_objects
                        )
                    )
                else:
                    relational = (
                        self._sales_detail_objects(
                            discovered_objects
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
                    detail_context,
                ) = matches[0]

                state = "MATCHED"

            elif len(matches) > 1:
                state = "AMBIGUOUS"

            else:
                return self._result(
                    answer=(
                        "La solicitud de detalle de ventas "
                        "fue reconocida, pero no existe una "
                        "fuente SQL gobernada con el esquema "
                        "requerido."
                    ),
                    structured=False,
                    fast_path="governed_sql_blocked",
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
                        "fail_closed":
                            True,
                        "reason":
                            "SALES_DETAIL_METADATA_NOT_AVAILABLE",
                        "llm_sql_generation":
                            False,
                    },
                )

        elif semantic_ranking_intent:
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
                    self._semantic_analytics_objects(
                        list(
                            discovery.get(
                                "objects"
                            )
                            or []
                        ),
                        semantic_plan.entity,
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
                    semantic_context,
                ) = matches[0]

                state = "MATCHED"

            elif len(matches) > 1:
                state = "AMBIGUOUS"

            else:
                return None

        elif top_products_intent:
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

        if sales_detail_intent:
            if (
                executor is None
                or detail_context is None
            ):
                return self._result(
                    answer=(
                        "La solicitud de ventas "
                        "no pudo compilarse de forma "
                        "gobernada."
                    ),
                    structured=False,
                    fast_path="governed_sql_blocked",
                    elapsed_ms=elapsed_ms,
                    governance={
                        "read_only": True,
                        "allowlist_enforced":
                            True,
                        "fail_closed":
                            True,
                        "reason":
                            "SALES_DETAIL_CONTEXT_NOT_AVAILABLE",
                        "llm_sql_generation":
                            False,
                    },
                )

            sales_item = (
                detail_context[
                    "sales"
                ]
            )

            sales_columns = (
                detail_context[
                    "sales_columns"
                ]
            )

            customer_item = (
                detail_context[
                    "customer"
                ]
            )

            customer_columns = (
                detail_context[
                    "customer_columns"
                ]
            )

            if analytic_bindings is None:
                return self._business_semantics_blocked(
                    started=started,
                    reason=(
                        "NO_VALIDATED_SALES_VALID_ROW_FILTER"
                    ),
                )

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

            sales_schema = str(
                sales_item.get("schema")
                or ""
            )

            sales_table = str(
                sales_item.get("name")
                or ""
            )

            customer_schema = str(
                customer_item.get("schema")
                or ""
            )

            customer_table = str(
                customer_item.get("name")
                or ""
            )

            sales_sale_id = (
                sales_columns[
                    "ventaid"
                ]
            )

            sales_customer_id = (
                sales_columns[
                    "clienteid"
                ]
            )

            customer_id = (
                customer_columns[
                    "clienteid"
                ]
            )

            customer_name = (
                customer_columns[
                    "nombre"
                ]
            )

            filter_parts = [
                str(
                    governed_filter.get(
                        "sql"
                    )
                    or ""
                )
            ]

            detail_parameters = list(
                governed_filter.get(
                    "parameters"
                )
                or []
            )

            if detail_seller is not None:
                filter_parts.append(
                    (
                        f"v.[{sales_columns['vendedor']}] "
                        "= ?"
                    )
                )

                detail_parameters.append(
                    detail_seller
                )

            if detail_period is not None:
                filter_parts.append(
                    (
                        f"v.[{sales_columns['fechaventa']}] "
                        ">= ?"
                    )
                )

                filter_parts.append(
                    (
                        f"v.[{sales_columns['fechaventa']}] "
                        "< ?"
                    )
                )

                detail_parameters.extend(
                    [
                        detail_period[
                            "start"
                        ],
                        detail_period[
                            "end_exclusive"
                        ],
                    ]
                )

            filter_clause = (
                "WHERE "
                + " AND ".join(
                    (
                        "("
                        + part
                        + ")"
                    )
                    for part in filter_parts
                    if part
                )
                + " "
            )

            detail_paged = (
                detail_page_requested
                and detail_page is not None
            )

            detail_offset = (
                (
                    detail_page - 1
                )
                * detail_limit
                if detail_paged
                else 0
            )

            detail_pagination_parameters = (
                [
                    detail_offset,
                    detail_limit + 1,
                ]
                if detail_paged
                else []
            )

            detail_select_prefix = (
                "SELECT "
                if detail_paged
                else f"SELECT TOP ({detail_limit}) "
            )

            detail_pagination_clause = (
                " OFFSET ? ROWS "
                "FETCH NEXT ? ROWS ONLY"
                if detail_paged
                else ""
            )

            if sales_detail_mode == "sale":
                query_plan = {
                    "operation": "SELECT",
                    "sql": (
                        detail_select_prefix
                        +                         f"v.[{sales_sale_id}] "
                        "AS [_VentaID], "
                        f"v.[{sales_columns['vendedor']}] "
                        "AS [Vendedor], "
                        f"v.[{sales_columns['fechaventa']}] "
                        "AS [FechaVenta], "
                        f"v.[{sales_columns['folio']}] "
                        "AS [Folio], "
                        f"c.[{customer_name}] "
                        "AS [Cliente], "
                        f"v.[{sales_columns['sucursal']}] "
                        "AS [Sucursal], "
                        f"v.[{sales_columns['estatus']}] "
                        "AS [Estatus], "
                        f"v.[{sales_columns['subtotal']}] "
                        "AS [Subtotal], "
                        f"v.[{sales_columns['iva']}] "
                        "AS [IVA], "
                        f"v.[{sales_columns['total']}] "
                        "AS [Total] "
                        f"FROM [{sales_schema}]"
                        f".[{sales_table}] AS v "
                        f"LEFT JOIN [{customer_schema}]"
                        f".[{customer_table}] AS c "
                        f"ON c.[{customer_id}] "
                        f"= v.[{sales_customer_id}] "
                        f"{filter_clause}"
                        "ORDER BY "
                        f"v.[{sales_columns['vendedor']}] ASC, "
                        f"v.[{sales_columns['fechaventa']}] DESC, "
                        f"v.[{sales_columns['folio']}] DESC"
                        + (
                            f", v.[{sales_sale_id}] DESC"
                            if detail_paged
                            else ""
                        )
                        + detail_pagination_clause
                    ),
                    "parameters":
                        detail_parameters
                        + detail_pagination_parameters,
                    "limit":
                        detail_limit,
                    "timeout_seconds": int(
                        profile.get(
                            "timeout_seconds"
                        )
                        or 30
                    ),
                }

                resource = (
                    f"{sales_schema}."
                    f"{sales_table},"
                    f"{customer_schema}."
                    f"{customer_table}"
                )

                analytic_kind = (
                    "sales_header"
                )

            else:
                detail_item = (
                    detail_context[
                        "detail"
                    ]
                )

                detail_columns = (
                    detail_context[
                        "detail_columns"
                    ]
                )

                product_item = (
                    detail_context[
                        "product"
                    ]
                )

                product_columns = (
                    detail_context[
                        "product_columns"
                    ]
                )

                detail_schema = str(
                    detail_item.get("schema")
                    or ""
                )

                detail_table = str(
                    detail_item.get("name")
                    or ""
                )

                product_schema = str(
                    product_item.get("schema")
                    or ""
                )

                product_table = str(
                    product_item.get("name")
                    or ""
                )

                detail_sale_id = (
                    detail_columns[
                        "ventaid"
                    ]
                )

                detail_id = (
                    detail_columns[
                        "detalleventaid"
                    ]
                )

                detail_product_id = (
                    detail_columns[
                        "productoid"
                    ]
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

                query_plan = {
                    "operation": "SELECT",
                    "sql": (
                        detail_select_prefix
                        +                         f"v.[{sales_sale_id}] "
                        "AS [_VentaID], "
                        f"d.[{detail_id}] "
                        "AS [_DetalleVentaID], "
                        f"v.[{sales_columns['vendedor']}] "
                        "AS [Vendedor], "
                        f"v.[{sales_columns['fechaventa']}] "
                        "AS [FechaVenta], "
                        f"v.[{sales_columns['folio']}] "
                        "AS [Folio], "
                        f"c.[{customer_name}] "
                        "AS [Cliente], "
                        f"v.[{sales_columns['sucursal']}] "
                        "AS [Sucursal], "
                        f"v.[{sales_columns['estatus']}] "
                        "AS [Estatus], "
                        f"v.[{sales_columns['subtotal']}] "
                        "AS [Subtotal], "
                        f"v.[{sales_columns['iva']}] "
                        "AS [IVA], "
                        f"v.[{sales_columns['total']}] "
                        "AS [Total], "
                        f"p.[{product_name}] "
                        "AS [Producto], "
                        f"d.[{detail_columns['cantidad']}] "
                        "AS [Cantidad], "
                        f"d.[{detail_columns['preciounitario']}] "
                        "AS [PrecioUnitario], "
                        f"d.[{detail_columns['importe']}] "
                        "AS [Importe] "
                        f"FROM [{sales_schema}]"
                        f".[{sales_table}] AS v "
                        f"LEFT JOIN [{customer_schema}]"
                        f".[{customer_table}] AS c "
                        f"ON c.[{customer_id}] "
                        f"= v.[{sales_customer_id}] "
                        f"LEFT JOIN [{detail_schema}]"
                        f".[{detail_table}] AS d "
                        f"ON d.[{detail_sale_id}] "
                        f"= v.[{sales_sale_id}] "
                        f"LEFT JOIN [{product_schema}]"
                        f".[{product_table}] AS p "
                        f"ON p.[{product_id}] "
                        f"= d.[{detail_product_id}] "
                        f"{filter_clause}"
                        "ORDER BY "
                        f"v.[{sales_columns['vendedor']}] ASC, "
                        f"v.[{sales_columns['fechaventa']}] DESC, "
                        f"v.[{sales_columns['folio']}] DESC"
                        + (
                            f", v.[{sales_sale_id}] DESC"
                            if detail_paged
                            else ""
                        )
                        + f", d.[{detail_id}] ASC"
                        + detail_pagination_clause
                    ),
                    "parameters":
                        detail_parameters
                        + detail_pagination_parameters,
                    "limit":
                        detail_limit,
                    "timeout_seconds": int(
                        profile.get(
                            "timeout_seconds"
                        )
                        or 30
                    ),
                }

                resource = (
                    f"{sales_schema}."
                    f"{sales_table},"
                    f"{customer_schema}."
                    f"{customer_table},"
                    f"{detail_schema}."
                    f"{detail_table},"
                    f"{product_schema}."
                    f"{product_table}"
                )

                analytic_kind = (
                    "sales_line_item"
                )

        elif semantic_ranking_intent:
            if (
                executor is None
                or semantic_context is None
                or semantic_plan is None
            ):
                return None

            sales_item = (
                semantic_context[
                    "sales"
                ]
            )

            sales_columns = (
                semantic_context[
                    "sales_columns"
                ]
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

            try:
                compiled_filter = (
                    self._compile_sales_row_filters(
                        analytic_bindings,
                        sales_columns,
                    )
                    if analytic_bindings
                    is not None
                    else None
                )
            except ValueError as exc:
                return self._business_semantics_blocked(
                    started=started,
                    reason=str(exc),
                )

            if (
                analytic_bindings is not None
                and compiled_filter is None
            ):
                return self._business_semantics_blocked(
                    started=started,
                    reason=(
                        "NO_VALIDATED_SALES_VALID_ROW_FILTER"
                    ),
                )

            if compiled_filter is not None:
                governed_filter = (
                    compiled_filter
                )

            if (
                semantic_plan.period
                is not None
            ):
                sales_date_column = (
                    sales_columns.get(
                        "fechaventa"
                    )
                )

                if not sales_date_column:
                    return None

                period_sql = (
                    f"v.[{sales_date_column}] "
                    ">= ? AND "
                    f"v.[{sales_date_column}] "
                    "< ?"
                )

                existing_sql = str(
                    governed_filter.get(
                        "sql"
                    )
                    or ""
                ).strip()

                if existing_sql:
                    governed_filter["sql"] = (
                        "("
                        + existing_sql
                        + ") AND ("
                        + period_sql
                        + ")"
                    )
                else:
                    governed_filter["sql"] = (
                        period_sql
                    )

                period_parameters = [
                    semantic_plan.period[
                        "start"
                    ],
                    semantic_plan.period[
                        "end_exclusive"
                    ],
                ]

                governed_filter[
                    "parameters"
                ] = (
                    list(
                        governed_filter.get(
                            "parameters"
                        )
                        or []
                    )
                    + period_parameters
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

            direction_sql = (
                "ASC"
                if semantic_plan.direction
                == "asc"
                else "DESC"
            )

            limit = (
                semantic_plan.limit
            )

            entity = (
                semantic_plan.entity
            )

            metric = (
                semantic_plan.metric
            )

            if entity == "seller":
                dimension_column = (
                    sales_columns[
                        "vendedor"
                    ]
                )

                dimension_sql = (
                    f"v.[{dimension_column}]"
                )

                dimension_alias = (
                    "Vendedor"
                )

                from_sql = (
                    f"FROM "
                    f"[{sales_schema}]"
                    f".[{sales_table}] "
                    "AS v "
                )

                if metric == "sales_amount":
                    measure_sql = (
                        f"SUM(v.["
                        f"{sales_columns['total']}"
                        f"])"
                    )

                    measure_alias = (
                        "ImporteVendido"
                    )

                elif metric == "transaction_count":
                    measure_sql = (
                        f"COUNT(v.["
                        f"{sales_columns['ventaid']}"
                        f"])"
                    )

                    measure_alias = (
                        "Operaciones"
                    )

                else:
                    return None

                group_sql = (
                    dimension_sql
                )

                resource = (
                    f"{sales_schema}."
                    f"{sales_table}"
                )

            elif entity == "branch":
                dimension_column = (
                    sales_columns[
                        "sucursal"
                    ]
                )

                dimension_sql = (
                    f"v.[{dimension_column}]"
                )

                dimension_alias = (
                    "Sucursal"
                )

                from_sql = (
                    f"FROM "
                    f"[{sales_schema}]"
                    f".[{sales_table}] "
                    "AS v "
                )

                if metric == "sales_amount":
                    measure_sql = (
                        f"SUM(v.["
                        f"{sales_columns['total']}"
                        f"])"
                    )

                    measure_alias = (
                        "ImporteVendido"
                    )

                elif metric == "transaction_count":
                    measure_sql = (
                        f"COUNT(v.["
                        f"{sales_columns['ventaid']}"
                        f"])"
                    )

                    measure_alias = (
                        "Operaciones"
                    )

                else:
                    return None

                group_sql = (
                    dimension_sql
                )

                resource = (
                    f"{sales_schema}."
                    f"{sales_table}"
                )

            elif entity == "customer":
                customer_item = (
                    semantic_context[
                        "customer"
                    ]
                )

                customer_columns = (
                    semantic_context[
                        "customer_columns"
                    ]
                )

                customer_schema = str(
                    customer_item.get(
                        "schema"
                    )
                    or ""
                )

                customer_table = str(
                    customer_item.get(
                        "name"
                    )
                    or ""
                )

                customer_name = (
                    customer_columns[
                        "nombre"
                    ]
                )

                customer_id = (
                    customer_columns[
                        "clienteid"
                    ]
                )

                sales_customer_id = (
                    sales_columns[
                        "clienteid"
                    ]
                )

                dimension_sql = (
                    f"c.[{customer_name}]"
                )

                dimension_alias = (
                    "Cliente"
                )

                from_sql = (
                    f"FROM "
                    f"[{sales_schema}]"
                    f".[{sales_table}] "
                    "AS v "
                    f"JOIN "
                    f"[{customer_schema}]"
                    f".[{customer_table}] "
                    "AS c "
                    f"ON c.[{customer_id}] "
                    f"= "
                    f"v.[{sales_customer_id}] "
                )

                if metric == "sales_amount":
                    measure_sql = (
                        f"SUM(v.["
                        f"{sales_columns['total']}"
                        f"])"
                    )

                    measure_alias = (
                        "ImporteVendido"
                    )

                elif metric == "transaction_count":
                    measure_sql = (
                        f"COUNT(v.["
                        f"{sales_columns['ventaid']}"
                        f"])"
                    )

                    measure_alias = (
                        "Operaciones"
                    )

                else:
                    return None

                group_sql = (
                    f"c.[{customer_id}], "
                    f"{dimension_sql}"
                )

                resource = (
                    f"{sales_schema}."
                    f"{sales_table},"
                    f"{customer_schema}."
                    f"{customer_table}"
                )

            elif entity == "product":
                product_item = (
                    semantic_context[
                        "product"
                    ]
                )

                product_columns = (
                    semantic_context[
                        "product_columns"
                    ]
                )

                detail_item = (
                    semantic_context[
                        "detail"
                    ]
                )

                detail_columns = (
                    semantic_context[
                        "detail_columns"
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

                product_name = (
                    product_columns[
                        "nombre"
                    ]
                )

                product_id = (
                    product_columns[
                        "productoid"
                    ]
                )

                detail_product_id = (
                    detail_columns[
                        "productoid"
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

                dimension_sql = (
                    f"p.[{product_name}]"
                )

                dimension_alias = (
                    "Producto"
                )

                from_sql = (
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
                )

                if metric == "quantity":
                    measure_sql = (
                        f"SUM(d.["
                        f"{detail_columns['cantidad']}"
                        f"])"
                    )

                    measure_alias = (
                        "CantidadVendida"
                    )

                elif metric == "sales_amount":
                    measure_sql = (
                        f"SUM(d.["
                        f"{detail_columns['importe']}"
                        f"])"
                    )

                    measure_alias = (
                        "ImporteVendido"
                    )

                else:
                    return None

                group_sql = (
                    f"p.[{product_id}], "
                    f"{dimension_sql}"
                )

                resource = (
                    f"{detail_schema}."
                    f"{detail_table},"
                    f"{product_schema}."
                    f"{product_table},"
                    f"{sales_schema}."
                    f"{sales_table}"
                )

            else:
                return None

            query_plan = {
                "operation": "SELECT",
                "sql": (
                    f"SELECT TOP ({limit}) "
                    f"{dimension_sql} "
                    f"AS [{dimension_alias}], "
                    f"{measure_sql} "
                    f"AS [{measure_alias}] "
                    f"{from_sql}"
                    f"{filter_clause}"
                    f"GROUP BY "
                    f"{group_sql} "
                    f"ORDER BY "
                    f"{measure_sql} "
                    f"{direction_sql}, "
                    f"{dimension_sql} "
                    "ASC"
                ),
                "parameters": list(
                    governed_filter.get(
                        "parameters"
                    )
                    or []
                ),
                "limit":
                    limit,
                "timeout_seconds": int(
                    profile.get(
                        "timeout_seconds"
                    )
                    or 30
                ),
            }

            analytic_kind = (
                "ranking_"
                + entity
                + "_by_"
                + metric
            )

        elif top_products_intent:
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

        detail_has_more = (
            bool(
                payload.get(
                    "truncated"
                )
            )
            if (
                sales_detail_intent
                and detail_page_requested
            )
            else None
        )

        if sales_detail_intent:

            if not rows:
                answer = (
                    "No se encontraron ventas válidas "
                    "para la consulta solicitada."
                )

            elif sales_detail_mode == "sale":
                output = [
                    (
                        "Ventas "
                        f"(se muestran hasta {detail_limit} ventas):"
                    )
                ]

                for row in rows[:detail_limit]:
                    if not isinstance(
                        row,
                        (list, tuple),
                    ):
                        continue

                    seller = (
                        str(
                            row[1]
                            or "Sin vendedor"
                        )
                        if len(row) > 1
                        else "Sin vendedor"
                    )

                    sale_date = (
                        row[2]
                        if len(row) > 2
                        else None
                    )

                    folio = (
                        row[3]
                        if len(row) > 3
                        else None
                    )

                    customer = (
                        row[4]
                        if len(row) > 4
                        else None
                    )

                    branch = (
                        row[5]
                        if len(row) > 5
                        else None
                    )

                    status = (
                        row[6]
                        if len(row) > 6
                        else None
                    )

                    subtotal = (
                        row[7]
                        if len(row) > 7
                        else None
                    )

                    tax = (
                        row[8]
                        if len(row) > 8
                        else None
                    )

                    total = (
                        row[9]
                        if len(row) > 9
                        else None
                    )

                    output.append(
                        (
                            f"- {sale_date}"
                            " | Folio "
                            f"{folio}"
                            " | Vendedor "
                            f"{seller}"
                            " | Cliente "
                            f"{customer}"
                            " | Sucursal "
                            f"{branch}"
                            " | Estatus "
                            f"{status}"
                            " | Subtotal "
                            f"{subtotal}"
                            " | IVA "
                            f"{tax}"
                            " | Total "
                            f"{total}"
                        )
                    )

                answer = "\n".join(
                    output
                )

            else:
                output = [
                    (
                        "Ventas detalladas por vendedor "
                        f"(se muestran hasta {detail_limit} renglones):"
                    )
                ]

                current_seller = None
                current_sale = object()

                for row in rows[:detail_limit]:
                    if not isinstance(
                        row,
                        (list, tuple),
                    ):
                        continue

                    sale_id = (
                        row[0]
                        if len(row) > 0
                        else None
                    )

                    detail_id = (
                        row[1]
                        if len(row) > 1
                        else None
                    )

                    seller = (
                        str(
                            row[2]
                            or "Sin vendedor"
                        )
                        if len(row) > 2
                        else "Sin vendedor"
                    )

                    sale_date = (
                        row[3]
                        if len(row) > 3
                        else None
                    )

                    folio = (
                        row[4]
                        if len(row) > 4
                        else None
                    )

                    customer = (
                        row[5]
                        if len(row) > 5
                        else None
                    )

                    branch = (
                        row[6]
                        if len(row) > 6
                        else None
                    )

                    status = (
                        row[7]
                        if len(row) > 7
                        else None
                    )

                    subtotal = (
                        row[8]
                        if len(row) > 8
                        else None
                    )

                    tax = (
                        row[9]
                        if len(row) > 9
                        else None
                    )

                    total = (
                        row[10]
                        if len(row) > 10
                        else None
                    )

                    product = (
                        row[11]
                        if len(row) > 11
                        else None
                    )

                    quantity = (
                        row[12]
                        if len(row) > 12
                        else None
                    )

                    unit_price = (
                        row[13]
                        if len(row) > 13
                        else None
                    )

                    amount = (
                        row[14]
                        if len(row) > 14
                        else None
                    )

                    if seller != current_seller:
                        output.append(
                            "Vendedor: "
                            + seller
                        )

                        current_seller = seller
                        current_sale = object()

                    sale_key = (
                        seller,
                        sale_id,
                    )

                    if sale_key != current_sale:
                        output.append(
                            (
                                "  Venta: "
                                f"{sale_date}"
                                " | Folio "
                                f"{folio}"
                                " | Cliente "
                                f"{customer}"
                                " | Sucursal "
                                f"{branch}"
                                " | Estatus "
                                f"{status}"
                                " | Subtotal "
                                f"{subtotal}"
                                " | IVA "
                                f"{tax}"
                                " | Total "
                                f"{total}"
                            )
                        )

                        current_sale = sale_key

                    if (
                        detail_id is not None
                        or product is not None
                    ):
                        output.append(
                            (
                                "    - Producto "
                                f"{product}"
                                " | Cantidad "
                                f"{quantity}"
                                " | Precio unitario "
                                f"{unit_price}"
                                " | Importe "
                                f"{amount}"
                            )
                        )

                answer = "\n".join(
                    output
                )

        elif semantic_ranking_intent:
            if not rows:

                answer = (
                    "No se encontraron "
                    "datos válidos para "
                    "construir el ranking."
                )

            else:
                labels = {
                    "seller":
                        "Vendedores",
                    "customer":
                        "Clientes",
                    "branch":
                        "Sucursales",
                    "product":
                        "Productos",
                }

                metric_labels = {
                    "sales_amount":
                        "importe vendido",
                    "transaction_count":
                        "número de operaciones",
                    "quantity":
                        "cantidad vendida",
                }

                direction_label = (
                    "menor a mayor"
                    if semantic_plan.direction
                    == "asc"
                    else
                    "mayor a menor"
                )

                output = [
                    (
                        labels.get(
                            semantic_plan.entity,
                            "Resultados",
                        )
                        + " por "
                        + metric_labels.get(
                            semantic_plan.metric,
                            semantic_plan.metric,
                        )
                        + " ("
                        + direction_label
                        + "):"
                    )
                ]

                for index, row in enumerate(
                    rows[
                        :semantic_plan.limit
                    ],
                    start=1,
                ):
                    if not isinstance(
                        row,
                        (list, tuple),
                    ):
                        continue

                    label = (
                        str(row[0])
                        if len(row) > 0
                        else ""
                    )

                    value = (
                        row[1]
                        if len(row) > 1
                        else None
                    )

                    detail = (
                        f"{index}. {label}"
                    )

                    if value is not None:
                        detail += (
                            f": {value}"
                        )

                    if (
                        semantic_plan.entity
                        == "product"
                        and len(row) > 2
                    ):
                        extra = row[2]

                        if extra is not None:
                            detail += (
                                f"; {extra}"
                            )

                    output.append(
                        detail
                    )

                answer = "\n".join(
                    output
                )

        elif top_products_intent:

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

        if sales_detail_intent:
            governance.update(
                {
                    "semantic_analytics_plan": {
                        "version":
                            (
                                R10_33_SALES_DETAIL_PAGINATION_VERSION
                                if detail_page_requested
                                else R10_32_SALES_DETAIL_VERSION
                            ),
                        "domain":
                            "sales",
                        "entity":
                            "sale",
                        "operation":
                            "detail",
                        "detail_level":
                            sales_detail_mode,
                        "grouping":
                            (
                                "seller"
                                if sales_detail_mode
                                == "line_item"
                                else None
                            ),
                        "limit":
                            detail_limit,
                        **(
                            {
                                "page":
                                    detail_page,
                                "page_size":
                                    detail_limit,
                                "offset":
                                    detail_offset,
                                "explicit":
                                    True,
                                "has_more":
                                    bool(
                                        detail_has_more
                                    ),
                            }
                            if detail_page_requested
                            else {}
                        ),
                        "seller":
                            detail_seller,
                        "period":
                            (
                                dict(
                                    detail_period
                                )
                                if detail_period
                                is not None
                                else None
                            ),
                    },
                    "semantic_planner":
                        (
                            R10_33_SALES_DETAIL_PAGINATION_VERSION
                            if detail_page_requested
                            else R10_32_SALES_DETAIL_VERSION
                        ),
                    "semantic_plan_source":
                        "deterministic",
                    "semantic_plan_validation_authority":
                        "strict_allowlist",
                    "llm_semantic_proposal":
                        False,
                    "llm_semantic_planning_authority":
                        False,
                }
            )

        if semantic_plan is not None:
            governance.update(
                {
                    "semantic_analytics_plan":
                        semantic_plan.as_dict(),
                    "semantic_planner":
                        R10_31_SEMANTIC_ANALYTICS_VERSION,
                    "semantic_plan_source":
                        semantic_plan_source,
                    "semantic_plan_validation_authority":
                        "strict_allowlist",
                    "llm_semantic_proposal":
                        (
                            semantic_plan_source
                            == "llm_structured"
                        ),
                    "llm_semantic_planning_authority":
                        False,
                }
            )

        if (
            top_products_intent
            or semantic_ranking_intent
            or sales_detail_intent
        ):
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
