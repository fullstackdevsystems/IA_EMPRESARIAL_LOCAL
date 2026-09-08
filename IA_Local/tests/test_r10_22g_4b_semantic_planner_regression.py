from __future__ import annotations

import pandas as pd

import dashboard_dynamic

from dashboard_dynamic import (
    _fallback_plan,
    _validate_plan,
)

from dashboard_prompt_guard import (
    enforce_prompt_contract,
    requested_intents,
)

from enterprise_prompt_compiler import (
    compile_enterprise_prompt,
)

from prompt_polarity import (
    positive_request_text,
)

from semantic_layer import (
    resolve_semantic_map,
)

from universal_prompt_engine import (
    infer_semantic_roles,
    parse_prompt_intent,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "CHECK:",
        name,
        "PASS",
    )


df = pd.DataFrame(
    {
        "VentaID": [1, 2, 3, 4],
        "Folio": ["F1", "F2", "F3", "F4"],

        "FechaVenta": pd.to_datetime(
            [
                "2026-01-05",
                "2026-01-10",
                "2026-02-02",
                "2026-02-08",
            ]
        ),

        "ClienteID": [10, 11, 10, 12],
        "CodigoCliente": ["C10", "C11", "C10", "C12"],
        "Cliente": ["A", "B", "A", "C"],

        "Segmento": [
            "Corporativo",
            "Retail",
            "Corporativo",
            "Retail",
        ],

        "Vendedor": [
            "V1",
            "V2",
            "V1",
            "V3",
        ],

        "Sucursal": [
            "Culiacan",
            "Mazatlan",
            "Culiacan",
            "Guasave",
        ],

        "Estatus": [
            "FACTURADA",
            "FACTURADA",
            "CANCELADA",
            "FACTURADA",
        ],

        "Subtotal": [
            100.0,
            200.0,
            300.0,
            400.0,
        ],

        "IVA": [
            16.0,
            32.0,
            48.0,
            64.0,
        ],

        "VentaTotal": [
            116.0,
            232.0,
            348.0,
            464.0,
        ],
    }
)


prompt = (
    "Genera un dashboard ejecutivo de ventas "
    "usando VentaTotal como importe de ventas. "
    "Incluye KPI de venta total, numero de ventas, "
    "ticket promedio y clientes. "
    "Incluye evolucion mensual por FechaVenta. "
    "Incluye rankings por Cliente, Vendedor y Sucursal. "
    "Incluye distribucion por Estatus y Segmento. "
    "Incluye filtros por FechaVenta, Sucursal, "
    "Vendedor, Estatus y Segmento. "
    "Incluye detalle transaccional. "
    "No inventes costos, utilidad, presupuesto, "
    "fletes ni productos. "
    "Usa solamente las columnas disponibles. "
    "Top 10."
)


print()
print(
    "=== POLARITY ==="
)


positive = positive_request_text(
    prompt
)


for forbidden_text in [
    "costos",
    "utilidad",
    "presupuesto",
    "fletes",
    "productos",
]:
    check(
        "negated text removed: "
        + forbidden_text,
        forbidden_text
        not in positive.lower(),
    )


check(
    "positive VentaTotal preserved",
    "ventatotal"
    in positive.lower(),
)


guard_intents = requested_intents(
    prompt
)


print(
    "GUARD INTENTS:",
    guard_intents,
)


check(
    "budget false intent eliminated",
    "budget"
    not in guard_intents,
)


print()
print(
    "=== UNIVERSAL INTENT ==="
)


intent = parse_prompt_intent(
    prompt
)


print(
    "METRICS:",
    intent.requested_metrics,
)

print(
    "DIMENSIONS:",
    intent.requested_dimensions,
)


check(
    "revenue requested",
    "revenue"
    in intent.requested_metrics,
)

check(
    "ticket average requested",
    "ticket_avg"
    in intent.requested_metrics,
)


for forbidden in [
    "cost",
    "profit",
    "freight",
]:
    check(
        "negated metric eliminated: "
        + forbidden,
        forbidden
        not in intent.requested_metrics,
    )


check(
    "negated product dimension eliminated",
    "product"
    not in intent.requested_dimensions,
)


for required in [
    "customer",
    "seller",
    "branch",
    "status",
    "category",
    "date",
]:
    check(
        "requested dimension: "
        + required,
        required
        in intent.requested_dimensions,
    )


print()
print(
    "=== UNIVERSAL SEMANTIC ROLES ==="
)


roles = infer_semantic_roles(
    df
)


for key in [
    "transaction_id",
    "date",
    "customer_id",
    "customer",
    "branch",
    "seller",
    "category",
    "status",
    "revenue",
]:
    print(
        "ROLE:",
        key,
        "=>",
        roles.get(key),
    )


check(
    "universal revenue VentaTotal",
    roles.get("revenue")
    == "VentaTotal",
)

check(
    "universal revenue not VentaID",
    roles.get("revenue")
    != "VentaID",
)

check(
    "universal date FechaVenta",
    roles.get("date")
    == "FechaVenta",
)

check(
    "universal customer id ClienteID",
    roles.get("customer_id")
    == "ClienteID",
)

check(
    "universal branch Sucursal",
    roles.get("branch")
    == "Sucursal",
)

check(
    "universal status Estatus",
    roles.get("status")
    == "Estatus",
)

check(
    "universal category Segmento",
    roles.get("category")
    == "Segmento",
)


print()
print(
    "=== STRICT SEMANTIC MAP ==="
)


strict = resolve_semantic_map(
    df
)


usable = dict(
    strict.get("usable")
    or {}
)


for key in [
    "date",
    "reference",
    "customer_id",
    "customer",
    "branch",
    "seller",
    "category",
    "status",
    "revenue",
]:
    print(
        "STRICT ROLE:",
        key,
        "=>",
        usable.get(key),
    )


check(
    "strict revenue VentaTotal",
    usable.get("revenue")
    == "VentaTotal",
)

check(
    "strict date FechaVenta",
    usable.get("date")
    == "FechaVenta",
)

check(
    "strict reference Folio",
    usable.get("reference")
    == "Folio",
)

strict_customer_id = usable.get(
    "customer_id"
)


check(
    "strict customer id governed",
    strict_customer_id
    in {
        "ClienteID",
        "CodigoCliente",
    },
)


check(
    "customer id alternatives have same cardinality",
    int(
        df["ClienteID"].nunique(
            dropna=True
        )
    )
    == int(
        df["CodigoCliente"].nunique(
            dropna=True
        )
    ),
)


print(
    "STRICT CUSTOMER ID GOVERNED COLUMN:",
    strict_customer_id,
)

check(
    "strict branch Sucursal",
    usable.get("branch")
    == "Sucursal",
)

check(
    "strict status Estatus",
    usable.get("status")
    == "Estatus",
)

check(
    "strict category Segmento",
    usable.get("category")
    == "Segmento",
)


print()
print(
    "=== PROMPT GUARD ==="
)


seed = {
    "title": "Diagnostic",
    "subtitle": "Diagnostic",
    "planner": "diagnostic-seed",

    "kpis": [
        {
            "key": "revenue",
            "label": "VENTA TOTAL",
            "op": "sum",
            "column": "VentaTotal",
            "format": "currency",
        }
    ],

    "charts": [
        {
            "type": "bar",
            "title": "Venta por Cliente",
            "dimension": "Cliente",
            "measure": "VentaTotal",
            "op": "sum",
            "top_n": 10,
        }
    ],

    "filters": [],

    "table": {
        "title": "Detalle",
        "columns": list(
            df.columns
        ),
        "limit": 100,
    },
}


guarded = enforce_prompt_contract(
    seed,
    df,
    prompt,
    "SQL DB_VENTAS",
    "SQL_REAL",
)


print(
    "GUARD STATUS:",
    guarded.get("status"),
)

print(
    "GUARD MISSING:",
    guarded.get(
        "missing_requirements"
    ),
)


check(
    "guard ready",
    guarded.get("status")
    == "ready",
)

check(
    "guard missing empty",
    not guarded.get(
        "missing_requirements"
    ),
)


print()
print(
    "=== FINAL ENTERPRISE COMPILER ==="
)


compiled = compile_enterprise_prompt(
    guarded,
    df,
    prompt,
    "SQL DB_VENTAS",
    "SQL_REAL",
)


print(
    "FINAL STATUS:",
    compiled.get("status"),
)

print(
    "FINAL MISSING:",
    compiled.get(
        "missing_requirements"
    ),
)

print(
    "FINAL KPIS:",
    compiled.get("kpis"),
)

print(
    "FINAL FILTERS:",
    compiled.get("filters"),
)

print(
    "FINAL CHARTS:",
    compiled.get("charts"),
)


check(
    "final compiler ready",
    compiled.get("status")
    == "ready",
)

check(
    "final missing empty",
    not compiled.get(
        "missing_requirements"
    ),
)


kpis = [
    item
    for item in (
        compiled.get("kpis")
        or []
    )
    if isinstance(
        item,
        dict,
    )
]


check(
    "VentaTotal sum KPI present",
    any(
        item.get("op") == "sum"
        and item.get("column")
            == "VentaTotal"
        for item in kpis
    ),
)


check(
    "VentaID revenue KPI eliminated",
    not any(
        item.get("key")
            == "revenue"
        and item.get("column")
            == "VentaID"
        for item in kpis
    ),
)


unique_customers = next(
    (
        item
        for item in kpis
        if item.get("key")
            == "unique_customers"
    ),
    None,
)


check(
    "unique customers KPI present",
    isinstance(
        unique_customers,
        dict,
    ),
)


check(
    "unique customers KPI uses strict customer id",
    unique_customers.get(
        "column"
    )
    == strict_customer_id,
)


ticket = next(
    (
        item
        for item in kpis
        if item.get("key")
            == "ticket_avg"
    ),
    None,
)


check(
    "ticket KPI present",
    isinstance(
        ticket,
        dict,
    ),
)

check(
    "ticket numerator VentaTotal",
    ticket.get("numerator")
    == "VentaTotal",
)

check(
    "ticket denominator Folio",
    ticket.get("denominator")
    == "Folio",
)


filters = {
    item.get("column")
    for item in (
        compiled.get("filters")
        or []
    )
    if isinstance(
        item,
        dict,
    )
}


for required_filter in [
    "FechaVenta",
    "Sucursal",
    "Vendedor",
    "Estatus",
    "Segmento",
]:
    check(
        "filter present: "
        + required_filter,
        required_filter
        in filters,
    )


charts = [
    item
    for item in (
        compiled.get("charts")
        or []
    )
    if isinstance(
        item,
        dict,
    )
]


check(
    "charts exist",
    bool(charts),
)

check(
    "VentaTotal chart exists",
    any(
        item.get("measure")
            == "VentaTotal"
        for item in charts
    ),
)

check(
    "VentaID revenue chart eliminated",
    not any(
        item.get("measure")
            == "VentaID"
        for item in charts
    ),
)


chart_dimensions = {
    item.get("dimension")
    for item in charts
}


for required_chart in [
    "FechaVenta",
    "Cliente",
    "Vendedor",
    "Sucursal",
    "Estatus",
    "Segmento",
]:
    check(
        "chart dimension present: "
        + required_chart,
        required_chart
        in chart_dimensions,
    )


print()
print(
    "=== TICKET AVG RENDER CONTRACT ==="
)


fallback = _fallback_plan(
    df,
    prompt,
    "SQL DB_VENTAS",
    "SQL_REAL",
)


ticket_candidate = {
    "planner": "ticket-test",

    "kpis": [
        {
            "key": "ticket_avg",
            "label": "TICKET PROMEDIO",
            "op": "sum_div_nunique",
            "numerator": "VentaTotal",
            "denominator": "Folio",
            "format": "currency",
        }
    ],
}


validated = _validate_plan(
    ticket_candidate,
    df,
    fallback,
)


check(
    "validator preserves sum_div_nunique",
    any(
        isinstance(
            item,
            dict,
        )
        and item.get("op")
            == "sum_div_nunique"
        for item in (
            validated.get("kpis")
            or []
        )
    ),
)


check(
    "browser runtime implements sum_div_nunique",
    "op==='sum_div_nunique'"
    in dashboard_dynamic._HTML,
)


expected_ticket = (
    float(
        df["VentaTotal"].sum()
    )
    /
    int(
        df["Folio"].nunique()
    )
)


check(
    "deterministic ticket fixture",
    abs(
        expected_ticket
        - 290.0
    )
    < 0.000001,
)


print()
print(
    "=================================================="
)

print(
    "R10.22G.4B SEMANTIC PLANNER REGRESSION: PASS"
)

print(
    "NEGATION POLARITY: PASS"
)

print(
    "CAMELCASE SEMANTICS: PASS"
)

print(
    "VentaTotal REVENUE BINDING: PASS"
)

print(
    "VentaID REVENUE MISBIND: ELIMINATED"
)

print(
    "REQUESTED FILTER COVERAGE: PASS"
)

print(
    "REQUESTED CHART COVERAGE: PASS"
)

print(
    "TICKET AVG CONTRACT: PASS"
)

print(
    "=================================================="
)
