from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
sys.path.insert(0,str(SCRIPTS))

from prompt_intelligence import parse_prompt_intelligence
from dashboard_spec_builder import build_dashboard_spec
from dynamic_renderer import attach_dynamic_renderer, build_dynamic_renderer_model, runtime_markup
from dashboard_dynamic import _prepare_rows

PROMPT='''Analiza el archivo exclusivamente desde una perspectiva logística.
Genera un dashboard enfocado en:
- movimientos por almacén
- origen y destino
- toneladas transportadas
- participación por ciudad origen
- participación por ciudad destino
- almacenes con mayor movimiento
- rutas principales
- clientes que recogen
- evolución mensual del movimiento
- calidad de datos logísticos
No generes páginas de clientes perdidos, perfil de cliente ni análisis comercial si no son necesarias.
Quiero las siguientes páginas:
- Resumen Logístico
- Almacenes
- Rutas
- Origen y Destino
- Evolución
- Detalle Logístico
- Calidad de Datos
No inventes el costo total de flete.
Si no existe una regla validada para combinar los diferentes componentes de flete, muéstralo como N/D.
No utilices una métrica derivada de flete salvo que exista provenance o una regla empresarial validada.'''

DF=pd.DataFrame({
 'Fecha':['2026-01-01','2026-02-01','2026-03-01'],
 'Cliente':['A','B','A'],'Cod_Cliente':['1','2','1'],'Articulo':['Maiz','Sorgo','Maiz'],
 'Toneladas_Vendidas':[10.0,20.0,5.0],'Costo':[80.0,200.0,40.0],'Importe_Venta':[100.0,250.0,50.0],
 'Refer':['R1','R2','R3'],'Almacen':['ALM1','ALM2','ALM1'],'Ciudad_Origen':['CULIACAN','NAVOLATO','CULIACAN'],
 'Ciudad_Destino':['MAZATLAN','CULIACAN','MAZATLAN'],'Cliente_Recoge':['S','N','S'],
 'Costo_Flete_Corto':[1,2,3],'Costo_Flete_Largo':[4,5,6],'Costo_Flete_Traspaso':[7,8,9],
})
ROLES={'date':'Fecha','customer':'Cliente','customer_id':'Cod_Cliente','product':'Articulo','quantity':'Toneladas_Vendidas','cost':'Costo','revenue':'Importe_Venta','transaction_id':'Refer','warehouse':'Almacen','origin_city':'Ciudad_Origen','destination_city':'Ciudad_Destino'}

def check(name,cond):
 if not cond: raise AssertionError(name)
 print('PASS',name)

intent=parse_prompt_intelligence(PROMPT)
spec=build_dashboard_spec(DF,PROMPT,sheet='Datos',semantic_roles=ROLES)
plan={'kpis':[],'charts':[],'filters':[],'execution_plan':{'dashboard_spec':spec,'requested_count':999,'ready_count':999,'blocked_count':0,'coverage_pct':100.0,'components':[]}}
attach_dynamic_renderer(plan)
rt=runtime_markup()
large=pd.DataFrame({'x':range(20005)})

checks=[
 ('renderer_b2_version',build_dynamic_renderer_model(spec,{})['version']=='r10.13b.2'),
 ('generic_cost_not_false_positive','cost' not in intent['metrics']),
 ('freight_requested','freight' in intent['metrics']),
 ('monthly_specializes_trend','monthly_movement' in intent['analyses'] and 'trend' not in intent['analyses']),
 ('freight_metric_blocked',any(c['id']=='kpi:freight' and c['status']=='BLOCKED' for c in spec['components'])),
 ('freight_analysis_blocked',any(c['id']=='analysis:freight_analysis' and c['status']=='BLOCKED' for c in spec['components'])),
 ('canonical_execution_authority',plan['execution_plan'].get('authority')=='dashboard_spec'),
 ('canonical_execution_coverage',plan['execution_plan']['coverage_pct']==spec['coverage']['percent']),
 ('canonical_execution_blocked',plan['execution_plan']['blocked_count']==spec['coverage']['blocked']),
 ('full_rows_not_truncated',len(_prepare_rows(large))==20005),
 ('warehouse_executor',"analysis:warehouse_movement" in rt and "Movimiento por almacén" in rt),
 ('routes_executor',"analysis:routes" in rt and "Rutas principales" in rt),
 ('origin_destination_executor',"Participación por ciudad origen" in rt and "Participación por ciudad destino" in rt),
 ('monthly_executor',"Evolución mensual del movimiento" in rt and "Serie cronológica" in rt),
 ('customer_pickup_executor',"analysis:customer_pickup" in rt and "Clientes que recogen" in rt),
 ('quality_executor',"analysis:data_quality" in rt and "Completitud" in rt),
 ('detail_executor',"analysis:detail" in rt and "Detalle Logístico" in rt),
 ('filter_runtime_api','__IA_DASHBOARD_API__' in (SCRIPTS/'dashboard_dynamic.py').read_text(encoding='utf-8')),
 ('filter_change_listener',"ia-dashboard-filter-change" in rt),
 ('commercial_compatibility',"legacyMode=model.domain==='sales'" in rt),
]
for n,c in checks: check(n,c)
print(f'{len(checks)}/{len(checks)} PASS R10.13B.2 DYNAMIC COMPONENT EXECUTOR')
