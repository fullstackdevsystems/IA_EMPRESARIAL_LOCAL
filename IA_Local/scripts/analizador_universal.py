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
import uuid
import ipaddress
import threading

import hashlib
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from fastapi import Header, Request

import analizador_app as base

# R10.21F.1: runtime release identity has one canonical authority.
_RELEASE_METADATA_PATH = base.ROOT.parent / "RELEASE_METADATA.json"

if not _RELEASE_METADATA_PATH.is_file():
    raise RuntimeError("RELEASE_METADATA_MISSING")

try:
    _RELEASE_METADATA = json.loads(
        _RELEASE_METADATA_PATH.read_text(encoding="utf-8-sig")
    )
except Exception as exc:
    raise RuntimeError("RELEASE_METADATA_INVALID") from exc

if _RELEASE_METADATA.get("schema_version") != 1:
    raise RuntimeError("RELEASE_METADATA_SCHEMA_UNSUPPORTED")

if _RELEASE_METADATA.get("product") != "IA_EMPRESARIAL_LOCAL":
    raise RuntimeError("RELEASE_METADATA_PRODUCT_INVALID")

for _release_field in ("product_version", "release", "channel"):
    _release_value = _RELEASE_METADATA.get(_release_field)
    if not isinstance(_release_value, str) or not _release_value.strip():
        raise RuntimeError(
            f"RELEASE_METADATA_FIELD_INVALID:{_release_field}"
        )

PRODUCT_VERSION = _RELEASE_METADATA["product_version"].strip()
RELEASE_ID = _RELEASE_METADATA["release"].strip()
RELEASE_CHANNEL = _RELEASE_METADATA["channel"].strip()
import reportes_profesionales as pro
import bi_productivo as bi
import dashboard_planner as dp
import dashboard_dynamic as dd
from data_contract import validate_workbook_contract, DataContractError
from enterprise_deliverable_manifest import build_governed_deliverable_manifest
from enterprise_deliverable_registry import (
    DeliverableRegistryError,
    GovernedDeliverableRegistry,
    deliverable_registry_public_audit,
)
from enterprise_knowledge_qa import answer_unified_enterprise_question
from enterprise_agent_orchestrator import answer_enterprise_question_orchestrated
from enterprise_knowledge_store import (
    EnterpriseKnowledgeError,
    EnterpriseKnowledgeStore,
)
from enterprise_sql_gateway import (
    EnterpriseSqlConnectionStore, EnterpriseSqlError, EnterpriseSqlExecutor,
    EnterpriseSecretStore, SqlServerPyodbcProvider, WindowsCredentialSecretProvider, build_transient_sql_probe_profile,
    discover_schema, execute_smoke_query, probe_sql_server_metadata,
    public_sql_profile, test_connection,
)
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError
from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError
from enterprise_onboarding import EnterpriseOnboarding, OnboardingError
from enterprise_ai.providers import OllamaProvider, LMStudioProvider
from enterprise_source_execution import (
    execute_uploaded_file_source_with_reader,
    public_source_execution_metadata,
)


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
    source_fingerprint_sha256: Optional[str] = None,
    output_intent: Optional[Dict[str, Any]] = None,
) -> None:
    manifest = build_governed_deliverable_manifest(
        dashboard_plan=dashboard_plan,
        filename=path.name,
        sheet=sheet,
        row_count=row_count,
        prompt_sha256=prompt_sha256,
        source_fingerprint_sha256=source_fingerprint_sha256,
        output_intent=output_intent,
        source_fingerprint_required=True,
    )
    dashboard_plan["enterprise_deliverable_manifest"] = manifest
    profile["deliverable_manifest"] = manifest


def _source_fingerprint_from_meta(meta: Dict[str, Any]) -> Optional[str]:
    execution = meta.get("source_execution") if isinstance(meta, dict) else None
    execution = execution if isinstance(execution, dict) else {}
    provenance = execution.get("provenance") if isinstance(execution.get("provenance"), dict) else {}
    value = str(provenance.get("fingerprint_sha256") or "").strip().lower()
    if re.fullmatch(r"[a-f0-9]{64}", value):
        return value
    return None


def _local_deliverable_scope() -> Dict[str, Optional[str]]:
    return {
        "company_id": str(os.environ.get("IA_COMPANY_ID") or "empresa-local"),
        "user_id": str(os.environ.get("IA_USER_ID") or "admin-local"),
        "business_unit": None,
        "branch": None,
    }


def _register_governed_deliverables(
    *,
    profile: Dict[str, Any],
    outputs: Dict[str, Optional[str]],
    domain: str,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    registry = GovernedDeliverableRegistry(
        base.REPORTES
    )

    effective_scope = (
        _local_deliverable_scope()
        if scope is None
        else scope
    )

    return registry.register(
        scope=effective_scope,
        run_id=f"run-{uuid.uuid4().hex}",
        manifest=profile["deliverable_manifest"],
        outputs=outputs,
        domain=domain,
    )


def _r10_27_authenticated_analytic_principal() -> Optional[Principal]:
    """Resolve the authenticated tenant principal for governed analytics."""
    if ENTERPRISE_COMPONENTS is None:
        return None

    actor = base.ANALYZE_AUTH_CONTEXT.get()
    if not isinstance(actor, dict):
        return None

    company_id = str(actor.get("tenant_id") or "").strip()
    user_id = str(actor.get("user_id") or "").strip()
    actor_roles = actor.get("roles") or []

    if not company_id or not user_id:
        return None

    if isinstance(actor_roles, str):
        actor_roles = [actor_roles]

    role = (
        "admin"
        if "SYSTEM_ADMIN" in set(actor_roles)
        else "user"
    )

    return Principal(
        company_id=company_id,
        user_id=user_id,
        role=role,
    )


def _r10_27_authenticated_analytic_context(
    roles: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build validated tenant-scoped analytic context for authenticated analysis."""
    principal = _r10_27_authenticated_analytic_principal()
    if principal is None:
        return None

    return ENTERPRISE_COMPONENTS.analytics.build_context(
        principal,
        roles or {},
    )

def analyze_file(path: Path, prompt: str, semantic_context: Optional[Dict[str, Any]] = None, analytic_context: Optional[Dict[str, Any]] = None, register_dataset: bool = True) -> Dict[str, Any]:
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
    source_execution = execute_uploaded_file_source_with_reader(
        path=path,
        workspace_root=base.WORKSPACE,
        reader=lambda governed_path: load_tabular(governed_path, prompt),
    )
    if source_execution.get("status") != "OPENED":
        raise RuntimeError(
            "GOVERNED_UNIVERSAL_SOURCE_EXECUTION_BLOCKED:"
            + str(source_execution.get("reason") or "unknown")
        )
    original = source_execution["dataframe"]
    meta = dict(source_execution.get("reader_metadata") or {})
    meta["source_execution"] = public_source_execution_metadata(source_execution)
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
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256, _source_fingerprint_from_meta(meta), spec.get("output_intent"))
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
        if analytic_context is None:
            analytic_context = _r10_27_authenticated_analytic_context(
                roles_bi,
            )
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
        analytic_principal = _r10_27_authenticated_analytic_principal()
        if analytic_principal is not None:
            with ENTERPRISE_COMPONENTS.analytics.bind(analytic_principal, roles_bi):
                dynamic_plan = _prepare_governed_deliverable_plan(original, prompt, path, meta.get("hoja_analizada") or "", semantic_context, prompt_sha256, prompt_preview)
        else:
            dynamic_plan = _prepare_governed_deliverable_plan(original, prompt, path, meta.get("hoja_analizada") or "", semantic_context, prompt_sha256, prompt_preview)
        profile["dynamic_dashboard_plan"] = dynamic_plan
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256, _source_fingerprint_from_meta(meta), spec.get("output_intent"))
        if spec["outputs"].get("html"):
            html_path = base.REPORTES / f"Dashboard_Dinamico_{stem}_{stamp}.html"
            if analytic_principal is not None:
                with ENTERPRISE_COMPONENTS.analytics.bind(analytic_principal, roles_bi):
                    dynamic_plan = dd.generate_dynamic_dashboard(html_path, original, prompt, path.name, meta.get("hoja_analizada") or "", semantic_context, prepared_plan=dynamic_plan)
            else:
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
        _attach_governed_deliverable_manifest(profile, dynamic_plan, path, meta.get("hoja_analizada") or "", len(original), prompt_sha256, _source_fingerprint_from_meta(meta), spec.get("output_intent"))
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

    auth_actor = (
        base.ANALYZE_AUTH_CONTEXT.get()
        if hasattr(base, "ANALYZE_AUTH_CONTEXT")
        else None
    )

    analysis_scope = (
        _authenticated_content_scope(auth_actor)
        if isinstance(auth_actor, dict)
        else _local_deliverable_scope()
    )

    # Registra el archivo tabular para consultas deterministicas futuras del ContextEngine.
    if register_dataset:
        try:
            if ENTERPRISE_COMPONENTS is not None:
                if isinstance(auth_actor, dict):
                    principal = Principal(
                        str(auth_actor["tenant_id"]),
                        str(auth_actor["user_id"]),
                        (
                            "admin"
                            if "SYSTEM_ADMIN" in set(auth_actor.get("roles") or [])
                            else "user"
                        ),
                    )
                else:
                    sec = ENTERPRISE_COMPONENTS.cfg.section("security")
                    principal = Principal(
                        sec.get("default_company", "empresa-local"),
                        sec.get("default_user", "admin-local"),
                        "admin",
                    )

                ENTERPRISE_COMPONENTS.datasets.register(
                    principal,
                    path,
                    name=path.name,
                    scope="company",
                    roles=roles,
                )
        except Exception as _dataset_exc:
            notes.append(f"V8: no se pudo registrar el dataset para consultas futuras: {_dataset_exc}")
    deliverable_run = _register_governed_deliverables(
        profile=profile,
        outputs=outputs,
        domain=domain,
        scope=analysis_scope,
    )
    response = {
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
        "deliverable_run": deliverable_run,
        "segundos": round(base.time.time() - started, 2),
    }
    return response


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
base.app.version = PRODUCT_VERSION

# Actualiza textos de la interfaz sin duplicar todo el HTML de V3.
base.INDEX_HTML = base.INDEX_HTML.replace(
    "Analizador Empresarial de Excel / CSV",
    f"Analizador Universal Empresarial de Excel / CSV - V{PRODUCT_VERSION} {RELEASE_ID.upper()} · Dashboard Dinámico IA",
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
    f"<title>IA Empresarial Local - V{PRODUCT_VERSION} {RELEASE_ID.upper()} · Dashboard Dinámico IA</title>",
).replace(
    "<h1>Analizador Universal Empresarial de Excel / CSV</h1>",
    f"<h1>Analizador Universal Empresarial de Excel / CSV <span style=\"font-size:14px;background:#dbeafe;color:#1d4ed8;padding:4px 8px;border-radius:999px;vertical-align:middle\">V{PRODUCT_VERSION} {RELEASE_ID.upper()}</span></h1>",
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

# ---------------------------------------------------------------------------
# R10.19A - Consultable Enterprise Agent UI
# ---------------------------------------------------------------------------

_qa_panel_old = (
    '<div id="status"></div>'
    '<div id="out" class="result" style="display:none"></div>'
    '<div id="links" class="links"></div>'
)

_qa_panel_new = (
    '<div id="status"></div>'
    '<div id="out" class="result" style="display:none"></div>'
    '<div id="links" class="links"></div>'
    '<div id="enterpriseAsk" '
    'style="margin-top:24px;padding:20px;border:1px solid #dbe2ea;'
    'border-radius:14px;background:#f8fafc">'
    '<h2 style="margin:0 0 6px;font-size:20px">'
    'Preg\u00fantale a tu an\u00e1lisis'
    '</h2>'
    '<div style="font-size:13px;color:#64748b;margin-bottom:12px">'
    'Consulta m\u00e9tricas, cobertura, bloqueos y entregables del an\u00e1lisis '
    'gobernado. Las respuestas no inventan c\u00e1lculos ni f\u00f3rmulas.'
    '</div>'
    '<div style="display:flex;gap:8px;flex-wrap:wrap">'
    '<input id="enterpriseQuestion" type="text" '
    'placeholder="Ej. \u00bfCu\u00e1l fue la cobertura del an\u00e1lisis?" '
    'style="flex:1;min-width:260px;box-sizing:border-box;'
    'border:1px solid #cbd5e1;border-radius:10px;padding:12px">'
    '<button type="button" class="btn" id="enterpriseAskButton">'
    'Preguntar'
    '</button>'
    '</div>'
    '<div id="enterpriseAskStatus"></div>'
    '<div id="enterpriseAskAnswer" class="result" '
    'style="display:none;margin-top:12px"></div>'
    '</div>'
)

if _qa_panel_old not in base.INDEX_HTML:
    raise RuntimeError(
        "R10.19A_UI_ANCHOR_NOT_FOUND: "
        "no se encontr\u00f3 el bloque status/out/links"
    )

base.INDEX_HTML = base.INDEX_HTML.replace(
    _qa_panel_old,
    _qa_panel_new,
    1,
)

_qa_script_marker = '</script></body></html>'

_qa_script = r'''
// R10.19A Consultable Enterprise Agent
window.__enterpriseRunId = window.__enterpriseRunId || null;

const enterpriseAskButton =
    document.getElementById('enterpriseAskButton');

const enterpriseQuestion =
    document.getElementById('enterpriseQuestion');

const enterpriseAskAnswer =
    document.getElementById('enterpriseAskAnswer');

const enterpriseAskStatus =
    document.getElementById('enterpriseAskStatus');

function enterpriseFormatAnswer(result){
    const status=String(result?.status||'UNRESOLVED');
    const answer=result?.answer;
    const reason=result?.reason||'';

    if(status==='BLOCKED'){
        return [
            'ESTADO: BLOQUEADO',
            '',
            'La m\u00e9trica o an\u00e1lisis solicitado no puede calcularse',
            'con las reglas y datos gobernados actuales.',
            '',
            reason ? ('Motivo: '+reason) : ''
        ].join('\n');
    }

    if(status==='UNRESOLVED'){
        return [
            'ESTADO: NO RESUELTO',
            '',
            'La pregunta todav\u00eda no est\u00e1 soportada por el',
            'agente empresarial gobernado.',
            '',
            reason ? ('Motivo: '+reason) : ''
        ].join('\n');
    }

    if(status!=='ANSWERED'){
        return (
            'ESTADO: '+status+
            '\n\n'+JSON.stringify(result,null,2)
        );
    }

    if(answer && typeof answer==='object'){

        if(
            Object.prototype.hasOwnProperty.call(answer,'percent') &&
            Object.prototype.hasOwnProperty.call(answer,'fulfilled')
        ){
            return [
                'Cobertura del an\u00e1lisis: '+answer.percent+'%',
                '',
                'Solicitado: '+answer.requested,
                'Soportado: '+answer.supported,
                'Derivable: '+answer.derivable,
                'Cumplido: '+answer.fulfilled,
                'Bloqueado: '+answer.blocked
            ].join('\n');
        }

        if(Array.isArray(answer)){
            if(!answer.length){
                return 'No existen elementos para mostrar.';
            }

            return answer.map((item,index)=>{
                if(item && typeof item==='object'){
                    const id=
                        item.id ||
                        item.component_id ||
                        ('Elemento '+(index+1));

                    const why=
                        item.reason
                        ? (' \u2022 '+item.reason)
                        : '';

                    return '\u2022 '+id+why;
                }

                return '\u2022 '+String(item);
            }).join('\n');
        }

        if(Array.isArray(answer.formats)){
            return (
                'Formatos generados: '+
                answer.formats.join(', ')
            );
        }

        if(
            Object.prototype.hasOwnProperty.call(
                answer,
                'value'
            )
        ){
            return 'Resultado: '+String(answer.value);
        }

        return JSON.stringify(answer,null,2);
    }

    return String(
        answer ?? 'Sin valor disponible.'
    );
}

async function enterpriseAsk(){
    const question=
        (enterpriseQuestion.value||'').trim();

    if(!question){
        enterpriseAskStatus.innerHTML=
            '<div class="note">Escribe una pregunta.</div>';
        return;
    }

    enterpriseAskButton.disabled=true;

    enterpriseAskAnswer.style.display='block';
    enterpriseAskAnswer.textContent=
        'Consultando an\u00e1lisis gobernado...';

    enterpriseAskStatus.innerHTML='';

    try{
        const body={question};

        if(window.__enterpriseRunId){
            body.run_id=
                window.__enterpriseRunId;
        }

        const sessionToken=
            window.__IA_ANALYZE_TOKEN__ ||
            sessionStorage.getItem(
                'iaEnterpriseSession'
            ) ||
            '';

        if(!sessionToken){
            throw new Error(
                'Sesión empresarial requerida.'
            );
        }

        const response=
            await fetch('/api/ask',{
                method:'POST',
                headers:{
                    'Content-Type':
                        'application/json; charset=utf-8',
                    'Authorization':
                        'Bearer '+sessionToken
                },
                body:JSON.stringify(body)
            });

        const data=await response.json();

        if(!response.ok){
            const detail=data?.detail;

            const message=
                detail?.message ||
                detail?.code ||
                (
                    typeof detail==='string'
                    ? detail
                    : null
                ) ||
                'Error al consultar el an\u00e1lisis.';

            throw new Error(message);
        }

        const result=data.result||{};

        window.__enterpriseRunId=
            data.run_id ||
            window.__enterpriseRunId;

        enterpriseAskAnswer.textContent=
            enterpriseFormatAnswer(result);

        const status=
            String(result.status||'');

        if(status==='ANSWERED'){
            enterpriseAskStatus.innerHTML=
                '<div class="note ok">'+
                'Respuesta gobernada \u2022 '+
                String(data.run_id||'')+
                '</div>';

        }else if(status==='BLOCKED'){

            enterpriseAskStatus.innerHTML=
                '<div class="note">'+
                'Solicitud bloqueada por gobernanza.'+
                '</div>';

        }else{

            enterpriseAskStatus.innerHTML=
                '<div class="note">'+
                'Pregunta no resuelta sin inventar respuesta.'+
                '</div>';
        }

    }catch(err){

        enterpriseAskAnswer.textContent=
            'ERROR: '+err.message;

        enterpriseAskStatus.innerHTML=
            '<div class="note">'+
            'No fue posible consultar el an\u00e1lisis.'+
            '</div>';

    }finally{
        enterpriseAskButton.disabled=false;
    }
}

if(enterpriseAskButton){
    enterpriseAskButton.addEventListener(
        'click',
        enterpriseAsk
    );
}

if(enterpriseQuestion){
    enterpriseQuestion.addEventListener(
        'keydown',
        event=>{
            if(event.key==='Enter'){
                event.preventDefault();
                enterpriseAsk();
            }
        }
    );
}
'''

if _qa_script_marker not in base.INDEX_HTML:
    raise RuntimeError(
        "R10.19A_SCRIPT_ANCHOR_NOT_FOUND"
    )

base.INDEX_HTML = base.INDEX_HTML.replace(
    _qa_script_marker,
    _qa_script + _qa_script_marker,
    1,
)



# ---------------------------------------------------------------------------
# R10.22 RC commercial analyzer authentication UX
# ---------------------------------------------------------------------------

_ANALYZE_LOGIN_GATE = r"""
<div id="ia-analyze-auth"
     style="position:fixed;inset:0;z-index:99999;background:#f4f7fb;
            display:flex;align-items:center;justify-content:center;padding:20px;overflow:hidden">
  <div style="width:min(760px,100%);max-height:calc(100vh - 40px);box-sizing:border-box;overflow:auto;background:#fff;border:1px solid #dbe4ef;border-radius:20px;padding:26px;
              box-shadow:0 24px 70px rgba(15,23,42,.16);color:#0f172a">

    <div id="ia-first-run-panel" style="display:none">
      <style>
        #ia-first-run-panel{font-family:Inter,Segoe UI,Arial,sans-serif}
        #ia-first-run-panel *{box-sizing:border-box}
        #ia-login-panel{max-width:470px;margin:0 auto}
        .ia-setup-kicker{font-size:13px;color:#2563eb;font-weight:800;margin-bottom:6px}
        .ia-setup-title{margin:0 0 8px;font-size:27px;line-height:1.15;color:#0f172a}
        .ia-setup-copy{margin:0 0 18px;color:#475569;line-height:1.5}
        .ia-setup-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 22px}
        .ia-setup-step{min-height:44px;border:1px solid #dbe4ef;border-radius:12px;padding:9px 10px;background:#f8fafc;color:#64748b;font-size:12px;font-weight:700;display:flex;align-items:center;gap:7px}
        .ia-setup-step strong{width:24px;height:24px;border-radius:999px;background:#e2e8f0;color:#334155;display:grid;place-items:center;flex:0 0 24px}
        .ia-setup-step.active{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8}
        .ia-setup-step.active strong{background:#2563eb;color:white}
        .ia-setup-section{border:1px solid #e2e8f0;border-radius:15px;padding:16px;margin:0 0 14px;background:#fff}
        .ia-setup-section h3{margin:0 0 4px;color:#0f172a;font-size:16px}
        .ia-setup-section p{margin:0 0 14px;color:#64748b;font-size:13px;line-height:1.45}
        .ia-setup-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 14px}
        .ia-setup-field label{display:block;color:#334155;font-size:13px;font-weight:700;margin-bottom:6px}
        .ia-setup-field input,.ia-setup-field select{width:100%;min-height:46px;border:1px solid #cbd5e1;border-radius:10px;padding:10px 11px;background:#fff;color:#0f172a;font:inherit}
        .ia-setup-field input[type="color"]{padding:5px;cursor:pointer}
        .ia-setup-field input:focus,.ia-setup-field select:focus{outline:3px solid #dbeafe;border-color:#60a5fa}
        .ia-setup-span-2{grid-column:1/-1}
        .ia-setup-actions{display:flex;justify-content:flex-end;margin-top:16px}
        .ia-setup-actions button{min-height:46px;border:0;border-radius:11px;padding:0 20px;background:#2563eb;color:#fff;font-weight:800;cursor:pointer}
        .ia-setup-actions button:disabled{opacity:.6;cursor:wait}
        #ia-setup-status{min-height:20px;margin-top:12px;font-size:13px;color:#b91c1c}
        .ia-setup-security{margin-top:14px;padding:11px 12px;border-radius:10px;background:#f8fafc;color:#64748b;font-size:12px;line-height:1.5}
        @media(max-width:640px){
          .ia-setup-title{font-size:23px}
          .ia-setup-steps{grid-template-columns:repeat(2,minmax(0,1fr))}
          .ia-setup-grid{grid-template-columns:1fr}
          .ia-setup-span-2{grid-column:auto}
          .ia-setup-actions button{width:100%}
        }
      </style>

      <div class="ia-setup-kicker">Primera configuración · Paso 1 de 4</div>
      <h2 class="ia-setup-title">Configura tu empresa</h2>
      <p class="ia-setup-copy">
        Prepara la identidad de tu empresa y crea la cuenta administradora.
        Después podrás conectar tus datos y elegir la inteligencia artificial.
      </p>

      <div class="ia-setup-steps" aria-label="Progreso de configuración">
        <div class="ia-setup-step active" aria-current="step"><strong>1</strong><span>Empresa</span></div>
        <div class="ia-setup-step"><strong>2</strong><span>Datos</span></div>
        <div class="ia-setup-step"><strong>3</strong><span>IA</span></div>
        <div class="ia-setup-step"><strong>4</strong><span>Listo</span></div>
      </div>

      <section class="ia-setup-section">
        <h3>Identidad de la empresa</h3>
        <p>Estos datos personalizan la experiencia desde el primer acceso.</p>
        <div class="ia-setup-grid">
          <div class="ia-setup-field ia-setup-span-2">
            <label for="ia-setup-company">Nombre de la empresa</label>
            <input id="ia-setup-company" autocomplete="organization" placeholder="Mi Empresa">
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-business-type">Tipo de empresa</label>
            <select id="ia-setup-business-type">
              <option value="Comercial">Comercial</option>
              <option value="Distribución">Distribución</option>
              <option value="Servicios">Servicios</option>
              <option value="Manufactura">Manufactura</option>
              <option value="Logística">Logística</option>
              <option value="Agropecuario">Agropecuario</option>
              <option value="Otro" selected>Otro</option>
            </select>
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-theme">Tema visual</label>
            <select id="ia-setup-theme">
              <option value="professional-light" selected>Claro</option>
              <option value="professional-dark">Oscuro</option>
            </select>
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-accent">Color principal</label>
            <input id="ia-setup-accent" type="color" value="#1d67d2">
          </div>
        </div>
      </section>

      <section class="ia-setup-section">
        <h3>Cuenta administradora</h3>
        <p>Usarás esta cuenta para administrar la configuración inicial.</p>
        <div class="ia-setup-grid">
          <div class="ia-setup-field">
            <label for="ia-setup-display">Tu nombre</label>
            <input id="ia-setup-display" autocomplete="name" placeholder="Administrador">
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-user">Usuario administrador</label>
            <input id="ia-setup-user" autocomplete="username" placeholder="admin">
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-password">Contraseña</label>
            <input id="ia-setup-password" type="password" autocomplete="new-password" placeholder="Mínimo 12 caracteres">
          </div>
          <div class="ia-setup-field">
            <label for="ia-setup-confirm">Confirmar contraseña</label>
            <input id="ia-setup-confirm" type="password" autocomplete="new-password">
          </div>
        </div>
      </section>

      <div class="ia-setup-actions">
        <button id="ia-setup-submit" type="button">Crear empresa y continuar</button>
      </div>

      <div id="ia-setup-status" role="status" aria-live="polite"></div>

      <div class="ia-setup-security">
        La configuración inicial sólo está disponible desde este equipo
        y se desactiva automáticamente después de crear el administrador.
      </div>
    </div>
    <div id="ia-login-panel">
      <h2 style="margin:0 0 8px">Acceso a IA Empresarial Local</h2>
      <p style="margin:0 0 16px;color:#475569">
        Inicia sesión para ejecutar análisis empresariales.
      </p>

      <label>Usuario</label>
      <input id="ia-auth-user"
             autocomplete="username"
             style="width:100%;box-sizing:border-box;padding:10px;margin:5px 0 12px">

      <label>Contraseña</label>
      <input id="ia-auth-password"
             type="password"
             autocomplete="current-password"
             style="width:100%;box-sizing:border-box;padding:10px;margin:5px 0 12px">

      <button id="ia-auth-login"
              type="button"
              style="width:100%;padding:11px;font-weight:700;cursor:pointer">
        Iniciar sesión
      </button>

      <div id="ia-auth-status"
           style="margin-top:10px;font-size:13px;color:#b91c1c"></div>
    </div>
  </div>
</div>
"""

_ANALYZE_LOGIN_SCRIPT = r"""
<script>
window.__IA_ANALYZE_TOKEN__ = '';

(function(){
  const gate =
    document.getElementById('ia-analyze-auth');

  const loginPanel =
    document.getElementById('ia-login-panel');

  const user =
    document.getElementById('ia-auth-user');

  const pass =
    document.getElementById('ia-auth-password');

  const button =
    document.getElementById('ia-auth-login');

  const status =
    document.getElementById('ia-auth-status');

  const setupPanel =
    document.getElementById('ia-first-run-panel');

  const setupCompany =
    document.getElementById('ia-setup-company');

  const setupDisplay =
    document.getElementById('ia-setup-display');

  const setupUser =
    document.getElementById('ia-setup-user');

  const setupPassword =
    document.getElementById('ia-setup-password');

  const setupConfirm =
    document.getElementById('ia-setup-confirm');

  const setupButton =
    document.getElementById('ia-setup-submit');

  const setupStatus =
    document.getElementById('ia-setup-status');

  let bootstrapNonce = '';

  function lockPageScroll(){
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
  }

  function unlockPageScroll(){
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
  }

  lockPageScroll();


  function showLogin(){
    lockPageScroll();
    setupPanel.style.display = 'none';
    loginPanel.style.display = '';
  }


  function showFirstRun(data){
    bootstrapNonce =
      String(data.bootstrap_nonce || '');

    lockPageScroll();
    loginPanel.style.display = 'none';
    setupPanel.style.display = '';
  }


  async function detectFirstRun(){
    try{
      const response = await fetch(
        '/api/onboarding/status',
        {
          method:'GET',
          cache:'no-store'
        }
      );

      if(!response.ok){
        showLogin();
        return;
      }

      const data = await response.json();

      if(
        data.status === 'FIRST_RUN'
        && data.bootstrap_available
        && data.bootstrap_nonce
      ){
        showFirstRun(data);
        return;
      }
    }
    catch(error){
      // Remote/non-local access intentionally falls back to login.
    }

    showLogin();
  }


  async function bootstrap(){
    setupStatus.textContent = '';

    const setupBusinessType =
      document.getElementById('ia-setup-business-type');

    const setupAccent =
      document.getElementById('ia-setup-accent');

    const setupTheme =
      document.getElementById('ia-setup-theme');

    if(
      !setupCompany.value.trim()
      || !setupUser.value.trim()
      || !setupPassword.value
    ){
      setupStatus.textContent =
        'Completa empresa, usuario y contraseña.';
      return;
    }

    if(setupPassword.value.length < 12){
      setupStatus.textContent =
        'La contraseña debe tener al menos 12 caracteres.';
      return;
    }

    if(setupPassword.value !== setupConfirm.value){
      setupStatus.textContent =
        'Las contraseñas no coinciden.';
      return;
    }

    setupButton.disabled = true;
    setupButton.textContent = 'Creando empresa...';

    try{
      const response = await fetch(
        '/api/onboarding/bootstrap',
        {
          method:'POST',
          headers:{
            'Content-Type':'application/json',
            'X-IA-Bootstrap-Nonce':bootstrapNonce
          },
          body:JSON.stringify({
            company_name:
              setupCompany.value.trim(),
            business_type:
              setupBusinessType.value,
            accent_color:
              setupAccent.value,
            theme:
              setupTheme.value,
            admin_display_name:
              setupDisplay.value.trim(),
            admin_username:
              setupUser.value.trim(),
            password:
              setupPassword.value,
            password_confirmation:
              setupConfirm.value
          })
        }
      );

      let data = {};

      try{
        data = await response.json();
      }
      catch(error){}

      if(!response.ok || !data.token){
        const detail = data.detail || {};

        throw new Error(
          detail.message
          || detail.code
          || 'No se pudo completar la configuración inicial.'
        );
      }

      setupPassword.value = '';
      setupConfirm.value = '';
      bootstrapNonce = '';

      sessionStorage.setItem(
        'iaEnterpriseSession',
        String(data.token)
      );

      window.location.assign(
        data.next || '/settings?setup=data'
      );
    }
    catch(error){
      setupPassword.value = '';
      setupConfirm.value = '';

      setupStatus.textContent =
        String(
          error.message
          || error
        );
    }
    finally{
      setupButton.disabled = false;
      setupButton.textContent = 'Crear empresa y continuar';
    }
  }

  async function login(){
    status.textContent = '';
    button.disabled = true;

    try{
      const response = await fetch(
        '/api/auth/login',
        {
          method:'POST',
          headers:{
            'Content-Type':'application/json'
          },
          body:JSON.stringify({
            username:
              (user.value || '').trim(),
            password:
              pass.value || ''
          })
        }
      );

      const data =
        await response.json();

      if(
        !response.ok
        || !data.token
      ){
        window.__IA_ANALYZE_TOKEN__ = '';

        throw new Error(
          (
            data.detail
            && (
              data.detail.message
              || data.detail.code
            )
          )
          || 'Credenciales inválidas'
        );
      }

      // Analyzer token stays memory-only.
      window.__IA_ANALYZE_TOKEN__ =
        String(data.token);

      pass.value = '';
      gate.style.display = 'none';
      unlockPageScroll();
    }
    catch(error){
      window.__IA_ANALYZE_TOKEN__ = '';
      pass.value = '';

      status.textContent =
        String(
          error.message
          || error
        );
    }
    finally{
      button.disabled = false;
    }
  }


  button.addEventListener(
    'click',
    login
  );

  pass.addEventListener(
    'keydown',
    function(event){
      if(event.key === 'Enter'){
        login();
      }
    }
  );

  setupButton.addEventListener(
    'click',
    bootstrap
  );

  setupConfirm.addEventListener(
    'keydown',
    function(event){
      if(event.key === 'Enter'){
        bootstrap();
      }
    }
  );

  detectFirstRun();
})();
</script>
"""

if 'id="ia-analyze-auth"' not in base.INDEX_HTML:
    if "<body>" not in base.INDEX_HTML or "</body>" not in base.INDEX_HTML:
        raise RuntimeError("ANALYZER_HTML_BODY_NOT_FOUND")

    base.INDEX_HTML = base.INDEX_HTML.replace(
        "<body>",
        "<body>" + _ANALYZE_LOGIN_GATE,
        1,
    )

    base.INDEX_HTML = base.INDEX_HTML.replace(
        "</body>",
        _ANALYZE_LOGIN_SCRIPT + "</body>",
        1,
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
    return {"prompt_integrity": "r10.13c.2-request-authority", "version": PRODUCT_VERSION, "release": RELEASE_ID, "channel": RELEASE_CHANNEL, "motor": "universal-profesional-memoria-rag", "script": "analizador_universal.py", "reportes": "dashboard HTML dinámico por prompt + PDF BI + Excel analitico", "enterprise_ai": "memoria persistente + RAG + datos estructurados + ContextEngine", "controles": "prompt authority + data contract + calculo deterministico + semantic mapper + aislamiento empresa/usuario"}

# V8: integra memoria persistente, RAG, seguridad y ContextEngine sin reemplazar el analizador V7.
try:
    from enterprise_ai.api import install_enterprise_routes
    from enterprise_ai.security import Principal
    ENTERPRISE_COMPONENTS = install_enterprise_routes(base.app, base.ROOT)
except Exception as _enterprise_exc:
    ENTERPRISE_COMPONENTS = None
    print(f"ADVERTENCIA V8: capa enterprise_ai no pudo inicializarse: {_enterprise_exc}")

app = base.app

# R10.20B.1: the default is explicitly fail-closed until the local host wires
# a real admin authority in the following phase.
_tenant_admin_guard = lambda: False


def configure_tenant_admin_guard(guard) -> None:
    global _tenant_admin_guard
    _tenant_admin_guard = guard if callable(guard) else (lambda: False)


def _tenant_registry() -> EnterpriseTenantRegistry:
    return EnterpriseTenantRegistry(base.REPORTES / ".tenants")

def _identity_store() -> EnterpriseIdentityStore:
    return EnterpriseIdentityStore(base.REPORTES / ".identity", _tenant_registry())

def _platform_config() -> EnterprisePlatformConfigStore:
    return EnterprisePlatformConfigStore(base.REPORTES / ".platform_config", _tenant_registry())

def _auth_error(exc: IdentityError):
    status=401 if exc.code.startswith("AUTH_") or exc.code=="USER_DISABLED" else (404 if exc.code=="USER_NOT_FOUND" else (409 if exc.code=="USER_ALREADY_EXISTS" else 403))
    raise base.HTTPException(status_code=status,detail={"code":exc.code,"message":str(exc)}) from exc

def _bearer(authorization: str):
    if not str(authorization or "").startswith("Bearer "): raise base.HTTPException(status_code=401,detail={"code":"AUTH_REQUIRED","message":"Autenticación requerida"})
    try:return _identity_store().authenticate(str(authorization)[7:])
    except IdentityError as exc:_auth_error(exc)
    except TenantRegistryError as exc:
        raise base.HTTPException(status_code=401,detail={"code":"AUTH_SESSION_INVALID","message":"Sesi?n inv?lida"}) from exc


def _authorize_analysis(authorization: str) -> Dict[str, Any]:
    """
    Commercial analysis authorization.

    A valid enterprise session and the existing analysis:run
    permission are mandatory before an uploaded file may be stored.
    """
    actor = _bearer(authorization)
    store = _identity_store()

    if not store.has_permission(actor, "analysis:run"):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code": "ANALYSIS_PERMISSION_DENIED",
                "message": "Permiso de análisis denegado",
            },
        )

    return actor

def _require_actor_permission(
    actor: Dict[str, Any],
    permission: str,
    *,
    code: str = "PERMISSION_DENIED",
    message: str = "Permiso denegado",
) -> Dict[str, Any]:
    if not _identity_store().has_permission(
        actor,
        permission,
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code": code,
                "message": message,
            },
        )

    return actor


def _actor_with_permission(
    authorization: str,
    permission: str,
    *,
    code: str = "PERMISSION_DENIED",
    message: str = "Permiso denegado",
) -> Dict[str, Any]:
    actor = _bearer(
        authorization
    )

    return _require_actor_permission(
        actor,
        permission,
        code=code,
        message=message,
    )


def _authenticated_content_scope(
    actor: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    try:
        return _identity_store().scope(
            actor
        )

    except IdentityError as exc:
        _auth_error(
            exc
        )

    raise AssertionError(
        "unreachable"
    )



@app.post("/api/enterprise/datasets/{dataset_id}/analyze")
def analyze_registered_enterprise_dataset(
    dataset_id: str,
    payload: Dict[str, Any],
    authorization: str = Header(""),
) -> Dict[str, Any]:
    """Generate governed deliverables from an already registered dataset."""
    actor = _authorize_analysis(authorization)

    _require_actor_permission(
        actor,
        "deliverable:read",
        code="DATASET_READ_PERMISSION_DENIED",
        message="Permiso para consultar datasets requerido",
    )

    if ENTERPRISE_COMPONENTS is None:
        raise base.HTTPException(
            status_code=503,
            detail={
                "code": "ENTERPRISE_COMPONENTS_UNAVAILABLE",
                "message": "La capa empresarial no está disponible.",
            },
        )

    requested_id = str(dataset_id or "").strip()
    request_prompt = str(
        (payload or {}).get("prompt") or ""
    ).strip()

    if not request_prompt:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": "PROMPT_REQUIRED",
                "message": "La solicitud de análisis es obligatoria.",
            },
        )

    principal = Principal(
        str(actor["tenant_id"]),
        str(actor["user_id"]),
        (
            "admin"
            if "SYSTEM_ADMIN" in set(actor.get("roles") or [])
            else "user"
        ),
    )

    dataset = next(
        (
            item
            for item in ENTERPRISE_COMPONENTS.datasets.list(principal)
            if str(item.get("id") or "") == requested_id
        ),
        None,
    )

    if dataset is None:
        raise base.HTTPException(
            status_code=404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": "Dataset no encontrado.",
            },
        )

    raw_path = str(dataset.get("path") or "").strip()

    if not raw_path:
        raise base.HTTPException(
            status_code=404,
            detail={
                "code": "DATASET_SOURCE_NOT_FOUND",
                "message": "La fuente del dataset no está disponible.",
            },
        )

    source_path = Path(raw_path).resolve()
    workspace_root = base.WORKSPACE.resolve()

    if (
        not source_path.is_file()
        or (
            source_path != workspace_root
            and workspace_root not in source_path.parents
        )
    ):
        raise base.HTTPException(
            status_code=404,
            detail={
                "code": "DATASET_SOURCE_NOT_FOUND",
                "message": "La fuente del dataset no está disponible.",
            },
        )

    if source_path.suffix.lower() not in {
        ".csv",
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
    }:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": "DATASET_FORMAT_UNSUPPORTED",
                "message": "El dataset no tiene un formato analizable.",
            },
        )

    auth_context_token = base.ANALYZE_AUTH_CONTEXT.set(actor)

    try:
        result = analyze_file(
            source_path,
            request_prompt,
            register_dataset=False,
        )
    finally:
        base.ANALYZE_AUTH_CONTEXT.reset(auth_context_token)

    if isinstance(result, dict):
        result["dataset_id"] = requested_id
        result["dataset_name"] = str(dataset.get("name") or "")

    return result


# analizador_app owns /api/analyze; the universal commercial runtime
# supplies its enterprise identity/permission guard at module startup.
base.ANALYZE_AUTHORIZER = _authorize_analysis



# ---------------------------------------------------------------------------
# GA.3-B1: secure guided first-run web bootstrap.
#
# This is deliberately NOT a general unauthenticated administration API.
# It is available only while the canonical onboarding state is FIRST_RUN,
# only to loopback clients using a local Host header, and only with an
# ephemeral process-local nonce obtained by the same local browser session.
# ---------------------------------------------------------------------------

_BOOTSTRAP_LOCK = threading.Lock()
_BOOTSTRAP_NONCE = uuid.uuid4().hex


def _bootstrap_client_is_loopback(value: str) -> bool:
    host = str(value or "").strip().lower()

    if not host:
        return False

    try:
        return bool(
            ipaddress.ip_address(
                host
            ).is_loopback
        )
    except ValueError:
        return False


def _bootstrap_host_is_local(value: str) -> bool:
    host = (
        str(value or "")
        .strip()
        .lower()
        .strip("[]")
    )

    if host == "localhost":
        return True

    try:
        return bool(
            ipaddress.ip_address(
                host
            ).is_loopback
        )
    except ValueError:
        return False


def _require_local_bootstrap(
    request: Request,
) -> None:
    client_host = (
        request.client.host
        if request.client
        else ""
    )

    request_host = (
        request.url.hostname
        or ""
    )

    if (
        not _bootstrap_client_is_loopback(
            client_host
        )
        or not _bootstrap_host_is_local(
            request_host
        )
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "BOOTSTRAP_LOCAL_ONLY",
                "message":
                    "La configuración inicial "
                    "sólo puede realizarse "
                    "desde este equipo.",
            },
        )


def _bootstrap_identifier(
    value: str,
    fallback: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    normalized = (
        normalized
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
        .lower()
    )

    result = []

    separator = False

    for char in normalized:
        if (
            char.isalnum()
            or char in "._-"
        ):
            result.append(char)
            separator = False
        elif not separator:
            result.append("-")
            separator = True

    identifier = (
        "".join(result)
        .strip("._-")
    )

    if not identifier:
        identifier = fallback

    return identifier[:80]


def _bootstrap_public_status() -> Dict[str, Any]:
    state = EnterpriseOnboarding(
        base.REPORTES
    ).status()

    first_run = (
        state.get("status")
        == "FIRST_RUN"
    )

    return {
        "status":
            state.get(
                "status",
                "INVALID_CONFIGURATION",
            ),
        "bootstrap_available":
            first_run,
        "password_min_length":
            12,
        "bootstrap_nonce":
            (
                _BOOTSTRAP_NONCE
                if first_run
                else None
            ),
    }


@app.get("/api/onboarding/status")
def onboarding_web_status(
    request: Request,
) -> Dict[str, Any]:
    _require_local_bootstrap(
        request
    )

    return _bootstrap_public_status()


@app.post("/api/onboarding/bootstrap")
def onboarding_web_bootstrap(
    payload: Dict[str, Any],
    request: Request,
    bootstrap_nonce: str = Header(
        "",
        alias="X-IA-Bootstrap-Nonce",
    ),
) -> Dict[str, Any]:
    global _BOOTSTRAP_NONCE

    _require_local_bootstrap(
        request
    )

    supplied_nonce = str(
        bootstrap_nonce
        or ""
    ).strip()

    if (
        not supplied_nonce
        or supplied_nonce
        != _BOOTSTRAP_NONCE
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "BOOTSTRAP_NONCE_INVALID",
                "message":
                    "La sesión de configuración "
                    "inicial no es válida. "
                    "Actualiza la página.",
            },
        )

    company_name = str(
        payload.get("company_name")
        or ""
    ).strip()

    raw_username = str(
        payload.get("admin_username")
        or ""
    ).strip()

    admin_display_name = str(
        payload.get("admin_display_name")
        or ""
    ).strip()

    business_type = str(
        payload.get("business_type")
        or "Otro"
    ).strip()

    accent_color = str(
        payload.get("accent_color")
        or "#1d67d2"
    ).strip()

    theme = str(
        payload.get("theme")
        or "professional-light"
    ).strip()

    password = payload.get(
        "password"
    )

    confirmation = payload.get(
        "password_confirmation"
    )

    if (
        not company_name
        or len(company_name) > 120
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "COMPANY_NAME_INVALID",
                "message":
                    "Escribe el nombre de tu empresa.",
            },
        )

    if not raw_username:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "ADMIN_USERNAME_REQUIRED",
                "message":
                    "Escribe el usuario administrador.",
            },
        )

    if (
        not isinstance(
            password,
            str,
        )
        or password
        != confirmation
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "PASSWORD_CONFIRMATION_MISMATCH",
                "message":
                    "Las contraseñas no coinciden.",
            },
        )

    tenant_id = _bootstrap_identifier(
        company_name,
        "empresa",
    )

    login_username = _bootstrap_identifier(
        raw_username,
        "admin",
    )

    display_name = (
        admin_display_name
        or "Administrador"
    )

    with _BOOTSTRAP_LOCK:
        onboarding = EnterpriseOnboarding(
            base.REPORTES
        )

        state = onboarding.status()

        if (
            state.get("status")
            != "FIRST_RUN"
        ):
            raise base.HTTPException(
                status_code=409,
                detail={
                    "code":
                        "BOOTSTRAP_ALREADY_COMPLETE",
                    "message":
                        "La configuración inicial "
                        "ya fue completada.",
                },
            )

        try:
            onboarding.configure(
                tenant_id=tenant_id,
                tenant_name=company_name,
                admin_user_id=login_username,
                admin_username=login_username,
                admin_display_name=display_name,
                password=password,
                business_type=business_type,
                accent_color=accent_color,
                theme=theme,
            )
        except OnboardingError as exc:
            status_code = (
                409
                if exc.code
                == "CONFIGURATION_CONFLICT"
                else 400
            )

            message = {
                "PASSWORD_INVALID":
                    "La contraseña debe tener "
                    "al menos 12 caracteres.",
                "CONFIGURATION_CONFLICT":
                    "La configuración inicial "
                    "entra en conflicto con "
                    "datos existentes.",
                "USER_INVALID_ID":
                    "El usuario administrador "
                    "no es válido.",
                "CONFIG_INVALID":
                    "Revisa el tipo de empresa "
                    "y la apariencia seleccionada.",
            }.get(
                exc.code,
                "No se pudo completar "
                "la configuración inicial.",
            )

            raise base.HTTPException(
                status_code=status_code,
                detail={
                    "code": exc.code,
                    "message": message,
                },
            ) from exc

        try:
            token, user = (
                _identity_store().login(
                    login_username,
                    password,
                )
            )
        except IdentityError as exc:
            raise base.HTTPException(
                status_code=500,
                detail={
                    "code":
                        "BOOTSTRAP_LOGIN_FAILED",
                    "message":
                        "La empresa fue configurada, "
                        "pero no se pudo iniciar "
                        "la sesión administrativa.",
                },
            ) from exc

        # Rotate even though the endpoint is now closed by state.
        _BOOTSTRAP_NONCE = (
            uuid.uuid4().hex
        )

        return {
            "status":
                "CONFIGURED",
            "bootstrap_available":
                False,
            "company": {
                "tenant_id":
                    tenant_id,
                "name":
                    company_name,
                "business_type":
                    business_type,
                "accent_color":
                    accent_color,
                "theme":
                    theme,
            },
            "user":
                user,
            "login_username":
                login_username,
            "token":
                token,
            "next":
                "/settings?setup=data",
        }


@app.post("/api/auth/login")
def auth_login(payload: Dict[str,Any]):
    try:
        token,user=_identity_store().login(payload.get("username"),payload.get("password"));return {"token":token,"user":user}
    except IdentityError as exc:_auth_error(exc)
    except TenantRegistryError as exc:
        raise base.HTTPException(status_code=401,detail={"code":"AUTH_INVALID_CREDENTIALS","message":"Credenciales inv?lidas"}) from exc

@app.post("/api/auth/logout")
def auth_logout(authorization: str = Header("")):
    try:_identity_store().logout(str(authorization)[7:] if str(authorization).startswith("Bearer ") else "");return {"ok":True}
    except IdentityError as exc:_auth_error(exc)

@app.get("/api/auth/me")
def auth_me(authorization: str = Header("")):
    user = _bearer(authorization)
    return {**user, "effective_permissions": _identity_store().effective_permissions(user)}

@app.get("/api/admin/users")
def admin_users(authorization: str = Header("")):
    user=_bearer(authorization); store=_identity_store()
    if not store.has_permission(user,"user:list"): raise base.HTTPException(status_code=403,detail={"code":"PERMISSION_DENIED","message":"Permiso denegado"})
    return {"users":store.list(None if "SYSTEM_ADMIN" in user["roles"] else user["tenant_id"])}

def _admin_user(authorization: str, permission: str, target: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    actor=_bearer(authorization);store=_identity_store()
    if not store.has_permission(actor,permission): raise base.HTTPException(status_code=403,detail={"code":"PERMISSION_DENIED","message":"Permiso denegado"})
    if target and "SYSTEM_ADMIN" not in actor["roles"] and target["tenant_id"]!=actor["tenant_id"]: raise base.HTTPException(status_code=404,detail={"code":"USER_NOT_FOUND","message":"Usuario no encontrado"})
    return actor

@app.post("/api/admin/users")
def create_admin_user(payload: Dict[str,Any], authorization: str = Header("")):
    actor=_admin_user(authorization,"user:create"); store=_identity_store(); tenant_id=payload.get("tenant_id") or actor["tenant_id"]
    if "SYSTEM_ADMIN" not in actor["roles"] and tenant_id!=actor["tenant_id"]: raise base.HTTPException(status_code=403,detail={"code":"TENANT_SCOPE_DENIED","message":"Tenant no permitido"})
    roles=payload.get("roles") or ["VIEWER"]
    if "SYSTEM_ADMIN" not in actor["roles"] and "SYSTEM_ADMIN" in roles: raise base.HTTPException(status_code=403,detail={"code":"PERMISSION_DENIED","message":"Escalación no permitida"})
    try:return store.create_user(user_id=payload.get("user_id"),username=payload.get("username"),display_name=payload.get("display_name"),password=payload.get("password"),tenant_id=tenant_id,roles=roles,business_units=payload.get("business_units"),branches=payload.get("branches"))
    except (IdentityError,TenantRegistryError) as exc: _auth_error(exc) if isinstance(exc,IdentityError) else _tenant_http_error(exc)

@app.get("/api/admin/users/{user_id}")
def get_admin_user(user_id: str, authorization: str = Header("")):
    store=_identity_store()
    try: target=store.get(user_id);_admin_user(authorization,"user:list",target);return target
    except IdentityError as exc:_auth_error(exc)

@app.patch("/api/admin/users/{user_id}")
def update_admin_user(user_id: str,payload: Dict[str,Any],authorization: str = Header("")):
    store=_identity_store()
    try:
        target=store.get(user_id);actor=_admin_user(authorization,"user:update",target)
        if "roles" in payload:
            _admin_user(authorization,"user:role_assign",target)
            if user_id==actor["user_id"] or ("SYSTEM_ADMIN" not in actor["roles"] and "SYSTEM_ADMIN" in payload["roles"]): raise base.HTTPException(status_code=403,detail={"code":"PERMISSION_DENIED","message":"Escalación no permitida"})
        return store.update(user_id,**{k:v for k,v in payload.items() if k in {"display_name","business_units","branches","roles"}})
    except IdentityError as exc:_auth_error(exc)

@app.post("/api/admin/users/{user_id}/{action}")
def user_action(user_id:str,action:str,payload:Dict[str,Any]={},authorization:str=Header("")):
    store=_identity_store()
    try:
        target=store.get(user_id)
        permission="user:update" if action=="reset-password" else "user:disable"
        _admin_user(authorization,permission,target)
        if action=="disable":return store.set_status(user_id,"DISABLED")
        if action=="enable":return store.set_status(user_id,"ACTIVE")
        if action=="reset-password":store.change_password(user_id,payload.get("password"));return {"user_id":user_id,"password_reset":True}
        raise base.HTTPException(status_code=404,detail={"code":"USER_NOT_FOUND","message":"Acción no encontrada"})
    except IdentityError as exc:_auth_error(exc)


def _require_tenant_admin(authorization: str = "", tenant_id: Optional[str] = None, permission: str = "tenant:list") -> Dict[str, Any]:
    if authorization:
        user = _bearer(authorization); store = _identity_store()
        if not store.has_permission(user, permission):
            raise base.HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "Permiso denegado"})
        if "SYSTEM_ADMIN" not in user["roles"] and tenant_id and tenant_id != user["tenant_id"]:
            raise base.HTTPException(status_code=403, detail={"code": "TENANT_SCOPE_DENIED", "message": "Tenant no permitido"})
        return user
    if bool(_tenant_admin_guard()): return {"roles": ["SYSTEM_ADMIN"], "tenant_id": None}
    raise base.HTTPException(status_code=403, detail={"code": "TENANT_ADMIN_REQUIRED", "message": "Autorización administrativa requerida"})


def _tenant_http_error(exc: TenantRegistryError):
    status = 404 if exc.code == "TENANT_NOT_FOUND" else (409 if exc.code == "TENANT_ALREADY_EXISTS" else 400)
    raise base.HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc

def _config_http_error(exc: PlatformConfigError):
    status=503 if exc.code in {"AI_PROVIDER_UNAVAILABLE","AI_PROVIDER_TIMEOUT"} else (403 if exc.code in {"CONFIG_PERMISSION_DENIED","CONFIG_TENANT_SCOPE_DENIED"} else 400)
    raise base.HTTPException(status_code=status,detail={"code":exc.code,"message":str(exc)}) from exc

def _config_actor(authorization: str, permission: str):
    actor=_bearer(authorization)
    if not _identity_store().has_permission(actor,permission):raise base.HTTPException(status_code=403,detail={"code":"CONFIG_PERMISSION_DENIED","message":"Permiso de configuración denegado"})
    return actor


_SQL_READINESS_MESSAGES = {
    "SQL_AUTH_FAILED": "Autenticación SQL rechazada",
    "SQL_TIMEOUT": "Tiempo de espera SQL agotado",
    "SQL_CONNECTION_DISABLED": "Conexión SQL deshabilitada",
    "SQL_CONNECTION_NOT_FOUND": "Conexión SQL requerida no configurada",
    "SQL_CONNECTION_TEST_FAILED": "Conexión SQL no disponible",
    "SQL_DATABASE_UNAVAILABLE": "Base de datos SQL no disponible",
    "SQL_DRIVER_NOT_AVAILABLE": "Driver SQL Server no disponible",
    "SQL_SCHEMA_DISCOVERY_FAILED": "Discovery SQL no disponible",
}


_AI_READINESS_MESSAGES = {
    "AI_PROVIDER_UNAVAILABLE": "Provider IA no disponible",
    "AI_PROVIDER_TIMEOUT": "Tiempo de espera IA agotado",
    "AI_MODEL_INVALID": "Modelo IA inválido o ausente",
    "AI_PROVIDER_INVALID": "Configuración de provider IA inválida",
}


_READINESS_MESSAGES = {
    "TENANT_DISABLED": "Empresa deshabilitada",
    "TENANT_INTEGRITY_MISMATCH": "Registro de empresa no confiable",
    "IDENTITY_INTEGRITY_MISMATCH": "Registro de identidad no confiable",
    "CONFIG_INTEGRITY_MISMATCH": "Configuración empresarial no confiable",
    "CONFIGURATION_REQUIRED": "Configuración empresarial requerida",
    **_SQL_READINESS_MESSAGES,
    **_AI_READINESS_MESSAGES,
}

_READINESS_ACTIONS = {
    "SQL_CONNECTION_TEST_FAILED": "Verifica que SQL Server esté disponible y vuelve a validar.",
    "SQL_DATABASE_UNAVAILABLE": "Verifica que SQL Server esté disponible y vuelve a validar.",
    "SQL_TIMEOUT": "Verifica conectividad o carga del servidor y vuelve a validar.",
    "SQL_AUTH_FAILED": "Revisa la referencia de credenciales configurada.",
    "SQL_CONNECTION_DISABLED": "Habilita una conexión SQL gobernada y vuelve a validar.",
    "SQL_CONNECTION_NOT_FOUND": "Configura una conexión SQL gobernada y vuelve a validar.",
    "AI_PROVIDER_UNAVAILABLE": "Verifica que el proveedor de IA esté disponible.",
    "AI_PROVIDER_TIMEOUT": "Verifica el proveedor de IA y vuelve a validar.",
    "AI_MODEL_INVALID": "Selecciona un modelo disponible.",
    "AI_PROVIDER_INVALID": "Completa la configuración del proveedor de IA.",
    "TENANT_DISABLED": "Habilita la empresa antes de continuar.",
    "TENANT_INTEGRITY_MISMATCH": "Restaura una configuración válida antes de continuar.",
    "IDENTITY_INTEGRITY_MISMATCH": "Restaura una configuración válida antes de continuar.",
    "CONFIG_INTEGRITY_MISMATCH": "Restaura una configuración válida antes de continuar.",
    "CONFIGURATION_REQUIRED": "Completa la configuración requerida y vuelve a validar.",
}


def _readiness_component_for_code(code: str) -> str:
    code = str(code or "")
    if code.startswith("TENANT_"):
        return "tenant"
    if code.startswith("IDENTITY_"):
        return "identity"
    if code.startswith("SQL_"):
        return "sql"
    if code.startswith(("AI_", "CONFIG_")):
        return "configuration"
    return "configuration"


def _readiness_observability(readiness: Dict[str, Any], *, sql_test=None, ai_test=None) -> Dict[str, Any]:
    """Project canonical readiness into safe, display-ready component evidence."""
    result = dict(readiness or {})
    steps = {
        key: dict(value or {})
        for key, value in dict(result.get("steps") or {}).items()
    }
    components = {
        "company": "tenant",
        "admin": "identity",
        "sql": "sql",
        "ai": "ai",
        "branding": "configuration",
    }

    transient = {"sql": sql_test, "ai": ai_test}
    for key, step in steps.items():
        step["component"] = components.get(key, "configuration")
        evidence = transient.get(key)
        if isinstance(evidence, dict) and evidence.get("code"):
            step["code"] = str(evidence["code"])
            step["safe_message"] = str(evidence.get("safe_message") or _READINESS_MESSAGES.get(step["code"], "Validación no disponible"))
            step["recoverable"] = bool(evidence.get("recoverable", True))
        code = str(step.get("code") or "")
        if code:
            step.setdefault("safe_message", _READINESS_MESSAGES.get(code, "Validación no disponible"))
            step.setdefault("recoverable", True)
            action = _READINESS_ACTIONS.get(code)
            if action:
                step["suggested_action"] = action

    top_code = str(result.get("code") or "")
    if top_code:
        component = _readiness_component_for_code(top_code)
        steps.setdefault(component, {
            "component": component,
            "status": "BLOCKED",
            "required": True,
        })
        steps[component].update({
            "code": top_code,
            "safe_message": _READINESS_MESSAGES.get(top_code, "Configuración empresarial no confiable"),
            "recoverable": True,
            "suggested_action": _READINESS_ACTIONS.get(top_code, "Restaura una configuración válida antes de continuar."),
        })

    result["steps"] = steps
    return result


def _ai_readiness_failure(exc: PlatformConfigError) -> Dict[str, Any]:
    code = str(exc.code or "AI_PROVIDER_UNAVAILABLE")
    return {
        "component": "ai",
        "status": "FAIL",
        "code": code,
        "safe_message": _AI_READINESS_MESSAGES.get(
            code,
            "Validación IA no disponible",
        ),
        "recoverable": True,
    }


def _sql_readiness_failure(exc: EnterpriseSqlError) -> Dict[str, Any]:
    code = str(exc.code or "SQL_CONNECTION_TEST_FAILED")
    return {
        "component": "sql",
        "status": "FAIL",
        "code": code,
        "safe_message": _SQL_READINESS_MESSAGES.get(
            code,
            "Validación SQL no disponible",
        ),
        "recoverable": True,
    }


def _validate_sql_readiness(onboarding: EnterpriseOnboarding, tenant_id: str, initial: Dict[str, Any]) -> Dict[str, Any]:
    """Run only governed connection/discovery checks for existing SQL profiles."""
    sql_step = dict(initial.get("steps", {}).get("sql", {}))
    if not sql_step.get("required"):
        return {"component": "sql", "status": "NOT_REQUIRED"}

    try:
        scope = onboarding.sql_readiness_scope(tenant_id)
        profiles = onboarding.sql.list(scope)
    except (EnterpriseSqlError, OnboardingError) as exc:
        if isinstance(exc, EnterpriseSqlError):
            return _sql_readiness_failure(exc)
        return {
            "component": "sql",
            "status": "BLOCKED",
            "code": "CONFIGURATION_REQUIRED",
            "safe_message": "Configuración SQL requerida",
            "recoverable": True,
        }

    active = [
        profile for profile in profiles
        if profile.get("enabled") and profile.get("read_only")
    ]
    if not active:
        code = (
            "SQL_CONNECTION_DISABLED"
            if profiles else "SQL_CONNECTION_NOT_FOUND"
        )
        return {
            "component": "sql",
            "status": "BLOCKED",
            "code": code,
            "safe_message": _SQL_READINESS_MESSAGES[code],
            "recoverable": True,
        }

    _, provider, _ = _sql_admin_services()
    for profile in active:
        try:
            test_connection(
                onboarding.sql,
                provider,
                scope,
                profile["connection_id"],
            )
            discover_schema(
                onboarding.sql,
                provider,
                scope,
                profile["connection_id"],
            )
        except EnterpriseSqlError as exc:
            return _sql_readiness_failure(exc)

    return {
        "component": "sql",
        "status": "PASS",
        "tested_count": len(active),
    }

class _EnterpriseAiHealthAdapter:
    """Bridge platform-config health contract to existing productive providers."""

    def health(self, config: Dict[str, Any]) -> bool:
        provider_type = str(
            config.get("provider_type")
            or ""
        ).upper()

        base_url = str(
            config.get("base_url")
            or ""
        ).strip()

        model = str(
            config.get("model")
            or ""
        ).strip()

        timeout = int(
            config.get("timeout")
            or 30
        )

        if not model:
            raise PlatformConfigError(
                "AI_MODEL_INVALID",
                "Modelo IA requerido para validar preparaci?n",
            )

        if provider_type == "OLLAMA":
            provider = OllamaProvider(
                base_url,
                model,
                timeout=timeout,
            )

        elif provider_type == "OPENAI_COMPATIBLE_LOCAL":
            provider = LMStudioProvider(
                base_url,
                model,
                timeout=timeout,
            )

        else:
            raise PlatformConfigError(
                "AI_PROVIDER_INVALID",
                "Provider IA inv?lido",
            )

        if not provider.healthy():
            raise PlatformConfigError(
                "AI_PROVIDER_UNAVAILABLE",
                "Provider IA no disponible",
            )

        return True

    def discover_models(self, config: Dict[str, Any]):
        provider_type = str(config.get("provider_type") or "").upper()
        if provider_type != "OLLAMA":
            return {"supported": False}
        provider = OllamaProvider(
            str(config.get("base_url") or ""),
            str(config.get("model") or "discovery"),
            timeout=int(config.get("timeout") or 30),
        )
        return provider.list_models()


def _enterprise_onboarding() -> EnterpriseOnboarding:
    return EnterpriseOnboarding(
        base.REPORTES
    )


def _config_target(
    actor: Dict[str, Any],
    tenant_id: Optional[str],
) -> str:
    target = str(
        tenant_id
        or actor["tenant_id"]
        or ""
    ).strip().lower()

    if not target:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": "TENANT_REQUIRED",
                "message": "Empresa requerida",
            },
        )

    if (
        "SYSTEM_ADMIN"
        not in actor["roles"]
        and target
        != str(
            actor["tenant_id"]
        ).strip().lower()
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "CONFIG_TENANT_SCOPE_DENIED",
                "message":
                    "Tenant no permitido",
            },
        )

    return target


@app.get("/api/admin/config")
def get_platform_config(authorization: str=Header("")):
    actor=_config_actor(authorization,"config:read")
    if "SYSTEM_ADMIN" not in actor["roles"]:raise base.HTTPException(status_code=403,detail={"code":"CONFIG_PERMISSION_DENIED","message":"Permiso global denegado"})
    return _platform_config().global_config()

@app.patch("/api/admin/config")
def update_platform_config(payload: Dict[str,Any],authorization: str=Header("")):
    actor=_config_actor(authorization,"config:write")
    if "SYSTEM_ADMIN" not in actor["roles"]:raise base.HTTPException(status_code=403,detail={"code":"CONFIG_PERMISSION_DENIED","message":"Permiso global denegado"})
    try:return _platform_config().update_global(payload)
    except PlatformConfigError as exc:_config_http_error(exc)

@app.get("/api/admin/tenants/{tenant_id}/config")
def get_tenant_config(tenant_id:str,authorization: str=Header("")):
    actor=_config_actor(authorization,"config:read")
    if "SYSTEM_ADMIN" not in actor["roles"] and tenant_id!=actor["tenant_id"]:raise base.HTTPException(status_code=403,detail={"code":"CONFIG_TENANT_SCOPE_DENIED","message":"Tenant no permitido"})
    return {"tenant":_platform_config().tenant_config(tenant_id),"effective":_platform_config().public_effective_config(tenant_id)}

@app.patch("/api/admin/tenants/{tenant_id}/config")
def update_tenant_config(tenant_id:str,payload:Dict[str,Any],authorization: str=Header("")):
    actor=_config_actor(authorization,"config:write")
    if "SYSTEM_ADMIN" not in actor["roles"] and tenant_id!=actor["tenant_id"]:raise base.HTTPException(status_code=403,detail={"code":"CONFIG_TENANT_SCOPE_DENIED","message":"Tenant no permitido"})
    try:return _platform_config().update_tenant(tenant_id,payload)
    except (PlatformConfigError,TenantRegistryError) as exc:_config_http_error(exc) if isinstance(exc,PlatformConfigError) else _tenant_http_error(exc)

@app.get("/api/admin/ai/providers")
def get_ai_provider(tenant_id:Optional[str]=None,authorization: str=Header("")):
    actor=_config_actor(authorization,"config:read"); target=tenant_id or actor["tenant_id"]
    if "SYSTEM_ADMIN" not in actor["roles"] and target!=actor["tenant_id"]:raise base.HTTPException(status_code=403,detail={"code":"CONFIG_TENANT_SCOPE_DENIED","message":"Tenant no permitido"})
    return {"provider":_platform_config().resolve_effective_config(target).get("ai_provider")}

@app.post("/api/admin/ai/provider/test")
def test_ai_provider(
    payload: Dict[str, Any],
    authorization: str = Header(""),
):
    actor = _config_actor(
        authorization,
        "config:read",
    )

    target = _config_target(
        actor,
        payload.get("tenant_id"),
    )

    try:
        provider = (
            payload.get("provider")
            or _platform_config()
            .resolve_effective_config(
                target
            )
            .get("ai_provider")
            or {}
        )

        result = (
            _platform_config()
            .test_provider(
                provider,
                adapter=
                    _EnterpriseAiHealthAdapter(),
            )
        )

        return {
            **result,
            "tenant_id": target,
        }

    except PlatformConfigError as exc:
        _config_http_error(exc)

@app.post("/api/admin/ai/provider/models")
def discover_ai_provider_models(
    payload: Dict[str, Any],
    authorization: str = Header(""),
):
    actor = _config_actor(authorization, "config:read")
    target = _config_target(actor, payload.get("tenant_id"))
    provider = (
        payload.get("provider")
        or _platform_config().resolve_effective_config(target).get("ai_provider")
        or {}
    )
    try:
        return {
            **_platform_config().discover_models(
                provider,
                adapter=_EnterpriseAiHealthAdapter(),
            ),
            "tenant_id": target,
        }
    except PlatformConfigError as exc:
        _config_http_error(exc)


@app.get("/api/admin/tenants/{tenant_id}/readiness")
def get_tenant_readiness(
    tenant_id: str,
    authorization: str = Header(""),
):
    actor = _config_actor(
        authorization,
        "config:read",
    )

    target = _config_target(
        actor,
        tenant_id,
    )

    return _readiness_observability(
        _enterprise_onboarding().readiness(target)
    )


@app.post("/api/admin/tenants/{tenant_id}/readiness/validate")
def validate_tenant_readiness(
    tenant_id: str,
    authorization: str = Header(""),
):
    actor = _config_actor(
        authorization,
        "config:read",
    )

    target = _config_target(
        actor,
        tenant_id,
    )

    if not _identity_store().has_permission(actor, "sql:read"):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code": "SQL_PERMISSION_DENIED",
                "message": "Permiso SQL denegado",
            },
        )

    onboarding = _enterprise_onboarding()

    initial = onboarding.readiness(
        target
    )

    sql_test = _validate_sql_readiness(
        onboarding,
        target,
        initial,
    )

    ai_step = (
        initial.get("steps", {})
        .get("ai", {})
    )

    if not ai_step.get("required"):
        return {
            "tenant_id": target,
            "sql_test": sql_test,
            "ai_test": {
                "status":
                    "NOT_REQUIRED",
            },
            "readiness": _readiness_observability(
                onboarding.readiness(target),
                sql_test=sql_test,
            ),
        }

    effective = (
        _platform_config()
        .resolve_effective_config(
            target
        )
    )

    provider = (
        effective.get("ai_provider")
        or {}
    )

    try:
        ai_test = (
            _platform_config()
            .test_provider(
                provider,
                adapter=
                    _EnterpriseAiHealthAdapter(),
            )
        )

    except PlatformConfigError as exc:
        if exc.code in _AI_READINESS_MESSAGES:
            ai_test = _ai_readiness_failure(exc)

            return {
                "tenant_id": target,
                "sql_test": sql_test,
                "ai_test": ai_test,
                "readiness": _readiness_observability(
                    onboarding.readiness(target, ai_test=ai_test),
                    sql_test=sql_test,
                    ai_test=ai_test,
                ),
            }

        _config_http_error(exc)

    return {
        "tenant_id": target,
        "sql_test": sql_test,
        "ai_test": ai_test,
        "readiness": _readiness_observability(
            onboarding.readiness(target, ai_test=ai_test),
            sql_test=sql_test,
            ai_test=ai_test,
        ),
    }


@app.get("/api/admin/tenants")
def list_admin_tenants(authorization: str = Header("")) -> Dict[str, Any]:
    user=_require_tenant_admin(authorization)
    try:
        items=_tenant_registry().list(); return {"tenants":items if "SYSTEM_ADMIN" in user["roles"] else [x for x in items if x["tenant_id"]==user["tenant_id"]]}
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.post("/api/admin/tenants")
def create_admin_tenant(payload: Dict[str, Any], authorization: str = Header("")) -> Dict[str, Any]:
    user=_require_tenant_admin(authorization,permission="tenant:update")
    if "SYSTEM_ADMIN" not in user["roles"]: raise base.HTTPException(status_code=403,detail={"code":"PERMISSION_DENIED","message":"Permiso denegado"})
    try:
        return _tenant_registry().create(tenant_id=payload.get("tenant_id"), name=payload.get("name"), settings=payload.get("settings"), default_business_unit=payload.get("default_business_unit"), default_branch=payload.get("default_branch"))
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.get("/api/admin/tenants/{tenant_id}")
def get_admin_tenant(tenant_id: str, authorization: str = Header("")) -> Dict[str, Any]:
    _require_tenant_admin(authorization,tenant_id)
    try:
        return _tenant_registry().get(tenant_id)
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.patch("/api/admin/tenants/{tenant_id}")
def update_admin_tenant(tenant_id: str, payload: Dict[str, Any], authorization: str = Header("")) -> Dict[str, Any]:
    _require_tenant_admin(authorization,tenant_id,permission="tenant:update")
    try:
        allowed = {"name", "settings", "default_business_unit", "default_branch"}
        if set(payload) - allowed:
            raise TenantRegistryError("TENANT_INVALID_SETTINGS", "Campos de actualización no permitidos")
        return _tenant_registry().update(tenant_id, **payload)
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.post("/api/admin/tenants/{tenant_id}/disable")
def disable_admin_tenant(tenant_id: str, authorization: str = Header("")) -> Dict[str, Any]:
    user = _require_tenant_admin(authorization,tenant_id,permission="tenant:update")
    if "SYSTEM_ADMIN" in user["roles"] and str(tenant_id).strip().lower() == str(user["tenant_id"]).strip().lower():
        raise base.HTTPException(status_code=403,detail={"code":"TENANT_SELF_DISABLE_DENIED","message":"No se puede deshabilitar la empresa de la sesion SYSTEM_ADMIN"})
    try:
        _identity_store().revoke_tenant_sessions(tenant_id)
        return _tenant_registry().disable(tenant_id)
    except IdentityError as exc:
        _auth_error(exc)
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.post("/api/admin/tenants/{tenant_id}/enable")
def enable_admin_tenant(tenant_id: str, authorization: str = Header("")) -> Dict[str, Any]:
    _require_tenant_admin(authorization,tenant_id,permission="tenant:update")
    try:
        return _tenant_registry().enable(tenant_id)
    except TenantRegistryError as exc:
        _tenant_http_error(exc)


@app.get("/api/deliverables")
def list_governed_deliverables(
    limit: int = 100,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _actor_with_permission(
        authorization,
        "deliverable:read",
        code="DELIVERABLE_PERMISSION_DENIED",
        message="Permiso de entregables denegado",
    )

    scope = _authenticated_content_scope(
        actor
    )

    try:
        records = GovernedDeliverableRegistry(
            base.REPORTES
        ).list(
            scope,
            limit=limit,
        )

        return {
            "registry":
                deliverable_registry_public_audit(
                    records
                ),
            "items":
                records,
        }

    except DeliverableRegistryError as exc:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc


@app.get("/api/deliverables/{run_id}")
def get_governed_deliverable(
    run_id: str,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _actor_with_permission(
        authorization,
        "deliverable:read",
        code="DELIVERABLE_PERMISSION_DENIED",
        message="Permiso de entregables denegado",
    )

    scope = _authenticated_content_scope(
        actor
    )

    try:
        return GovernedDeliverableRegistry(
            base.REPORTES
        ).get(
            scope,
            run_id,
        )

    except DeliverableRegistryError as exc:
        status = (
            404
            if exc.code
            in {
                "RUN_NOT_FOUND",
                "ARTIFACT_NOT_FOUND",
            }
            else 400
        )

        raise base.HTTPException(
            status_code=status,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc


@app.get("/api/deliverables/{run_id}/download/{kind}")
def download_governed_deliverable(
    run_id: str,
    kind: str,
    authorization: str = Header(""),
):
    actor = _actor_with_permission(
        authorization,
        "deliverable:read",
        code="DELIVERABLE_PERMISSION_DENIED",
        message="Permiso de entregables denegado",
    )

    scope = _authenticated_content_scope(
        actor
    )

    try:
        path = GovernedDeliverableRegistry(
            base.REPORTES
        ).artifact_path(
            scope,
            run_id,
            kind,
        )

        return base.FileResponse(
            path,
            filename=path.name,
        )

    except DeliverableRegistryError as exc:
        status = (
            404
            if exc.code
            in {
                "RUN_NOT_FOUND",
                "ARTIFACT_NOT_FOUND",
            }
            else 400
        )

        raise base.HTTPException(
            status_code=status,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc


def _sql_http_error(exc: EnterpriseSqlError):
    status = 404 if exc.code in {"SQL_CONNECTION_NOT_FOUND", "SQL_SCOPE_DENIED"} else (503 if exc.code == "SQL_DRIVER_NOT_AVAILABLE" else (504 if exc.code == "SQL_TIMEOUT" else 400))
    raise base.HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc



def _production_sql_secret_store() -> EnterpriseSecretStore:
    """
    Production SQL_AUTH secrets use Windows Credential Manager.

    SQL profile files contain only the opaque secret reference.
    """
    return EnterpriseSecretStore(
        WindowsCredentialSecretProvider()
    )


def _sql_executor():
    secrets = _production_sql_secret_store()

    return EnterpriseSqlExecutor(
        EnterpriseSqlConnectionStore(
            base.REPORTES
            / ".sql_connections"
        ),
        SqlServerPyodbcProvider(
            secrets
        ),
    )


# R10.20B.3.3: SQL administration is deliberately wired through the B.2
# identity boundary and the B.3.1/B.3.2 gateway.  The configuration hook is
# only an injectable local seam for deterministic tests; production has no
# implicit plaintext secret provider.
_sql_admin_overrides: Dict[str, Any] = {}
_sql_admin_events: List[Dict[str, Any]] = []


def configure_sql_admin_services(*, store=None, provider=None, secret_store=None, audit_events=None) -> None:
    global _sql_admin_overrides, _sql_admin_events
    _sql_admin_overrides = {"store": store, "provider": provider, "secret_store": secret_store}
    _sql_admin_events = audit_events if audit_events is not None else []



def _sql_admin_services():
    store = (
        _sql_admin_overrides.get("store")
        or EnterpriseSqlConnectionStore(
            base.REPORTES
            / ".sql_connections",
            _tenant_registry(),
        )
    )

    secrets = _sql_admin_overrides.get(
        "secret_store"
    )

    if secrets is None:
        secrets = _production_sql_secret_store()

    provider = (
        _sql_admin_overrides.get("provider")
        or SqlServerPyodbcProvider(
            secrets
        )
    )

    return store, provider, secrets


def _sql_admin_audit(event: str, actor: Dict[str, Any], connection_id: str, tenant_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    event_data = {"event": event, "actor_user_id": actor["user_id"], "tenant_id": tenant_id, "connection_id": connection_id, "at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    if metadata: event_data.update(metadata)
    _sql_admin_events.append(event_data)


def _sql_admin_scope(actor: Dict[str, Any], tenant_id: Optional[str]) -> Dict[str, Any]:
    requested = str(tenant_id or "").strip().lower() or None
    system = "SYSTEM_ADMIN" in actor["roles"]
    if system:
        if not requested:
            raise base.HTTPException(status_code=400, detail={"code": "TENANT_REQUIRED", "message": "tenant_id es obligatorio para SYSTEM_ADMIN"})
        try: _tenant_registry().assert_active(requested)
        except TenantRegistryError as exc: _tenant_http_error(exc)
        company_id = requested
    else:
        if requested and requested != actor["tenant_id"]:
            raise base.HTTPException(status_code=403, detail={"code": "TENANT_SCOPE_DENIED", "message": "Tenant no permitido"})
        company_id = actor["tenant_id"]
    return {"company_id": company_id, "user_id": "sql-admin", "business_unit": None, "branch": None}


def _sql_admin_actor(authorization: str, permission: str) -> Dict[str, Any]:
    actor = _bearer(authorization)
    if not _identity_store().has_permission(actor, permission):
        raise base.HTTPException(status_code=403, detail={"code": "SQL_PERMISSION_DENIED", "message": "Permiso SQL denegado"})
    return actor


def _sql_admin_http_error(exc: EnterpriseSqlError):
    if exc.code == "SQL_CONNECTION_NOT_FOUND": status = 404
    elif exc.code in {"SQL_SECRET_UNAVAILABLE", "SQL_DRIVER_NOT_AVAILABLE"}: status = 503
    elif exc.code in {"SQL_SCOPE_DENIED"}: status = 403
    elif exc.code == "SQL_CONNECTION_ALREADY_EXISTS": status = 409
    else: status = 400
    raise base.HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc


def _sql_profile_or_error(store, scope, connection_id):
    try: return store.get(scope, connection_id)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)


class _TransientSqlSecretProvider:
    """Request-local secret provider for a single SQL probe."""

    def __init__(self) -> None:
        self._values: Dict[str, str] = {}

    def set(
        self,
        reference: str,
        value: str,
    ) -> None:
        self._values[
            str(reference)
        ] = str(value)

    def get(
        self,
        reference: str,
    ) -> Optional[str]:
        return self._values.get(
            str(reference)
        )

    def delete(
        self,
        reference: str,
    ) -> None:
        self._values.pop(
            str(reference),
            None,
        )

    def clear(self) -> None:
        self._values.clear()



# ---------------------------------------------------------
# R10.23-B.6 — governed out-of-process backup / recovery.
# Runtime-wide maintenance is SYSTEM_ADMIN-only.
# The browser never supplies or receives filesystem paths.
# ---------------------------------------------------------

import asyncio as _maintenance_asyncio

from fastapi import File as _maintenance_file
from fastapi import Request as _maintenance_request
from fastapi import UploadFile as _maintenance_upload_file

from enterprise_maintenance_worker import (
    MaintenanceBusy as _MaintenanceBusy,
    MaintenanceError as _MaintenanceError,
    backup_artifact_path as _maintenance_backup_artifact_path,
    create_job as _maintenance_create_job,
    fail_job as _maintenance_fail_job,
    get_public_job as _maintenance_get_public_job,
    launch_worker as _launch_maintenance_worker,
    list_public_jobs as _maintenance_list_public_jobs,
    max_upload_bytes as _maintenance_max_upload_bytes,
    new_job_id as _maintenance_new_job_id,
    release_job_lock as _maintenance_release_job_lock,
    restore_upload_path as _maintenance_restore_upload_path,
    sha256_file as _maintenance_sha256_file,
    strict_validate_archive as _maintenance_validate_archive,
    update_job as _maintenance_update_job,
)



def _maintenance_actor(
    authorization: str,
    permission: str,
) -> Dict[str, Any]:
    actor = _bearer(
        authorization
    )

    if (
        "SYSTEM_ADMIN"
        not in set(
            actor.get(
                "roles"
            )
            or []
        )
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "MAINTENANCE_SYSTEM_ADMIN_REQUIRED",
                "message":
                    "La recuperación del sistema requiere SYSTEM_ADMIN",
            },
        )

    if permission not in {
        "backup:create",
        "backup:restore",
    }:
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "MAINTENANCE_PERMISSION_DENIED",
                "message":
                    "Permiso de mantenimiento denegado",
            },
        )

    if not _identity_store().has_permission(
        actor,
        permission,
    ):
        raise base.HTTPException(
            status_code=403,
            detail={
                "code":
                    "MAINTENANCE_PERMISSION_DENIED",
                "message":
                    "Permiso de mantenimiento denegado",
            },
        )

    return actor



def _maintenance_product_root() -> Path:
    return (
        base.ROOT
        .resolve()
        .parent
    )



def _maintenance_runtime_port(
    request: _maintenance_request,
) -> int:
    try:
        server = (
            request.scope.get(
                "server"
            )
            or (
                None,
                8090,
            )
        )

        port = int(
            server[1]
            or 8090
        )

    except Exception:
        port = 8090

    if not (
        1
        <= port
        <= 65535
    ):
        return 8090

    return port


async def _maintenance_upload_heartbeat(
    product_root: Path,
    job_id: str,
    *,
    interval_seconds: float = 30.0,
) -> None:
    try:
        interval = float(
            interval_seconds
        )
    except Exception:
        interval = 30.0

    # stale_job_seconds() has a minimum of five minutes.
    # Keep the normal heartbeat comfortably below that
    # without allowing an excessively tight loop.
    interval = max(
        5.0,
        min(
            interval,
            60.0,
        ),
    )

    while True:
        await _maintenance_asyncio.sleep(
            interval
        )

        _maintenance_update_job(
            product_root,
            job_id,
            status="UPLOADING",
        )


def _maintenance_http_error(
    exc: Exception,
):
    if isinstance(
        exc,
        _MaintenanceBusy,
    ):
        raise base.HTTPException(
            status_code=409,
            detail={
                "code":
                    "MAINTENANCE_BUSY",
                "message":
                    "Ya existe una operación de mantenimiento en curso",
            },
        )

    if isinstance(
        exc,
        _MaintenanceError,
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    exc.code,
                "message":
                    "El respaldo no cumple el contrato de recuperación",
            },
        )

    raise exc


@app.get("/api/admin/maintenance/jobs")
def admin_maintenance_jobs(
    authorization: str = Header(""),
) -> Dict[str, Any]:
    _maintenance_actor(
        authorization,
        "backup:create",
    )

    return {
        "items":
            _maintenance_list_public_jobs(
                _maintenance_product_root(),
                30,
            )
    }


@app.get("/api/admin/maintenance/jobs/{job_id}")
def admin_maintenance_job(
    job_id: str,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    _maintenance_actor(
        authorization,
        "backup:create",
    )

    try:
        return _maintenance_get_public_job(
            _maintenance_product_root(),
            job_id,
        )
    except _MaintenanceError:
        raise base.HTTPException(
            status_code=404,
            detail={
                "code":
                    "MAINTENANCE_JOB_NOT_FOUND",
                "message":
                    "Operación no encontrada",
            },
        )


@app.post(
    "/api/admin/maintenance/backup",
    status_code=202,
)

def admin_maintenance_backup(
    request: _maintenance_request,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _maintenance_actor(
        authorization,
        "backup:create",
    )

    product_root = (
        _maintenance_product_root()
    )

    job = None

    try:
        job = _maintenance_create_job(
            product_root,
            "backup",
            actor.get(
                "user_id"
            ),
            runtime_port=(
                _maintenance_runtime_port(
                    request
                )
            ),
            restart_after=True,
        )

        _launch_maintenance_worker(
            product_root,
            job[
                "job_id"
            ],
        )

        return _maintenance_get_public_job(
            product_root,
            job[
                "job_id"
            ],
        )

    except Exception as exc:
        if job:
            _maintenance_fail_job(
                product_root,
                job[
                    "job_id"
                ],
                (
                    exc.code
                    if isinstance(
                        exc,
                        _MaintenanceError,
                    )
                    else
                    "MAINTENANCE_LAUNCH_FAILED"
                ),
            )

        _maintenance_http_error(
            exc
        )


@app.post(
    "/api/admin/maintenance/restore",
    status_code=202,
)


async def admin_maintenance_restore(
    request: _maintenance_request,
    file: _maintenance_upload_file = _maintenance_file(...),
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _maintenance_actor(
        authorization,
        "backup:restore",
    )

    product_root = (
        _maintenance_product_root()
    )

    job_id = (
        _maintenance_new_job_id()
    )

    upload = (
        _maintenance_restore_upload_path(
            product_root,
            job_id,
        )
    )

    job = None
    heartbeat_task = None
    total = 0

    limit = (
        _maintenance_max_upload_bytes()
    )

    try:
        # Reserve the global maintenance slot before reading
        # the potentially large backup body.
        job = _maintenance_create_job(
            product_root,
            "restore",
            actor.get(
                "user_id"
            ),
            job_id=job_id,
            runtime_port=(
                _maintenance_runtime_port(
                    request
                )
            ),
            restart_after=True,
        )

        _maintenance_update_job(
            product_root,
            job_id,
            status="UPLOADING",
        )

        # Refresh the pre-worker lease by elapsed time rather
        # than transferred bytes. This keeps a legitimately
        # slow upload alive even when no 16 MiB boundary is
        # crossed for several minutes.
        heartbeat_task = (
            _maintenance_asyncio.create_task(
                _maintenance_upload_heartbeat(
                    product_root,
                    job_id,
                )
            )
        )

        try:
            with upload.open(
                "wb"
            ) as stream:
                while True:
                    chunk = await file.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    total += len(
                        chunk
                    )

                    if total > limit:
                        raise base.HTTPException(
                            status_code=413,
                            detail={
                                "code":
                                    "BACKUP_UPLOAD_TOO_LARGE",
                                "message":
                                    "El respaldo excede el límite configurado",
                            },
                        )

                    stream.write(
                        chunk
                    )

        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()

                try:
                    await heartbeat_task

                except _maintenance_asyncio.CancelledError:
                    pass

                heartbeat_task = None

        if total <= 0:
            raise base.HTTPException(
                status_code=400,
                detail={
                    "code":
                        "BACKUP_UPLOAD_EMPTY",
                    "message":
                        "Selecciona un respaldo válido",
                },
            )

        validation = (
            _maintenance_validate_archive(
                upload
            )
        )

        upload_hash = (
            _maintenance_sha256_file(
                upload
            )
        )

        _maintenance_update_job(
            product_root,
            job_id,
            status="QUEUED",
            input_sha256=upload_hash,
        )

        _launch_maintenance_worker(
            product_root,
            job_id,
        )

        result = (
            _maintenance_get_public_job(
                product_root,
                job_id,
            )
        )

        result[
            "validated_files"
        ] = int(
            validation[
                "total_files"
            ]
        )

        return result

    except base.HTTPException as exc:
        upload.unlink(
            missing_ok=True
        )

        if job:
            detail = (
                exc.detail
                if isinstance(
                    exc.detail,
                    dict,
                )
                else {}
            )

            _maintenance_fail_job(
                product_root,
                job_id,
                str(
                    detail.get(
                        "code"
                    )
                    or "MAINTENANCE_REQUEST_FAILED"
                ),
            )

        raise

    except Exception as exc:
        upload.unlink(
            missing_ok=True
        )

        if job:
            _maintenance_fail_job(
                product_root,
                job_id,
                (
                    exc.code
                    if isinstance(
                        exc,
                        _MaintenanceError,
                    )
                    else
                    "MAINTENANCE_REQUEST_FAILED"
                ),
            )

        _maintenance_http_error(
            exc
        )


@app.get(
    "/api/admin/maintenance/jobs/{job_id}/download"
)
def admin_maintenance_download(
    job_id: str,
    authorization: str = Header(""),
):
    _maintenance_actor(
        authorization,
        "backup:create",
    )

    product_root = (
        _maintenance_product_root()
    )

    try:
        job = _maintenance_get_public_job(
            product_root,
            job_id,
        )
    except _MaintenanceError:
        raise base.HTTPException(
            status_code=404,
            detail={
                "code":
                    "MAINTENANCE_JOB_NOT_FOUND",
                "message":
                    "Operación no encontrada",
            },
        )

    if (
        job.get(
            "operation"
        )
        != "backup"
        or job.get(
            "status"
        )
        != "COMPLETED"
        or not job.get(
            "download_ready"
        )
    ):
        raise base.HTTPException(
            status_code=409,
            detail={
                "code":
                    "BACKUP_NOT_READY",
                "message":
                    "El respaldo todavía no está disponible",
            },
        )

    artifact = (
        _maintenance_backup_artifact_path(
            product_root,
            job_id,
        )
    )

    if not artifact.is_file():
        raise base.HTTPException(
            status_code=404,
            detail={
                "code":
                    "BACKUP_ARTIFACT_NOT_FOUND",
                "message":
                    "El respaldo ya no está disponible",
            },
        )

    return base.FileResponse(
        artifact,
        media_type="application/zip",
        filename=(
            "IA_EMPRESARIAL_LOCAL_"
            "backup_"
            + str(job_id)
            + ".zip"
        ),
    )


@app.post("/api/admin/sql/probe")
def admin_sql_probe(
    payload: Dict[str, Any],
    tenant_id: Optional[str] = None,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    """
    Validate SQL connectivity and discover selectable metadata before a
    governed profile exists.

    No connection profile is persisted and SQL_AUTH credentials live only
    inside the request-local transient secret provider.
    """

    actor = _sql_admin_actor(
        authorization,
        "sql:configure",
    )

    scope = _sql_admin_scope(
        actor,
        tenant_id,
    )

    allowed = {
        "server",
        "database",
        "auth_mode",
        "driver",
        "timeout_seconds",
        "trust_server_certificate",
        "username",
        "secret",
        "password",
    }

    if (
        not isinstance(
            payload,
            dict,
        )
        or set(payload)
        - allowed
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "SQL_CONNECTION_PROFILE_INVALID",
                "message":
                    "Campos SQL no permitidos",
            },
        )

    mode = str(
        payload.get(
            "auth_mode"
        )
        or ""
    ).strip().upper()

    if mode in {
        "INTEGRATED",
        "WINDOWS",
    }:
        mode = "WINDOWS_INTEGRATED"

    secret = payload.get(
        "secret",
        payload.get(
            "password"
        ),
    )

    username = str(
        payload.get(
            "username"
        )
        or ""
    ).strip()

    if (
        mode == "SQL_AUTH"
        and (
            not username
            or not isinstance(
                secret,
                str,
            )
            or not secret
        )
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "SQL_SECRET_UNAVAILABLE",
                "message":
                    "Usuario y contraseña SQL son obligatorios",
            },
        )

    _, configured_provider, _ = (
        _sql_admin_services()
    )

    transient_backend = None
    transient_store = None
    transient_reference = ""

    try:
        provider = configured_provider

        if mode == "SQL_AUTH":
            transient_backend = (
                _TransientSqlSecretProvider()
            )

            transient_store = (
                EnterpriseSecretStore(
                    transient_backend
                )
            )

            transient_reference = (
                "probe:"
                + uuid.uuid4().hex
            )

            transient_store.set(
                transient_reference,
                secret,
            )

            if isinstance(
                configured_provider,
                SqlServerPyodbcProvider,
            ):
                provider = (
                    SqlServerPyodbcProvider(
                        transient_store
                    )
                )

        profile = (
            build_transient_sql_probe_profile(
                server=payload.get(
                    "server"
                ),
                database=payload.get(
                    "database"
                ),
                auth_mode=mode,
                driver=payload.get(
                    "driver",
                    "ODBC Driver 18 for SQL Server",
                ),
                timeout_seconds=payload.get(
                    "timeout_seconds",
                    30,
                ),
                trust_server_certificate=bool(
                    payload.get(
                        "trust_server_certificate",
                        False,
                    )
                ),
                username=username,
                secret_reference=(
                    transient_reference
                    if mode
                    == "SQL_AUTH"
                    else ""
                ),
            )
        )

        result = (
            probe_sql_server_metadata(
                provider,
                profile,
            )
        )

    except EnterpriseSqlError as exc:
        _sql_admin_http_error(
            exc
        )

    finally:
        if (
            transient_store
            and transient_reference
        ):
            try:
                transient_store.delete(
                    transient_reference
                )
            except EnterpriseSqlError:
                pass

        if transient_backend:
            transient_backend.clear()

    _sql_admin_audit(
        "SQL_CONNECTION_PROBED",
        actor,
        "transient-probe",
        scope["company_id"],
        {
            "auth_mode": mode,
            "discovered_object_count":
                result[
                    "discovered_object_count"
                ],
            "result_status":
                result["status"],
        },
    )

    return result



@app.get("/api/admin/sql/connections")
def admin_sql_connections(tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:read"); scope = _sql_admin_scope(actor, tenant_id); store, _, _ = _sql_admin_services()
    try: return {"items": [public_sql_profile(item) for item in store.list(scope)]}
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)


@app.post("/api/admin/sql/connections")
def admin_sql_create_connection(payload: Dict[str, Any], tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:configure"); scope = _sql_admin_scope(actor, tenant_id); store, _, secrets = _sql_admin_services()
    allowed = {"connection_id", "server", "database", "auth_mode", "allowed_schemas", "allowed_tables", "display_name", "driver", "timeout_seconds", "max_rows", "trust_server_certificate", "username", "secret", "password"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise base.HTTPException(status_code=400, detail={"code": "SQL_CONNECTION_PROFILE_INVALID", "message": "Campos SQL no permitidos"})
    mode = str(payload.get("auth_mode") or "").upper()
    secret_reference = ""
    secret = payload.get("secret", payload.get("password"))
    if mode == "SQL_AUTH":
        if not isinstance(secret, str) or not secret:
            raise base.HTTPException(status_code=400, detail={"code": "SQL_SECRET_UNAVAILABLE", "message": "Secret SQL requerido"})
        secret_reference = "sql:" + uuid.uuid4().hex
        try: secrets.set(secret_reference, secret)
        except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    try:
        record = store.register(scope=scope, connection_id=payload.get("connection_id"), server=payload.get("server"), database=payload.get("database"), auth_mode=mode, allowed_schemas=payload.get("allowed_schemas"), allowed_tables=payload.get("allowed_tables"), display_name=payload.get("display_name", ""), driver=payload.get("driver", "ODBC Driver 18 for SQL Server"), timeout_seconds=payload.get("timeout_seconds", 30), max_rows=payload.get("max_rows", 500), trust_server_certificate=bool(payload.get("trust_server_certificate", False)), secret_reference=secret_reference, username=payload.get("username", ""))
    except EnterpriseSqlError as exc:
        if secret_reference:
            try: secrets.delete(secret_reference)
            except EnterpriseSqlError: pass
        _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_CONNECTION_CREATED", actor, record["connection_id"], scope["company_id"])
    return {"profile": public_sql_profile(record)}


@app.get("/api/admin/sql/connections/{connection_id}")
def admin_sql_get_connection(connection_id: str, tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:read"); scope = _sql_admin_scope(actor, tenant_id); store, _, _ = _sql_admin_services()
    return {"profile": public_sql_profile(_sql_profile_or_error(store, scope, connection_id))}


@app.patch("/api/admin/sql/connections/{connection_id}")
def admin_sql_update_connection(connection_id: str, payload: Dict[str, Any], tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:configure"); scope = _sql_admin_scope(actor, tenant_id); store, _, _ = _sql_admin_services()
    allowed = {"display_name", "server", "database", "driver", "timeout_seconds", "max_rows", "trust_server_certificate", "username"}
    if not isinstance(payload, dict) or not payload or set(payload) - allowed:
        raise base.HTTPException(status_code=400, detail={"code": "SQL_CONNECTION_PROFILE_INVALID", "message": "Campos SQL no permitidos"})
    try: record = store.update(scope, connection_id, **payload)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_CONNECTION_UPDATED", actor, connection_id, scope["company_id"])
    return {"profile": public_sql_profile(record)}


@app.patch("/api/admin/sql/connections/{connection_id}/allowlist")
def admin_sql_allowlist(connection_id: str, payload: Dict[str, Any], tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:configure"); scope = _sql_admin_scope(actor, tenant_id); store, _, _ = _sql_admin_services()
    if not isinstance(payload, dict) or set(payload) != {"schemas", "objects"}:
        raise base.HTTPException(status_code=400, detail={"code": "SQL_CONNECTION_PROFILE_INVALID", "message": "Allowlist inválida"})
    try: record = store.update(scope, connection_id, allowed_schemas=payload["schemas"], allowed_tables=payload["objects"])
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_ALLOWLIST_CHANGED", actor, connection_id, scope["company_id"])
    return {"profile": public_sql_profile(record)}


@app.post("/api/admin/sql/connections/{connection_id}/secret")
def admin_sql_rotate_secret(connection_id: str, payload: Dict[str, Any], tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:configure"); scope = _sql_admin_scope(actor, tenant_id); store, _, secrets = _sql_admin_services(); profile = _sql_profile_or_error(store, scope, connection_id)
    if profile.get("auth_mode") != "SQL_AUTH":
        raise base.HTTPException(status_code=400, detail={"code": "SQL_CONNECTION_PROFILE_INVALID", "message": "Secret no aplica a Windows Integrated"})
    secret = payload.get("secret", payload.get("password")) if isinstance(payload, dict) else None
    if not isinstance(secret, str) or not secret:
        raise base.HTTPException(status_code=400, detail={"code": "SQL_SECRET_UNAVAILABLE", "message": "Secret SQL requerido"})
    try: secrets.set(profile["secret_reference"], secret)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_SECRET_ROTATED", actor, connection_id, scope["company_id"])
    return {"connection_id": connection_id, "secret_rotated": True}


def _admin_sql_state_change(connection_id: str, enabled: bool, tenant_id: Optional[str], authorization: str) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:configure"); scope = _sql_admin_scope(actor, tenant_id); store, _, _ = _sql_admin_services()
    try: record = store.enable(scope, connection_id) if enabled else store.disable(scope, connection_id)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_CONNECTION_ENABLED" if enabled else "SQL_CONNECTION_DISABLED", actor, connection_id, scope["company_id"])
    return {"profile": public_sql_profile(record)}


@app.post("/api/admin/sql/connections/{connection_id}/disable")
def admin_sql_disable(connection_id: str, tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    return _admin_sql_state_change(connection_id, False, tenant_id, authorization)


@app.post("/api/admin/sql/connections/{connection_id}/enable")
def admin_sql_enable(connection_id: str, tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    return _admin_sql_state_change(connection_id, True, tenant_id, authorization)


def _admin_sql_run(connection_id: str, discovery: bool, tenant_id: Optional[str], authorization: str) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:read"); scope = _sql_admin_scope(actor, tenant_id); store, provider, _ = _sql_admin_services()
    try: result = discover_schema(store, provider, scope, connection_id) if discovery else test_connection(store, provider, scope, connection_id)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    _sql_admin_audit("SQL_DISCOVERY_RUN" if discovery else "SQL_CONNECTION_TESTED", actor, connection_id, scope["company_id"])
    return result


@app.post("/api/admin/sql/connections/{connection_id}/test")
def admin_sql_test(connection_id: str, tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    return _admin_sql_run(connection_id, False, tenant_id, authorization)


@app.post("/api/admin/sql/connections/{connection_id}/discover")
def admin_sql_discover(connection_id: str, tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    return _admin_sql_run(connection_id, True, tenant_id, authorization)


@app.post("/api/admin/sql/connections/{connection_id}/smoke")
def admin_sql_smoke(connection_id: str, payload: Dict[str, Any], tenant_id: Optional[str] = None, authorization: str = Header("")) -> Dict[str, Any]:
    actor = _sql_admin_actor(authorization, "sql:read"); scope = _sql_admin_scope(actor, tenant_id); store, provider, _ = _sql_admin_services()
    try: result = execute_smoke_query(store, provider, scope, connection_id, payload)
    except EnterpriseSqlError as exc: _sql_admin_http_error(exc)
    provenance = result["provenance"]
    _sql_admin_audit("SQL_SMOKE_RUN", actor, connection_id, scope["company_id"], {"object": f"{provenance['schema']}.{provenance['object']}", "row_count": result["row_count"], "truncated": result["truncated"], "query_fingerprint_sha256": provenance["query_fingerprint_sha256"], "result_status": result["status"], "query_ms": result["query_ms"]})
    return result


@app.get("/api/sql/connections")
def list_sql_connections(
    tenant_id: Optional[str] = None,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _sql_admin_actor(
        authorization,
        "sql:read",
    )

    scope = _sql_admin_scope(
        actor,
        tenant_id,
    )

    try:
        records = EnterpriseSqlConnectionStore(
            base.REPORTES
            / ".sql_connections"
        ).list(
            scope
        )

        fields = (
            "connection_id",
            "provider",
            "server",
            "database",
            "auth_mode",
            "enabled",
            "allowed_schemas",
            "allowed_tables",
            "read_only",
        )

        return {
            "items": [
                {
                    key:
                        item.get(key)
                    for key in fields
                }
                for item in records
            ]
        }

    except EnterpriseSqlError as exc:
        _sql_http_error(exc)


@app.get("/api/sql/schema")
def sql_schema(
    connection_id: str,
    tenant_id: Optional[str] = None,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _sql_admin_actor(
        authorization,
        "sql:read",
    )

    scope = _sql_admin_scope(
        actor,
        tenant_id,
    )

    try:
        return _sql_executor().discover(
            scope,
            connection_id,
        )

    except EnterpriseSqlError as exc:
        _sql_http_error(exc)


@app.post("/api/sql/query")
def sql_query(
    payload: Dict[str, Any],
    tenant_id: Optional[str] = None,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _sql_admin_actor(
        authorization,
        "sql:read",
    )

    scope = _sql_admin_scope(
        actor,
        tenant_id,
    )

    try:
        connection_id = str(
            payload.get("connection_id")
            or ""
        ).strip()

        if not connection_id:
            raise EnterpriseSqlError(
                "SQL_CONNECTION_NOT_FOUND",
                "connection_id es obligatorio",
            )

        return _sql_executor().execute(
            scope,
            connection_id,
            payload.get("query_plan")
            or {},
        )

    except EnterpriseSqlError as exc:
        _sql_http_error(exc)


@app.post("/api/sql/query-safe")
def sql_safe_query(
    payload: Dict[str, Any],
    tenant_id: Optional[str] = None,
    authorization: str = Header(""),
) -> Dict[str, Any]:
    """
    Execute a governed SQL query assembled from structured
    schema/object/column input.

    The client never supplies raw SQL. The canonical SQL gateway
    builds and validates the SELECT statement against the persisted
    read-only allowlist before execution.
    """
    actor = _sql_admin_actor(
        authorization,
        "sql:read",
    )

    scope = _sql_admin_scope(
        actor,
        tenant_id,
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "SQL_QUERY_INVALID",
                "message":
                    "Solicitud SQL inválida",
            },
        )

    allowed = {
        "connection_id",
        "schema",
        "object",
        "columns",
        "limit",
    }

    if set(payload) - allowed:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "SQL_QUERY_INVALID",
                "message":
                    "La consulta estructurada contiene campos no permitidos",
            },
        )

    connection_id = str(
        payload.get(
            "connection_id"
        )
        or ""
    ).strip()

    if not connection_id:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code":
                    "SQL_CONNECTION_NOT_FOUND",
                "message":
                    "connection_id es obligatorio",
            },
        )

    request = {
        key:
            payload[key]
        for key in (
            "schema",
            "object",
            "columns",
            "limit",
        )
        if key in payload
    }

    try:
        executor = _sql_executor()

        return execute_smoke_query(
            executor.store,
            executor.provider,
            scope,
            connection_id,
            request,
        )

    except EnterpriseSqlError as exc:
        _sql_http_error(
            exc
        )


@app.post("/api/ask")
def ask_enterprise_question(
    payload: Dict[str, Any],
    authorization: str = Header(""),
) -> Dict[str, Any]:
    actor = _authorize_analysis(
        authorization
    )

    _require_actor_permission(
        actor,
        "deliverable:read",
        code="DELIVERABLE_PERMISSION_DENIED",
        message="Permiso de entregables denegado",
    )

    sql_context = payload.get(
        "sql"
    )

    if sql_context is None:
        _require_actor_permission(
            actor,
            "knowledge:read",
            code="KNOWLEDGE_PERMISSION_DENIED",
            message="Permiso de conocimiento denegado",
        )

        sql_scope = None

    else:
        _require_actor_permission(
            actor,
            "sql:read",
            code="SQL_PERMISSION_DENIED",
            message="Permiso SQL denegado",
        )

        if not isinstance(
            sql_context,
            dict,
        ):
            raise base.HTTPException(
                status_code=400,
                detail={
                    "code": "SQL_CONTEXT_INVALID",
                    "message": "El contexto SQL debe ser un objeto",
                },
            )

        sql_scope = _sql_admin_scope(
            actor,
            sql_context.get(
                "tenant_id"
            ),
        )

    scope = _authenticated_content_scope(
        actor
    )

    question = str(
        payload.get("question")
        or ""
    ).strip()

    if not question:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": "QUESTION_REQUIRED",
                "message": "La pregunta es obligatoria.",
            },
        )

    requested_run_id = str(
        payload.get("run_id")
        or ""
    ).strip()

    registry = GovernedDeliverableRegistry(
        base.REPORTES
    )

    try:
        run_id = requested_run_id

        if not run_id:
            runs = registry.list(
                scope,
                limit=1,
            )

            if runs:
                run_id = str(
                    runs[0].get("run_id")
                    or ""
                ).strip()

        knowledge_store = EnterpriseKnowledgeStore(
            base.REPORTES
            / ".knowledge"
        )

        result = answer_enterprise_question_orchestrated(
            registry=registry,
            knowledge_store=knowledge_store,
            scope=scope,
            sql_scope=sql_scope,
            run_id=run_id,
            question=question,
            sql_context=sql_context,
            sql_executor=(
                _sql_executor()
                if sql_context is not None
                else None
            ),
        )

        return {
            "api_version": "r10.19d",
            "run_id": run_id,
            "result": result,
        }

    except DeliverableRegistryError as exc:
        status = (
            404
            if exc.code
            in {
                "RUN_NOT_FOUND",
                "ARTIFACT_NOT_FOUND",
            }
            else 400
        )

        raise base.HTTPException(
            status_code=status,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc

    except EnterpriseKnowledgeError as exc:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc

    except ValueError as exc:
        raise base.HTTPException(
            status_code=400,
            detail={
                "code": "ENTERPRISE_QA_ERROR",
                "message": str(exc),
            },
        ) from exc

def main() -> None:
    parser = base.argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
