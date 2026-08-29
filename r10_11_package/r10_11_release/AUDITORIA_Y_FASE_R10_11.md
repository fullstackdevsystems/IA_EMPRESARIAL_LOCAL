# R10.11 — Optimización para archivos grandes y rendimiento

## Principio
El perfilado puede usar una muestra controlada; las métricas empresariales no. Las agregaciones elegibles sobre CSV grandes se ejecutan en streaming por chunks y devuelven `exact=true` y `sampled_for_metric=false`.

## Cambios
- `performance.py`: inventario de motores, plan de ejecución, perfilado de muestra y agregación exacta por chunks.
- `structured_data.py`: fast-path para CSV grandes antes de cargar el archivo completo en RAM.
- `api.py`: `GET /api/enterprise/performance` (admin) para exponer política y motores disponibles.
- Reglas de negocio/analíticas gobernadas: si existe una regla que requiere el evaluador completo, el fast-path no se usa; se conserva la ruta productiva existente.
- Profit/utilidad: no se optimiza con una fórmula inferida; cae a la ruta gobernada existente.

## Seguridad semántica
No se sustituyen cálculos validados por aproximaciones. DuckDB/Polars son opcionales; la ausencia de esas librerías no rompe la instalación porque Pandas chunked es el fallback local.
