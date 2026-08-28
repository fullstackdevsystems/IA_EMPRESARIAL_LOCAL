from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERSION = '8.5.5'
NAVY='#0B1F33'; BLUE='#2563EB'; ORANGE='#C97B0A'; GREEN='#169447'; RED='#D82C3F'; PURPLE='#7C3AED'; TEAL='#007D79'
MID='#697077'; BORDER='#DDE1E6'; LIGHT='#F4F7FB'; WHITE='#FFFFFF'; PALE_GREEN='#ECFDF5'; PALE_RED='#FFF1F1'; PALE_BLUE='#EFF6FF'; PALE_ORANGE='#FFF7ED'


def norm(value: Any) -> str:
    s = str(value or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9%]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _num(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors='coerce')
    ss = s.astype(str).str.replace(r'[^0-9,.-]', '', regex=True)
    if ss.str.contains(r'\.', regex=True).any() and ss.str.contains(',', regex=False).any():
        ss = ss.str.replace(',', '', regex=False)
    else:
        ss = ss.str.replace(',', '.', regex=False)
    return pd.to_numeric(ss, errors='coerce')


def _first_existing(df: pd.DataFrame, exact: Iterable[str], contains: Iterable[str] = (), exclude: Iterable[str] = ()) -> Optional[str]:
    cols = list(df.columns)
    nmap = {c: norm(c) for c in cols}
    exact_n = [norm(x) for x in exact]
    for wanted in exact_n:
        for c, nc in nmap.items():
            if nc == wanted:
                return c
    for token in (norm(x) for x in contains):
        cand = [c for c, nc in nmap.items() if token and token in nc and not any(norm(e) in nc for e in exclude)]
        if cand:
            cand.sort(key=lambda c: (len(nmap[c]), list(df.columns).index(c)))
            return cand[0]
    return None


def semantic_map(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Mapeo semántico robusto para BI, sin usar cardinalidad como criterio dominante.

    La prioridad es el significado del encabezado. Esto evita clasificar importes/costos
    como identificadores solo por tener muchos valores únicos.
    """
    r: Dict[str, Optional[str]] = {}
    r['date'] = _first_existing(df, ['Fecha','Fecha_Factura','InvoiceDate','OrderDate'], ['fecha','date'])
    r['invoice'] = _first_existing(df, ['Refer','Referencia','Factura','Invoice','InvoiceNo','Folio','Ticket','Operacion','OrderID'], ['refer','factura','invoice','folio','ticket','operacion'])
    r['customer_id'] = _first_existing(df, ['Cod_Cliente','Codigo_Cliente','Customer ID','CustomerID','Id_Cliente','Cliente_ID'], ['cod cliente','codigo cliente','customer id','id cliente'])
    r['customer'] = _first_existing(df, ['Cliente','Razon_Social','Razon Social','Customer Name','Customer'], ['cliente','razon social','customer'], ['cod','codigo',' id'])
    r['product_id'] = _first_existing(df, ['Cod_Articulo','Codigo_Articulo','Cod_Producto','SKU','StockCode','Product ID'], ['cod articulo','codigo articulo','sku','stockcode','product id'])
    r['product'] = _first_existing(df, ['Articulo','Producto','Description','Descripcion','Product Name'], ['articulo','producto','description','descripcion'], ['cod','codigo',' id'])
    r['line'] = _first_existing(df, ['cod_linea','Linea','Línea','Linea_Negocio'], ['linea'])
    r['zone'] = _first_existing(df, ['Zona','Cod_Zona','Region','Región'], ['zona','region'])
    r['seller_id'] = _first_existing(df, ['Cod_Vendedor','Codigo_Vendedor','Seller ID'], ['cod vendedor','seller id'])
    r['seller'] = _first_existing(df, ['Vendedor','Ejecutivo','Asesor','Salesperson','Seller'], ['vendedor','ejecutivo','asesor','salesperson','seller'], ['cod','codigo',' id'])
    r['quantity'] = _first_existing(df, ['Toneladas_Vendidas','Toneladas','Tons','Cantidad','Quantity','Unidades'], ['toneladas vendidas','toneladas','tons','cantidad','quantity','unidades'])
    r['revenue'] = _first_existing(df, ['Importe_Venta','Venta','Ventas','Ventas_Netas','Importe','Revenue','Sales','Amount'], ['importe venta','ventas netas','venta','sales','revenue','importe'])
    r['total_cost'] = _first_existing(df, ['Costo','Costo_Total','Total_Cost','Cost'], ['costo total','total cost'])
    r['cost_without_freight'] = _first_existing(df, ['Costo_Sin_Flete','Costo sin flete'], ['costo sin flete'])
    r['product_cost'] = _first_existing(df, ['Costo_Producto','Costo Producto'], ['costo producto'])
    r['other_cost'] = _first_existing(df, ['Otros_Costos','Otros Costos'], ['otros costos'])
    r['freight_short'] = _first_existing(df, ['Costo_Flete_Corto','Flete_Corto'], ['flete corto'])
    r['freight_long'] = _first_existing(df, ['Costo_Flete_Largo','Flete_Largo'], ['flete largo'])
    r['freight_transfer'] = _first_existing(df, ['Costo_Flete_Traspaso','Flete_Traspaso'], ['flete traspaso'])
    r['warehouse'] = _first_existing(df, ['Almacen','Almacén','Warehouse'], ['almacen','warehouse'])
    r['origin_city'] = _first_existing(df, ['Ciudad_Origen','Ciudad Origen','Origin City'], ['ciudad origen','origin city'])
    r['destination_city'] = _first_existing(df, ['Ciudad_Destino','Ciudad Destino','Destination City'], ['ciudad destino','destination city'])
    r['category'] = _first_existing(df, ['Categoria','Categoría','Category'], ['categoria','category'])
    return r


def _coverage_ratio(a: pd.Series, b: pd.Series) -> Tuple[float, float]:
    mask = a.notna() & b.notna()
    if not mask.any():
        return 0.0, float('inf')
    av = a[mask].astype(float)
    bv = b[mask].astype(float)
    denom = av.abs().clip(lower=1.0)
    rel = ((av - bv).abs() / denom)
    return float(mask.mean()), float(rel.median())


def prepare_business(df: pd.DataFrame, roles: Dict[str, Optional[str]]) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
    work = df.copy()
    notes: List[str] = []
    derived: Dict[str, Any] = {'roles_bi': roles.copy()}

    if roles.get('date'):
        work['_fecha'] = pd.to_datetime(work[roles['date']], errors='coerce')
        work['_mes'] = work['_fecha'].dt.to_period('M').astype(str)
        work['_anio'] = work['_fecha'].dt.year
    if roles.get('quantity'):
        work['_cantidad'] = _num(work[roles['quantity']])
    if roles.get('revenue'):
        work['_ventas'] = _num(work[roles['revenue']])

    freight_cols = [roles.get('freight_short'), roles.get('freight_long'), roles.get('freight_transfer')]
    freight_cols = [c for c in freight_cols if c]
    if freight_cols:
        freight = pd.Series(0.0, index=work.index)
        any_value = pd.Series(False, index=work.index)
        for c in freight_cols:
            n = _num(work[c])
            any_value |= n.notna()
            freight = freight.add(n.fillna(0), fill_value=0)
        work['_flete'] = freight.where(any_value)
        derived['flete'] = ' + '.join(freight_cols)

    # Costo total: prioriza una columna semánticamente explícita. Verifica componentes
    # para no volver a restar fletes si ya están incluidos.
    total_cost_col = roles.get('total_cost')
    cwo = roles.get('cost_without_freight')
    if total_cost_col:
        work['_costo'] = _num(work[total_cost_col])
        derived['costo'] = total_cost_col
        if cwo and freight_cols:
            component = _num(work[cwo]).fillna(0)
            for c in freight_cols:
                component = component.add(_num(work[c]).fillna(0), fill_value=0)
            coverage, median_rel = _coverage_ratio(work['_costo'], component)
            derived['validacion_costo'] = {'formula_componentes': f"{cwo} + {' + '.join(freight_cols)}", 'cobertura': coverage, 'error_relativo_mediano': median_rel}
            if coverage >= 0.70 and median_rel <= 0.01:
                derived['costo_incluye_flete'] = True
                notes.append('El costo total coincide con Costo_Sin_Flete + componentes de flete; el flete no se resta nuevamente para evitar doble conteo.')
    elif cwo:
        cost = _num(work[cwo]).fillna(0)
        for c in freight_cols:
            cost = cost.add(_num(work[c]).fillna(0), fill_value=0)
        work['_costo'] = cost
        derived['costo'] = f"{cwo}" + (f" + {' + '.join(freight_cols)}" if freight_cols else '')
    elif roles.get('product_cost'):
        cost = _num(work[roles['product_cost']]).fillna(0)
        if roles.get('other_cost'):
            cost = cost.add(_num(work[roles['other_cost']]).fillna(0), fill_value=0)
        for c in freight_cols:
            cost = cost.add(_num(work[c]).fillna(0), fill_value=0)
        work['_costo'] = cost
        derived['costo'] = 'componentes disponibles'
    else:
        notes.append('No se detectó una estructura de costo total utilizable; utilidad y margen se omiten.')

    if '_ventas' in work.columns and '_costo' in work.columns:
        work['_utilidad'] = work['_ventas'] - work['_costo']
        derived['utilidad'] = 'ventas - costo total'
    if '_cantidad' in work.columns:
        q = pd.to_numeric(work['_cantidad'], errors='coerce').replace(0, pd.NA)
        if '_ventas' in work.columns:
            work['_precio_ton'] = work['_ventas'] / q
        if '_flete' in work.columns:
            work['_flete_ton'] = work['_flete'] / q
        if '_utilidad' in work.columns:
            work['_util_ton'] = work['_utilidad'] / q
    return work, derived, notes


ALL_SECTIONS = [
    'resumen','evolucion','lineas','productos','clientes','perfil_cliente','vendedores','facturas',
    'clientes_perdidos','clientes_caida','oportunidades','calidad_datos'
]


def compile_report_spec(prompt: str) -> Dict[str, Any]:
    """Compila el prompt a un contrato de reporte seguro y auditable.

    El prompt puede decidir salidas, secciones, top-N y criterio de inactividad,
    pero nunca crear columnas, fórmulas o cifras. Las negaciones explícitas
    ("sin PDF", "no generar Excel", "excluir facturas") tienen prioridad.
    """
    raw = str(prompt or '')
    n = norm(raw)

    def has_any(*terms: str) -> bool:
        return any(norm(t) in n for t in terms)

    def negated(*terms: str) -> bool:
        for term in terms:
            t = norm(term)
            patterns = (
                rf'\bsin\s+{re.escape(t)}\b',
                rf'\bno\s+(?:generar|generes|incluyas|incluir|quiero)?\s*{re.escape(t)}\b',
                rf'\bexcluir\s+{re.escape(t)}\b',
                rf'\bomite\s+{re.escape(t)}\b',
            )
            if any(re.search(pat, n) for pat in patterns):
                return True
        return False

    outputs = {'html': False, 'pdf': False, 'excel': False}
    html_terms = ('html','dashboard','tablero','interactivo','business intelligence','power bi')
    pdf_terms = ('pdf','reporte ejecutivo','direccion','dirección','directivo')
    excel_terms = ('excel','excel analitico','excel analítico','xlsx','libro analitico','libro analítico')
    if has_any(*html_terms) and not negated('html','dashboard','tablero'): outputs['html'] = True
    if has_any(*pdf_terms) and not negated('pdf','reporte ejecutivo'): outputs['pdf'] = True
    if has_any(*excel_terms) and not negated('excel','xlsx','libro analitico'): outputs['excel'] = True

    # "solo X" debe restringir la salida aunque el resto del prompt describa otras secciones.
    if re.search(r'\bsolo\s+(?:un\s+|el\s+)?pdf\b', n): outputs = {'html':False,'pdf':True,'excel':False}
    elif re.search(r'\bsolo\s+(?:un\s+|el\s+)?(?:html|dashboard|tablero)\b', n): outputs = {'html':True,'pdf':False,'excel':False}
    elif re.search(r'\bsolo\s+(?:un\s+|el\s+)?(?:excel|xlsx)\b', n): outputs = {'html':False,'pdf':False,'excel':True}

    broad = has_any('analiza completamente','analisis completo','análisis completo','reporte completo','dashboard comercial','dashboard profesional','genera 3 salidas','genera tres salidas','resultado final','reporte integral')
    if broad and not any(outputs.values()): outputs = {'html': True, 'pdf': True, 'excel': True}
    if not any(outputs.values()):
        # Compatibilidad y mejor experiencia: un análisis empresarial sin formato explícito genera las tres vistas.
        outputs = {'html': True, 'pdf': True, 'excel': True}

    section_terms = {
        'resumen': ('resumen','kpi','indicadores'),
        'evolucion': ('evolucion','evolución','mensual','anual','tendencia','historico','histórico'),
        'lineas': ('linea','línea','lineas','líneas'),
        'productos': ('producto','productos','articulo','artículo','artículos'),
        'clientes': ('cliente','clientes','directorio'),
        'perfil_cliente': ('perfil individual','perfil cliente','perfil de cliente'),
        'vendedores': ('vendedor','vendedores','ejecutivo','asesor'),
        'facturas': ('factura','facturas','operacion','operación','referencia','ticket'),
        'clientes_perdidos': ('cliente perdido','clientes perdidos','inactivo','inactivos','dejaron de comprar'),
        'clientes_caida': ('cliente en caida','clientes en caida','clientes en caída','reduccion','reducción','deterioro'),
        'oportunidades': ('oportunidad','oportunidades','crecimiento','alto volumen','bajo margen','riesgo','riesgos'),
        'calidad_datos': ('calidad','nulos','duplicados','inconsistencias','datos invalidos','datos inválidos'),
    }
    section_neg = {
        'resumen': ('resumen','kpi'), 'evolucion': ('evolucion','tendencia'), 'lineas': ('lineas','líneas'),
        'productos': ('productos','articulos','artículos'), 'clientes': ('clientes',), 'perfil_cliente': ('perfil cliente',),
        'vendedores': ('vendedores',), 'facturas': ('facturas','operaciones'), 'clientes_perdidos': ('clientes perdidos',),
        'clientes_caida': ('clientes en caida','clientes en caída'), 'oportunidades': ('oportunidades','riesgos'),
        'calidad_datos': ('calidad de datos','calidad'),
    }
    if broad or has_any('dashboard','business intelligence','power bi'):
        sections = list(ALL_SECTIONS)
    else:
        sections = [k for k, terms in section_terms.items() if any(norm(t) in n for t in terms)]
        if not sections: sections = list(ALL_SECTIONS)
        elif 'resumen' not in sections: sections.insert(0, 'resumen')
    sections = [s for s in sections if not negated(*section_neg.get(s,(s,)))]
    if not sections: sections = ['resumen']

    inactivity_days = 365
    m = re.search(r'(\d{2,4})\s*dias', n)
    if m: inactivity_days = max(30, min(int(m.group(1)), 3650))
    else:
        m = re.search(r'(\d{1,2})\s*meses', n)
        if m: inactivity_days = max(30, min(int(m.group(1))*30, 3650))

    top_n = 15
    m = re.search(r'\btop\s*(\d{1,3})\b', n)
    if not m: m = re.search(r'\b(?:mejores|principales)\s+(\d{1,3})\b', n)
    if m: top_n = max(3, min(int(m.group(1)), 100))

    style = 'powerbi' if has_any('power bi','dashboard','business intelligence','moderno','ejecutivo') else 'executive'
    return {
        'version': VERSION,
        'outputs': outputs,
        'sections': sections,
        'interactive': bool(outputs['html']),
        'style': style,
        'top_n': top_n,
        'inactivity_days': inactivity_days,
        'comparison_policy': 'periodos_equivalentes',
        'calculation_policy': 'deterministic_python',
        'prompt_applied': True,
    }

def _mode_text(s: pd.Series) -> str:
    s = s.dropna().astype(str).str.strip()
    s = s[s.ne('')]
    if s.empty:
        return ''
    m = s.mode()
    return str(m.iloc[0]) if len(m) else str(s.iloc[0])


def _group_metrics(work: pd.DataFrame, col: Optional[str], name: str) -> pd.DataFrame:
    if not col or col not in work.columns:
        return pd.DataFrame()
    rows = []
    for key, g in work.groupby(col, dropna=False):
        if pd.isna(key) or str(key).strip() == '':
            continue
        ventas = float(pd.to_numeric(g.get('_ventas'), errors='coerce').sum(skipna=True)) if '_ventas' in g else None
        tons = float(pd.to_numeric(g.get('_cantidad'), errors='coerce').sum(skipna=True)) if '_cantidad' in g else None
        costo = float(pd.to_numeric(g.get('_costo'), errors='coerce').sum(skipna=True)) if '_costo' in g else None
        utilidad = float(pd.to_numeric(g.get('_utilidad'), errors='coerce').sum(skipna=True)) if '_utilidad' in g else None
        row = {name: str(key), 'Ventas': ventas, 'Toneladas': tons, 'Costo': costo, 'Utilidad': utilidad}
        row['Margen_%'] = (utilidad/ventas*100.0) if utilidad is not None and ventas else None
        row['Utilidad_Ton'] = (utilidad/tons) if utilidad is not None and tons else None
        inv = None
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty and 'Ventas' in out:
        out = out.sort_values('Ventas', ascending=False, na_position='last').reset_index(drop=True)
    return out


def _annual(work: pd.DataFrame) -> pd.DataFrame:
    if '_fecha' not in work or '_ventas' not in work:
        return pd.DataFrame()
    rows=[]
    dates = pd.to_datetime(work['_fecha'], errors='coerce')
    valid = dates.dropna()
    if valid.empty:
        return pd.DataFrame()
    gmin, gmax = valid.min(), valid.max()
    for y,g in work.loc[dates.notna()].groupby(dates.loc[dates.notna()].dt.year):
        gd = pd.to_datetime(g['_fecha'], errors='coerce').dropna(); months=gd.dt.month.nunique()
        complete = months == 12 and not (int(y)==gmin.year and gd.min().month>1) and not (int(y)==gmax.year and (gd.max().month<12 or (gd.max().month==12 and gd.max().day<20)))
        ventas=float(pd.to_numeric(g['_ventas'],errors='coerce').sum(skipna=True))
        row={'Año':int(y),'Ventas':ventas,'Meses_con_datos':int(months),'Cobertura':'Completo' if complete else f"Parcial ({gd.min().date()} a {gd.max().date()}; {months}/12 meses)",'Desde':gd.min().date().isoformat(),'Hasta':gd.max().date().isoformat()}
        if '_cantidad' in g: row['Toneladas']=float(pd.to_numeric(g['_cantidad'],errors='coerce').sum(skipna=True))
        if '_utilidad' in g: row['Utilidad']=float(pd.to_numeric(g['_utilidad'],errors='coerce').sum(skipna=True))
        rows.append(row)
    out=pd.DataFrame(rows).sort_values('Año').reset_index(drop=True)
    out['Variacion_%']=None; out['Variacion_comparable_%']=None; out['Periodo_comparable']=None
    for i in range(1,len(out)):
        if out.at[i-1,'Cobertura']=='Completo' and out.at[i,'Cobertura']=='Completo' and out.at[i-1,'Ventas']:
            out.at[i,'Variacion_%']=(out.at[i,'Ventas']/out.at[i-1,'Ventas']-1)*100
    last_i=out.index[out['Año'].eq(gmax.year)].tolist()
    prev_i=out.index[out['Año'].eq(gmax.year-1)].tolist()
    if last_i and prev_i and out.at[last_i[0],'Cobertura']!='Completo':
        cut_cur=gmax.normalize()+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1)
        try: cut_prev=cut_cur.replace(year=gmax.year-1)
        except ValueError: cut_prev=cut_cur.replace(year=gmax.year-1,day=28)
        cur=float(pd.to_numeric(work.loc[(dates.dt.year==gmax.year)&(dates<=cut_cur),'_ventas'],errors='coerce').sum(skipna=True))
        prev=float(pd.to_numeric(work.loc[(dates.dt.year==gmax.year-1)&(dates<=cut_prev),'_ventas'],errors='coerce').sum(skipna=True))
        if prev:
            idx=last_i[0]; out.at[idx,'Variacion_comparable_%']=(cur/prev-1)*100; out.at[idx,'Periodo_comparable']=f"01-01 a {cut_cur.strftime('%m-%d')} vs {gmax.year-1}"
    return out


def _monthly(work: pd.DataFrame) -> pd.DataFrame:
    if '_mes' not in work or '_ventas' not in work:
        return pd.DataFrame()
    aggs={'Ventas':('_ventas','sum')}
    if '_cantidad' in work: aggs['Toneladas']=('_cantidad','sum')
    if '_costo' in work: aggs['Costo']=('_costo','sum')
    if '_utilidad' in work: aggs['Utilidad']=('_utilidad','sum')
    out=work.groupby('_mes').agg(**aggs).reset_index().rename(columns={'_mes':'Mes'}).sort_values('Mes')
    out['Variacion_Ventas_%']=pd.to_numeric(out['Ventas'],errors='coerce').pct_change()*100
    if 'Utilidad' in out and 'Ventas' in out: out['Margen_%']=out['Utilidad']/out['Ventas'].replace(0,pd.NA)*100
    return out


def _customers(work: pd.DataFrame, roles: Dict[str,Optional[str]]) -> pd.DataFrame:
    c=roles.get('customer')
    if not c or c not in work: return pd.DataFrame()
    g=work.loc[work[c].notna() & work[c].astype(str).str.strip().ne('')].groupby(c,dropna=False,sort=False)
    out=pd.DataFrame(index=g.size().index)
    if '_ventas' in work: out['Ventas']=g['_ventas'].sum(min_count=1)
    if '_cantidad' in work: out['Toneladas']=g['_cantidad'].sum(min_count=1)
    if '_utilidad' in work: out['Utilidad']=g['_utilidad'].sum(min_count=1)
    if '_costo' in work: out['Costo']=g['_costo'].sum(min_count=1)
    inv=roles.get('invoice'); seller=roles.get('seller'); zone=roles.get('zone'); prod=roles.get('product'); cid=roles.get('customer_id')
    out['Operaciones']=g[inv].nunique(dropna=True) if inv and inv in work else g.size()
    if prod and prod in work: out['Productos']=g[prod].nunique(dropna=True)
    if seller and seller in work: out['Vendedor']=g[seller].first()
    if zone and zone in work: out['Zona']=g[zone].first()
    if cid and cid in work: out['Codigo_Cliente']=g[cid].first()
    if '_fecha' in work:
        out['Primera_Compra']=g['_fecha'].min(); out['Ultima_Compra']=g['_fecha'].max()
    if '_mes' in work: out['Meses_Activos']=g['_mes'].nunique(dropna=True)
    out=out.reset_index().rename(columns={c:'Cliente'})
    if 'Ventas' in out and 'Utilidad' in out: out['Margen_%']=out['Utilidad']/out['Ventas'].replace(0,pd.NA)*100
    if 'Toneladas' in out and 'Utilidad' in out: out['Utilidad_Ton']=out['Utilidad']/out['Toneladas'].replace(0,pd.NA)
    return out.sort_values('Ventas',ascending=False,na_position='last').reset_index(drop=True) if 'Ventas' in out else out


def _invoices(work: pd.DataFrame, roles: Dict[str,Optional[str]]) -> pd.DataFrame:
    inv=roles.get('invoice')
    if not inv or inv not in work: return pd.DataFrame()
    base=work.loc[work[inv].notna() & work[inv].astype(str).str.strip().ne('')]
    g=base.groupby(inv,dropna=False,sort=False)
    out=pd.DataFrame(index=g.size().index)
    if '_fecha' in work: out['Fecha']=g['_fecha'].min()
    for role,name in [('customer','Cliente'),('product','Articulo'),('seller','Vendedor'),('warehouse','Almacen'),('destination_city','Destino')]:
        col=roles.get(role)
        if col and col in work: out[name]=g[col].first()
    for src,name in [('_cantidad','Toneladas'),('_ventas','Ventas'),('_costo','Costo'),('_flete','Flete'),('_utilidad','Utilidad')]:
        if src in work: out[name]=g[src].sum(min_count=1)
    out=out.reset_index().rename(columns={inv:'Referencia'})
    if 'Ventas' in out and 'Toneladas' in out: out['Precio_Ton']=out['Ventas']/out['Toneladas'].replace(0,pd.NA)
    if 'Flete' in out and 'Toneladas' in out: out['Flete_Ton']=out['Flete']/out['Toneladas'].replace(0,pd.NA)
    if 'Utilidad' in out and 'Toneladas' in out: out['Utilidad_Ton']=out['Utilidad']/out['Toneladas'].replace(0,pd.NA)
    return out.sort_values('Fecha',ascending=False,na_position='last').reset_index(drop=True) if 'Fecha' in out else out


def _lost_clients(customers: pd.DataFrame, max_date: Optional[pd.Timestamp], inactivity_days: int) -> pd.DataFrame:
    if customers.empty or max_date is None or 'Ultima_Compra' not in customers: return pd.DataFrame()
    x=customers.copy(); x['Dias_Sin_Comprar']=(pd.Timestamp(max_date).normalize()-pd.to_datetime(x['Ultima_Compra'],errors='coerce').dt.normalize()).dt.days
    x=x.loc[x['Dias_Sin_Comprar']>=inactivity_days].copy()
    return x.rename(columns={'Ventas':'Ventas_Historicas','Toneladas':'Toneladas_Historicas'}).sort_values(['Ventas_Historicas','Dias_Sin_Comprar'],ascending=[False,False]).reset_index(drop=True)


def _declining_clients(work: pd.DataFrame, roles: Dict[str,Optional[str]]) -> pd.DataFrame:
    c=roles.get('customer')
    if not c or '_fecha' not in work or '_ventas' not in work: return pd.DataFrame()
    ds=pd.to_datetime(work['_fecha'],errors='coerce'); maxd=ds.max()
    if pd.isna(maxd): return pd.DataFrame()
    # Dos ventanas equivalentes de 90 días, excluyendo el día posterior al corte.
    cur_start=maxd.normalize()-pd.Timedelta(days=89); prev_end=cur_start-pd.Timedelta(days=1); prev_start=prev_end-pd.Timedelta(days=89)
    cur=work.loc[(ds>=cur_start)&(ds<=maxd)].groupby(c)['_ventas'].sum(min_count=1)
    prev=work.loc[(ds>=prev_start)&(ds<=prev_end)].groupby(c)['_ventas'].sum(min_count=1)
    idx=cur.index.union(prev.index); out=[]
    for k in idx:
        pv=float(prev.get(k,0) or 0); cv=float(cur.get(k,0) or 0)
        if pv<=0: continue
        var=(cv/pv-1)*100
        if var<=-20:
            out.append({'Cliente':str(k),'Ventas_Anterior':pv,'Ventas_Actual':cv,'Variacion_%':var,'Periodo_Anterior':f'{prev_start.date()} a {prev_end.date()}','Periodo_Actual':f'{cur_start.date()} a {maxd.date()}'})
    return pd.DataFrame(out).sort_values('Variacion_%').reset_index(drop=True) if out else pd.DataFrame()


def _opportunities(customers: pd.DataFrame, products: pd.DataFrame, lines: pd.DataFrame, decline: pd.DataFrame) -> pd.DataFrame:
    out=[]
    if not customers.empty:
        qv=customers['Ventas'].quantile(.75) if 'Ventas' in customers else None
        medm=customers['Margen_%'].median() if 'Margen_%' in customers else None
        if qv is not None and medm is not None:
            for _,r in customers.loc[(customers['Ventas']>=qv)&(customers['Margen_%'].notna())&(customers['Margen_%']<medm)].head(10).iterrows():
                out.append({'Tipo':'Cliente','Entidad':r['Cliente'],'Indicador':'Alto volumen / margen bajo','Detalle':f"Ventas {r['Ventas']:,.0f}; margen {r['Margen_%']:.2f}%"})
        for _,r in customers.loc[customers['Utilidad_Ton'].notna()].sort_values('Utilidad_Ton',ascending=False).head(5).iterrows():
            out.append({'Tipo':'Cliente','Entidad':r['Cliente'],'Indicador':'Alta utilidad por tonelada','Detalle':f"{r['Utilidad_Ton']:,.2f} por ton"})
    if not products.empty and 'Utilidad_Ton' in products:
        for _,r in products.loc[products['Utilidad_Ton'].notna()].sort_values('Utilidad_Ton',ascending=False).head(5).iterrows():
            out.append({'Tipo':'Producto','Entidad':r.iloc[0],'Indicador':'Alta utilidad por tonelada','Detalle':f"{r['Utilidad_Ton']:,.2f} por ton"})
    if not decline.empty:
        for _,r in decline.head(10).iterrows(): out.append({'Tipo':'Riesgo','Entidad':r['Cliente'],'Indicador':'Cliente en caída','Detalle':f"Variación {r['Variacion_%']:.1f}% en periodos equivalentes"})
    return pd.DataFrame(out)


def _quality(df: pd.DataFrame, roles: Dict[str,Optional[str]], derived: Dict[str,Any]) -> pd.DataFrame:
    total=max(1,len(df)); cells=max(1,len(df)*max(1,len(df.columns)))
    q=[
        ('Filas analizadas',int(len(df)),'Archivo completo procesado'),
        ('Columnas',int(len(df.columns)),'Estructura detectada'),
        ('Filas idénticas',int(df.duplicated().sum()),'Revisar antes de eliminar; pueden ser operaciones legítimas'),
        ('Celdas nulas %',round(float(df.isna().sum().sum())/cells*100,2),'Porcentaje global de datos faltantes'),
    ]
    for role,label in [('date','Fecha'),('invoice','Operación'),('customer','Cliente'),('product','Producto'),('quantity','Volumen'),('revenue','Ventas'),('total_cost','Costo'),('seller','Vendedor')]:
        q.append((f'Mapeo {label}',roles.get(role) or 'N/D','Columna elegida por el mapeador semántico'))
    if derived.get('validacion_costo'):
        v=derived['validacion_costo']; q.append(('Validación costo por componentes',f"cobertura {v['cobertura']*100:.1f}% / error mediano {v['error_relativo_mediano']*100:.4f}%",'Verifica que el costo total ya incluya componentes/fletes'))
    return pd.DataFrame(q,columns=['Indicador','Valor','Interpretación'])


def build_bi_model(df: pd.DataFrame, work: pd.DataFrame, roles: Dict[str,Optional[str]], derived: Dict[str,Any], prompt: str, spec: Dict[str,Any]) -> Dict[str,Any]:
    monthly=_monthly(work); annual=_annual(work); lines=_group_metrics(work,roles.get('line'),'Linea'); products=_group_metrics(work,roles.get('product'),'Producto'); sellers=_group_metrics(work,roles.get('seller'),'Vendedor'); customers=_customers(work,roles); invoices=_invoices(work,roles)
    max_date=pd.to_datetime(work['_fecha'],errors='coerce').max() if '_fecha' in work else None
    lost=_lost_clients(customers,max_date,spec.get('inactivity_days',365)); decline=_declining_clients(work,roles); opp=_opportunities(customers,products,lines,decline); quality=_quality(df,roles,derived)
    sales=float(pd.to_numeric(work['_ventas'],errors='coerce').sum(skipna=True)) if '_ventas' in work else None; tons=float(pd.to_numeric(work['_cantidad'],errors='coerce').sum(skipna=True)) if '_cantidad' in work else None; cost=float(pd.to_numeric(work['_costo'],errors='coerce').sum(skipna=True)) if '_costo' in work else None; profit=float(pd.to_numeric(work['_utilidad'],errors='coerce').sum(skipna=True)) if '_utilidad' in work else None
    operations=int(work[roles['invoice']].nunique(dropna=True)) if roles.get('invoice') else None; nclients=int(work[roles['customer']].nunique(dropna=True)) if roles.get('customer') else None
    kpis={'Ventas':sales,'Toneladas':tons,'Costo':cost,'Utilidad':profit,'Margen_%':(profit/sales*100 if profit is not None and sales else None),'Utilidad_Ton':(profit/tons if profit is not None and tons else None),'Operaciones':operations,'Clientes':nclients,'Ticket_Promedio':(sales/operations if sales is not None and operations else None)}
    return {'kpis':kpis,'monthly':monthly,'annual':annual,'lines':lines,'products':products,'sellers':sellers,'customers':customers,'invoices':invoices,'lost':lost,'decline':decline,'opportunities':opp,'quality':quality,'roles':roles,'derived':derived,'spec':spec,'prompt':prompt,'max_date':max_date}


def _records(df: pd.DataFrame, max_rows: Optional[int]=None) -> List[Dict[str,Any]]:
    if df is None or df.empty: return []
    x=df if max_rows is None else df.head(max_rows)
    out=[]
    for _,r in x.iterrows():
        d={}
        for k,v in r.items():
            if isinstance(v,(pd.Timestamp,datetime)): d[str(k)]=v.isoformat()
            elif v is None or (not isinstance(v,str) and pd.isna(v)): d[str(k)]=None
            elif hasattr(v,'item'):
                try: d[str(k)]=v.item()
                except Exception: d[str(k)]=v
            else: d[str(k)]=v
        out.append(d)
    return out


def build_dashboard_payload(work: pd.DataFrame, model: Dict[str,Any], filename: str) -> Dict[str,Any]:
    roles=model['roles']; cols=[]
    mapping={'d':'_fecha','m':'_mes','inv':roles.get('invoice'),'c':roles.get('customer'),'cid':roles.get('customer_id'),'p':roles.get('product'),'pid':roles.get('product_id'),'s':roles.get('seller'),'l':roles.get('line'),'z':roles.get('zone'),'w':roles.get('warehouse'),'dst':roles.get('destination_city'),'t':'_cantidad','v':'_ventas','co':'_costo','fr':'_flete','u':'_utilidad','pt':'_precio_ton','ft':'_flete_ton','ut':'_util_ton'}
    # Para HTML grandes, conserva las dimensiones/métricas necesarias. Hasta 120k filas
    # usa detalle; arriba de eso agrega por mes + dimensiones para mantener el dashboard ágil.
    src=work
    detail_mode=True
    if len(src)>120000:
        detail_mode=False
        group_keys=[c for c in [roles.get('customer'),roles.get('product'),roles.get('seller'),roles.get('line'),roles.get('zone'),'_mes'] if c]
        agg={}
        for c in ['_cantidad','_ventas','_costo','_flete','_utilidad']:
            if c in src: agg[c]='sum'
        if group_keys and agg:
            src=src.groupby(group_keys,dropna=False).agg(agg).reset_index()
            src['_fecha']=pd.to_datetime(src['_mes'].astype(str)+'-01',errors='coerce')
            src['_precio_ton']=src['_ventas']/src['_cantidad'].replace(0,pd.NA) if '_ventas' in src and '_cantidad' in src else None
            src['_flete_ton']=src['_flete']/src['_cantidad'].replace(0,pd.NA) if '_flete' in src and '_cantidad' in src else None
            src['_util_ton']=src['_utilidad']/src['_cantidad'].replace(0,pd.NA) if '_utilidad' in src and '_cantidad' in src else None
    tx=[]
    for _,row in src.iterrows():
        rec={}
        for key,col in mapping.items():
            if not col or col not in src.columns: rec[key]=None; continue
            v=row[col]
            if key=='d':
                try: rec[key]=pd.Timestamp(v).date().isoformat() if pd.notna(v) else ''
                except Exception: rec[key]=''
            elif key=='m': rec[key]=str(v) if pd.notna(v) else ''
            elif key in {'t','v','co','fr','u','pt','ft','ut'}: rec[key]=_safe_float(v)
            else: rec[key]='' if pd.isna(v) else str(v)
        tx.append(rec)
    period_from=''; period_to=''
    if '_fecha' in work and pd.to_datetime(work['_fecha'],errors='coerce').notna().any():
        ds=pd.to_datetime(work['_fecha'],errors='coerce'); period_from=ds.min().date().isoformat(); period_to=ds.max().date().isoformat()
    return {'tx':tx,'meta':{'file':filename,'rows':int(len(work)),'from':period_from,'to':period_to,'roles':roles,'spec':model['spec'],'prompt':model['prompt'],'quality':_records(model['quality']), 'lost':_records(model['lost'],2000),'decline':_records(model['decline'],1000),'opportunities':_records(model['opportunities'],1000),'detail_mode':detail_mode}}


def _json_for_inline_script(value: Any, *, compact: bool = True) -> str:
    # JSON seguro para un <script> inline. Además de escapar caracteres que pueden
    # cerrar el elemento HTML, conserva literalmente backslashes como \n, \t, etc.
    kwargs={'ensure_ascii':False}
    if compact:
        kwargs['separators']=(',',':')
    text=json.dumps(value,**kwargs)
    return (text
            .replace('&','\\u0026')
            .replace('<','\\u003c')
            .replace('>','\\u003e')
            .replace('\u2028','\\u2028')
            .replace('\u2029','\\u2029'))


def generate_html(path: Path, template_path: Path, payload: Dict[str,Any], requested: List[str]) -> None:
    template=template_path.read_text(encoding='utf-8')
    data_json=_json_for_inline_script(payload,compact=True)
    requested_json=_json_for_inline_script(requested,compact=False)
    replacement=f'const DATA={data_json}; const REQUESTED={requested_json};'
    # IMPORTANTE: usar función de reemplazo. Si se pasa replacement como string,
    # re.sub interpreta backslashes del JSON (\n, \t, etc.) y puede convertirlos
    # en caracteres literales que rompen JavaScript en datasets reales.
    template,n=re.subn(r'const DATA=.*?; const REQUESTED=.*?;', lambda _m: replacement, template, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError('No se encontro el bloque DATA/REQUESTED en la plantilla del dashboard.')
    path.write_text(template,encoding='utf-8')


def _fmt_money(v: Any) -> str:
    x=_safe_float(v)
    if x is None: return 'N/D'
    a=abs(x); sign='-' if x<0 else ''
    if a>=1e9: return f'{sign}${a/1e9:.2f} B'
    if a>=1e6: return f'{sign}${a/1e6:.2f} M'
    if a>=1e3: return f'{sign}${a/1e3:.1f} K'
    return f'${x:,.2f}'


def _fmt_num(v: Any, d: int=1) -> str:
    x=_safe_float(v); return 'N/D' if x is None else f'{x:,.{d}f}'


def _chart(kind: str, df: pd.DataFrame, x: str, y: str, title: str, color: str=BLUE, max_rows: int=15) -> Optional[BytesIO]:
    if df is None or df.empty or x not in df or y not in df: return None
    show=df[[x,y]].dropna().head(max_rows); vals=pd.to_numeric(show[y],errors='coerce')
    if show.empty or not vals.notna().any(): return None
    fig,ax=plt.subplots(figsize=(8.2,3.0))
    if kind=='line':
        ax.plot(show[x].astype(str),vals,marker='o',linewidth=2.2,color=color); ax.tick_params(axis='x',labelrotation=45,labelsize=7)
    else:
        ax.barh(show[x].astype(str).tolist()[::-1],vals.tolist()[::-1],color=color); ax.tick_params(axis='y',labelsize=7)
    ax.set_title(title,loc='left',fontsize=11,fontweight='bold',color=NAVY); ax.spines[['top','right','left']].set_visible(False); ax.grid(axis='y' if kind=='line' else 'x',alpha=.18); ax.tick_params(colors='#525252',labelsize=7); fig.tight_layout(); b=BytesIO(); fig.savefig(b,format='png',dpi=150,bbox_inches='tight'); plt.close(fig); b.seek(0); return b


def _pdf_table(df: pd.DataFrame, styles, cols: List[str], max_rows: int=12) -> Table:
    show=df[[c for c in cols if c in df.columns]].head(max_rows).copy()
    body=[[Paragraph(f'<b>{str(c).replace("_"," ")}</b>',styles['TH']) for c in show.columns]]
    for _,r in show.iterrows():
        row=[]
        for c,v in r.items():
            if isinstance(v,(pd.Timestamp,datetime)): txt=str(v)[:10]
            elif c in {'Ventas','Costo','Utilidad','Ventas_Historicas','Ventas_Anterior','Ventas_Actual','Ticket_Promedio'}: txt=_fmt_money(v)
            elif 'Margen' in c or 'Variacion' in c: txt='N/D' if _safe_float(v) is None else f'{float(v):,.1f}%'
            elif c in {'Toneladas','Toneladas_Historicas','Utilidad_Ton','Precio_Ton','Flete_Ton'}: txt=_fmt_num(v,1)
            else: txt='' if v is None or (not isinstance(v,str) and pd.isna(v)) else str(v)
            row.append(Paragraph(txt,styles['TC']))
        body.append(row)
    widths=[25.2*cm/max(1,len(show.columns))]*max(1,len(show.columns))
    t=Table(body,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.HexColor(BORDER)),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#FAFAFA')]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3.5),('BOTTOMPADDING',(0,0),(-1,-1),3.5)]))
    return t


def _has_section(model: Dict[str,Any], *names: str) -> bool:
    requested=set(model.get('spec',{}).get('sections') or [])
    return any(n in requested for n in names)


def generate_pdf(path: Path, filename: str, model: Dict[str,Any], notes: List[str]) -> None:
    k=model['kpis']; spec=model['spec']; top_n=int(spec.get('top_n') or 15); pdf_rows=min(top_n,10); doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),rightMargin=1.0*cm,leftMargin=1.0*cm,topMargin=1.35*cm,bottomMargin=1.15*cm,title='Reporte Ejecutivo BI',author='IA Empresarial Local')
    st=getSampleStyleSheet(); st.add(ParagraphStyle(name='TitleBI',parent=st['Title'],fontName='Helvetica-Bold',fontSize=20,leading=23,textColor=colors.HexColor(NAVY),alignment=TA_LEFT,spaceAfter=4)); st.add(ParagraphStyle(name='SecBI',parent=st['Heading2'],fontName='Helvetica-Bold',fontSize=12.5,leading=15,textColor=colors.HexColor(NAVY),spaceBefore=4,spaceAfter=6)); st.add(ParagraphStyle(name='SmallBI',parent=st['BodyText'],fontSize=7.5,leading=10,textColor=colors.HexColor(MID))); st.add(ParagraphStyle(name='TH',parent=st['BodyText'],fontSize=6.6,leading=7.5,textColor=colors.white)); st.add(ParagraphStyle(name='TC',parent=st['BodyText'],fontSize=6.5,leading=7.8,textColor=colors.HexColor('#343A3F'))); st.add(ParagraphStyle(name='CardBI',parent=st['BodyText'],fontSize=8,leading=10,alignment=TA_CENTER,textColor=colors.HexColor(NAVY)))
    def footer(can,doc_):
        can.saveState(); w,h=landscape(A4); can.setFillColor(colors.HexColor(NAVY)); can.rect(0,h-.5*cm,w,.5*cm,stroke=0,fill=1); can.setFillColor(colors.HexColor(MID)); can.setFont('Helvetica',7); can.drawString(1*cm,.5*cm,'IA Empresarial Local | BI determinístico'); can.drawRightString(w-1*cm,.5*cm,f'Página {doc_.page}'); can.restoreState()
    story=[Paragraph('Reporte Ejecutivo · Business Intelligence',st['TitleBI'])]
    period=''
    if model.get('max_date') is not None and not model['monthly'].empty: period=f" | Periodo: {model['monthly']['Mes'].min()} a {model['monthly']['Mes'].max()}"
    story += [Paragraph(f"Archivo: <b>{filename}</b>{period} | Secciones solicitadas: <b>{', '.join(spec['sections'])}</b>",st['SmallBI']),Spacer(1,.12*cm)]
    cards=[('VENTAS',_fmt_money(k.get('Ventas')),'Ingresos acumulados'),('TONELADAS',_fmt_num(k.get('Toneladas'),0),'Volumen vendido'),('UTILIDAD',_fmt_money(k.get('Utilidad')),f"Margen {_fmt_num(k.get('Margen_%'),2)}%"),('UTILIDAD / TON',('N/D' if k.get('Utilidad_Ton') is None else '$'+_fmt_num(k.get('Utilidad_Ton'),2)),f"{k.get('Operaciones') or 0:,} operaciones")]
    cells=[Paragraph(f"<font size='7' color='{MID}'><b>{a}</b></font><br/><font size='16' color='{NAVY}'><b>{b}</b></font><br/><font size='6.5' color='{MID}'>{c}</font>",st['CardBI']) for a,b,c in cards]
    ct=Table([cells],colWidths=[6.2*cm]*4,rowHeights=[2.05*cm]); ct.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.4,colors.HexColor(BORDER)),('BACKGROUND',(0,0),(0,0),colors.HexColor(PALE_BLUE)),('BACKGROUND',(1,0),(1,0),colors.HexColor(PALE_ORANGE)),('BACKGROUND',(2,0),(2,0),colors.HexColor(PALE_GREEN)),('BACKGROUND',(3,0),(3,0),colors.HexColor('#F3E8FF')),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story += [ct]

    if _has_section(model,'evolucion','resumen'):
        story += [Spacer(1,.2*cm),Paragraph('Evolución y comparativo',st['SecBI'])]
        imgs=[]
        if not model['monthly'].empty:
            b=_chart('line',model['monthly'],'Mes','Ventas','Evolución mensual de ventas',BLUE,72)
            if b: imgs.append(Image(b,width=12.5*cm,height=5.2*cm))
        if not model['annual'].empty:
            b=_chart('bar',model['annual'].sort_values('Ventas',ascending=False),'Año','Ventas','Ventas por año',ORANGE,10)
            if b: imgs.append(Image(b,width=12.5*cm,height=5.2*cm))
        if imgs:
            while len(imgs)<2: imgs.append(Spacer(1,1))
            story.append(Table([imgs[:2]],colWidths=[12.7*cm,12.7*cm]))
        if not model['annual'].empty: story += [Spacer(1,.15*cm),_pdf_table(model['annual'],st,['Año','Ventas','Toneladas','Utilidad','Cobertura','Variacion_%','Variacion_comparable_%'],10)]

    if _has_section(model,'lineas','vendedores'):
        story += [PageBreak(),Paragraph('Rentabilidad por línea y vendedor',st['TitleBI'])]
        pair=[]
        if _has_section(model,'lineas') and not model['lines'].empty:
            b=_chart('bar',model['lines'],'Linea','Ventas','Ventas por línea',BLUE,top_n); pair.append(Image(b,width=12.4*cm,height=5.3*cm) if b else Spacer(1,1))
        if _has_section(model,'vendedores') and not model['sellers'].empty:
            b=_chart('bar',model['sellers'],'Vendedor','Ventas','Ventas por vendedor',PURPLE,top_n); pair.append(Image(b,width=12.4*cm,height=5.3*cm) if b else Spacer(1,1))
        if pair:
            while len(pair)<2: pair.append(Spacer(1,1))
            story.append(Table([pair[:2]],colWidths=[12.6*cm,12.6*cm]))
        if _has_section(model,'lineas') and not model['lines'].empty: story += [Paragraph('Líneas',st['SecBI']),_pdf_table(model['lines'],st,['Linea','Toneladas','Ventas','Costo','Utilidad','Margen_%','Utilidad_Ton'],pdf_rows)]
        if _has_section(model,'vendedores') and not model['sellers'].empty: story += [Spacer(1,.15*cm),Paragraph('Vendedores',st['SecBI']),_pdf_table(model['sellers'],st,['Vendedor','Toneladas','Ventas','Utilidad','Margen_%','Utilidad_Ton'],pdf_rows)]

    if _has_section(model,'productos') and not model['products'].empty:
        story += [PageBreak(),Paragraph('Productos',st['TitleBI'])]
        b=_chart('bar',model['products'],'Producto','Ventas','Top productos por ventas',BLUE,top_n)
        if b: story.append(Image(b,width=18.5*cm,height=6.2*cm))
        story += [Paragraph(f'Top {min(top_n, len(model["products"]))} productos · vista ejecutiva',st['SecBI']),_pdf_table(model['products'],st,['Producto','Toneladas','Ventas','Utilidad','Margen_%','Utilidad_Ton'],pdf_rows)]
        if top_n>pdf_rows: story.append(Paragraph(f'El dashboard HTML y el Excel analítico conservan el ranking solicitado Top {top_n}; el PDF muestra una selección ejecutiva Top {pdf_rows} para mantener legibilidad.',st['SmallBI']))

    if _has_section(model,'clientes','perfil_cliente') and not model['customers'].empty:
        story += [PageBreak(),Paragraph('Clientes',st['TitleBI'])]
        b=_chart('bar',model['customers'],'Cliente','Ventas','Top clientes por ventas',PURPLE,top_n)
        if b: story.append(Image(b,width=18.5*cm,height=6.2*cm))
        story += [Paragraph(f'Top {min(top_n, len(model["customers"]))} clientes · vista ejecutiva',st['SecBI']),_pdf_table(model['customers'],st,['Cliente','Toneladas','Ventas','Utilidad','Margen_%','Utilidad_Ton','Operaciones'],pdf_rows)]
        if top_n>pdf_rows: story.append(Paragraph(f'El dashboard HTML y el Excel analítico conservan el ranking solicitado Top {top_n}; el PDF muestra una selección ejecutiva Top {pdf_rows} para mantener legibilidad.',st['SmallBI']))

    if _has_section(model,'clientes_perdidos','clientes_caida','oportunidades'):
        story += [PageBreak(),Paragraph('Riesgos y oportunidades',st['TitleBI'])]
        if _has_section(model,'clientes_perdidos') and not model['lost'].empty: story += [Paragraph(f"Clientes perdidos / inactivos · criterio {spec['inactivity_days']} días",st['SecBI']),_pdf_table(model['lost'],st,['Cliente','Ultima_Compra','Dias_Sin_Comprar','Ventas_Historicas','Toneladas_Historicas','Vendedor','Zona'],12),Spacer(1,.15*cm)]
        if _has_section(model,'clientes_caida') and not model['decline'].empty: story += [Paragraph('Clientes en caída · periodos equivalentes',st['SecBI']),_pdf_table(model['decline'],st,['Cliente','Ventas_Anterior','Ventas_Actual','Variacion_%','Periodo_Anterior','Periodo_Actual'],12),Spacer(1,.15*cm)]
        if _has_section(model,'oportunidades') and not model['opportunities'].empty: story += [Paragraph('Oportunidades detectadas',st['SecBI']),_pdf_table(model['opportunities'],st,['Tipo','Entidad','Indicador','Detalle'],10)]

    if _has_section(model,'facturas') and not model['invoices'].empty:
        story += [PageBreak(),Paragraph('Facturas / operaciones',st['TitleBI']),_pdf_table(model['invoices'],st,['Referencia','Fecha','Cliente','Articulo','Vendedor','Toneladas','Precio_Ton','Flete_Ton','Utilidad_Ton','Ventas','Utilidad'],18)]

    if _has_section(model,'calidad_datos'):
        story += [PageBreak(),Paragraph('Calidad, mapeo y metodología',st['TitleBI']),_pdf_table(model['quality'],st,['Indicador','Valor','Interpretación'],25),Spacer(1,.2*cm)]
        story += [Paragraph('Metodología',st['SecBI']),Paragraph('Los cálculos se ejecutan localmente sobre el archivo completo. La salida HTML/PDF/Excel consume un mismo modelo BI canónico para evitar discrepancias. Los costos se validan por semántica y componentes; si una columna de costo total ya incluye fletes, éstos no se restan nuevamente. El prompt controla las salidas y secciones permitidas, pero nunca puede inventar columnas o sustituir los cálculos determinísticos.',st['SmallBI'])]
        if notes:
            story += [Spacer(1,.12*cm),Paragraph('Notas de validación',st['SecBI'])]
            for n in list(dict.fromkeys(str(x) for x in notes if str(x).strip()))[:10]: story.append(Paragraph('• '+n,st['SmallBI']))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def _excel_write_table(writer, name: str, df: pd.DataFrame, title: str, color: str=BLUE) -> None:
    wb=writer.book; ws=wb.add_worksheet(name); writer.sheets[name]=ws; ws.hide_gridlines(2); ws.set_zoom(90); ws.write(0,0,title,wb.add_format({'bold':True,'font_size':16,'font_color':NAVY})); show=df.copy(); sr=2
    if show.empty:
        ws.write(sr,0,'Sin datos para esta sección.'); return
    # fechas a naive datetime
    for c in show.columns:
        if pd.api.types.is_datetime64_any_dtype(show[c]): show[c]=pd.to_datetime(show[c],errors='coerce').dt.tz_localize(None)
    show.to_excel(writer,sheet_name=name,startrow=sr,index=False)
    hf=wb.add_format({'bold':True,'font_color':WHITE,'bg_color':NAVY}); nf=wb.add_format({'num_format':'#,##0.00;[Red]-#,##0.00'}); pf=wb.add_format({'num_format':'0.00"%";[Red]-0.00"%"'}); dfmt=wb.add_format({'num_format':'yyyy-mm-dd'}); text=wb.add_format({'valign':'top'})
    for j,c in enumerate(show.columns):
        ws.write(sr,j,str(c),hf); nc=norm(c)
        if pd.api.types.is_datetime64_any_dtype(show[c]): width,fmt=14,dfmt
        elif pd.api.types.is_numeric_dtype(show[c]): width,fmt=(14,pf) if ('margen' in nc or 'variacion' in nc or 'participacion' in nc) else (18,nf)
        else:
            sample=max([len(str(c))]+[len(str(x)) for x in show[c].dropna().astype(str).head(100)]); width,fmt=min(38,max(12,sample+2)),text
        ws.set_column(j,j,width,fmt)
    er=sr+len(show); tbl=re.sub(r'[^A-Za-z0-9]','',name)[:20]+'Tbl'; ws.add_table(sr,0,er,len(show.columns)-1,{'name':tbl,'style':'Table Style Medium 2','columns':[{'header':str(c)} for c in show.columns]}); ws.freeze_panes(sr+1,0)


def generate_excel(path: Path, filename: str, model: Dict[str,Any]) -> None:
    k=model['kpis']; requested=set(model.get('spec',{}).get('sections') or [])
    with pd.ExcelWriter(path,engine='xlsxwriter') as writer:
        wb=writer.book; ws=wb.add_worksheet('Dashboard'); writer.sheets['Dashboard']=ws; ws.hide_gridlines(2); ws.set_zoom(90); ws.set_column('A:L',13)
        title=wb.add_format({'bold':True,'font_size':21,'font_color':WHITE,'bg_color':NAVY,'align':'left','valign':'vcenter'}); sub=wb.add_format({'font_size':9,'font_color':MID}); lab=wb.add_format({'bold':True,'font_size':8,'font_color':WHITE,'bg_color':BLUE,'align':'center'}); val=wb.add_format({'bold':True,'font_size':17,'font_color':NAVY,'border':1,'border_color':BORDER,'align':'center'}); sec=wb.add_format({'bold':True,'font_size':12,'font_color':NAVY,'bottom':2,'bottom_color':BLUE})
        ws.merge_range('A1:L2','Dashboard Ejecutivo · IA Empresarial',title); ws.merge_range('A3:L3',f'Archivo: {filename} | Prompt aplicado | Versión {VERSION}',sub)
        cards=[('VENTAS',_fmt_money(k.get('Ventas'))),('TONELADAS',_fmt_num(k.get('Toneladas'),0)),('UTILIDAD',_fmt_money(k.get('Utilidad'))),('MARGEN',('N/D' if k.get('Margen_%') is None else _fmt_num(k.get('Margen_%'),2)+'%')),('UTIL/T',('N/D' if k.get('Utilidad_Ton') is None else '$'+_fmt_num(k.get('Utilidad_Ton'),2))),('OPERACIONES',str(k.get('Operaciones') or 'N/D')),('CLIENTES',str(k.get('Clientes') or 'N/D')),('TICKET',_fmt_money(k.get('Ticket_Promedio')))]
        positions=[('A5:C5','A6:C7'),('D5:F5','D6:F7'),('G5:I5','G6:I7'),('J5:L5','J6:L7'),('A9:C9','A10:C11'),('D9:F9','D10:F11'),('G9:I9','G10:I11'),('J9:L9','J10:L11')]
        for (lbl,v),(rl,rv) in zip(cards,positions): ws.merge_range(rl,lbl,lab); ws.merge_range(rv,v,val)
        if 'evolucion' in requested or 'resumen' in requested:
            ws.merge_range('A13:L13','Evolución mensual',sec); model['monthly'].to_excel(writer,sheet_name='Dashboard',startrow=14,startcol=0,index=False)
            if not model['monthly'].empty and 'Mes' in model['monthly'] and 'Ventas' in model['monthly']:
                rows=min(len(model['monthly']),72); ch=wb.add_chart({'type':'line'}); ch.add_series({'name':'Ventas','categories':['Dashboard',15,0,14+rows,0],'values':['Dashboard',15,1,14+rows,1],'line':{'color':BLUE,'width':2.2},'marker':{'type':'circle','size':3}}); ch.set_title({'name':'Ventas mensuales'}); ch.set_legend({'none':True}); ws.insert_chart('G14',ch,{'x_scale':1.0,'y_scale':1.0})
            _excel_write_table(writer,'Mensual',model['monthly'],'Evolución mensual'); _excel_write_table(writer,'Anual',model['annual'],'Comparativo anual')
        mapping=[('lineas','Lineas',model['lines'],'Análisis por línea'),('productos','Productos',model['products'],'Análisis por producto'),('clientes','Clientes',model['customers'],'Directorio de clientes'),('vendedores','Vendedores',model['sellers'],'Análisis por vendedor'),('facturas','Facturas',model['invoices'],'Facturas / operaciones'),('clientes_perdidos','Clientes_Perdidos',model['lost'],'Clientes perdidos / inactivos'),('clientes_caida','Clientes_Caida',model['decline'],'Clientes en caída'),('oportunidades','Oportunidades',model['opportunities'],'Oportunidades y riesgos'),('calidad_datos','Calidad_Datos',model['quality'],'Calidad de datos y mapeo')]
        for key,name,df,title2 in mapping:
            if key in requested: _excel_write_table(writer,name,df,title2)
        trace=pd.DataFrame([{'Campo':'Prompt','Valor':model['prompt']},{'Campo':'Especificación','Valor':json.dumps(model['spec'],ensure_ascii=False)},{'Campo':'Roles BI','Valor':json.dumps(model['roles'],ensure_ascii=False)},{'Campo':'Cálculos derivados','Valor':json.dumps(model['derived'],ensure_ascii=False,default=str)}])
        _excel_write_table(writer,'Trazabilidad',trace,'Trazabilidad de la generación'); writer.sheets['Trazabilidad'].hide()


def executive_narrative(model: Dict[str,Any], outputs: Dict[str,Optional[str]]) -> str:
    k=model['kpis']; parts=[f"Análisis determinístico completado. Ventas {_fmt_money(k.get('Ventas'))}; toneladas {_fmt_num(k.get('Toneladas'),1)}; operaciones {k.get('Operaciones') if k.get('Operaciones') is not None else 'N/D'}; clientes {k.get('Clientes') if k.get('Clientes') is not None else 'N/D'}." ]
    if k.get('Utilidad') is not None: parts.append(f"Utilidad {_fmt_money(k.get('Utilidad'))}, margen {_fmt_num(k.get('Margen_%'),2)}% y utilidad por tonelada ${_fmt_num(k.get('Utilidad_Ton'),2)}.")
    if not model['annual'].empty:
        last=model['annual'].iloc[-1]
        if _safe_float(last.get('Variacion_comparable_%')) is not None: parts.append(f"El último periodo parcial comparado contra el mismo corte del año anterior varía {float(last['Variacion_comparable_%']):+.2f}%.")
    generated=[f"{k.upper()}: {v}" for k,v in outputs.items() if v]
    if generated: parts.append('Archivos generados: '+', '.join(generated)+'.')
    parts.append('El prompt se compiló a una especificación de reporte segura; los cálculos se hicieron con Python sobre el archivo y la IA no sustituyó cifras ni inventó columnas.')
    return '\n'.join(parts)
