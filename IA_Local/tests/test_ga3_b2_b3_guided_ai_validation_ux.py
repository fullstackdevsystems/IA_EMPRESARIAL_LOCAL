from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_ai.admin_console import UNIFIED_ADMIN_HTML
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


html = UNIFIED_ADMIN_HTML

check("guided_ai_card_present", "guidedAiCard" in html)
check(
    "guided_ai_customer_labels",
    all(
        label in html
        for label in (
            "Configurar inteligencia artificial",
            "Ollama local",
            "Servidor local compatible",
            "Continuar sin IA",
            "Probar IA",
            "Guardar y continuar",
            "Validar preparación",
        )
    ),
)
check(
    "guided_ai_uses_canonical_endpoints",
    "'/api/admin/ai/provider/test'" in html
    and "'/api/admin/tenants/'+encodeURIComponent(tenant)+'/config'" in html
    and "controlValidateReadiness()" in html,
)
check(
    "guided_ai_requires_live_test_before_enabled_save",
    "GUIDED_AI_TEST.fingerprint===guidedAiFingerprint(provider)" in html
    and "Primero prueba la IA con la configuración actual." in html,
)
check(
    "guided_ai_change_invalidates_test",
    "function guidedAiInvalidate()" in html
    and "GUIDED_AI_TEST=null;" in html
    and ("oninput=\"guidedAiInvalidate()\"" in html or "onchange=\"guidedAiInvalidate()\"" in html),
)
check(
    "guided_ai_readiness_is_server_authoritative",
    "status==='READY'" in html
    and "Listo: la preparación fue confirmada por el servidor." in html,
)
check(
    "technical_ai_editor_preserved_and_collapsed",
    "id=\"cpAiEditor\"" in html
    and "controlToggleAiAdvanced" in html
    and "editor.style.display='none';" in html,
)
check(
    "guided_ai_primary_hides_technical_names",
    "provider_type" not in html.split("guided.innerHTML=", 1)[1].split(
        "advanced.parentNode", 1
    )[0]
    and "base_url" not in html.split("guided.innerHTML=", 1)[1].split(
        "advanced.parentNode", 1
    )[0],
)
check(
    "session_storage_only",
    "sessionStorage" in html and "localStorage" not in html,
)
check(
    "no_new_backend_endpoint",
    "fetch('/api/admin" not in html
    and "api('/api/admin" in html,
)

with tempfile.TemporaryDirectory() as directory:
    store = EnterprisePlatformConfigStore(Path(directory))
    original = store.resolve_effective_config("tenant-a")["enabled_features"]
    disabled = {
        "provider_id": "disabled",
        "provider_type": "DISABLED",
        "enabled": False,
        "timeout": 30,
    }
    store.update_tenant(
        "tenant-a",
        {
            "ai_provider": disabled,
            "enabled_features": {**original, "ai_enabled": False},
        },
    )
    effective = store.resolve_effective_config("tenant-a")
    check("disabled_ai_persists", effective["ai_provider"]["provider_type"] == "DISABLED")
    check("disabled_ai_feature_persists", effective["enabled_features"]["ai_enabled"] is False)
    check(
        "other_feature_flags_preserved",
        effective["enabled_features"]["sql_enabled"] == original["sql_enabled"]
        and effective["enabled_features"]["dashboard_enabled"] == original["dashboard_enabled"],
    )
    try:
        store.update_tenant(
            "tenant-a",
            {
                "ai_provider": {
                    "provider_type": "OLLAMA",
                    "base_url": "https://remote.invalid",
                    "model": "local-model",
                    "enabled": True,
                    "timeout": 30,
                }
            },
        )
    except PlatformConfigError as exc:
        check("invalid_local_provider_blocked", exc.code == "AI_PROVIDER_INVALID")
    else:
        raise AssertionError("invalid_local_provider_blocked")

print("PASS GA.3-B2-B3 GUIDED AI VALIDATION UX")
