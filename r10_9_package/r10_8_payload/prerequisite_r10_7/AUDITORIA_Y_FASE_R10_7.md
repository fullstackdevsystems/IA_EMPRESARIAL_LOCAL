# R10.7 — RAG Empresarial Avanzado

## Objetivo
Mejorar la recuperación contextual existente sin reemplazar memoria, embeddings, VectorStore ni DocumentService.

## Implementación
- `advanced_retrieval.py`: capa híbrida local sobre recuperación existente.
- detección de área de la consulta;
- candidatos ampliados y top-k final limitado;
- vigencia opcional desde metadata (`valid_from`, `valid_to`, `expires_at`);
- reranking híbrido: score vectorial + coincidencia léxica + área + autoridad;
- deduplicación exacta y por similitud Jaccard;
- compresión query-aware por oraciones;
- recuperación de reglas empresariales validadas por área;
- ContextEngine conserva structured data como autoridad para cifras y recibe contexto reducido.

## Seguridad
- aislamiento company/user permanece delegado a los servicios existentes;
- no se mezclan resultados entre principals;
- prompt injection sigue tratándose como dato por DocumentService/ContextEngine;
- R10.7 no ejecuta contenido recuperado;
- no agrega servicios externos ni requiere GPU.

## Compatibilidad
El constructor de `ContextEngine` conserva compatibilidad mediante parámetro opcional `advanced_retrieval=None`.

## Resultado esperado
Menos contexto irrelevante, menor consumo de tokens, mayor prioridad a conocimiento validado y documentos oficiales, y comportamiento más estable con modelos locales pequeños.
