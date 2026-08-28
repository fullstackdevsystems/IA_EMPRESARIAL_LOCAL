# IA Local Empresarial V8 — Arquitectura de Memoria, RAG y Datos

## 1. Estado heredado y componentes reutilizados

V8 evoluciona el proyecto V7 sin sustituir las funciones que ya estaban validadas. Se conservan:

- Python 3.11 + FastAPI.
- Ollama como motor local principal y `qwen3:4b` como modelo predeterminado.
- Open WebUI como chat general.
- Open Terminal como herramienta auxiliar local.
- Analizador Universal de Excel/CSV en el puerto 8090.
- Cálculos determinísticos con Pandas para archivos tabulares.
- Reportes Excel/PDF profesionales y las protecciones V7 contra filtros inventados.

## 2. Arquitectura V8

```text
Usuario
  |
  v
Asistente Empresarial / API V8
  |
  v
ContextEngine
  |-- Politicas y permisos
  |-- StructuredDataService ------> Excel/CSV -> Python/Pandas
  |-- DocumentService / RAG ------> Embeddings -> VectorStore
  |-- MemoryManager --------------> SQLite + VectorStore
  |-- Historial reciente
  v
LLMProvider
  |-- OllamaProvider
  `-- LMStudioProvider
```

Prioridad del contexto:

1. políticas del sistema;
2. identidad/permisos;
3. datos actuales calculados;
4. documentos recuperados;
5. memoria permanente;
6. conversación reciente;
7. conocimiento general del modelo.

## 3. Memoria persistente

La memoria se almacena en `data/enterprise/enterprise_ai.sqlite3`. No depende de la ventana de contexto ni de que Ollama permanezca encendido.

Campos principales: ID, empresa, usuario, alcance, categoría, contenido, fuente, confianza, importancia, etiquetas, sensibilidad, estado, vigencia, versión, memoria sustituida y timestamps.

El Memory Manager clasifica mensajes en:

- contexto temporal: no se guarda;
- petición explícita de recordar: se almacena;
- posible regla/conocimiento estable: queda `pending` para confirmación;
- sensible: no se guarda automáticamente;
- conflicto: se propone como nueva versión y, al confirmarse, la memoria anterior se marca `superseded`.

## 4. RAG documental

Formatos admitidos por el código:

- PDF (`pypdf`)
- Word DOCX (`python-docx`)
- TXT / Markdown
- CSV
- XLSX/XLS/XLSM/XLSB cuando las librerías instaladas permiten su lectura

Proceso:

1. validar formato/tamaño;
2. SHA-256 del archivo;
3. copiar a `workspace/Conocimiento/<empresa>/<document_id>/`;
4. extraer texto y metadatos;
5. fragmentar con solapamiento;
6. generar embeddings locales;
7. guardar vectores;
8. guardar documento, versión y chunks en SQLite;
9. recuperar solo fragmentos relevantes.

Los IDs vectoriales se derivan del documento, ubicación y hash del texto. En una nueva versión, los fragmentos idénticos conservan el vector; solo los nuevos/cambiados requieren embedding y los obsoletos se eliminan.

### Archivos tabulares

Excel/CSV se indexan documentalmente solo con esquema y una muestra acotada para descubrir el dataset. Las cifras no se calculan leyendo fragmentos RAG. `StructuredDataService` abre el dataset completo y calcula con Pandas.

## 5. Por qué Qdrant

V8 selecciona Qdrant como opción preferente porque encaja mejor con crecimiento empresarial que FAISS/Chroma para este proyecto: persistencia local, filtros por metadata, buen mantenimiento, posibilidad de pasar de modo local a servicio independiente y mejor ruta hacia concurrencia/multiusuario.

Para no hacer frágil la instalación en Windows, existe `SQLiteVectorStore`, también persistente y con similitud coseno real. Si `qdrant-client` no está instalado, V8 usa automáticamente ese backend en lugar de simular RAG.

Una futura instalación con gran volumen/concurrencia puede mover Qdrant a servidor sin cambiar `MemoryManager`, `DocumentService` ni `ContextEngine`.

## 6. Embeddings locales

Modelo predeterminado: `nomic-embed-text` ejecutado por Ollama.

Configuración centralizada en `config/enterprise_ai.json`. Los documentos no se envían a APIs externas. Existen `OllamaEmbeddingProvider` y `LMStudioEmbeddingProvider`; Ollama/nomic-embed-text es el valor predeterminado. Para pruebas automatizadas existe un embedding hash determinista, pero no se usa como embedding de producción.

## 7. Datos estructurados

`StructuredDataService` registra datasets y detecta roles de columnas (fecha, producto, cliente, proveedor, cantidad, precio, ventas, costo, flete, etc.).

Regla esencial:

> El LLM interpreta. Python calcula.

Los filtros propuestos por el LLM se validan y no se aplican si el valor no aparece explícitamente en la petición. Esto conserva las garantías introducidas en V7.

## 8. Seguridad

- servicios locales en `127.0.0.1` por defecto;
- HMAC para tokens de usuario/empresa;
- filtrado de memoria/documentos/datasets por `company_id` y `user_id`;
- roles `user` y `admin`;
- sanitización de nombres;
- protección de rutas;
- límite de tamaño durante la subida;
- extensiones permitidas;
- auditoría de memoria/documentos/configuración;
- logs/metricas sin prompt completo;
- detección de prompt injection documental;
- los fragmentos recuperados se etiquetan como DATOS, nunca como instrucciones.

Para desplegar a varios usuarios por LAN, no se recomienda simplemente cambiar el host a `0.0.0.0`. Debe añadirse TLS/reverse proxy e integración de identidad corporativa. El aislamiento lógico V8 ya prepara esa evolución.

## 9. Observabilidad

`query_metrics` registra por consulta: duración total, memoria, RAG, datos estructurados, LLM, cantidad de memorias/chunks/fuentes, modelo/proveedor, longitud y hash del prompt, estado y tipo de error.

`audit_events` registra cambios administrativos sin volcar automáticamente contenido confidencial completo.

## 10. Persistencia y respaldo

Respaldar, con servicios detenidos:

- `data/enterprise/`
- `workspace/Conocimiento/`
- `config/enterprise_ai.json`
- `config/enterprise.secret` (archivo sensible)

No publicar ni compartir `enterprise.secret` ni `local-user.token`.

## 11. Fine-tuning

No se modifica ningún peso del modelo por conversaciones. El conocimiento cotidiano se implementa con memoria, RAG, datasets y herramientas. Fine-tuning queda como módulo futuro independiente.
