"""Development-only deterministic manifest regeneration; never run by installer."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'MANIFEST_SHA256.json';old=json.loads(path.read_text(encoding='utf8'))
paths={item['path'] for item in old['files']}|{'InstalarLimpio.ps1','INSTALAR_IA_EMPRESARIAL_LOCAL.bat','InstallerR1020C1.ps1','OperarIA.ps1','BuildReleaseR1021A.ps1'}
files=[]
for rel in sorted(paths):
 p=ROOT/rel
 if not p.is_file():raise SystemExit(f'missing manifest file: {rel}')
 files.append({'path':rel.replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size})
path.write_text(json.dumps({'version':'r10.20c.1','files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
