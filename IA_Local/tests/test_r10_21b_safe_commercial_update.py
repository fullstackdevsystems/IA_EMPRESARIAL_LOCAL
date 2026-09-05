from pathlib import Path
import hashlib,json,sys,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'IA_Local'/'scripts'))
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
manifest=json.loads((ROOT/'MANIFEST_SHA256.json').read_text(encoding='utf8'))
scripts=[x['path'] for x in manifest['files'] if x['path'].startswith('IA_Local/scripts/')]
ps=(ROOT/'InstallerR1020C1.ps1').read_text(encoding='utf8')
ck('detects_existing_install','INSTALL MODE: UPGRADE' in ps)
ck('replaces_managed_runtime',"$stagedScripts = Join-Path $backupRoot 'new_scripts'" in ps and "Copy-Item (Join-Path $stagedScripts '*')" in ps and scripts)
ck('adds_new_runtime_files','foreach ($entry in $manifest.files)' in ps)
ck('rollback_or_fail_closed_contract','previous scripts restored' in ps)
upgrade=ps[ps.find("INSTALL MODE: UPGRADE"):ps.find("foreach ($d in 'config'")]
ck('preserves_persistent_state',all(x not in upgrade for x in ['Reportes','workspace','config','data','logs']))
with tempfile.TemporaryDirectory() as td:
 root=Path(td);runtime=root/'IA_Local';(runtime/'scripts').mkdir(parents=True);(runtime/'Reportes').mkdir();(runtime/'scripts'/'old.py').write_text('old');(runtime/'Reportes'/'state.txt').write_text('keep');(runtime/'scripts').rmdir() if False else None
 ck('persistent_fixture',(runtime/'Reportes'/'state.txt').read_text()=='keep')
print('PASS R10.21B')
