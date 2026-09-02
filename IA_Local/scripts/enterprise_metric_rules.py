from __future__ import annotations
import hashlib, json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ENTERPRISE_METRIC_RULES_VERSION = "r10.15e"
_ALLOWED_OPERATORS = {"sum_columns"}
_ALLOWED_SCOPE_KEYS = {"tenant_id","company_id","business_unit_id","branch_id"}
_FORBIDDEN_RULE_KEYS = {"formula","expression","python","code","eval"}

def _default_registry_path():
    return Path(__file__).resolve().parents[1] / "config" / "enterprise_metric_rules.json"

def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _parse_date(v):
    if v in (None,""): return None
    try: return date.fromisoformat(str(v))
    except Exception: return None

def _base(p):
    return {"schema_version":ENTERPRISE_METRIC_RULES_VERSION,"status":"EMPTY","path":str(p),
            "registry_id":None,"ruleset_version":None,"rule_count":0,"rules":[],
            "fingerprint_sha256":None,"errors":[],
            "governance":{"fail_closed":True,"explicit_rules_only":True,
            "arbitrary_formula_evaluation":False,"whitelist_operators_only":True,
            "allowed_operators":sorted(_ALLOWED_OPERATORS),"scope_guard":True,
            "effective_date_guard":True,"missing_source_columns_block_execution":True,
            "default_enterprise_metric_rules_are_never_invented":True}}

def _validate_rule(rule,index):
    e=[]; rid=str(rule.get("rule_id") or "").strip()
    if not rid: return [f"rule_{index}:missing_rule_id"]
    bad=sorted(k for k in _FORBIDDEN_RULE_KEYS if k in rule)
    if bad: e.append(f"rule_{index}:forbidden_keys:{rid}:{','.join(bad)}")
    if not str(rule.get("metric") or "").strip(): e.append(f"rule_{index}:missing_metric:{rid}")
    op=str(rule.get("operator") or "")
    if op not in _ALLOWED_OPERATORS: e.append(f"rule_{index}:unsupported_operator:{rid}:{op}")
    cols=rule.get("source_columns")
    if not isinstance(cols,list) or not cols or any(not str(c).strip() for c in cols):
        e.append(f"rule_{index}:source_columns_required:{rid}")
    scope=rule.get("scope") or {}
    if not isinstance(scope,dict): e.append(f"rule_{index}:scope_must_be_object:{rid}")
    else:
        u=sorted(set(scope)-_ALLOWED_SCOPE_KEYS)
        if u: e.append(f"rule_{index}:unsupported_scope_keys:{rid}:{','.join(u)}")
    ef,et=rule.get("effective_from"),rule.get("effective_to")
    pef,pet=_parse_date(ef),_parse_date(et)
    if ef not in (None,"") and pef is None: e.append(f"rule_{index}:invalid_effective_from:{rid}")
    if et not in (None,"") and pet is None: e.append(f"rule_{index}:invalid_effective_to:{rid}")
    if pef and pet and pef>pet: e.append(f"rule_{index}:invalid_effective_range:{rid}")
    try:
        p=int(rule.get("priority") or 0)
        if p<0: e.append(f"rule_{index}:negative_priority:{rid}")
    except Exception: e.append(f"rule_{index}:invalid_priority:{rid}")
    if str(rule.get("approval_status") or "")!="APPROVED": e.append(f"rule_{index}:rule_not_approved:{rid}")
    return e

def load_governed_enterprise_metric_rule_registry(path: Optional[str]=None)->Dict[str,Any]:
    p=Path(path) if path else _default_registry_path(); base=_base(p)
    if not p.exists(): return base
    try: raw=p.read_bytes()
    except Exception as exc:
        o=dict(base); o["status"]="ERROR"; o["errors"]=[f"read_error:{type(exc).__name__}"]; return o
    d=_fingerprint(raw)
    try: data=json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=d; o["errors"]=[f"json_error:{type(exc).__name__}"]; return o
    if not isinstance(data,dict):
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=d; o["errors"]=["registry_root_must_be_object"]; return o
    if str(data.get("schema_version") or "")!=ENTERPRISE_METRIC_RULES_VERSION:
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=d; o["errors"]=["unsupported_registry_schema"]; return o
    rules=data.get("rules")
    if not isinstance(rules,list):
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=d; o["errors"]=["rules_must_be_array"]; return o
    seen=set(); clean=[]; errors=[]
    for i,rr in enumerate(rules):
        if not isinstance(rr,dict): errors.append(f"rule_{i}:rule_must_be_object"); continue
        r=dict(rr); rid=str(r.get("rule_id") or "").strip()
        if rid and rid in seen: errors.append(f"rule_{i}:duplicate_rule_id:{rid}"); continue
        if rid: seen.add(rid)
        re=_validate_rule(r,i)
        if re: errors.extend(re); continue
        clean.append(r)
    if errors:
        o=dict(base); o.update({"status":"INVALID","registry_id":data.get("registry_id"),
        "ruleset_version":data.get("ruleset_version"),"fingerprint_sha256":d,"errors":errors}); return o
    o=dict(base); o.update({"status":"LOADED" if clean else "EMPTY","registry_id":data.get("registry_id"),
    "ruleset_version":data.get("ruleset_version"),"rule_count":len(clean),"rules":clean,
    "fingerprint_sha256":d}); return o

def _scope_matches(scope,context):
    for k,v in dict(scope or {}).items():
        if k not in _ALLOWED_SCOPE_KEYS: return False
        if v in (None,"","*"): continue
        if str(context.get(k) or "")!=str(v): return False
    return True

def resolve_governed_enterprise_metric_rule(*,metric,available_columns,rule_registry=None,context=None,as_of=None):
    reg=dict(rule_registry) if isinstance(rule_registry,dict) else load_governed_enterprise_metric_rule_registry()
    ctx=dict(context or {}); cols={str(c) for c in (available_columns or [])}
    ro=_parse_date(as_of) if as_of else date.today()
    if ro is None: return {"status":"BLOCKED","reason":"invalid_as_of","rule":None}
    c=[]
    for r in list(reg.get("rules") or []):
        if not bool(r.get("enabled",True)): continue
        if str(r.get("metric") or "")!=str(metric or ""): continue
        if str(r.get("approval_status") or "")!="APPROVED": continue
        if not _scope_matches(dict(r.get("scope") or {}),ctx): continue
        ef,et=_parse_date(r.get("effective_from")),_parse_date(r.get("effective_to"))
        if ef and ro<ef: continue
        if et and ro>et: continue
        if any(str(x) not in cols for x in (r.get("source_columns") or [])): continue
        c.append(r)
    c.sort(key=lambda r:(-int(r.get("priority") or 0),str(r.get("rule_id") or "")))
    if not c: return {"status":"BLOCKED","reason":"no_applicable_approved_enterprise_metric_rule","rule":None}
    return {"status":"DERIVABLE","reason":None,"rule":dict(c[0]),
            "governance":{"selection_policy":"highest_priority_first_match",
            "arbitrary_formula_evaluation":False,"whitelist_operators_only":True}}
