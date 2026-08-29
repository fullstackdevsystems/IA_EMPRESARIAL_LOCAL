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


def test_r9_dynamic_dashboard_prompt_driven_no_domain_template():
    import os
    import dashboard_dynamic as dd
    old=os.environ.get('IA_DYNAMIC_DASHBOARD_LLM')
    os.environ['IA_DYNAMIC_DASHBOARD_LLM']='0'
    try:
        df=pd.DataFrame([
            {'Cliente':'A','Producto':'Maiz','Zona':'Norte','Actual':100.0,'Presupuesto':120.0,'Anterior':80.0},
            {'Cliente':'B','Producto':'Sorgo','Zona':'Sur','Actual':50.0,'Presupuesto':40.0,'Anterior':60.0},
        ])
        plan=dd.build_dashboard_plan(df,'Genera dashboard de clientes con top 20 por zona, actual, presupuesto y anterior','demo.xlsx','BDO')
        assert plan['kpis']
        assert plan['charts']
        assert any(f['column']=='Zona' for f in plan['filters'])
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'dynamic.html'
            used=dd.generate_dynamic_dashboard(out,df,'dashboard por zona y cliente','demo.xlsx','BDO')
            html=out.read_text(encoding='utf-8')
            assert 'PRIMOS & COUSINS' in html
            assert 'Dashboard generado automáticamente' in html
            assert 'dashboard_clientes.html' not in html
            assert 'dashboard_bi.html' not in html
            assert used['planner'].startswith('deterministic-fallback')
    finally:
        if old is None: os.environ.pop('IA_DYNAMIC_DASHBOARD_LLM',None)
        else: os.environ['IA_DYNAMIC_DASHBOARD_LLM']=old


def test_r9_sales_without_cost_does_not_require_utilidad_ton():
    customers=pd.DataFrame([{'Cliente':'A','Ventas':100.0},{'Cliente':'B','Ventas':50.0}])
    products=pd.DataFrame([{'Producto':'P','Ventas':150.0}])
    out=bi._opportunities(customers,products,pd.DataFrame(),pd.DataFrame())
    assert isinstance(out,pd.DataFrame)

def test_r9_1_prompt_contract_blocks_fake_budget_and_previous():
    import os
    import dashboard_dynamic as dd
    old = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        df = pd.DataFrame([
            {"Cod_Cliente":"C1","Cliente":"A","Vendedor":"Ana","Articulo":"Maiz","Zona":"Norte",
             "Toneladas_Vendidas":100.0,"Importe_Venta":1000.0,"Utilidad":100.0,"Costo":900.0},
            {"Cod_Cliente":"C2","Cliente":"B","Vendedor":"Beto","Articulo":"Sorgo","Zona":"Sur",
             "Toneladas_Vendidas":50.0,"Importe_Venta":600.0,"Utilidad":50.0,"Costo":550.0},
        ])
        plan = dd.build_dashboard_plan(
            df,
            "Genera un dashboard ejecutivo centrado en clientes perdidos, presupuesto sin venta, recuperación de clientes y cumplimiento. Prioriza riesgos y oportunidades.",
            "detalle.xlsx",
            "BD",
        )
        assert plan["status"] == "partial"
        assert plan["kpis"]
        assert plan["charts"]
        assert plan["semantic_columns_strict"]["budget"] is None
        assert plan["semantic_columns_strict"]["previous"] is None
        assert "compliance" in plan["missing_requirements"]
        assert "lost_customers" in plan["missing_requirements"]
        assert "prompt-contract-partial" in plan["planner"]
    finally:
        if old is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old


def test_r9_1_prompt_contract_allows_real_actual_budget_previous():
    import os
    import dashboard_dynamic as dd
    old = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        df = pd.DataFrame([
            {"Cod_Cliente":"C1","Cliente":"A","Actual":100.0,"Presupuesto":120.0,"Anterior":80.0,"Zona":"Norte"},
            {"Cod_Cliente":"C2","Cliente":"B","Actual":0.0,"Presupuesto":40.0,"Anterior":60.0,"Zona":"Sur"},
        ])
        plan = dd.build_dashboard_plan(
            df,
            "Dashboard de clientes perdidos, recuperación, cumplimiento y presupuesto",
            "clientes.xlsx",
            "BDO",
        )
        assert plan["status"] == "ready"
        assert plan["semantic_columns_strict"]["actual"] == "Actual"
        assert plan["semantic_columns_strict"]["budget"] == "Presupuesto"
        assert plan["semantic_columns_strict"]["previous"] == "Anterior"
        assert "prompt-contract-ok" in plan["planner"]
    finally:
        if old is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old

def test_r9_3_names_previous_does_not_trigger_previous_comparison():
    import dashboard_prompt_guard as g
    p = "NO dependas exclusivamente de los nombres anteriores. Detecta automáticamente todos los valores únicos de ctrl_alm."
    intents = g.requested_intents(p)
    assert "previous_comparison" not in intents


def test_r9_3_real_previous_period_does_trigger_previous_comparison():
    import dashboard_prompt_guard as g
    p = "Compara las ventas del periodo actual contra el periodo anterior."
    intents = g.requested_intents(p)
    assert "previous_comparison" in intents


def test_r9_3_partial_fulfillment_keeps_valid_content():
    import os
    import pandas as pd
    import dashboard_dynamic as dd
    old = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        df = pd.DataFrame([
            {"Cod_Cliente":"C1","Cliente":"A","Vendedor":"Ana","Zona":"Norte","Articulo":"Maiz",
             "Toneladas_Vendidas":100.0,"Importe_Venta":1000.0,"Costo":900.0,"Utilidad":100.0},
            {"Cod_Cliente":"C2","Cliente":"B","Vendedor":"Beto","Zona":"Sur","Articulo":"Sorgo",
             "Toneladas_Vendidas":50.0,"Importe_Venta":600.0,"Costo":550.0,"Utilidad":50.0},
        ])
        plan = dd.build_dashboard_plan(
            df,
            "Genera ventas, utilidad y riesgos. Además compara contra el periodo anterior.",
            "demo.xlsx","BD"
        )
        assert plan["status"] == "partial"
        assert plan["kpis"]
        assert plan["charts"]
        assert "previous_comparison" in plan["missing_requirements"]
        assert "prompt-contract-partial" in plan["planner"]
    finally:
        if old is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old

def test_r9_4_enterprise_prompt_compiler_builds_full_plan():
    import os
    import pandas as pd
    import dashboard_dynamic as dd
    old = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        df = pd.DataFrame([{
            "Fecha":"2026-08-01","Semana":"Semana 1-8","Zona":"PACIFICO",
            "Categoria":"VENTA EN CAMPO","Vendedor":"ANA","Cod_Cliente":"C1","Cliente":"CLIENTE 1",
            "Articulo":"MAIZ","ctrl_alm":"MAIZ AMARILLO GRANEL","Proveedor":"PROV 1","Almacen":"ALM 1",
            "Ciudad_Origen":"CULIACAN","Ciudad_Destino":"GUADALAJARA","Cliente_Recoge":"N",
            "Refer":"A1","Toneladas_Vendidas":10.0,"Importe_Venta":1000.0,"Costo":900.0,
            "Utilidad":100.0,"Costo_Producto":800.0,"Costo_Flete":80.0,"Otros_Costos":20.0,
            "Toneladas_Mermadas":0.1,"cod_linea":"GRANO"
        }])
        prompt = """Genera un dashboard ejecutivo de ventas, costos, logística, fletes y rentabilidad.
        KPIs ejecutivos: toneladas vendidas, venta total, costo total, utilidad total, margen %,
        utilidad por tonelada, costo por tonelada, precio promedio por tonelada, costo de producto,
        costo de fletes, otros costos, toneladas mermadas, clientes únicos y operaciones/referencias.
        Analiza productos, clientes, vendedores, zonas, categorías, proveedores, almacenes,
        fletes, origen destino, evolución por fecha, comparación por semana y alertas."""
        plan = dd.build_dashboard_plan(df,prompt,"demo.xlsx","BD")
        assert plan["title"] == "Dashboard Ejecutivo de Ventas y Rentabilidad"
        assert plan["prompt_compiler"]["version"] in {"r9.4","r9.5","r9.5.1","r9.6","r9.7"}
        assert plan["prompt_compiler"]["kpi_count"] >= 14
        assert plan["prompt_compiler"]["filter_count"] >= 10
        assert plan["prompt_compiler"]["chart_count"] >= 10
        labels = {x["label"] for x in plan["kpis"]}
        assert "Margen %" in labels
        assert "Utilidad por Tonelada" in labels
        assert "Costo de Fletes" in labels
        assert any(x.get("column") == "ctrl_alm" for x in plan["filters"])
        assert "enterprise-prompt-compiler-r9." in plan["planner"]
    finally:
        if old is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old


def test_r9_4_ratio_kpi_renderer_present():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "scripts" / "dashboard_dynamic.py"
    s = p.read_text(encoding="utf-8")
    assert "if(op==='ratio')" in s

def test_r9_5_advanced_analytics_payload():
    import os, pandas as pd, dashboard_dynamic as dd
    old1=os.environ.get("IA_DYNAMIC_DASHBOARD_LLM"); old2=os.environ.get("IA_EXECUTIVE_SUMMARY_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"]="0"; os.environ["IA_EXECUTIVE_SUMMARY_LLM"]="0"
    try:
        df=pd.DataFrame([
          {"Fecha":"2026-08-01","Semana":"Semana 1-8","Zona":"PACIFICO","Categoria":"VENTA EN CAMPO","Vendedor":"ANA","Cod_Cliente":"C1","Cliente":"CLIENTE 1","Articulo":"MAIZ","ctrl_alm":"MAIZ AMARILLO GRANEL","Proveedor":"P1","Almacen":"A1","Ciudad_Origen":"CULIACAN","Ciudad_Destino":"GDL","Cliente_Recoge":"N","Refer":"R1","Toneladas_Vendidas":10.0,"Importe_Venta":1000.0,"Costo":900.0,"Utilidad":100.0,"Costo_Producto":800.0,"Costo_Flete":80.0,"Otros_Costos":20.0,"Toneladas_Mermadas":0.0,"cod_linea":"GRANO"},
          {"Fecha":"2026-08-02","Semana":"Semana 1-8","Zona":"PACIFICO","Categoria":"VENTA EN CAMPO","Vendedor":"ANA","Cod_Cliente":"C2","Cliente":"CLIENTE 2","Articulo":"MAIZ","ctrl_alm":"MAIZ AMARILLO GRANEL","Proveedor":"P1","Almacen":"A1","Ciudad_Origen":"CULIACAN","Ciudad_Destino":"MTY","Cliente_Recoge":"N","Refer":"R2","Toneladas_Vendidas":0.0,"Importe_Venta":0.0,"Costo":50.0,"Utilidad":-50.0,"Costo_Producto":0.0,"Costo_Flete":50.0,"Otros_Costos":0.0,"Toneladas_Mermadas":0.0,"cod_linea":"GRANO"}])
        p=dd.build_dashboard_plan(df,"Genera dashboard ejecutivo completo de ventas, rentabilidad, fletes, clientes, proveedores, rutas, operaciones con utilidad negativa, margen por tonelada, KPIs ejecutivos y evolución por fecha.","demo.xlsx","BD")
        assert p["prompt_compiler"]["version"] in {"r9.5","r9.5.1","r9.6","r9.7"}
        assert p["advanced"]["negative_operations"]
        assert p["advanced"]["clients"]
        assert p["advanced"]["routes"]
        assert p["advanced"]["executive_findings"]
        assert p["advanced"]["validation"]["checks"]
    finally:
        if old1 is None: os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM",None)
        else: os.environ["IA_DYNAMIC_DASHBOARD_LLM"]=old1
        if old2 is None: os.environ.pop("IA_EXECUTIVE_SUMMARY_LLM",None)
        else: os.environ["IA_EXECUTIVE_SUMMARY_LLM"]=old2

def test_r9_5_renderer_has_advanced_features():
    from pathlib import Path
    s=(Path(__file__).resolve().parents[1]/"scripts"/"dashboard_dynamic.py").read_text(encoding="utf-8")
    assert "Buscar cliente" in s
    assert "Fecha desde / hasta" in s
    assert "tablePageSize" in s
    assert "Operaciones con Utilidad Negativa" in s
    assert "Rutas Origen → Destino" in s
    assert "negative" in s

def test_r9_5_1_renderer_recomputes_advanced_from_filtered_rows():
    from pathlib import Path
    s=(Path(__file__).resolve().parents[1]/"scripts"/"dashboard_dynamic.py").read_text(encoding="utf-8")
    assert "renderAdvanced(r)" in s
    assert "function advGroup(rows,dims)" in s
    assert "function dynamicFindings(rows,clients,products,routes,neg)" in s
    assert "function dynamicValidation(rows)" in s
    assert "operaciones negativas en la selección actual" in s

def test_r9_5_1_negative_count_is_not_detail_cap():
    import os, pandas as pd
    from enterprise_analytics import build_advanced_analytics
    old=os.environ.get("IA_EXECUTIVE_SUMMARY_LLM")
    os.environ["IA_EXECUTIVE_SUMMARY_LLM"]="0"
    try:
        rows=[{"Utilidad":-1.0,"Importe_Venta":0.0,"Costo":1.0,"Toneladas_Vendidas":0.0,"Costo_Flete":0.0,"Refer":f"R{i}","Cliente":f"C{i}","Cod_Cliente":f"C{i}"} for i in range(55)]
        a=build_advanced_analytics(pd.DataFrame(rows))
        assert len(a["negative_operations"]) == 40
        assert a["facts"]["operaciones_negativas"] == 55
        assert a["facts"]["impacto_negativo"] == -55.0
    finally:
        if old is None: os.environ.pop("IA_EXECUTIVE_SUMMARY_LLM",None)
        else: os.environ["IA_EXECUTIVE_SUMMARY_LLM"]=old


def test_r9_6_drilldown_is_exact_and_no_or_bug():
    import dashboard_dynamic as dd
    h = dd._HTML
    assert "function openDrill(kind,value)" in h
    assert "else if(kind==='product')" in h
    assert "else if(kind==='operation')" in h
    assert "||(product&&" not in h


def test_r9_6_clickable_charts_zero_axis_and_coverage():
    import dashboard_dynamic as dd
    h = dd._HTML
    assert "function applyChartFilter(dim,value)" in h
    assert "data-chart-dim" in h
    assert "bars zero" in h
    assert "promptCoverage" in h
    assert "Cobertura del Prompt" in h


def test_r9_6_prepare_rows_trims_text_without_dropping_zero_rows():
    import dashboard_dynamic as dd
    df = pd.DataFrame([{"Cliente":"  ACME  ","Toneladas_Vendidas":0.0,"Utilidad":-10.0}])
    rows = dd._prepare_rows(df)
    assert len(rows) == 1
    assert rows[0]["Cliente"] == "ACME"
    assert rows[0]["Toneladas_Vendidas"] == 0.0
    assert rows[0]["Utilidad"] == -10.0





def test_r9_7_execution_plan_detects_generic_components():
    import os
    import dashboard_dynamic as dd
    old = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        df = pd.DataFrame([{
            "Cod_Cliente":"C1","Cliente":"Cliente 1","ctrl_alm":"GRUPO A","Toneladas_Vendidas":10.0,
            "Importe_Venta":1000.0,"Costo":800.0,"Utilidad":200.0,"Costo_Flete":100.0,
            "Vendedor":"Ana","Zona":"Norte","Categoria":"Campo","Proveedor":"Prov A","Almacen":"A1",
            "Ciudad_Origen":"Culiacan","Ciudad_Destino":"Mazatlan","Toneladas_Mermadas":0.1,"Refer":"R1","Fecha":"2026-08-01","Semana":31
        }])
        prompt = """Genera dashboard ejecutivo, KPIs y filtros globales. Crea tabla dinámica por cliente,
        reportes derivados por producto, análisis de vendedores, zonas, categorías, proveedores, almacenes,
        análisis de fletes, rutas origen destino, mermas, operaciones con pérdida, oportunidades,
        resumen ejecutivo, validación matemática y preguntas en lenguaje natural."""
        plan = dd.build_dashboard_plan(df,prompt,"demo.xlsx","BD")
        ep = plan["execution_plan"]
        assert ep["version"] == "r9.7"
        assert ep["source_of_truth"] == "BD"
        by_key = {x["key"]:x for x in ep["components"]}
        assert by_key["pivot_customer"]["status"] == "ready"
        assert by_key["derived_product_reports"]["status"] == "ready"
        assert by_key["sellers"]["status"] == "ready"
        assert by_key["natural_language"]["status"] == "unsupported"
        assert ep["requested_count"] >= 10
        assert 0 < ep["coverage_pct"] <= 100
        assert "enterprise-prompt-compiler-r9.7" in plan["planner"]
    finally:
        if old is None: os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM",None)
        else: os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old


def test_r9_7_renderer_has_dynamic_components_and_execution_coverage():
    import dashboard_dynamic as dd
    html = dd._HTML
    assert 'id="dynamicComponents"' in html
    assert 'function renderDynamicComponents(rows)' in html
    assert "execRequested('pivot_customer')" in html
    assert "execRequested('derived_product_reports')" in html
    assert 'productViewSelect' in html
    assert 'coverage_pct' in html
    assert 'renderAdvanced(r);renderDynamicComponents(r)' in html


def test_r9_7_warning_and_version_are_consistent():
    import enterprise_prompt_compiler as c
    import inspect
    src = inspect.getsource(c.compile_enterprise_prompt)
    assert '"version":"r9.7"' in src
    assert 'R9.7 compiló un plan de ejecución auditable' in src
    assert 'R9.5.1 compiló métricas' not in src

if __name__=='__main__':
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for t in tests:
        t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')


def test_r9_7_1_multiselect_filters_have_todos_and_clear_semantics():
    import inspect
    import dashboard_dynamic as dd
    src = inspect.getsource(dd)
    assert 'value="__ALL__" selected>Todos</option>' in src
    assert "vals.includes('__ALL__')" in src
    assert "selected[col]=[]" in src
    assert "o.value==='__ALL__'" in src
