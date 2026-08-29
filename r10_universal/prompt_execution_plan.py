from __future__ import annotations

from typing import Any, Dict, List

from universal_prompt_engine import compile_universal_plan


def _component(key: str, name: str, requested: bool, status: str, detail: str, missing=None, renderer=None) -> Dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "requested": bool(requested),
        "status": status,
        "detail": detail,
        "missing": list(missing or []),
        "renderer": renderer,
    }


def build_prompt_execution_plan(df, prompt: str, sheet: str = "") -> Dict[str, Any]:
    """Build an auditable execution contract from arbitrary prompt + arbitrary schema."""
    plan = compile_universal_plan(df, prompt, sheet=sheet)
    intent = plan.get("intent", {})
    roles = plan.get("semantic_roles", {})
    components: List[Dict[str, Any]] = []

    for metric in plan.get("kpis", []):
        components.append(_component(
            f"metric:{metric.get('key')}", metric.get("label") or metric.get("key"), True, "ready",
            "Métrica vinculada a columnas reales del archivo.", renderer="kpi"
        ))
    for metric in plan.get("blocked_metrics", []):
        components.append(_component(
            f"metric:{metric.get('key')}", metric.get("label") or metric.get("key"), True, "blocked",
            "La métrica fue solicitada pero faltan columnas para calcularla sin inventar datos.",
            missing=[metric.get("key")], renderer="kpi"
        ))

    requested_dims = set(intent.get("requested_dimensions") or [])
    for role in requested_dims:
        col = roles.get(role)
        components.append(_component(
            f"dimension:{role}", role.replace("_", " ").title(), True,
            "ready" if col else "blocked",
            f"Dimensión enlazada a '{col}'." if col else "No se encontró una columna compatible.",
            missing=[] if col else [role], renderer="filter/chart"
        ))

    analysis_renderer = {
        "trend": "charts", "ranking": "rankings", "lost_customers": "customer_risk",
        "profitability": "profitability", "data_quality": "validation", "detail": "detail_table",
        "opportunities": "opportunities",
    }
    for a in intent.get("requested_analyses") or []:
        requirements = {
            "trend": ["date"],
            "lost_customers": ["customer", "date"],
            "profitability": ["revenue"],
            "detail": [], "ranking": [], "data_quality": [], "opportunities": [],
        }.get(a, [])
        missing = [r for r in requirements if not roles.get(r)]
        components.append(_component(
            f"analysis:{a}", a.replace("_", " ").title(), True,
            "ready" if not missing else "blocked",
            "Análisis derivado de roles semánticos disponibles." if not missing else "No hay datos suficientes para ejecutar este análisis.",
            missing=missing, renderer=analysis_renderer.get(a)
        ))

    requested = [c for c in components if c["requested"]]
    ready = [c for c in requested if c["status"] == "ready"]
    partial = [c for c in requested if c["status"] == "partial"]
    blocked = [c for c in requested if c["status"] in {"blocked", "unsupported"}]
    coverage = round((len(ready) + 0.5 * len(partial)) / len(requested) * 100, 1) if requested else 100.0

    return {
        "version": "r10.2",
        "mode": "universal-prompt-driven",
        "source_of_truth": sheet or None,
        "prompt_length": len(str(prompt or "")),
        "requested_count": len(requested),
        "ready_count": len(ready),
        "partial_count": len(partial),
        "blocked_count": len(blocked),
        "coverage_pct": coverage,
        "semantic_roles": roles,
        "components": components,
    }
