from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def norm(value: Any) -> str:
    s=str(value or '').strip().lower()
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    s=re.sub(r'[^a-z0-9%]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()


def _find(df: pd.DataFrame, *names: str) -> Optional[str]:
    cmap={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in cmap: return cmap[norm(n)]
    return None


def detect_dashboard_plan(df: pd.DataFrame, prompt: str='', semantic_context: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    """Clasifica el dataset sin inventar campos. Las familias especializadas tienen
    prioridad; si no encaja, devuelve generic para que el sistema pueda generar HTML.
    """
    cols={
        'line':_find(df,'cod_linea','linea'),
        'customer_id':_find(df,'Cod_Cliente','Codigo_Cliente','CustomerID','Customer ID'),
        'product':_find(df,'articulo','producto','description'),
        'customer':_find(df,'cliente','razon social','customer'),
        'category':_find(df,'categoria','category'),
        'zone':_find(df,'Zona','Region'),
        'seller':_find(df,'Vendedor','Ejecutivo','Asesor'),
        'actual':_find(df,'Toneladas_Vendidas_Actual'),
        'budget':_find(df,'Toneladas_Vendidas_Presupuesto'),
        'previous':_find(df,'Toneladas_Vendidas_Anterior'),
        'period_start':_find(df,'Fecha_Inicial'),
        'period_end':_find(df,'Fecha_Final'),
    }
    try:
        from enterprise_ai.semantic_registry import merge_context_roles, current_context
        ctx = semantic_context if semantic_context is not None else current_context()
        governed = merge_context_roles({}, ctx)
        for key in ('line','customer_id','product','customer','category','zone','seller','actual','budget','previous','period_start','period_end'):
            if governed.get(key): cols[key] = governed[key]
    except Exception:
        pass
    customer_score=sum(bool(cols[k]) for k in ('customer_id','customer','actual','budget','previous'))
    p=norm(prompt)
    requested_customer=any(t in p for t in ('manejo de clientes','seguimiento de clientes','desempeno de clientes','clientes perdidos','presupuesto sin venta','semaforo de cartera'))
    if cols['actual'] and cols['previous'] and (cols['customer_id'] or cols['customer']) and (cols['budget'] or customer_score>=4):
        return {'type':'customer_performance','template':'dashboard_clientes.html','columns':cols,'confidence':'high','reason':'actual_budget_previous_customer'}
    if requested_customer and customer_score>=3:
        return {'type':'customer_performance','template':'dashboard_clientes.html','columns':cols,'confidence':'medium','reason':'prompt_customer_intent'}
    return {'type':'generic','template':'dashboard_generico.html','columns':cols,'confidence':'fallback','reason':'no_specialized_family'}


def _number(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s): return pd.to_numeric(s,errors='coerce').fillna(0.0)
    x=s.astype(str).str.replace(r'[^0-9,.-]','',regex=True)
    if x.str.contains(r'\.',regex=True).any() and x.str.contains(',',regex=False).any(): x=x.str.replace(',','',regex=False)
    else: x=x.str.replace(',','.',regex=False)
    return pd.to_numeric(x,errors='coerce').fillna(0.0)


def _clean_text(s: pd.Series) -> pd.Series:
    return s.fillna('').astype(str).str.strip().str.replace(r'\s+',' ',regex=True)


def _date_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        n=pd.to_numeric(s,errors='coerce')
        return pd.to_datetime(n,unit='D',origin='1899-12-30',errors='coerce')
    return pd.to_datetime(s,errors='coerce')


def prepare_customer_performance(df: pd.DataFrame, plan: Dict[str,Any]) -> Tuple[pd.DataFrame,List[str]]:
    c=plan['columns']; w=pd.DataFrame(index=df.index)
    text_map={'line':'line','customer_id':'customer_id','product':'product','customer':'customer','category':'category','zone':'zone','seller':'seller'}
    for src_key,dst in text_map.items():
        col=c.get(src_key); w[dst]=_clean_text(df[col]) if col else ''
    for src_key,dst in [('actual','actual'),('budget','budget'),('previous','previous')]:
        col=c.get(src_key); w[dst]=_number(df[col]) if col else 0.0
    for src_key,dst in [('period_start','period_start'),('period_end','period_end')]:
        col=c.get(src_key); w[dst]=_date_series(df[col]) if col else pd.NaT
    notes=[]
    if not c.get('budget'): notes.append('No existe columna de presupuesto; los indicadores contra presupuesto se muestran como N/A.')
    if not c.get('period_start') or not c.get('period_end'): notes.append('No existe periodo completo Fecha_Inicial/Fecha_Final.')
    notes.append('Fecha_Inicial y Fecha_Final se tratan como cobertura del reporte, no como fechas de transacción.')
    return w,notes


def _safe_pct(num: float, den: float) -> Optional[float]:
    return num/den*100.0 if den else None


def _client_table(w: pd.DataFrame) -> pd.DataFrame:
    key='customer_id' if w['customer_id'].astype(str).str.strip().ne('').any() else 'customer'
    agg=w.groupby(key,dropna=False).agg(
        Cliente=('customer','first'), Zona=('zone','first'), Vendedor=('seller','first'), Categoria=('category','first'),
        Actual=('actual','sum'), Presupuesto=('budget','sum'), Anterior=('previous','sum'),
        Productos=('product',lambda s:' | '.join(sorted({x for x in s if str(x).strip()})))
    ).reset_index().rename(columns={key:'Cod_Cliente'})
    agg['Diferencia_Presupuesto']=agg['Actual']-agg['Presupuesto']
    agg['Cumplimiento_%']=[_safe_pct(a,b) for a,b in zip(agg['Actual'],agg['Presupuesto'])]
    agg['Diferencia_Anterior']=agg['Actual']-agg['Anterior']
    agg['Variacion_%']=[_safe_pct(a-b,b) for a,b in zip(agg['Actual'],agg['Anterior'])]
    def status(r):
        if (r.Anterior>0 and r.Actual<=0) or (r.Presupuesto>0 and r.Actual<=0): return 'ROJO'
        if r.Actual>0 and r.Anterior<=0: return 'AZUL'
        if r.Actual>0 and r.Presupuesto>0 and (r.Actual/r.Presupuesto)<0.80: return 'AMARILLO'
        if r.Presupuesto>0 and (r.Actual/r.Presupuesto)>=1: return 'VERDE'
        return 'SIN CLASIFICAR'
    agg['Estado']=agg.apply(status,axis=1)
    agg['Volumen_Potencial']=(agg[['Presupuesto','Anterior']].max(axis=1)-agg['Actual']).clip(lower=0)
    return agg


def _group(w: pd.DataFrame, col: str, clients: pd.DataFrame) -> pd.DataFrame:
    if not col or col not in w or not w[col].astype(str).str.strip().ne('').any(): return pd.DataFrame()
    rows=[]
    for k,g in w.groupby(col,dropna=False):
        if not str(k).strip(): continue
        ids=set(g['customer_id'].astype(str)) if g['customer_id'].astype(str).str.strip().ne('').any() else set(g['customer'].astype(str))
        sub=clients[clients['Cod_Cliente'].astype(str).isin(ids)] if not clients.empty else pd.DataFrame()
        a=float(g.actual.sum()); b=float(g.budget.sum()); p=float(g.previous.sum())
        rows.append({col:str(k),'Actual':a,'Presupuesto':b,'Anterior':p,'Cumplimiento_%':_safe_pct(a,b),'Variacion_%':_safe_pct(a-p,p),
                     'Clientes_Actuales':int((sub.Actual>0).sum()) if not sub.empty else None,
                     'Clientes_Perdidos':int(((sub.Actual<=0)&(sub.Anterior>0)).sum()) if not sub.empty else None,
                     'Clientes_Recuperados':int(((sub.Actual>0)&(sub.Anterior<=0)).sum()) if not sub.empty else None,
                     'Presupuesto_Sin_Venta':int(((sub.Presupuesto>0)&(sub.Actual<=0)).sum()) if not sub.empty else None})
    return pd.DataFrame(rows).sort_values('Actual',ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def build_customer_performance_model(w: pd.DataFrame, prompt: str, plan: Dict[str,Any]) -> Dict[str,Any]:
    clients=_client_table(w)
    actual=float(w.actual.sum()); budget=float(w.budget.sum()); previous=float(w.previous.sum())
    prev_clients=int((clients.Anterior>0).sum()); retained=int(((clients.Actual>0)&(clients.Anterior>0)).sum())
    lost=clients[(clients.Actual<=0)&(clients.Anterior>0)].sort_values('Anterior',ascending=False).copy()
    recovered=clients[(clients.Actual>0)&(clients.Anterior<=0)].sort_values('Actual',ascending=False).copy()
    budget_no_sale=clients[(clients.Presupuesto>0)&(clients.Actual<=0)].sort_values('Presupuesto',ascending=False).copy()
    low=clients[(clients.Actual>0)&(clients.Presupuesto>0)&(clients['Cumplimiento_%']<80)].sort_values('Volumen_Potencial',ascending=False).copy()
    declines=clients[(clients.Anterior>0)&(clients.Actual<clients.Anterior)].sort_values('Diferencia_Anterior').copy()
    growth=clients[clients.Actual>clients.Anterior].sort_values('Diferencia_Anterior',ascending=False).copy()
    budget_clients=int((clients.Presupuesto>0).sum()); budget_with_sale=int(((clients.Presupuesto>0)&(clients.Actual>0)).sum())
    kpis={
        'Toneladas_Actuales':actual,'Presupuesto':budget,'Toneladas_Anteriores':previous,
        'Cumplimiento_%':_safe_pct(actual,budget),'Diferencia_Presupuesto':actual-budget,
        'Variacion_Absoluta':actual-previous,'Variacion_%':_safe_pct(actual-previous,previous),
        'Clientes_Activos':int((clients.Actual>0).sum()),'Clientes_Anterior':prev_clients,'Clientes_Retenidos':retained,
        'Clientes_Perdidos':int(len(lost)),'Clientes_Recuperados':int(len(recovered)),'Clientes_Presupuesto':budget_clients,
        'Clientes_Presupuesto_Con_Venta':budget_with_sale,'Clientes_Presupuesto_Sin_Venta':int(len(budget_no_sale)),
        'Tasa_Retencion_%':_safe_pct(retained,prev_clients),'Tasa_Perdida_%':_safe_pct(len(lost),prev_clients),'Cobertura_Presupuesto_%':_safe_pct(budget_with_sale,budget_clients),
        'Volumen_Pendiente_Presupuesto':float((clients.Presupuesto-clients.Actual).clip(lower=0).sum())
    }
    sem=clients.groupby('Estado').size().reset_index(name='Clientes').sort_values('Clientes',ascending=False)
    opp=clients.copy()
    def motive(r):
        if r.Actual<=0 and r.Anterior>0: return 'Cliente perdido'
        if r.Actual<=0 and r.Presupuesto>0: return 'Presupuesto sin venta'
        if r.Anterior>0 and r.Actual<r.Anterior: return 'Caída de volumen'
        if r.Presupuesto>0 and r.Actual/r.Presupuesto<.8: return 'Bajo cumplimiento'
        return 'Oportunidad de crecimiento'
    opp['Motivo']=opp.apply(motive,axis=1)
    opp=opp[(opp.Volumen_Potencial>0)|(opp.Diferencia_Anterior<0)].sort_values(['Volumen_Potencial','Anterior'],ascending=False).head(100)
    period_from=w.period_start.dropna().min(); period_to=w.period_end.dropna().max()
    return {'type':'customer_performance','prompt':prompt,'plan':plan,'kpis':kpis,'clients':clients,'semaphore':sem,
            'products':_group(w,'product',clients),'sellers':_group(w,'seller',clients),'zones':_group(w,'zone',clients),'categories':_group(w,'category',clients),
            'lost':lost,'recovered':recovered,'budget_no_sale':budget_no_sale,'low_compliance':low,'declines':declines,'growth':growth,'opportunities':opp,
            'detail':w.copy(),'period_from':period_from,'period_to':period_to}


def records(df: pd.DataFrame, max_rows: Optional[int]=None) -> List[Dict[str,Any]]:
    if df is None or df.empty: return []
    x=df if max_rows is None else df.head(max_rows); out=[]
    for _,r in x.iterrows():
        d={}
        for k,v in r.items():
            if isinstance(v,pd.Timestamp): d[str(k)]=v.date().isoformat() if not pd.isna(v) else None
            elif v is None or (not isinstance(v,str) and pd.isna(v)): d[str(k)]=None
            elif hasattr(v,'item'):
                try:d[str(k)]=v.item()
                except Exception:d[str(k)]=v
            else:d[str(k)]=v
        out.append(d)
    return out


def customer_payload(model: Dict[str,Any], filename: str, rows: int) -> Dict[str,Any]:
    w=model['detail']; tx=[]
    for _,r in w.iterrows():
        tx.append({'line':r['line'],'cid':r['customer_id'],'p':r['product'],'c':r['customer'],'cat':r['category'],'z':r['zone'],'s':r['seller'],
                   'a':float(r['actual']),'b':float(r['budget']),'prev':float(r['previous']),
                   'fi':r['period_start'].date().isoformat() if pd.notna(r['period_start']) else '', 'ff':r['period_end'].date().isoformat() if pd.notna(r['period_end']) else ''})
    return {'tx':tx,'meta':{'file':filename,'rows':rows,'prompt':model['prompt'],'type':'customer_performance',
                            'from':model['period_from'].date().isoformat() if pd.notna(model['period_from']) else '',
                            'to':model['period_to'].date().isoformat() if pd.notna(model['period_to']) else ''}}


def customer_sections(model: Dict[str,Any]) -> Dict[str,pd.DataFrame]:
    return {
        'KPIs_Clientes':pd.DataFrame([model['kpis']]), 'Semaforo_Cartera':model['semaphore'], 'Productos':model['products'],
        'Vendedores':model['sellers'],'Zonas':model['zones'],'Categorias':model['categories'],'Top_Clientes':model['clients'].sort_values('Actual',ascending=False).head(50),
        'Clientes_Perdidos':model['lost'],'Presupuesto_Sin_Venta':model['budget_no_sale'],'Bajo_Cumplimiento':model['low_compliance'],
        'Clientes_Recuperados':model['recovered'],'Mayores_Caidas':model['declines'].head(50),'Mayores_Crecimientos':model['growth'].head(50),
        'Oportunidades_Prioritarias':model['opportunities'],'Detalle':model['detail']
    }


def customer_narrative(model: Dict[str,Any]) -> str:
    k=model['kpis']; pct=k.get('Cumplimiento_%'); var=k.get('Variacion_%')
    return (f"El periodo registra {k['Toneladas_Actuales']:,.2f} toneladas actuales frente a {k['Presupuesto']:,.2f} presupuestadas"
            + (f" ({pct:.2f}% de cumplimiento)" if pct is not None else '') + ". "
            + f"Contra el periodo anterior la diferencia es {k['Variacion_Absoluta']:,.2f} toneladas"
            + (f" ({var:.2f}%)" if var is not None else '') + f". Se identificaron {k['Clientes_Perdidos']} clientes perdidos, "
            + f"{k['Clientes_Recuperados']} nuevos/recuperados y {k['Clientes_Presupuesto_Sin_Venta']} clientes con presupuesto sin venta. "
            + f"El volumen pendiente contra presupuesto es {k['Volumen_Pendiente_Presupuesto']:,.2f} toneladas.")


def generic_payload(df: pd.DataFrame, filename: str, prompt: str, sheet: str='') -> Dict[str,Any]:
    # Fallback HTML universal. Conserva como máximo 20k filas para que el navegador
    # siga siendo utilizable; el PDF/Excel mantienen el análisis completo.
    cols=[str(c) for c in df.columns]
    rows=[]
    for _,r in df.head(20000).iterrows():
        d={}
        for c in df.columns:
            v=r[c]
            if isinstance(v,pd.Timestamp): v=v.isoformat() if pd.notna(v) else None
            elif v is None or (not isinstance(v,str) and pd.isna(v)): v=None
            elif hasattr(v,'item'):
                try:v=v.item()
                except Exception:pass
            d[str(c)]=v
        rows.append(d)
    return {'rows':rows,'meta':{'file':filename,'prompt':prompt,'sheet':sheet,'columns':cols,'rows_total':int(len(df)),'rows_embedded':len(rows)}}
