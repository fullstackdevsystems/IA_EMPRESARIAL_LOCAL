from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dashboard_spec_builder import resolve_metric


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"PASS: {name}")


roles = {
    "quantity": "Toneladas_Vendidas",
}

sources = {
    "quantity": "direct_column",
}

columns = [
    "Toneladas_Vendidas",
    "Costo_Flete_Corto",
    "Costo_Flete_Largo",
    "Costo_Flete_Traspaso",
]

validated_context = {
    "company_id": "TENANT_A",
    "user_id": "ADMIN_A",
    "bindings": [
        {
            "target": "freight",
            "rule_type": "metric",
            "expression": (
                "Costo_Flete_Corto + "
                "Costo_Flete_Largo + "
                "Costo_Flete_Traspaso"
            ),
            "status": "VALIDATED",
        }
    ],
    "precedence": (
        "validated_business_rule > "
        "validated_semantic_definition > system_inference"
    ),
}

freight = resolve_metric(
    "freight",
    roles,
    sources,
    analytic_context=validated_context,
    available_columns=columns,
)

check("validated tenant freight becomes derivable", freight["status"] == "DERIVABLE")
check("validated analytic rule is provenance", freight.get("provenance", {}).get("source") == "validated_analytic_rule")
check(
    "validated expression preserved",
    freight.get("formula")
    == "Costo_Flete_Corto + Costo_Flete_Largo + Costo_Flete_Traspaso",
)

freight_per_unit = resolve_metric(
    "freight_per_unit",
    {**roles, "freight": "_flete"},
    {**sources, "freight": "validated_analytic_rule"},
    analytic_context=validated_context,
    available_columns=columns,
)

check("freight per unit becomes derivable", freight_per_unit["status"] == "DERIVABLE")

blocked = resolve_metric(
    "freight",
    roles,
    sources,
    analytic_context={
        "company_id": "TENANT_B",
        "user_id": "ADMIN_B",
        "bindings": [],
    },
    available_columns=columns,
)

check("freight remains fail closed without validated rule", blocked["status"] == "BLOCKED")

unrelated = resolve_metric(
    "revenue",
    {"revenue": "Importe_Venta"},
    {"revenue": "direct_column"},
    analytic_context=validated_context,
    available_columns=columns + ["Importe_Venta"],
)

check("unrelated direct metric remains supported", unrelated["status"] == "SUPPORTED")

print("R10_27_GOVERNED_FREIGHT_CAPABILITY_REGRESSION=PASS")