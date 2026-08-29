# IA Empresarial Local — R10.4 Enterprise Precedence

## FASE
R10.4 — Precedencia Empresarial

## Objetivo
Hacer operativa la gobernanza de R10.3. Las reglas empresariales y definiciones semánticas VALIDADO y vigentes deben prevalecer sobre inferencias heurísticas, memoria libre y conocimiento general del LLM.

## Código real revisado
- `enterprise_ai/knowledge_governance.py` — base acumulativa R10.3.
- `enterprise_ai/structured_data.py` — cálculo determinístico y roles heurísticos.
- `enterprise_ai/context_engine.py` — recuperación de datos, documentos y memoria.
- `enterprise_ai/factory.py` — composición de dependencias.
- `enterprise_ai/memory.py` — memoria persistente existente.
- `enterprise_ai/documents.py` — RAG documental existente.
- `enterprise_ai/security.py` — aislamiento empresa/usuario y prompt-injection.

## Hallazgo principal
R10.3 almacenaba y gobernaba reglas/diccionario, pero todavía no estaban conectados al camino de ejecución. `StructuredDataService` seguía infiriendo roles desde nombres de columnas y la utilidad podía caer en una fórmula heurística. `ContextEngine` tampoco elevaba explícitamente reglas/diccionario validados por encima de memoria e inferencia.

## Archivos nuevos
- `enterprise_ai/precedence_engine.py`

## Archivos modificados por el instalador
- `enterprise_ai/knowledge_governance.py` — elimina snapshot inicial duplicado de definición semántica.
- `enterprise_ai/factory.py` — inyecta `KnowledgeGovernance` + `PrecedenceEngine`.
- `enterprise_ai/structured_data.py` — usa definiciones validadas antes de inferencia; aplica regla validada para profit/utilidad antes del fallback heurístico.
- `enterprise_ai/context_engine.py` — incorpora reglas validadas en contexto y actualiza la jerarquía explícita.
- `VERSION.txt` — `8.5.5-r10.4-precedence`.

## Precedencia aplicada
1. Regla empresarial VALIDADA vigente.
2. Definición semántica VALIDADA vigente.
3. Configuración empresarial.
4. Documento oficial recuperado.
5. Memoria confirmada.
6. Inferencia del sistema.
7. Conocimiento general del LLM.

Las políticas del sistema y permisos permanecen por encima de la precedencia empresarial por seguridad.

## Seguridad de fórmulas
Las expresiones de reglas NO se ejecutan con `eval()` ni `exec()`. Se interpretan mediante AST restringido a nombres autorizados, constantes numéricas y `+ - * /`. Llamadas, atributos, imports y cualquier otra construcción se rechazan.

## Regla anti-degradación silenciosa
Si existe una regla VALIDADA aplicable y faltan columnas necesarias para ejecutarla, el sistema debe reportar el error de regla y no sustituirla silenciosamente por una fórmula inferida.

## Pruebas ejecutadas en construcción
- PASS validated_semantic_overrides_inference
- PASS semantic_company_isolation
- PASS validated_rule_temporal_precedence
- PASS deterministic_validated_rule_calculation
- PASS unsafe_rule_expression_blocked
- PASS validated_rule_conflict_blocked
- PASS explicit_precedence_chain
- PASS governance_history_deduplicated

Resultado: **8/8 PASS R10.4 ENTERPRISE PRECEDENCE**.

El instalador vuelve a ejecutar 8 pruebas de integración contra la instalación destino después de parchear y compilar.

## Riesgos
- Las reglas matemáticas soportan de forma deliberada un subconjunto seguro. Funciones avanzadas (`IF`, `CASE`, acumulados, ventanas) quedan para una fase posterior del motor de reglas.
- El instalador usa puntos de parcheo validados y cancela ante una estructura inesperada para evitar corrupción.
- R10.4 no modifica automáticamente reglas existentes ni valida propuestas sin intervención.

## Siguiente fase recomendada
R10.5 — Integración semántica universal BI: conectar el diccionario validado con `analizador_universal`, `bi_productivo`, `dashboard_dynamic` y el planificador para que los dashboards y reportes compartan exactamente el mismo mapa semántico gobernado.
