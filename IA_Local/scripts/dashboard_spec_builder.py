from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import re
import unicodedata

import pandas as pd

from prompt_intelligence import parse_prompt_intelligence
from capability_rules import (
    RULESET_VERSION,
    select_rule,
    rule_public_metadata,
)
from analysis_planner import build_governed_analytical_plan
from analysis_executor import execute_governed_analytical_plan
from insight_engine import build_governed_business_insights
from business_rule_engine import apply_governed_business_rules
from business_rule_registry import load_governed_business_rule_registry
from business_rule_context import load_governed_business_context
from enterprise_metric_rules import (
    load_governed_enterprise_metric_rule_registry,
    resolve_governed_enterprise_metric_rule,
)
from enterprise_rule_governance import build_enterprise_rule_governance_audit
from enterprise_knowledge_registry import load_governed_enterprise_knowledge_registry
from enterprise_knowledge_retrieval import (
    public_knowledge_context,
    retrieve_contextual_enterprise_knowledge,
)

SCHEMA_VERSION = "r10.13a"

SUPPORTED = "SUPPORTED"
DERIVABLE = "DERIVABLE"
BLOCKED = "BLOCKED"


# ======================================================================
# NORMALIZATION
# ======================================================================

def norm(v: Any) -> str:
    s = str(v or "").strip().lower()

    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

    return re.sub(
        r"[^a-z0-9_]+",
        "_",
        s,
    ).strip("_")


# ======================================================================
# SEMANTIC SOURCES
# ======================================================================

def _strict_map(df):
    try:
        from semantic_layer import resolve_semantic_map
        return resolve_semantic_map(df)
    except Exception:
        return {
            "usable": {},
            "concepts": {},
        }


def _governed_roles():
    try:
        from enterprise_ai.semantic_registry import current_context

        return dict(
            (current_context() or {}).get("roles")
            or {}
        )
    except Exception:
        return {}


def _analytic_context():
    try:
        from enterprise_ai import analytic_rules as ar

        getter = (
            getattr(ar, "current_context", None)
            or getattr(
                ar,
                "current_analytic_context",
                None,
            )
        )

        return (
            dict(getter() or {})
            if getter
            else {}
        )

    except Exception:
        return {}


# ======================================================================
# ROLE BRIDGE
# ======================================================================

def _bridge(roles):
    out = dict(roles or {})

    if (
        out.get("total_cost")
        and not out.get("cost")
    ):
        out["cost"] = out["total_cost"]

    if (
        out.get("cost")
        and not out.get("total_cost")
    ):
        out["total_cost"] = out["cost"]

    if (
        out.get("sales")
        and not out.get("revenue")
    ):
        out["revenue"] = out["sales"]

    if (
        out.get("revenue")
        and not out.get("sales")
    ):
        out["sales"] = out["revenue"]

    if (
        out.get("invoice")
        and not out.get("transaction_id")
    ):
        out["transaction_id"] = out["invoice"]

    if (
        out.get("reference")
        and not out.get("transaction_id")
    ):
        out["transaction_id"] = out["reference"]

    return out


# ======================================================================
# FREIGHT SAFETY
# ======================================================================

def _is_invalid_freight_mapping(
    role: str,
    col: Any,
) -> bool:

    if role != "freight" or not col:
        return False

    n = norm(col)

    # Evidencia semántica negativa:
    # "sin flete" significa explícitamente que excluye flete.
    return (
        "sin_flete" in n
        or "without_freight" in n
        or "excluding_freight" in n
        or n in {
            "costo_sin_flete",
            "cost_without_freight",
        }
    )


# ======================================================================
# ROLE MERGE
# ======================================================================

def _merge_roles(
    df,
    semantic_map=None,
    semantic_roles=None,
    semantic_context=None,
):

    cols = {
        str(c)
        for c in df.columns
    }

    inferred = _bridge(
        dict(
            (
                semantic_map
                or _strict_map(df)
            ).get("usable")
            or {}
        )
    )

    provided = _bridge(
        dict(
            semantic_roles
            or {}
        )
    )

    governed = _bridge(
        dict(
            (
                semantic_context
                or {}
            ).get("roles")
            or _governed_roles()
        )
    )

    roles = {}
    sources = {}

    for source_name, mapping in (
        (
            "semantic_fallback",
            inferred,
        ),
        (
            "semantic_contract",
            provided,
        ),
        (
            "governed_semantic_definition",
            governed,
        ),
    ):

        for role, col in mapping.items():

            if col not in cols:
                continue

            # Nunca aceptar contradicciones explícitas:
            # Costo_Sin_Flete -> freight.
            if _is_invalid_freight_mapping(
                role,
                col,
            ):
                continue

            roles[role] = col
            sources[role] = source_name

    # Alias operacional seguro para Cliente_Recoge.
    if not roles.get("customer_pickup"):

        by_norm = {
            norm(c): str(c)
            for c in df.columns
        }

        for alias in (
            "cliente_recoge",
            "customer_pickup",
            "pickup_customer",
        ):

            if alias in by_norm:

                roles["customer_pickup"] = (
                    by_norm[alias]
                )

                sources["customer_pickup"] = (
                    "exact_column_alias"
                )

                break

    return _bridge(roles), sources


# ======================================================================
# CAPABILITY FACTORY
# ======================================================================

def _cap(
    key,
    kind,
    status,
    role=None,
    columns=None,
    formula=None,
    reason=None,
    source="capability_resolver",
    confidence=1.0,
    dependencies=None,
):

    return {
        "id": f"{kind}:{key}",
        "type": kind,
        "requested_by_prompt": True,
        "status": status,
        "semantic_role": role or key,
        "source_columns": list(
            columns
            or []
        ),
        "formula": formula,
        "title": key.replace(
            "_",
            " ",
        ).title(),
        "reason": reason,
        "provenance": {
            "source": source,
            "confidence": confidence,
        },
        "dependencies": list(
            dependencies
            or []
        ),
    }


# ======================================================================
# ROLE REGISTRIES
# ======================================================================

DIRECT = {
    "revenue": "revenue",
    "quantity": "quantity",
    "cost": "cost",
    "profit": "profit",
    "freight": "freight",
    "stock": "stock",
    "overdue_balance": "balance",
    "days_overdue": "days_overdue",
}


DIMS = {
    "date": "date",
    "week": "week",
    "customer": "customer",
    "product": "product",
    "product_group": "product_group",
    "line": "line",
    "seller": "seller",
    "zone": "zone",
    "supplier": "supplier",
    "warehouse": "warehouse",
    "origin_city": "origin_city",
    "destination_city": "destination_city",
    "invoice": "transaction_id",
    "customer_pickup": "customer_pickup",
    "employee": "employee",
}


# ======================================================================
# DIRECT METRIC
# ======================================================================

def _direct_metric(
    key,
    roles,
    sources,
):

    role = DIRECT.get(key)

    col = (
        roles.get(role)
        if role
        else None
    )

    if not col:
        return None

    return _cap(
        key,
        "kpi",
        SUPPORTED,
        role=role,
        columns=[col],
        source=sources.get(
            role,
            "direct_column",
        ),
    )


# ======================================================================
# DERIVED METRIC
# ======================================================================

def _derived_metric(
    key,
    roles,
    sources=None,
):

    governed_roles = {
        r
        for r, src in dict(
            sources
            or {}
        ).items()
        if src in {
            "governed_semantic_definition",
            "validated_analytic_rule",
        }
    }

    rule, missing = select_rule(
        key,
        roles,
        governed_roles,
    )

    if not rule:
        return None

    deps = list(
        rule.get("dependencies")
        or []
    )

    cols = [
        roles.get(dep)
        for dep in deps
        if roles.get(dep)
    ]

    cap = _cap(
        key,
        "kpi",
        DERIVABLE,
        columns=cols,
        formula=rule.get("formula"),
        source="capability_rule_registry",
        dependencies=deps,
    )

    cap["rule"] = (
        rule_public_metadata(rule)
    )

    cap["output_format"] = (
        rule.get("format")
        or "number"
    )

    cap["execution"] = {
        "operator": rule.get("operator"),
        "dependency_roles": deps,
        "zero_division": "N/D",
    }

    return cap


# ======================================================================
# GOVERNED ENTERPRISE DERIVED METRIC
# ======================================================================
def _enterprise_derived_metric(key, available_columns):
    registry = load_governed_enterprise_metric_rule_registry()
    context_doc = load_governed_business_context()
    if context_doc.get("status") == "INVALID":
        return None
    context = dict(context_doc.get("context") or {})
    as_of = context.pop("as_of", None)
    resolution = resolve_governed_enterprise_metric_rule(
        metric=key,
        available_columns=available_columns,
        rule_registry=registry,
        context=context,
        as_of=as_of,
    )
    if resolution.get("status") != DERIVABLE:
        return None
    rule = dict(resolution.get("rule") or {})
    cols = [str(c) for c in (rule.get("source_columns") or [])]
    cap = _cap(
        key, "kpi", DERIVABLE, columns=cols, formula=None,
        source="governed_enterprise_metric_rule", dependencies=cols,
    )
    cap["rule"] = {
        "rule_id": rule.get("rule_id"),
        "ruleset_version": registry.get("ruleset_version"),
        "scope": rule.get("scope") or {},
        "operator": rule.get("operator"),
        "approval_status": rule.get("approval_status"),
        "source_columns": cols,
        "provenance": rule.get("provenance"),
    }
    cap["output_format"] = rule.get("format") or "number"
    cap["execution"] = {
        "operator": rule.get("operator"),
        "dependency_roles": [],
        "source_columns": cols,
        "zero_division": "N/D",
    }
    return cap


# ======================================================================
# AUTHORIZED FREIGHT
# ======================================================================

def _authorized_freight(
    analytic_context=None,
):

    ctx = dict(
        analytic_context
        or _analytic_context()
    )

    bindings = (
        list(
            ctx.get("bindings")
            or []
        )
        + list(
            ctx.get("rules")
            or []
        )
    )

    for b in bindings:

        target = norm(
            b.get("target")
            or b.get("metric")
            or b.get("name")
        )

        expr = str(
            b.get("expression")
            or b.get("formula")
            or b.get("rule")
            or ""
        ).strip()

        if (
            target
            in {
                "freight",
                "flete",
                "freight_total",
                "costo_flete",
            }
            and expr
        ):

            return _cap(
                "freight",
                "kpi",
                DERIVABLE,
                formula=expr,
                source="validated_analytic_rule",
                dependencies=[
                    "validated_analytic_rule"
                ],
            )

    return None


# ======================================================================
# METRIC RESOLVER
# ======================================================================

def resolve_metric(
    key,
    roles,
    sources,
    analytic_context=None,
    available_columns=None,
):

    direct = _direct_metric(
        key,
        roles,
        sources,
    )

    if direct:
        return direct

    enterprise = _enterprise_derived_metric(
        key,
        list(available_columns) if available_columns is not None else [],
    )

    if enterprise:
        return enterprise

    derived = _derived_metric(
        key,
        roles,
        sources,
    )

    if derived:
        return derived

    governed_roles = {
        r
        for r, src in sources.items()
        if src in {
            "governed_semantic_definition",
            "validated_analytic_rule",
        }
    }

    rule, missing = select_rule(
        key,
        roles,
        governed_roles,
    )

    reason = (
        "No direct semantic role or safe deterministic "
        f"derivation exists for '{key}'."
    )

    if missing:

        reason += (
            " Missing dependencies: "
            + ", ".join(missing)
        )

    return _cap(
        key,
        "kpi",
        BLOCKED,
        reason=reason,
        dependencies=[
            x.replace(
                "governed:",
                "",
            )
            for x in missing
        ],
    )


# ======================================================================
# DIMENSION RESOLVER
# ======================================================================

def resolve_dimension(
    key,
    roles,
    sources,
):

    role = DIMS.get(
        key,
        key,
    )

    col = roles.get(role)

    if col:

        return _cap(
            key,
            "filter",
            SUPPORTED,
            role=role,
            columns=[col],
            source=sources.get(
                role,
                "direct_column",
            ),
        )

    if (
        key == "week"
        and roles.get("date")
    ):

        return _cap(
            key,
            "filter",
            DERIVABLE,
            role="week",
            columns=[
                roles["date"]
            ],
            formula="ISO week(date)",
            source="derived_dimension_rule",
            dependencies=["date"],
        )

    return _cap(
        key,
        "filter",
        BLOCKED,
        role=role,
        reason=(
            "No semantic column or safe derivation "
            f"exists for dimension '{key}'."
        ),
    )


# ======================================================================
# ANALYSIS RESOLVER
# ======================================================================

def resolve_analysis(
    key,
    roles,
):

    req = {
        "executive_summary": [],
        "trend": ["date"],
        "ranking": [],
        "customer_profile": ["customer"],
        "lost_customers": [
            "customer",
            "date",
        ],
        "profitability": [
            "revenue",
        ],
        "risks": [],
        "opportunities": [],
        "routes": [
            "origin_city",
            "destination_city",
        ],
        "warehouse_movement": [
            "warehouse",
            "quantity",
        ],
        "origin_share": [
            "origin_city",
            "quantity",
        ],
        "destination_share": [
            "destination_city",
            "quantity",
        ],
        "monthly_movement": [
            "date",
            "quantity",
        ],
        "customer_pickup": [
            "customer_pickup",
            "quantity",
        ],
        "freight_analysis": [
            "freight",
        ],
        "aging": [
            "customer",
        ],
        "collections": [
            "customer",
        ],
        "critical_stock": [
            "product",
        ],
        "inventory_turnover": [
            "product",
            "date",
            "stock",
        ],
        "obsolete_inventory": [
            "product",
            "date",
            "stock",
        ],
        "data_quality": [],
        "detail": [],
    }.get(
        key,
        [],
    )

    missing = [
        r
        for r in req
        if not roles.get(r)
    ]

    if missing:

        return _cap(
            key,
            "analysis",
            BLOCKED,
            reason=(
                "Missing required semantic roles: "
                + ", ".join(missing)
            ),
            dependencies=req,
        )

    return _cap(
        key,
        "analysis",
        SUPPORTED,
        columns=[
            roles[r]
            for r in req
            if roles.get(r)
        ],
        dependencies=req,
    )


# ======================================================================
# R10.13D.2
# GENERIC DIMENSION ANALYSIS COMPONENTS
# ======================================================================

def _dimension_analysis_caps(
    intent,
    roles,
):
    """
    R10.13D.7 - Canonical Dimension Profitability Planner.
    Componentes internos, no alteran coverage.
    """

    out = []
    dimensions = list(intent.get("dimensions") or [])

    measure_kpis = [
        "kpi:revenue",
        "kpi:cost",
        "kpi:profit",
        "kpi:margin_pct",
        "kpi:quantity",
        "kpi:operations",
        "kpi:ticket_avg",
        "kpi:price_per_unit",
        "kpi:cost_per_unit",
        "kpi:profit_per_unit",
    ]

    identity_roles = {
        "customer": "customer_id",
        "product": "product_id",
        "seller": "seller_id",
    }

    title_labels = {
        "customer": "cliente",
        "product": "producto",
        "seller": "vendedor",
        "warehouse": "almacén",
        "zone": "zona",
        "line": "línea",
        "category": "categoría",
        "supplier": "proveedor",
        "origin_city": "ciudad origen",
        "destination_city": "ciudad destino",
    }

    for key in dimensions:
        if not roles.get(key):
            continue

        identity_role = identity_roles.get(key, key)
        if not roles.get(identity_role):
            identity_role = key

        source_columns = []
        for role_key in (identity_role, key):
            col = roles.get(role_key)
            if col and col not in source_columns:
                source_columns.append(col)

        label = title_labels.get(
            key,
            key.replace("_", " "),
        )

        out.append({
            "id": f"analysis:dimension_{key}",
            "type": "analysis",
            "requested_by_prompt": False,
            "status": SUPPORTED,
            "semantic_role": key,
            "source_columns": source_columns,
            "formula": None,
            "title": f"Rentabilidad por {label}",
            "reason": None,
            "provenance": {
                "source": "canonical_dimension_profitability_planner",
                "confidence": 1.0,
            },
            "dependencies": [key],
            "execution": {
                "operator": "dimension_profitability",
                "dimension_role": key,
                "identity_role": identity_role,
                "label_role": key,
                "measure_kpis": measure_kpis,
                "sort_metric": "kpi:revenue",
                "top_n": 15,
                "chart": {
                    "operator": "dimension_bar_chart",
                    "metric": "kpi:revenue",
                    "top_n": 15,
                },
            },
        })

    return out


# ======================================================================
# PAGE COMPOSITION
# R10.13D + R10.13D.2
# ======================================================================

def _pages(
    intent,
    caps,
):

    explicit = list(
        intent.get("explicit_pages")
        or []
    )

    requested = list(
        intent.get("pages")
        or []
    )

    if explicit:

        out = [
            {
                "id": str(
                    p.get("id")
                ),
                "title": str(
                    p.get("title")
                    or p.get("id")
                ),
                "components": [],
            }
            for p in explicit
            if p.get("id")
        ]

    else:

        if not requested:

            requested = {
                "sales": [
                    "summary",
                    "customers",
                    "analysis",
                ],
                "logistics": [
                    "summary",
                    "logistics",
                ],
                "receivables": [
                    "summary",
                    "receivables",
                ],
                "inventory": [
                    "summary",
                    "inventory",
                ],
                "finance": [
                    "summary",
                    "analysis",
                ],
                "purchasing": [
                    "summary",
                    "analysis",
                ],
                "hr": [
                    "summary",
                    "analysis",
                ],
                "generic": [
                    "summary",
                ],
            }.get(
                intent.get("domain"),
                ["summary"],
            )

        titles = {
            "summary": "Resumen Ejecutivo",
            "customers": "Clientes",
            "analysis": "Análisis",
            "operations": "Facturas / Operaciones",
            "customer_profile": "Perfil de Cliente",
            "line_analysis": "Análisis por Línea",
            "lost_customers": "Clientes Perdidos",
            "logistics": "Logística",
            "inventory": "Inventario",
            "receivables": "Cobranza",
            "profitability": "Rentabilidad",
            "products": "Productos",
            "sellers": "Vendedores",
            "evolution": "Evolución",
            "detail": "Detalle",
        }

        out = [
            {
                "id": p,
                "title": titles.get(
                    p,
                    p.replace(
                        "_",
                        " ",
                    ).title(),
                ),
                "components": [],
            }
            for p in requested
        ]

    if not out:

        out = [
            {
                "id": "summary",
                "title": "Resumen Ejecutivo",
                "components": [],
            }
        ]

    ids = {
        p["id"]
        for p in out
    }


    # ------------------------------------------------------------------
    # R10.13D
    # Page Composition Planner
    # ------------------------------------------------------------------

    def find_page(*aliases):
        """
        Devuelve el ID real de una página solicitada
        comparando ID canónico y título visible.
        """

        aliases = [
            str(a).casefold()
            for a in aliases
            if a
        ]

        for page in out:

            pid = str(
                page.get("id")
                or ""
            ).casefold()

            title = str(
                page.get("title")
                or ""
            ).casefold()

            haystack = (
                f"{pid} {title}"
            )

            if any(
                alias == pid
                or alias in haystack
                for alias in aliases
            ):
                return page["id"]

        return None


    summary_page = find_page(
        "summary",
        "resumen",
        "resumen ejecutivo",
    )

    profitability_page = find_page(
        "profitability",
        "rentabilidad",
        "profit",
        "margin",
    )

    customers_page = find_page(
        "customers",
        "clientes",
        "customer",
    )

    products_page = find_page(
        "products",
        "productos",
        "product",
    )

    sellers_page = find_page(
        "sellers",
        "vendedores",
        "seller",
        "salespeople",
    )

    evolution_page = find_page(
        "evolution",
        "evolución",
        "evolucion",
        "trend",
        "tendencia",
    )

    detail_page = find_page(
        "detail",
        "detalle",
        "operations",
        "operaciones",
    )

    analysis_page = find_page(
        "analysis",
        "análisis",
        "analisis",
    )

    logistics_page = find_page(
        "logistics",
        "logística",
        "logistica",
    )

    inventory_page = find_page(
        "inventory",
        "inventario",
    )


    def choose(c):

        role = str(
            c.get("semantic_role")
            or ""
        ).casefold()

        cid = str(
            c.get("id")
            or ""
        ).casefold()

        typ = str(
            c.get("type")
            or ""
        ).casefold()

        status = str(
            c.get("status")
            or ""
        ).upper()


        # ==============================================================
        # 1. ARQUITECTURA LOGÍSTICA EXISTENTE
        # ==============================================================

        if (
            "warehouses" in ids
            and (
                role == "warehouse"
                or cid
                == "analysis:warehouse_movement"
            )
        ):
            return "warehouses"


        if (
            "routes" in ids
            and cid
            == "analysis:routes"
        ):
            return "routes"


        if (
            "origin_destination" in ids
            and (
                role in {
                    "origin_city",
                    "destination_city",
                }
                or cid in {
                    "analysis:origin_share",
                    "analysis:destination_share",
                }
            )
        ):
            return "origin_destination"


        if (
            "evolution" in ids
            and (
                role == "date"
                or cid in {
                    "analysis:trend",
                    "analysis:monthly_movement",
                }
            )
        ):
            return "evolution"


        if (
            "logistics_detail" in ids
            and (
                cid in {
                    "analysis:detail",
                    "analysis:customer_pickup",
                }
                or role
                == "customer_pickup"
                or typ
                == "table"
            )
        ):
            return "logistics_detail"


        if (
            "data_quality" in ids
            and cid
            == "analysis:data_quality"
        ):
            return "data_quality"


        if (
            "logistics_summary" in ids
            and (
                typ in {
                    "kpi",
                    "deliverable",
                }
                or role
                == "quantity"
            )
        ):
            return "logistics_summary"


        # ==============================================================
        # 2. R10.13D - EVOLUCIÓN
        # ==============================================================

        if (
            evolution_page
            and (
                role == "date"
                or "trend" in cid
                or "monthly" in cid
                or "evolution" in cid
                or "evolucion" in cid
            )
        ):
            return evolution_page


        # ==============================================================
        # 3. R10.13D - CLIENTES
        # ==============================================================

        if (
            customers_page
            and (
                role in {
                    "customer",
                    "customer_id",
                    "active_customers",
                    "lost_customers",
                }
                or "customer" in cid
                or "cliente" in cid
            )
        ):
            return customers_page


        # ==============================================================
        # 4. R10.13D - PRODUCTOS
        # ==============================================================

        if (
            products_page
            and (
                role in {
                    "product",
                    "product_id",
                    "products_sold",
                    "category",
                }
                or "product" in cid
                or "producto" in cid
                or "article" in cid
                or "articulo" in cid
            )
        ):
            return products_page


        # ==============================================================
        # 5. R10.13D - VENDEDORES
        # ==============================================================

        if (
            sellers_page
            and (
                role in {
                    "seller",
                    "seller_id",
                    "active_sellers",
                    "salesperson",
                }
                or "seller" in cid
                or "vendedor" in cid
                or "salesperson" in cid
            )
        ):
            return sellers_page


        # ==============================================================
        # 5.1 R10.13D.2
        # GENERIC DIMENSION ANALYSIS ROUTING
        # ==============================================================

        if (
            cid
            == "analysis:dimension_customer"
            and customers_page
        ):
            return customers_page


        if (
            cid
            == "analysis:dimension_product"
            and products_page
        ):
            return products_page


        if (
            cid
            == "analysis:dimension_seller"
            and sellers_page
        ):
            return sellers_page


        if (
            cid
            == "analysis:dimension_warehouse"
        ):

            if logistics_page:
                return logistics_page

            if summary_page:
                return summary_page


        # ==============================================================
        # 6. R10.13D - RENTABILIDAD
        # ==============================================================

        profitability_roles = {
            "cost",
            "profit",
            "margin",
            "margin_pct",
            "profit_margin",
            "price_per_unit",
            "cost_per_unit",
            "profit_per_unit",
            "unit_price",
            "unit_cost",
            "freight",
            "freight_per_unit",
        }


        profitability_tokens = {
            "profit",
            "margin",
            "cost",
            "price_per_unit",
            "cost_per_unit",
            "profit_per_unit",
            "rentabilidad",
            "utilidad",
            "freight",
            "flete",
        }


        if (
            profitability_page
            and (
                role
                in profitability_roles
                or any(
                    token in cid
                    for token
                    in profitability_tokens
                )
            )
        ):
            return profitability_page


        # ==============================================================
        # 7. R10.13D - DETALLE
        # ==============================================================

        if (
            detail_page
            and (
                typ == "table"
                or cid
                == "analysis:detail"
                or cid.startswith(
                    "table:"
                )
                or "detail" in cid
                or "detalle" in cid
            )
        ):
            return detail_page


        # ==============================================================
        # 8. COMPATIBILIDAD COMERCIAL ANTERIOR
        # ==============================================================

        if (
            role in {
                "customer",
                "active_customers",
            }
            and "customers" in ids
        ):
            return "customers"


        if (
            role in {
                "freight",
                "origin_city",
                "destination_city",
            }
            and logistics_page
        ):
            return logistics_page


        if (
            role
            == "lost_customers"
            and "lost_customers"
            in ids
        ):
            return "lost_customers"


        if (
            typ == "analysis"
            and analysis_page
        ):
            return analysis_page


        if (
            inventory_page
            and (
                role
                == "inventory"
                or "inventory"
                in cid
            )
        ):
            return inventory_page


        # ==============================================================
        # 9. KPIs EJECUTIVOS / GLOBALES
        # ==============================================================

        if (
            summary_page
            and typ in {
                "kpi",
                "deliverable",
            }
        ):
            return summary_page


        # ==============================================================
        # 10. FALLBACK CONTROLADO
        # ==============================================================

        if summary_page:
            return summary_page


        if (
            "logistics_summary"
            in ids
        ):
            return "logistics_summary"


        if inventory_page:
            return inventory_page


        return out[0]["id"]


    # ------------------------------------------------------------------
    # COMPOSICIÓN FINAL + ROUTING PROVENANCE
    # ------------------------------------------------------------------

    page_map = {
        p["id"]: p
        for p in out
    }


    for c in caps:

        target = choose(c)

        if target not in page_map:
            target = out[0]["id"]

        page_map[target][
            "components"
        ].append(
            c["id"]
        )

        # R10.13D:
        # trazabilidad de composición.
        # No modifica provenance de cálculo R10.13C.
        c["page_routing"] = {
            "assigned_page": target,
            "planner_version": "r10.13d",
            "status": "ROUTED",
        }

    return out


# ======================================================================
# CHART SPEC FROM ANALYSES
# ======================================================================

def _charts_from_analyses(
    caps,
):

    definitions = {
        "analysis:trend": (
            "Evolución temporal",
            "line",
        ),
        "analysis:monthly_movement": (
            "Evolución mensual del movimiento",
            "line",
        ),
        "analysis:warehouse_movement": (
            "Movimiento por almacén",
            "bar",
        ),
        "analysis:origin_share": (
            "Participación por ciudad origen",
            "bar",
        ),
        "analysis:destination_share": (
            "Participación por ciudad destino",
            "bar",
        ),
        "analysis:routes": (
            "Rutas principales",
            "bar",
        ),
        "analysis:customer_pickup": (
            "Clientes que recogen",
            "bar",
        ),
        "analysis:inventory_turnover": (
            "Rotación por producto",
            "bar",
        ),
        "analysis:obsolete_inventory": (
            "Productos obsoletos / sin movimiento",
            "bar",
        ),
    }


    out = []


    for c in caps:

        if (
            c.get("id")
            not in definitions
        ):
            continue

        title, kind = (
            definitions[c["id"]]
        )

        out.append({
            "id": (
                "chart:"
                + c["id"].split(
                    ":",
                    1,
                )[1]
            ),
            "type": kind,
            "title": title,
            "status": c.get(
                "status"
            ),
            "source_columns": list(
                c.get(
                    "source_columns"
                )
                or []
            ),
            "reason": c.get(
                "reason"
            ),
            "provenance": dict(
                c.get(
                    "provenance"
                )
                or {}
            ),
        })

    return out


# ======================================================================
# BUILD DASHBOARD SPEC
# ======================================================================

def build_dashboard_spec(
    df,
    prompt,
    *,
    sheet="",
    semantic_map=None,
    semantic_roles=None,
    semantic_context=None,
    analytic_context=None,
    source_context=None,
):

    intent = parse_prompt_intelligence(
        prompt
    )


    roles, sources = _merge_roles(
        df,
        semantic_map,
        semantic_roles,
        semantic_context,
    )


    caps = []


    # ------------------------------------------------------------------
    # METRICS
    # ------------------------------------------------------------------

    for k in (
        intent.get("metrics")
        or []
    ):

        caps.append(
            resolve_metric(
                k,
                roles,
                sources,
                analytic_context,
                df.columns,
            )
        )


    # ------------------------------------------------------------------
    # DIMENSIONS / FILTERS REQUESTED BY PROMPT
    # ------------------------------------------------------------------

    for k in (
        intent.get("dimensions")
        or []
    ):

        caps.append(
            resolve_dimension(
                k,
                roles,
                sources,
            )
        )


    # ------------------------------------------------------------------
    # ANALYSES REQUESTED BY PROMPT
    # ------------------------------------------------------------------

    for k in (
        intent.get("analyses")
        or []
    ):

        caps.append(
            resolve_analysis(
                k,
                roles,
            )
        )


    # ==================================================================
    # R10.13D.2
    # GENERIC DIMENSION ANALYSIS COMPONENTS
    #
    # IMPORTANTE:
    # Son componentes internos.
    # requested_by_prompt=False.
    # NO deben alterar coverage.
    # ==================================================================

    existing = {
        c["id"]
        for c in caps
        if (
            isinstance(c, dict)
            and c.get("id")
        )
    }


    for c in _dimension_analysis_caps(
        intent,
        roles,
    ):

        if (
            c["id"]
            not in existing
        ):

            caps.append(c)

            existing.add(
                c["id"]
            )


    # ------------------------------------------------------------------
    # EXPLICIT FILTERS
    # ------------------------------------------------------------------

    existing = {
        c["id"]
        for c in caps
        if (
            isinstance(c, dict)
            and c.get("id")
        )
    }


    for k in (
        intent.get("filters")
        or []
    ):

        c = resolve_dimension(
            k,
            roles,
            sources,
        )

        c["id"] = (
            f"filter:{k}"
        )

        c["type"] = "filter"

        if (
            c["id"]
            not in existing
        ):

            caps.append(c)

            existing.add(
                c["id"]
            )

    # ======================================================================
    # R10.13D.4
    # SPEC-DRIVEN BUSINESS TABLE EXECUTION
    # ======================================================================

    def _table_execution_spec(
        key: str,
        roles: Dict[str, Any],
    ) -> Dict[str, Any]:

        grouped_metrics = [
            "kpi:revenue",
            "kpi:cost",
            "kpi:profit",
            "kpi:margin_pct",
            "kpi:quantity",
            "kpi:operations",
            "kpi:ticket_avg",
            "kpi:price_per_unit",
            "kpi:cost_per_unit",
            "kpi:profit_per_unit",
        ]

        if key == "customers":

            return {
                "operator": "grouped_business_table",
                "grain_roles": (
                    ["customer_id"]
                    if roles.get("customer_id")
                    else ["customer"]
                ),
                "fallback_grain_roles": [
                    "customer",
                ],
                "label_roles": [
                    "customer",
                ],
                "measure_kpis": grouped_metrics,
                "sort_metric": "kpi:revenue",
                "limit": 100,
            }

        if key == "products":

            return {
                "operator": "grouped_business_table",
                "grain_roles": (
                    ["product_id"]
                    if roles.get("product_id")
                    else ["product"]
                ),
                "fallback_grain_roles": [
                    "product",
                ],
                "label_roles": [
                    "product",
                ],
                "measure_kpis": grouped_metrics,
                "sort_metric": "kpi:revenue",
                "limit": 100,
            }

        if key == "sellers":

            return {
                "operator": "grouped_business_table",
                "grain_roles": (
                    ["seller_id"]
                    if roles.get("seller_id")
                    else ["seller"]
                ),
                "fallback_grain_roles": [
                    "seller",
                ],
                "label_roles": [
                    "seller",
                ],
                "measure_kpis": grouped_metrics,
                "sort_metric": "kpi:revenue",
                "limit": 100,
            }

        if key == "operations":

            return {
                "operator": "transaction_table",
                "grain_roles": [
                    "transaction_id",
                ],
                "columns": [
                    "transaction_id",
                    "date",
                    "customer",
                    "product",
                    "seller",
                    "warehouse",
                    "revenue",
                    "cost",
                    "quantity",
                    "origin_city",
                    "destination_city",
                    "customer_pickup",
                ],
                "limit": 250,
            }

        return {
            "operator": "raw_table",
            "limit": 100,
        }

    # ------------------------------------------------------------------
    # TABLES
    # ------------------------------------------------------------------

    for k in (
        intent.get("tables")
        or []
    ):

        c = _cap(
            k,
            "table",
            SUPPORTED,
            source=(
                "prompt_specification"
            ),
        )

        c["execution"] = (
            _table_execution_spec(
                k,
                roles,
            )
        )

        c["provenance"] = {
            "source": "table_execution_planner",
            "confidence": 1.0,
        }

        caps.append(c)


    # ------------------------------------------------------------------
    # DELIVERABLES
    # ------------------------------------------------------------------

    for k in (
        intent.get("deliverables")
        or []
    ):

        caps.append(
            _cap(
                k,
                "deliverable",
                SUPPORTED,
                source=(
                    "prompt_specification"
                ),
            )
        )


    # ==================================================================
    # COVERAGE
    #
    # IMPORTANTE R10.13D.2:
    # Solo cuenta componentes realmente solicitados por el prompt.
    # analysis:dimension_* son internos y NO alteran requested_count.
    # ==================================================================

    requested_caps = [
        c
        for c in caps
        if c.get(
            "requested_by_prompt",
            True,
        )
    ]


    requested = len(
        requested_caps
    )


    supported = sum(
        c.get("status")
        == SUPPORTED
        for c in requested_caps
    )


    derivable = sum(
        c.get("status")
        == DERIVABLE
        for c in requested_caps
    )


    blocked = sum(
        c.get("status")
        == BLOCKED
        for c in requested_caps
    )


    fulfilled = (
        supported
        + derivable
    )


    percent = (
        round(
            fulfilled
            / requested
            * 100,
            2,
        )
        if requested
        else 100.0
    )


    # ------------------------------------------------------------------
    # SOURCE RESOLUTION
    # ------------------------------------------------------------------

    reqsrc = intent.get(
        "requested_source"
    )

    resolved = (
        sheet
        or None
    )


    if (
        reqsrc
        and resolved
        and norm(reqsrc)
        != norm(resolved)
    ):

        reason = (
            "requested_source_differs_from_resolved_source; "
            "current source-selection contract resolved the dataset"
        )


    elif reqsrc:

        reason = (
            "requested_source_matches_resolved_source"
        )


    else:

        reason = (
            "auto_discovery_or_existing_transactional_selector"
        )


    # ------------------------------------------------------------------
    # BLOCKED / DERIVED FOR GOVERNANCE
    #
    # Aquí sí conservamos capacidades reales.
    # Los D.2 actuales son SUPPORTED y por lo tanto no interfieren.
    # ------------------------------------------------------------------

    blocked_items = [
        c
        for c in requested_caps
        if c.get("status")
        == BLOCKED
    ]


    derived = [
        c
        for c in requested_caps
        if c.get("status")
        == DERIVABLE
    ]


    # ------------------------------------------------------------------
    # R10.14A - GOVERNED ANALYTICAL PLAN
    # ------------------------------------------------------------------

    analytical_plan = build_governed_analytical_plan(
        intent=intent,
        roles=roles,
        components=caps,
    )

    analytical_results = execute_governed_analytical_plan(
        df,
        analytical_plan=analytical_plan,
        roles=roles,
    )

    business_insights = build_governed_business_insights(
        analytical_results=analytical_results,
    )

    business_rule_registry = load_governed_business_rule_registry()
    enterprise_metric_rule_registry = load_governed_enterprise_metric_rule_registry()
    enterprise_knowledge_registry = load_governed_enterprise_knowledge_registry()
    business_rule_context = load_governed_business_context()

    resolved_rule_context = dict(business_rule_context.get("context") or {})
    resolved_rule_as_of = resolved_rule_context.pop("as_of", None)

    enterprise_knowledge_retrieval = retrieve_contextual_enterprise_knowledge(
        prompt=prompt,
        registry=enterprise_knowledge_registry,
        context=({} if business_rule_context.get("status") == "INVALID" else resolved_rule_context),
        as_of=(None if business_rule_context.get("status") == "INVALID" else resolved_rule_as_of),
    )
    enterprise_knowledge_context = public_knowledge_context(enterprise_knowledge_retrieval)
    intent["knowledge_context"] = enterprise_knowledge_context
    resolved_business_rule_registry = (
        []
        if business_rule_context.get("status") == "INVALID"
        else business_rule_registry.get("rules")
    )

    business_rule_interpretation = apply_governed_business_rules(
        business_insights=business_insights,
        rule_registry=resolved_business_rule_registry,
        context=resolved_rule_context,
        as_of=resolved_rule_as_of,
    )

    business_rule_interpretation["context_governance"] = {
        "schema_version": business_rule_context.get("schema_version"),
        "status": business_rule_context.get("status"),
        "context": business_rule_context.get("context"),
        "errors": business_rule_context.get("errors"),
        "governance": business_rule_context.get("governance"),
    }

    business_rule_interpretation["registry"] = {
        "schema_version": business_rule_registry.get("schema_version"),
        "status": business_rule_registry.get("status"),
        "registry_id": business_rule_registry.get("registry_id"),
        "ruleset_version": business_rule_registry.get("ruleset_version"),
        "rule_count": business_rule_registry.get("rule_count"),
        "fingerprint_sha256": business_rule_registry.get("fingerprint_sha256"),
        "errors": business_rule_registry.get("errors"),
        "governance": business_rule_registry.get("governance"),
    }

    enterprise_rule_governance = build_enterprise_rule_governance_audit(
        business_rule_interpretation=business_rule_interpretation,
        business_rule_registry=business_rule_registry,
        business_rule_context=business_rule_context,
        enterprise_metric_rule_registry=enterprise_metric_rule_registry,
    )


    # ------------------------------------------------------------------
    # FINAL SPEC
    # ------------------------------------------------------------------

    return {

        "schema_version":
            SCHEMA_VERSION,

        "domain":
            intent.get(
                "domain",
                "generic",
            ),

        "prompt":
            str(
                prompt
                or ""
            ),

        "intent":
            intent,

        "analytical_plan":
            analytical_plan,

        "analytical_results":
            analytical_results,

        "business_insights":
            business_insights,

        "business_rule_interpretation":
            business_rule_interpretation,

        "enterprise_rule_governance":
            enterprise_rule_governance,

        "enterprise_knowledge_context":
            enterprise_knowledge_context,

        "enterprise_knowledge_registry": {
            "schema_version": enterprise_knowledge_registry.get("schema_version"),
            "status": enterprise_knowledge_registry.get("status"),
            "registry_id": enterprise_knowledge_registry.get("registry_id"),
            "knowledge_version": enterprise_knowledge_registry.get("knowledge_version"),
            "entry_count": enterprise_knowledge_registry.get("entry_count"),
            "approved_entry_count": enterprise_knowledge_registry.get("approved_entry_count"),
            "fingerprint_sha256": enterprise_knowledge_registry.get("fingerprint_sha256"),
            "errors": enterprise_knowledge_registry.get("errors"),
            "governance": enterprise_knowledge_registry.get("governance"),
        },

        "enterprise_metric_rule_registry": {
            "schema_version": enterprise_metric_rule_registry.get("schema_version"),
            "status": enterprise_metric_rule_registry.get("status"),
            "registry_id": enterprise_metric_rule_registry.get("registry_id"),
            "ruleset_version": enterprise_metric_rule_registry.get("ruleset_version"),
            "rule_count": enterprise_metric_rule_registry.get("rule_count"),
            "fingerprint_sha256": enterprise_metric_rule_registry.get("fingerprint_sha256"),
            "errors": enterprise_metric_rule_registry.get("errors"),
            "governance": enterprise_metric_rule_registry.get("governance"),
        },


        "source": {

            "requested_source":
                reqsrc,

            "sheet":
                resolved,

            "resolved_source":
                resolved,

            "resolution_reason":
                (
                    source_context
                    or {}
                ).get(
                    "resolution_reason"
                )
                or reason,

            "rows":
                int(
                    len(df)
                ),

            "columns": [
                str(c)
                for c in df.columns
            ],
        },


        "pages":
            _pages(
                intent,
                caps,
            ),


        "filters": [
            c
            for c in caps
            if c.get("type")
            == "filter"
        ],


        "kpis": [
            c
            for c in caps
            if c.get("type")
            == "kpi"
        ],


        "charts":
            _charts_from_analyses(
                caps
            ),


        "tables": [
            c
            for c in caps
            if c.get("type")
            == "table"
        ],


        "analyses": [
            c
            for c in caps
            if c.get("type")
            == "analysis"
        ],


        "components":
            caps,


        "blocked":
            blocked_items,


        "coverage": {

            "requested":
                requested,

            "supported":
                supported,

            "derivable":
                derivable,

            "blocked":
                blocked,

            "fulfilled":
                fulfilled,

            "percent":
                percent,
        },


        "provenance": {

            "policy": (
                "governed_semantics > "
                "validated_business_rule > "
                "direct_semantic_contract > "
                "safe_derivation > "
                "fallback_semantics > "
                "BLOCKED"
            ),

            "semantic_roles":
                roles,

            "role_sources":
                sources,

            "ruleset_version":
                RULESET_VERSION,

            "derived": [

                {
                    "id":
                        c["id"],

                    "formula":
                        c.get(
                            "formula"
                        ),

                    "inputs":
                        c.get(
                            "source_columns"
                        ),

                    "dependencies":
                        c.get(
                            "dependencies"
                        ),

                    "rule":
                        c.get(
                            "rule"
                        ),

                    "execution":
                        c.get(
                            "execution"
                        ),

                    "source":
                        c[
                            "provenance"
                        ][
                            "source"
                        ],
                }

                for c in derived
            ],

            "blocked": [

                {
                    "id":
                        c["id"],

                    "reason":
                        c.get(
                            "reason"
                        ),
                }

                for c in blocked_items
            ],
        },
    }