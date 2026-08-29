# IA Empresarial Local — Auditoría y primera fase segura

## Base revisada
Rama revisada: `feature/r10-dashboard-intelligence`.
Versión observada antes de este hito: `8.5.5-r10.1.1` en la rama. La actualización universal R10.2 se mantiene como capa acumulativa local.

## Diagnóstico basado en código real

### EXISTE Y FUNCIONA
- SQLite persistente con WAL y migraciones aditivas.
- Memoria empresarial persistente con empresa/usuario, categoría, fuente, confianza, importancia, estado, versión e historial.
- Recuperación lexical y semántica de memoria.
- RAG documental para PDF, DOCX, TXT/Markdown, CSV y Excel.
- Embeddings locales con Ollama o LM Studio.
- Vector store abstraído.
- Hash/fingerprint de documentos, versiones y chunks.
- Detección de prompt injection documental y tratamiento del contenido recuperado como datos.
- Aislamiento lógico company/user mediante `Principal` y `scope_clause`.
- Auditoría de acciones y métricas de consulta.
- Datos estructurados calculados con Python/Pandas en lugar de entregar el dataset completo al LLM.
- Planificación y dashboard dinámico ya existentes.

### EXISTE PARCIALMENTE / REQUIERE MEJORA
- Estados de memoria: existen estados operativos, pero no un modelo empresarial formal PROPUESTO/VALIDADO/RECHAZADO/OBSOLETO para reglas y diccionario.
- Procedencia: existe `source_type/source_ref`, pero reglas y definiciones semánticas requieren entidad estructurada propia.
- Vigencia temporal: memoria admite expiración, pero no selección formal de reglas por `valid_from/valid_to`.
- Conflictos: memoria detecta algunos reemplazos semánticos, pero no garantiza conflictos por nombre + vigencia en reglas empresariales.
- Mapa semántico: existe inferencia por patrones, pero falta diccionario persistente validado editable que prevalezca sobre inferencias.
- Reglas empresariales: hoy viven como memoria libre; falta contrato estructurado y auditable.
- RAG tabular: indexa muestra y esquema; los cálculos completos se deben mantener en el motor estructurado.

### NO EXISTE COMO CAPA FORMAL
- Tabla/servicio dedicado para diccionario empresarial validado.
- Tabla/servicio dedicado para reglas empresariales versionadas con vigencia y conflicto explícito.
- Precedencia programática completa: regla validada > definición validada > configuración > documento > memoria > inferencia > LLM.
- UI completa de Diccionario Empresarial y Reglas Empresariales.
- Dataset aprobado para fine-tuning separado de memoria.

### RIESGOS DE REGRESIÓN
- Reemplazar MemoryManager o DocumentService: NO recomendado.
- Hacer que el LLM escriba reglas VALIDADO automáticamente: prohibido.
- Mezclar inferencias semánticas con definiciones confirmadas sin procedencia: riesgo alto.
- Aplicar automáticamente una regla de una empresa a otra: bloqueado por diseño y debe conservarse.

## FASE IMPLEMENTADA: R10.3 — Knowledge Governance

### Objetivo
Agregar gobernanza estructurada sobre componentes existentes sin reescribir memoria/RAG.

### Archivos nuevos
- `scripts/enterprise_ai/knowledge_governance.py`
- `tests/test_r10_3_governance.py`

### Archivo modificado por instalador
- `scripts/enterprise_ai/factory.py`
- `VERSION.txt`

### Funcionalidad
- Reglas empresariales persistentes.
- Diccionario semántico persistente.
- Estados: PROPUESTO, VALIDADO, RECHAZADO, OBSOLETO.
- Aislamiento por empresa/usuario.
- Vigencia `valid_from` / `valid_to`.
- Detección de conflictos por vigencia.
- Reemplazo explícito de reglas/definiciones conflictivas.
- Historial y procedencia auditable.
- Ninguna propuesta se convierte automáticamente en VALIDADO.

### Pruebas ejecutadas durante construcción del paquete
- persistencia/schema
- aislamiento de empresa
- vigencia temporal
- conflicto de reglas
- conflicto de diccionario semántico
- historial/procedencia

Resultado: **6/6 PASS** en prueba aislada de la capa de gobernanza.

### Siguiente fase recomendada
R10.4 — Integración de precedencia: conectar `KnowledgeGovernance` con `StructuredDataService`, `ContextEngine` y el planificador BI para que las reglas/definiciones VALIDADO sean recuperadas antes de inferir o calcular, manteniendo las reglas propuestas fuera de producción.
