# R9.1 corregido

Este paquete sustituye el parche anterior que tenía un error de sintaxis en `APLICAR_R9_1.py`.

Desde `C:\IA_EMPRESARIAL_LOCAL`:

```powershell
.\.venv\Scripts\python.exe .\R9_1_PATCH\APLICAR_R9_1.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"

.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```
