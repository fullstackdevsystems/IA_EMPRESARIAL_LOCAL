# IA Empresarial Local — R9.4 Prompt Compiler Empresarial

Esta actualización agrega un compilador estructurado de prompts empresariales.

## Qué cambia

- Detecta prompts amplios de ventas/rentabilidad/logística.
- Genera KPIs exactos a partir de columnas reales.
- Agrega operación `ratio` para Utilidad/Ton, Costo/Ton y Precio/Ton.
- Genera filtros de Fecha, Semana, Zona, Categoría, Vendedor, Cliente, Artículo,
  ctrl_alm, Proveedor, Almacén, Origen, Destino y Cliente_Recoge cuando existen.
- Genera visualizaciones de producto, clientes, vendedores, zonas, categorías,
  proveedores, almacenes, fletes, origen/destino, evolución diaria, semanas y mermas.
- Mantiene R9.3 como guardia de seguridad.
- No inventa funciones que el renderer todavía no soporte.

## Aplicar

```powershell
cd C:\IA_EMPRESARIAL_LOCAL

.\.venv\Scripts\python.exe .\R9_4_PATCH\APLICAR_R9_4.py

$env:PYTHONPATH="$PWD\IA_Local\scripts"

.\.venv\Scripts\python.exe IA_Local\tests\test_bi_productivo.py
.\.venv\Scripts\python.exe IA_Local\scripts\run_enterprise_tests.py
```

La suite BI debe pasar 21/21.

Después reinicia el analizador y comprueba:

```powershell
Invoke-RestMethod "http://127.0.0.1:8090/version"
```

Debe mostrar:

`8.5.5-r9.4`
