# IA Empresarial Local — R9.2 Diseño institucional

Este parche cambia la capa visual de los dashboards dinámicos y conserva la lógica de datos y el Prompt Authority/Data Contract de R9.1.

Todos los dashboards generados usarán el mismo estilo institucional claro, turquesa Primos & Cousins, tarjetas KPI amigables, gráficas, tablas, filtros, sidebar y el logo original. Lo que cambia en cada dashboard será el contenido definido por el archivo y el prompt.

## Aplicación

```powershell
cd C:\IA_EMPRESARIAL_LOCAL
.\.venv\Scripts\python.exe .\R9_2_PATCH\APLICAR_R9_2_DISENO.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"
.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

Después reinicia el analizador y verifica `/version`; debe indicar `8.5.5-r9.2`.
