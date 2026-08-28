import tempfile
from pathlib import Path
import sys
import json
import re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bi_productivo as bi


def sample_df():
    return pd.DataFrame([
        {'cod_linea':'GRANO','Cod_Cliente':'C1','Cliente':'Cliente Uno','Cod_Articulo':'P1','Articulo':'Sorgo','Refer':'F1','Fecha':'2026-01-10','Zona':'NORTE','Toneladas_Vendidas':10,'Importe_Venta':1000,'Costo':800,'Costo_Sin_Flete':700,'Costo_Producto':650,'Otros_Costos':50,'Costo_Flete_Corto':50,'Costo_Flete_Largo':20,'Costo_Flete_Traspaso':30,'Almacen':'A','Ciudad_Destino':'D','Vendedor':'Ana'},
        {'cod_linea':'GRANO','Cod_Cliente':'C1','Cliente':'Cliente Uno','Cod_Articulo':'P2','Articulo':'Maiz','Refer':'F2','Fecha':'2026-02-10','Zona':'NORTE','Toneladas_Vendidas':20,'Importe_Venta':2200,'Costo':1800,'Costo_Sin_Flete':1600,'Costo_Producto':1500,'Otros_Costos':100,'Costo_Flete_Corto':100,'Costo_Flete_Largo':50,'Costo_Flete_Traspaso':50,'Almacen':'A','Ciudad_Destino':'D','Vendedor':'Ana'},
        {'cod_linea':'PASTA','Cod_Cliente':'C2','Cliente':'Cliente Dos','Cod_Articulo':'P3','Articulo':'Soya','Refer':'F3','Fecha':'2025-01-05','Zona':'SUR','Toneladas_Vendidas':5,'Importe_Venta':700,'Costo':600,'Costo_Sin_Flete':550,'Costo_Producto':500,'Otros_Costos':50,'Costo_Flete_Corto':50,'Costo_Flete_Largo':0,'Costo_Flete_Traspaso':0,'Almacen':'B','Ciudad_Destino':'E','Vendedor':'Beto'},
    ])


def test_semantic_map_and_cost():
    df=sample_df(); roles=bi.semantic_map(df)
    assert roles['customer']=='Cliente'
    assert roles['customer_id']=='Cod_Cliente'
    assert roles['product']=='Articulo'
    assert roles['invoice']=='Refer'
    assert roles['total_cost']=='Costo'
    work,derived,notes=bi.prepare_business(df,roles)
    assert derived.get('costo_incluye_flete') is True
    assert round(work['_utilidad'].sum(),2)==700.00


def test_prompt_compiler_all_outputs():
    s=bi.compile_report_spec('Genera dashboard HTML, reporte PDF y Excel analítico con clientes perdidos, vendedores y calidad. Estilo Power BI.')
    assert s['outputs']=={'html':True,'pdf':True,'excel':True}
    assert 'clientes_perdidos' in s['sections'] and 'vendedores' in s['sections'] and 'calidad_datos' in s['sections']


def test_prompt_compiler_pdf_only():
    s=bi.compile_report_spec('Genera solo PDF ejecutivo con vendedores y clientes perdidos')
    assert s['outputs']['pdf'] is True and s['outputs']['html'] is False and s['outputs']['excel'] is False
    assert s['sections'][0]=='resumen' and 'vendedores' in s['sections'] and 'clientes_perdidos' in s['sections']


def test_model_kpis():
    df=sample_df(); roles=bi.semantic_map(df); work,derived,notes=bi.prepare_business(df,roles); spec=bi.compile_report_spec('dashboard html pdf excel completo')
    m=bi.build_bi_model(df,work,roles,derived,'x',spec)
    assert m['kpis']['Ventas']==3900.0
    assert m['kpis']['Costo']==3200.0
    assert m['kpis']['Utilidad']==700.0
    assert m['kpis']['Operaciones']==3
    assert m['kpis']['Clientes']==2


def test_generators_smoke():
    df=sample_df(); roles=bi.semantic_map(df); work,derived,notes=bi.prepare_business(df,roles); spec=bi.compile_report_spec('dashboard html pdf excel completo')
    m=bi.build_bi_model(df,work,roles,derived,'x',spec)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        tpl=ROOT/'scripts'/'templates'/'dashboard_bi.html'
        bi.generate_html(td/'d.html',tpl,bi.build_dashboard_payload(work,m,'x.xlsx'),spec['sections'])
        bi.generate_pdf(td/'r.pdf','x.xlsx',m,notes)
        bi.generate_excel(td/'a.xlsx','x.xlsx',m)
        assert (td/'d.html').stat().st_size>10000
        assert (td/'r.pdf').stat().st_size>10000
        assert (td/'a.xlsx').stat().st_size>10000
        html=(td/'d.html').read_text(encoding='utf-8')
        assert 'Clientes perdidos' in html and 'Facturas / operaciones' in html and 'const DATA=' in html
        assert 'cdnjs' not in html and 'fonts.googleapis.com' not in html and 'https://' not in html
        assert 'V8.5.5' in html
        assert 'Exportar CSV' in html and 'sortClients' in html and 'toggleClient' in html
        assert 'Notas del dashboard' in html and 'localStorage' in html
        assert 'Análisis por línea y zona' in html and 'toggleZone' in html



def test_dashboard_inline_json_is_js_safe():
    payload={
        'tx':[{'c':'Cliente "Especial"\nLinea 2\tC:\\Datos','p':'</script><script>alert(1)</script>','z':'Unicode \u2028 separador'}],
        'meta':{'prompt':'Primera linea\nSegunda linea\tcon tab\\ruta y "comillas"','rows':1}
    }
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        out=td/'safe.html'
        bi.generate_html(out,ROOT/'scripts'/'templates'/'dashboard_bi.html',payload,['resumen'])
        html=out.read_text(encoding='utf-8')
        assert 'const DATA=' in html
        assert r'\u003c/script\u003e' in html
        # El JSON debe conservar \n como dos caracteres, no insertar un salto dentro de la cadena JS.
        assert r'\"Especial\"\nLinea 2' in html
        assert r'Primera linea\nSegunda linea' in html
        match=re.search(r'const DATA=(.*?); const REQUESTED=(.*?);',html,re.S)
        assert match, 'No se encontro DATA/REQUESTED embebido'
        decoded=json.loads(match.group(1))
        decoded_requested=json.loads(match.group(2))
        assert decoded['tx'][0]['c'].startswith('Cliente \"Especial\"'.replace('\\"','"'))
        assert decoded['meta']['prompt'].startswith('Primera linea\nSegunda linea')
        assert decoded_requested==['resumen']

def test_prompt_negations_and_topn():
    s=bi.compile_report_spec('Genera dashboard HTML y PDF, sin Excel, top 20 productos y clientes, sin facturas, clientes inactivos de 6 meses.')
    assert s['outputs']=={'html':True,'pdf':True,'excel':False}
    assert s['top_n']==20
    assert s['inactivity_days']==180
    assert 'facturas' not in s['sections']
    assert 'productos' in s['sections'] and 'clientes' in s['sections']


def test_prompt_only_excel():
    s=bi.compile_report_spec('Genera solo Excel analítico con vendedores y calidad de datos')
    assert s['outputs']=={'html':False,'pdf':False,'excel':True}
    assert 'vendedores' in s['sections'] and 'calidad_datos' in s['sections']



def test_dashboard_tonnage_legend_and_hover_tooltip():
    tpl=(ROOT/'scripts'/'templates'/'dashboard_bi.html').read_text(encoding='utf-8')
    assert 'class="brton"' in tpl
    assert 'class="brpct"' in tpl
    assert 'showChartTip' in tpl and 'data-tip=' in tpl
    assert "chartValue(v,yKey)" in tpl
    assert "fmt(x.t,2)} T" in tpl
    assert ".slice(0,8),tot=" not in tpl
    assert "function productColor" in tpl
    assert "#productShare{height:auto" in tpl


def test_dashboard_negative_utilities_supported():
    tpl=(ROOT/'scripts'/'templates'/'dashboard_bi.html').read_text(encoding='utf-8')
    assert 'Utilidades negativas' in tpl
    assert 'negativeClientProfit' in tpl
    assert "filter(x=>num(x.u)<0)" in tpl
    assert "Math.abs(val)/mx*100" in tpl
    assert "background:${neg?'var(--rd)':color}" in tpl
    assert 'vmin=Math.min(0,...vals)' in tpl
    assert 'vmax=Math.max(0,...vals)' in tpl
    assert 'sy(0)' in tpl


def test_r8_customer_performance_planner_and_dashboard():
    import dashboard_planner as dp
    df=pd.DataFrame([
        {'cod_linea':'GRANO','Cod_Cliente':'C1','articulo':'MAIZ','cliente':'Cliente Uno','categoria':'VENTA EN CAMPO','Zona':' NORTE ','Vendedor':' Ana ','Toneladas_Vendidas_Actual':100,'Toneladas_Vendidas_Presupuesto':120,'Toneladas_Vendidas_Anterior':80,'Fecha_Inicial':'2026-01-01','Fecha_Final':'2026-12-31'},
        {'cod_linea':'GRANO','Cod_Cliente':'C2','articulo':'SORGO','cliente':'Cliente Dos','categoria':'CUENTA CLAVE','Zona':' SUR ','Vendedor':' Beto ','Toneladas_Vendidas_Actual':0,'Toneladas_Vendidas_Presupuesto':50,'Toneladas_Vendidas_Anterior':75,'Fecha_Inicial':'2026-01-01','Fecha_Final':'2026-12-31'},
        {'cod_linea':'PASTA','Cod_Cliente':'C3','articulo':'SOYA','cliente':'Cliente Tres','categoria':'CALL CENTER','Zona':' CENTRO ','Vendedor':' Carla ','Toneladas_Vendidas_Actual':30,'Toneladas_Vendidas_Presupuesto':0,'Toneladas_Vendidas_Anterior':0,'Fecha_Inicial':'2026-01-01','Fecha_Final':'2026-12-31'},
    ])
    plan=dp.detect_dashboard_plan(df,'dashboard de manejo y seguimiento de clientes con semaforo y presupuesto')
    assert plan['type']=='customer_performance'
    work,notes=dp.prepare_customer_performance(df,plan)
    model=dp.build_customer_performance_model(work,'prompt',plan)
    assert model['kpis']['Toneladas_Actuales']==130.0
    assert model['kpis']['Clientes_Perdidos']==1
    assert model['kpis']['Clientes_Recuperados']==1
    assert model['kpis']['Clientes_Presupuesto_Sin_Venta']==1
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)/'clientes.html'
        bi.generate_html(out,ROOT/'scripts'/'templates'/'dashboard_clientes.html',dp.customer_payload(model,'clientes.xlsx',len(df)),['customer_performance'])
        html=out.read_text(encoding='utf-8')
        assert 'SEMÁFORO DE CARTERA' in html
        assert 'CLIENTES PERDIDOS' in html
        assert 'Presupuesto' in html
        assert 'const DATA=' in html


def test_r8_generic_dashboard_fallback_exists():
    import dashboard_planner as dp
    df=pd.DataFrame([{'Equipo':'A','Temperatura':10},{'Equipo':'B','Temperatura':20}])
    plan=dp.detect_dashboard_plan(df,'crea un dashboard interactivo')
    assert plan['type']=='generic'
    payload=dp.generic_payload(df,'equipos.xlsx','crea un dashboard','Datos')
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)/'generic.html'
        bi.generate_html(out,ROOT/'scripts'/'templates'/'dashboard_generico.html',payload,['generic'])
        html=out.read_text(encoding='utf-8')
        assert 'DASHBOARD ADAPTABLE' in html
        assert 'Temperatura' in html

if __name__=='__main__':
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for t in tests:
        t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')

