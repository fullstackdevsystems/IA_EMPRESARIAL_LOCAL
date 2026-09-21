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
        period_dates = pd.to_datetime(g[col], errors="coerce").dropna()
        row = {
            "period": str(period),
            "record_count": int(len(g)),
            "observed_min_date": (
                period_dates.min().date().isoformat()
                if not period_dates.empty
                else None
            ),
            "observed_max_date": (
                period_dates.max().date().isoformat()
                if not period_dates.empty
                else None
            ),
        }
        for e in _metrics(task):
            row[str(e.get("key"))] = _metric_value(g, e)
        rows.append(row)
    return {"kind": "time_trend", "grain": "month", "date_column": str(col), "rows": rows}


def _grouped(df, task, roles):
    dims = [str(x) for x in task.get("required_dimensions") or [] if roles.get(str(x))]
    cols = [roles[d] for d in dims]
    if not cols:
        return _snapshot(df, task)

    row_limit = 500
    grouped = df.groupby(cols, dropna=False, sort=False)
    total_group_count = int(grouped.ngroups)
    rows = []

    for keys, g in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {dims[i]: ("Sin dato" if pd.isna(v) else str(v)) for i, v in enumerate(keys)}
        row["record_count"] = int(len(g))
        for e in _metrics(task):
            row[str(e.get("key"))] = _metric_value(g, e)
        rows.append(row)
        if len(rows) >= row_limit:
            break

    return {
        "kind": "grouped_analysis",
        "dimensions": dims,
        "row_limit": row_limit,
        "returned_group_count": len(rows),
        "total_group_count": total_group_count,
        "is_truncated": total_group_count > len(rows),
        "rows": rows,
    }



def _cancellation_analysis(df, task, roles):
    """Deterministic cancellation/return facts from governed roles only."""
    quantity_col = roles.get("quantity")
    revenue_col = roles.get("revenue")
    reference_col = roles.get("invoice") or roles.get("reference")

    mask = pd.Series(False, index=df.index, dtype=bool)
    signals = []

    if quantity_col and quantity_col in df.columns:
        values = pd.to_numeric(df[quantity_col], errors="coerce")
        matched = (values < 0).fillna(False)
        mask = mask | matched
        signals.append({
            "signal": "negative_quantity",
            "source_column": str(quantity_col),
            "matched_rows": int(matched.sum()),
        })

    if revenue_col and revenue_col in df.columns:
        values = pd.to_numeric(df[revenue_col], errors="coerce")
        matched = (values < 0).fillna(False)
        mask = mask | matched
        signals.append({
            "signal": "negative_revenue",
            "source_column": str(revenue_col),
            "matched_rows": int(matched.sum()),
        })

    if reference_col and reference_col in df.columns:
        matched = (
            df[reference_col]
            .astype(str)
            .str.strip()
            .str.upper()
            .str.startswith("C", na=False)
        )
        matched = matched.fillna(False)
        mask = mask | matched
        signals.append({
            "signal": "reference_prefix_c",
            "source_column": str(reference_col),
            "matched_rows": int(matched.sum()),
        })

    if not signals:
        return {
            "kind": "cancellation_analysis",
            "evidence_available": False,
            "row_count": int(len(df)),
            "cancellation_rows": 0,
            "signals": [],
            "reason": (
                "No governed quantity, revenue, or invoice/reference "
                "role is available."
            ),
            "governance": {
                "deterministic": True,
                "uses_resolved_semantic_roles_only": True,
                "llm_numeric_inference": False,
                "llm_cancellation_detection": False,
                "business_thresholds_invented": False,
                "status_values_invented": False,
            },
        }

    row_count = int(len(df))
    cancellation_rows = int(mask.sum())

    result = {
        "kind": "cancellation_analysis",
        "evidence_available": True,
        "row_count": row_count,
        "cancellation_rows": cancellation_rows,
        "cancellation_row_pct": (
            float(cancellation_rows / row_count * 100.0)
            if row_count
            else 0.0
        ),
        "signals": signals,
        "governance": {
            "deterministic": True,
            "uses_resolved_semantic_roles_only": True,
            "llm_numeric_inference": False,
            "llm_cancellation_detection": False,
            "business_thresholds_invented": False,
            "status_values_invented": False,
        },
    }

    if revenue_col and revenue_col in df.columns:
        revenue = pd.to_numeric(df[revenue_col], errors="coerce")
        cancellation_revenue = revenue.where(mask)

        result["cancellation_revenue_net"] = float(
            cancellation_revenue.sum(skipna=True)
        )
        result["cancellation_revenue_impact_abs"] = float(
            cancellation_revenue.abs().sum(skipna=True)
        )

        positive_revenue = float(
            revenue.where(revenue > 0).sum(skipna=True)
        )
        result["positive_revenue"] = positive_revenue

        result["cancellation_impact_pct_of_positive_revenue"] = (
            float(
                result["cancellation_revenue_impact_abs"]
                / positive_revenue
                * 100.0
            )
            if positive_revenue > 0
            else None
        )

    return result



def _anomaly_scan(df, task, roles):
    """Detect statistical anomalies in governed monthly metric series.

    IQR is a statistical detection rule only. It does not assign business
    severity, risk, opportunity, or any other enterprise classification.
    """
    trend = _trend(df, task, roles)
    rows = list(trend.get("rows") or [])

    base_governance = {
        "deterministic": True,
        "method": "iqr",
        "statistical_rule": "values outside Q1 - 1.5*IQR or Q3 + 1.5*IQR",
        "statistical_multiplier": 1.5,
        "business_thresholds_invented": False,
        "business_classification_applied": False,
        "llm_numeric_inference": False,
        "llm_anomaly_detection_authority": False,
        "uses_resolved_semantic_roles_only": True,
    }

    if not roles.get("date") or not rows:
        return {
            "kind": "anomaly_scan",
            "evidence_available": False,
            "reason": "Governed monthly time-series evidence unavailable.",
            "grain": "month",
            "metrics": [],
            "anomalies": [],
            "governance": base_governance,
        }

    metric_keys = []
    seen = set()
    excluded = {
        "period",
        "record_count",
        "observed_min_date",
        "observed_max_date",
    }

    for row in rows:
        for key, value in row.items():
            if key in excluded or key in seen:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if pd.isna(numeric):
                continue
            metric_keys.append(key)
            seen.add(key)

    metric_results = []
    anomalies = []

    for metric in metric_keys:
        points = []
        for row in rows:
            value = row.get(metric)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if pd.isna(numeric):
                continue
            points.append({
                "period": row.get("period"),
                "value": numeric,
            })

        # Four values are the minimum required to form two quartile halves
        # without pretending that shorter series provide robust evidence.
        if len(points) < 4:
            continue

        series = pd.Series(
            [point["value"] for point in points],
            dtype="float64",
        )
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - (1.5 * iqr)
        upper = q3 + (1.5 * iqr)

        metric_anomalies = []
        for point in points:
            value = point["value"]
            if value < lower:
                direction = "below_lower_bound"
            elif value > upper:
                direction = "above_upper_bound"
            else:
                continue

            evidence = {
                "metric": metric,
                "period": point["period"],
                "value": value,
                "direction": direction,
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "lower_bound": lower,
                "upper_bound": upper,
            }
            metric_anomalies.append(evidence)
            anomalies.append(evidence)

        metric_results.append({
            "metric": metric,
            "sample_count": len(points),
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower_bound": lower,
            "upper_bound": upper,
            "anomaly_count": len(metric_anomalies),
            "anomalies": metric_anomalies,
        })

    if not metric_results:
        return {
            "kind": "anomaly_scan",
            "evidence_available": False,
            "reason": "At least four governed monthly observations for a numeric metric are required.",
            "grain": "month",
            "period_count": len(rows),
            "metrics": [],
            "anomalies": [],
            "governance": base_governance,
        }

    return {
        "kind": "anomaly_scan",
        "evidence_available": True,
        "reason": None,
        "grain": "month",
        "period_count": len(rows),
        "metrics": metric_results,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "governance": base_governance,
    }


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
        elif op == "cancellation_analysis":
            result = _cancellation_analysis(df, task, roles)
            if not result.get("evidence_available"):
                results.append({
                    **base,
                    "execution_status": "NOT_EXECUTED",
                    "reason": result.get("reason"),
                    "result": result,
                })
                continue
        elif op == "anomaly_scan":
            result = _anomaly_scan(df, task, roles)
            if not result.get("evidence_available"):
                results.append({
                    **base,
                    "execution_status": "NOT_EXECUTED",
                    "reason": result.get("reason"),
                    "result": result,
                })
                continue
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
