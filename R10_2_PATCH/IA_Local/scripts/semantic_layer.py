from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

CONFIDENCE_ORDER = {"MISSING": 0, "AMBIGUOUS": 1, "INFERRED": 2, "STRONG": 3, "EXACT": 4}


def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(v: Any) -> Tuple[str, ...]:
    return tuple(x for x in _norm(v).split() if x)


def _series_kind(s: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    if pd.api.types.is_numeric_dtype(s):
        return "number"
    nonnull = s.dropna()
    if nonnull.empty:
        return "empty"
    # Conservative date inference: only infer when the majority parses as date and values look date-like.
    sample = nonnull.astype(str).head(80)
    looks_date = sample.str.contains(r"[-/]", regex=True).mean() >= 0.6
    if looks_date:
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.85:
            return "date"
    return "text"


@dataclass(frozen=True)
class ConceptSpec:
    key: str
    label: str
    aliases: Tuple[str, ...]
    kinds: Tuple[str, ...]
    positive_tokens: Tuple[str, ...] = ()
    negative_tokens: Tuple[str, ...] = ()


SPECS: Tuple[ConceptSpec, ...] = (
    ConceptSpec("date", "Fecha", ("fecha", "date", "fecha venta", "fecha factura", "transaction date", "invoice date"), ("date", "text"), ("fecha", "date"), ("inicio", "inicial", "fin", "final")),
    ConceptSpec("period_start", "Fecha inicial", ("fecha inicial", "fecha_inicial", "period start", "start date", "desde"), ("date", "text"), ("inicio", "inicial", "start")),
    ConceptSpec("period_end", "Fecha final", ("fecha final", "fecha_final", "period end", "end date", "hasta"), ("date", "text"), ("fin", "final", "end")),
    ConceptSpec("week", "Semana", ("semana", "week", "week number", "week label", "semana venta"), ("text", "number"), ("semana", "week")),
    ConceptSpec("customer", "Cliente", ("cliente", "customer", "customer name", "nombre cliente", "razon social", "razón social", "account name"), ("text",), ("cliente", "customer", "razon", "account"), ("codigo", "cod", "id")),
    ConceptSpec("customer_id", "Código cliente", ("cod cliente", "cod_cliente", "codigo cliente", "código cliente", "customer id", "customerid", "client id", "id cliente", "account id"), ("text", "number"), ("cliente", "customer", "client", "account", "id", "codigo", "cod")),
    ConceptSpec("product", "Producto", ("articulo", "artículo", "producto", "product", "product name", "descripcion producto", "descripción producto", "item", "item description", "sku description"), ("text",), ("producto", "product", "articulo", "item", "sku"), ("codigo", "cod", "id", "grupo")),
    ConceptSpec("product_group", "Grupo de producto", ("ctrl alm", "ctrl_alm", "grupo producto", "product group", "familia producto", "agrupador producto"), ("text",), ("grupo", "group", "familia", "agrupador", "ctrl")),
    ConceptSpec("category", "Categoría", ("categoria", "categoría", "category", "familia", "segmento producto", "product category"), ("text",), ("categoria", "category", "familia", "segmento")),
    ConceptSpec("seller", "Vendedor", ("vendedor", "ejecutivo", "asesor", "sales rep", "salesrep", "seller", "account executive", "representante"), ("text",), ("vendedor", "ejecutivo", "asesor", "sales", "seller", "representante"), ("codigo", "cod", "id")),
    ConceptSpec("zone", "Zona", ("zona", "region", "región", "territorio", "territory", "sales region"), ("text",), ("zona", "region", "territorio", "territory"), ("codigo", "cod", "id")),
    ConceptSpec("line", "Línea", ("linea", "línea", "cod linea", "cod_linea", "business line", "line"), ("text", "number"), ("linea", "line")),
    ConceptSpec("reference", "Referencia", ("refer", "referencia", "reference", "folio", "factura", "invoice", "transaction id", "operation id"), ("text", "number"), ("refer", "referencia", "folio", "invoice", "factura", "operation")),
    ConceptSpec("revenue", "Venta", ("importe venta", "importe_venta", "venta total", "ventas", "venta", "sales", "sales amount", "revenue", "net sales", "ventas netas", "monto venta", "monto facturado", "total facturado", "importe"), ("number",), ("venta", "sales", "revenue", "importe", "facturado", "monto"), ("costo", "cost", "utilidad", "profit", "flete", "tax", "iva")),
    ConceptSpec("quantity", "Cantidad", ("toneladas vendidas", "toneladas_vendidas", "cantidad", "unidades", "quantity", "qty", "volume", "volumen", "tons sold", "tonnage"), ("number",), ("cantidad", "unidades", "quantity", "qty", "toneladas", "volume", "volumen"), ("merma", "costo", "cost", "precio", "price")),
    ConceptSpec("actual", "Actual", ("actual", "real", "venta actual", "ventas actual", "actual sales", "toneladas vendidas actual", "toneladas_vendidas_actual"), ("number",), ("actual", "real"), ("budget", "presupuesto", "previous", "anterior")),
    ConceptSpec("budget", "Presupuesto", ("presupuesto", "budget", "budget sales", "venta presupuesto", "toneladas vendidas presupuesto", "toneladas_vendidas_presupuesto"), ("number",), ("presupuesto", "budget"), ("actual", "previous", "anterior")),
    ConceptSpec("previous", "Periodo anterior", ("anterior", "previous", "previous period", "periodo anterior", "venta anterior", "toneladas vendidas anterior", "toneladas_vendidas_anterior"), ("number",), ("anterior", "previous"), ("actual", "budget", "presupuesto")),
    ConceptSpec("cost", "Costo", ("costo", "coste", "cost", "costo total", "total cost"), ("number",), ("costo", "cost", "coste"), ("flete", "freight", "producto", "product", "unitario", "por tonelada", "xton")),
    ConceptSpec("profit", "Utilidad", ("utilidad", "ganancia", "profit", "gross profit", "net profit", "margen pesos", "margen $"), ("number",), ("utilidad", "ganancia", "profit", "margin"), ("pct", "porcentaje", "%")),
    ConceptSpec("freight", "Flete", ("costo flete", "costo_flete", "flete", "freight", "freight cost", "shipping cost", "costo transporte"), ("number",), ("flete", "freight", "shipping", "transporte"), ("por tonelada", "xton", "unitario", "rate")),
    ConceptSpec("freight_per_unit", "Flete por unidad", ("costo fletexton", "costo_fletexton", "costo flete por ton", "flete por tonelada", "freight per ton", "freight rate", "shipping rate"), ("number",), ("flete", "freight", "shipping", "ton", "rate", "unit")),
    ConceptSpec("product_cost", "Costo de producto", ("costo producto", "costo_producto", "product cost", "material cost", "costo mercancia"), ("number",), ("costo", "cost", "producto", "product", "material")),
    ConceptSpec("other_cost", "Otros costos", ("otros costos", "otros_costos", "other costs", "other cost", "gastos otros"), ("number",), ("otros", "other", "costos", "cost")),
    ConceptSpec("shrinkage", "Merma", ("toneladas mermadas", "toneladas_mermadas", "merma", "shrinkage", "waste", "loss quantity"), ("number",), ("merma", "shrinkage", "waste", "loss")),
    ConceptSpec("supplier", "Proveedor", ("proveedor", "supplier", "vendor", "nombre proveedor", "vendor name"), ("text",), ("proveedor", "supplier", "vendor"), ("codigo", "cod", "id")),
    ConceptSpec("warehouse", "Almacén", ("almacen", "almacén", "warehouse", "bodega", "store location"), ("text",), ("almacen", "warehouse", "bodega"), ("codigo", "cod", "id")),
    ConceptSpec("origin_city", "Ciudad origen", ("ciudad origen", "ciudad_origen", "origin city", "origen ciudad", "ship from"), ("text",), ("origen", "origin", "from", "ciudad", "city")),
    ConceptSpec("destination_city", "Ciudad destino", ("ciudad destino", "ciudad_destino", "destination city", "destino ciudad", "ship to"), ("text",), ("destino", "destination", "to", "ciudad", "city")),
)


def _name_score(col: str, spec: ConceptSpec) -> Tuple[float, str]:
    nc = _norm(col)
    ct = set(_tokens(col))
    aliases = [_norm(a) for a in spec.aliases]
    if nc in aliases:
        # Prefer a more specific exact alias (e.g. Toneladas_Mermadas over generic Merma).
        specificity = max(0, len(nc.split()) - 1) * 10.0
        return 100.0 + specificity, "alias exacto"

    # Context anchors: comparison/rate/id concepts must include their defining token.
    anchors = {
        "actual": {"actual", "real"},
        "budget": {"presupuesto", "budget"},
        "previous": {"anterior", "previous"},
        "freight_per_unit": {"rate", "ton", "xton", "unitario", "unidad"},
        "customer_id": {"id", "codigo", "cod"},
        "product_group": {"grupo", "group", "familia", "agrupador", "ctrl"},
    }
    if spec.key in anchors and not (ct & anchors[spec.key]):
        return 0.0, "falta token contextual obligatorio"

    best = 0.0
    reason = "sin coincidencia léxica"
    for a in aliases:
        at = set(a.split())
        if not at or not ct:
            continue
        overlap = len(at & ct) / len(at | ct)
        containment = len(at & ct) / len(at)
        score = 42.0 * overlap + 28.0 * containment
        # Whole-token containment is safer than substring containment.
        if at.issubset(ct):
            score += 18.0
        if score > best:
            best, reason = score, f"tokens similares a '{a}'"

    pos = sum(1 for t in spec.positive_tokens if _norm(t) in ct)
    neg = sum(1 for t in spec.negative_tokens if set(_tokens(t)).issubset(ct))
    best += min(12.0, pos * 3.0)
    best -= min(30.0, neg * 8.0)
    return max(0.0, best), reason


def _type_score(kind: str, spec: ConceptSpec) -> float:
    if kind in spec.kinds:
        return 12.0
    if kind == "empty":
        return -4.0
    return -30.0


def _content_score(s: pd.Series, kind: str, spec: ConceptSpec) -> float:
    nonnull = s.dropna()
    if nonnull.empty:
        return 0.0
    unique = int(nonnull.nunique(dropna=True))
    n = max(1, len(nonnull))
    ur = unique / n
    score = 0.0
    if spec.key.endswith("_id") or spec.key == "reference":
        if ur >= 0.6:
            score += 4.0
    if spec.key in {"customer", "product", "seller", "supplier", "warehouse", "zone", "category", "product_group"} and kind == "text":
        if unique >= 2:
            score += 2.0
    if spec.key in {"revenue", "quantity", "cost", "profit", "freight", "freight_per_unit", "product_cost", "other_cost", "shrinkage", "actual", "budget", "previous"} and kind == "number":
        numeric = pd.to_numeric(nonnull, errors="coerce").dropna()
        if len(numeric):
            finite = numeric.map(lambda x: math.isfinite(float(x))).mean()
            score += 3.0 * float(finite)
    if spec.key in {"date", "period_start", "period_end"} and kind == "date":
        score += 6.0
    return score


def _confidence(score: float, exact_name: bool) -> str:
    if exact_name and score >= 90:
        return "EXACT"
    if score >= 72:
        return "STRONG"
    if score >= 58:
        return "INFERRED"
    return "MISSING"


def resolve_semantic_map(df: pd.DataFrame) -> Dict[str, Any]:
    """Return an auditable, conservative semantic map.

    Only EXACT/STRONG/INFERRED mappings are auto-usable. AMBIGUOUS never auto-resolves.
    The resolver relies on whole-token aliases, dtype/content evidence and ambiguity margins;
    it intentionally avoids raw substring matching.
    """
    columns = [str(c) for c in df.columns]
    kinds = {c: _series_kind(df[c]) for c in columns}
    concepts: Dict[str, Dict[str, Any]] = {}

    for spec in SPECS:
        ranked: List[Dict[str, Any]] = []
        for c in columns:
            ns, why = _name_score(c, spec)
            score = ns + _type_score(kinds[c], spec) + _content_score(df[c], kinds[c], spec)
            ranked.append({"column": c, "score": round(score, 2), "kind": kinds[c], "reason": why, "exact_name": _norm(c) in {_norm(a) for a in spec.aliases}})
        ranked.sort(key=lambda x: (-x["score"], x["column"].lower()))
        top = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None
        if not top or top["score"] < 58:
            concepts[spec.key] = {"label": spec.label, "column": None, "confidence": "MISSING", "score": round(top["score"], 2) if top else 0.0, "reason": "sin evidencia suficiente", "alternatives": ranked[:3]}
            continue

        conf = _confidence(top["score"], bool(top["exact_name"]))
        # Close competitors make the mapping unsafe. Exact aliases remain exact only when unique.
        delta = top["score"] - (second["score"] if second else -999)
        close = second is not None and second["score"] >= 58 and delta < 8.0
        exact_collision = bool(top["exact_name"] and second and second["exact_name"] and delta < 3.0)
        if close or exact_collision:
            concepts[spec.key] = {"label": spec.label, "column": None, "confidence": "AMBIGUOUS", "score": top["score"], "reason": f"candidatos demasiado cercanos ({top['column']} vs {second['column']})", "alternatives": ranked[:3]}
        else:
            concepts[spec.key] = {"label": spec.label, "column": top["column"], "confidence": conf, "score": top["score"], "reason": top["reason"], "alternatives": ranked[:3]}

    # Cross-concept safety rules for known collision families.
    freight = concepts.get("freight", {})
    freight_rate = concepts.get("freight_per_unit", {})
    if freight.get("column") and freight.get("column") == freight_rate.get("column"):
        # The total freight concept must not reuse a rate column.
        nc = set(_tokens(freight["column"]))
        if {"ton"} & nc or {"xton"} & nc or "rate" in nc or "unitario" in nc:
            concepts["freight"] = {**freight, "column": None, "confidence": "AMBIGUOUS", "reason": "posible tarifa de flete, no costo total"}

    usable = {k: v.get("column") if v.get("confidence") in {"EXACT", "STRONG", "INFERRED"} else None for k, v in concepts.items()}
    return {
        "version": "r10.2",
        "policy": "name+dtype+content+context; ambiguous=no-auto-calc",
        "concepts": concepts,
        "usable": usable,
        "columns": [{"name": c, "kind": kinds[c]} for c in columns],
    }


def usable_semantic_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return dict(resolve_semantic_map(df)["usable"])
