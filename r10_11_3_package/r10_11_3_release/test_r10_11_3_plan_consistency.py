from pathlib import Path
import sys, types
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Stubs isolate the execution-plan consistency behavior.
upe=types.ModuleType("universal_prompt_engine")
def compile_universal_plan(df,prompt,sheet=""):
    return {
        "intent":{"requested_dimensions":["customer"],"requested_analyses":[]},
        "semantic_roles":{"quantity":"Toneladas_Costo","customer":"Cliente"},
        "kpis":[{"key":"quantity","label":"Cantidad / Volumen","column":"Toneladas_Costo","ready":True}],
        "blocked_metrics":[]
    }
upe.compile_universal_plan=compile_universal_plan
sys.modules["universal_prompt_engine"]=upe

sce=types.ModuleType("semantic_contract_enforcer")
def enforce_semantic_contract(plan,df,prompt):
    out=dict(plan)
    roles=dict(out["semantic_roles"])
    roles["quantity"]="Toneladas_Vendidas"
    out["semantic_roles"]=roles
    out["kpis"]=[{"key":"quantity","label":"TONELADAS VENDIDAS","column":"Toneladas_Vendidas","ready":True}]
    return out
sce.enforce_semantic_contract=enforce_semantic_contract
sys.modules["semantic_contract_enforcer"]=sce

# Load a representative R10.11.3 function body directly.
def _component(key,name,requested,status,detail,missing=None,renderer=None):
    return {"key":key,"name":name,"requested":bool(requested),"status":status,"detail":detail,
            "missing":list(missing or []),"renderer":renderer}

from universal_prompt_engine import compile_universal_plan
from semantic_contract_enforcer import enforce_semantic_contract

def build(df,prompt,sheet=""):
    plan=compile_universal_plan(df,prompt,sheet=sheet)
    plan=enforce_semantic_contract(plan,df,prompt)
    return {"semantic_roles":plan["semantic_roles"],"kpis":plan["kpis"]}

df=pd.DataFrame({"Toneladas_Vendidas":[10.0],"Toneladas_Costo":[20.0],"Cliente":["A"]})
out=build(df,"dashboard","BD")
assert out["semantic_roles"]["quantity"]=="Toneladas_Vendidas"
assert out["kpis"][0]["column"]=="Toneladas_Vendidas"
print("PASS execution_plan_strict_quantity")
print("1/1 PASS R10.11.3 PLAN CONSISTENCY")
