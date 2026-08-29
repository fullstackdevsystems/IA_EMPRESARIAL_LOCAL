from __future__ import annotations

from typing import Any, Dict

from universal_prompt_engine import compile_universal_plan, norm
from semantic_contract_enforcer import enforce_semantic_contract


def is_enterprise_analytics_prompt(prompt: str) -> bool:
    """R10.2: any non-empty analytical request can be compiled; no domain keyword gate."""
    p = norm(prompt)
    return bool(p)


def compile_enterprise_prompt(
    plan: Dict[str, Any], df, prompt: str,
    filename: str = "", sheet: str = ""
) -> Dict[str, Any]:
    """Universal prompt adapter.

    Replaces the R9/R10.1 grain-specific compiler. It never requires physical
    columns such as Toneladas_Vendidas, Importe_Venta, ctrl_alm, etc. Instead it
    binds prompt concepts to columns discovered in the current dataframe.
    """
    out = dict(plan or {})
    if not str(prompt or "").strip():
        return out

    universal = compile_universal_plan(df, prompt, filename, sheet)
    universal = enforce_semantic_contract(universal, df, prompt)

    # The universal contract controls domain-sensitive parts. Keep a validated
    # generic fallback only when the prompt/data did not produce a replacement.
    if universal.get("kpis"):
        out["kpis"] = universal["kpis"]
    if universal.get("charts"):
        out["charts"] = universal["charts"]
    if universal.get("filters"):
        out["filters"] = universal["filters"]
    if universal.get("table", {}).get("columns"):
        out["table"] = universal["table"]

    out["title"] = universal.get("title") or out.get("title") or "Dashboard Ejecutivo"
    out["subtitle"] = universal.get("subtitle") or out.get("subtitle") or filename
    out["top_n"] = universal.get("top_n", out.get("top_n", 15))
    out["status"] = universal.get("status", out.get("status", "ready"))
    out["semantic_columns_strict"] = universal.get("semantic_roles", {})
    out["data_profile"] = universal.get("data_profile", {})
    out["missing_requirements"] = [m.get("key") for m in universal.get("blocked_metrics", [])]
    out["warnings"] = list(dict.fromkeys(list(out.get("warnings") or []) + list(universal.get("warnings") or []) + [
        "R10.2 usa un compilador universal: el dashboard se vincula al prompt y al esquema real del archivo, no a un prompt o industria específicos.",
        "Las cifras base se calculan por código sobre columnas existentes; las métricas no soportadas quedan como N/D en vez de inventarse.",
    ]))
    out["prompt_compiler"] = {
        "version": "r10.2",
        "mode": "universal-prompt-driven",
        "source_of_truth": sheet or None,
        "semantic_roles": universal.get("semantic_roles", {}),
        "requested_metrics": universal.get("intent", {}).get("requested_metrics", []),
        "requested_dimensions": universal.get("intent", {}).get("requested_dimensions", []),
        "blocked_metrics": out["missing_requirements"],
        "calculation_policy": "deterministic_python",
        "no_invent_data": True,
    }

    from prompt_execution_plan import build_prompt_execution_plan
    out["execution_plan"] = build_prompt_execution_plan(df, prompt, sheet)
    out["planner"] = str(out.get("planner") or "validated") + "|universal-prompt-compiler-r10.2"
    return out
