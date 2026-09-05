"""Governed backup/restore of commercial persistent state only."""
from __future__ import annotations
import hashlib,json,shutil,tempfile,zipfile
import argparse
from datetime import datetime,timezone
from pathlib import Path

STATE=(".tenants",".identity",".platform_config",".sql_connections","workspace","data")
class BackupError(ValueError):pass
def safe(rel):
 p=Path(rel)
 if not rel or rel.startswith(("/","\\")) or p.is_absolute() or ".." in p.parts or ":" in rel or "\\" in rel:raise BackupError("unsafe backup path")
 return p.as_posix()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def backup(reports,output):
 reports=Path(reports);files=[]
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name in STATE:
   root=reports/name
   if root.exists():
    for f in root.rglob('*') if root.is_dir() else [root]:
     if f.is_file():
      rel=safe('persistent/Reportes/'+f.relative_to(reports).as_posix());raw=f.read_bytes();files.append({'path':rel,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()});z.writestr(rel,raw)
  m={'format':'IA_EMPRESARIAL_LOCAL_BACKUP','version':1,'created_at':datetime.now(timezone.utc).isoformat(),'files':files,'total_files':len(files)};z.writestr('backup_manifest.json',json.dumps(m,sort_keys=True))
 return Path(output)
def restore(reports,source,*,_fail_after_stage=False):
 reports=Path(reports);source=Path(source)
 with zipfile.ZipFile(source) as z:
  try:m=json.loads(z.read('backup_manifest.json'))
  except Exception as e:raise BackupError('missing manifest') from e
  names=z.namelist(); seen=set()
  for e in m.get('files',[]):
   rel=safe(e['path']);k=rel.lower()
   if k in seen or rel not in names or hashlib.sha256(z.read(rel)).hexdigest()!=e['sha256']:raise BackupError('backup integrity mismatch')
   seen.add(k)
  with tempfile.TemporaryDirectory() as td:
   stage=Path(td)/'state'
   for e in m['files']:
    target=stage/safe(e['path']).removeprefix('persistent/Reportes/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(e['path']))
   old=Path(td)/'old';old.mkdir()
   for n in STATE:
    if (reports/n).exists():shutil.move(str(reports/n),str(old/n))
   try:
    if _fail_after_stage:raise BackupError('injected restore failure')
    for n in STATE:
     if (stage/n).exists():shutil.move(str(stage/n),str(reports/n))
   except Exception:
    for n in STATE:
     if (reports/n).exists():shutil.rmtree(reports/n) if (reports/n).is_dir() else (reports/n).unlink()
     if (old/n).exists():shutil.move(str(old/n),str(reports/n))
    raise
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=('backup','restore'));p.add_argument('--runtime-root',required=True);p.add_argument('--backup-path');p.add_argument('--restore-path');a=p.parse_args();r=Path(a.runtime_root)/'IA_Local'/'Reportes'
 try:
  result=backup(r,a.backup_path) if a.action=='backup' and a.backup_path else restore(r,a.restore_path) if a.action=='restore' and a.restore_path else (_ for _ in ()).throw(BackupError('required path missing'))
  print(json.dumps({'status':'PASS'}));return 0
 except Exception as e:print(json.dumps({'status':'FAIL','code':type(e).__name__}));return 1
if __name__=='__main__':raise SystemExit(main())
