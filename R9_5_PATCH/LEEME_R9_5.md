# IA Empresarial Local — R9.5 Analytical Renderer

Incluye filtros avanzados, fecha desde/hasta, búsqueda de cliente, multiselección,
Top 10/20/50/Todos, tabla ordenable y paginada, negativos en rojo, rankings de
rentabilidad, operaciones negativas, rutas Origen → Destino, validación matemática,
drill-down y resumen ejecutivo con Qwen usando únicamente resultados calculados por Python.

## Aplicar

```powershell
cd C:\IA_EMPRESARIAL_LOCAL
.\.venv\Scripts\python.exe .\R9_5_PATCH\APLICAR_R9_5.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"
.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

Esperado BI: **23/23 PASS**

Reinicia el analizador y verifica:

```powershell
Invoke-RestMethod "http://127.0.0.1:8090/version"
```

Esperado: `8.5.5-r9.5`

Para desactivar solo el resumen Qwen:

```powershell
$env:IA_EXECUTIVE_SUMMARY_LLM="0"
```
