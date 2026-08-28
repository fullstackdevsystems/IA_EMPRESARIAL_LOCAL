# Guía de instalación y pruebas — V8

## Instalación en Windows

Extraer el paquete para que exista exactamente:

```text
C:\IA_Local\
```

Abrir PowerShell como administrador si la política del equipo lo requiere:

```powershell
cd C:\IA_Local
.\INSTALAR_Y_ABRIR.bat
```

El instalador detecta/repara Python 3.11, crea `.venv`, instala dependencias, intenta instalar Qdrant, inicia Ollama y descarga:

```powershell
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

Luego inicializa SQLite, vector store y token local.

## Inicio diario

```powershell
cd C:\IA_Local
.\INICIAR_IA.bat
```

Interfaces:

- Open WebUI: `http://127.0.0.1:8080`
- Analizador Excel/CSV: `http://127.0.0.1:8090`
- Asistente V8: ejecutar `ABRIR_ASISTENTE.bat`
- Administración: ejecutar `ABRIR_ADMIN_MEMORIA_RAG.bat`

## Diagnóstico

```powershell
C:\IA_Local\DIAGNOSTICO.bat
```

Verificación de versión:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/version
```

Debe indicar versión `8.0` y motor `universal-profesional-memoria-rag`.

## Pruebas automatizadas

```powershell
C:\IA_Local\PROBAR_MEMORIA_RAG.bat
```

O directamente:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\run_enterprise_tests.py
```

## Probar memoria persistente

En el Asistente V8:

```text
Recuerda: la utilidad de una operación se calcula como venta - compra - flete.
```

Si el sistema lo guarda directamente por petición explícita, aparecerá en Administración > Memoria. Para una regla expresada sin "recuerda", puede quedar pendiente y se debe confirmar.

Cerrar V8, ejecutar `DETENER_IA.bat`, volver a iniciar y preguntar:

```text
¿Cómo calculamos la utilidad de una operación?
```

También se puede administrar por CLI:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-list
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-search "utilidad flete"
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-add "La utilidad se calcula venta menos compra menos flete" --category regla_negocio
```

Actualizar/confirmar/olvidar:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-update ID "Nueva regla" --category regla_negocio
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-confirm ID
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py mem-forget ID
```

## Probar RAG

Desde Administración > Conocimiento, cargar un PDF/DOCX/TXT/MD/CSV/XLSX y esperar que aparezca como indexado. Luego preguntar al Asistente por un dato específico del documento.

CLI equivalente:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py doc-index "C:\Documentos\Manual_Comercial.pdf"
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py doc-list
```

Para reindexar o eliminar:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py doc-reindex ID
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py doc-delete ID
```

Si se carga otra vez el mismo nombre con contenido cambiado, V8 calcula un nuevo hash, crea una nueva versión y sustituye los chunks activos. Si el hash es igual, no reindexa innecesariamente.

## Probar Excel con cálculo real

Primero analizar/cargar el Excel mediante el Analizador 8090. Esto registra el dataset. Después preguntar al Asistente:

```text
¿Cuánto vendimos de melaza durante 2025?
```

El resultado debe indicar como fuente el dataset y el cálculo `python/pandas`. El LLM no calcula el total leyendo fragmentos.

## Probar falta de evidencia

Preguntar por una cifra interna que no exista en memorias, documentos ni datasets:

```text
¿Cuánto compramos al proveedor X en 2022?
```

V8 debe responder que no dispone de datos internos suficientes, no inventar una cifra.

## Probar aislamiento

Crear tokens distintos:

```powershell
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py --company EmpresaA --user Rafael token-create --token-role admin --days 365
& C:\IA_Local\.venv\Scripts\python.exe C:\IA_Local\scripts\enterprise_cli.py --company EmpresaB --user UsuarioB token-create --token-role user --days 365
```

Los recursos de EmpresaA no deben aparecer en búsquedas de EmpresaB.

## Cambiar a LM Studio

Desde Administración > Configuración IA seleccionar `lmstudio`, indicar el identificador del modelo cargado en LM Studio y reiniciar V8. El endpoint OpenAI-compatible esperado por defecto es:

```text
http://127.0.0.1:1234/v1
```

Los embeddings son locales. Por defecto se usan con Ollama/nomic-embed-text; V8 también incluye `LMStudioEmbeddingProvider` para usar un modelo de embeddings servido por el endpoint OpenAI-compatible de LM Studio.

## Copia de seguridad

Detener servicios:

```powershell
C:\IA_Local\DETENER_IA.bat
```

Respaldar `C:\IA_Local\data\enterprise`, `C:\IA_Local\workspace\Conocimiento` y la configuración. Proteger especialmente `config\enterprise.secret`.
