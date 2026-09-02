from pathlib import Path
import json, sys, tempfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_metric_rules import ENTERPRISE_METRIC_RULES_VERSION, load_governed_enterprise_metric_rule_registry, resolve_governed_enterprise_metric_rule
from capability_rules import evaluate_rule
def check(n,c):
    if not c: print("FAIL",n); raise AssertionError(n)
    print("PASS",n)
print("\n=== R10.15E GOVERNED ENTERPRISE DERIVED METRIC RULES ===")
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"r.json"
    cols=["Costo_Flete_Corto","Costo_Flete_Largo","Costo_Flete_Traspaso"]
    p.write_text(json.dumps({"schema_version":"r10.15e","registry_id":"demo","ruleset_version":"1","rules":[{
        "rule_id":"company.demo.freight.sum_components.v1","metric":"freight","enabled":True,
        "approval_status":"APPROVED","scope":{"company_id":"DEMO"},"effective_from":"2026-01-01",
        "effective_to":"2026-12-31","priority":100,"operator":"sum_columns","source_columns":cols,
        "format":"currency","provenance":{"source":"enterprise_approved_rule"}}]}),encoding="utf-8")
    reg=load_governed_enterprise_metric_rule_registry(str(p))
    check("version",ENTERPRISE_METRIC_RULES_VERSION=="r10.15e"); check("valid_loaded",reg["status"]=="LOADED")
    check("no_context_blocked",resolve_governed_enterprise_metric_rule(metric="freight",available_columns=cols,rule_registry=reg,context={},as_of="2026-09-02")["status"]=="BLOCKED")
    good=resolve_governed_enterprise_metric_rule(metric="freight",available_columns=cols,rule_registry=reg,context={"company_id":"DEMO"},as_of="2026-09-02")
    check("approved_rule_derivable",good["status"]=="DERIVABLE")
    check("cross_company_blocked",resolve_governed_enterprise_metric_rule(metric="freight",available_columns=cols,rule_registry=reg,context={"company_id":"OTHER"},as_of="2026-09-02")["status"]=="BLOCKED")
    check("missing_column_blocked",resolve_governed_enterprise_metric_rule(metric="freight",available_columns=cols[:2],rule_registry=reg,context={"company_id":"DEMO"},as_of="2026-09-02")["status"]=="BLOCKED")
    df=pd.DataFrame({cols[0]:[10,20],cols[1]:[1,2],cols[2]:[100,200]})
    check("whitelist_execution_exact",evaluate_rule(df,{"status":"DERIVABLE","source_columns":cols,"execution":{"operator":"sum_columns"}})==333.0)
    u=Path(td)/"u.json"; u.write_text(json.dumps({"schema_version":"r10.15e","registry_id":"u","ruleset_version":"1","rules":[{"rule_id":"u","metric":"freight","approval_status":"APPROVED","operator":"sum_columns","source_columns":cols,"formula":"eval(x)"}]}),encoding="utf-8")
    check("arbitrary_formula_rejected",load_governed_enterprise_metric_rule_registry(str(u))["status"]=="INVALID")
default=load_governed_enterprise_metric_rule_registry(str(ROOT/"config"/"enterprise_metric_rules.json"))
check("default_empty",default["status"]=="EMPTY" and default["rule_count"]==0)
check("no_arbitrary_eval",default["governance"]["arbitrary_formula_evaluation"] is False)
b=(S/"dashboard_spec_builder.py").read_text(encoding="utf-8",errors="replace")
check("builder_integrated","resolve_governed_enterprise_metric_rule" in b and '"enterprise_metric_rule_registry"' in b)
check("legacy_arbitrary_freight_not_called","auth = _authorized_freight(" not in b)
print("\nPASS R10.15E GOVERNED ENTERPRISE DERIVED METRIC RULES")
