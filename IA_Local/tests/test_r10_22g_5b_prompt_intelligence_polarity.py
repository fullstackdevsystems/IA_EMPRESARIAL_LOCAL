from __future__ import annotations

from dashboard_spec_builder import _pages
from dynamic_renderer import build_dynamic_renderer_model
from prompt_intelligence import parse_prompt_intelligence


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "CHECK:",
        name,
        "PASS",
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
    "=== NEGATED REAL G.4 PROMPT ==="
)


intent = parse_prompt_intelligence(
    prompt
)


print(
    "DOMAIN:",
    intent.get("domain"),
)

print(
    "DOMAIN EVIDENCE:",
    intent.get(
        "domain_evidence"
    ),
)

print(
    "METRICS:",
    intent.get("metrics"),
)

print(
    "DIMENSIONS:",
    intent.get("dimensions"),
)

print(
    "PAGES:",
    intent.get("pages"),
)

print(
    "EXCLUDED:",
    intent.get("excluded"),
)


check(
    "domain remains sales",
    intent.get("domain")
    == "sales",
)


domain_evidence = (
    intent.get(
        "domain_evidence"
    )
    or {}
)


check(
    "negated logistics evidence removed",
    int(
        (
            domain_evidence.get(
                "logistics"
            )
            or {}
        ).get(
            "score"
        )
        or 0
    )
    == 0,
)


check(
    "negated finance evidence removed",
    int(
        (
            domain_evidence.get(
                "finance"
            )
            or {}
        ).get(
            "score"
        )
        or 0
    )
    == 0,
)


for forbidden_metric in [
    "cost",
    "profit",
    "freight",
]:
    check(
        "negated metric absent: "
        + forbidden_metric,
        forbidden_metric
        not in (
            intent.get("metrics")
            or []
        ),
    )


check(
    "negated product dimension absent",
    "product"
    not in (
        intent.get("dimensions")
        or []
    ),
)


check(
    "negated logistics page absent",
    "logistics"
    not in (
        intent.get("pages")
        or []
    ),
)


excluded = (
    intent.get("excluded")
    or {}
)


for expected_metric in [
    "cost",
    "profit",
    "freight",
]:
    check(
        "negated metric audited: "
        + expected_metric,
        expected_metric
        in (
            excluded.get(
                "metrics"
            )
            or []
        ),
    )


check(
    "negated product dimension audited",
    "product"
    in (
        excluded.get(
            "dimensions"
        )
        or []
    ),
)


check(
    "negated logistics page audited",
    "logistics"
    in (
        excluded.get(
            "pages"
        )
        or []
    ),
)


pages = _pages(
    intent,
    [],
)


page_ids = [
    str(
        page.get("id")
    )
    for page in pages
]


print(
    "COMPOSED PAGE IDS:",
    page_ids,
)


check(
    "customers page retained",
    "customers"
    in page_ids,
)


check(
    "logistics page not composed",
    "logistics"
    not in page_ids,
)


renderer = (
    build_dynamic_renderer_model(
        {
            "domain":
                intent.get(
                    "domain"
                ),

            "pages":
                pages,
        },
        {},
    )
)


renderer_page_ids = [
    str(
        page.get("id")
    )
    for page in (
        renderer.get("pages")
        or []
    )
]


print(
    "RENDERER DOMAIN:",
    renderer.get("domain"),
)

print(
    "RENDERER PAGE IDS:",
    renderer_page_ids,
)


check(
    "renderer domain sales",
    renderer.get("domain")
    == "sales",
)


check(
    "renderer logistics absent",
    "logistics"
    not in renderer_page_ids,
)


# ==================================================
# POSITIVE CONTROL:
# logistics must still work when explicitly requested.
# ==================================================

print()
print(
    "=== POSITIVE LOGISTICS CONTROL ==="
)


positive_prompt = (
    "Genera un dashboard de logistica "
    "con rutas y fletes."
)


positive_intent = (
    parse_prompt_intelligence(
        positive_prompt
    )
)


print(
    "POSITIVE DOMAIN:",
    positive_intent.get(
        "domain"
    ),
)

print(
    "POSITIVE PAGES:",
    positive_intent.get(
        "pages"
    ),
)

print(
    "POSITIVE DOMAIN EVIDENCE:",
    positive_intent.get(
        "domain_evidence"
    ),
)


check(
    "explicit logistics still detected",
    positive_intent.get(
        "domain"
    )
    == "logistics",
)


check(
    "explicit logistics page retained",
    "logistics"
    in (
        positive_intent.get(
            "pages"
        )
        or []
    ),
)


check(
    "explicit logistics evidence positive",
    int(
        (
            positive_intent.get(
                "domain_evidence",
                {}
            ).get(
                "logistics",
                {}
            ).get(
                "score"
            )
            or 0
        )
    )
    > 0,
)



# ==================================================
# GOVERNED FREIGHT SAFETY CONTROL
#
# Freight is not excluded when the prompt explicitly
# asks for governed validation / provenance and a
# blocked or N/D fallback.
# ==================================================

print()
print(
    "=== GOVERNED FREIGHT SAFETY CONTROL ==="
)


governed_freight_prompt = (
    "Analiza el archivo exclusivamente desde una "
    "perspectiva logistica. "
    "Incluye movimientos, rutas y almacenes. "
    "No inventes el costo total de flete. "
    "Si no existe una regla validada para combinar "
    "los diferentes componentes de flete, "
    "muestralo como N/D. "
    "No utilices una metrica derivada de flete "
    "salvo que exista provenance o una regla "
    "empresarial validada."
)


governed_intent = (
    parse_prompt_intelligence(
        governed_freight_prompt
    )
)


print(
    "GOVERNED DOMAIN:",
    governed_intent.get(
        "domain"
    ),
)

print(
    "GOVERNED METRICS:",
    governed_intent.get(
        "metrics"
    ),
)

print(
    "GOVERNED EXCLUDED METRICS:",
    (
        governed_intent.get(
            "excluded"
        )
        or {}
    ).get(
        "metrics"
    ),
)

print(
    "GOVERNED DOMAIN EVIDENCE:",
    governed_intent.get(
        "domain_evidence"
    ),
)


check(
    "governed freight domain logistics",
    governed_intent.get(
        "domain"
    )
    == "logistics",
)


check(
    "governed freight remains requested",
    "freight"
    in (
        governed_intent.get(
            "metrics"
        )
        or []
    ),
)


check(
    "governed freight not treated as simple exclusion",
    "freight"
    not in (
        (
            governed_intent.get(
                "excluded"
            )
            or {}
        ).get(
            "metrics"
        )
        or []
    ),
)


check(
    "governed freight evidence remains positive",
    int(
        (
            governed_intent.get(
                "domain_evidence",
                {}
            ).get(
                "logistics",
                {}
            ).get(
                "score"
            )
            or 0
        )
    )
    > 0,
)


print(
    "GOVERNED ANALYSES:",
    governed_intent.get(
        "analyses"
    ),
)

print(
    "GOVERNED EXCLUDED ANALYSES:",
    (
        governed_intent.get(
            "excluded"
        )
        or {}
    ).get(
        "analyses"
    ),
)


check(
    "governed freight analysis remains requested",
    "freight_analysis"
    in (
        governed_intent.get(
            "analyses"
        )
        or []
    ),
)


check(
    "governed freight analysis not simple exclusion",
    "freight_analysis"
    not in (
        (
            governed_intent.get(
                "excluded"
            )
            or {}
        ).get(
            "analyses"
        )
        or []
    ),
)


print()
print(
    "=================================================="
)

print(
    "R10.22G.5B PROMPT INTELLIGENCE POLARITY: PASS"
)

print(
    "NEGATED LOGISTICS DOMAIN EVIDENCE: ELIMINATED"
)

print(
    "NEGATED FINANCE DOMAIN EVIDENCE: ELIMINATED"
)

print(
    "NEGATED LOGISTICS PAGE: ELIMINATED"
)

print(
    "NEGATED METRICS/DIMENSIONS: AUDITABLE"
)

print(
    "EXPLICIT LOGISTICS POSITIVE CONTROL: PASS"
)

print(
    "=================================================="
)
