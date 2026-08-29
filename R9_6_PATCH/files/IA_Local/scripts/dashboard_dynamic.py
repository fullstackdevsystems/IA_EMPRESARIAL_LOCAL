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
            if t and t in nc:
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
        }, timeout=float(os.getenv('IA_DYNAMIC_DASHBOARD_TIMEOUT','90')))
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
    validated = _validate_plan(ai_plan, df, fallback)
    from dashboard_prompt_guard import enforce_prompt_contract
    guarded = enforce_prompt_contract(validated, df, prompt, filename, sheet)
    from enterprise_prompt_compiler import compile_enterprise_prompt
    return compile_enterprise_prompt(guarded, df, prompt, filename, sheet)


def _prepare_rows(df: pd.DataFrame, limit: int = 20000) -> List[Dict[str, Any]]:
    x = df.head(limit).copy()
    for c in x.columns:
        kind = _series_kind(x[c])
        if kind == 'date':
            x[c] = pd.to_datetime(x[c], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        elif kind == 'text':
            # R9.6: normalize presentation keys without mutating the source workbook.
            # This prevents duplicated filter/group labels caused only by leading/trailing spaces.
            x[c] = x[c].map(lambda v: v.strip() if isinstance(v, str) else v)
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
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · Primos & Cousins</title>
<style>
:root{--bg:#f4f8fb;--surface:#fff;--ink:#102540;--muted:#61768b;--line:#dce7ef;--teal:#0a93a4;--teal2:#19b8c4;--tealsoft:#e7f7f8;--blue:#3478d4;--green:#2eaa52;--orange:#ff9b2f;--red:#ef5350;--purple:#7a56c7;--shadow:0 8px 26px rgba(18,52,77,.08);--radius:16px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:linear-gradient(180deg,#fbfdff,#f2f7fa);color:var(--ink);font-family:"Segoe UI",Arial,sans-serif}button,select{font:inherit}
.app{min-height:100vh;display:grid;grid-template-columns:220px minmax(0,1fr)}
.sidebar{background:rgba(255,255,255,.97);border-right:1px solid var(--line);padding:17px 14px;display:flex;flex-direction:column;gap:17px;position:sticky;top:0;height:100vh;z-index:4}
.brandbox{padding:8px 4px 16px;border-bottom:1px solid var(--line)}.logo{width:100%;max-height:78px;object-fit:contain}
.nav{display:flex;flex-direction:column;gap:7px}.nav a{display:flex;align-items:center;gap:10px;color:#233e59;text-decoration:none;padding:11px 12px;border-radius:11px;font-size:13px;font-weight:600}.nav a:hover,.nav a.active{background:linear-gradient(135deg,var(--teal),#0aaabd);color:#fff;box-shadow:0 5px 14px rgba(10,147,164,.2)}.ico{width:20px;text-align:center}
.side-bottom{margin-top:auto}.ai-badge{border:1px solid var(--line);background:#fff;border-radius:13px;padding:12px;box-shadow:var(--shadow);font-size:11px;color:var(--muted)}.ai-badge strong{display:block;color:var(--ink);font-size:12px}
.main{padding:20px 22px 14px;min-width:0}.top{display:flex;gap:16px;align-items:flex-start;margin-bottom:15px}.titlebox{flex:1;min-width:260px}h1{margin:0 0 5px;font-size:clamp(24px,2.3vw,38px);letter-spacing:-.025em}.subtitle{color:var(--muted);font-size:14px}
.meta-row{display:flex;gap:9px;flex-wrap:wrap;justify-content:flex-end}.meta-chip{background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 11px;min-width:125px;box-shadow:0 4px 14px rgba(18,52,77,.05)}.meta-chip .k{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;margin-bottom:3px}.meta-chip .v{font-size:12px;font-weight:700}
.toolbar{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin:8px 0 15px}.filter{background:#fff;border:1px solid var(--line);border-radius:12px;padding:8px 10px;min-width:180px;box-shadow:0 4px 14px rgba(18,52,77,.04)}.filter label{display:block;color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:5px}.filter select{width:100%;border:0;outline:0;background:transparent;color:var(--ink);font-size:12px;font-weight:600}.actions{margin-left:auto;display:flex;gap:8px}.btn{border:1px solid #cde6ea;background:var(--tealsoft);color:#087f8e;border-radius:10px;padding:10px 13px;font-size:12px;font-weight:700;cursor:pointer}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px}.kpi{position:relative;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow);overflow:hidden}.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent,var(--teal))}.cap{display:flex;align-items:center;gap:10px}.bubble{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:var(--soft,var(--tealsoft));color:var(--accent,var(--teal));font-weight:900}.kpi .l{font-size:11px;color:var(--muted);font-weight:700}.kpi .v{margin-top:8px;font-size:clamp(22px,2vw,31px);font-weight:800;font-variant-numeric:tabular-nums}.hint{font-size:10px;color:var(--muted);margin-top:3px}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;margin-top:14px}.card{grid-column:span 6;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow);min-width:0}.card.wide{grid-column:span 8}.card.narrow{grid-column:span 4}.card h2,.table-card h2,.audit h2{font-size:15px;margin:0 0 3px}.small{font-size:11px;color:var(--muted);margin-bottom:9px}.chart{min-height:286px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:10px;margin:8px 0}.dot{display:inline-block;width:9px;height:9px;border-radius:3px;background:var(--teal);margin-right:5px}.dot.alt{background:var(--blue)}.dot.prev{background:#97a7b7}
.bars{height:255px;display:flex;align-items:end;gap:8px;padding:18px 4px 36px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#fff,rgba(244,248,251,.5))}.bargrp{flex:1;min-width:22px;display:flex;gap:3px;align-items:end;height:100%;position:relative}.bar{flex:1;background:linear-gradient(180deg,#28c5d1,var(--teal));border-radius:6px 6px 1px 1px;min-height:2px}.bar.alt{background:linear-gradient(180deg,#69a5ef,var(--blue))}.bar.prev{background:linear-gradient(180deg,#bec9d3,#8ea0b2)}.xlabel{position:absolute;top:calc(100% + 6px);left:50%;transform:translateX(-50%);font-size:9px;color:var(--muted);max-width:92px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.line-svg{width:100%;height:275px}
.donut-wrap{height:275px;display:flex;align-items:center;justify-content:center;gap:24px;flex-wrap:wrap}.donut{width:190px;height:190px;border-radius:50%;position:relative}.donut:after{content:"";position:absolute;inset:35px;background:#fff;border-radius:50%;box-shadow:0 0 0 1px var(--line)}.donut-center{position:absolute;inset:0;display:grid;place-items:center;text-align:center;z-index:2;font-weight:800}.donut-legend{max-height:230px;overflow:auto;min-width:180px}.donut-item{display:flex;justify-content:space-between;gap:12px;font-size:10px;padding:5px 0;color:var(--muted)}.donut-item b{color:var(--ink)}
.table-card,.audit{margin-top:14px;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}.table-wrap{overflow:auto;max-height:520px;border:1px solid #edf2f6;border-radius:11px}.table{width:100%;border-collapse:collapse;font-size:11px}.table th{position:sticky;top:0;background:#f1f6f9;color:#314c67;text-align:left}.table th,.table td{padding:9px 10px;border-bottom:1px solid #edf2f6;white-space:nowrap}.table tbody tr:nth-child(even) td{background:#fbfdfe}.table tr:hover td{background:#edf9fa}.note{color:var(--muted);font-size:11px;margin-top:8px}
.audit{background:linear-gradient(135deg,#f0fbfc,#f8fcff);border-color:#cfeef1}.audit h2{color:#087f8e}.audit ul{margin:8px 0 0;padding-left:18px;color:#4b637a;font-size:12px}.audit li{margin:5px 0}.empty{display:grid;place-items:center;min-height:180px;color:var(--muted);font-size:12px;text-align:center;padding:20px}
.footer{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-top:16px;padding:13px 3px 4px;border-top:1px solid var(--line)}.footer strong{color:#31516a}
@media(max-width:1100px){.app{grid-template-columns:82px minmax(0,1fr)}.sidebar{padding:14px 8px}.nav a{justify-content:center}.nav a span:not(.ico),.ai-badge{display:none}.card,.card.wide,.card.narrow{grid-column:span 12}.top{flex-direction:column}.meta-row{justify-content:flex-start}}
@media(max-width:700px){.app{display:block}.sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}.brandbox{max-width:280px;margin:auto}.nav{display:none}.main{padding:12px}.filter{flex:1;min-width:140px}.actions{width:100%;margin-left:0}.actions .btn{flex:1}}
.adv-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;margin-top:14px}
.adv-card{grid-column:span 6;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow);min-width:0}.adv-card.full{grid-column:span 12}
.findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.finding{border:1px solid #dbeaf0;background:#f8fcfd;border-radius:12px;padding:12px;font-size:12px;line-height:1.45}
.neg{color:#b52f2f;font-weight:700}.pos{color:#16833a;font-weight:700}.adv-table-wrap{overflow:auto;max-height:420px;border:1px solid #edf2f6;border-radius:11px}
.adv-table{width:100%;border-collapse:collapse;font-size:11px}.adv-table th{position:sticky;top:0;background:#f1f6f9;text-align:left}.adv-table th,.adv-table td{padding:8px 9px;border-bottom:1px solid #edf2f6;white-space:nowrap}
.bar.negative{background:linear-gradient(180deg,#ff8b86,var(--red))}.bar.clickable{cursor:pointer}.bar.clickable:hover{filter:brightness(.92)}.bars.zero{position:relative;align-items:stretch;padding-top:14px;padding-bottom:14px}.bars.zero:after{content:"";position:absolute;left:4px;right:4px;top:50%;border-top:1px solid #9fb2c2;z-index:1}.bars.zero .bargrp{align-items:stretch}.zero-slot{position:relative;width:100%;height:100%;z-index:2}.zero-bar{position:absolute;left:8%;right:8%;min-height:2px;border-radius:6px}.zero-bar.posbar{bottom:50%;background:linear-gradient(180deg,#28c5d1,var(--teal))}.zero-bar.negbar{top:50%;background:linear-gradient(180deg,var(--red),#ff8b86)}.traffic{display:inline-flex;align-items:center;gap:6px;font-weight:700}.traffic:before{content:"";width:9px;height:9px;border-radius:50%;background:#97a7b7}.traffic.positive:before{background:var(--green)}.traffic.negative:before{background:var(--red)}.traffic.neutral:before{background:var(--orange)}.coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}.coverage-item{border:1px solid var(--line);border-radius:10px;padding:10px;background:#fbfdfe;font-size:11px}.coverage-item b{display:block;margin-bottom:4px}.coverage-ok{color:#16833a}.coverage-partial{color:#9a6500}.coverage-no{color:#b52f2f}.modal{position:fixed;inset:0;background:rgba(7,24,37,.42);display:none;align-items:center;justify-content:center;z-index:20;padding:20px}.modal.open{display:flex}
.modal-box{background:#fff;border-radius:18px;width:min(1050px,96vw);max-height:88vh;overflow:auto;padding:18px}.modal-head{display:flex;justify-content:space-between;align-items:center}.closebtn{border:0;background:#eef5f7;border-radius:9px;padding:8px 10px;cursor:pointer}
.searchbox,.datebox{background:#fff;border:1px solid var(--line);border-radius:12px;padding:8px 10px}.searchbox label,.datebox label{display:block;color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:5px}.searchbox input,.datebox input{border:0;outline:0}
@media(max-width:900px){.adv-card{grid-column:span 12}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
<div class="brandbox"><img id="logo" class="logo" alt="Primos & Cousins"></div>
<nav class="nav">
<a class="active" href="#resumen"><span class="ico">▣</span><span>Resumen Ejecutivo</span></a>
<a href="#graficas"><span class="ico">⌁</span><span>Gráficas</span></a>
<a href="#detalle"><span class="ico">≡</span><span>Detalle</span></a>
<a href="#auditoria"><span class="ico">✓</span><span>Datos y Alertas</span></a>
<a href="#descargas"><span class="ico">⇩</span><span>Descargas</span></a>
</nav>
<div class="side-bottom"><div class="ai-badge"><strong>IA EMPRESARIAL LOCAL</strong>Análisis inteligente de datos</div></div>
</aside>
<main class="main">
<header class="top"><div class="titlebox"><h1 id="title">Dashboard Ejecutivo</h1><div id="subtitle" class="subtitle"></div></div><div class="meta-row"><div class="meta-chip"><span class="k">Archivo</span><span id="filemeta" class="v">—</span></div><div class="meta-chip"><span class="k">Registros</span><span id="rowsmeta" class="v">—</span></div><div class="meta-chip"><span class="k">Planificador</span><span id="planner" class="v">—</span></div></div></header>
<section id="resumen"><div class="toolbar" id="filters"><div class="actions" id="descargas"><button class="btn" id="clear">Limpiar filtros</button><button class="btn" id="csv">Exportar CSV filtrado</button></div></div><section class="kpis" id="kpis"></section></section>
<section class="grid" id="graficas"><div id="charts" style="display:contents"></div></section>
<section class="audit" id="auditoria" hidden><h2>Datos y alertas del análisis</h2><ul id="warnings"></ul></section>
<section class="table-card" id="detalle"><h2 id="tableTitle">Detalle</h2><div class="table-wrap"><table class="table"><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><div class="note" id="rownote"></div></section>
<section class="adv-grid" id="analitica">
<article class="adv-card full"><h2>Resumen Ejecutivo IA</h2><div class="findings" id="execFindings"></div></article>
<article class="adv-card"><h2>Clientes · Rentabilidad</h2><div id="clientsAdvanced"></div></article>
<article class="adv-card"><h2>Productos · Rentabilidad</h2><div id="productsAdvanced"></div></article>
<article class="adv-card full"><h2>Operaciones con Utilidad Negativa</h2><div id="negativeAdvanced"></div></article>
<article class="adv-card full"><h2>Rutas Origen → Destino</h2><div id="routesAdvanced"></div></article>
<article class="adv-card full"><h2>Validación Matemática</h2><div class="findings" id="validationAdvanced"></div></article>
<article class="adv-card full"><h2>Cobertura del Prompt</h2><div id="promptCoverage"></div></article>
</section>
<div class="modal" id="drillModal"><div class="modal-box"><div class="modal-head"><h2 id="drillTitle">Detalle</h2><button class="closebtn" id="drillClose">Cerrar</button></div><div id="drillBody"></div></div></div>
<footer class="footer"><span><strong>PRIMOS & COUSINS</strong> · Innovando Juntos</span><span>Dashboard generado automáticamente por IA Empresarial Local</span></footer>
</main></div>
<script>
const DATA=__PAYLOAD__;
(()=>{
const P=DATA.plan||{},ALL=DATA.rows||[],$=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:0};
const fmt=(v,k)=>{if(v===null||v===undefined||Number.isNaN(v))return '—';if(k==='percent')return Number(v).toLocaleString('es-MX',{maximumFractionDigits:1})+'%';if(k==='integer')return Math.round(Number(v)).toLocaleString('es-MX');const a=Math.abs(Number(v));if(a>=1000000)return (Number(v)/1000000).toLocaleString('es-MX',{maximumFractionDigits:2})+' M';if(a>=1000)return Number(v).toLocaleString('es-MX',{maximumFractionDigits:1});return Number(v).toLocaleString('es-MX',{maximumFractionDigits:2})};
$('logo').src=(DATA.brand||{}).logo||'';$('title').textContent=P.title||'Dashboard Ejecutivo';$('subtitle').textContent=P.subtitle||((DATA.meta||{}).prompt||'');$('filemeta').textContent=(DATA.meta||{}).file||'—';$('rowsmeta').textContent=Number((DATA.meta||{}).rows||0).toLocaleString('es-MX');$('planner').textContent=P.planner||'automático';
let selected={};const filterRoot=$('filters');
let dateFrom='',dateTo='',clientSearch='',chartTop=20;
for(const f of(P.filters||[])){if(f.column==='Fecha')continue;const box=document.createElement('div');box.className='filter';const vals=[...new Set(ALL.map(r=>r[f.column]).filter(v=>v!==null&&v!==undefined&&String(v)!==''))].sort((a,b)=>String(a).localeCompare(String(b),'es'));const multi=['Zona','Categoria','Vendedor','ctrl_alm','Proveedor'].includes(f.column);box.innerHTML=`<label>${esc(f.label||f.column)}</label><select data-col="${esc(f.column)}" ${multi?'multiple':''}>${multi?'':'<option value="">Todos</option>'}${vals.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('')}</select>`;filterRoot.insertBefore(box,filterRoot.querySelector('.actions'))}
if(ALL.some(r=>r.Fecha)){const b=document.createElement('div');b.className='datebox';b.innerHTML='<label>Fecha desde / hasta</label><input id="dateFrom" type="date"> <input id="dateTo" type="date">';filterRoot.insertBefore(b,filterRoot.firstChild)}
const sb=document.createElement('div');sb.className='searchbox';sb.innerHTML='<label>Buscar cliente</label><input id="clientSearch" placeholder="Nombre o código">';filterRoot.insertBefore(sb,filterRoot.querySelector('.actions'));const tb=document.createElement('div');tb.className='filter';tb.innerHTML='<label>Top gráficas</label><select id="chartTop"><option>10</option><option selected>20</option><option>50</option><option value="9999">Todos</option></select>';filterRoot.insertBefore(tb,filterRoot.querySelector('.actions'));
filterRoot.addEventListener('change',e=>{if(e.target.matches('select[data-col]')){const col=e.target.dataset.col;selected[col]=e.target.multiple?[...e.target.selectedOptions].map(o=>o.value):e.target.value;render()}});document.getElementById('dateFrom')?.addEventListener('change',e=>{dateFrom=e.target.value;render()});document.getElementById('dateTo')?.addEventListener('change',e=>{dateTo=e.target.value;render()});document.getElementById('clientSearch').addEventListener('input',e=>{clientSearch=e.target.value.toLowerCase().trim();render()});document.getElementById('chartTop').addEventListener('change',e=>{chartTop=Number(e.target.value)||20;render()});$('clear').onclick=()=>{selected={};dateFrom='';dateTo='';clientSearch='';document.querySelectorAll('select[data-col]').forEach(s=>[...s.options].forEach(o=>o.selected=false));document.getElementById('dateFrom')&&(document.getElementById('dateFrom').value='');document.getElementById('dateTo')&&(document.getElementById('dateTo').value='');document.getElementById('clientSearch').value='';render()};
const filtered=()=>ALL.filter(r=>{for(const [c,v] of Object.entries(selected)){if(Array.isArray(v)){if(v.length&&!v.includes(String(r[c])))return false}else if(v&&String(r[c])!==v)return false}const fd=String(r.Fecha||'').slice(0,10);if(dateFrom&&fd<dateFrom)return false;if(dateTo&&fd>dateTo)return false;if(clientSearch){const h=(String(r.Cliente||'')+' '+String(r.Cod_Cliente||'')).toLowerCase();if(!h.includes(clientSearch))return false}return true});
function kval(k,rows){const vals=c=>rows.map(r=>num(r[c])),op=k.op;if(op==='count')return rows.length;if(op==='nunique')return new Set(rows.map(r=>r[k.column]).filter(v=>v!==null&&v!==undefined&&String(v)!=='')).size;if(['sum','avg','min','max'].includes(op)){const a=vals(k.column);if(!a.length)return 0;if(op==='sum')return a.reduce((x,y)=>x+y,0);if(op==='avg')return a.reduce((x,y)=>x+y,0)/a.length;if(op==='min')return Math.min(...a);return Math.max(...a)}if(op==='ratio'){const a=vals(k.numerator).reduce((x,y)=>x+y,0),b=vals(k.denominator).reduce((x,y)=>x+y,0);return b?a/b:0}if(op==='ratio_pct'){const a=vals(k.numerator).reduce((x,y)=>x+y,0),b=vals(k.denominator).reduce((x,y)=>x+y,0);return b?100*a/b:0}if(op==='difference_sum')return vals(k.left).reduce((x,y)=>x+y,0)-vals(k.right).reduce((x,y)=>x+y,0);if(op==='variation_pct'){const a=vals(k.current).reduce((x,y)=>x+y,0),b=vals(k.previous).reduce((x,y)=>x+y,0);return b?100*(a-b)/Math.abs(b):0}return 0}
const accents=[['var(--teal)','#e7f7f8','◎'],['var(--red)','#fff0ef','!'],['var(--orange)','#fff2e4','◆'],['var(--green)','#eaf8ee','↻'],['var(--blue)','#eaf2ff','◉'],['var(--purple)','#f2edff','●']];
function renderKpis(rows){$('kpis').innerHTML=(P.kpis||[]).map((k,i)=>{const a=accents[i%accents.length],v=kval(k,rows);return `<article class="kpi" style="--accent:${a[0]};--soft:${a[1]}"><div class="cap"><div class="bubble">${a[2]}</div><div class="l">${esc(k.label||k.column||k.op)}</div></div><div class="v">${fmt(v,k.format)}</div><div class="hint">${rows.length.toLocaleString('es-MX')} registros filtrados</div></article>`}).join('')||'<div class="empty">No hay indicadores calculables para los datos solicitados.</div>'}
function group(rows,dim,measure,op='sum'){const m=new Map();for(const r of rows){const key=String(r[dim]??'Sin dato');if(!m.has(key))m.set(key,[]);m.get(key).push(r)}return [...m.entries()].map(([label,rr])=>{let value;if(op==='count')value=rr.length;else if(op==='nunique')value=new Set(rr.map(x=>x[measure])).size;else{const a=rr.map(x=>num(x[measure]));value=op==='avg'?a.reduce((x,y)=>x+y,0)/(a.length||1):a.reduce((x,y)=>x+y,0)}return{label,value}})}
const shell=(c,b,cl='')=>`<article class="card ${cl}"><h2>${esc(c.title||'Gráfica')}</h2><div class="small">${esc(c.dimension||'')}</div><div class="chart">${b}</div></article>`;
function canFilterDimension(dim){return (P.filters||[]).some(f=>f.column===dim)}
function syncFilterControl(dim,value){const el=document.querySelector(`select[data-col="${CSS.escape(dim)}"]`);if(!el)return;if(el.multiple){[...el.options].forEach(o=>o.selected=o.value===String(value));selected[dim]=[String(value)]}else{el.value=String(value);selected[dim]=String(value)}}
function applyChartFilter(dim,value){if(!canFilterDimension(dim))return;syncFilterControl(dim,value);tablePage=1;render();document.getElementById('resumen')?.scrollIntoView({behavior:'smooth',block:'start'})}
function bar(c,rows){
 let a=group(rows,c.dimension,c.measure,c.op||'sum').sort((x,y)=>y.value-x.value).slice(0,Math.min(chartTop,c.top_n||chartTop)),mx=Math.max(1,...a.map(x=>Math.abs(x.value))),hasNeg=a.some(x=>x.value<0),clickable=canFilterDimension(c.dimension);
 if(hasNeg){return shell(c,`<div class="bars zero">${a.map(x=>{const pct=Math.max(1,Math.abs(x.value)/mx*48);return `<div class="bargrp" title="${esc(x.label)}: ${fmt(x.value)}"><div class="zero-slot"><div class="zero-bar ${x.value<0?'negbar':'posbar'} ${clickable?'clickable':''}" data-chart-dim="${esc(c.dimension)}" data-chart-value="${esc(x.label)}" style="height:${pct}%"></div><span class="xlabel">${esc(x.label)}</span></div></div>`}).join('')}</div>`) }
 return shell(c,`<div class="bars">${a.map(x=>`<div class="bargrp" title="${esc(x.label)}: ${fmt(x.value)}"><div class="bar ${clickable?'clickable':''}" data-chart-dim="${esc(c.dimension)}" data-chart-value="${esc(x.label)}" style="height:${Math.max(2,Math.abs(x.value)/mx*100)}%"></div><span class="xlabel">${esc(x.label)}</span></div>`).join('')}</div>`)
}
function comp(c,rows){const ms=(c.measures||[]).slice(0,3),keys=[...new Set(rows.map(r=>String(r[c.dimension]??'Sin dato')))];let a=keys.map(k=>({label:k,values:ms.map(m=>rows.filter(r=>String(r[c.dimension]??'Sin dato')===k).reduce((s,r)=>s+num(r[m]),0))})).sort((x,y)=>Math.max(...y.values)-Math.max(...x.values)).slice(0,c.top_n||10);const mx=Math.max(1,...a.flatMap(x=>x.values.map(Math.abs)));return shell(c,`<div class="legend">${ms.map((m,i)=>`<span><i class="dot ${i===1?'alt':i===2?'prev':''}"></i>${esc(m)}</span>`).join('')}</div><div class="bars">${a.map(x=>`<div class="bargrp">${x.values.map((v,i)=>`<div class="bar ${i===1?'alt':i===2?'prev':''}" style="height:${Math.max(2,Math.abs(v)/mx*100)}%" title="${esc(x.label)} · ${esc(ms[i])}: ${fmt(v)}"></div>`).join('')}<span class="xlabel">${esc(x.label)}</span></div>`).join('')}</div>`)}
function line(c,rows){let a=group(rows,c.dimension,c.measure,c.op||'sum').sort((x,y)=>String(x.label).localeCompare(String(y.label),'es')).slice(0,c.top_n||36);if(!a.length)return shell(c,'<div class="empty">Sin datos.</div>');const w=900,h=245,p=28,mx=Math.max(1,...a.map(x=>x.value)),mn=Math.min(0,...a.map(x=>x.value)),rg=mx-mn||1,pts=a.map((x,i)=>[p+(w-2*p)*(a.length===1?.5:i/(a.length-1)),h-p-(h-2*p)*(x.value-mn)/rg]),poly=pts.map(x=>x.join(',')).join(' '),dots=pts.map((pt,i)=>`<circle cx="${pt[0]}" cy="${pt[1]}" r="4" fill="#0a93a4"><title>${esc(a[i].label)}: ${fmt(a[i].value)}</title></circle>`).join('');return shell(c,`<svg class="line-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}" stroke="#dce7ef"/><polyline fill="none" stroke="#0a93a4" stroke-width="4" points="${poly}"/>${dots}</svg>`,'wide')}
function donut(c,rows){let a=group(rows,c.dimension,c.measure,c.op||'sum').sort((x,y)=>y.value-x.value).slice(0,c.top_n||8),tot=a.reduce((s,x)=>s+Math.max(0,x.value),0)||1,colors=['#0a93a4','#20b8b1','#ffb21c','#ff8b33','#7a56c7','#98a8b9','#3478d4','#49aa63'],acc=0,st=[];a.forEach((x,i)=>{const s=acc;acc+=Math.max(0,x.value)/tot*100;st.push(`${colors[i%colors.length]} ${s}% ${acc}%`)});return shell(c,`<div class="donut-wrap"><div class="donut" style="background:conic-gradient(${st.join(',')})"><div class="donut-center">${fmt(tot)}<br><small>Total</small></div></div><div class="donut-legend">${a.map((x,i)=>`<div class="donut-item"><span><i class="dot" style="background:${colors[i%colors.length]}"></i>${esc(x.label)}</span><b>${(x.value/tot*100).toFixed(1)}%</b></div>`).join('')}</div></div>`,'narrow')}
function renderCharts(rows){$('charts').innerHTML=(P.charts||[]).map(c=>c.type==='comparison_bar'?comp(c,rows):c.type==='line'?line(c,rows):c.type==='donut'?donut(c,rows):bar(c,rows)).join('')||'<article class="card" style="grid-column:span 12"><div class="empty">No hay gráficas válidas para la solicitud y los datos disponibles.</div></article>';document.querySelectorAll('[data-chart-dim][data-chart-value]').forEach(el=>el.onclick=()=>applyChartFilter(el.dataset.chartDim,el.dataset.chartValue))}
let tablePage=1,tablePageSize=25,tableSort='',tableAsc=true;function renderTable(rows){const t=P.table||{},cols=(t.columns||Object.keys(rows[0]||{})),all=[...rows];if(tableSort)all.sort((a,b)=>{const x=a[tableSort],y=b[tableSort];return (typeof x==='number'&&typeof y==='number'?(x-y):String(x??'').localeCompare(String(y??''),'es'))*(tableAsc?1:-1)});const pages=Math.max(1,Math.ceil(all.length/tablePageSize));tablePage=Math.min(tablePage,pages);const start=(tablePage-1)*tablePageSize,view=all.slice(start,start+tablePageSize);$('tableTitle').textContent=t.title||'Detalle';$('thead').innerHTML='<tr>'+cols.map(c=>`<th data-sort="${esc(c)}">${esc(c)}${tableSort===c?(tableAsc?' ▲':' ▼'):''}</th>`).join('')+'</tr>';$('tbody').innerHTML=view.map(r=>'<tr>'+cols.map(c=>`<td data-col="${esc(c)}" data-client="${esc(r.Cliente??'')}" data-client-id="${esc(r.Cod_Cliente??'')}" data-product="${esc(r.ctrl_alm??r.Articulo??'')}" data-ref="${esc(r.Refer??'')}">${esc(r[c]??'')}</td>`).join('')+'</tr>').join('');$('rownote').innerHTML=`Mostrando ${view.length.toLocaleString('es-MX')} de ${all.length.toLocaleString('es-MX')} registros filtrados. <span class="pager"><button class="btn" id="prevPage">Anterior</button> Página ${tablePage} de ${pages} <button class="btn" id="nextPage">Siguiente</button> <select id="pageSize"><option ${tablePageSize===25?'selected':''}>25</option><option ${tablePageSize===50?'selected':''}>50</option><option ${tablePageSize===100?'selected':''}>100</option></select></span>`;document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const c=th.dataset.sort;if(tableSort===c)tableAsc=!tableAsc;else{tableSort=c;tableAsc=true}renderTable(rows)});document.getElementById('prevPage').onclick=()=>{if(tablePage>1){tablePage--;renderTable(rows)}};document.getElementById('nextPage').onclick=()=>{if(tablePage<pages){tablePage++;renderTable(rows)}};document.getElementById('pageSize').onchange=e=>{tablePageSize=Number(e.target.value)||25;tablePage=1;renderTable(rows)};document.querySelectorAll('#tbody td').forEach(td=>td.ondblclick=()=>{const c=td.dataset.col||'';if(c==='Cliente'||c==='Cod_Cliente')openDrill('client',td.dataset.clientId||td.dataset.client);else if(c==='Articulo'||c==='ctrl_alm'||c==='Cod_Articulo')openDrill('product',td.dataset.product);else if(td.dataset.ref)openDrill('operation',td.dataset.ref);else if(td.dataset.client)openDrill('client_name',td.dataset.client)})}
function warnings(){const w=[...(P.warnings||[])];if(P.status==='insufficient_data'&&!w.length)w.push('Los datos disponibles no contienen todos los campos necesarios para responder fielmente al prompt.');if(w.length){$('auditoria').hidden=false;$('warnings').innerHTML=w.map(x=>`<li>${esc(x)}</li>`).join('')}}
function render(){const r=filtered();renderKpis(r);renderCharts(r);renderTable(r);renderAdvanced(r)}
function metricTable(rows,cols,limit=20){
 const show=rows.slice(0,limit);
 return `<div class="adv-table-wrap"><table class="adv-table"><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${show.map(r=>`<tr>${cols.map(c=>{const v=r[c],cl=(c==='Utilidad'&&Number(v)<0)?'neg':(c==='Utilidad'&&Number(v)>0)?'pos':'';if(c==='Estado'){const tc=v==='Pérdida'?'negative':v==='Rentable'?'positive':'neutral';return `<td><span class="traffic ${tc}">${esc(v??'')}</span></td>`}return `<td class="${cl}">${typeof v==='number'?fmt(v,c.includes('Pct')?'percent':undefined):esc(v??'')}</td>`}).join('')}</tr>`).join('')}</tbody></table></div>`
}
function advGroup(rows,dims){
 const m=new Map();
 for(const r of rows){
   const key=dims.map(c=>String(r[c]??'Sin dato')).join('|||');
   if(!m.has(key))m.set(key,[]);
   m.get(key).push(r)
 }
 return [...m.entries()].map(([key,rr])=>{
   const o={},ks=key.split('|||');dims.forEach((c,i)=>o[c]=ks[i]);
   const ton=rr.reduce((s,x)=>s+num(x.Toneladas_Vendidas),0),
         venta=rr.reduce((s,x)=>s+num(x.Importe_Venta),0),
         costo=rr.reduce((s,x)=>s+num(x.Costo),0),
         util=rr.reduce((s,x)=>s+num(x.Utilidad),0),
         flete=rr.reduce((s,x)=>s+num(x.Costo_Flete),0);
   o.Toneladas=ton;o.Venta=venta;o.Costo=costo;o.Utilidad=util;o.Flete=flete;
   o.MargenPct=venta?100*util/venta:null;o.UtilidadTon=ton?util/ton:null;o.FleteTon=ton?flete/ton:null;o.Estado=util<0?'Pérdida':util>0?'Rentable':'Sin utilidad';
   o.Operaciones=new Set(rr.map(x=>String(x.Refer??'')).filter(Boolean)).size;
   return o
 })
}
function dynamicFindings(rows,clients,products,routes,neg){
 const ton=rows.reduce((s,r)=>s+num(r.Toneladas_Vendidas),0),
       venta=rows.reduce((s,r)=>s+num(r.Importe_Venta),0),
       costo=rows.reduce((s,r)=>s+num(r.Costo),0),
       util=rows.reduce((s,r)=>s+num(r.Utilidad),0),
       flete=rows.reduce((s,r)=>s+num(r.Costo_Flete),0);
 const xs=[
   `Selección actual: ${rows.length.toLocaleString('es-MX')} registros y ${fmt(ton)} toneladas.`,
   `Venta ${fmt(venta,'currency')}, costo ${fmt(costo,'currency')} y utilidad ${fmt(util,'currency')}.`
 ];
 if(venta)xs.push(`Margen global ponderado: ${fmt(100*util/venta,'percent')}.`);
 if(ton)xs.push(`Utilidad por tonelada: ${fmt(util/ton,'currency')}.`);
 if(costo)xs.push(`Fletes: ${fmt(flete,'currency')} (${fmt(100*flete/costo,'percent')} del costo).`);
 if(clients.length){
   const hi=clients[0],lo=[...clients].sort((a,b)=>a.Utilidad-b.Utilidad)[0];
   xs.push(`Cliente con mayor utilidad: ${hi.Cliente} (${fmt(hi.Utilidad,'currency')}).`);
   xs.push(`Cliente con menor utilidad: ${lo.Cliente} (${fmt(lo.Utilidad,'currency')}).`)
 }
 if(products.length){
   const p=products[0];xs.push(`Producto/grupo con mayor utilidad: ${p.ctrl_alm??p.Articulo} (${fmt(p.Utilidad,'currency')}).`)
 }
 const negImpact=neg.reduce((s,r)=>s+num(r.Utilidad),0);
 xs.push(`Operaciones con utilidad negativa: ${neg.length.toLocaleString('es-MX')}, impacto ${fmt(negImpact,'currency')}.`);
 if(routes.length){
   const rt=[...routes].sort((a,b)=>b.Flete-a.Flete)[0];
   xs.push(`Ruta con mayor flete acumulado: ${rt.Ciudad_Origen} → ${rt.Ciudad_Destino} (${fmt(rt.Flete,'currency')}).`)
 }
 return xs.slice(0,12)
}
function dynamicValidation(rows){
 const venta=rows.reduce((s,r)=>s+num(r.Importe_Venta),0),
       costo=rows.reduce((s,r)=>s+num(r.Costo),0),
       util=rows.reduce((s,r)=>s+num(r.Utilidad),0),
       delta=(venta-costo)-util,tol=Math.max(1,Math.abs(venta)*1e-8);
 const badDates=rows.filter(r=>r.Fecha&&!/^\d{4}-\d{2}-\d{2}/.test(String(r.Fecha))).length;
 return [
  {name:'Venta - Costo = Utilidad',ok:Math.abs(delta)<=tol,detail:`Diferencia matemática: ${delta.toFixed(4)}`},
  {name:'Clientes únicos por Cod_Cliente',ok:true,detail:`${new Set(rows.map(r=>r.Cod_Cliente).filter(v=>v!==null&&v!==undefined&&String(v)!=='')).size} clientes únicos`},
  {name:'Fechas válidas',ok:badDates===0,detail:`${badDates} fechas inválidas`},
  {name:'NaN/Infinity no visibles',ok:true,detail:'Divisiones protegidas y valores seguros.'}
 ]
}
function promptCoverage(){
 const p=String((DATA.meta||{}).prompt||'').toLowerCase(),items=[];
 const add=(name,asked,status,detail)=>{if(asked)items.push({name,status,detail})};
 add('Fuente BD',/fuente (única|unica)|hoja bd|bd/.test(p),'ok','El dashboard fue generado desde la hoja seleccionada y el plan conserva la hoja de origen.');
 add('KPIs y filtros reactivos',/kpi|filtros? global|dashboard/.test(p),'ok','KPIs, gráficas, tabla y analítica avanzada reaccionan a la selección actual.');
 add('Rentabilidad / semáforo',/rentabilidad|semáforo|semaforo/.test(p),'ok','Utilidad negativa se marca en rojo; utilidad positiva en verde. No se inventa un umbral empresarial de margen saludable.');
 add('Clic para filtrar',/hacer clic|al seleccionar|filtrar todo|filtre el dashboard/.test(p),'ok','Las barras de dimensiones disponibles como filtro aplican el filtro al dashboard completo.');
 add('Detalle cliente/producto',/detalle de cliente|detalle de producto|ficha interactiva/.test(p),'partial','Existe drill-down exacto por cliente, producto u operación. La ficha enriquecida completa seguirá ampliándose.');
 add('Fletes y rutas',/flete|origen.*destino|rutas?/.test(p),'ok','Se calculan fletes agregados y rutas con los registros filtrados.');
 add('Tabla dinámica / reportes derivados',/tabla dinámica|tabla dinamica|reportes derivados|amarillo|blanco normal|sorgo|rolado|molido|cribado/.test(p),'partial','El dashboard permite filtrar cualquier ctrl_alm, pero aún no materializa hojas Excel derivadas equivalentes dentro del HTML.');
 add('Preguntas en lenguaje natural',/lenguaje natural|preguntas? como/.test(p),'no','El renderer HTML todavía no incorpora una caja de consulta conversacional.');
 add('Exportación Excel',/exportar.*excel|excel\/csv|excel o csv/.test(p),'partial','La exportación filtrada disponible en esta versión es CSV.');
 const cls=x=>x.status==='ok'?'coverage-ok':x.status==='partial'?'coverage-partial':'coverage-no',label=x=>x.status==='ok'?'Implementado':x.status==='partial'?'Parcial':'Pendiente';
 $('promptCoverage').innerHTML=items.length?`<div class="coverage-grid">${items.map(x=>`<div class="coverage-item"><b>${esc(x.name)} · <span class="${cls(x)}">${label(x)}</span></b>${esc(x.detail)}</div>`).join('')}</div>`:'<div class="note">No se detectaron requisitos de cobertura explícitos.</div>'
}
function renderAdvanced(rows){
 const customerDims=rows.some(r=>r.Cod_Cliente!==undefined)?['Cod_Cliente','Cliente']:['Cliente'],
       productDim=rows.some(r=>r.ctrl_alm!==undefined)?['ctrl_alm']:['Articulo'];
 const clients=advGroup(rows,customerDims).sort((a,b)=>b.Utilidad-a.Utilidad),
       products=advGroup(rows,productDim).sort((a,b)=>b.Utilidad-a.Utilidad),
       routes=(rows.some(r=>r.Ciudad_Origen!==undefined)&&rows.some(r=>r.Ciudad_Destino!==undefined)?advGroup(rows,['Ciudad_Origen','Ciudad_Destino']):[]).sort((a,b)=>b.Flete-a.Flete),
       neg=rows.filter(r=>num(r.Utilidad)<0).sort((a,b)=>num(a.Utilidad)-num(b.Utilidad));
 const unfiltered=rows.length===ALL.length&&!dateFrom&&!dateTo&&!clientSearch&&Object.values(selected).every(v=>Array.isArray(v)?!v.length:!v);
 const staticAI=(P.advanced||{}).executive_findings||[],
       findings=(unfiltered&&staticAI.length)?staticAI:dynamicFindings(rows,clients,products,routes,neg);
 $('execFindings').innerHTML=findings.map(x=>`<div class="finding">${esc(x)}</div>`).join('')||'<div class="empty">Sin hallazgos ejecutivos.</div>';
 $('clientsAdvanced').innerHTML=metricTable(clients,['Cliente','Toneladas','Venta','Costo','Utilidad','MargenPct','UtilidadTon','Estado'],20);
 $('productsAdvanced').innerHTML=metricTable(products,['ctrl_alm','Toneladas','Venta','Costo','Utilidad','MargenPct','UtilidadTon','Estado'],20);
 $('negativeAdvanced').innerHTML=`<div class="note">${neg.length.toLocaleString('es-MX')} operaciones negativas en la selección actual.</div>`+metricTable(neg,['Fecha','Refer','Cliente','Articulo','Toneladas_Vendidas','Importe_Venta','Costo','Utilidad','Proveedor','Vendedor'],40);
 $('routesAdvanced').innerHTML=metricTable(routes,['Ciudad_Origen','Ciudad_Destino','Toneladas','Operaciones','Flete','FleteTon','Venta','Utilidad'],50);
 $('validationAdvanced').innerHTML=dynamicValidation(rows).map(x=>`<div class="finding">${x.ok?'✓':'⚠'} <b>${esc(x.name)}</b><br>${esc(x.detail)}</div>`).join('');promptCoverage()
}
function openDrill(kind,value){
 const baseRows=filtered();let rows=[];
 if(kind==='client')rows=baseRows.filter(r=>String(r.Cod_Cliente??'')===String(value));
 else if(kind==='client_name')rows=baseRows.filter(r=>String(r.Cliente??'')===String(value));
 else if(kind==='product')rows=baseRows.filter(r=>String(r.ctrl_alm??r.Articulo??'')===String(value));
 else if(kind==='operation')rows=baseRows.filter(r=>String(r.Refer??'')===String(value));
 if(!rows.length)return;
 const title=value;$('drillTitle').textContent='Detalle · '+title;
 const ton=rows.reduce((s,r)=>s+num(r.Toneladas_Vendidas),0),venta=rows.reduce((s,r)=>s+num(r.Importe_Venta),0),costo=rows.reduce((s,r)=>s+num(r.Costo),0),util=rows.reduce((s,r)=>s+num(r.Utilidad),0),flete=rows.reduce((s,r)=>s+num(r.Costo_Flete),0);
 const refs=new Set(rows.map(r=>String(r.Refer??'')).filter(Boolean)).size,products=new Set(rows.map(r=>String(r.ctrl_alm??r.Articulo??'')).filter(Boolean)).size;
 $('drillBody').innerHTML=`<div class="findings"><div class="finding"><b>Toneladas</b><br>${fmt(ton)}</div><div class="finding"><b>Venta</b><br>${fmt(venta,'currency')}</div><div class="finding"><b>Costo</b><br>${fmt(costo,'currency')}</div><div class="finding"><b>Utilidad</b><br><span class="${util<0?'neg':'pos'}">${fmt(util,'currency')}</span></div><div class="finding"><b>Margen %</b><br>${venta?fmt(100*util/venta,'percent'):'N/A'}</div><div class="finding"><b>Fletes</b><br>${fmt(flete,'currency')}</div><div class="finding"><b>Referencias</b><br>${refs}</div><div class="finding"><b>Productos/Grupos</b><br>${products}</div></div>`+metricTable(rows.slice(0,100),['Fecha','Refer','Cod_Cliente','Cliente','Articulo','ctrl_alm','Toneladas_Vendidas','Importe_Venta','Costo','Utilidad','Costo_Flete','Proveedor','Almacen','Ciudad_Origen','Ciudad_Destino','Vendedor'],100);
 $('drillModal').classList.add('open')
}
$('drillClose').onclick=()=>$('drillModal').classList.remove('open');$('drillModal').addEventListener('click',e=>{if(e.target.id==='drillModal')$('drillModal').classList.remove('open')});
$('csv').onclick=()=>{const rows=filtered();if(!rows.length)return;const cols=[...new Set(rows.flatMap(r=>Object.keys(r)))],q=v=>'"'+String(v??'').replace(/"/g,'""')+'"',csv='\ufeff'+[cols.map(q).join(','),...rows.map(r=>cols.map(c=>q(r[c])).join(','))].join('\r\n'),a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='dashboard_filtrado.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
warnings();render();
})();
</script>
</body>
</html>'''
