from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_knowledge_registry import load_governed_enterprise_knowledge_registry
def check(name,cond):
    if not cond: print("FAIL",name); raise AssertionError(name)
    print("PASS",name)
def registry_for(scope):
    return {"schema_version":"r10.16a","registry_id":"demo","knowledge_version":"1","entries":[{"entry_id":"e1","type":"fact","status":"DRAFT","title":"x","content":"y","scope":scope,"provenance":{"source":"manual_validation"}}]}
print("\n=== R10.16D REGISTRY SCOPE HARDENING ===")
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"k.json"
    for name,scope in [("whitespace_empty",{"company_id":"   "}),("whitespace_wildcard",{"company_id":" * "}),("none_scope",{"company_id":None}),("bool_scope",{"company_id":True}),("list_scope",{"company_id":["DEMO"]}),("dict_scope",{"company_id":{"id":"DEMO"}})]:
        p.write_text(json.dumps(registry_for(scope)),encoding="utf-8")
        check(name,load_governed_enterprise_knowledge_registry(str(p))["status"]=="INVALID")
    p.write_text(json.dumps(registry_for({})),encoding="utf-8"); check("empty_scope_global_valid",load_governed_enterprise_knowledge_registry(str(p))["status"]=="LOADED")
    p.write_text(json.dumps(registry_for({"company_id":"DEMO"})),encoding="utf-8"); check("exact_scalar_scope_valid",load_governed_enterprise_knowledge_registry(str(p))["status"]=="LOADED")
print("\nPASS R10.16D REGISTRY SCOPE HARDENING")
