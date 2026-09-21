from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "product_settings_ui.py"

text = UI.read_text(encoding="utf-8")

def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print("PASS", name)

check(
    "verification_fingerprint_exists",
    'let AI_VERIFIED_FINGERPRINT=""' in text,
)
check(
    "first_run_mode_is_explicit",
    'function aiSetupMode(){return new URLSearchParams(window.location.search).get("setup")==="ai"}' in text,
)
check(
    "fingerprint_uses_engine_and_model",
    'function aiFingerprint(){return q("aiEngine").value+"|"+q("aiModel").value.trim()}' in text,
)
check(
    "enabled_first_run_save_requires_exact_verified_selection",
    'if(aiSetupMode()&&engine!=="disabled"&&AI_VERIFIED_FINGERPRINT!==aiFingerprint())' in text,
)
check(
    "commercial_warning_is_nontechnical",
    "Prueba la configuración actual antes de guardar." in text,
)
check(
    "successful_live_test_sets_fingerprint",
    'AI_VERIFIED_FINGERPRINT=verified?aiFingerprint():""' in text,
)
check(
    "failed_test_clears_fingerprint",
    "invalidateAiVerification()" in text,
)
check(
    "engine_change_invalidates_test",
    'q("aiEngine").addEventListener("change",invalidateAiVerification);' in text,
)
check(
    "model_change_invalidates_test",
    'q("aiModel").addEventListener("change",invalidateAiVerification);' in text,
)
check(
    "redetect_invalidates_test",
    'async function detectAiModels(){invalidateAiVerification();' in text,
)
check(
    "disabled_ai_does_not_require_test",
    'engine!=="disabled"&&AI_VERIFIED_FINGERPRINT' in text,
)
check(
    "regular_settings_not_globally_gated",
    "if(aiSetupMode()" in text,
)

print("R10_24B3_COMMERCIAL_TEST_BEFORE_SAVE=PASS")
