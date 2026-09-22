from pathlib import Path

root = Path(__file__).resolve().parents[2]
ui = (root / "IA_Local/scripts/enterprise_ai/product_settings_ui.py").read_text(encoding="utf8")

def check(name, value):
    assert value, name
    print(f"PASS {name}")

for label in ("Mi empresa", "Usuarios", "Datos y conexiones", "Inteligencia artificial", "Apariencia", "Seguridad y recuperación", "Avanzado"):
    check("section_" + label, label in ui)
for state in ("Listo", "Verificado", "Configurado", "Requiere configuración", "Requiere atención"):
    check("friendly_state_" + state, state in ui)
check("backup_recovery_reused", 'id="createBackup"' in ui and 'id="restoreBackup"' in ui)
check("permission_messages", "No tienes permiso" in ui)
print("R10_26D_COMMERCIAL_OPERATIONS_UX=PASS")
