from pathlib import Path
import json, sys, tempfile
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import analizador_universal as app
from enterprise_tenant_registry import EnterpriseTenantRegistry
from enterprise_identity import EnterpriseIdentityStore,IdentityError
def ck(n,x):
 if not x: raise AssertionError(n)
 print('PASS',n)
def code(expected,fn):
 try:fn()
 except IdentityError as e: ck(expected,e.code==expected);return
 raise AssertionError(expected)
with tempfile.TemporaryDirectory() as td:
 root=Path(td); tenants=EnterpriseTenantRegistry(root/'tenants')
 for i,n in [('construction','Construcción'),('services','Servicios'),('logistics','Logística')]:tenants.create(tenant_id=i,name=n)
 store=EnterpriseIdentityStore(root/'identity',tenants,ttl_minutes=1,lock_attempts=2)
 admin=store.bootstrap_admin(user_id='root',username='root',display_name='Raíz',password='StrongPassword!1',tenant_id='construction')
 raw=(root/'identity'/'identity.json').read_text(encoding='utf8');ck('hash_secret','StrongPassword!1' not in raw and 'scrypt$' in raw)
 tok,me=store.login('root','StrongPassword!1');ck('login_scope',store.scope(me,'obra','norte')['company_id']=='construction')
 store.update('root',business_units=['obra'],branches=['norte']); me=store.authenticate(tok);code('BUSINESS_UNIT_SCOPE_DENIED',lambda:store.scope(me,'otra'));code('BRANCH_SCOPE_DENIED',lambda:store.scope(me,'obra','sur'))
 store.change_password('root','AnotherPassword!2');code('AUTH_SESSION_INVALID',lambda:store.authenticate(tok));code('AUTH_INVALID_CREDENTIALS',lambda:store.login('root','StrongPassword!1'));tok,_=store.login('root','AnotherPassword!2');store.logout(tok);code('AUTH_SESSION_INVALID',lambda:store.authenticate(tok))
 code('AUTH_INVALID_CREDENTIALS',lambda:store.login('unknown','no'));code('AUTH_INVALID_CREDENTIALS',lambda:store.login('root','bad'));code('AUTH_INVALID_CREDENTIALS',lambda:store.login('root','bad'));code('AUTH_LOCKED',lambda:store.login('root','AnotherPassword!2'))
 data=json.loads((root/'identity'/'identity.json').read_text());data['users'][0]['display_name']='tampered';(root/'identity'/'identity.json').write_text(json.dumps(data),encoding='utf8');code('IDENTITY_INTEGRITY_MISMATCH',lambda:EnterpriseIdentityStore(root/'identity',tenants).list())
with tempfile.TemporaryDirectory() as td:
 old=app.base.REPORTES;app.base.REPORTES=Path(td)/'reports';reg=app._tenant_registry();reg.create(tenant_id='construction',name='Construcción');reg.create(tenant_id='services',name='Servicios')
 try:
  s=app._identity_store();s.bootstrap_admin(user_id='sys',username='sys',display_name='System',password='SystemPassword!1',tenant_id='construction');s.create_user(user_id='ta',username='tenantadmin',display_name='Admin Ñ',password='TenantPassword!1',tenant_id='construction',roles=['TENANT_ADMIN'],business_units=['obra'],branches=['norte']);s.create_user(user_id='viewer',username='viewer',display_name='Viewer',password='ViewerPassword!1',tenant_id='construction',roles=['VIEWER'])
  with TestClient(app.app) as c:
   ck('api_required',c.get('/api/admin/users').status_code==401 and c.get('/api/admin/tenants').status_code==403)
   login=c.post('/api/auth/login',json={'username':'sys','password':'SystemPassword!1'});ck('api_login',login.status_code==200 and 'password_hash' not in login.text);h={'Authorization':'Bearer '+login.json()['token']};ck('api_me',c.get('/api/auth/me',headers=h).status_code==200);created=c.post('/api/admin/users',headers=h,json={'user_id':'analyst','username':'analyst','display_name':'Analyst','password':'AnalystPassword!1','tenant_id':'services','roles':['ANALYST']});ck('api_create',created.status_code==200 and 'password_hash' not in created.text);ck('api_get_list',c.get('/api/admin/users/analyst',headers=h).status_code==200 and c.get('/api/admin/users',headers=h).status_code==200);ck('api_patch',c.patch('/api/admin/users/analyst',headers=h,json={'roles':['VIEWER']}).status_code==200);ck('api_reset',c.post('/api/admin/users/analyst/reset-password',headers=h,json={'password':'ResetPassword!3'}).status_code==200);tlogin=c.post('/api/auth/login',json={'username':'tenantadmin','password':'TenantPassword!1'});th={'Authorization':'Bearer '+tlogin.json()['token']};deny=c.post('/api/admin/users',headers=th,json={'user_id':'bad','username':'bad','display_name':'bad','password':'BadPassword!12','tenant_id':'services','roles':['SYSTEM_ADMIN']});ck('escalation_blocked',deny.status_code==403);ck('tenant_guard',c.get('/api/admin/tenants',headers=th).status_code==200 and len(c.get('/api/admin/tenants',headers=th).json()['tenants'])==1);vlogin=c.post('/api/auth/login',json={'username':'viewer','password':'ViewerPassword!1'});ck('viewer_denied',c.get('/api/admin/users',headers={'Authorization':'Bearer '+vlogin.json()['token']}).status_code==403);ck('logout_api',c.post('/api/auth/logout',headers=h).status_code==200 and c.get('/api/auth/me',headers=h).status_code==401)
 finally:app.base.REPORTES=old
print('PASS R10.20B.2')
