from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Tuple

RULESET_VERSION = "r10.13c"

# Universal, deterministic derivations only. Company-specific formulas belong in
# the governed analytic/business-rule registry and are not added here.
DERIVED_METRIC_RULES: Dict[str, List[Dict[str, Any]]] = {
    "profit": [
        {
            "rule_id": "universal.profit.revenue_minus_cost.v1",
            "formula": "revenue - cost",
            "dependencies": ["revenue", "cost"],
            "operator": "difference_of_sums",
            "format": "currency",
        }
    ],
    "margin_pct": [
        {
            "rule_id": "universal.margin_pct.profit_over_revenue.v1",
            "formula": "profit / revenue * 100",
            "dependencies": ["profit", "revenue"],
            "operator": "ratio_of_sums_pct",
            "format": "percent",
        },
        {
            "rule_id": "universal.margin_pct.revenue_cost_over_revenue.v1",
            "formula": "(revenue - cost) / revenue * 100",
            "dependencies": ["revenue", "cost"],
            "operator": "difference_over_sum_pct",
            "format": "percent",
        },
    ],
    "profit_per_unit": [
        {
            "rule_id": "universal.profit_per_unit.profit_over_quantity.v1",
            "formula": "profit / quantity",
            "dependencies": ["profit", "quantity"],
            "operator": "ratio_of_sums",
            "format": "currency",
        },
        {
            "rule_id": "universal.profit_per_unit.revenue_cost_over_quantity.v1",
            "formula": "(revenue - cost) / quantity",
            "dependencies": ["revenue", "cost", "quantity"],
            "operator": "difference_over_sum",
            "format": "currency",
        },
    ],
    "price_per_unit": [
        {
            "rule_id": "universal.price_per_unit.revenue_over_quantity.v1",
            "formula": "revenue / quantity",
            "dependencies": ["revenue", "quantity"],
            "operator": "ratio_of_sums",
            "format": "currency",
        }
    ],
    "cost_per_unit": [
        {
            "rule_id": "universal.cost_per_unit.cost_over_quantity.v1",
            "formula": "cost / quantity",
            "dependencies": ["cost", "quantity"],
            "operator": "ratio_of_sums",
            "format": "currency",
        }
    ],
    "freight_per_unit": [
        {
            "rule_id": "universal.freight_per_unit.freight_over_quantity.v1",
            "formula": "freight / quantity",
            "dependencies": ["freight", "quantity"],
            "operator": "ratio_of_sums",
            "format": "currency",
        }
    ],
    "operations": [
        {
            "rule_id": "universal.operations.nunique_transaction.v1",
            "formula": "nunique(transaction_id)",
            "dependencies": ["transaction_id"],
            "operator": "nunique",
            "format": "integer",
        }
    ],
    "ticket_avg": [
        {
            "rule_id": "universal.ticket_avg.revenue_over_operations.v1",
            "formula": "revenue / nunique(transaction_id)",
            "dependencies": ["revenue", "transaction_id"],
            "operator": "sum_over_nunique",
            "format": "currency",
        }
    ],
    "active_customers": [
        {
            "rule_id": "universal.active_customers.nunique_customer_id.v1",
            "formula": "nunique(customer_id)",
            "dependencies": ["customer_id"],
            "operator": "nunique",
            "format": "integer",
        },
        {
            "rule_id": "universal.active_customers.nunique_customer.v1",
            "formula": "nunique(customer)",
            "dependencies": ["customer"],
            "operator": "nunique",
            "format": "integer",
        },
    ],
    "active_sellers": [
        {
            "rule_id": "universal.active_sellers.nunique_seller.v1",
            "formula": "nunique(seller)",
            "dependencies": ["seller"],
            "operator": "nunique",
            "format": "integer",
        }
    ],
    "products_sold": [
        {
            "rule_id": "universal.products_sold.nunique_product.v1",
            "formula": "nunique(product)",
            "dependencies": ["product"],
            "operator": "nunique",
            "format": "integer",
        }
    ],
}


def iter_rules(metric: str) -> Iterable[Dict[str, Any]]:
    return tuple(DERIVED_METRIC_RULES.get(str(metric or ""), ()))


def select_rule(metric: str, available_roles: Dict[str, Any], governed_roles: Optional[Iterable[str]] = None) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    available = {str(k) for k, v in dict(available_roles or {}).items() if v}
    governed = {str(x) for x in (governed_roles or ())}
    best_missing: List[str] = []
    for rule in iter_rules(metric):
        deps = [str(x) for x in rule.get("dependencies") or []]
        missing = [x for x in deps if x not in available]
        governed_required = [str(x) for x in rule.get("requires_governed_dependency") or []]
        ungoverned = [x for x in governed_required if x not in governed]
        if not missing and not ungoverned:
            return dict(rule), []
        candidate = missing + [f"governed:{x}" for x in ungoverned]
        if not best_missing or len(candidate) < len(best_missing):
            best_missing = candidate
    return None, best_missing


def rule_public_metadata(rule: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rule_id": rule.get("rule_id"),
        "ruleset_version": RULESET_VERSION,
        "scope": "universal",
        "operator": rule.get("operator"),
        "zero_division": "N/D",
        "format": rule.get("format") or "number",
    }


def evaluate_rule(df, capability: Dict[str, Any]) -> Optional[float]:
    """Deterministically evaluate one resolved metric capability on a dataframe.

    Returns None for blocked/unsupported operators or zero denominators. This is
    intentionally small and whitelist-based; arbitrary formulas are never eval'd.
    """
    if str(capability.get("status") or "") != "DERIVABLE":
        return None
    execution = dict(capability.get("execution") or {})
    op = str(execution.get("operator") or "")
    cols = [str(c) for c in capability.get("source_columns") or [] if c]

    def _sum(col: str) -> float:
        if col not in df.columns:
            return 0.0
        import pandas as pd
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())

    def _nunique(col: str) -> int:
        if col not in df.columns:
            return 0
        s = df[col]
        return int(s.dropna().astype(str).str.strip().replace("", None).dropna().nunique())

    if op == "difference_of_sums" and len(cols) >= 2:
        return _sum(cols[0]) - _sum(cols[1])
    if op == "ratio_of_sums" and len(cols) >= 2:
        den = _sum(cols[1])
        return (_sum(cols[0]) / den) if den else None
    if op == "difference_over_sum" and len(cols) >= 3:
        den = _sum(cols[2])
        return ((_sum(cols[0]) - _sum(cols[1])) / den) if den else None
    if op == "ratio_of_sums_pct" and len(cols) >= 2:
        den = _sum(cols[1])
        return (100.0 * _sum(cols[0]) / den) if den else None
    if op == "difference_over_sum_pct" and len(cols) >= 2:
        den = _sum(cols[0])
        return (100.0 * (_sum(cols[0]) - _sum(cols[1])) / den) if den else None
    if op == "nunique" and cols:
        return float(_nunique(cols[0]))
    if op == "sum_over_nunique" and len(cols) >= 2:
        den = _nunique(cols[1])
        return (_sum(cols[0]) / den) if den else None
    return None
