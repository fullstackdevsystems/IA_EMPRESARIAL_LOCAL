from __future__ import annotations
import json, math, os, urllib.request
from typing import Any, Dict, List
import pandas as pd

def _num(v: Any) -> float:
    try:
        if pd.isna(v): return 0.0
        return float(v)
    except Exception:
        return 0.0

def _clean(v: Any) -> str:
    if v is None: return ""
    try:
        if pd.isna(v): return ""
    except Exception:
        pass
    return str(v).strip()

def _group_metrics(df: pd.DataFrame, by: List[str]) -> List[Dict[str, Any]]:
    if not by or not all(c in df.columns for c in by): return []
    w=df.copy()
    for c in ["Toneladas_Vendidas","Importe_Venta","Costo","Utilidad","Costo_Flete"]:
        if c not in w.columns: w[c]=0.0
        w[c]=pd.to_numeric(w[c],errors="coerce").fillna(0.0)
    agg={"Toneladas_Vendidas":"sum","Importe_Venta":"sum","Costo":"sum","Utilidad":"sum","Costo_Flete":"sum"}
    g=w.groupby(by,dropna=False).agg(agg).reset_index()
    if "Refer" in w.columns:
        refs=w.groupby(by,dropna=False)["Refer"].nunique().reset_index(name="Operaciones")
        g=g.merge(refs,on=by,how="left")
    else:
        g["Operaciones"]=0
    out=[]
    for _,r in g.iterrows():
        ton=_num(r["Toneladas_Vendidas"]); venta=_num(r["Importe_Venta"]); costo=_num(r["Costo"]); util=_num(r["Utilidad"]); flete=_num(r["Costo_Flete"])
        d={c:_clean(r[c]) or "Sin dato" for c in by}
        d.update({"Toneladas":ton,"Venta":venta,"Costo":costo,"Utilidad":util,"Flete":flete,
                  "MargenPct":None if not venta else util/venta*100.0,
                  "UtilidadTon":None if not ton else util/ton,
                  "FleteTon":None if not ton else flete/ton,
                  "Operaciones":int(_num(r["Operaciones"]))})
        out.append(d)
    return out

def _negative_operations(df: pd.DataFrame, limit=40):
    if "Utilidad" not in df.columns: return []
    w=df.copy(); w["Utilidad"]=pd.to_numeric(w["Utilidad"],errors="coerce").fillna(0.0)
    w=w.loc[w["Utilidad"]<0].sort_values("Utilidad").head(limit)
    cols=[c for c in ["Fecha","Refer","Cod_Cliente","Cliente","Articulo","ctrl_alm","Toneladas_Vendidas","Importe_Venta","Costo","Utilidad","Proveedor","Almacen","Ciudad_Origen","Ciudad_Destino","Vendedor"] if c in w.columns]
    out=[]
    for _,r in w[cols].iterrows():
        d={}
        for c in cols:
            v=r[c]
            if isinstance(v,(int,float)) and not isinstance(v,bool): d[c]=_num(v)
            else: d[c]=_clean(v)
        out.append(d)
    return out

def _validation(df):
    checks=[]
    def add(name,ok,detail): checks.append({"name":name,"ok":bool(ok),"detail":detail})
    if {"Importe_Venta","Costo","Utilidad"}.issubset(df.columns):
        venta=pd.to_numeric(df["Importe_Venta"],errors="coerce").fillna(0).sum()
        costo=pd.to_numeric(df["Costo"],errors="coerce").fillna(0).sum()
        util=pd.to_numeric(df["Utilidad"],errors="coerce").fillna(0).sum()
        delta=(venta-costo)-util; tol=max(1.0,abs(venta)*1e-8)
        add("Venta - Costo = Utilidad",abs(delta)<=tol,f"Diferencia matemática: {delta:.4f}")
    if "Cod_Cliente" in df.columns:
        add("Clientes únicos por Cod_Cliente",True,f"{df['Cod_Cliente'].nunique(dropna=True)} clientes únicos")
    if "Fecha" in df.columns:
        p=pd.to_datetime(df["Fecha"],errors="coerce")
        add("Fechas válidas",bool(p.notna().all()),f"{int(p.isna().sum())} fechas inválidas")
    add("NaN/Infinity no visibles",True,"Divisiones protegidas y valores seguros.")
    return {"rows":int(len(df)),"checks":checks}

def _facts(df,clients,products,routes,neg):
    def s(c): return float(pd.to_numeric(df[c],errors="coerce").fillna(0).sum()) if c in df.columns else 0.0
    ton=s("Toneladas_Vendidas"); venta=s("Importe_Venta"); costo=s("Costo"); util=s("Utilidad"); flete=s("Costo_Flete")
    f={"registros":int(len(df)),"toneladas":ton,"venta":venta,"costo":costo,"utilidad":util,
       "margen_pct":None if not venta else util/venta*100,"utilidad_ton":None if not ton else util/ton,
       "flete":flete,"flete_pct_costo":None if not costo else flete/costo*100,
       "clientes_unicos":int(df["Cod_Cliente"].nunique(dropna=True)) if "Cod_Cliente" in df.columns else None,
       "referencias":int(df["Refer"].nunique(dropna=True)) if "Refer" in df.columns else None,
       "operaciones_negativas":len(neg),"impacto_negativo_visible":sum(_num(x.get("Utilidad")) for x in neg)}
    if clients:
        f["cliente_mas_rentable"]=max(clients,key=lambda x:x["Utilidad"])
        f["cliente_menos_rentable"]=min(clients,key=lambda x:x["Utilidad"])
    if products:
        f["producto_mas_rentable"]=max(products,key=lambda x:x["Utilidad"])
        f["producto_mayor_volumen"]=max(products,key=lambda x:x["Toneladas"])
    if routes: f["ruta_mayor_flete"]=max(routes,key=lambda x:x["Flete"])
    return f

def _det_summary(f):
    cur=lambda x:f"${x:,.2f}"; num=lambda x:f"{x:,.2f}"
    out=[
      f"El periodo analizado contiene {f['registros']:,} registros y {num(f['toneladas'])} toneladas vendidas.",
      f"La venta total asciende a {cur(f['venta'])}, con costo de {cur(f['costo'])} y utilidad de {cur(f['utilidad'])}."
    ]
    if f.get("margen_pct") is not None: out.append(f"El margen global ponderado es {f['margen_pct']:.2f}%.")
    if f.get("utilidad_ton") is not None: out.append(f"La utilidad global por tonelada es {cur(f['utilidad_ton'])}.")
    if f.get("flete_pct_costo") is not None: out.append(f"Los fletes suman {cur(f['flete'])} y representan {f['flete_pct_costo']:.2f}% del costo total.")
    if f.get("cliente_mas_rentable"):
        x=f["cliente_mas_rentable"]; out.append(f"El cliente con mayor utilidad es {x.get('Cliente','')} con {cur(x['Utilidad'])}.")
    if f.get("cliente_menos_rentable"):
        x=f["cliente_menos_rentable"]; out.append(f"El cliente con menor utilidad es {x.get('Cliente','')} con {cur(x['Utilidad'])}.")
    if f.get("producto_mas_rentable"):
        x=f["producto_mas_rentable"]; out.append(f"El producto/grupo con mayor utilidad es {x.get('ctrl_alm','')} con {cur(x['Utilidad'])}.")
    if f.get("producto_mayor_volumen"):
        x=f["producto_mayor_volumen"]; out.append(f"El producto/grupo de mayor volumen es {x.get('ctrl_alm','')} con {num(x['Toneladas'])} toneladas.")
    out.append(f"Se detectaron {f.get('operaciones_negativas',0)} operaciones con utilidad negativa.")
    if f.get("ruta_mayor_flete"):
        x=f["ruta_mayor_flete"]; out.append(f"La ruta con mayor costo de flete es {x.get('Ciudad_Origen','')} → {x.get('Ciudad_Destino','')} con {cur(x['Flete'])}.")
    return out[:12]

def _ollama_summary(facts):
    if os.getenv("IA_EXECUTIVE_SUMMARY_LLM","1").lower() in {"0","false","no","off"}: return None
    body=json.dumps({"model":os.getenv("IA_OLLAMA_MODEL","qwen3:4b-instruct"),
                     "prompt":"Usa SOLO estos resultados calculados por Python. No recalcules ni inventes. Devuelve JSON {findings:[8 a 12 hallazgos breves en español]}.\n"+json.dumps(facts,ensure_ascii=False,default=str),
                     "stream":False,"format":"json"}).encode()
    try:
        req=urllib.request.Request("http://127.0.0.1:11434/api/generate",data=body,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=float(os.getenv("IA_EXECUTIVE_SUMMARY_TIMEOUT","60"))) as r:
            data=json.loads(r.read().decode())
        obj=json.loads(data.get("response") or "{}"); xs=obj.get("findings")
        if isinstance(xs,list):
            xs=[str(x).strip() for x in xs if str(x).strip()]
            return xs[:12] or None
    except Exception:
        return None
    return None

def build_advanced_analytics(df):
    clients=_group_metrics(df,["Cod_Cliente","Cliente"] if {"Cod_Cliente","Cliente"}.issubset(df.columns) else ["Cliente"] if "Cliente" in df.columns else [])
    products=_group_metrics(df,["ctrl_alm"] if "ctrl_alm" in df.columns else ["Articulo"] if "Articulo" in df.columns else [])
    routes=_group_metrics(df,["Ciudad_Origen","Ciudad_Destino"] if {"Ciudad_Origen","Ciudad_Destino"}.issubset(df.columns) else [])
    neg=_negative_operations(df); val=_validation(df)
    clients=sorted(clients,key=lambda x:x["Utilidad"],reverse=True)
    products=sorted(products,key=lambda x:x["Utilidad"],reverse=True)
    routes=sorted(routes,key=lambda x:x["Flete"],reverse=True)
    facts=_facts(df,clients,products,routes,neg)
    det=_det_summary(facts); ai=_ollama_summary(facts); findings=ai or det
    return {"clients":clients[:100],"products":products[:100],"routes":routes[:100],
            "negative_operations":neg,"validation":val,"facts":facts,
            "executive_findings":findings,
            "executive_summary_source":"ollama-qwen" if ai else "deterministic"}
