# IA Empresarial Local V8.5.5 R9 — Dashboard Dinámico IA + Identidad Primos & Cousins

## Objetivo
R9 elimina la dependencia de una plantilla de negocio específica para generar HTML.
Todos los dashboards HTML pasan por un único motor `dashboard_dynamic.py` que:

1. perfila automáticamente las columnas reales del archivo;
2. interpreta el prompt del usuario;
3. pide a Ollama/Qwen local un plan JSON de KPIs, filtros, gráficas y tabla cuando está disponible;
4. valida el plan contra columnas reales para impedir campos inventados;
5. usa un plan determinístico de respaldo si Ollama no está disponible o devuelve un plan inválido;
6. genera el HTML completo desde código, sin `dashboard_clientes.html`, `dashboard_bi.html` ni `dashboard_generico.html` como dependencia del dashboard generado;
7. aplica siempre la identidad visual institucional de PRIMOS & COUSINS y usa el logo proporcionado.

## Archivos
- `IA_Local/scripts/dashboard_dynamic.py` NUEVO
- `IA_Local/scripts/assets/primos_cousins_logo.png` NUEVO
- `IA_Local/scripts/analizador_universal.py` MODIFICADO
- `IA_Local/scripts/bi_productivo.py` MODIFICADO (incluye guard contra ausencia de Utilidad_Ton)
- `IA_Local/tests/test_bi_productivo.py` MODIFICADO

## Comportamiento
Las ramas actuales de clientes, BI comercial y analizador universal siguen calculando PDF/Excel como antes, pero cualquier HTML solicitado se genera por `dashboard_dynamic.py`.

El planificador IA local usa por defecto:
- URL: `http://127.0.0.1:11434/api/generate`
- modelo: `qwen3:4b-instruct`

Variables opcionales:
- `IA_OLLAMA_MODEL`: cambia el modelo.
- `IA_DYNAMIC_DASHBOARD_LLM=0`: desactiva el planificador LLM y fuerza el plan determinístico.

## Validación realizada
- BI: 14/14 PASS
- Enterprise: 30/30 PASS
- Excel real `Indicador de manejo de clientes`: hoja BDO detectada con el prompt completo.
- Generación real: HTML dinámico + PDF + Excel.
- JavaScript del preview: `node --check` PASS.

## Aplicar sobre C:\IA_EMPRESARIAL_LOCAL
Extraer este ZIP sobre la raíz del repositorio respetando las rutas y reemplazando archivos existentes.

Luego:
```powershell
cd C:\IA_EMPRESARIAL_LOCAL
$env:PYTHONPATH="$PWD\IA_Local\scripts"
.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

Esperado: 14/14 PASS y 30 tests OK.

Después:
```powershell
git status
git add IA_Local/scripts/dashboard_dynamic.py
git add IA_Local/scripts/assets/primos_cousins_logo.png
git add IA_Local/scripts/analizador_universal.py
git add IA_Local/scripts/bi_productivo.py
git add IA_Local/tests/test_bi_productivo.py
git add LEEME_R9_GIT.md
git commit -m "feat: generate prompt-driven institutional dashboards dynamically"
git push
```
