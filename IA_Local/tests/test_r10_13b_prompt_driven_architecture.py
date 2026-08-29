from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
sys.path.insert(0,str(SCRIPTS))

from prompt_intelligence import parse_prompt_intelligence
from dashboard_spec_builder import build_dashboard_spec
from dynamic_renderer import build_dynamic_renderer_model, runtime_markup

DF=pd.DataFrame({
    'Fecha':['2026-01-01','2026-02-01'],
    'Cliente':['A','B'],
    'Cod_Cliente':['1','2'],
    'Articulo':['Maiz','Sorgo'],
    'Vendedor':['V1','V2'],
    'Toneladas_Vendidas':[10.0,20.0],
    'Importe_Venta':[100.0,250.0],
    'Costo':[80.0,200.0],
    'Refer':['R1','R2'],
    'Almacen':['ALM1','ALM2'],
    'Ciudad_Origen':['CULIACAN','NAVOLATO'],
    'Ciudad_Destino':['MAZATLAN','CULIACAN'],
    'Cliente_Recoge':['S','N'],
})
ROLES={
    'date':'Fecha','customer':'Cliente','customer_id':'Cod_Cliente','product':'Articulo',
    'seller':'Vendedor','quantity':'Toneladas_Vendidas','revenue':'Importe_Venta','cost':'Costo',
    'transaction_id':'Refer','warehouse':'Almacen','origin_city':'Ciudad_Origen','destination_city':'Ciudad_Destino'
}

COMMERCIAL='''Analiza comercialmente el archivo. Quiero las siguientes páginas:\n- Resumen Ejecutivo\n- Clientes\n- Análisis\n- Facturas / Operaciones\n- Perfil de Cliente\n- Análisis por Línea\n- Clientes Perdidos\nIncluye ventas, toneladas, costos, utilidad, clientes, vendedores y facturas.'''
LOGISTICS='''Analiza el archivo exclusivamente desde una perspectiva logística.\nGenera un dashboard enfocado en:\n- movimientos por almacén\n- origen y destino\n- toneladas transportadas\n- participación por ciudad origen\n- participación por ciudad destino\n- almacenes con mayor movimiento\n- rutas principales\n- clientes que recogen\n- evolución mensual del movimiento\n- calidad de datos logísticos\nNo generes páginas de clientes perdidos, perfil de cliente ni análisis comercial si no son necesarias.\nQuiero las siguientes páginas:\n- Resumen Logístico\n- Almacenes\n- Rutas\n- Origen y Destino\n- Evolución\n- Detalle Logístico\n- Calidad de Datos\nNo inventes el costo total de flete.\nSi no existe una regla validada para combinar los diferentes componentes de flete, muéstralo como N/D.\nNo utilices una métrica derivada de flete salvo que exista provenance o una regla empresarial validada.'''
INVENTORY='''Analiza este archivo exclusivamente desde una perspectiva de inventario y operaciones.\nGenera un dashboard centrado en:\n- inventario\n- almacenes\n- productos\n- movimientos\n- rotación\n- stock\n- productos críticos\n- productos obsoletos\n- entradas y salidas\n- tendencias por producto\n- análisis por almacén\n- calidad de datos\nNo generes páginas de clientes, vendedores, facturación comercial ni rentabilidad si los datos no permiten esos análisis.\nEl dashboard debe crear únicamente las páginas relevantes que realmente pueda soportar con los datos disponibles.\nNo inventes columnas ni métricas.\nLas capacidades faltantes deben quedar como N/D o BLOCKED.'''

def spec(prompt):
    return build_dashboard_spec(DF,prompt,sheet='Datos',semantic_roles=ROLES)

def ids(s): return [p['id'] for p in s['pages']]

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('PASS',name)

ci=parse_prompt_intelligence(COMMERCIAL); cs=spec(COMMERCIAL)
li=parse_prompt_intelligence(LOGISTICS); ls=spec(LOGISTICS)
ii=parse_prompt_intelligence(INVENTORY); ins=spec(INVENTORY)

checks=[
 ('commercial_domain_sales',ci['domain']=='sales'),
 ('commercial_seven_pages',ids(cs)==['summary','customers','analysis','operations','customer_profile','line_analysis','lost_customers']),
 ('logistics_domain',li['domain']=='logistics'),
 ('logistics_exact_pages',ids(ls)==['logistics_summary','warehouses','routes','origin_destination','evolution','logistics_detail','data_quality']),
 ('logistics_no_lost_customers','lost_customers' not in ids(ls)),
 ('logistics_no_customer_profile','customer_profile' not in ids(ls)),
 ('logistics_warehouse_analysis',any(c['id']=='analysis:warehouse_movement' and c['status']=='SUPPORTED' for c in ls['components'])),
 ('logistics_routes_analysis',any(c['id']=='analysis:routes' and c['status']=='SUPPORTED' for c in ls['components'])),
 ('logistics_origin_share',any(c['id']=='analysis:origin_share' and c['status']=='SUPPORTED' for c in ls['components'])),
 ('logistics_destination_share',any(c['id']=='analysis:destination_share' and c['status']=='SUPPORTED' for c in ls['components'])),
 ('logistics_customer_pickup',any(c['semantic_role']=='customer_pickup' and c['status']=='SUPPORTED' for c in ls['components'])),
 ('unsafe_freight_blocked',any(c['id']=='kpi:freight' and c['status']=='BLOCKED' for c in ls['blocked'])),
 ('logistics_coverage_not_100',ls['coverage']['percent']<100),
 ('inventory_domain',ii['domain']=='inventory'),
 ('inventory_only_relevant_page',ids(ins)==['inventory']),
 ('inventory_no_customers','customers' not in ids(ins)),
 ('inventory_no_operations_page','operations' not in ids(ins)),
 ('inventory_no_profitability',not any(c['id']=='analysis:profitability' for c in ins['components'])),
 ('inventory_stock_blocked',any(c['id']=='kpi:stock' and c['status']=='BLOCKED' for c in ins['blocked'])),
 ('inventory_turnover_blocked',any(c['id']=='analysis:inventory_turnover' and c['status']=='BLOCKED' for c in ins['blocked'])),
 ('inventory_obsolete_blocked',any(c['id']=='analysis:obsolete_inventory' and c['status']=='BLOCKED' for c in ins['blocked'])),
 ('specs_differ',ids(cs)!=ids(ls) and ids(ls)!=ids(ins) and ids(cs)!=ids(ins)),
 ('renderer_version',build_dynamic_renderer_model(ls,{})['version']=='r10.13b.2'),
 ('renderer_uses_logistics_pages',[p['id'] for p in build_dynamic_renderer_model(ls,{})['pages']]==ids(ls)),
 ('runtime_host',"host.id='r13bPageHost'" in runtime_markup()),
]
for n,c in checks: check(n,c)
print(f'{len(checks)}/{len(checks)} PASS R10.13B.2 PROMPT-DRIVEN ARCHITECTURE')
