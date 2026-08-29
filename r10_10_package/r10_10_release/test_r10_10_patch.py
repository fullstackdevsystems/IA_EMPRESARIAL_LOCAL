from pathlib import Path
import tempfile,sys
sys.path.insert(0,str(Path(__file__).parent))
from apply_r10_10 import patch_api
BASE='''from typing import Optional\nfrom pydantic import BaseModel\nfrom .security import Principal, ensure_secret, safe_component, verify_token\nclass SettingsRequest(BaseModel):\n    x: Optional[str]=None\nADMIN_HTML="old"\ndef f():\n    @router.get("/admin", response_class=HTMLResponse)\n    def admin_page():\n        return ADMIN_HTML\n    @router.get("/api/enterprise/settings")\n    def settings(): pass\n'''
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'api.py';p.write_text(BASE);patch_api(p);s=p.read_text()
 assert 'UNIFIED_ADMIN_HTML' in s
 assert '/api/enterprise/admin/overview' in s
 assert '/api/enterprise/business-rules' in s
 assert '/api/enterprise/semantic-definitions' in s
 assert '/api/enterprise/analytic-rules' in s
 assert '/history' in s
 print('PASS unified_admin_route');print('PASS governance_endpoints');print('PASS semantic_endpoints');print('PASS analytic_endpoints');print('PASS history_endpoint');print('5/5 PASS R10.10 PATCH')
