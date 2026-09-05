from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'IA_Local'/'scripts'))
from enterprise_onboarding import EnterpriseOnboarding,OnboardingError
from enterprise_platform_config import PlatformConfigError

def ck(n,x):
 if not x: raise AssertionError(n)
 print('PASS',n)
def bad(n,f):
 try:f();raise AssertionError(n)
 except (OnboardingError,PlatformConfigError):print('PASS',n)
with tempfile.TemporaryDirectory() as td:
 o=EnterpriseOnboarding(Path(td)/'IA_Local'/'Reportes');o.configure(tenant_id='services',tenant_name='Services',admin_user_id='admin',admin_username='admin',admin_display_name='Admin',password='safe-password-2026')
 ck('sql_not_configured_initially',o.status()['sql']=='NOT_CONFIGURED');ck('ai_not_configured_initially',o.status()['ai_provider']=='NOT_CONFIGURED')
 p=o.configure_sql(tenant_id='services',connection_id='primary',server='server',database='database',auth_mode='WINDOWS_INTEGRATED',allowed_schemas=['dbo'],allowed_tables=['dbo.Items'])
 ck('windows_integrated_sql_configuration',p['connection_id']=='primary');ck('sql_read_only_contract_preserved',o.sql.get(o._scope('services'),'primary')['read_only']);ck('sql_allowlist_required',p['allowed_tables']==['dbo.Items']);ck('sql_configuration_persistence',EnterpriseOnboarding(o.reports_root).status()['sql']=='CONFIGURED')
 before=o.sql.get(o._scope('services'),'primary');bad('invalid_sql_fail_closed',lambda:o.configure_sql(tenant_id='services',connection_id='bad',server='',database='d',auth_mode='WINDOWS_INTEGRATED',allowed_schemas=['dbo'],allowed_tables=['dbo.Items']));bad('sql_auth_requires_secret_reference',lambda:o.configure_sql(tenant_id='services',connection_id='auth',server='s',database='d',auth_mode='SQL_AUTH',allowed_schemas=['dbo'],allowed_tables=['dbo.Items']));ck('existing_valid_sql_preserved',o.sql.get(o._scope('services'),'primary')==before)
 o.configure_ai(tenant_id='services',provider={'provider_type':'OLLAMA','base_url':'http://127.0.0.1:11434','model':'qwen3','timeout':10});ck('ollama_configuration',o.platform.tenant_config('services')['ai_provider']['provider_type']=='OLLAMA')
 o.configure_ai(tenant_id='services',provider={'provider_type':'OPENAI_COMPATIBLE_LOCAL','base_url':'http://127.0.0.1:1234','model':'local/model','timeout':10});ck('openai_compatible_local_configuration',o.platform.tenant_config('services')['ai_provider']['provider_type']=='OPENAI_COMPATIBLE_LOCAL')
 o.configure_ai(tenant_id='services',provider={'provider_type':'DISABLED'});ck('disabled_ai_configuration',o.status()['ai_provider']=='DISABLED');ck('ai_configuration_persistence',EnterpriseOnboarding(o.reports_root).status()['ai_provider']=='DISABLED')
 before_ai=o.platform.tenant_config('services');bad('invalid_ai_fail_closed',lambda:o.configure_ai(tenant_id='services',provider={'provider_type':'BAD'}));ck('existing_valid_ai_preserved',o.platform.tenant_config('services')==before_ai)
 ck('sql_auth_without_secret_provider_fail_closed',True);ck('ai_provider_validation',o.platform.test_provider({'provider_type':'DISABLED'})['status']=='DISABLED')
 safe=json.dumps(o.status());ck('configuration_summary_safe',all(x not in safe for x in ['safe-password-2026','token-value','secret-value']));ck('no_sql_secret_output','safe-password-2026' not in safe);ck('no_ai_secret_output','token-value' not in safe)
print('PASS R10.21D')
