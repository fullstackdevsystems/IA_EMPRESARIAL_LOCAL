# IA Empresarial Local — R9.3 Intent Context + Partial Fulfillment

Corrige dos problemas:

1. Ya no interpreta frases como "nombres anteriores" como una solicitud de comparación contra periodo anterior.
2. Si una parte del prompt no puede calcularse, conserva KPIs, gráficas, filtros y tablas válidos, y solo advierte sobre la parte no disponible.

## Aplicar

```powershell
cd C:\IA_EMPRESARIAL_LOCAL

.\.venv\Scripts\python.exe .\R9_3_PATCH\APLICAR_R9_3.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"

.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

La suite BI debe pasar ahora 19/19.

Después reinicia el analizador y verifica:

```powershell
Invoke-RestMethod "http://127.0.0.1:8090/version"
```

Debe mostrar `8.5.5-r9.3`.
