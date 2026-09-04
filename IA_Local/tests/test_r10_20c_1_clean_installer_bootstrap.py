from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'IA_Local'/'scripts'))
from enterprise_platform_config import EnterprisePlatformConfigStore
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
ps=(ROOT/'InstallerR1020C1.ps1').read_text(encoding='utf8');bat=(ROOT/'INSTALAR_IA_EMPRESARIAL_LOCAL.bat').read_text(encoding='utf8')
ck('installer_files',(ROOT/'InstallerR1020C1.ps1').is_file() and 'InstalarLimpio.ps1' in bat and 'InstallerR1020C1.ps1' in (ROOT/'InstalarLimpio.ps1').read_text(encoding='utf8') and (ROOT/'IA_Local'/'requirements-local.txt').is_file())
ck('prechecks','Windows x64 required' in ps and 'Unsupported Python' in ps and 'Install path not writable' in ps)
ck('venv_dependencies','python -m venv' in ps and 'pip install' in ps and 'requirements-local.txt' in ps)
ck('idempotent','-not(Test-Path (Join-Path $InstallPath \'scripts\'))' in ps and 'ValidateOnly' in ps)
ck('secure_bootstrap','No hardcoded tenant/admin/password' in ps and 'AdminPassword' not in ps and 'no model download' in ps)
ck('health_optional','HEALTH:PASS' in ps and 'AI_PROVIDER: NOT CONFIGURED' in ps and 'SkipSqlCheck' in ps)
ck('dirs_log','config' in ps and 'Reportes' in ps and 'installer-r10.20c.1.log' in ps)
ck('config_contract',EnterprisePlatformConfigStore)
print('PASS R10.20C.1')
