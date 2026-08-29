from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re, unicodedata
import pandas as pd
from prompt_intelligence import parse_prompt_intelligence
from capability_rules import RULESET_VERSION, select_rule, rule_public_metadata

SCHEMA_VERSION="r10.13a"
SUPPORTED="SUPPORTED"
DERIVABLE="DERIVABLE"
BLOCKED="BLOCKED"

def norm(v: Any) -> str:
    s=str(v or "").strip().lower()
    s="".join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9_]+","_",s).strip("_")

def _strict_map(df):
    try:
        from semantic_layer import resolve_semantic_map
        return resolve_semantic_map(df)
    except Exception:
        return {"usable":{},"concepts":{}}

def _governed_roles():
    try:
        from enterprise_ai.semantic_registry import current_context
        return dict((current_context() or {}).get("roles") or {})
    except Exception:
        return {}

def _analytic_context():
    try:
        from enterprise_ai import analytic_rules as ar
        getter=getattr(ar,"current_context",None) or getattr(ar,"current_analytic_context",None)
        return dict(getter() or {}) if getter else {}
    except Exception:
        return {}

def _bridge(roles):
    out=dict(roles or {})
    if out.get("total_cost") and not out.get("cost"): out["cost"]=out["total_cost"]
    if out.get("cost") and not out.get("total_cost"): out["total_cost"]=out["cost"]
    if out.get("sales") and not out.get("revenue"): out["revenue"]=out["sales"]
    if out.get("revenue") and not out.get("sales"): out["sales"]=out["revenue"]
    if out.get("invoice") and not out.get("transaction_id"): out["transaction_id"]=out["invoice"]
    if out.get("reference") and not out.get("transaction_id"): out["transaction_id"]=out["reference"]
    return out


def _is_invalid_freight_mapping(role: str, col: Any) -> bool:
    if role != "freight" or not col:
        return False
    n = norm(col)
    # Negative semantic evidence: "sin flete" explicitly means excluding freight.
    return (
        "sin_flete" in n
        or "without_freight" in n
        or "excluding_freight" in n
        or n in {"costo_sin_flete","cost_without_freight"}
    )

def _merge_roles(df, semantic_map=None, semantic_roles=None, semantic_context=None):
    cols={str(c) for c in df.columns}
    inferred=_bridge(dict((semantic_map or _strict_map(df)).get("usable") or {}))
    provided=_bridge(dict(semantic_roles or {}))
    governed=_bridge(dict((semantic_context or {}).get("roles") or _governed_roles()))
    roles={}; sources={}
    for source_name, mapping in (("semantic_fallback",inferred),("semantic_contract",provided),("governed_semantic_definition",governed)):
        for role,col in mapping.items():
            if col in cols:
                # Never accept an explicit contradiction such as Costo_Sin_Flete -> freight.
                # Governed mappings still win when semantically valid.
                if _is_invalid_freight_mapping(role, col):
                    continue
                roles[role]=col; sources[role]=source_name
    # Exact operational aliases that are unambiguous and safe to expose.
    if not roles.get("customer_pickup"):
        by_norm={norm(c):str(c) for c in df.columns}
        for alias in ("cliente_recoge","customer_pickup","pickup_customer"):
            if alias in by_norm:
                roles["customer_pickup"]=by_norm[alias]; sources["customer_pickup"]="exact_column_alias"; break
    return _bridge(roles),sources

def _cap(key,kind,status,role=None,columns=None,formula=None,reason=None,source="capability_resolver",confidence=1.0,dependencies=None):
    return {
      "id":f"{kind}:{key}","type":kind,"requested_by_prompt":True,"status":status,
      "semantic_role":role or key,"source_columns":list(columns or []),"formula":formula,
      "title":key.replace("_"," ").title(),"reason":reason,
      "provenance":{"source":source,"confidence":confidence},"dependencies":list(dependencies or [])
    }

DIRECT={"revenue":"revenue","quantity":"quantity","cost":"cost","profit":"profit","freight":"freight","stock":"stock","overdue_balance":"balance","days_overdue":"days_overdue"}
DIMS={"date":"date","week":"week","customer":"customer","product":"product","product_group":"product_group","line":"line","seller":"seller","zone":"zone","supplier":"supplier","warehouse":"warehouse","origin_city":"origin_city","destination_city":"destination_city","invoice":"transaction_id","customer_pickup":"customer_pickup","employee":"employee"}

def _direct_metric(key,roles,sources):
    role=DIRECT.get(key); col=roles.get(role) if role else None
    return _cap(key,"kpi",SUPPORTED,role=role,columns=[col],source=sources.get(role,"direct_column")) if col else None

def _derived_metric(key,roles,sources=None):
    governed_roles={r for r,src in dict(sources or {}).items() if src in {"governed_semantic_definition","validated_analytic_rule"}}
    rule, missing = select_rule(key, roles, governed_roles)
    if not rule:
        return None
    deps=list(rule.get("dependencies") or [])
    cols=[roles.get(dep) for dep in deps if roles.get(dep)]
    cap=_cap(
        key,"kpi",DERIVABLE,columns=cols,formula=rule.get("formula"),
        source="capability_rule_registry",dependencies=deps,
    )
    cap["rule"]=rule_public_metadata(rule)
    cap["output_format"]=rule.get("format") or "number"
    cap["execution"]={"operator":rule.get("operator"),"dependency_roles":deps,"zero_division":"N/D"}
    return cap

def _authorized_freight(analytic_context=None):
    ctx=dict(analytic_context or _analytic_context())
    for b in list(ctx.get("bindings") or [])+list(ctx.get("rules") or []):
        target=norm(b.get("target") or b.get("metric") or b.get("name"))
        expr=str(b.get("expression") or b.get("formula") or b.get("rule") or "").strip()
        if target in {"freight","flete","freight_total","costo_flete"} and expr:
            return _cap("freight","kpi",DERIVABLE,formula=expr,source="validated_analytic_rule",dependencies=["validated_analytic_rule"])
    return None

def resolve_metric(key,roles,sources,analytic_context=None):
    direct=_direct_metric(key,roles,sources)
    if direct:return direct
    if key=="freight":
        auth=_authorized_freight(analytic_context)
        if auth:return auth
    d=_derived_metric(key,roles,sources)
    if d:return d
    rule, missing = select_rule(key, roles, {r for r,src in sources.items() if src in {"governed_semantic_definition","validated_analytic_rule"}})
    reason=f"No direct semantic role or safe deterministic derivation exists for '{key}'."
    if missing:
        reason += " Missing dependencies: " + ", ".join(missing)
    return _cap(key,"kpi",BLOCKED,reason=reason,dependencies=[x.replace("governed:","") for x in missing])

def resolve_dimension(key,roles,sources):
    role=DIMS.get(key,key); col=roles.get(role)
    if col:return _cap(key,"filter",SUPPORTED,role=role,columns=[col],source=sources.get(role,"direct_column"))
    if key=="week" and roles.get("date"):
        return _cap(key,"filter",DERIVABLE,role="week",columns=[roles["date"]],formula="ISO week(date)",source="derived_dimension_rule",dependencies=["date"])
    return _cap(key,"filter",BLOCKED,role=role,reason=f"No semantic column or safe derivation exists for dimension '{key}'.")

def resolve_analysis(key,roles):
    req={
      "executive_summary":[],"trend":["date"],"ranking":[],
      "customer_profile":["customer"],"lost_customers":["customer","date"],
      "profitability":["revenue"],"risks":[],"opportunities":[],
      "routes":["origin_city","destination_city"],
      "warehouse_movement":["warehouse","quantity"],
      "origin_share":["origin_city","quantity"],
      "destination_share":["destination_city","quantity"],
      "monthly_movement":["date","quantity"],
      "customer_pickup":["customer_pickup","quantity"],
      "freight_analysis":["freight"],"aging":["customer"],
      "collections":["customer"],"critical_stock":["product"],
      "inventory_turnover":["product","date","stock"],"obsolete_inventory":["product","date","stock"],
      "data_quality":[],"detail":[]
    }.get(key,[])
    missing=[r for r in req if not roles.get(r)]
    return _cap(key,"analysis",BLOCKED,reason="Missing required semantic roles: "+", ".join(missing),dependencies=req) if missing else _cap(key,"analysis",SUPPORTED,columns=[roles[r] for r in req if roles.get(r)],dependencies=req)

def _pages(intent,caps):
    explicit=list(intent.get("explicit_pages") or [])
    requested=list(intent.get("pages") or [])
    if explicit:
        out=[{"id":str(p.get("id")),"title":str(p.get("title") or p.get("id")),"components":[]} for p in explicit if p.get("id")]
    else:
        if not requested:
            requested={"sales":["summary","customers","analysis"],"logistics":["summary","logistics"],"receivables":["summary","receivables"],"inventory":["summary","inventory"],"finance":["summary","analysis"],"purchasing":["summary","analysis"],"hr":["summary","analysis"],"generic":["summary"]}.get(intent.get("domain"),["summary"])
        titles={"summary":"Resumen Ejecutivo","customers":"Clientes","analysis":"Análisis","operations":"Facturas / Operaciones","customer_profile":"Perfil de Cliente","line_analysis":"Análisis por Línea","lost_customers":"Clientes Perdidos","logistics":"Logística","inventory":"Inventario","receivables":"Cobranza"}
        out=[{"id":p,"title":titles.get(p,p.replace("_"," ").title()),"components":[]} for p in requested]
    if not out:
        out=[{"id":"summary","title":"Resumen Ejecutivo","components":[]}]

    ids={p["id"] for p in out}
    def choose(c):
        role=c.get("semantic_role")
        cid=c.get("id")
        typ=c.get("type")
        # Explicit logistics architecture has deterministic semantic destinations.
        if "warehouses" in ids and (role=="warehouse" or cid=="analysis:warehouse_movement"):
            return "warehouses"
        if "routes" in ids and cid=="analysis:routes":
            return "routes"
        if "origin_destination" in ids and (role in {"origin_city","destination_city"} or cid in {"analysis:origin_share","analysis:destination_share"}):
            return "origin_destination"
        if "evolution" in ids and (role=="date" or cid in {"analysis:trend","analysis:monthly_movement"}):
            return "evolution"
        if "logistics_detail" in ids and (cid in {"analysis:detail","analysis:customer_pickup"} or role=="customer_pickup" or typ=="table"):
            return "logistics_detail"
        if "data_quality" in ids and cid=="analysis:data_quality":
            return "data_quality"
        if "logistics_summary" in ids and (typ in {"kpi","deliverable"} or role=="quantity"):
            return "logistics_summary"
        # Existing commercial/domain routing remains backward compatible.
        if role in {"customer","active_customers"} and "customers" in ids:return "customers"
        if role in {"freight","origin_city","destination_city"} and "logistics" in ids:return "logistics"
        if role=="lost_customers" and "lost_customers" in ids:return "lost_customers"
        if typ=="analysis" and "analysis" in ids:return "analysis"
        if "summary" in ids:return "summary"
        if "logistics_summary" in ids:return "logistics_summary"
        if "inventory" in ids:return "inventory"
        return out[0]["id"]
    for c in caps:
        target=choose(c)
        next((p for p in out if p["id"]==target),out[0])["components"].append(c["id"])
    return out

def _charts_from_analyses(caps):
    definitions={
      "analysis:trend":("Evolución temporal","line"),
      "analysis:monthly_movement":("Evolución mensual del movimiento","line"),
      "analysis:warehouse_movement":("Movimiento por almacén","bar"),
      "analysis:origin_share":("Participación por ciudad origen","bar"),
      "analysis:destination_share":("Participación por ciudad destino","bar"),
      "analysis:routes":("Rutas principales","bar"),
      "analysis:customer_pickup":("Clientes que recogen","bar"),
      "analysis:inventory_turnover":("Rotación por producto","bar"),
      "analysis:obsolete_inventory":("Productos obsoletos / sin movimiento","bar"),
    }
    out=[]
    for c in caps:
        if c.get("id") not in definitions: continue
        title,kind=definitions[c["id"]]
        out.append({"id":"chart:"+c["id"].split(":",1)[1],"type":kind,"title":title,"status":c.get("status"),"source_columns":list(c.get("source_columns") or []),"reason":c.get("reason"),"provenance":dict(c.get("provenance") or {})})
    return out

def build_dashboard_spec(df,prompt,*,sheet="",semantic_map=None,semantic_roles=None,semantic_context=None,analytic_context=None,source_context=None):
    intent=parse_prompt_intelligence(prompt)
    roles,sources=_merge_roles(df,semantic_map,semantic_roles,semantic_context)
    caps=[]
    for k in intent.get("metrics") or []: caps.append(resolve_metric(k,roles,sources,analytic_context))
    for k in intent.get("dimensions") or []: caps.append(resolve_dimension(k,roles,sources))
    for k in intent.get("analyses") or []: caps.append(resolve_analysis(k,roles))
    existing={c["id"] for c in caps}
    for k in intent.get("filters") or []:
        c=resolve_dimension(k,roles,sources); c["id"]=f"filter:{k}"; c["type"]="filter"
        if c["id"] not in existing: caps.append(c); existing.add(c["id"])
    for k in intent.get("tables") or []: caps.append(_cap(k,"table",SUPPORTED,source="prompt_specification"))
    for k in intent.get("deliverables") or []: caps.append(_cap(k,"deliverable",SUPPORTED,source="prompt_specification"))
    requested=len(caps); supported=sum(c["status"]==SUPPORTED for c in caps); derivable=sum(c["status"]==DERIVABLE for c in caps); blocked=sum(c["status"]==BLOCKED for c in caps)
    fulfilled=supported+derivable; percent=round(fulfilled/requested*100,2) if requested else 100.0
    reqsrc=intent.get("requested_source"); resolved=sheet or None
    if reqsrc and resolved and norm(reqsrc)!=norm(resolved): reason="requested_source_differs_from_resolved_source; current source-selection contract resolved the dataset"
    elif reqsrc: reason="requested_source_matches_resolved_source"
    else: reason="auto_discovery_or_existing_transactional_selector"
    blocked_items=[c for c in caps if c["status"]==BLOCKED]; derived=[c for c in caps if c["status"]==DERIVABLE]
    return {
      "schema_version":SCHEMA_VERSION,"domain":intent.get("domain","generic"),"prompt":str(prompt or ""),"intent":intent,
      "source":{"requested_source":reqsrc,"sheet":resolved,"resolved_source":resolved,"resolution_reason":(source_context or {}).get("resolution_reason") or reason,"rows":int(len(df)),"columns":[str(c) for c in df.columns]},
      "pages":_pages(intent,caps),"filters":[c for c in caps if c["type"]=="filter"],"kpis":[c for c in caps if c["type"]=="kpi"],"charts":_charts_from_analyses(caps),
      "tables":[c for c in caps if c["type"]=="table"],"analyses":[c for c in caps if c["type"]=="analysis"],"components":caps,"blocked":blocked_items,
      "coverage":{"requested":requested,"supported":supported,"derivable":derivable,"blocked":blocked,"fulfilled":fulfilled,"percent":percent},
      "provenance":{"policy":"governed_semantics > validated_business_rule > direct_semantic_contract > safe_derivation > fallback_semantics > BLOCKED","semantic_roles":roles,"role_sources":sources,
                    "ruleset_version":RULESET_VERSION,
                    "derived":[{"id":c["id"],"formula":c.get("formula"),"inputs":c.get("source_columns"),"dependencies":c.get("dependencies"),"rule":c.get("rule"),"execution":c.get("execution"),"source":c["provenance"]["source"]} for c in derived],
                    "blocked":[{"id":c["id"],"reason":c.get("reason")} for c in blocked_items]}
    }
