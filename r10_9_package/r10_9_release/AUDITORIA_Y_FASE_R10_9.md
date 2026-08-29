# R10.9 — Auditoría y Trazabilidad Completa

## Objetivo
Responder de forma verificable **“¿Cómo obtuve este resultado?”** sin depender de la memoria del LLM ni exponer secretos.

## Implementado
- `result_traces`: una traza por ejecución autenticada.
- `result_trace_steps`: pasos ordenados de semántica, cálculo, reglas, RAG e interpretación.
- Sanitización/redacción de secretos y hash de payloads grandes.
- Aislamiento por `company_id` + `user_id`.
- Endpoints `/api/enterprise/traces`, `/{id}` y `/{id}/explain`.
- Hook de recuperación en `ContextEngine`.
- Hook de cálculo en `StructuredDataService`.
- Hook de reglas en `AnalyticRuleEngine`.
- `build_file_trace()` para manifiestos del analizador local sin inventar identidad empresarial.

## Qué debe mostrar una traza
- archivo/dataset;
- hoja;
- filas usadas;
- filtros;
- columnas/roles semánticos;
- reglas y versiones;
- fórmulas;
- motor (`python/pandas`, `SafeRuleEvaluator`, RAG, LLM local);
- fuentes y procedencia;
- estado/errores.

## Seguridad
No se guardan secretos. Campos sensibles se redactan. Prompt/respuesta/documentos completos se sustituyen por hash + longitud cuando llegan como detalle de traza.
