from pathlib import Path
import sys,tempfile,json
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import analizador_universal as a
from enterprise_sql_gateway import EnterpriseSqlConnectionStore,EnterpriseSecretStore
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
class S:
 def __init__(s):s.x={}
 def set(s,k,v):s.x[k]=v
 def get(s,k):return s.x.get(k)
 def delete(s,k):s.x.pop(k,None)
class P:
 def test_connection(s,p,t):return {}
 def discover(s,p):return [{'schema':'dbo','name':'Allowed','type':'TABLE','columns':[{'name':'Id','type':'int','nullable':False}]}]
 def execute(s,p,sql,params,t):return {'columns':['Id'],'rows':[[1],[2],[3]]}
with tempfile.TemporaryDirectory() as td:
 old=a.base.REPORTES;a.base.REPORTES=Path(td)/'r';events=[];sp=S();store=EnterpriseSqlConnectionStore(Path(td)/'sql',a._tenant_registry());a.configure_sql_admin_services(store=store,provider=P(),secret_store=EnterpriseSecretStore(sp),audit_events=events)
 try:
  reg=a._tenant_registry()
  for t in ('construction','services','logistics'):reg.create(tenant_id=t,name=t)
  ids=a._identity_store();ids.bootstrap_admin(user_id='sys',username='sys',display_name='Sys',password='SystemPassword!1',tenant_id='construction');ids.create_user(user_id='ta',username='ta',display_name='TA',password='TenantPassword!1',tenant_id='construction',roles=['TENANT_ADMIN']);ids.create_user(user_id='an',username='an',display_name='AN',password='AnalystPassword!1',tenant_id='construction',roles=['ANALYST']);ids.create_user(user_id='vw',username='vw',display_name='VW',password='ViewerPassword!1',tenant_id='construction',roles=['VIEWER'])
  with TestClient(a.app) as c:
   def h(u,p):return {'Authorization':'Bearer '+c.post('/api/auth/login',json={'username':u,'password':p}).json()['token']}
   sh,th,ah,vh=h('sys','SystemPassword!1'),h('ta','TenantPassword!1'),h('an','AnalystPassword!1'),h('vw','ViewerPassword!1')
   profile={'connection_id':'a','server':'s','database':'d','auth_mode':'WINDOWS_INTEGRATED','allowed_schemas':['dbo'],'allowed_tables':['dbo.Allowed'],'max_rows':2}
   ck('tenant_users_sql',c.post('/api/admin/sql/connections',headers=th,json=profile).status_code==200 and c.get('/api/admin/users',headers=th).status_code==200)
   smoke=c.post('/api/admin/sql/connections/a/smoke',headers=ah,json={'schema':'dbo','object':'Allowed','columns':['Id'],'limit':9});ck('analyst_smoke',smoke.status_code==200 and smoke.json()['row_count']==2 and smoke.json()['truncated'])
   ck('viewer_denied',c.post('/api/admin/sql/connections/a/smoke',headers=vh,json={'schema':'dbo','object':'Allowed','columns':['Id'],'limit':1}).status_code==403)
   ck('cross_tenant',c.get('/api/admin/tenants/services/config',headers=th).status_code==403 and c.get('/api/admin/sql/connections?tenant_id=services',headers=th).status_code==403)
   ck('system_global',c.patch('/api/admin/config',headers=sh,json={'default_ai_model':'future/model-1'}).status_code==200 and c.patch('/api/admin/config',headers=th,json={'product_name':'x'}).status_code==403)
   cfg=c.patch('/api/admin/tenants/construction/config',headers=th,json={'display_name':'Construcción','branding':{'accent_color':'#123ABC','theme':'professional-dark'}});ck('branding_config',cfg.status_code==200 and c.get('/api/admin/tenants/construction/config',headers=ah).status_code==200)
   ck('sql_policy',c.post('/api/admin/sql/connections/a/smoke',headers=th,json={'sql':'DELETE'}).status_code==400)
   ck('secret_safety','password' not in str(c.get('/api/admin/sql/connections/a',headers=th).json()).lower() and 'rows' not in str(events).lower())
   ck('audit',any(x['event']=='SQL_SMOKE_RUN' for x in events) and 'password' not in str(events).lower())
   ck('logout',c.post('/api/auth/logout',headers=vh).status_code==200 and c.get('/api/auth/me',headers=vh).status_code==401)
 finally:a.configure_sql_admin_services();a.base.REPORTES=old
print('PASS R10.20B.5')
