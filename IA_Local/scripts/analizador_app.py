from __future__ import annotations

import argparse
import html
import hashlib
import json
import math
import os
import re
import shutil
import traceback
import sys
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(os.environ.get("IA_LOCAL_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
WORKSPACE = ROOT / "workspace"
ENTRADA = WORKSPACE / "Entrada"
REPORTES = WORKSPACE / "Reportes"
HISTORICO = WORKSPACE / "Historico"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")
MAX_SAMPLE_ROWS = 5
MAX_RESULT_ROWS_FOR_LLM = 30

for p in (ENTRADA, REPORTES, HISTORICO):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="IA Empresarial Local - Analizador", version="3.0")


def norm(text: Any) -> str:
    s = str(text or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def safe_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "archivo"
    ext = Path(name).suffix.lower()
    return stem[:100] + ext


def unique_path(base_dir: Path, filename: str) -> Path:
    p = base_dir / filename
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    for i in range(1, 10000):
        q = base_dir / f"{stem}_{i}{suffix}"
        if not q.exists():
            return q
    raise RuntimeError("No se pudo generar un nombre de archivo unico")


def read_csv_robust(path: Path) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python", low_memory=False)
        except Exception as e:
            last_err = e
    raise ValueError(f"No se pudo leer el CSV: {last_err}")


def load_tabular(path: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    ext = path.suffix.lower()
    meta: Dict[str, Any] = {"archivo": path.name, "extension": ext, "hojas": []}

    if ext in (".csv", ".txt"):
        df = read_csv_robust(path)
        meta["hojas"] = ["CSV"]
        meta["hoja_analizada"] = "CSV"
        return df, meta

    if ext not in (".xlsx", ".xlsm", ".xls", ".xlsb"):
        raise ValueError("Formato no soportado. Usa XLSX, XLS, XLSB o CSV.")

    # Calamine suele ser mucho mas rapido para libros grandes. Si no esta disponible,
    # se usa el motor tradicional correspondiente.
    engine = None
    try:
        import python_calamine  # noqa: F401
        engine = "calamine"
    except Exception:
        engine = "openpyxl" if ext in (".xlsx", ".xlsm") else ("xlrd" if ext == ".xls" else "pyxlsb")

    try:
        xls = pd.ExcelFile(path, engine=engine)
    except Exception:
        fallback = "openpyxl" if ext in (".xlsx", ".xlsm") else ("xlrd" if ext == ".xls" else "pyxlsb")
        xls = pd.ExcelFile(path, engine=fallback)
        engine = fallback
    meta["motor_excel"] = engine
    meta["hojas"] = list(xls.sheet_names)
    frames: List[Tuple[str, pd.DataFrame]] = []
    for sheet in xls.sheet_names:
        try:
            f = pd.read_excel(xls, sheet_name=sheet)
            if not f.empty or len(f.columns) > 0:
                frames.append((sheet, f))
        except Exception as e:
            meta.setdefault("errores_hojas", {})[sheet] = str(e)

    if not frames:
        raise ValueError("El libro no contiene hojas legibles con datos.")

    # Si varias hojas comparten el mismo esquema, se consolidan. Es muy comun en libros por anio/mes.
    schemas: Dict[Tuple[str, ...], List[Tuple[str, pd.DataFrame]]] = {}
    for sheet, f in frames:
        key = tuple(norm(c) for c in f.columns)
        schemas.setdefault(key, []).append((sheet, f))

    best_group = max(schemas.values(), key=lambda g: sum(len(x[1]) for x in g))
    if len(best_group) > 1:
        combined = []
        for sheet, f in best_group:
            ff = f.copy()
            ff["_HojaOrigen"] = sheet
            combined.append(ff)
        df = pd.concat(combined, ignore_index=True)
        meta["hoja_analizada"] = ", ".join(x[0] for x in best_group)
        meta["hojas_consolidadas"] = [x[0] for x in best_group]
    else:
        # Si los esquemas son diferentes, se analiza la hoja con mas filas y se deja constancia.
        sheet, df = max(frames, key=lambda x: len(x[1]))
        meta["hoja_analizada"] = sheet
        if len(frames) > 1:
            meta["advertencia_hojas"] = (
                "Las hojas tienen estructuras diferentes. Para el analisis automatico se uso la hoja con mas filas: " + sheet
            )

    return df, meta


ROLE_PATTERNS: Dict[str, List[str]] = {
    "date": ["fecha", "date", "invoice date", "transaction date", "order date", "created at"],
    "customer": ["customer id", "customer", "cliente id", "id cliente", "cliente", "client", "cust"],
    "product": ["producto", "product", "description", "descripcion", "articulo", "item", "sku", "stock code", "stockcode"],
    "quantity": ["quantity", "qty", "cantidad", "unidades", "units", "piezas"],
    "unit_price": ["unit price", "unitprice", "precio unitario", "precio venta", "price", "precio"],
    "revenue": ["venta total", "ventas", "sales", "revenue", "importe venta", "importe", "amount", "total venta", "subtotal"],
    "unit_cost": ["unit cost", "costo unitario", "precio compra", "purchase price", "cost price", "costo", "cost"],
    "total_cost": ["costo total", "total cost", "cost total", "importe costo"],
    "invoice": ["invoice no", "invoiceno", "invoice", "factura", "folio", "ticket", "order id", "pedido"],
    "country": ["country", "pais", "país"],
    "seller": ["vendedor", "seller", "salesperson", "agent", "asesor"],
}


def score_col(col_norm: str, patterns: Iterable[str]) -> int:
    best = 0
    for p in patterns:
        pn = norm(p)
        if col_norm == pn:
            best = max(best, 100)
        elif pn in col_norm:
            best = max(best, 70 + min(len(pn), 20))
        elif all(tok in col_norm.split() for tok in pn.split()):
            best = max(best, 60)
    return best


def infer_roles(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(df.columns)
    ncols = {c: norm(c) for c in cols}
    roles: Dict[str, Optional[str]] = {k: None for k in ROLE_PATTERNS}
    used: set[str] = set()

    # Primero roles muy especificos para no confundir costo total/costo unitario y venta/precio.
    order = ["total_cost", "unit_cost", "revenue", "unit_price", "date", "customer", "product", "quantity", "invoice", "country", "seller"]
    for role in order:
        candidates = []
        for c in cols:
            if c in used:
                continue
            s = score_col(ncols[c], ROLE_PATTERNS[role])
            if role == "product" and ncols[c] in {"description", "descripcion", "producto", "product"}:
                s += 5
            if s:
                candidates.append((s, c))
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            roles[role] = candidates[0][1]
            used.add(candidates[0][1])

    return roles


def numeric_series(df: pd.DataFrame, col: Optional[str]) -> Optional[pd.Series]:
    if not col or col not in df.columns:
        return None
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    # Quita simbolos monetarios y separadores comunes sin destruir decimales.
    ss = s.astype(str).str.replace(r"[^0-9,.-]", "", regex=True)
    # Si hay coma y punto, se asume coma como separador de miles. Si solo hay coma, prueba decimal.
    if ss.str.contains(r"\.", regex=True).any() and ss.str.contains(",", regex=False).any():
        ss = ss.str.replace(",", "", regex=False)
    else:
        ss = ss.str.replace(",", ".", regex=False)
    return pd.to_numeric(ss, errors="coerce")


def prepare_df(df: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    work = df.copy()
    derived: Dict[str, Any] = {}

    qty = numeric_series(work, roles.get("quantity"))
    unit_price = numeric_series(work, roles.get("unit_price"))
    revenue = numeric_series(work, roles.get("revenue"))
    unit_cost = numeric_series(work, roles.get("unit_cost"))
    total_cost = numeric_series(work, roles.get("total_cost"))

    if qty is not None:
        work["_cantidad"] = qty
        derived["cantidad"] = roles.get("quantity")

    if revenue is not None:
        work["_ventas"] = revenue
        derived["ventas"] = roles.get("revenue")
    elif qty is not None and unit_price is not None:
        work["_ventas"] = qty * unit_price
        derived["ventas"] = f"{roles.get('quantity')} * {roles.get('unit_price')}"

    if total_cost is not None:
        work["_costo"] = total_cost
        derived["costo"] = roles.get("total_cost")
    elif unit_cost is not None and qty is not None:
        work["_costo"] = unit_cost * qty
        derived["costo"] = f"{roles.get('unit_cost')} * {roles.get('quantity')}"
    elif unit_cost is not None:
        # No asumimos que un costo unitario sea total si existe cantidad ausente.
        derived["costo_no_utilizable"] = roles.get("unit_cost")

    if "_ventas" in work.columns and "_costo" in work.columns:
        work["_utilidad"] = work["_ventas"] - work["_costo"]
        derived["utilidad"] = "ventas - costo"

    date_col = roles.get("date")
    if date_col:
        work["_fecha"] = pd.to_datetime(work[date_col], errors="coerce")
        work["_mes"] = work["_fecha"].dt.to_period("M").astype(str)
        work["_anio"] = work["_fecha"].dt.year

    return work, derived


def compact_value(v: Any) -> Any:
    if pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def dataframe_records(df: pd.DataFrame, n: int = MAX_RESULT_ROWS_FOR_LLM) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.head(n).iterrows():
        out.append({str(k): compact_value(v) for k, v in row.items()})
    return out


def build_profile(work: pd.DataFrame, original: pd.DataFrame, roles: Dict[str, Optional[str]], derived: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    p: Dict[str, Any] = {
        "archivo": meta.get("archivo"),
        "hojas": meta.get("hojas", []),
        "hoja_analizada": meta.get("hoja_analizada"),
        "filas": int(len(original)),
        "columnas": [str(c) for c in original.columns],
        "roles_detectados": roles,
        "calculos_derivados": derived,
        "nulos_por_columna": {str(c): int(original[c].isna().sum()) for c in original.columns},
        "muestra": dataframe_records(original.head(MAX_SAMPLE_ROWS), MAX_SAMPLE_ROWS),
    }
    if "_fecha" in work.columns and work["_fecha"].notna().any():
        p["periodo"] = {
            "desde": work["_fecha"].min().isoformat(),
            "hasta": work["_fecha"].max().isoformat(),
        }
    if "_ventas" in work.columns:
        p["ventas_totales"] = float(work["_ventas"].sum(skipna=True))
    if "_cantidad" in work.columns:
        p["cantidad_total"] = float(work["_cantidad"].sum(skipna=True))
    if "_utilidad" in work.columns:
        v = float(work["_ventas"].sum(skipna=True))
        u = float(work["_utilidad"].sum(skipna=True))
        p["utilidad_total"] = u
        p["margen_total_pct"] = (u / v * 100.0) if v else None
    inv = roles.get("invoice")
    if inv:
        p["operaciones"] = int(work[inv].nunique(dropna=True))
    if meta.get("advertencia_hojas"):
        p["advertencia_hojas"] = meta["advertencia_hojas"]
    return p


def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.ok
    except Exception:
        return False


def ollama_chat(messages: List[Dict[str, str]], json_mode: bool = False, timeout: int = 180, num_predict: int = 320) -> str:
    payload: Dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": num_predict},
    }
    if json_mode:
        payload["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return str(data.get("message", {}).get("content", "")).strip()


def extract_top_n(prompt: str, default: int = 10) -> int:
    m = re.search(r"\b(?:top|mejores?|principales?|primeros?|ultimos?|peores?)\s+(\d{1,3})\b", norm(prompt))
    if not m:
        m = re.search(r"\b(\d{1,3})\s+(?:clientes?|productos?|paises?|meses?|vendedores?)\b", norm(prompt))
    if m:
        return max(1, min(int(m.group(1)), 100))
    return default


def heuristic_plan(prompt: str) -> Dict[str, Any]:
    n = norm(prompt)
    plan: Dict[str, Any] = {"type": "overview", "dimension": None, "metric": None, "order": "desc", "top_n": extract_top_n(prompt)}

    # Las solicitudes de analisis/reporte completo tienen prioridad sobre palabras
    # aisladas como "margen" que pueden aparecer en frases negativas como
    # "no inventes costos ni margenes".
    full_analysis_phrases = [
        "analiza completamente", "analisis completo", "analiza todo", "reporte completo",
        "reporte general", "resumen general", "analisis general", "todos los indicadores",
        "principales productos y clientes", "tendencia mensual",
    ]
    if any(x in n for x in full_analysis_phrases):
        plan["type"] = "overview"
        return plan

    # Quita clausulas negativas comunes antes de inferir la metrica solicitada.
    positive = re.sub(r"\bno\s+(?:inventes?|calcules?|uses?|estimes?)\b[^.;\n]*", " ", n)
    positive = re.sub(r"\bsin\s+(?:inventar|calcular|estimar)\b[^.;\n]*", " ", positive)

    if any(x in positive for x in ["cliente", "customer"]):
        plan["dimension"] = "customer"
    elif any(x in positive for x in ["producto", "articulo", "item"]):
        plan["dimension"] = "product"
    elif any(x in positive for x in ["pais", "country"]):
        plan["dimension"] = "country"
    elif any(x in positive for x in ["vendedor", "seller"]):
        plan["dimension"] = "seller"
    elif "mes" in positive or "mensual" in positive:
        plan["dimension"] = "month"
    elif "ano" in positive or "anual" in positive:
        plan["dimension"] = "year"

    if any(x in positive for x in ["margen", "rentabilidad", "rentable"]):
        plan["metric"] = "margin"
    elif any(x in positive for x in ["utilidad", "ganancia", "profit"]):
        plan["metric"] = "profit"
    elif any(x in positive for x in ["cantidad", "unidades", "volumen", "quantity"]):
        plan["metric"] = "quantity"
    elif any(x in positive for x in ["ticket promedio", "average ticket"]):
        plan["metric"] = "avg_ticket"
    elif any(x in positive for x in ["operaciones", "facturas", "tickets", "pedidos"]):
        plan["metric"] = "operations"
    elif any(x in positive for x in ["venta", "ingreso", "facturacion", "revenue", "sales"]):
        plan["metric"] = "sales"

    if plan["dimension"] or plan["metric"]:
        plan["type"] = "ranking" if plan["dimension"] else "metric"
    if any(x in positive for x in ["peor", "menor", "mas bajo", "baja", "caida"]):
        plan["order"] = "asc"
    return plan


def llm_plan(prompt: str, profile: Dict[str, Any], roles: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
    if not ollama_available():
        return None
    schema = {
        "columnas": profile["columnas"],
        "roles": roles,
        "calculos_derivados": profile.get("calculos_derivados"),
        "periodo": profile.get("periodo"),
    }
    system = """Eres un planificador de analisis de datos. Devuelve SOLO JSON valido, sin markdown.
No inventes columnas. El ejecutor solo acepta:
type: overview|ranking|metric
dimension: customer|product|country|seller|month|year|null
metric: sales|quantity|profit|margin|operations|avg_ticket|null
order: desc|asc
top_n: entero 1..100
filters: lista opcional de objetos {role: customer|product|country|seller, op: contains|equals, value: texto}
Si el usuario pide una metrica no disponible, aun debes indicar esa metrica; el ejecutor informara que falta el dato."""
    user = json.dumps({"solicitud": prompt, "esquema": schema}, ensure_ascii=False)
    try:
        raw = ollama_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True, timeout=120, num_predict=180)
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        return obj
    except Exception:
        return None


def apply_filters(work: pd.DataFrame, filters: Any, roles: Dict[str, Optional[str]]) -> pd.DataFrame:
    if not isinstance(filters, list):
        return work
    out = work
    for f in filters[:10]:
        if not isinstance(f, dict):
            continue
        role = str(f.get("role", ""))
        col = roles.get(role)
        if not col or col not in out.columns:
            continue
        value = str(f.get("value", "")).strip()
        if not value:
            continue
        op = str(f.get("op", "contains"))
        s = out[col].astype(str)
        if op == "equals":
            out = out[s.str.casefold() == value.casefold()]
        else:
            out = out[s.str.contains(re.escape(value), case=False, na=False)]
    return out


def dimension_col(plan_dim: Optional[str], roles: Dict[str, Optional[str]]) -> Optional[str]:
    if plan_dim in ("customer", "product", "country", "seller"):
        return roles.get(plan_dim)
    if plan_dim == "month":
        return "_mes"
    if plan_dim == "year":
        return "_anio"
    return None


def metric_requirements(metric: Optional[str], work: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[bool, str]:
    if metric == "sales" and "_ventas" not in work.columns:
        return False, "No hay una columna de ventas/importe ni una combinacion util de cantidad y precio unitario."
    if metric == "quantity" and "_cantidad" not in work.columns:
        return False, "No se detecto una columna de cantidad/unidades."
    if metric in ("profit", "margin") and "_costo" not in work.columns:
        return False, "No se detecto un costo total utilizable. Sin costo no es posible calcular utilidad ni margen real."
    if metric in ("profit", "margin") and "_ventas" not in work.columns:
        return False, "No se detectaron ventas/importe suficientes para calcular utilidad o margen."
    if metric in ("operations", "avg_ticket") and not roles.get("invoice"):
        if metric == "avg_ticket":
            return False, "No se detecto identificador de operacion/factura para calcular ticket promedio."
    if metric == "avg_ticket" and "_ventas" not in work.columns:
        return False, "No se detectaron ventas para calcular ticket promedio."
    return True, ""


def aggregate_metric(work: pd.DataFrame, dimension: str, metric: str, invoice_col: Optional[str]) -> pd.DataFrame:
    g = work.groupby(dimension, dropna=False)
    if metric == "sales":
        out = g["_ventas"].sum(min_count=1).reset_index(name="Ventas")
    elif metric == "quantity":
        out = g["_cantidad"].sum(min_count=1).reset_index(name="Cantidad")
    elif metric == "profit":
        out = g["_utilidad"].sum(min_count=1).reset_index(name="Utilidad")
    elif metric == "margin":
        tmp = g[["_ventas", "_utilidad"]].sum(min_count=1).reset_index()
        tmp["Margen_%"] = tmp.apply(lambda r: (r["_utilidad"] / r["_ventas"] * 100.0) if r["_ventas"] not in (0, None) and not pd.isna(r["_ventas"]) else math.nan, axis=1)
        out = tmp[[dimension, "_ventas", "_utilidad", "Margen_%"]].rename(columns={"_ventas": "Ventas", "_utilidad": "Utilidad"})
    elif metric == "operations":
        if invoice_col:
            out = g[invoice_col].nunique(dropna=True).reset_index(name="Operaciones")
        else:
            out = g.size().reset_index(name="Operaciones")
    elif metric == "avg_ticket":
        tmp_sales = g["_ventas"].sum(min_count=1)
        tmp_ops = g[invoice_col].nunique(dropna=True) if invoice_col else g.size()
        out = pd.DataFrame({dimension: tmp_sales.index, "Ventas": tmp_sales.values, "Operaciones": tmp_ops.values})
        out["Ticket_Promedio"] = out["Ventas"] / out["Operaciones"].replace(0, pd.NA)
    else:
        raise ValueError(f"Metrica no soportada: {metric}")
    return out


def build_overview_sections(work: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any], List[str]]:
    notes: List[str] = []
    sections: Dict[str, pd.DataFrame] = {}
    kpis: List[Tuple[str, Any]] = []

    inv = roles.get("invoice")
    cancel_mask = pd.Series(False, index=work.index)
    if "_cantidad" in work.columns:
        cancel_mask = cancel_mask | (work["_cantidad"] < 0)
    if inv:
        cancel_mask = cancel_mask | work[inv].astype(str).str.upper().str.startswith("C", na=False)

    valid_mask = ~cancel_mask
    if "_ventas" in work.columns:
        ventas_netas = float(work["_ventas"].sum(skipna=True))
        ventas_positivas = float(work.loc[work["_ventas"] > 0, "_ventas"].sum(skipna=True))
        devoluciones = float(work.loc[work["_ventas"] < 0, "_ventas"].sum(skipna=True))
        kpis += [("Ventas netas", ventas_netas), ("Ventas positivas", ventas_positivas)]
        if devoluciones:
            kpis.append(("Importe devoluciones/cancelaciones", devoluciones))
    if "_cantidad" in work.columns:
        kpis.append(("Unidades netas", float(work["_cantidad"].sum(skipna=True))))
    if inv:
        ops_total = int(work[inv].nunique(dropna=True))
        ops_validas = int(work.loc[valid_mask, inv].nunique(dropna=True))
        ops_cancel = int(work.loc[cancel_mask, inv].nunique(dropna=True)) if cancel_mask.any() else 0
        kpis += [("Operaciones totales", ops_total), ("Operaciones sin cancelacion", ops_validas)]
        if ops_cancel:
            kpis.append(("Operaciones cancelacion/devolucion", ops_cancel))
        if "_ventas" in work.columns and ops_validas:
            kpis.append(("Ticket promedio neto", float(work["_ventas"].sum(skipna=True)) / ops_validas))
    if cancel_mask.any():
        kpis.append(("Registros cancelacion/devolucion", int(cancel_mask.sum())))
        kpis.append(("Cancelacion/devolucion % filas", float(cancel_mask.mean() * 100.0)))

    if "_utilidad" in work.columns:
        ventas = float(work["_ventas"].sum(skipna=True))
        util = float(work["_utilidad"].sum(skipna=True))
        kpis += [("Utilidad", util), ("Margen %", (util / ventas * 100.0) if ventas else math.nan)]
    else:
        notes.append("No se detecto costo utilizable; utilidad y margen real no se calcularon.")

    sections["KPIs"] = pd.DataFrame(kpis, columns=["Indicador", "Valor"])

    def ranking(role: str, label: str, n: int = 20) -> Optional[pd.DataFrame]:
        col = roles.get(role)
        if not col or "_ventas" not in work.columns:
            return None
        base = work.loc[work[col].notna()].copy()
        if pd.api.types.is_object_dtype(base[col]) or pd.api.types.is_string_dtype(base[col]):
            base = base.loc[base[col].astype(str).str.strip().ne("")]
        tmp = base.groupby(col, dropna=True)["_ventas"].sum(min_count=1).reset_index(name="Ventas")
        tmp = tmp.sort_values("Ventas", ascending=False, na_position="last").head(n).reset_index(drop=True)
        return tmp.rename(columns={col: label})

    for key, role, label in [
        ("Top_Productos", "product", "Producto"),
        ("Top_Clientes", "customer", "Cliente"),
        ("Top_Paises", "country", "Pais"),
        ("Top_Vendedores", "seller", "Vendedor"),
    ]:
        df = ranking(role, label)
        if df is not None and not df.empty:
            sections[key] = df

    if "_mes" in work.columns and "_ventas" in work.columns:
        agg = {"_ventas": "sum"}
        if "_cantidad" in work.columns:
            agg["_cantidad"] = "sum"
        mensual = work.groupby("_mes", dropna=False).agg(agg).reset_index().rename(columns={"_mes": "Mes", "_ventas": "Ventas", "_cantidad": "Unidades"})
        if inv:
            ops = work.groupby("_mes", dropna=False)[inv].nunique(dropna=True).reset_index(name="Operaciones").rename(columns={"_mes": "Mes"})
            mensual = mensual.merge(ops, on="Mes", how="left")
        mensual = mensual.sort_values("Mes").reset_index(drop=True)
        if len(mensual) > 1:
            mensual["Variacion_%"] = mensual["Ventas"].pct_change() * 100.0
        sections["Tendencia_Mensual"] = mensual

    if cancel_mask.any():
        cancel_data = [
            ("Registros", int(cancel_mask.sum())),
            ("Porcentaje de filas", float(cancel_mask.mean() * 100.0)),
        ]
        if "_ventas" in work.columns:
            cancel_data.append(("Importe neto asociado", float(work.loc[cancel_mask, "_ventas"].sum(skipna=True))))
        sections["Cancelaciones"] = pd.DataFrame(cancel_data, columns=["Indicador", "Valor"])

    summary = {
        "tipo": "overview",
        "filas_analizadas": int(len(work)),
        "indicadores": {str(k): compact_value(v) for k, v in kpis},
        "secciones": list(sections.keys()),
    }
    return sections, summary, notes


def execute_plan(work: pd.DataFrame, roles: Dict[str, Optional[str]], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], pd.DataFrame, List[str], Dict[str, pd.DataFrame]]:
    notes: List[str] = []
    filtered = apply_filters(work, plan.get("filters"), roles)
    if len(filtered) != len(work):
        notes.append(f"Se aplicaron filtros: {len(filtered):,} de {len(work):,} filas quedaron para el calculo.")

    ptype = plan.get("type") or "overview"
    metric = plan.get("metric")
    dim = plan.get("dimension")
    top_n = max(1, min(int(plan.get("top_n") or 10), 100))
    order = "asc" if plan.get("order") == "asc" else "desc"

    summary: Dict[str, Any] = {"tipo": ptype, "metrica": metric, "dimension": dim, "filas_analizadas": int(len(filtered))}

    if ptype == "overview" or (not metric and not dim):
        sections, full_summary, full_notes = build_overview_sections(filtered, roles)
        notes.extend(full_notes)
        result = sections.get("KPIs", pd.DataFrame())
        return full_summary, result, notes, sections

    ok, why = metric_requirements(metric, filtered, roles)
    if not ok:
        notes.append(why)
        res = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}]); return summary, res, notes, {"Resultado": res}

    dcol = dimension_col(dim, roles)
    if dim and not dcol:
        why = f"No se detecto una columna apropiada para agrupar por {dim}."
        notes.append(why)
        res = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}]); return summary, res, notes, {"Resultado": res}
    if dcol and dcol not in filtered.columns:
        why = f"No existe la dimension necesaria: {dim}."
        notes.append(why)
        res = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}]); return summary, res, notes, {"Resultado": res}

    inv = roles.get("invoice")
    if dcol:
        result = aggregate_metric(filtered, dcol, metric, inv)
        metric_col = {
            "sales": "Ventas", "quantity": "Cantidad", "profit": "Utilidad", "margin": "Margen_%",
            "operations": "Operaciones", "avg_ticket": "Ticket_Promedio"
        }[metric]
        result = result.sort_values(metric_col, ascending=(order == "asc"), na_position="last").head(top_n).reset_index(drop=True)
        result = result.rename(columns={dcol: {"customer": "Cliente", "product": "Producto", "country": "Pais", "seller": "Vendedor", "month": "Mes", "year": "Anio"}.get(dim, str(dcol))})
    else:
        if metric == "sales":
            value = float(filtered["_ventas"].sum(skipna=True))
        elif metric == "quantity":
            value = float(filtered["_cantidad"].sum(skipna=True))
        elif metric == "profit":
            value = float(filtered["_utilidad"].sum(skipna=True))
        elif metric == "margin":
            sales = float(filtered["_ventas"].sum(skipna=True))
            profit = float(filtered["_utilidad"].sum(skipna=True))
            value = profit / sales * 100.0 if sales else math.nan
        elif metric == "operations":
            value = int(filtered[inv].nunique(dropna=True)) if inv else int(len(filtered))
        elif metric == "avg_ticket":
            ops = int(filtered[inv].nunique(dropna=True)) if inv else int(len(filtered))
            value = float(filtered["_ventas"].sum(skipna=True)) / ops if ops else math.nan
        else:
            value = math.nan
        result = pd.DataFrame([{"Metrica": metric, "Valor": value}])

    return summary, result, notes, {"Resultado": result}


def format_num(v: Any) -> str:
    if v is None or pd.isna(v):
        return "N/D"
    if isinstance(v, (int, float)):
        if abs(float(v)) >= 1000:
            return f"{float(v):,.2f}"
        return f"{float(v):.2f}"
    return str(v)


def _clean_model_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.I | re.S).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.S).strip()
    return t


def deterministic_narrative(profile: Dict[str, Any], sections: Dict[str, pd.DataFrame], notes: List[str]) -> str:
    kpis = sections.get("KPIs", pd.DataFrame())
    lines = []
    if not kpis.empty:
        for _, r in kpis.head(8).iterrows():
            lines.append(f"- {r['Indicador']}: {format_num(r['Valor'])}")
    for sec, label in [("Top_Productos", "Producto lider"), ("Top_Clientes", "Cliente lider"), ("Top_Paises", "Pais lider")]:
        df = sections.get(sec)
        if df is not None and not df.empty:
            lines.append(f"- {label}: {format_num(df.iloc[0,0])} con ventas de {format_num(df.iloc[0,1])}.")
    mensual = sections.get("Tendencia_Mensual")
    if mensual is not None and not mensual.empty and "Ventas" in mensual.columns:
        mx = mensual.loc[mensual["Ventas"].idxmax()]
        mn = mensual.loc[mensual["Ventas"].idxmin()]
        lines.append(f"- Mejor mes por ventas: {mx['Mes']} ({format_num(mx['Ventas'])}).")
        lines.append(f"- Menor mes por ventas: {mn['Mes']} ({format_num(mn['Ventas'])}).")
    if notes:
        lines.append("Limitaciones")
        lines.extend(f"- {n}" for n in notes)
    return "\n".join(lines)


def narrate(prompt: str, profile: Dict[str, Any], plan: Dict[str, Any], sections: Dict[str, pd.DataFrame], notes: List[str]) -> str:
    digest: Dict[str, Any] = {}
    for name, df in sections.items():
        digest[name] = dataframe_records(df, 8)
    payload = {
        "solicitud": prompt,
        "archivo": profile.get("archivo"),
        "filas": profile.get("filas"),
        "periodo": profile.get("periodo"),
        "resultados_calculados": digest,
        "advertencias": notes,
    }
    if ollama_available():
        system = """/no_think
Eres un analista empresarial. Usa EXCLUSIVAMENTE los resultados calculados por Python.
Devuelve SOLO JSON valido con esta forma exacta:
{"resumen":"texto breve en espanol","hallazgos":["hallazgo 1"],"limitaciones":["limitacion 1"]}
Reglas: no muestres razonamiento interno, no expliques tu proceso, no incluyas ingles, no inventes datos, costos, margenes ni causas. No repitas el plan tecnico."""
        try:
            raw = ollama_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": "/no_think\n" + json.dumps(payload, ensure_ascii=False)}],
                json_mode=True, timeout=180, num_predict=260,
            )
            raw = _clean_model_text(raw)
            obj = json.loads(raw)
            resumen = str(obj.get("resumen", "")).strip()
            hallazgos = obj.get("hallazgos") if isinstance(obj.get("hallazgos"), list) else []
            limitaciones = obj.get("limitaciones") if isinstance(obj.get("limitaciones"), list) else []
            if resumen:
                lines = [resumen]
                if hallazgos:
                    lines.append("\nHallazgos")
                    lines.extend(f"- {str(x).strip()}" for x in hallazgos[:8] if str(x).strip())
                merged_limits = [str(x).strip() for x in limitaciones if str(x).strip()]
                for n in notes:
                    if n not in merged_limits:
                        merged_limits.append(n)
                if merged_limits:
                    lines.append("\nLimitaciones")
                    lines.extend(f"- {x}" for x in merged_limits[:8])
                return "\n".join(lines)
        except Exception:
            pass
    return deterministic_narrative(profile, sections, notes)


def excel_report(path: Path, prompt: str, profile: Dict[str, Any], plan: Dict[str, Any], sections: Dict[str, pd.DataFrame], notes: List[str], narrative: str, source_preview: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        title_fmt = wb.add_format({"bold": True, "font_size": 16})
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        wrap = wb.add_format({"text_wrap": True, "valign": "top"})
        num_fmt = wb.add_format({"num_format": "#,##0.00"})

        ws = wb.add_worksheet("Resumen")
        writer.sheets["Resumen"] = ws
        ws.write("A1", "IA Empresarial Local - Reporte de Analisis", title_fmt)
        ws.write("A3", "Archivo", hdr_fmt); ws.write("B3", profile.get("archivo", ""))
        ws.write("A4", "Filas", hdr_fmt); ws.write("B4", profile.get("filas", 0))
        ws.write("A5", "Solicitud", hdr_fmt); ws.write("B5", prompt, wrap)
        ws.write("A7", "Interpretacion", hdr_fmt); ws.write("B7", narrative, wrap)
        ws.set_column("A:A", 24)
        ws.set_column("B:B", 90)
        row = 9
        if notes:
            ws.write(row, 0, "Advertencias", hdr_fmt)
            for note in notes:
                row += 1; ws.write(row, 0, "-"); ws.write(row, 1, note, wrap)

        # Cada seccion calculada se guarda en su propia hoja.
        for sheet_name, table in sections.items():
            safe_sheet = re.sub(r"[\/*?:\[\]]", "_", sheet_name)[:31] or "Resultado"
            table.to_excel(writer, sheet_name=safe_sheet, index=False)
            rs = writer.sheets[safe_sheet]
            for i, c in enumerate(table.columns):
                rs.write(0, i, c, hdr_fmt)
                width = min(max(len(str(c)) + 2, 12), 35)
                rs.set_column(i, i, width, num_fmt if pd.api.types.is_numeric_dtype(table[c]) else None)
            if 1 < len(table) <= 30 and len(table.columns) >= 2:
                numeric_cols = [i for i, c in enumerate(table.columns) if pd.api.types.is_numeric_dtype(table[c])]
                if numeric_cols:
                    val_idx = numeric_cols[-1]
                    chart = wb.add_chart({"type": "column"})
                    chart.add_series({"name": str(table.columns[val_idx]), "categories": [safe_sheet, 1, 0, len(table), 0], "values": [safe_sheet, 1, val_idx, len(table), val_idx]})
                    chart.set_title({"name": safe_sheet.replace("_", " ")})
                    rs.insert_chart("H2", chart, {"x_scale": 1.3, "y_scale": 1.2})

        roles_df = pd.DataFrame([{"Rol": k, "Columna detectada": v or ""} for k, v in profile.get("roles_detectados", {}).items()])
        roles_df.to_excel(writer, sheet_name="Mapa_Columnas", index=False)
        pd.DataFrame([{"Campo": "Plan", "Valor": json.dumps(plan, ensure_ascii=False)}, {"Campo": "Calculos derivados", "Valor": json.dumps(profile.get("calculos_derivados", {}), ensure_ascii=False)}]).to_excel(writer, sheet_name="Trazabilidad", index=False)

        # Solo una muestra para evitar duplicar libros enormes dentro del reporte.
        source_preview.head(1000).to_excel(writer, sheet_name="Muestra_Datos", index=False)



def pdf_report(path: Path, prompt: str, profile: Dict[str, Any], sections: Dict[str, pd.DataFrame], notes: List[str], narrative: str) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenterTitle2", parent=styles["Title"], alignment=TA_CENTER, fontSize=18, leading=22))
    story = [Paragraph("IA Empresarial Local - Reporte de Analisis", styles["CenterTitle2"]), Spacer(1, 0.35*cm)]
    story.append(Paragraph(f"<b>Archivo:</b> {html.escape(str(profile.get('archivo','')))}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Filas analizadas:</b> {profile.get('filas',0):,}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Solicitud:</b> {html.escape(prompt)}", styles["BodyText"]))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph("Resumen ejecutivo", styles["Heading2"]))
    for para in [x.strip() for x in narrative.split("\n") if x.strip()]:
        story.append(Paragraph(html.escape(para), styles["BodyText"]))
    if notes:
        story.append(Spacer(1, 0.2*cm)); story.append(Paragraph("Advertencias", styles["Heading2"]))
        for note in notes:
            story.append(Paragraph("• " + html.escape(note), styles["BodyText"]))

    for section_name, result in sections.items():
        story.append(Spacer(1, 0.3*cm)); story.append(Paragraph(html.escape(section_name.replace("_", " ")), styles["Heading2"]))
        if result.empty:
            story.append(Paragraph("Sin resultados tabulares.", styles["BodyText"]))
            continue
        show = result.head(20).copy()
        data = [[Paragraph(f"<b>{html.escape(str(c))}</b>", styles["BodyText"]) for c in show.columns]]
        for _, row in show.iterrows():
            data.append([Paragraph(html.escape(format_num(v)), styles["BodyText"]) for v in row])
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9EAF7")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
        ]))
        story.append(tbl)
    doc.build(story)


def analyze_file(path: Path, prompt: str) -> Dict[str, Any]:
    started = time.time()
    original, meta = load_tabular(path)
    original.columns = [str(c).strip() for c in original.columns]
    roles = infer_roles(original)
    work, derived = prepare_df(original, roles)
    profile = build_profile(work, original, roles, derived, meta)

    # Para consultas empresariales comunes usamos un plan determinista y evitamos
    # gastar tiempo de CPU pidiendo al LLM que decida algo que ya puede inferirse.
    hplan = heuristic_plan(prompt)
    prompt_n = norm(prompt)
    overview_words = ("analiza", "resumen", "reporte", "indicadores", "metricas", "completamente", "general")
    recognized = bool(hplan.get("dimension") or hplan.get("metric") or any(w in prompt_n for w in overview_words))
    plan = hplan if recognized else (llm_plan(prompt, profile, roles) or hplan)
    # Completa/valida campos que el modelo pudo omitir.
    allowed_types = {"overview", "ranking", "metric"}
    allowed_dims = {None, "customer", "product", "country", "seller", "month", "year"}
    allowed_metrics = {None, "sales", "quantity", "profit", "margin", "operations", "avg_ticket"}
    if plan.get("type") not in allowed_types: plan["type"] = hplan["type"]
    if plan.get("dimension") not in allowed_dims: plan["dimension"] = hplan["dimension"]
    if plan.get("metric") not in allowed_metrics: plan["metric"] = hplan["metric"]
    if not plan.get("dimension") and hplan.get("dimension"): plan["dimension"] = hplan["dimension"]
    if not plan.get("metric") and hplan.get("metric"): plan["metric"] = hplan["metric"]
    if not plan.get("top_n"): plan["top_n"] = hplan["top_n"]
    if plan.get("order") not in ("asc", "desc"): plan["order"] = hplan["order"]
    if (plan.get("dimension") or plan.get("metric")) and plan.get("type") == "overview":
        plan["type"] = "ranking" if plan.get("dimension") else "metric"

    summary, result, notes, sections = execute_plan(work, roles, plan)
    if meta.get("advertencia_hojas"):
        notes.append(meta["advertencia_hojas"])
    narrative = narrate(prompt, profile, plan, sections, notes)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)[:60]
    xlsx_path = REPORTES / f"Reporte_{base}_{stamp}.xlsx"
    pdf_path = REPORTES / f"Reporte_{base}_{stamp}.pdf"
    excel_report(xlsx_path, prompt, profile, plan, sections, notes, narrative, original)
    pdf_report(pdf_path, prompt, profile, sections, notes, narrative)

    return {
        "ok": True,
        "archivo": path.name,
        "filas": int(len(original)),
        "columnas": [str(c) for c in original.columns],
        "roles": roles,
        "plan": plan,
        "resultado": dataframe_records(result, 100),
        "secciones": {k: dataframe_records(v, 30) for k, v in sections.items()},
        "advertencias": notes,
        "narrativa": narrative,
        "excel": xlsx_path.name,
        "pdf": pdf_path.name,
        "segundos": round(time.time() - started, 2),
    }


INDEX_HTML = r"""
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>IA Empresarial Local - Analizador</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f5f7fb;color:#172033}.wrap{max-width:1100px;margin:38px auto;padding:0 20px}
.card{background:white;border:1px solid #dbe2ea;border-radius:16px;padding:26px;box-shadow:0 8px 30px rgba(30,50,80,.07)}
h1{margin:0 0 8px;font-size:28px}.sub{color:#5d6b80;margin-bottom:22px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
label{font-weight:600;display:block;margin:8px 0}.full{grid-column:1/-1}input[type=file],textarea{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:10px;padding:12px;background:#fff}
textarea{min-height:120px;resize:vertical}.btn{background:#2563eb;color:white;border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer}.btn:disabled{opacity:.6}
.links a{display:inline-block;margin-right:10px;margin-top:10px;color:#1d4ed8}.result{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;border-radius:12px;padding:18px;min-height:90px;margin-top:20px;overflow:auto}
.note{background:#fff7ed;border:1px solid #fed7aa;padding:12px;border-radius:10px;margin-top:14px}.ok{background:#ecfdf5;border-color:#a7f3d0}.toplinks{float:right;font-size:14px}.toplinks a{margin-left:12px}
@media(max-width:760px){.grid{grid-template-columns:1fr}.full{grid-column:1}.toplinks{float:none;display:block;margin-top:10px}}
</style></head><body><div class="wrap"><div class="card">
<div class="toplinks"><a href="http://127.0.0.1:8080" target="_blank">Chat Open WebUI</a></div>
<h1>Analizador Empresarial de Excel / CSV</h1><div style="font-size:11px;color:#64748b;margin-bottom:8px">R10.13C.2 V9 · Verified Prompt Transport</div><div class="sub">Procesa archivos grandes con Python/Pandas y usa Qwen local solo para interpretar los resultados. Los datos no se envian a Internet.</div>
<div class="note"><b>Importante:</b> para Excel grandes usa esta pantalla en lugar de adjuntarlos directamente al chat de Open WebUI. Aqui el archivo se calcula con Python y el modelo recibe solo resultados resumidos.</div>
<form id="f" autocomplete="off"><div class="grid"><div class="full"><label>Archivo</label><input id="file" name="file" type="file" accept=".xlsx,.xls,.xlsb,.xlsm,.csv,.txt" required></div>
<div class="full"><label>Que quieres analizar</label><textarea id="prompt" name="prompt" required autocomplete="off" spellcheck="false" placeholder="Escribe o pega aquí la solicitud exacta para este análisis."></textarea></div>
<div class="full"><button class="btn" id="go">Analizar y generar Excel/PDF</button></div></div></form>
<div id="status"></div><div id="out" class="result" style="display:none"></div><div id="links" class="links"></div>
</div></div><script>
const f=document.getElementById('f'),go=document.getElementById('go'),out=document.getElementById('out'),status=document.getElementById('status'),links=document.getElementById('links');
// r10c2PromptFreshGuard
window.addEventListener('pageshow',()=>{const p=document.getElementById('prompt');if(p){p.value='';p.setAttribute('autocomplete','off');}});
f.addEventListener('submit',async(e)=>{e.preventDefault();go.disabled=true;out.style.display='block';out.textContent='Procesando archivo... En Excel grandes puede tardar varios minutos.';links.innerHTML='';status.innerHTML='';
const promptEl=document.getElementById('prompt');
const requestPrompt=(promptEl.value||'').trim();
if(!requestPrompt){throw new Error('Escribe o pega el prompt que quieres analizar.');}

// Canonicaliza los saltos de línea antes de calcular SHA-256.
const canonicalPrompt=requestPrompt
  .replace(/\r\n/g,'\n')
  .replace(/\r/g,'\n');

const enc=new TextEncoder().encode(canonicalPrompt);
const digest=await crypto.subtle.digest('SHA-256',enc);
const promptHash=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('');
const requestId=(crypto.randomUUID?crypto.randomUUID():('req-'+Date.now()+'-'+Math.random().toString(16).slice(2)));
const fd=new FormData();
fd.append('file',document.getElementById('file').files[0]);
fd.append('prompt',requestPrompt);
fd.append('prompt_sha256',promptHash);
fd.append('request_id',requestId);
try{const r=await fetch('/api/analyze',{method:'POST',body:fd});const d=await r.json();if(!r.ok||!d.ok){const detail=d.detail;let msg=d.error||'Error';if(Array.isArray(detail)){msg=detail.map(x=>((x.loc||[]).join('.')+': '+(x.msg||JSON.stringify(x)))).join(' | ');}else if(detail){msg=(typeof detail==='string'?detail:JSON.stringify(detail));}throw new Error(msg);}
out.textContent=d.narrativa;
const details=document.createElement('details');details.style.marginTop='12px';const sm=document.createElement('summary');sm.textContent='Ver detalles tecnicos';details.appendChild(sm);const pre=document.createElement('pre');pre.textContent='Plan: '+JSON.stringify(d.plan,null,2)+'\n\nSecciones: '+JSON.stringify(Object.keys(d.secciones||{}),null,2);details.appendChild(pre);out.appendChild(details);
status.innerHTML='<div class="note ok">Listo: '+d.filas.toLocaleString()+' filas procesadas en '+d.segundos+' s.</div>';
links.innerHTML='<a href="/download/'+encodeURIComponent(d.excel)+'">Descargar Excel</a><a href="/download/'+encodeURIComponent(d.pdf)+'">Descargar PDF</a>';
}catch(err){out.textContent='ERROR: '+err.message;status.innerHTML='<div class="note">Revisa C:\\IA_Local\\logs\\analizador.err.log si el problema continua.</div>';}finally{go.disabled=false;}});
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(
        INDEX_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-IA-Prompt-Transport": "r10.13c.2-v9",
        },
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "ollama": ollama_available(), "modelo": OLLAMA_MODEL, "entrada": str(ENTRADA), "reportes": str(REPORTES)}


@app.post("/api/analyze")
async def api_analyze(file: UploadFile = File(...), prompt: str = Form(...), prompt_sha256: Optional[str] = Form(None), request_id: Optional[str] = Form(None)):
    try:
        filename = safe_name(file.filename or "archivo.xlsx")
        ext = Path(filename).suffix.lower()
        if ext not in {".xlsx", ".xls", ".xlsb", ".xlsm", ".csv", ".txt"}:
            raise HTTPException(status_code=400, detail="Formato no soportado. Usa XLSX, XLS, XLSB o CSV.")
        dest = unique_path(ENTRADA, filename)
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024*1024)
        request_prompt = str(prompt or "").strip()

        # Canonicaliza saltos de línea para verificar la integridad del prompt
        # independientemente de CRLF/LF del navegador o del sistema operativo.
        canonical_prompt = request_prompt.replace("\r\n", "\n").replace("\r", "\n")

        if not request_prompt:
            raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")

        actual_hash = hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest()
        supplied_hash = str(prompt_sha256 or "").strip().lower()
        if supplied_hash and supplied_hash != actual_hash:
            raise HTTPException(status_code=409, detail="PROMPT_INTEGRITY_MISMATCH: el prompt recibido no coincide con su SHA-256.")
        rid = str(request_id or "").strip() or f"server-{uuid.uuid4()}"
        transport_mode = "client-verified" if supplied_hash and request_id else "server-fallback"
        result = analyze_file(dest, request_prompt)
        if isinstance(result, dict):
            result["request_id"] = rid
            result["request_prompt_sha256"] = actual_hash
            result["request_prompt_preview"] = " ".join(request_prompt.split())[:240]
            result["prompt_integrity"] = "r10.13c.2-verified-transport"
            result["prompt_transport_mode"] = transport_mode
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        stage = getattr(e, "stage", "analyze_file")
        code = getattr(e, "code", "INTERNAL_ANALYZER_ERROR")
        details = getattr(e, "details", None)
        payload = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "code": code,
            "stage": stage,
            "details": details,
        }
        try:
            log_dir = ROOT / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "analizador.err.log").open("a", encoding="utf-8") as fh:
                fh.write("\n=== ANALYZER ERROR ===\n")
                fh.write(f"stage={stage} code={code} file={getattr(file, 'filename', '')}\n")
                fh.write(traceback.format_exc())
                fh.write("\n")
        except Exception:
            pass
        status = 422 if code in {"SOURCE_SHEET_NOT_FOUND","DECLARED_COLUMNS_MISSING","SOURCE_SHEET_UNREADABLE","DATA_CONTRACT_ERROR"} else 500
        return JSONResponse(payload, status_code=status)


@app.get("/download/{filename}")
def download(filename: str):
    name = Path(filename).name
    path = REPORTES / name
    if not path.exists() or path.parent.resolve() != REPORTES.resolve():
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(path, filename=name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
