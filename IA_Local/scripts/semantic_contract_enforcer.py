from __future__ import annotations

from typing import Any, Dict, List
import re
import unicodedata

from semantic_layer import resolve_semantic_map

VERSION = "r10.11.2"

def norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9_%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _has(prompt_n: str, *terms: str) -> bool:
    return any(norm(t) in prompt_n for t in terms)

def _filter(col: str | None, label: str, role: str) -> Dict[str, Any] | None:
    if not col:
        return None
    return {"column": col, "label": label, "role": role}

def enforce_semantic_contract(plan: Dict[str, Any], df, prompt: str) -> Dict[str, Any]:
    out = dict(plan or {})
    smap = resolve_semantic_map(df)
    s = dict(smap.get("usable") or {})
    p = norm(prompt)

    roles = dict(out.get("semantic_roles") or {})
    strict_to_universal = {
        "date": "date",
        "customer_id": "customer_id",
        "customer": "customer",
        "product": "product",
        "line": "line",
        "zone": "zone",
        "seller": "seller",
        "supplier": "supplier",
        "warehouse": "warehouse",
        "category": "category",
        "quantity": "quantity",
        "revenue": "revenue",
        "cost": "cost",
        "profit": "profit",
        "freight": "freight",
    }
    for strict_key, role_key in strict_to_universal.items():
        if s.get(strict_key):
            roles[role_key] = s[strict_key]
    if s.get("reference"):
        roles["transaction_id"] = s["reference"]
    out["semantic_roles"] = roles

    broad = _has(p, "dashboard", "analiza completamente", "analisis completo", "kpis ejecutivos", "salida final")
    requested_business = broad or _has(
        p, "toneladas vendidas", "venta total", "costo total", "utilidad total",
        "margen %", "utilidad por tonelada", "costo por tonelada",
        "precio promedio por tonelada", "costo de producto", "costo de fletes",
        "otros costos", "toneladas mermadas"
    )

    if requested_business:
        kpis: List[Dict[str, Any]] = []
        def add(item):
            if item and all(x.get("label") != item.get("label") for x in kpis):
                kpis.append(item)

        q, rev, cost, profit = s.get("quantity"), s.get("revenue"), s.get("cost"), s.get("profit")
        freight = s.get("freight")
        if q: add({"key":"quantity","label":"TONELADAS VENDIDAS","op":"sum","column":q,"ready":True,"format":"number"})
        if rev: add({"key":"revenue","label":"VENTA TOTAL","op":"sum","column":rev,"ready":True,"format":"currency"})
        if cost: add({"key":"cost","label":"COSTO TOTAL","op":"sum","column":cost,"ready":True,"format":"currency"})
        if profit: add({"key":"profit","label":"UTILIDAD TOTAL","op":"sum","column":profit,"ready":True,"format":"currency"})
        if profit and rev:
            add({"key":"margin_pct","label":"MARGEN %","op":"ratio_pct","numerator":profit,"denominator":rev,"ready":True,"format":"percent"})
        if profit and q:
            add({"key":"profit_per_unit","label":"UTILIDAD POR TONELADA","op":"ratio","numerator":profit,"denominator":q,"ready":True,"format":"currency"})
        if cost and q:
            add({"key":"cost_per_unit","label":"COSTO POR TONELADA","op":"ratio","numerator":cost,"denominator":q,"ready":True,"format":"currency"})
        if rev and q:
            add({"key":"price_per_unit","label":"PRECIO PROMEDIO POR TONELADA","op":"ratio","numerator":rev,"denominator":q,"ready":True,"format":"currency"})
        if s.get("product_cost"):
            add({"key":"product_cost","label":"COSTO DE PRODUCTO","op":"sum","column":s["product_cost"],"ready":True,"format":"currency"})
        if freight:
            add({"key":"freight","label":"COSTO DE FLETES","op":"sum","column":freight,"ready":True,"format":"currency"})
        if s.get("other_cost"):
            add({"key":"other_cost","label":"OTROS COSTOS","op":"sum","column":s["other_cost"],"ready":True,"format":"currency"})
        if s.get("shrinkage"):
            add({"key":"shrinkage","label":"TONELADAS MERMADAS","op":"sum","column":s["shrinkage"],"ready":True,"format":"number"})
        if s.get("customer_id"):
            add({"key":"unique_customers","label":"CLIENTES ÚNICOS","op":"nunique","column":s["customer_id"],"ready":True,"format":"integer"})
        if s.get("reference"):
            add({"key":"operations","label":"OPERACIONES / REFERENCIAS","op":"nunique","column":s["reference"],"ready":True,"format":"integer"})
        out["kpis"] = kpis

    wanted_filters = [
        _filter(s.get("date"), "Fecha", "date"),
        _filter(s.get("week"), "Semana", "week"),
        _filter(s.get("zone"), "Zona", "zone"),
        _filter(s.get("category"), "Categoria", "category"),
        _filter(s.get("seller"), "Vendedor", "seller"),
        _filter(s.get("customer"), "Cliente", "customer"),
        _filter(s.get("product"), "Articulo", "product"),
        _filter(s.get("product_group"), "ctrl_alm", "product_group"),
        _filter(s.get("supplier"), "Proveedor", "supplier"),
        _filter(s.get("warehouse"), "Almacen", "warehouse"),
        _filter(s.get("origin_city"), "Ciudad_Origen", "origin_city"),
        _filter(s.get("destination_city"), "Ciudad_Destino", "destination_city"),
    ]

    collect_col = next((str(c) for c in df.columns if norm(c) == norm("Cliente_Recoge")), None)
    if collect_col:
        wanted_filters.append(_filter(collect_col, "Cliente_Recoge", "customer_pickup"))

    if broad or _has(p, "filtros globales", "fecha desde", "fecha hasta", "ctrl alm", "cliente recoge"):
        dedup = []
        seen = set()
        for f in wanted_filters:
            if f and f["column"] not in seen:
                seen.add(f["column"])
                dedup.append(f)
        out["filters"] = dedup

    if s.get("quantity"):
        for ch in out.get("charts") or []:
            if ch.get("measure") and ch.get("op") in {"sum","avg"}:
                label = norm(ch.get("title"))
                if any(x in label for x in ("cantidad volumen","toneladas","evolucion de cantidad")):
                    ch["measure"] = s["quantity"]
                    ch["title"] = ch.get("title","").replace("Cantidad / Volumen", "Toneladas Vendidas")

    out["semantic_contract"] = {
        "version": VERSION,
        "policy": "strict_semantic_map_precedence",
        "quantity": s.get("quantity"),
        "profit": s.get("profit"),
        "freight": s.get("freight"),
        "reference": s.get("reference"),
        "customer_id": s.get("customer_id"),
        "product_group": s.get("product_group"),
        "week": s.get("week"),
    }
    out["strict_semantic_map"] = smap
    warnings = list(out.get("warnings") or [])
    msg = "R10.11.2: el mapa semántico estricto tiene precedencia sobre inferencias heurísticas."
    if msg not in warnings:
        warnings.append(msg)
    out["warnings"] = warnings
    return out
