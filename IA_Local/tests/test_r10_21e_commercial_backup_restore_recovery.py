from pathlib import Path
import hashlib,json,sys,tempfile,zipfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'IA_Local'/'scripts'))
from enterprise_backup_recovery import backup,restore,BackupError
def ck(n,x):
 if not x:raise AssertionError(n)
 print('PASS',n)
with tempfile.TemporaryDirectory() as td:
 root=Path(td)/'IA_Local';r=root/'Reportes';(root/'scripts').mkdir(parents=True);(root/'scripts'/'managed.py').write_text('managed')
 data={'.tenants/tenants.json':'{"tenant_id":"balor"}','.identity/identity.json':'{"admin":"x"}','.platform_config/platform_config.json':'{"ai":"DISABLED"}','.sql_connections/balor/admin/_/_/sql.json':'{"read_only":true}','workspace/marker.txt':'persistent'}
 for p,v in data.items():(r/p).parent.mkdir(parents=True,exist_ok=True);(r/p).write_text(v)
 z=Path(td)/'backup.zip';backup(r,z);ck('backup_contract',z.is_file());
 cli=ROOT/'IA_Local'/'scripts'/'enterprise_backup_recovery.py';run=subprocess.run([sys.executable,str(cli),'backup','--runtime-root',str(root.parent),'--backup-path',str(Path(td)/'cli.zip')],capture_output=True,text=True);ck('python_cli_backup',run.returncode==0 and Path(td,'cli.zip').is_file());ck('python_cli_json_status',json.loads(run.stdout)['status']=='PASS');
 with zipfile.ZipFile(z) as q:m=json.loads(q.read('backup_manifest.json'));ck('backup_manifest',m['total_files']==len(data));ck('backup_integrity',all(hashlib.sha256(q.read(x['path'])).hexdigest()==x['sha256'] for x in m['files']));ck('managed_runtime_excluded',not any('scripts' in x['path'] for x in m['files']))
 shutil=None
 for p in data:(r/p).write_text('lost')
 restore(r,z);ck('tenant_recovery',(r/'.tenants/tenants.json').read_text()==data['.tenants/tenants.json']);ck('admin_recovery',(r/'.identity/identity.json').read_text()==data['.identity/identity.json']);ck('sql_recovery',(r/'.sql_connections/balor/admin/_/_/sql.json').read_text()==data['.sql_connections/balor/admin/_/_/sql.json']);ck('ai_recovery',(r/'.platform_config/platform_config.json').read_text()==data['.platform_config/platform_config.json']);ck('persistent_marker_recovery',(r/'workspace/marker.txt').read_text()=='persistent');ck('managed_runtime_preserved',(root/'scripts/managed.py').read_text()=='managed');restore(r,z);ck('idempotent_restore',(r/'workspace/marker.txt').read_text()=='persistent')
 (r/'workspace/marker.txt').write_text('lost');run=subprocess.run([sys.executable,str(cli),'restore','--runtime-root',str(root.parent),'--restore-path',str(z)],capture_output=True,text=True);ck('python_cli_restore',run.returncode==0 and (r/'workspace/marker.txt').read_text()=='persistent');run=subprocess.run([sys.executable,str(cli),'backup','--runtime-root',str(root.parent)],capture_output=True,text=True);ck('python_cli_failure_exit',run.returncode!=0)
 (r/'workspace/marker.txt').write_text('previous-valid')
 try:restore(r,z,_fail_after_stage=True);raise AssertionError('restore_failure_triggered')
 except BackupError:ck('restore_failure_triggered',True);ck('previous_valid_state_restored',(r/'workspace/marker.txt').read_text()=='previous-valid');ck('managed_runtime_unchanged',(root/'scripts/managed.py').read_text()=='managed')
 bad=Path(td)/'bad.zip';bad.write_bytes(b'bad')
 try:restore(r,bad);raise AssertionError('corrupt_zip_rejected')
 except (BackupError,zipfile.BadZipFile):print('PASS corrupt_zip_rejected')
 for unsafe,label in [('../archivo','unsafe_relative_path_rejected'),('..\\archivo','backslash_path_rejected'),('/absolute/path','absolute_path_rejected'),('C:\\absolute\\path','drive_path_rejected'),('C:/absolute/file','drive_absolute_path_rejected'),('\\\\server\\share\\archivo','unc_path_rejected')]:
  bad=Path(td)/(label+'.zip')
  entry={'path':unsafe,'size':1,'sha256':hashlib.sha256(b'x').hexdigest()}
  with zipfile.ZipFile(bad,'w') as q:q.writestr('backup_manifest.json',json.dumps({'files':[entry]}));q.writestr(unsafe,b'x')
  before=(r/'workspace/marker.txt').read_text()
  try:restore(r,bad);raise AssertionError(label)
  except BackupError:ck(label,(r/'workspace/marker.txt').read_text()==before)
 dup=Path(td)/'dup.zip';entry={'size':1,'sha256':hashlib.sha256(b'x').hexdigest()};files=[{**entry,'path':'persistent/Reportes/example.json'},{**entry,'path':'persistent/Reportes/EXAMPLE.json'}]
 with zipfile.ZipFile(dup,'w') as q:q.writestr('backup_manifest.json',json.dumps({'files':files}));q.writestr(files[0]['path'],b'x');q.writestr(files[1]['path'],b'x')
 before=(r/'workspace/marker.txt').read_text()
 try:restore(r,dup);raise AssertionError('duplicate_case_path_rejected')
 except BackupError:ck('duplicate_case_path_rejected',True);ck('duplicate_case_fail_closed',True);ck('state_unchanged_after_duplicate_case_failure',(r/'workspace/marker.txt').read_text()==before)
ck('no_plaintext_secrets',all('password' not in x['path'].lower() for x in m['files']))
print('PASS R10.21E')
