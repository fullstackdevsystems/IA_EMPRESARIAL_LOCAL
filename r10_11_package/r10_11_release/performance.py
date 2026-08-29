from __future__ import annotations

import importlib.util
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import pandas as pd

DEFAULT_CHUNK_ROWS = 100_000
DEFAULT_LARGE_MB = 64
PROFILE_ROWS = 5_000


def optional_engines() -> Dict[str, bool]:
    return {
        "pandas": True,
        "polars": importlib.util.find_spec("polars") is not None,
        "duckdb": importlib.util.find_spec("duckdb") is not None,
        "calamine": importlib.util.find_spec("python_calamine") is not None,
    }


def file_size_mb(path: str | Path) -> float:
    p = Path(path)
    return round(p.stat().st_size / (1024 * 1024), 3)


def execution_plan(path: str | Path, *, chunk_rows: int = DEFAULT_CHUNK_ROWS, large_mb: int = DEFAULT_LARGE_MB) -> Dict[str, Any]:
    p = Path(path)
    ext = p.suffix.lower()
    size = file_size_mb(p)
    engines = optional_engines()
    large = size >= float(large_mb)
    if ext == ".csv" and large:
        engine = "duckdb" if engines["duckdb"] else "polars" if engines["polars"] else "pandas-chunked"
        mode = "streaming-exact"
    elif ext == ".csv":
        engine = "pandas"
        mode = "in-memory"
    elif ext in {".xlsx", ".xls", ".xlsm"}:
        engine = "calamine/pandas" if engines["calamine"] else "pandas/openpyxl"
        mode = "excel-compatible"
    else:
        engine = "pandas"
        mode = "compatible"
    return {
        "file": p.name,
        "extension": ext,
        "size_mb": size,
        "large": large,
        "mode": mode,
        "engine": engine,
        "chunk_rows": max(10_000, int(chunk_rows)),
        "profile_rows": PROFILE_ROWS,
        "engines_available": engines,
        "metrics_exact": True,
        "profiling_may_sample": True,
    }


def profile_source(path: str | Path, *, rows: int = PROFILE_ROWS) -> Dict[str, Any]:
    p = Path(path)
    started = time.perf_counter()
    if p.suffix.lower() == ".csv":
        frame = pd.read_csv(p, nrows=max(100, int(rows)), low_memory=False)
        sheet = "CSV"
    else:
        try:
            frame = pd.read_excel(p, nrows=max(100, int(rows)), engine="calamine")
        except Exception:
            frame = pd.read_excel(p, nrows=max(100, int(rows)))
        sheet = "FIRST_SHEET"
    return {
        "rows_sampled": int(len(frame)),
        "columns": [str(c) for c in frame.columns],
        "sheet": sheet,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "sample_only": True,
    }


def _norm(value: Any) -> str:
    import re, unicodedata
    text = str(value or "").strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _metric_series(frame: pd.DataFrame, roles: Dict[str, Any], metric: str) -> Optional[pd.Series]:
    if metric == "quantity" and roles.get("quantity") in frame.columns:
        return _numeric(frame[roles["quantity"]])
    if metric == "cost" and roles.get("cost") in frame.columns:
        cost = _numeric(frame[roles["cost"]])
        if roles.get("quantity") in frame.columns and "unit" in _norm(roles.get("cost")):
            cost = cost * _numeric(frame[roles["quantity"]])
        return cost
    if metric == "sales":
        if roles.get("sales") in frame.columns:
            return _numeric(frame[roles["sales"]])
        if roles.get("quantity") in frame.columns and roles.get("price") in frame.columns:
            return _numeric(frame[roles["quantity"]]) * _numeric(frame[roles["price"]])
    if metric in frame.columns:
        return _numeric(frame[metric])
    return None


def _apply_safe_filters(frame: pd.DataFrame, roles: Dict[str, Any], plan: Dict[str, Any]) -> pd.DataFrame:
    work = frame
    year = plan.get("year")
    date_col = roles.get("date")
    if year and date_col in work.columns:
        dates = pd.to_datetime(work[date_col], errors="coerce")
        work = work.loc[dates.dt.year == int(year)]
    for item in plan.get("filters") or []:
        role = item.get("role")
        value = str(item.get("value", "")).strip()
        column = roles.get(role) or (role if role in work.columns else None)
        if not column or column not in work.columns or not value:
            continue
        mask = work[column].astype(str).str.contains(value, case=False, regex=False, na=False)
        work = work.loc[mask]
    return work


def can_stream_exact(dataset: Dict[str, Any], plan: Dict[str, Any], *, analytics=None, precedence=None, principal=None, large_mb: int = DEFAULT_LARGE_MB) -> Tuple[bool, str]:
    path = Path(dataset.get("path", ""))
    if path.suffix.lower() != ".csv":
        return False, "only_csv"
    if not path.exists() or file_size_mb(path) < float(large_mb):
        return False, "below_threshold"
    if plan.get("metric") == "profit":
        return False, "profit_requires_governed_rule_or_full_frame"
    # Analytic row filters/metric rules must preserve exactly the existing evaluator.
    if analytics is not None and principal is not None:
        try:
            context = analytics.build_context(principal, dataset.get("roles") or {})
            if context and (context.get("bindings") or context.get("rules")):
                return False, "validated_analytic_rules_present"
        except Exception:
            return False, "analytic_context_unknown"
    return True, "ok"


def execute_csv_chunked_exact(dataset: Dict[str, Any], plan: Dict[str, Any], *, chunk_rows: int = DEFAULT_CHUNK_ROWS) -> Dict[str, Any]:
    path = Path(dataset["path"])
    roles = dict(dataset.get("roles") or {})
    group_role = plan.get("group_by")
    group_col = roles.get(group_role) or (group_role if group_role in dataset.get("columns", []) else None)
    op = str(plan.get("operation") or "sum")
    metric = str(plan.get("metric") or "sales")
    started = time.perf_counter()
    rows_read = rows_used = 0
    chunk_count = 0
    total = 0.0
    valid_count = 0
    grouped: Dict[str, float] = {}
    grouped_count: Dict[str, int] = {}

    for chunk in pd.read_csv(path, chunksize=max(10_000, int(chunk_rows)), low_memory=False):
        chunk_count += 1
        rows_read += len(chunk)
        work = _apply_safe_filters(chunk, roles, plan)
        rows_used += len(work)
        if op == "count" and metric not in {"sales", "quantity", "cost"}:
            if group_col and group_col in work.columns:
                counts = work.groupby(group_col, dropna=False).size()
                for key, val in counts.items():
                    skey = str(key)
                    grouped_count[skey] = grouped_count.get(skey, 0) + int(val)
            else:
                valid_count += int(len(work))
            continue
        series = _metric_series(work, roles, metric)
        if series is None:
            raise ValueError(f"No existe una columna/rol calculable para la metrica {metric}")
        valid = series.notna()
        if group_col and group_col in work.columns:
            temp = pd.DataFrame({"g": work.loc[valid, group_col].astype(str), "v": series.loc[valid]})
            sums = temp.groupby("g", dropna=False)["v"].sum()
            counts = temp.groupby("g", dropna=False)["v"].count()
            for key, val in sums.items():
                grouped[key] = grouped.get(key, 0.0) + float(val)
            for key, val in counts.items():
                grouped_count[key] = grouped_count.get(key, 0) + int(val)
        else:
            total += float(series.sum(skipna=True))
            valid_count += int(valid.sum())

    if group_col:
        keys = set(grouped) | set(grouped_count)
        if op == "mean":
            items = [(k, grouped.get(k, 0.0) / grouped_count[k]) for k in keys if grouped_count.get(k, 0)]
        elif op == "count":
            items = [(k, float(grouped_count.get(k, 0))) for k in keys]
        else:
            items = [(k, grouped.get(k, 0.0)) for k in keys]
        items.sort(key=lambda kv: kv[1], reverse=True)
        limit = 20 if op == "top" else 200
        value: Any = [{"group": k, "value": round(v, 6)} for k, v in items[:limit]]
    else:
        if op == "mean":
            value = total / valid_count if valid_count else None
        elif op == "count":
            value = valid_count
        else:
            value = total
        if isinstance(value, float):
            value = round(value, 6)

    return {
        "answer_type": "structured_calculation",
        "value": value,
        "plan": plan,
        "source": {
            "type": "dataset",
            "file": dataset.get("name") or path.name,
            "sheet": "CSV",
            "rows_read": rows_read,
            "rows_used": rows_used,
            "chunks": chunk_count,
            "calculation": "python/pandas-chunked",
            "exact": True,
            "sampled_for_metric": False,
        },
        "performance": {
            "engine": "pandas-chunked",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "chunk_rows": max(10_000, int(chunk_rows)),
            "peak_frame_scope": "single_chunk",
        },
    }


def try_execute_large_query(dataset: Dict[str, Any], plan: Dict[str, Any], *, principal=None, prompt: str = "", analytics=None, precedence=None, large_mb: int = DEFAULT_LARGE_MB) -> Optional[Dict[str, Any]]:
    ok, reason = can_stream_exact(dataset, plan, analytics=analytics, precedence=precedence, principal=principal, large_mb=large_mb)
    if not ok:
        return None
    result = execute_csv_chunked_exact(dataset, plan)
    result.setdefault("performance", {})["eligibility"] = reason
    return result
