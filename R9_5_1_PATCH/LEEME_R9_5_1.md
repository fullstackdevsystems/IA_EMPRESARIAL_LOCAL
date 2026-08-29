# R9.5.1 — Reactive Analytics Fix

Hace que las secciones avanzadas reaccionen al mismo conjunto filtrado que KPIs, gráficas y detalle.

- Clientes, productos, pérdidas y rutas se recalculan con los filtros.
- Validación matemática se recalcula con los filtros.
- El resumen inicial puede provenir de Qwen; al filtrar, el resumen se recalcula inmediatamente en JavaScript con cifras exactas.
- El conteo total de operaciones negativas ya no queda limitado al Top 40 mostrado.

```powershell
cd C:\IA_EMPRESARIAL_LOCAL
.\.venv\Scripts\python.exe .\R9_5_1_PATCH\APLICAR_R9_5_1.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"
$env:IA_DYNAMIC_DASHBOARD_LLM="0"
$env:IA_EXECUTIVE_SUMMARY_LLM="0"

.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

Esperado BI acumulativo: **25/25 PASS**.
Versión: `8.5.5-r9.5.1`.
