from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _norm(v: Any) -> str:
    s = str(v or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9%]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _json_safe(v: Any) -> Any:
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, 'item'):
        try:
            return v.item()
        except Exception:
            pass
    return v


def _series_kind(s: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(s):
        return 'date'
    if pd.api.types.is_numeric_dtype(s):
        return 'number'
    # Conservative date detection for object columns: only date-looking samples.
    sample = s.dropna().astype(str).head(50)
    if len(sample) >= 3:
        looks_date = sample.str.match(r'^\s*(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})').mean()
        if float(looks_date) >= 0.85:
            parsed = pd.to_datetime(sample, errors='coerce')
            if float(parsed.notna().mean()) >= 0.85:
                return 'date'
    return 'text'


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    cols = []
    for c in df.columns:
        s = df[c]
        kind = _series_kind(s)
        cols.append({
            'name': str(c),
            'kind': kind,
            'non_null': int(s.notna().sum()),
            'unique': int(s.nunique(dropna=True)),
        })
    return {'rows': int(len(df)), 'columns': cols}


def _find_col(df: pd.DataFrame, *terms: str) -> Optional[str]:
    nmap = {_norm(c): str(c) for c in df.columns}
    for t in terms:
        nt = _norm(t)
        if nt in nmap:
            return nmap[nt]
    # fuzzy contains, longest term first
    for t in sorted((_norm(x) for x in terms), key=len, reverse=True):
        for nc, orig in nmap.items():
            if t and (t in nc or nc in t):
                return orig
    return None


def _semantic_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        'date': _find_col(df, 'fecha', 'date', 'fecha venta', 'fecha factura'),
        'period_start': _find_col(df, 'fecha inicial', 'fecha_inicial'),
        'period_end': _find_col(df, 'fecha final', 'fecha_final'),
        'customer': _find_col(df, 'cliente', 'customer', 'razon social'),
        'customer_id': _find_col(df, 'cod cliente', 'cod_cliente', 'customer id', 'customerid'),
        'product': _find_col(df, 'articulo', 'producto', 'product', 'descripcion'),
        'category': _find_col(df, 'categoria', 'category', 'familia'),
        'seller': _find_col(df, 'vendedor', 'ejecutivo', 'asesor', 'seller'),
        'zone': _find_col(df, 'zona', 'region', 'territorio'),
        'line': _find_col(df, 'linea', 'cod linea', 'cod_linea'),
        'revenue': _find_col(df, 'venta neta', 'ventas netas', 'importe', 'monto', 'revenue', 'total venta', 'venta'),
        'quantity': _find_col(df, 'cantidad', 'unidades', 'toneladas', 'quantity', 'qty'),
        'actual': _find_col(df, 'toneladas vendidas actual', 'toneladas_vendidas_actual', 'actual'),
        'budget': _find_col(df, 'toneladas vendidas presupuesto', 'toneladas_vendidas_presupuesto', 'presupuesto', 'budget'),
        'previous': _find_col(df, 'toneladas vendidas anterior', 'toneladas_vendidas_anterior', 'anterior', 'previous'),
        'cost': _find_col(df, 'costo', 'coste', 'cost'),
        'profit': _find_col(df, 'utilidad', 'ganancia', 'profit'),
    }


def _extract_top_n(prompt: str) -> int:
    p = _norm(prompt)
    m = re.search(r'\btop\s*(\d{1,4})\b', p)
    if not m:
        m = re.search(r'\b(\d{1,4})\s+(?:principales|mejores|peores|clientes|productos|vendedores)\b', p)
    if m:
        return max(3, min(100, int(m.group(1))))
    return 10


def _human_label(col: str) -> str:
    s = str(col).replace('_', ' ')
    return re.sub(r'\s+', ' ', s).strip().title()


def _fallback_plan(df: pd.DataFrame, prompt: str, filename: str, sheet: str) -> Dict[str, Any]:
    sem = _semantic_columns(df)
    p = _norm(prompt)
    numeric = [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    text = [str(c) for c in df.columns if _series_kind(df[c]) == 'text' and df[c].nunique(dropna=True) <= 5000]
    top_n = _extract_top_n(prompt)

    # Prioritize business measures explicitly mentioned or semantically meaningful.
    prioritized_measures: List[str] = []
    for k in ('actual', 'budget', 'previous', 'revenue', 'quantity', 'profit', 'cost'):
        c = sem.get(k)
        if c and c in numeric and c not in prioritized_measures:
            prioritized_measures.append(c)
    for c in numeric:
        if c not in prioritized_measures:
            prioritized_measures.append(c)

    # Dimensions adapt to prompt first, then business semantics.
    dims: List[str] = []
    keyword_map = [
        ('cliente', sem.get('customer') or sem.get('customer_id')),
        ('producto', sem.get('product')),
        ('articulo', sem.get('product')),
        ('vendedor', sem.get('seller')),
        ('ejecutivo', sem.get('seller')),
        ('zona', sem.get('zone')),
        ('region', sem.get('zone')),
        ('categoria', sem.get('category')),
        ('linea', sem.get('line')),
    ]
    for kw, col in keyword_map:
        if kw in p and col and col not in dims:
            dims.append(col)
    for k in ('customer', 'product', 'seller', 'zone', 'category', 'line'):
        c = sem.get(k)
        if c and c in text and c not in dims:
            dims.append(c)
    for c in text:
        if c not in dims:
            dims.append(c)

    kpis = []
    for c in prioritized_measures[:6]:
        kpis.append({'label': _human_label(c), 'op': 'sum', 'column': c, 'format': 'number'})
    # Useful count KPIs.
    cust = sem.get('customer_id') or sem.get('customer')
    if cust:
        kpis.append({'label': 'Clientes', 'op': 'nunique', 'column': cust, 'format': 'integer'})

    # Derived comparison KPIs when the real columns exist.
    if sem.get('actual') and sem.get('budget'):
        kpis.append({'label': 'Cumplimiento Presupuesto', 'op': 'ratio_pct', 'numerator': sem['actual'], 'denominator': sem['budget'], 'format': 'percent'})
        kpis.append({'label': 'Diferencia vs Presupuesto', 'op': 'difference_sum', 'left': sem['actual'], 'right': sem['budget'], 'format': 'number'})
    if sem.get('actual') and sem.get('previous'):
        kpis.append({'label': 'Variación vs Anterior', 'op': 'variation_pct', 'current': sem['actual'], 'previous': sem['previous'], 'format': 'percent'})

    charts = []
    measure = prioritized_measures[0] if prioritized_measures else None
    date_col = sem.get('date')
    # Fecha_Inicial/Fecha_Final often describe report coverage, not transactions.
    if date_col in {sem.get('period_start'), sem.get('period_end')}:
        date_col = None
    if date_col and measure:
        charts.append({'type': 'line', 'title': f'{_human_label(measure)} por periodo', 'dimension': date_col, 'measure': measure, 'op': 'sum', 'top_n': 36})
    for d in dims[:4]:
        if measure:
            charts.append({'type': 'bar', 'title': f'{_human_label(measure)} por {_human_label(d)}', 'dimension': d, 'measure': measure, 'op': 'sum', 'top_n': top_n})

    if sem.get('actual') and sem.get('budget') and (sem.get('customer') or sem.get('customer_id')):
        d = sem.get('customer') or sem.get('customer_id')
        charts.insert(0, {'type': 'comparison_bar', 'title': 'Actual vs Presupuesto por Cliente', 'dimension': d, 'measures': [sem['actual'], sem['budget']], 'op': 'sum', 'top_n': top_n})
    if sem.get('actual') and sem.get('previous') and (sem.get('seller') or sem.get('zone')):
        d = sem.get('seller') or sem.get('zone')
        charts.append({'type': 'comparison_bar', 'title': f'Actual vs Anterior por {_human_label(d)}', 'dimension': d, 'measures': [sem['actual'], sem['previous']], 'op': 'sum', 'top_n': top_n})

    filters = []
    for d in dims[:6]:
        if int(df[d].nunique(dropna=True)) <= 500:
            filters.append({'column': d, 'label': _human_label(d)})

    table_cols = []
    for c in dims[:3] + prioritized_measures[:5]:
        if c and c not in table_cols:
            table_cols.append(c)

    requested_title = 'Dashboard Ejecutivo'
    if 'cliente' in p:
        requested_title = 'Dashboard de Clientes'
    elif 'venta' in p:
        requested_title = 'Dashboard de Ventas'
    elif 'inventario' in p:
        requested_title = 'Dashboard de Inventario'
    elif 'compra' in p:
        requested_title = 'Dashboard de Compras'

    return {
        'title': requested_title,
        'subtitle': filename + (f' · Hoja {sheet}' if sheet else ''),
        'kpis': kpis[:10],
        'charts': charts[:8],
        'filters': filters,
        'table': {'title': 'Detalle', 'columns': table_cols[:10], 'limit': 100},
        'top_n': top_n,
        'planner': 'deterministic-fallback',
    }


def _ollama_plan(df: pd.DataFrame, prompt: str, filename: str, sheet: str) -> Optional[Dict[str, Any]]:
    if os.getenv('IA_DYNAMIC_DASHBOARD_LLM', '1').strip().lower() in {'0', 'false', 'no'}:
        return None
    try:
        import requests
    except Exception:
        return None
    profile = profile_dataframe(df)
    cols = [{'name': c['name'], 'kind': c['kind'], 'unique': c['unique']} for c in profile['columns']]
    model = os.getenv('IA_OLLAMA_MODEL', 'qwen3:4b-instruct')
    system = """Eres un planificador de dashboards empresariales. Devuelve SOLO JSON valido.
Usa exclusivamente columnas proporcionadas. No inventes datos, formulas, costos ni fechas.
El dashboard se renderiza automaticamente: tu trabajo es elegir KPIs, filtros, graficas y columnas de detalle segun la peticion.
Operaciones KPI permitidas: sum, avg, min, max, count, nunique, ratio_pct, difference_sum, variation_pct.
Tipos de grafica permitidos: bar, line, donut, comparison_bar.
Para ratio_pct usa numerator y denominator. Para difference_sum usa left y right. Para variation_pct usa current y previous.
Para graficas normales usa dimension, measure, op=sum|avg|count|nunique y top_n. comparison_bar usa dimension, measures:[col1,col2].
No uses Fecha_Inicial/Fecha_Final como serie temporal si solo representan cobertura del reporte.
JSON esperado: {title,subtitle,kpis:[...],charts:[...],filters:[{column,label}],table:{title,columns,limit},top_n}.
"""
    user = json.dumps({'archivo': filename, 'hoja': sheet, 'prompt_usuario': prompt, 'columnas': cols}, ensure_ascii=False)
    try:
        r = requests.post('http://127.0.0.1:11434/api/generate', json={
            'model': model,
            'prompt': system + '\n\n' + user,
            'stream': False,
            'format': 'json',
            'options': {'temperature': 0.1, 'num_predict': 1600},
        }, timeout=12)
        r.raise_for_status()
        raw = r.json().get('response', '')
        plan = json.loads(raw)
        if isinstance(plan, dict):
            plan['planner'] = f'ollama:{model}'
            return plan
    except Exception:
        return None
    return None


def _validate_plan(plan: Optional[Dict[str, Any]], df: pd.DataFrame, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return fallback
    cols = {str(c) for c in df.columns}
    out = dict(fallback)
    if isinstance(plan.get('title'), str) and plan['title'].strip():
        out['title'] = plan['title'].strip()[:120]
    if isinstance(plan.get('subtitle'), str) and plan['subtitle'].strip():
        out['subtitle'] = plan['subtitle'].strip()[:180]
    out['planner'] = plan.get('planner', 'validated')

    allowed_ops = {'sum', 'avg', 'min', 'max', 'count', 'nunique', 'ratio_pct', 'difference_sum', 'variation_pct'}
    vk = []
    for k in plan.get('kpis', []) if isinstance(plan.get('kpis'), list) else []:
        if not isinstance(k, dict) or k.get('op') not in allowed_ops:
            continue
        op = k['op']
        needed = []
        if op in {'sum','avg','min','max','count','nunique'}:
            needed = [k.get('column')]
        elif op == 'ratio_pct':
            needed = [k.get('numerator'), k.get('denominator')]
        elif op == 'difference_sum':
            needed = [k.get('left'), k.get('right')]
        elif op == 'variation_pct':
            needed = [k.get('current'), k.get('previous')]
        if all(x in cols for x in needed):
            kk = dict(k)
            kk['label'] = str(kk.get('label') or op)[:80]
            vk.append(kk)
    if vk:
        out['kpis'] = vk[:10]

    vc = []
    for c in plan.get('charts', []) if isinstance(plan.get('charts'), list) else []:
        if not isinstance(c, dict) or c.get('type') not in {'bar','line','donut','comparison_bar'}:
            continue
        d = c.get('dimension')
        if d not in cols:
            continue
        if c['type'] == 'comparison_bar':
            measures = [m for m in c.get('measures', []) if m in cols]
            if len(measures) < 2:
                continue
            cc = dict(c); cc['measures'] = measures[:3]
        else:
            if c.get('measure') not in cols:
                continue
            cc = dict(c)
            if cc.get('op') not in {'sum','avg','count','nunique'}:
                cc['op'] = 'sum'
        cc['title'] = str(cc.get('title') or _human_label(d))[:120]
        try: cc['top_n'] = max(3, min(100, int(cc.get('top_n', out.get('top_n', 10)))))
        except Exception: cc['top_n'] = out.get('top_n', 10)
        vc.append(cc)
    if vc:
        out['charts'] = vc[:8]

    vf = []
    for f in plan.get('filters', []) if isinstance(plan.get('filters'), list) else []:
        if isinstance(f, dict) and f.get('column') in cols and int(df[f['column']].nunique(dropna=True)) <= 500:
            vf.append({'column': f['column'], 'label': str(f.get('label') or _human_label(f['column']))[:80]})
    if vf:
        out['filters'] = vf[:8]

    t = plan.get('table')
    if isinstance(t, dict):
        tc = [c for c in t.get('columns', []) if c in cols]
        if tc:
            out['table'] = {'title': str(t.get('title') or 'Detalle')[:80], 'columns': tc[:12], 'limit': max(10, min(500, int(t.get('limit', 100))))}
    return out


def build_dashboard_plan(df: pd.DataFrame, prompt: str, filename: str = '', sheet: str = '') -> Dict[str, Any]:
    fallback = _fallback_plan(df, prompt, filename, sheet)
    ai_plan = _ollama_plan(df, prompt, filename, sheet)
    return _validate_plan(ai_plan, df, fallback)


def _prepare_rows(df: pd.DataFrame, limit: int = 20000) -> List[Dict[str, Any]]:
    x = df.head(limit).copy()
    for c in x.columns:
        kind = _series_kind(x[c])
        if kind == 'date':
            x[c] = pd.to_datetime(x[c], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    rows = []
    for rec in x.to_dict(orient='records'):
        rows.append({str(k): _json_safe(v) for k, v in rec.items()})
    return rows


def _logo_data_uri() -> str:
    path = Path(__file__).resolve().parent / 'assets' / 'primos_cousins_logo.png'
    try:
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        return 'data:image/png;base64,' + data
    except Exception:
        return ''


def _safe_inline_json(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('</', '<\\/')


def generate_dynamic_dashboard(output_path: Path, df: pd.DataFrame, prompt: str, filename: str, sheet: str = '') -> Dict[str, Any]:
    plan = build_dashboard_plan(df, prompt, filename, sheet)
    kinds = {str(c): _series_kind(df[c]) for c in df.columns}
    payload = {
        'plan': plan,
        'rows': _prepare_rows(df),
        'meta': {'file': filename, 'sheet': sheet, 'rows': int(len(df)), 'embedded_rows': int(min(len(df), 20000)), 'prompt': prompt, 'column_kinds': kinds},
        'brand': {'company': 'PRIMOS & COUSINS', 'logo': _logo_data_uri()},
    }
    data = _safe_inline_json(payload)
    title = html.escape(plan.get('title') or 'Dashboard Ejecutivo')
    page = _HTML.replace('__TITLE__', title).replace('__PAYLOAD__', data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding='utf-8')
    return plan


_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · Primos & Cousins</title>
<style>
:root{--pc-bg:#04111a;--pc-bg2:#071c28;--pc-panel:#0a202d;--pc-panel2:#0e2a38;--pc-cyan:#16b8c8;--pc-cyan2:#68dce5;--pc-text:#f4fbfd;--pc-muted:#9fb8c2;--pc-border:#173d4b;--pc-green:#7fd34e;--pc-yellow:#f6c84c;--pc-red:#ef5a5a;--pc-blue:#50a7ff}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,var(--pc-bg),#061822);color:var(--pc-text);font-family:Segoe UI,Arial,sans-serif}button,select,input{font:inherit}.wrap{max-width:1900px;margin:auto;padding:18px}.head{display:flex;align-items:center;gap:22px;border-bottom:1px solid var(--pc-border);padding:8px 4px 16px}.logo{width:min(390px,33vw);max-height:86px;object-fit:contain;object-position:left center}.headtext{min-width:0}.head h1{font-size:clamp(22px,2.3vw,40px);margin:0 0 4px;letter-spacing:.02em}.sub{color:var(--pc-cyan2);font-size:14px}.meta{margin-left:auto;text-align:right;color:var(--pc-muted);font-size:12px}.planner{color:var(--pc-cyan2)}.filters{display:flex;flex-wrap:wrap;gap:10px;padding:16px 0}.filter{background:var(--pc-panel);border:1px solid var(--pc-border);border-radius:8px;padding:8px 10px;min-width:180px}.filter label{display:block;color:var(--pc-cyan2);font-size:11px;margin-bottom:5px;text-transform:uppercase}.filter select{width:100%;background:#061923;color:var(--pc-text);border:1px solid #1b5362;border-radius:6px;padding:8px}.actions{margin-left:auto;display:flex;gap:8px;align-items:end}.btn{background:#073442;color:var(--pc-cyan2);border:1px solid #187186;border-radius:7px;padding:9px 13px;cursor:pointer}.btn:hover{background:#0a4658}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.kpi{background:linear-gradient(145deg,var(--pc-panel),#071b26);border:1px solid var(--pc-border);border-top:3px solid var(--pc-cyan);border-radius:9px;padding:15px}.kpi .l{color:var(--pc-muted);font-size:12px;text-transform:uppercase}.kpi .v{font-size:clamp(21px,2vw,31px);margin-top:7px;font-variant-numeric:tabular-nums}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;margin-top:14px}.card{grid-column:span 6;background:var(--pc-panel);border:1px solid var(--pc-border);border-radius:9px;padding:14px;min-width:0}.card h2,.table-card h2{font-size:16px;margin:0 0 10px}.chart{min-height:280px;position:relative}.bars{height:260px;display:flex;align-items:end;gap:8px;padding:18px 4px 34px;border-bottom:1px solid #28505d}.bargrp{flex:1;min-width:24px;display:flex;gap:2px;align-items:end;height:100%;position:relative}.bar{flex:1;background:linear-gradient(180deg,var(--pc-cyan2),var(--pc-cyan));border-radius:4px 4px 0 0;min-height:1px}.bar.alt{background:linear-gradient(180deg,#87a9b5,#315d6d)}.bar.prev{background:linear-gradient(180deg,#4da2e8,#236294)}.xlabel{position:absolute;top:calc(100% + 5px);left:50%;transform:translateX(-50%);font-size:10px;color:var(--pc-muted);max-width:100px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.legend{display:flex;gap:15px;flex-wrap:wrap;color:var(--pc-muted);font-size:11px;margin-bottom:4px}.dot{display:inline-block;width:9px;height:9px;border-radius:2px;background:var(--pc-cyan);margin-right:4px}.dot.alt{background:#587f8d}.dot.prev{background:#347fb9}.line-svg{width:100%;height:270px}.table-card{margin-top:14px;background:var(--pc-panel);border:1px solid var(--pc-border);border-radius:9px;padding:14px}.table-wrap{overflow:auto;max-height:520px}.table{width:100%;border-collapse:collapse;font-size:12px}.table th{position:sticky;top:0;background:#0c2936;color:var(--pc-cyan2);text-align:left}.table th,.table td{padding:8px;border-bottom:1px solid #153844;white-space:nowrap}.table tr:hover td{background:#0b2a37}.note{color:var(--pc-muted);font-size:12px;margin-top:8px}.foot{text-align:center;color:var(--pc-muted);border-top:1px solid var(--pc-border);margin-top:16px;padding:14px}.foot strong{color:var(--pc-cyan2)}
@media(max-width:900px){.head{align-items:flex-start;flex-wrap:wrap}.meta{margin-left:0;text-align:left;width:100%}.logo{width:280px}.card{grid-column:span 12}.actions{margin-left:0;width:100%}.wrap{padding:10px}}
</style></head><body><div class="wrap">
<header class="head"><img id="logo" class="logo" alt="Primos & Cousins"><div class="headtext"><h1 id="title"></h1><div id="subtitle" class="sub"></div></div><div class="meta"><div id="filemeta"></div><div class="planner" id="planner"></div></div></header>
<section class="filters" id="filters"><div class="actions"><button class="btn" id="clear">Limpiar filtros</button><button class="btn" id="csv">Exportar CSV filtrado</button></div></section>
<section class="kpis" id="kpis"></section><section class="grid" id="charts"></section>
<section class="table-card"><h2 id="tableTitle">Detalle</h2><div class="table-wrap"><table class="table"><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><div class="note" id="rownote"></div></section>
<footer class="foot"><strong>PRIMOS & COUSINS</strong> · Dashboard generado automáticamente por IA Empresarial Local</footer></div>
<script>const DATA=__PAYLOAD__;
(()=>{const P=DATA.plan||{},ROWS=DATA.rows||[],KINDS=(DATA.meta||{}).column_kinds||{};const $=id=>document.getElementById(id);$('logo').src=(DATA.brand||{}).logo||'';$('title').textContent=P.title||'Dashboard Ejecutivo';$('subtitle').textContent=P.subtitle||'';$('filemeta').textContent=`${DATA.meta.file||''} · ${DATA.meta.rows||0} filas`;$('planner').textContent=`Plan: ${P.planner||'automático'}`;
const fstate={};function num(v){if(v===null||v===undefined||v==='')return 0;const n=Number(String(v).replace(/,/g,''));return Number.isFinite(n)?n:0}function fmt(v,f){if(v===null||v===undefined||!Number.isFinite(Number(v)))return 'N/A';if(f==='percent')return Number(v).toLocaleString('es-MX',{maximumFractionDigits:2})+'%';if(f==='integer')return Math.round(Number(v)).toLocaleString('es-MX');return Number(v).toLocaleString('es-MX',{maximumFractionDigits:2})}
function filtered(){return ROWS.filter(r=>Object.entries(fstate).every(([c,v])=>!v||String(r[c]??'')===v))}function agg(rows,op,col){if(op==='count')return rows.length;if(op==='nunique')return new Set(rows.map(r=>String(r[col]??'')).filter(Boolean)).size;const a=rows.map(r=>num(r[col]));if(!a.length)return 0;if(op==='avg')return a.reduce((x,y)=>x+y,0)/a.length;if(op==='min')return Math.min(...a);if(op==='max')return Math.max(...a);return a.reduce((x,y)=>x+y,0)}function kval(k,rows){if(['sum','avg','min','max','count','nunique'].includes(k.op))return agg(rows,k.op,k.column);if(k.op==='ratio_pct'){const d=agg(rows,'sum',k.denominator);return d?agg(rows,'sum',k.numerator)/d*100:null}if(k.op==='difference_sum')return agg(rows,'sum',k.left)-agg(rows,'sum',k.right);if(k.op==='variation_pct'){const p=agg(rows,'sum',k.previous);return p?(agg(rows,'sum',k.current)-p)/p*100:null}return null}
function makeFilters(){const host=$('filters'),anchor=host.querySelector('.actions');(P.filters||[]).forEach(f=>{const vals=[...new Set(ROWS.map(r=>String(r[f.column]??'')).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'es'));const box=document.createElement('div');box.className='filter';const lab=document.createElement('label');lab.textContent=f.label||f.column;const sel=document.createElement('select');sel.innerHTML='<option value="">Todos</option>'+vals.map(v=>`<option>${esc(v)}</option>`).join('');sel.addEventListener('change',()=>{fstate[f.column]=sel.value;render()});box.append(lab,sel);host.insertBefore(box,anchor);f._sel=sel})}
function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}function group(rows,c,op,m){const map=new Map();rows.forEach(r=>{const k=String(r[c]??'Sin dato');if(!map.has(k))map.set(k,[]);map.get(k).push(r)});return [...map].map(([k,rs])=>({k,v:agg(rs,op||'sum',m),rs})).sort((a,b)=>b.v-a.v)}
function renderKpis(rows){$('kpis').innerHTML=(P.kpis||[]).map(k=>`<article class="kpi"><div class="l">${esc(k.label||k.column||k.op)}</div><div class="v">${fmt(kval(k,rows),k.format)}</div></article>`).join('')}
function barChart(c,rows){let groups=group(rows,c.dimension,c.op,c.measure).slice(0,c.top_n||10);const max=Math.max(1,...groups.map(x=>Math.abs(x.v)));return `<div class="bars">${groups.map(x=>`<div class="bargrp" title="${esc(x.k)}: ${fmt(x.v)}"><div class="bar" style="height:${Math.max(1,Math.abs(x.v)/max*100)}%"></div><div class="xlabel">${esc(x.k)}</div></div>`).join('')}</div>`}
function compChart(c,rows){const measures=c.measures||[];const map=new Map();rows.forEach(r=>{const k=String(r[c.dimension]??'Sin dato');if(!map.has(k))map.set(k,Array(measures.length).fill(0));const a=map.get(k);measures.forEach((m,i)=>a[i]+=num(r[m]))});let gs=[...map].map(([k,v])=>({k,v,total:Math.max(...v.map(Math.abs))})).sort((a,b)=>b.total-a.total).slice(0,c.top_n||10);const max=Math.max(1,...gs.flatMap(g=>g.v.map(Math.abs)));const lg=measures.map((m,i)=>`<span><i class="dot ${i===1?'alt':i===2?'prev':''}"></i>${esc(m)}</span>`).join('');return `<div class="legend">${lg}</div><div class="bars">${gs.map(g=>`<div class="bargrp">${g.v.map((v,i)=>`<div class="bar ${i===1?'alt':i===2?'prev':''}" title="${esc(g.k)} · ${esc(measures[i])}: ${fmt(v)}" style="height:${Math.max(1,Math.abs(v)/max*100)}%"></div>`).join('')}<div class="xlabel">${esc(g.k)}</div></div>`).join('')}</div>`}
function lineChart(c,rows){let groups=group(rows,c.dimension,c.op,c.measure).slice().sort((a,b)=>String(a.k).localeCompare(String(b.k)));if(groups.length>60)groups=groups.slice(-60);const vals=groups.map(x=>x.v),min=Math.min(0,...vals),max=Math.max(1,...vals),w=800,h=240,pad=28,span=max-min||1;const pts=groups.map((x,i)=>`${pad+(w-pad*2)*(i/Math.max(1,groups.length-1))},${h-pad-(h-pad*2)*((x.v-min)/span)}`).join(' ');return `<svg class="line-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(c.title)}"><line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#315361"/><polyline fill="none" stroke="#24c4d2" stroke-width="4" points="${pts}"/>${groups.map((x,i)=>{const [cx,cy]=pts.split(' ')[i].split(',');return `<circle cx="${cx}" cy="${cy}" r="4" fill="#73e3ea"><title>${esc(x.k)}: ${fmt(x.v)}</title></circle>`}).join('')}</svg>`}
function donut(c,rows){const gs=group(rows,c.dimension,c.op,c.measure).slice(0,c.top_n||8),tot=gs.reduce((a,x)=>a+Math.max(0,x.v),0)||1;let cur=0;const stops=gs.map((x,i)=>{const a=cur/tot*360;cur+=Math.max(0,x.v);const b=cur/tot*360;const colors=['#16b8c8','#34869a','#5eaab5','#76c7c7','#2b6074','#7ccfda','#4c8da2','#9bdde1'];return `${colors[i%colors.length]} ${a}deg ${b}deg`}).join(',');return `<div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap"><div style="width:220px;height:220px;border-radius:50%;background:conic-gradient(${stops});box-shadow:inset 0 0 0 55px var(--pc-panel)"></div><div class="legend" style="display:block">${gs.map((x,i)=>`<div style="margin:7px 0">${esc(x.k)} · ${fmt(x.v)} (${(x.v/tot*100).toFixed(1)}%)</div>`).join('')}</div></div>`}
function renderCharts(rows){$('charts').innerHTML=(P.charts||[]).map(c=>{let body='';if(c.type==='comparison_bar')body=compChart(c,rows);else if(c.type==='line')body=lineChart(c,rows);else if(c.type==='donut')body=donut(c,rows);else body=barChart(c,rows);return `<article class="card"><h2>${esc(c.title||'Gráfica')}</h2><div class="chart">${body}</div></article>`}).join('')}
function renderTable(rows){const t=P.table||{},cols=t.columns||Object.keys(ROWS[0]||{}).slice(0,10),lim=t.limit||100;$('tableTitle').textContent=t.title||'Detalle';$('thead').innerHTML='<tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>';$('tbody').innerHTML=rows.slice(0,lim).map(r=>'<tr>'+cols.map(c=>`<td>${esc(r[c]??'')}</td>`).join('')+'</tr>').join('');$('rownote').textContent=`Mostrando ${Math.min(rows.length,lim)} de ${rows.length} registros filtrados. Dataset original: ${DATA.meta.rows} filas.`}
function render(){const rows=filtered();renderKpis(rows);renderCharts(rows);renderTable(rows)}$('clear').addEventListener('click',()=>{Object.keys(fstate).forEach(k=>delete fstate[k]);(P.filters||[]).forEach(f=>{if(f._sel)f._sel.value=''});render()});$('csv').addEventListener('click',()=>{const rows=filtered();if(!rows.length)return;const cols=Object.keys(rows[0]);const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';const txt=[cols.map(q).join(','),...rows.map(r=>cols.map(c=>q(r[c])).join(','))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([txt],{type:'text/csv;charset=utf-8'}));a.download='dashboard_filtrado.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});makeFilters();render()})();</script></body></html>'''
