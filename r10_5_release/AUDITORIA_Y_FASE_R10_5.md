# R10.5 — Integración Semántica Universal BI

## Objetivo
Unificar el significado de columnas entre StructuredDataService, `bi_productivo.py`, `dashboard_dynamic.py`, `dashboard_planner.py` y `analizador_universal.py` sin depender de nombres físicos ni romper aislamiento empresarial.

## Hallazgo
Los módulos usan dialectos semánticos distintos (`sales/revenue`, `cost/total_cost`, `price/unit_price`). R10.4 ya resuelve definiciones validadas por empresa, pero esa resolución no llegaba de manera común a todos los motores BI.

## Implementación
- Nuevo `enterprise_ai/semantic_registry.py`.
- Contrato canónico y bridge de aliases.
- Contexto semántico acotado mediante `contextvars`, evitando fugas entre solicitudes.
- `bi_productivo.semantic_map(..., semantic_context=None)` acepta overrides validados.
- `dashboard_dynamic`, `dashboard_planner` y `analizador_universal` aceptan el mismo contexto.
- Endpoint autenticado `/api/enterprise/semantic/resolve` para resolver y auditar el mapa por empresa/usuario.
- Sin identidad empresarial no se inventa una empresa default: se conserva la inferencia existente.

## Seguridad
Una definición de Empresa A no se aplica a Empresa B. El contexto ligado a una operación se limpia al finalizar mediante `ContextVar`.

## Compatibilidad
Todos los nuevos parámetros son opcionales. Los callers legacy continúan funcionando.

## Resultado esperado
El mismo campo validado debe representar el mismo rol en datos estructurados, BI productivo y dashboards. Las inferencias solo son fallback cuando no existe una definición validada.
