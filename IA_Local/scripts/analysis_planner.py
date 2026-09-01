from __future__ import annotations
from typing import Any, Dict, Iterable, List

PLAN_VERSION = "r10.14a"
SUPPORTED = "SUPPORTED"
DERIVABLE = "DERIVABLE"
PARTIAL = "PARTIAL"
BLOCKED = "BLOCKED"

_ANALYSIS_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "executive_summary": {"operator":"executive_summary","dimensions":[],"metrics":[],"optional_metrics":["revenue","cost","profit","margin_pct","quantity"]},
    "trend": {"operator":"time_trend","dimensions":["date"],"metrics":[],"optional_metrics":["revenue","profit","quantity","operations"]},
    "ranking": {"operator":"dimension_ranking","dimensions":[],"metrics":[],"optional_metrics":["revenue","profit","margin_pct","quantity"]},
    "customer_profile": {"operator":"customer_profile","dimensions":["customer"],"metrics":[],"optional_metrics":["revenue","profit","margin_pct","quantity","operations"]},
    "lost_customers": {"operator":"customer_deterioration","dimensions":["customer","date"],"metrics":["revenue"],"optional_metrics":["profit","quantity","operations"]},
    "profitability": {"operator":"profitability_analysis","dimensions":[],"metrics":["revenue"],"optional_metrics":["cost","profit","margin_pct","profit_per_unit"]},
    "risks": {"operator":"risk_scan","dimensions":[],"metrics":[],"optional_metrics":["revenue","profit","margin_pct","quantity"]},
    "opportunities": {"operator":"opportunity_scan","dimensions":[],"metrics":[],"optional_metrics":["revenue","profit","margin_pct","quantity"]},
    "routes": {"operator":"route_analysis","dimensions":["origin_city","destination_city"],"metrics":[],"optional_metrics":["quantity","revenue","freight"]},
    "warehouse_movement": {"operator":"warehouse_movement","dimensions":["warehouse"],"metrics":["quantity"],"optional_metrics":["revenue","profit"]},
    "origin_share": {"operator":"origin_share","dimensions":["origin_city"],"metrics":["quantity"],"optional_metrics":["revenue"]},
    "destination_share": {"operator":"destination_share","dimensions":["destination_city"],"metrics":["quantity"],"optional_metrics":["revenue"]},
    "monthly_movement": {"operator":"monthly_movement","dimensions":["date"],"metrics":["quantity"],"optional_metrics":["revenue","profit"]},
    "customer_pickup": {"operator":"customer_pickup","dimensions":["customer_pickup"],"metrics":["quantity"],"optional_metrics":["revenue"]},
    "freight_analysis": {"operator":"freight_analysis","dimensions":[],"metrics":["freight"],"optional_metrics":["freight_per_unit","quantity"]},
    "aging": {"operator":"aging","dimensions":["customer"],"metrics":[],"optional_metrics":["overdue_balance","days_overdue"]},
    "collections": {"operator":"collections","dimensions":["customer"],"metrics":[],"optional_metrics":["overdue_balance"]},
    "critical_stock": {"operator":"critical_stock","dimensions":["product"],"metrics":[],"optional_metrics":["stock"]},
    "inventory_turnover": {"operator":"inventory_turnover","dimensions":["product","date"],"metrics":["stock"],"optional_metrics":["quantity"]},
    "obsolete_inventory": {"operator":"obsolete_inventory","dimensions":["product","date"],"metrics":["stock"],"optional_metrics":[]},
    "data_quality": {"operator":"data_quality","dimensions":[],"metrics":[],"optional_metrics":[]},
    "detail": {"operator":"transaction_detail","dimensions":[],"metrics":[],"optional_metrics":[]},
}

def _component_index(components: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(c.get("id")): c for c in (components or []) if isinstance(c, dict) and c.get("id")}

def _evidence(*, kind: str, key: str, roles: Dict[str, Any], index: Dict[str, Dict[str, Any]], required: bool) -> Dict[str, Any]:
    component_id = f"{'kpi' if kind == 'metric' else 'filter'}:{key}"
    component = index.get(component_id)
    if component:
        status = str(component.get("status") or BLOCKED).upper()
        return {"kind":kind,"key":key,"required":bool(required),"status":status,"source_columns":list(component.get("source_columns") or []),"formula":component.get("formula"),"dependencies":list(component.get("dependencies") or []),"rule":dict(component.get("rule") or {}),"reason":component.get("reason"),"provenance":dict(component.get("provenance") or {})}
    if kind == "dimension" and roles.get(key):
        return {"kind":kind,"key":key,"required":bool(required),"status":SUPPORTED,"source_columns":[roles[key]],"formula":None,"dependencies":[],"rule":{},"reason":None,"provenance":{"source":"semantic_role","confidence":1.0}}
    return {"kind":kind,"key":key,"required":bool(required),"status":BLOCKED if required else "UNAVAILABLE","source_columns":[],"formula":None,"dependencies":[],"rule":{},"reason":f"No governed capability is available for {kind} '{key}'.","provenance":{"source":"r10.14a_analytical_planner","confidence":1.0}}

def _task(analysis_key: str, *, roles: Dict[str, Any], index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    spec = dict(_ANALYSIS_REQUIREMENTS.get(analysis_key) or {})
    analysis_component = index.get(f"analysis:{analysis_key}") or {}
    required_dims = list(spec.get("dimensions") or [])
    required_metrics = list(spec.get("metrics") or [])
    optional_metrics = list(spec.get("optional_metrics") or [])
    evidence: List[Dict[str, Any]] = []
    for key in required_dims:
        evidence.append(_evidence(kind="dimension",key=key,roles=roles,index=index,required=True))
    for key in required_metrics:
        evidence.append(_evidence(kind="metric",key=key,roles=roles,index=index,required=True))
    optional_evidence = [_evidence(kind="metric",key=key,roles=roles,index=index,required=False) for key in optional_metrics]
    blocked_required = [e for e in evidence if e["status"] not in {SUPPORTED,DERIVABLE}]
    available_optional = [e for e in optional_evidence if e["status"] in {SUPPORTED,DERIVABLE}]
    component_status = str(analysis_component.get("status") or "").upper()
    if blocked_required or component_status == BLOCKED:
        status = BLOCKED
    elif optional_metrics and not available_optional and not evidence:
        status = PARTIAL
    else:
        status = SUPPORTED
    reason = None
    if blocked_required:
        reason = "Blocked because required governed evidence is unavailable: " + ", ".join(f"{e['kind']}:{e['key']}" for e in blocked_required)
    elif component_status == BLOCKED:
        reason = analysis_component.get("reason") or "Analysis capability is blocked."
    return {"id":f"analysis_plan:{analysis_key}","analysis":analysis_key,"operator":spec.get("operator") or analysis_key,"status":status,"required_dimensions":required_dims,"required_metrics":required_metrics,"optional_metrics":optional_metrics,"evidence":evidence,"optional_evidence":optional_evidence,"blocked_evidence":blocked_required,"reason":reason,"provenance":{"source":"r10.14a_governed_analytical_planner","confidence":1.0}}

def build_governed_analytical_plan(*, intent: Dict[str, Any], roles: Dict[str, Any], components: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Build an auditable analytical plan without inventing business math."""
    index = _component_index(components)
    requested_analyses = list(dict.fromkeys(intent.get("analyses") or []))
    tasks = [_task(key,roles=dict(roles or {}),index=index) for key in requested_analyses]
    blocked = [t for t in tasks if t["status"] == BLOCKED]
    partial = [t for t in tasks if t["status"] == PARTIAL]
    ready = [t for t in tasks if t["status"] == SUPPORTED]
    return {"schema_version":PLAN_VERSION,"mode":"governed-capability-driven","requested_analyses":requested_analyses,"task_count":len(tasks),"ready_count":len(ready),"partial_count":len(partial),"blocked_count":len(blocked),"tasks":tasks,"blocked":blocked,"governance":{"uses_resolved_capabilities_only":True,"arbitrary_formula_evaluation":False,"blocked_metrics_are_not_promoted":True}}
