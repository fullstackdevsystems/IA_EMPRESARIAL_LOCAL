from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_ai.product_settings_ui import PRODUCT_SETTINGS_HTML

def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print("PASS", name)

html = PRODUCT_SETTINGS_HTML

check("b4_ready_panel_present", 'id="readyPanel"' in html)
check("b4_customer_heading", "Preparación final" in html)
check("b4_company_status", 'id="readyCompany"' in html)
check("b4_admin_status", 'id="readyAdmin"' in html)
check("b4_data_status", 'id="readyData"' in html)
check("b4_ai_status", 'id="readyAi"' in html)
check("b4_server_authoritative_validation", 'pf("/api/enterprise/readiness/validate",{method:"POST"})' in html)
check("b4_ready_gate", 'overall==="READY"' in html)
check("b4_enter_label", "Entrar a IA Empresarial Local" in html)
check("b4_enter_route", 'window.location.assign("/app")' in html)
check("b4_setup_route", 'setup==="ready"' in html)
check("b3_continue_present", 'id="continueAiSetup"' in html)
check("b3_to_b4", 'window.location.assign("/settings?setup=ready")' in html)
check("no_local_storage", "localStorage" not in html)

print("R10_24B4_FIRST_RUN_READINESS=PASS")
