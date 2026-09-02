from __future__ import annotations
import calendar
from datetime import date

from typing import Any, Dict, List, Optional

INSIGHT_VERSION = "r10.14c"


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _period_completeness(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(rows) < 3:
        return {
            "status": "UNKNOWN",
            "reason": "Insufficient history to assess period completeness.",
            "calendar_status": "UNKNOWN",
            "volume_status": "UNKNOWN",
        }

    latest_row = rows[-1]
    latest_period = str(latest_row.get("period") or "")
    latest_max_date = latest_row.get("observed_max_date")
    latest_min_date = latest_row.get("observed_min_date")

    calendar_status = "UNKNOWN"
    expected_period_end = None
    calendar_reason = None

    try:
        year_s, month_s = latest_period.split("-", 1)
        year = int(year_s)
        month = int(month_s)
        last_day = calendar.monthrange(year, month)[1]
        expected_period_end = date(year, month, last_day).isoformat()

        if latest_max_date:
            if str(latest_max_date) < expected_period_end:
                calendar_status = "PARTIAL"
                calendar_reason = (
                    "Latest observed date does not reach the calendar end of the period."
                )
            else:
                calendar_status = "COMPLETE"
        else:
            calendar_reason = "Observed maximum date is unavailable."
    except Exception:
        calendar_reason = "Unable to resolve calendar end for latest period."

    counts = [
        int(r.get("record_count") or 0)
        for r in rows[:-1]
        if int(r.get("record_count") or 0) > 0
    ]
    latest = int(latest_row.get("record_count") or 0)

    volume_status = "UNKNOWN"
    volume_reason = None
    baseline = None
    ratio = None

    if len(counts) >= 2 and latest > 0:
        baseline_window = counts[-6:]
        baseline = sum(baseline_window) / len(baseline_window)

        if baseline > 0:
            ratio = latest / baseline
            if ratio < 0.8:
                volume_status = "PARTIAL"
                volume_reason = (
                    "Latest period record count is below 80% of the recent-period baseline."
                )
            else:
                volume_status = "COMPARABLE"
        else:
            volume_reason = "Invalid record-count baseline."
    else:
        volume_reason = "Insufficient record-count evidence."

    if calendar_status == "PARTIAL" or volume_status == "PARTIAL":
        reasons = [r for r in (calendar_reason, volume_reason) if r]
        return {
            "status": "PARTIAL",
            "calendar_status": calendar_status,
            "volume_status": volume_status,
            "observed_min_date": latest_min_date,
            "observed_max_date": latest_max_date,
            "expected_period_end": expected_period_end,
            "latest_record_count": latest,
            "baseline_record_count": round(baseline, 4) if baseline is not None else None,
            "ratio": round(ratio, 4) if ratio is not None else None,
            "reason": " ".join(reasons) or "Latest period is not comparable.",
        }

    if calendar_status == "COMPLETE" and volume_status == "COMPARABLE":
        return {
            "status": "COMPARABLE",
            "calendar_status": calendar_status,
            "volume_status": volume_status,
            "observed_min_date": latest_min_date,
            "observed_max_date": latest_max_date,
            "expected_period_end": expected_period_end,
            "latest_record_count": latest,
            "baseline_record_count": round(baseline, 4) if baseline is not None else None,
            "ratio": round(ratio, 4) if ratio is not None else None,
            "reason": None,
        }

    return {
        "status": "UNKNOWN",
        "calendar_status": calendar_status,
        "volume_status": volume_status,
        "observed_min_date": latest_min_date,
        "observed_max_date": latest_max_date,
        "expected_period_end": expected_period_end,
        "latest_record_count": latest,
        "baseline_record_count": round(baseline, 4) if baseline is not None else None,
        "ratio": round(ratio, 4) if ratio is not None else None,
        "reason": calendar_reason or volume_reason or "Period completeness is unknown.",
    }

def _trend_insights(item: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    result = dict(item.get("result") or {})
    rows = list(result.get("rows") or [])
    if len(rows) < 2:
        return [], []

    completeness = _period_completeness(rows)
    if completeness.get("status") == "PARTIAL":
        cur = rows[-1]
        prev = rows[-2]
        return [], [{
            "id": f"observation:{item.get('analysis')}:partial_period",
            "observation_type": "partial_period_comparison",
            "analysis": item.get("analysis"),
            "current_period": cur.get("period"),
            "previous_period": prev.get("period"),
            "comparison_status": "NOT_COMPARABLE",
            "reason": completeness.get("reason"),
            "period_completeness": completeness,
            "evidence_source": item.get("task_id"),
            "confidence": 1.0,
            "provenance": {
                "source": "r10.14c2_calendar_completeness_guard",
                "execution_status": item.get("execution_status"),
            },
        }]

    metric_keys: List[str] = []
    seen = set()
    for row in rows:
        for key, value in row.items():
            if key in {"period", "record_count"}:
                continue
            if key not in seen and _num(value) is not None:
                metric_keys.append(key)
                seen.add(key)

    out: List[Dict[str, Any]] = []
    prev = rows[-2]
    cur = rows[-1]

    for metric in metric_keys:
        previous = _num(prev.get(metric))
        current = _num(cur.get(metric))
        if previous is None or current is None or previous == 0:
            continue

        change_pct = ((current - previous) / abs(previous)) * 100.0
        if abs(change_pct) < 0.01:
            continue

        insight_type = "growth" if change_pct > 0 else "decline"

        out.append({
            "id": f"insight:{item.get('analysis')}:{metric}:{insight_type}",
            "insight_type": insight_type,
            "metric": metric,
            "current_period": cur.get("period"),
            "previous_period": prev.get("period"),
            "current_value": current,
            "previous_value": previous,
            "change_pct": round(change_pct, 4),
            "direction": "increase" if change_pct > 0 else "decrease",
            "severity": None,
            "evidence_source": item.get("task_id"),
            "confidence": 1.0,
            "period_completeness": completeness,
            "provenance": {
                "source": "r10.14c4_policy_boundary_guard",
                "execution_status": item.get("execution_status"),
                "interpretation_policy": "NOT_APPLIED",
            },
        })

    return out, []


def _grouped_concentration_insights(
    item: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    result = dict(item.get("result") or {})
    rows = list(result.get("rows") or [])
    dims = list(result.get("dimensions") or [])

    if not rows or not dims:
        return [], []

    if bool(result.get("is_truncated")):
        return [], [{
            "id": f"observation:{item.get('analysis')}:concentration_truncated",
            "observation_type": "concentration_not_assessed",
            "analysis": item.get("analysis"),
            "reason": "Grouped result is truncated; concentration is not promoted from an incomplete population.",
            "evidence_source": item.get("task_id"),
            "returned_group_count": result.get("returned_group_count"),
            "total_group_count": result.get("total_group_count"),
            "row_limit": result.get("row_limit"),
            "confidence": 1.0,
            "provenance": {
                "source": "r10.14c3_safe_concentration_guard",
                "execution_status": item.get("execution_status"),
            },
        }]

    numeric_keys = []
    seen = set()
    for row in rows:
        for key, value in row.items():
            if key in dims or key == "record_count":
                continue
            if key not in seen and _num(value) is not None:
                numeric_keys.append(key)
                seen.add(key)

    out = []
    for metric in numeric_keys:
        vals = [(row, _num(row.get(metric))) for row in rows]
        vals = [(row, value) for row, value in vals if value is not None]
        total = sum(value for _, value in vals)
        if not vals or total <= 0:
            continue

        top_row, top_value = max(vals, key=lambda x: x[1])
        share = (top_value / total) * 100.0

        entity = {d: top_row.get(d) for d in dims}
        out.append({
            "id": f"insight:{item.get('analysis')}:{metric}:concentration",
            "insight_type": "concentration",
            "metric": metric,
            "entity": entity,
            "entity_value": top_value,
            "total_value": total,
            "share_pct": round(share, 4),
            "severity": None,
            "evidence_source": item.get("task_id"),
            "confidence": 1.0,
            "provenance": {
                "source": "r10.14c4_policy_boundary_guard",
                "execution_status": item.get("execution_status"),
                "population_complete": True,
                "interpretation_policy": "NOT_APPLIED",
            },
        })

    return out, []

def _blocked_observation(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"observation:{item.get('analysis')}:blocked",
        "observation_type": "blocked_analysis",
        "analysis": item.get("analysis"),
        "reason": item.get("reason"),
        "evidence_source": item.get("task_id"),
        "confidence": 1.0,
        "provenance": {
            "source": "r10.14c_governance_observation",
            "execution_status": item.get("execution_status"),
        },
    }


def build_governed_business_insights(*, analytical_results: Dict[str, Any]) -> Dict[str, Any]:
    """Create deterministic, auditable business insights from executed results only."""
    insights: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []

    for item in list((analytical_results or {}).get("results") or []):
        status = str(item.get("execution_status") or "").upper()

        if status != "EXECUTED":
            if status == "NOT_EXECUTED":
                observations.append(_blocked_observation(item))
            continue

        result = dict(item.get("result") or {})
        kind = str(result.get("kind") or "")

        if kind == "time_trend":
            trend_insights, trend_observations = _trend_insights(item)
            insights.extend(trend_insights)
            observations.extend(trend_observations)
        elif kind == "grouped_analysis":
            grouped_insights, grouped_observations = _grouped_concentration_insights(item)
            insights.extend(grouped_insights)
            observations.extend(grouped_observations)

    return {
        "schema_version": INSIGHT_VERSION,
        "mode": "deterministic-evidence-only",
        "insight_count": len(insights),
        "observation_count": len(observations),
        "insights": insights,
        "observations": observations,
        "governance": {
            "llm_numeric_inference": False,
            "uses_executed_results_only": True,
            "not_executed_results_are_never_promoted": True,
            "confidence_for_deterministic_claims": 1.0,
            "partial_periods_are_not_promoted": True,
            "calendar_period_completeness_guard": True,
            "truncated_grouped_results_are_not_used_for_concentration": True,
            "business_severity_thresholds_are_not_hardcoded": True,
            "concentration_thresholds_are_not_hardcoded": True,
            "enterprise_interpretation_deferred_to_business_rule_engine": True,
        },
    }
