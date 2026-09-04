from pathlib import Path
import json,sys,tempfile
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import analizador_universal as app
from enterprise_platform_config import EnterprisePlatformConfigStore,PlatformConfigError
from enterprise_tenant_registry import EnterpriseTenantRegistry
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
def bad(n,f):
 try:f()
 except PlatformConfigError:print('PASS',n);return
 raise AssertionError(n)
class Adapter:
 def health(self,p):return True
with tempfile.TemporaryDirectory() as td:
 root=Path(td); tenants=EnterpriseTenantRegistry(root/'tenants')
 for t in ('construction','services','logistics'):tenants.create(tenant_id=t,name=t)
 store=EnterprisePlatformConfigStore(root/'config',tenants);ck('defaults',store.global_config()['product_name']=='IA Empresarial Local')
 store.update_global({'default_theme':'professional-dark','ai_provider':{'provider_id':'ollama','provider_type':'OLLAMA','base_url':'http://localhost:11434','model':'qwen3:4b-instruct','enabled':True,'timeout':10}})
 store.update_tenant('construction',{'display_name':'Construcción Ñ','theme':'professional-light','branding':{'accent_color':'#123ABC','logo_reference':'logos/build.svg','theme':'professional-light'},'enabled_features':{'ai_enabled':True}})
 store.update_tenant('services',{'display_name':'Servicios','ai_provider':{'provider_id':'local','provider_type':'OPENAI_COMPATIBLE_LOCAL','base_url':'http://127.0.0.1:1234','model':'custom/model-1','enabled':True,'timeout':10}})
 ck('precedence',store.resolve_effective_config('construction')['branding']['display_name']=='Construcción Ñ' and store.resolve_effective_config('construction')['default_sql_timeout']==30)
 ck('design_context',store.design_context('construction')['display_name']=='Construcción Ñ' and store.design_context('construction')['tokens']['colors']['accent']=='#123ABC')
 ck('providers',store.test_provider(store.resolve_effective_config('services')['ai_provider'],Adapter())['status']=='PASS' and store.test_provider({'provider_id':'disabled','provider_type':'DISABLED'})['status']=='DISABLED')
 bad('invalid_branding',lambda:store.update_tenant('logistics',{'branding':{'logo_reference':'../secret'}}));bad('invalid_provider',lambda:store.update_global({'ai_provider':{'provider_type':'BAD'}}));bad('unknown',lambda:store.update_tenant('logistics',{'sql_read_only':False}))
 ck('public_safe','secret' not in json.dumps(store.public_effective_config('construction')).lower())
 reload=EnterprisePlatformConfigStore(root/'config',tenants);ck('reload',reload.tenant_config('construction')['display_name']=='Construcción Ñ')
 raw=root/'config'/'platform_config.json';d=json.loads(raw.read_text());d['global']['product_name']='tamper';raw.write_text(json.dumps(d));bad('tamper',lambda:EnterprisePlatformConfigStore(root/'config',tenants).global_config())
with tempfile.TemporaryDirectory() as td:
 old=app.base.REPORTES;app.base.REPORTES=Path(td)/'reports'
 try:
  reg=app._tenant_registry();reg.create(tenant_id='construction',name='C');reg.create(tenant_id='services',name='S');s=app._identity_store();s.bootstrap_admin(user_id='sys',username='sys',display_name='S',password='SystemPassword!1',tenant_id='construction');s.create_user(user_id='tenant',username='tenant',display_name='T',password='TenantPassword!1',tenant_id='construction',roles=['TENANT_ADMIN']);s.create_user(user_id='analyst',username='analyst',display_name='A',password='AnalystPassword!1',tenant_id='construction',roles=['ANALYST']);s.create_user(user_id='viewer',username='viewer',display_name='V',password='ViewerPassword!1',tenant_id='construction',roles=['VIEWER'])
  with TestClient(app.app) as c:
   def h(u,p):return {'Authorization':'Bearer '+c.post('/api/auth/login',json={'username':u,'password':p}).json()['token']}
   sh,th,ah,vh=h('sys','SystemPassword!1'),h('tenant','TenantPassword!1'),h('analyst','AnalystPassword!1'),h('viewer','ViewerPassword!1')
   ck('api_global',c.patch('/api/admin/config',headers=sh,json={'product_name':'Local Platform'}).status_code==200 and c.patch('/api/admin/config',headers=th,json={'product_name':'x'}).status_code==403)
   ck('api_tenant',c.patch('/api/admin/tenants/construction/config',headers=th,json={'display_name':'Obras'}).status_code==200 and c.patch('/api/admin/tenants/services/config',headers=th,json={'display_name':'No'}).status_code==403)
   ck('api_roles',c.get('/api/admin/tenants/construction/config',headers=ah).status_code==200 and c.patch('/api/admin/tenants/construction/config',headers=ah,json={'theme':'professional-dark'}).status_code==403 and c.get('/api/admin/config',headers=vh).status_code==403)
   ck('api_provider',c.post('/api/admin/ai/provider/test',headers=sh,json={'provider':{'provider_type':'DISABLED'}}).status_code==200)
 finally:app.base.REPORTES=old
print('PASS R10.20B.4')
