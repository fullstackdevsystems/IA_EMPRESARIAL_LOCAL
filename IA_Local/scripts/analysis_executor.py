from __future__ import annotations
from typing import Any, Dict
import pandas as pd

EXECUTOR_VERSION = "r10.14b"
SUPPORTED = "SUPPORTED"
DERIVABLE = "DERIVABLE"
BLOCKED = "BLOCKED"


def _sum(df, col):
    if not col or col not in df.columns:
        return None
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())


def _metric_value(df, e):
    status = str(e.get("status") or "").upper()
    cols = [str(c) for c in e.get("source_columns") or [] if c]
    if status == SUPPORTED:
        return _sum(df, cols[0] if cols else None)
    if status != DERIVABLE:
        return None
    op = str((e.get("rule") or {}).get("operator") or "")
    vals = [float(_sum(df, c) or 0.0) for c in cols]
    if op == "difference_of_sums" and len(vals) >= 2:
        return vals[0] - vals[1]
    if op == "ratio_of_sums" and len(vals) >= 2:
        return vals[0] / vals[1] if vals[1] else None
    if op == "difference_over_sum_pct" and len(vals) >= 2:
        return 100.0 * (vals[0] - vals[1]) / vals[0] if vals[0] else None
    if op == "ratio_of_sums_pct" and len(vals) >= 2:
        return 100.0 * vals[0] / vals[1] if vals[1] else None
    if op == "nunique" and cols and cols[0] in df.columns:
        s = df[cols[0]].dropna().astype(str).str.strip()
        return float(s[s != ""].nunique())
    if op == "sum_over_nunique" and len(cols) >= 2 and cols[1] in df.columns:
        s = df[cols[1]].dropna().astype(str).str.strip()
        n = int(s[s != ""].nunique())
        return vals[0] / n if n else None
    return None


def _metrics(task):
    out, seen = [], set()
    for e in list(task.get("evidence") or []) + list(task.get("optional_evidence") or []):
        k = str(e.get("key") or "")
        if e.get("kind") == "metric" and k and k not in seen and str(e.get("status") or "").upper() in {SUPPORTED, DERIVABLE}:
            out.append(e)
            seen.add(k)
    return out


def _snapshot(df, task):
    return {
        "kind": "metric_snapshot",
        "record_count": int(len(df)),
        "metrics": {str(e.get("key")): _metric_value(df, e) for e in _metrics(task)},
    }


def _trend(df, task, roles):
    col = roles.get("date")
    if not col or col not in df.columns:
        return {"kind": "time_trend", "grain": "month", "rows": [], "reason": "Date role unavailable."}
    p = pd.to_datetime(df[col], errors="coerce")
    w = df.loc[p.notna()].copy()
    w["__period"] = p.loc[p.notna()].dt.to_period("M").astype(str)
    rows = []
    for period, g in w.groupby("__period", sort=True):
        row = {"period": str(period), "record_count": int(len(g))}
        for e in _metrics(task):
            row[str(e.get("key"))] = _metric_value(g, e)
        rows.append(row)
    return {"kind": "time_trend", "grain": "month", "date_column": str(col), "rows": rows}


def _grouped(df, task, roles):
    dims = [str(x) for x in task.get("required_dimensions") or [] if roles.get(str(x))]
    cols = [roles[d] for d in dims]
    if not cols:
        return _snapshot(df, task)
    rows = []
    for keys, g in df.groupby(cols, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {dims[i]: ("Sin dato" if pd.isna(v) else str(v)) for i, v in enumerate(keys)}
        row["record_count"] = int(len(g))
        for e in _metrics(task):
            row[str(e.get("key"))] = _metric_value(g, e)
        rows.append(row)
        if len(rows) >= 500:
            break
    return {"kind": "grouped_analysis", "dimensions": dims, "row_limit": 500, "rows": rows}


def execute_governed_analytical_plan(df, *, analytical_plan: Dict[str, Any], roles: Dict[str, Any]) -> Dict[str, Any]:
    results = []
    grouped_ops = {
        "customer_profile", "customer_deterioration", "route_analysis", "warehouse_movement",
        "origin_share", "destination_share", "customer_pickup", "aging", "collections",
        "critical_stock", "inventory_turnover", "obsolete_inventory",
    }
    snapshot_ops = {
        "executive_summary", "profitability_analysis", "risk_scan", "opportunity_scan",
        "dimension_ranking", "data_quality", "transaction_detail",
    }
    for task in list((analytical_plan or {}).get("tasks") or []):
        status = str(task.get("status") or "").upper()
        base = {
            "task_id": task.get("id"),
            "analysis": task.get("analysis"),
            "operator": task.get("operator"),
            "plan_status": status,
        }
        if status == BLOCKED:
            results.append({**base, "execution_status": "NOT_EXECUTED", "reason": task.get("reason") or "Blocked by governed evidence.", "result": None})
            continue
        op = str(task.get("operator") or "")
        if op in {"time_trend", "monthly_movement"}:
            result = _trend(df, task, roles)
        elif op in grouped_ops:
            result = _grouped(df, task, roles)
        elif op in snapshot_ops:
            result = _snapshot(df, task)
        else:
            results.append({**base, "execution_status": "NOT_EXECUTED", "reason": f"Operator '{op}' is not in the R10.14B whitelist.", "result": None})
            continue
        results.append({**base, "execution_status": "EXECUTED", "reason": None, "result": result})
    return {
        "schema_version": EXECUTOR_VERSION,
        "mode": "governed-whitelist-execution",
        "task_count": len(results),
        "executed_count": sum(r["execution_status"] == "EXECUTED" for r in results),
        "not_executed_count": sum(r["execution_status"] == "NOT_EXECUTED" for r in results),
        "results": results,
        "governance": {
            "blocked_tasks_are_never_executed": True,
            "arbitrary_formula_evaluation": False,
            "whitelist_only": True,
        },
    }
