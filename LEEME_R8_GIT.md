# IA EMPRESARIAL LOCAL V8.5.5 R8 - Dashboard Adaptativo

R8 introduce un Dashboard Planner para que la generacion HTML no dependa de una unica estructura transaccional de ventas.

## Cambios principales

- `dashboard_planner.py`: clasifica datasets y prepara familias de dashboard.
- `dashboard_clientes.html`: familia especializada Actual / Presupuesto / Anterior.
- `dashboard_generico.html`: fallback universal para datasets no especializados.
- `analizador_universal.py`: router R8; BDO ya no exige importe de venta ni fecha transaccional.
- `test_bi_productivo.py`: regresiones R8.

## Caso BDO validado

Columnas detectadas: cod_linea, Cod_Cliente, articulo, cliente, categoria, Zona, Vendedor,
Toneladas_Vendidas_Actual, Toneladas_Vendidas_Presupuesto, Toneladas_Vendidas_Anterior,
Fecha_Inicial, Fecha_Final.

Fecha_Inicial y Fecha_Final se tratan como cobertura del reporte, no como fecha de cada venta.

## Aplicar al repositorio

Copiar el contenido de este paquete encima de `C:\IA_EMPRESARIAL_LOCAL` conservando rutas.

Despues:

```powershell
cd C:\IA_EMPRESARIAL_LOCAL
$env:PYTHONPATH="IA_Local\scripts"
python IA_Local\tests\test_bi_productivo.py
python IA_Local\scripts\run_enterprise_tests.py

git status
git add IA_Local/scripts/dashboard_planner.py IA_Local/scripts/analizador_universal.py IA_Local/scripts/templates/dashboard_clientes.html IA_Local/scripts/templates/dashboard_generico.html IA_Local/tests/test_bi_productivo.py
git commit -m "feat: add adaptive dashboard planner and customer performance dashboard"
git push
```

Resultados esperados: BI 12/12 PASS y Enterprise 30/30 PASS.
