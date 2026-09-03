from __future__ import annotations
try:
    from enterprise_ai.traceability import build_file_trace
except Exception:
    build_file_trace = None


"""Capa universal V4 sobre el analizador V3.

Objetivo: aceptar libros tabulares con nombres de columnas y estructuras distintas,
detectar encabezados/hojas/tipos de datos, conservar el analisis especializado de
ventas cuando aplica y ofrecer analisis generico para cualquier tabla.
"""

import json
import math
import os
import re

import hashlib
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

import analizador_app as base
import reportes_profesionales as pro
import bi_productivo as bi
import dashboard_planner as dp
import dashboard_dynamic as dd
from data_contract import validate_workbook_contract, DataContractError
from enterprise_deliverable_manifest import build_governed_deliverable_manifest


# ---------------------------------------------------------------------------
# Normalizacion y utilidades
# ---------------------------------------------------------------------------

def norm(text: Any) -> str:
    s = str(text or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _dedupe_columns(columns: Iterable[Any]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for i, raw in enumerate(columns, start=1):
        name = str(raw).strip() if raw is not None else ""
        if not name or name.lower().startswith("unnamed:") or name.lower() == "nan":
            name = f"Columna_{i}"
        base_name = name
        key = norm(base_name) or f"columna {i}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            name = f"{base_name}_{seen[key]}"
        out.append(name)
    return out


def _nonempty(v: Any) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass
    return str(v).strip() != ""


def detect_header_row(sample: pd.DataFrame) -> int:
    """Detecta una fila probable de encabezados dentro de las primeras filas.

    Tolera titulos arriba de la tabla y hojas con algunas filas vacias. Devuelve
    indice cero-based para usarlo como ``header=`` en pandas.read_excel.
    """
    if sample.empty:
        return 0
    best_idx, best_score = 0, -1e9
    max_rows = min(len(sample), 25)
    for idx in range(max_rows):
        row = list(sample.iloc[idx])
        vals = [v for v in row if _nonempty(v)]
        if len(vals) < 2:
            continue
        strings = sum(isinstance(v, str) and str(v).strip() != "" for v in vals)
        nums = sum(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)
        unique = len({norm(v) for v in vals if norm(v)})
        # Densidad de las siguientes filas: un buen encabezado suele tener datos debajo.
        below = sample.iloc[idx + 1 : min(idx + 5, max_rows)]
        if len(below):
            below_density = sum(_nonempty(v) for v in below.to_numpy().ravel()) / max(1, below.size)
        else:
            below_density = 0.0
        # Penaliza filas que parecen registros numericos y premia etiquetas unicas.
        score = len(vals) * 2.0 + strings * 1.5 + unique * 0.8 + below_density * 8.1 - nums * 0.8
        if idx == 0:
            score += 1.0
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx


def clean_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    out = out.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if out.empty and len(out.columns) == 0:
        return out
    out.columns = _dedupe_columns(out.columns)
    # dropna(how="all") ya elimina filas realmente vacias. Evitamos apply(axis=1),
    # que seria extremadamente lento en libros de cientos de miles/millones de filas.
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Lectura universal de Excel/CSV
# ---------------------------------------------------------------------------



def read_csv_robust(path: Path) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    # Primero intenta separadores comunes de forma rapida; despues deteccion automatica.
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        for sep in (",", ";", "\t", "|"):
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep, low_memory=False)
                if len(df.columns) > 1:
                    return df
            except Exception as e:
                last_err = e
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception as e:
            last_err = e
    raise ValueError(f"No se pudo leer el CSV/TXT: {last_err}")


def _excel_engine(ext: str) -> str:
    try:
        import python_calamine  # noqa: F401
        return "calamine"
    except Exception:
        if ext in (".xlsx", ".xlsm"):
            return "openpyxl"
        if ext == ".xls":
            return "xlrd"
        return "pyxlsb"


def _sheet_relevance(sheet: str, df: pd.DataFrame, prompt: str) -> float:
    """R10.2: rank sheets by explicit user intent + transactional detail.

    A sheet is no longer selected merely because it is large or because a domain
    prompt happened to mention legacy columns. If the user explicitly names a
    sheet, that instruction wins. Otherwise the engine favors tables that look
    like detailed transactions and only uses prompt/schema overlap as a tiebreaker.
    """
    from universal_prompt_engine import norm as _unorm, score_transactional_source

    p = _unorm(prompt)
    sname = _unorm(sheet)
    info = score_transactional_source(df)
    score = float(info.get("score", 0.0)) * 4.0

    # Explicit source references are authoritative.
    explicit_patterns = [
        rf"\bhoja\s+{re.escape(sname)}\b",
        rf"\b{sname}\s+(?:es\s+)?(?:la\s+)?(?:fuente|base de datos principal|unica fuente)\b",
    ] if sname else []
    if any(re.search(pat, p) for pat in explicit_patterns):
        score += 1000.0
    elif sname and sname in p:
        score += 40.0

    # Prompt/schema overlap is useful, but secondary to transactional structure.
    stop = {"analiza","analizar","archivo","excel","reporte","resumen","completo","completamente",
            "dame","quiero","calcula","calcular","datos","informacion","principales","mejor","peor",
            "todos","todas","sobre","para","con","del","las","los","una","uno","por","que"}
    tokens = [t for t in p.split() if len(t) >= 3 and t not in stop]
    blob_cols = " | ".join(_unorm(c) for c in df.columns)
    for tok in tokens:
        if tok in blob_cols:
            score += 1.5
        if tok in sname:
            score += 2.0

    # Weak naming hints only; never override explicit user choice.
    if any(x in sname for x in ("resumen", "dashboard", "grafica", "pivot", "td", "reporte")):
        score -= 6.0
    if any(x in sname for x in ("bd", "base", "datos", "detalle", "movimiento", "transaccion")):
        score += 3.0
    return score


def load_tabular(path: Path, prompt: str = "") -> Tuple[pd.DataFrame, Dict[str, Any]]:
    contract = validate_workbook_contract(path, prompt)
    ext = path.suffix.lower()
    meta: Dict[str, Any] = {"archivo": path.name, "extension": ext, "hojas": [], "hojas_info": []}

    if ext in (".csv", ".txt"):
        df = clean_table(read_csv_robust(path))
        meta.update({"hojas": ["CSV"], "hoja_analizada": "CSV", "motor_excel": None})
        meta["hojas_info"] = [{"hoja": "CSV", "filas": int(len(df)), "columnas": list(map(str, df.columns)), "encabezado_fila": 1}]
        return df, meta

    if ext not in (".xlsx", ".xlsm", ".xls", ".xlsb"):
        raise ValueError("Formato no soportado. Usa XLSX, XLS, XLSB, XLSM o CSV.")

    engine = _excel_engine(ext)
    try:
        xls = pd.ExcelFile(path, engine=engine)
    except Exception:
        fallback = "openpyxl" if ext in (".xlsx", ".xlsm") else ("xlrd" if ext == ".xls" else "pyxlsb")
        xls = pd.ExcelFile(path, engine=fallback)
        engine = fallback

    meta["motor_excel"] = engine
    meta["hojas"] = list(xls.sheet_names)
    frames: List[Tuple[str, pd.DataFrame, int]] = []
    for sheet in xls.sheet_names:
        try:
            # La lectura pequena permite detectar si hay titulo/filas vacias antes de la tabla.
            sample = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=25)
            header_idx = detect_header_row(sample)
            f = pd.read_excel(xls, sheet_name=sheet, header=header_idx)
            f = clean_table(f)
            if not f.empty or len(f.columns) > 0:
                frames.append((sheet, f, header_idx))
                meta["hojas_info"].append({
                    "hoja": sheet,
                    "filas": int(len(f)),
                    "columnas": list(map(str, f.columns)),
                    "encabezado_fila": int(header_idx + 1),
                })
        except Exception as e:
            meta.setdefault("errores_hojas", {})[sheet] = str(e)

    if not frames:
        raise ValueError("El libro no contiene hojas legibles con datos tabulares.")

    requested_sheet = contract.get("explicit_sheet")
    if requested_sheet:
        for _sheet, _frame, _header_idx in frames:
            if norm(_sheet) == norm(requested_sheet):
                meta["hoja_analizada"] = _sheet
                meta["data_contract"] = contract
                return _frame, meta
        raise DataContractError(
            f'La hoja requerida "{requested_sheet}" no pudo cargarse como tabla.',
            code="SOURCE_SHEET_UNREADABLE",
            details={"requested_sheet": requested_sheet},
        )

    # Agrupa hojas con el mismo esquema normalizado. Si un esquema aparece en varias
    # hojas (por ano, mes, sucursal, etc.) se consolidan automaticamente.
    schemas: Dict[Tuple[str, ...], List[Tuple[str, pd.DataFrame, int]]] = {}
    for sheet, f, header_idx in frames:
        key = tuple(norm(c) for c in f.columns)
        schemas.setdefault(key, []).append((sheet, f, header_idx))

    groups = sorted(schemas.values(), key=lambda g: sum(len(x[1]) for x in g), reverse=True)
    best_group = groups[0]
    if len(best_group) > 1:
        combined: List[pd.DataFrame] = []
        for sheet, f, _ in best_group:
            ff = f.copy()
            ff["_HojaOrigen"] = sheet
            combined.append(ff)
        df = pd.concat(combined, ignore_index=True, copy=False)
        meta["hoja_analizada"] = ", ".join(x[0] for x in best_group)
        meta["hojas_consolidadas"] = [x[0] for x in best_group]
        if len(groups) > 1:
            meta["advertencia_hojas"] = (
                "Se consolidaron las hojas con el esquema tabular principal. Otras hojas con estructuras diferentes "
                "se documentaron pero no se mezclaron para evitar combinar datos incompatibles."
            )
        return df, meta

    # Si todas las hojas tienen esquemas distintos, selecciona la mas relevante para
    # la pregunta; sin una pregunta especifica elige la tabla con mayor volumen.
    candidates = [(sheet, f, header_idx, _sheet_relevance(sheet, f, prompt)) for sheet, f, header_idx in frames]
    candidates.sort(key=lambda x: (x[3], len(x[1])), reverse=True)
    sheet, df, _, _ = candidates[0]
    meta["hoja_analizada"] = sheet
    if len(frames) > 1:
        meta["advertencia_hojas"] = (
            f"El libro contiene {len(frames)} tablas con estructuras diferentes. Se eligio automaticamente la hoja "
            f"'{sheet}' por su relevancia/volumen. Las demas hojas aparecen en el perfil del reporte."
        )
    return df, meta


# ---------------------------------------------------------------------------
# Inferencia semantica y perfil generico
# ---------------------------------------------------------------------------

# Amplia el diccionario V3 sin borrar sus patrones originales.
EXTRA_ROLE_PATTERNS: Dict[str, List[str]] = {
    "date": ["fecha factura", "fecha movimiento", "fecha operacion", "fecha registro", "fec", "fch", "timestamp", "datetime"],
    "customer": ["codigo cliente", "cod cliente", "cve cliente", "clave cliente", "no cliente", "numero cliente", "cuenta cliente", "razon social", "customer number"],
    "product": ["codigo producto", "cod producto", "cve producto", "clave producto", "codigo articulo", "material", "part number", "part no", "concepto"],
    "quantity": ["cantidad vendida", "cantidad compra", "qty sold", "volume", "volumen", "cant", "cantidad total"],
    "unit_price": ["precio venta", "precio unit", "p unitario", "valor unitario", "unit value", "rate"],
    "revenue": ["venta neta", "ventas netas", "importe neto", "monto venta", "monto total", "total amount", "net amount", "neto", "facturacion neta", "ingreso total"],
    "unit_cost": ["costo compra", "costo promedio", "costo unit", "cost unit", "unit purchase cost"],
    "total_cost": ["costo extendido", "importe costo", "total costo", "costo neto"],
    "invoice": ["no factura", "num factura", "numero factura", "factura no", "documento", "doc no", "folio venta", "folio operacion", "transaction id"],
    "country": ["nacion", "country name"],
    "seller": ["ejecutivo", "asesor", "agente", "empleado ventas", "sales rep", "representative"],
}
for role, pats in EXTRA_ROLE_PATTERNS.items():
    base.ROLE_PATTERNS.setdefault(role, [])
    for p in pats:
        if p not in base.ROLE_PATTERNS[role]:
            base.ROLE_PATTERNS[role].append(p)


def infer_roles(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    roles = ORIGINAL_INFER_ROLES(df)

    # Fallback basado en tipo/valores para fechas cuando el encabezado es poco descriptivo.
    if not roles.get("date"):
        for c in df.columns:
            s = df[c]
            if pd.api.types.is_datetime64_any_dtype(s):
                roles["date"] = c
                break
        if not roles.get("date"):
            for c in df.columns:
                cn = norm(c)
                if not any(x in cn for x in ("fecha", "date", "time", "fec", "fch")):
                    continue
                nonnull = df[c].dropna().head(250)
                if len(nonnull):
                    parsed = pd.to_datetime(nonnull, errors="coerce")
                    if float(parsed.notna().mean()) >= 0.8:
                        roles["date"] = c
                        break
    return roles


def _sample_values(s: pd.Series, n: int = 3) -> List[str]:
    vals: List[str] = []
    for v in s.dropna().head(100):
        txt = str(v).strip()
        if txt and txt not in vals:
            vals.append(txt[:80])
        if len(vals) >= n:
            break
    return vals


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    total = max(1, len(df))
    for c in df.columns:
        if str(c).startswith("_"):
            continue
        s = df[c]
        nonnull = int(s.notna().sum())
        unique = int(s.nunique(dropna=True)) if nonnull else 0
        unique_ratio = unique / max(1, nonnull)
        tipo = "texto"
        parsed_date: Optional[pd.Series] = None
        numeric = pd.api.types.is_numeric_dtype(s)
        if pd.api.types.is_datetime64_any_dtype(s):
            tipo = "fecha"
        elif pd.api.types.is_bool_dtype(s):
            tipo = "booleano"
        elif numeric:
            tipo = "identificador_numerico" if unique_ratio > 0.97 and unique > 20 else "numerico"
        else:
            sample = s.dropna().head(300)
            cn = norm(c)
            if len(sample) and any(k in cn for k in ("fecha", "date", "time", "timestamp", "fec", "fch")):
                parsed_date = pd.to_datetime(sample, errors="coerce")
                if float(parsed_date.notna().mean()) >= 0.8:
                    tipo = "fecha"
            if tipo == "texto":
                if unique_ratio > 0.97 and unique > 20:
                    tipo = "identificador"
                elif unique <= min(100, max(20, int(total * 0.20))):
                    tipo = "categoria"

        row: Dict[str, Any] = {
            "Columna": str(c),
            "Tipo_detectado": tipo,
            "No_nulos": nonnull,
            "Nulos_%": round((1 - nonnull / total) * 100.0, 2),
            "Valores_unicos": unique,
            "Ejemplos": " | ".join(_sample_values(s)),
        }
        if numeric:
            ns = pd.to_numeric(s, errors="coerce")
            if ns.notna().any():
                row.update({
                    "Min": float(ns.min()), "Max": float(ns.max()), "Promedio": float(ns.mean()),
                    "Mediana": float(ns.median()), "Suma": float(ns.sum()),
                })
        elif tipo == "fecha":
            ds = pd.to_datetime(s, errors="coerce")
            if ds.notna().any():
                row["Min"] = ds.min().isoformat()
                row["Max"] = ds.max().isoformat()
        rows.append(row)
    return pd.DataFrame(rows)


def build_generic_sections(work: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    original_cols = [c for c in work.columns if not str(c).startswith("_")]
    df = work[original_cols]
    profile_df = column_profile(df)
    sections: Dict[str, pd.DataFrame] = {"Perfil_Columnas": profile_df}

    total_cells = max(1, len(df) * max(1, len(df.columns)))
    null_cells = int(df.isna().sum().sum())
    duplicates = int(df.duplicated().sum()) if len(df.columns) else 0
    type_counts = profile_df["Tipo_detectado"].value_counts() if not profile_df.empty else pd.Series(dtype=int)
    kpis = [
        ("Filas", int(len(df))),
        ("Columnas", int(len(df.columns))),
        ("Filas duplicadas", duplicates),
        ("Celdas nulas %", round(null_cells / total_cells * 100.0, 2)),
        ("Columnas numericas", int(type_counts.get("numerico", 0))),
        ("Columnas fecha", int(type_counts.get("fecha", 0))),
        ("Columnas categoria", int(type_counts.get("categoria", 0))),
    ]
    sections["KPIs_Generales"] = pd.DataFrame(kpis, columns=["Indicador", "Valor"])

    numeric_cols = [str(r["Columna"]) for _, r in profile_df.iterrows() if r["Tipo_detectado"] == "numerico"]
    if numeric_cols:
        rows = []
        for c in numeric_cols[:50]:
            s = pd.to_numeric(df[c], errors="coerce")
            if not s.notna().any():
                continue
            rows.append({
                "Columna": c, "Conteo": int(s.count()), "Suma": float(s.sum()), "Promedio": float(s.mean()),
                "Mediana": float(s.median()), "Min": float(s.min()), "Max": float(s.max()),
            })
        if rows:
            sections["Estadisticos_Numericos"] = pd.DataFrame(rows)

    # Top de categorias informativas; evita IDs de alta cardinalidad.
    cat_rows = profile_df.loc[profile_df["Tipo_detectado"].eq("categoria")].copy()
    cat_rows = cat_rows.sort_values("Valores_unicos").head(5)
    for _, r in cat_rows.iterrows():
        c = str(r["Columna"])
        vc = df[c].fillna("(Nulo)").astype(str).value_counts(dropna=False).head(20).reset_index()
        vc.columns = [c, "Registros"]
        safe = re.sub(r"[^A-Za-z0-9]+", "_", c).strip("_")[:18] or "Categoria"
        sections[f"Top_{safe}"] = vc

    # Correlacion compacta entre variables numericas reales.
    corr_cols = numeric_cols[:10]
    if len(corr_cols) >= 2:
        # Para libros gigantes una muestra reproducible evita que una correlacion secundaria
        # haga mas lento todo el reporte. Los KPIs/rankings principales siguen siendo exactos.
        corr_base = df[corr_cols]
        if len(corr_base) > 100000:
            corr_base = corr_base.sample(n=100000, random_state=42)
        corr = corr_base.apply(pd.to_numeric, errors="coerce").corr().round(4)
        corr.insert(0, "Variable", corr.index)
        sections["Correlaciones"] = corr.reset_index(drop=True)

    # Tendencia generica: primera fecha + primera metrica numerica no-ID.
    date_candidates = [str(r["Columna"]) for _, r in profile_df.iterrows() if r["Tipo_detectado"] == "fecha"]
    if date_candidates and numeric_cols:
        dc = date_candidates[0]
        # Prioriza montos/cantidades/precios sobre columnas arbitrarias.
        preference = ["venta", "sales", "revenue", "importe", "monto", "total", "cantidad", "quantity", "precio", "price", "costo", "cost"]
        metric = sorted(numeric_cols, key=lambda c: (0 if any(k in norm(c) for k in preference) else 1, numeric_cols.index(c)))[0]
        ds = pd.to_datetime(df[dc], errors="coerce")
        ns = pd.to_numeric(df[metric], errors="coerce")
        tmp = pd.DataFrame({"Fecha": ds, "Valor": ns}).dropna(subset=["Fecha"])
        if not tmp.empty:
            tmp["Mes"] = tmp["Fecha"].dt.to_period("M").astype(str)
            tr = tmp.groupby("Mes", dropna=False)["Valor"].agg(["sum", "mean", "count"]).reset_index()
            tr.columns = ["Mes", f"Suma_{metric}", f"Promedio_{metric}", "Registros"]
            sections["Tendencia_Generica"] = tr

    return sections


def build_overview_sections(work: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any], List[str]]:
    # Siempre genera un perfil generico, incluso si el archivo no es de ventas.
    generic = build_generic_sections(work)
    notes: List[str] = []
    sections: Dict[str, pd.DataFrame] = dict(generic)
    summary: Dict[str, Any] = {
        "tipo": "overview",
        "filas_analizadas": int(len(work)),
        "secciones": list(sections.keys()),
    }

    # Si realmente se pudieron derivar ventas, conserva el motor comercial especializado V3.
    # Esto evita mostrar secciones de ventas en archivos de RH, inventarios, encuestas, etc.
    if "_ventas" in work.columns:
        try:
            business_sections, business_summary, business_notes = ORIGINAL_BUILD_OVERVIEW(work, roles)
            notes.extend(business_notes)
            for name, table in business_sections.items():
                target = "KPIs_Comerciales" if name == "KPIs" else name
                sections[target] = table
            summary.update({"indicadores_comerciales": business_summary.get("indicadores", {})})
        except Exception as e:
            notes.append(f"El perfil general fue generado; el bloque comercial especializado no pudo calcularse: {e}")

    summary["secciones"] = list(sections.keys())
    return sections, summary, notes


# ---------------------------------------------------------------------------
# Plan generico de preguntas arbitrarias
# ---------------------------------------------------------------------------

def _resolve_col(name: Any, df: pd.DataFrame) -> Optional[str]:
    if name is None:
        return None
    raw = str(name).strip()
    if raw in df.columns:
        return raw
    nn = norm(raw)
    exact = [str(c) for c in df.columns if norm(c) == nn]
    return exact[0] if exact else None


def llm_generic_plan(prompt: str, work: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if not base.ollama_available():
        return None
    prof = column_profile(work[[c for c in work.columns if not str(c).startswith("_")]])
    schema = prof[[c for c in ["Columna", "Tipo_detectado", "Valores_unicos", "Ejemplos"] if c in prof.columns]].to_dict("records")
    system = """/no_think
Eres un planificador de analisis tabular. Devuelve SOLO JSON valido, sin markdown ni explicaciones.
Usa exclusivamente nombres EXACTOS de columnas que aparecen en el esquema.
Formato:
{
  "type":"generic",
  "operation":"sum|mean|median|min|max|count|nunique|top|bottom|describe|trend|correlation",
  "value_column":"columna exacta o null",
  "group_by":"columna exacta o null",
  "date_column":"columna exacta o null",
  "compare_column":"columna exacta o null",
  "top_n":10,
  "filters":[{"column":"exacta","op":"contains|equals|gt|gte|lt|lte","value":"valor"}]
}
Reglas:
- 'top/bottom' con group_by y value_column agrega SUMA de value_column por grupo; sin value_column usa conteo.
- 'trend' usa date_column y, si existe, value_column.
- 'correlation' requiere value_column y compare_column numericas.
- No inventes columnas ni formulas. Si la pregunta es ambigua usa describe.
"""
    user = json.dumps({"solicitud": prompt, "columnas": schema}, ensure_ascii=False)
    try:
        raw = base.ollama_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True, timeout=180, num_predict=220)
        obj = json.loads(base._clean_model_text(raw))
        if not isinstance(obj, dict):
            return None
        obj["type"] = "generic"
        return obj
    except Exception:
        return None


def _apply_generic_filters(df: pd.DataFrame, filters: Any) -> pd.DataFrame:
    if not isinstance(filters, list):
        return df
    out = df
    for f in filters[:10]:
        if not isinstance(f, dict):
            continue
        c = _resolve_col(f.get("column"), out)
        if not c:
            continue
        op = str(f.get("op", "contains")).lower()
        value = f.get("value")
        if op in {"gt", "gte", "lt", "lte"}:
            s = pd.to_numeric(out[c], errors="coerce")
            try:
                v = float(value)
            except Exception:
                continue
            mask = {"gt": s > v, "gte": s >= v, "lt": s < v, "lte": s <= v}[op]
            out = out.loc[mask.fillna(False)]
        else:
            s = out[c].astype(str)
            vv = str(value or "")
            if op == "equals":
                out = out.loc[s.str.casefold().eq(vv.casefold())]
            else:
                out = out.loc[s.str.contains(re.escape(vv), case=False, na=False)]
    return out


def execute_generic_plan(work: pd.DataFrame, plan: Dict[str, Any]) -> Tuple[Dict[str, Any], pd.DataFrame, List[str], Dict[str, pd.DataFrame]]:
    notes: List[str] = []
    data = work[[c for c in work.columns if not str(c).startswith("_")]].copy()
    data = _apply_generic_filters(data, plan.get("filters"))
    op = str(plan.get("operation") or "describe").lower()
    value_col = _resolve_col(plan.get("value_column"), data)
    group_col = _resolve_col(plan.get("group_by"), data)
    date_col = _resolve_col(plan.get("date_column"), data)
    compare_col = _resolve_col(plan.get("compare_column"), data)
    top_n = max(1, min(int(plan.get("top_n") or 10), 100))

    summary = {"tipo": "generic", "operacion": op, "filas_analizadas": int(len(data))}
    sections: Dict[str, pd.DataFrame] = {}

    if op == "describe":
        sections = build_generic_sections(data)
        result = sections.get("Estadisticos_Numericos", sections.get("Perfil_Columnas", pd.DataFrame()))
        return summary, result, notes, sections

    if op in {"sum", "mean", "median", "min", "max", "top", "bottom"} and value_col:
        nums = pd.to_numeric(data[value_col], errors="coerce")
        if not nums.notna().any():
            why = f"La columna '{value_col}' no contiene valores numericos utilizables."
            notes.append(why)
            result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
            return summary, result, notes, {"Resultado": result}
        data = data.copy(); data["__valor"] = nums

    if op in {"top", "bottom"}:
        if group_col:
            if value_col:
                result = data.groupby(group_col, dropna=False)["__valor"].sum(min_count=1).reset_index(name=f"Suma_{value_col}")
                metric_col = f"Suma_{value_col}"
            else:
                result = data.groupby(group_col, dropna=False).size().reset_index(name="Registros")
                metric_col = "Registros"
            result = result.sort_values(metric_col, ascending=(op == "bottom"), na_position="last").head(top_n).reset_index(drop=True)
        elif value_col:
            result = data[[value_col]].copy()
            result["__num"] = pd.to_numeric(result[value_col], errors="coerce")
            result = result.sort_values("__num", ascending=(op == "bottom")).drop(columns="__num").head(top_n).reset_index(drop=True)
        else:
            why = "Para un ranking se requiere group_by o value_column."
            notes.append(why); result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
        sections["Resultado"] = result
        return summary, result, notes, sections

    if op in {"sum", "mean", "median", "min", "max"}:
        if not value_col:
            why = f"La operacion {op} requiere una columna numerica."
            notes.append(why); result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
        elif group_col:
            result = data.groupby(group_col, dropna=False)["__valor"].agg(op).reset_index(name=f"{op}_{value_col}")
            result = result.sort_values(result.columns[-1], ascending=False, na_position="last").reset_index(drop=True)
        else:
            val = getattr(data["__valor"], op)()
            result = pd.DataFrame([{"Operacion": op, "Columna": value_col, "Valor": float(val) if pd.notna(val) else None}])
        sections["Resultado"] = result
        return summary, result, notes, sections

    if op == "count":
        if group_col:
            result = data.groupby(group_col, dropna=False).size().reset_index(name="Registros").sort_values("Registros", ascending=False).reset_index(drop=True)
        else:
            result = pd.DataFrame([{"Registros": int(len(data))}])
        sections["Resultado"] = result
        return summary, result, notes, sections

    if op == "nunique":
        if value_col:
            if group_col:
                result = data.groupby(group_col, dropna=False)[value_col].nunique(dropna=True).reset_index(name=f"Unicos_{value_col}")
            else:
                result = pd.DataFrame([{"Columna": value_col, "Valores_unicos": int(data[value_col].nunique(dropna=True))}])
        else:
            result = pd.DataFrame([{"Columna": str(c), "Valores_unicos": int(data[c].nunique(dropna=True))} for c in data.columns])
        sections["Resultado"] = result
        return summary, result, notes, sections

    if op == "trend":
        if not date_col:
            # Busca automaticamente una fecha.
            p = column_profile(data)
            dates = p.loc[p["Tipo_detectado"].eq("fecha"), "Columna"].tolist()
            date_col = dates[0] if dates else None
        if not date_col:
            why = "No se detecto una columna de fecha para construir la tendencia."
            notes.append(why); result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
            sections["Resultado"] = result; return summary, result, notes, sections
        dates = pd.to_datetime(data[date_col], errors="coerce")
        tmp = data.copy(); tmp["__fecha"] = dates; tmp = tmp.loc[tmp["__fecha"].notna()]
        tmp["Mes"] = tmp["__fecha"].dt.to_period("M").astype(str)
        if value_col:
            tmp["__valor"] = pd.to_numeric(tmp[value_col], errors="coerce")
            result = tmp.groupby("Mes", dropna=False)["__valor"].agg(["sum", "mean", "count"]).reset_index()
            result.columns = ["Mes", f"Suma_{value_col}", f"Promedio_{value_col}", "Registros"]
        else:
            result = tmp.groupby("Mes", dropna=False).size().reset_index(name="Registros")
        sections["Tendencia"] = result
        return summary, result, notes, sections

    if op == "correlation":
        if not value_col or not compare_col:
            why = "La correlacion requiere dos columnas numericas."
            notes.append(why); result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
        else:
            a = pd.to_numeric(data[value_col], errors="coerce")
            b = pd.to_numeric(data[compare_col], errors="coerce")
            corr = a.corr(b)
            result = pd.DataFrame([{"Variable_1": value_col, "Variable_2": compare_col, "Correlacion": float(corr) if pd.notna(corr) else None}])
        sections["Resultado"] = result
        return summary, result, notes, sections

    why = f"Operacion generica no soportada: {op}."
    notes.append(why); result = pd.DataFrame([{"Resultado": "No calculable", "Motivo": why}])
    return summary, result, notes, {"Resultado": result}


# ---------------------------------------------------------------------------
# Analisis principal universal
# ---------------------------------------------------------------------------

def build_profile(work: pd.DataFrame, original: pd.DataFrame, roles: Dict[str, Optional[str]], derived: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    p = ORIGINAL_BUILD_PROFILE(work, original, roles, derived, meta)
    cp = column_profile(original)
    p["perfil_columnas"] = cp.to_dict("records")
    p["hojas_info"] = meta.get("hojas_info", [])
    p["motor_excel"] = meta.get("motor_excel")

    # V7: la calidad siempre describe el archivo COMPLETO, nunca el subconjunto
    # temporal usado para responder una pregunta o un filtro. En V6 un plan del LLM
    # podia filtrar a cero filas y terminaba haciendo parecer que todas las columnas
    # estaban 100% vacias.
    user_cols = [c for c in original.columns if not str(c).startswith("_")]
    quality_df = original[user_cols] if user_cols else original.iloc[:, 0:0]
    total_cells = max(1, len(quality_df) * max(1, len(quality_df.columns)))
    null_cells = int(quality_df.isna().sum().sum()) if len(quality_df.columns) else 0
    duplicate_rows = int(quality_df.duplicated().sum()) if len(quality_df.columns) else 0
    p["columnas"] = [str(c) for c in user_cols]
    p["calidad_archivo"] = {
        "filas": int(len(quality_df)),
        "columnas": int(len(quality_df.columns)),
        "filas_duplicadas": duplicate_rows,
        "filas_duplicadas_pct": (duplicate_rows / len(original) * 100.0) if len(original) else 0.0,
        "celdas_nulas_pct": null_cells / total_cells * 100.0,
    }
    return p


def _is_broad_overview_request(prompt: str, hplan: Dict[str, Any]) -> bool:
    """Decide si la solicitud pide un reporte general.

    V6 descartaba el modo overview por cualquier aparicion de la palabra "por".
    Eso rompia prompts validos como "no inventes formulas respaldadas por los datos"
    y dejaba que el LLM inventara filtros a partir de los ejemplos del archivo.
    """
    n = norm(prompt)
    if not n:
        return True
    broad_phrases = (
        "analiza completamente", "analisis completo", "analiza todo", "reporte completo",
        "reporte general", "resumen general", "analisis general", "todos los indicadores",
        "identifica la estructura", "calidad de datos", "rankings y tendencias",
        "principales productos", "principales clientes", "tendencia mensual",
        "analiza el archivo", "revisa el archivo", "perfil del archivo",
    )
    if any(x in n for x in broad_phrases):
        return True
    # El plan heuristico comercial ya protege frases negativas como
    # "no inventes margen". Si sigue siendo overview y el texto contiene una
    # intencion de reporte/resumen, se respeta sin consultar al LLM.
    if hplan.get("type") == "overview" and any(w in n for w in ("analiza", "analisis", "reporte", "resumen", "indicadores", "metricas", "perfil")):
        return True
    return False


def _validate_generic_plan(plan: Optional[Dict[str, Any]], prompt: str, work: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Valida un plan propuesto por el LLM y elimina filtros no solicitados.

    Regla critica: un valor de filtro debe aparecer explicitamente en la pregunta.
    Asi el modelo no puede reutilizar como filtros valores de ejemplo del perfil
    (por ejemplo 489434/489435/489436), que fue la regresion observada en V6.
    """
    if not isinstance(plan, dict):
        return None
    valid_ops = {"sum", "mean", "median", "min", "max", "count", "nunique", "top", "bottom", "describe", "trend", "correlation"}
    out = dict(plan)
    op = str(out.get("operation") or "describe").lower()
    out["operation"] = op if op in valid_ops else "describe"
    out["type"] = "generic"

    for key in ("value_column", "group_by", "date_column", "compare_column"):
        resolved = _resolve_col(out.get(key), work)
        out[key] = resolved

    try:
        out["top_n"] = max(1, min(int(out.get("top_n") or 10), 100))
    except Exception:
        out["top_n"] = 10

    prompt_n = norm(prompt)
    safe_filters: List[Dict[str, Any]] = []
    filters = out.get("filters")
    if isinstance(filters, list):
        for f in filters[:10]:
            if not isinstance(f, dict):
                continue
            col = _resolve_col(f.get("column"), work)
            value = f.get("value")
            opf = str(f.get("op") or "contains").lower()
            if not col or opf not in {"contains", "equals", "gt", "gte", "lt", "lte"}:
                continue
            value_text = str(value if value is not None else "").strip()
            value_n = norm(value_text)
            # Solo se acepta un filtro si el usuario escribio ese valor. Esto evita
            # filtros alucinados desde los ejemplos enviados al LLM.
            if not value_n or value_n not in prompt_n:
                continue
            safe_filters.append({"column": col, "op": opf, "value": value})
    out["filters"] = safe_filters
    return out


def _ensure_commercial_report_sections(work: pd.DataFrame, roles: Dict[str, Optional[str]], sections: Dict[str, pd.DataFrame], notes: List[str]) -> Dict[str, pd.DataFrame]:
    """Garantiza que un archivo comercial siempre tenga contexto ejecutivo completo.

    Una consulta especifica puede seguir devolviendo su ``Resultado``, pero el Excel/PDF
    no debe producir paginas vacias: se completan KPIs, rankings, tendencia y cancelaciones
    a partir del archivo completo.
    """
    if "_ventas" not in work.columns:
        return sections
    if "KPIs_Comerciales" in sections and "Tendencia_Mensual" in sections:
        return sections
    try:
        full_sections, _, full_notes = build_overview_sections(work, roles)
        for name, table in full_sections.items():
            target = "KPIs_Comerciales" if name == "KPIs" else name
            if target not in sections or sections[target] is None or sections[target].empty:
                sections[target] = table
        for n in full_notes:
            if n not in notes:
                notes.append(n)
    except Exception as e:
        notes.append(f"No fue posible completar el contexto comercial del reporte: {e}")
    return sections


def _prepare_governed_deliverable_plan(
    original: pd.DataFrame,
    prompt: str,
    path: Path,
    sheet: str,
    semantic_context: Optional[Dict[str, Any]],
    prompt_sha256: str,
    prompt_preview: str,
) -> Dict[str, Any]:
    plan = dd.build_dashboard_plan(original, prompt, path.name, sheet, semantic_context)
    plan["request_prompt_sha256"] = prompt_sha256
    plan["request_prompt_preview"] = prompt_preview
    plan["prompt_integrity"] = "r10.18a-cross-format-authority"
    return plan


def _attach_governed_deliverable_manifest(
    profile: Dict[str, Any],
    dashboard_plan: Dict[str, Any],
    path: Path,
    sheet: str,
    row_count: int,
    prompt_sha256: str,
) -> None:
    manifest = build_governed_deliverable_manifest(
        dashboard_plan=dashboard_plan,
        filename=path.name,
        sheet=sheet,
        row_count=row_count,
        prompt_sha256=prompt_sha256,
    )
    dashboard_plan["enterprise_deliverable_manifest"] = manifest
    profile["deliverable_manifest"] = manifest


def analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None, analytic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # R10.13C.2: request prompt is immutable authority for this execution.
    request_prompt = str(prompt or "").strip()
    if not request_prompt:
        raise ValueError("PROMPT_REQUIRED")
    prompt = request_prompt
    request_prompt_sha256 = hashlib.sha256(request_prompt.encode("utf-8")).hexdigest()
    request_prompt_preview = " ".join(request_prompt.split())[:240]
    # R10.13C.1: el prompt de ESTA solicitud es la unica autoridad.
    prompt = str(prompt or "").strip()
    if not prompt:
        prompt = "Analiza completamente este archivo sin inventar datos."
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8", errors="strict")).hexdigest()
    prompt_preview = " ".join(prompt.split())[:220]

    started = base.time.time()
    original, meta = load_tabular(path, prompt)
    original.columns = _dedupe_columns(original.columns)

    # V8.5.5: mapeo BI semántico independiente de la cardinalidad. El encabezado y
    # las relaciones entre columnas tienen prioridad sobre el número de valores únicos.
    roles_bi = bi.semantic_map(original, semantic_context)
    dashboard_plan = dp.detect_dashboard_plan(original, prompt, semantic_context)
    is_customer_performance = dashboard_plan.get("type") == "customer_performance"
    is_commercial_bi = bool(roles_bi.get("revenue") and roles_bi.get("date") and (roles_bi.get("customer") or roles_bi.get("product")))

    if is_customer_performance:
        # R8: familia especializada para seguimiento de clientes Actual/Presupuesto/Anterior.
        # No exige importe de venta ni fecha transaccional y respeta Fecha_Inicial/Fecha_Final
        # únicamente como cobertura del reporte.
        work, planner_notes = dp.prepare_customer_performance(original, dashboard_plan)
        model = dp.build_customer_performance_model(work, prompt, dashboard_plan)
        spec = bi.compile_report_spec(prompt)
        notes = list(planner_notes)
        if meta.get("advertencia_hojas"):
            notes.append(meta["advertencia_hojas"])
        if meta.get("errores_hojas"):
            notes.append("Algunas hojas no pudieron leerse y quedaron registradas en la trazabilidad.")

        # Perfil universal para trazabilidad y para los generadores PDF/Excel existentes.
        roles = infer_roles(original)
        try:
            from enterprise_ai.semantic_registry import merge_context_roles
            roles = merge_context_roles(roles, semantic_context)
        except Exception:
            pass
        source_work, source_derived = base.prepare_df(original, roles)
        profile = build_profile(source_work, original, roles, source_derived, meta)
        profile["dashboard_plan"] = dashboard_plan
        profile["customer_performance_kpis"] = model["kpis"]
        sections = dp.customer_sections(model)
        narrative = dp.customer_narrative(model)

        stamp = base.datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)[:60]
        outputs: Dict[str, Optional[str]] = {"html": None, "pdf": None, "excel": None}
        dynamic_plan = _prepare_governed_deliverable_plan(original, prompt, path, meta.get("hoja_analizada") or "", semantic_context, prompt_sha256, prompt_preview)
        profile["dynamic_dashboard_plan"] = dynamic_plan
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256)
        if spec["outputs"].get("html"):
            html_path = base.REPORTES / f"Dashboard_Dinamico_{stem}_{stamp}.html"
            dynamic_plan = dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "", semantic_context, prepared_plan=dynamic_plan)
            profile["dynamic_dashboard_plan"] = dynamic_plan
            outputs["html"] = html_path.name
        if spec["outputs"].get("pdf"):
            pdf_path = base.REPORTES / f"Reporte_Ejecutivo_Clientes_{stem}_{stamp}.pdf"
            pro.pdf_report_professional(pdf_path, prompt, profile, sections, notes, narrative, "comercial")
            outputs["pdf"] = pdf_path.name
        if spec["outputs"].get("excel"):
            xlsx_path = base.REPORTES / f"Analisis_Clientes_{stem}_{stamp}.xlsx"
            pro.excel_report_professional(xlsx_path, prompt, profile, {"type":"customer_performance","dashboard_plan":dashboard_plan}, sections, notes, narrative, original, source_work, roles, "comercial")
            outputs["excel"] = xlsx_path.name

        if build_file_trace:
            profile["traceability"] = build_file_trace(filename=path.name, sheet=meta.get("hoja_analizada"), rows=len(original), columns=[str(c) for c in original.columns], roles=roles, derived=profile.get("calculos_derivados", {}), notes=notes, outputs=outputs, prompt=prompt)
        result = pd.DataFrame([model["kpis"]])
        plan = {"type":"customer_performance","dashboard_plan":dashboard_plan,"report_spec":spec}
        domain = "comercial-clientes"

    elif is_commercial_bi:
        work, derived_bi, bi_notes = bi.prepare_business(original, roles_bi, analytic_context)
        # Compatibilidad con las capas existentes (perfil, registro de dataset y RAG).
        roles = {
            "date": roles_bi.get("date"),
            "customer": roles_bi.get("customer"),
            "product": roles_bi.get("product"),
            "quantity": roles_bi.get("quantity"),
            "unit_price": None,
            "revenue": roles_bi.get("revenue"),
            "unit_cost": None,
            "total_cost": roles_bi.get("total_cost"),
            "invoice": roles_bi.get("invoice"),
            "country": None,
            "seller": roles_bi.get("seller"),
        }
        profile = build_profile(work, original, roles, derived_bi, meta)
        profile["roles_bi"] = roles_bi
        profile["calculos_derivados"] = derived_bi

        spec = bi.compile_report_spec(prompt)
        model = bi.build_bi_model(original, work, roles_bi, derived_bi, prompt, spec)
        notes = list(bi_notes)
        if meta.get("advertencia_hojas"):
            notes.append(meta["advertencia_hojas"])
        if meta.get("errores_hojas"):
            notes.append("Algunas hojas no pudieron leerse y quedaron registradas en la trazabilidad.")

        stamp = base.datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)[:60]
        outputs: Dict[str, Optional[str]] = {"html": None, "pdf": None, "excel": None}
        dynamic_plan = _prepare_governed_deliverable_plan(original, prompt, path, meta.get("hoja_analizada") or "", semantic_context, prompt_sha256, prompt_preview)
        profile["dynamic_dashboard_plan"] = dynamic_plan
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256)
        if spec["outputs"].get("html"):
            html_path = base.REPORTES / f"Dashboard_Dinamico_{stem}_{stamp}.html"
            dynamic_plan = dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "", semantic_context, prepared_plan=dynamic_plan)
            profile["dynamic_dashboard_plan"] = dynamic_plan
            outputs["html"] = html_path.name
        if spec["outputs"].get("pdf"):
            pdf_path = base.REPORTES / f"Reporte_Ejecutivo_BI_{stem}_{stamp}.pdf"
            bi.generate_pdf(pdf_path, path.name, model, notes, profile["deliverable_manifest"])
            outputs["pdf"] = pdf_path.name
        if spec["outputs"].get("excel"):
            xlsx_path = base.REPORTES / f"Analisis_BI_{stem}_{stamp}.xlsx"
            bi.generate_excel(xlsx_path, path.name, model, profile["deliverable_manifest"])
            outputs["excel"] = xlsx_path.name

        narrative = bi.executive_narrative(model, outputs)
        sections = {
            "KPIs_BI": pd.DataFrame([model["kpis"]]),
            "Mensual": model["monthly"], "Anual": model["annual"], "Lineas": model["lines"],
            "Productos": model["products"], "Clientes": model["customers"], "Vendedores": model["sellers"],
            "Facturas": model["invoices"], "Clientes_Perdidos": model["lost"], "Clientes_Caida": model["decline"],
            "Oportunidades": model["opportunities"], "Calidad_Datos": model["quality"],
        }
        result = pd.DataFrame([model["kpis"]])
        plan: Dict[str, Any] = {"type": "bi_report", "report_spec": spec, "roles_bi": roles_bi, "calculos_derivados": derived_bi}
        domain = "comercial"
    else:
        # Mantiene el analizador universal V7/V8 para archivos que no son comerciales.
        roles = infer_roles(original)
        try:
            from enterprise_ai.semantic_registry import merge_context_roles
            roles = merge_context_roles(roles, semantic_context)
        except Exception:
            pass
        work, derived = base.prepare_df(original, roles)
        profile = build_profile(work, original, roles, derived, meta)
        hplan = base.heuristic_plan(prompt)
        has_overview_intent = _is_broad_overview_request(prompt, hplan)
        business_specific = hplan.get("type") in {"ranking", "metric"} and bool(hplan.get("metric") or hplan.get("dimension"))
        if has_overview_intent or not prompt.strip():
            plan = {"type": "overview", "dimension": None, "metric": None, "order": "desc", "top_n": base.extract_top_n(prompt)}
            sections, summary, notes = build_overview_sections(work, roles)
            result = sections.get("KPIs_Comerciales", sections.get("KPIs_Generales", sections.get("Perfil_Columnas", pd.DataFrame())))
        elif business_specific:
            plan = hplan
            summary, result, notes, sections = base.execute_plan(work, roles, plan)
        else:
            gplan = _validate_generic_plan(llm_generic_plan(prompt, work), prompt, work)
            if gplan:
                plan = gplan
                summary, result, notes, sections = execute_generic_plan(work, gplan)
            else:
                plan = {"type": "overview", "dimension": None, "metric": None, "order": "desc", "top_n": 10}
                sections, summary, notes = build_overview_sections(work, roles)
                result = sections.get("KPIs_Comerciales", sections.get("KPIs_Generales", sections.get("Perfil_Columnas", pd.DataFrame())))
                notes.append("La solicitud libre no pudo convertirse en un plan estructurado; se genero el analisis universal del archivo.")
        if meta.get("advertencia_hojas"):
            notes.append(meta["advertencia_hojas"])
        if meta.get("errores_hojas"):
            notes.append("Algunas hojas no pudieron leerse y quedaron registradas en la trazabilidad.")
        domain = pro.infer_domain(work, roles)
        if domain == "comercial":
            sections = _ensure_commercial_report_sections(work, roles, sections, notes)
        sections = pro.enrich_sections(work, roles, sections, profile)
        narrative = base.narrate(prompt, profile, plan, sections, notes)
        stamp = base.datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)[:60]
        # R8: el fallback universal también respeta las salidas pedidas y SI puede
        # producir HTML, evitando el antiguo camino que siempre devolvía html=None.
        spec = bi.compile_report_spec(prompt)
        outputs = {"html": None, "pdf": None, "excel": None}
        dynamic_plan = _prepare_governed_deliverable_plan(original, prompt, path, meta.get("hoja_analizada") or "", semantic_context, prompt_sha256, prompt_preview)
        profile["dynamic_dashboard_plan"] = dynamic_plan
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256)
        if spec["outputs"].get("html"):
            html_path = base.REPORTES / f"Dashboard_Dinamico_{stem}_{stamp}.html"
            dynamic_plan = dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "", semantic_context, prepared_plan=dynamic_plan)
            profile["dynamic_dashboard_plan"] = dynamic_plan
            outputs["html"] = html_path.name
        if spec["outputs"].get("excel"):
            xlsx_path = base.REPORTES / f"Reporte_Ejecutivo_{stem}_{stamp}.xlsx"
            pro.excel_report_professional(xlsx_path, prompt, profile, plan, sections, notes, narrative, original, work, roles, domain)
            outputs["excel"] = xlsx_path.name
        if spec["outputs"].get("pdf"):
            pdf_path = base.REPORTES / f"Reporte_Ejecutivo_{stem}_{stamp}.pdf"
            pro.pdf_report_professional(pdf_path, prompt, profile, sections, notes, narrative, domain)
            outputs["pdf"] = pdf_path.name

    # Registra el archivo tabular para consultas deterministicas futuras del ContextEngine.
    try:
        if ENTERPRISE_COMPONENTS is not None:
            sec = ENTERPRISE_COMPONENTS.cfg.section("security")
            principal = Principal(sec.get("default_company", "empresa-local"), sec.get("default_user", "admin-local"), "admin")
            ENTERPRISE_COMPONENTS.datasets.register(principal, path, name=path.name, scope="company", roles=roles)
    except Exception as _dataset_exc:
        notes.append(f"V8: no se pudo registrar el dataset para consultas futuras: {_dataset_exc}")

    return {
        "ok": True,
        "request_prompt_sha256": request_prompt_sha256,
        "request_prompt_preview": request_prompt_preview,
        "prompt_integrity": "r10.13c.2-request-authority",
        "prompt_sha256": prompt_sha256,
        "prompt_preview": prompt_preview,
        "prompt_integrity": "r10.13c.2-request-authority",
        "archivo": path.name,
        "filas": int(len(original)),
        "columnas": [str(c) for c in original.columns],
        "hoja_analizada": meta.get("hoja_analizada"),
        "hojas": meta.get("hojas_info", []),
        "motor_excel": meta.get("motor_excel"),
        "dominio": domain,
        "roles": roles,
        "roles_bi": roles_bi if (is_commercial_bi or is_customer_performance) else None,
        "plan": plan,
        "report_spec": spec,
        "resultado": base.dataframe_records(result, 100),
        "secciones": {k: base.dataframe_records(v, 30) for k, v in sections.items()},
        "advertencias": notes,
        "narrativa": narrative,
        "html": outputs.get("html"),
        "excel": outputs.get("excel"),
        "pdf": outputs.get("pdf"),
        "segundos": round(base.time.time() - started, 2),
    }


# ---------------------------------------------------------------------------
# Monkey patches y UI V4
# ---------------------------------------------------------------------------

ORIGINAL_INFER_ROLES = base.infer_roles
ORIGINAL_BUILD_OVERVIEW = base.build_overview_sections
ORIGINAL_BUILD_PROFILE = base.build_profile

base.load_tabular = load_tabular
base.infer_roles = infer_roles
base.build_profile = build_profile
base.build_overview_sections = build_overview_sections
base.analyze_file = analyze_file
base.app.version = "8.5.5-r10.2"

# Actualiza textos de la interfaz sin duplicar todo el HTML de V3.
base.INDEX_HTML = base.INDEX_HTML.replace(
    "Analizador Empresarial de Excel / CSV",
    "Analizador Universal Empresarial de Excel / CSV - V8.5.5 R10.2 · Dashboard Dinámico IA",
).replace(
    "Procesa archivos grandes con Python/Pandas y usa Qwen local solo para interpretar los resultados. Los datos no se envian a Internet.",
    "Detecta automaticamente hojas, encabezados, columnas, tipos de datos y metricas. Procesa los datos con Python y usa Qwen local solo para interpretar resultados; nada se envia a Internet.",
).replace(
    "<b>Importante:</b> para Excel grandes usa esta pantalla en lugar de adjuntarlos directamente al chat de Open WebUI. Aqui el archivo se calcula con Python y el modelo recibe solo resultados resumidos.",
    "<b>Universal:</b> admite libros con nombres de columnas distintos. Si varias hojas comparten estructura las consolida; si son diferentes elige la tabla mas relevante y documenta las demas. Para libros no comerciales genera perfil, estadisticos, categorias, fechas y correlaciones sin inventar campos.",
).replace(
    "Analiza completamente el archivo. Calcula ventas netas, unidades, operaciones, ticket promedio, principales productos, clientes y paises, tendencia mensual y cancelaciones/devoluciones. Detecta limitaciones de los datos. Si no existe costo, indicalo y no inventes utilidad ni margen.",
    "Analiza completamente el archivo y genera un dashboard HTML interactivo, un reporte ejecutivo PDF y un Excel analitico. Incluye resumen, evolucion, lineas, productos, clientes, vendedores, facturas, clientes perdidos, clientes en caida, oportunidades y calidad de datos. Usa solo columnas reales y calculos deterministas; no inventes costos, margenes ni formulas.",
).replace(
    "<title>IA Empresarial Local - Analizador</title>",
    "<title>IA Empresarial Local - V8.5.5 R10.2 · Dashboard Dinámico IA</title>",
).replace(
    "<h1>Analizador Universal Empresarial de Excel / CSV</h1>",
    "<h1>Analizador Universal Empresarial de Excel / CSV <span style=\"font-size:14px;background:#dbeafe;color:#1d4ed8;padding:4px 8px;border-radius:999px;vertical-align:middle\">V8.5.5 R10.2</span></h1>",
)


# V8.5.5: la UI refleja las salidas reales solicitadas por el prompt.
base.INDEX_HTML = base.INDEX_HTML.replace(
    "Analizar y generar Excel/PDF",
    "Analizar y generar Dashboard / PDF / Excel",
).replace(
    """links.innerHTML='<a href="/download/'+encodeURIComponent(d.excel)+'">Descargar Excel</a><a href="/download/'+encodeURIComponent(d.pdf)+'">Descargar PDF</a>';""",
    """links.innerHTML=''; if(d.html) { links.innerHTML+='<a href="/view/'+encodeURIComponent(d.html)+'" target="_blank">Abrir Dashboard HTML</a>'; links.innerHTML+='<a href="/download/'+encodeURIComponent(d.html)+'" download>Descargar Dashboard HTML</a>'; } if(d.pdf) links.innerHTML+='<a href="/download/'+encodeURIComponent(d.pdf)+'">Descargar PDF</a>'; if(d.excel) links.innerHTML+='<a href="/download/'+encodeURIComponent(d.excel)+'">Descargar Excel</a>';""",
)

# R10.13C.1 UI prompt authority
base.INDEX_HTML = base.INDEX_HTML.replace(
    '<textarea id="prompt" name="prompt" required>',
    '<textarea id="prompt" name="prompt" required autocomplete="off" data-r1013c1="prompt-authority">',
)
base.INDEX_HTML = base.INDEX_HTML.replace(
    "status.innerHTML='<div class=\"note ok\">Listo: '+d.filas.toLocaleString()+' filas procesadas en '+d.segundos+' s.</div>';",
    "status.innerHTML='<div class=\"note ok\">Listo: '+d.filas.toLocaleString()+' filas procesadas en '+d.segundos+' s.<br><small>Prompt recibido: '+(d.prompt_preview||'')+'<br>SHA-256: '+(d.prompt_sha256||'N/D')+'</small></div>';",
)

@base.app.get("/view/{filename}")
def view_html_report(filename: str):
    """Abre dashboards HTML en el navegador; otros formatos siguen usando /download."""
    name = Path(filename).name
    path = base.REPORTES / name
    if path.suffix.lower() != ".html" or not path.exists() or path.parent.resolve() != base.REPORTES.resolve():
        raise base.HTTPException(status_code=404, detail="Dashboard no encontrado")
    return base.FileResponse(path, media_type="text/html; charset=utf-8")


@base.app.get("/version")
def version_info() -> Dict[str, Any]:
    return {"prompt_integrity": "r10.13c.2-request-authority", "version": "8.5.5-r10.2", "motor": "universal-profesional-memoria-rag", "script": "analizador_universal.py", "reportes": "dashboard HTML dinámico por prompt + PDF BI + Excel analitico", "enterprise_ai": "memoria persistente + RAG + datos estructurados + ContextEngine", "controles": "prompt authority + data contract + calculo deterministico + semantic mapper + aislamiento empresa/usuario"}

# V8: integra memoria persistente, RAG, seguridad y ContextEngine sin reemplazar el analizador V7.
try:
    from enterprise_ai.api import install_enterprise_routes
    from enterprise_ai.security import Principal
    ENTERPRISE_COMPONENTS = install_enterprise_routes(base.app, base.ROOT)
except Exception as _enterprise_exc:
    ENTERPRISE_COMPONENTS = None
    print(f"ADVERTENCIA V8: capa enterprise_ai no pudo inicializarse: {_enterprise_exc}")

app = base.app


def main() -> None:
    parser = base.argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
