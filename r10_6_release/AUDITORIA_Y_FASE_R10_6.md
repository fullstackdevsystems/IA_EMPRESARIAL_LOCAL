# R10.6 — Reglas Empresariales en el Motor Analítico Universal

## Objetivo
Hacer que reglas empresariales VALIDADO gobiernen cálculos y selección de filas antes de BI, sin delegar aritmética al LLM.

## Diseño
Se agrega `enterprise_ai/analytic_rules.py` con dos tipos explícitos de binding:
- `row_filter`: determina qué filas participan en cálculos (ej. `Estatus == "A"`).
- `metric`: define una métrica calculada (ej. `Venta - Costo - Flete`).

Los bindings apuntan a reglas existentes de `business_rules`; solo se ejecutan si la regla continúa VALIDADA, activa, vigente y visible para la empresa/usuario.

## Seguridad
Las expresiones se interpretan con AST restringido. Se permiten constantes, columnas/roles autorizados, `+ - * /`, comparaciones y `and/or/not`. Se bloquean llamadas, atributos, imports, índices, comprehensions y código arbitrario. No se usa `eval()` ni `exec()`.

## Precedencia
`regla empresarial VALIDADA > definición semántica VALIDADA > inferencia del sistema > LLM`.

Si una regla VALIDADA vinculada no puede ejecutarse por falta de una columna/rol requerido, el motor no degrada silenciosamente a una fórmula heurística.

## Integración
- `factory.py`: registra `AnalyticRuleEngine`.
- `structured_data.py`: aplica filtros antes de agregaciones y métricas validadas antes del resultado.
- `bi_productivo.py`: aplica `row_filter` antes de preparar KPIs y `metric` antes de ratios.
- `analizador_universal.py`: acepta `analytic_context` y lo propaga al BI.
- `api.py`: endpoints para vincular reglas y listar bindings aplicables.

## Pruebas ejecutadas
- 7/7 PASS motor de reglas.
- 3/3 PASS seguridad de parcheo.

La suite instalada vuelve a probar filtro, utilidad validada y trazabilidad directamente sobre la instalación destino.

## Resultado
PASS — paquete acumulativo R10.6 preparado.

## Siguiente fase sugerida
R10.7 — Recuperación contextual/RAG empresarial avanzada: filtros por área/empresa/vigencia, deduplicación, reranking y compresión de contexto.
