# R9.6 — Prompt Coverage + Interactive Renderer

Cambios principales:

- Corrige el drill-down contaminado por la condicion Cliente OR Producto.
- Doble clic en Cliente abre exclusivamente ese cliente; en Producto abre exclusivamente ese producto; en otra celda usa Refer para abrir la operacion exacta.
- Barras de dimensiones filtrables aplican el filtro al dashboard completo al hacer clic.
- Barras con valores negativos usan eje cero visual real.
- Semaforo deterministico: utilidad negativa rojo; positiva verde; cero naranja. No inventa umbrales empresariales.
- Limpia espacios al inicio/final de textos solo en la copia usada para el dashboard; no modifica BD.
- Agrega Cobertura del Prompt: Implementado / Parcial / Pendiente para funciones relevantes solicitadas.
- Mantiene analitica avanzada reactiva de R9.5.1.
- Version 8.5.5-r9.6.

## Aplicacion

Extrae la carpeta `R9_6_PATCH` dentro de `C:\IA_EMPRESARIAL_LOCAL` y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\R9_6_PATCH\APLICAR_R9_6.ps1
```

## Validacion

```powershell
$env:PYTHONPATH="$PWD\IA_Local\scripts"
$env:IA_DYNAMIC_DASHBOARD_LLM="0"
$env:IA_EXECUTIVE_SUMMARY_LLM="0"
.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

Esperado: BI 28/28 PASS y Enterprise 30/30 OK.

Reinicia el analizador y comprueba:

```powershell
Invoke-RestMethod "http://127.0.0.1:8090/version"
```

Debe devolver `8.5.5-r9.6`.
