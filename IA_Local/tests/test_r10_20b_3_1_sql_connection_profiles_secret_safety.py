from pathlib import Path
import sys,tempfile,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from enterprise_sql_gateway import EnterpriseSqlConnectionStore,EnterpriseSqlError,EnterpriseSecretStore,public_sql_profile,assert_sql_profile_active
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
class Fake:
 def __init__(s):s.x={}
 def set(s,k,v):s.x[k]=v
 def get(s,k):return s.x.get(k)
 def delete(s,k):s.x.pop(k,None)
def scope(c):return {'company_id':c,'user_id':'admin','business_unit':None,'branch':None}
with tempfile.TemporaryDirectory() as td:
 st=EnterpriseSqlConnectionStore(Path(td));a=scope('construction');b=scope('services')
 w=st.register(scope=a,connection_id='win',server='server',database='db',auth_mode='WINDOWS_INTEGRATED',allowed_schemas=['dbo'],allowed_tables=['dbo.Objects'])
 q=st.register(scope=a,connection_id='sql',server='server',database='db',auth_mode='SQL_AUTH',secret_reference='secret:sql',allowed_schemas=['dbo'],allowed_tables=['dbo.Objects'])
 ck('profiles',w['auth_mode']=='WINDOWS_INTEGRATED' and q['secret_reference']=='secret:sql')
 ck('public_safe','password' not in json.dumps(public_sql_profile(q)).lower() and 'connection string' not in json.dumps(q).lower())
 ck('crud',len(st.list(a))==2 and st.get(a,'win')['connection_id']=='win' and st.update(a,'win',display_name='Construcción ñ')['display_name']=='Construcción ñ')
 ck('isolation',st.list(b)==[])
 d=st.disable(a,'win');ck('disable',d['status']=='DISABLED')
 try:assert_sql_profile_active(d)
 except EnterpriseSqlError as e:ck('disabled_closed',e.code=='SQL_CONNECTION_DISABLED')
 ck('enable',st.enable(a,'win')['status']=='ACTIVE')
 ck('reload',EnterpriseSqlConnectionStore(Path(td)).get(a,'win')['display_name']=='Construcción ñ')
 raw=Path(td)/'construction'/'admin'/'_'/'_'/'win.json';data=json.loads(raw.read_text());data['server']='tamper';raw.write_text(json.dumps(data))
 try:st.get(a,'win')
 except EnterpriseSqlError as e:ck('tamper',e.code=='SQL_CONNECTION_INTEGRITY_MISMATCH')
 f=Fake();sec=EnterpriseSecretStore(f);sec.set('secret:sql','value');ck('secret',sec.get('secret:sql')=='value');sec.delete('secret:sql')
 try:sec.get('secret:sql')
 except EnterpriseSqlError as e:ck('secret_closed',e.code=='SQL_SECRET_UNAVAILABLE')
print('PASS R10.20B.3.1')
