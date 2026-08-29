# R10.10 — Administración Empresarial Unificada

## Objetivo
Unificar en `/admin` la operación de Memoria, Documentos/RAG, Diccionario semántico, Reglas empresariales, bindings analíticos, Feedback, Trazabilidad, Historial y Auditoría.

## Principios
- No duplicar motores ya existentes.
- Lectura con identidad autenticada y aislamiento por empresa/usuario.
- Validar/rechazar/obsoletar requiere rol admin.
- Las propuestas no se vuelven verdad automáticamente.
- Conflictos de reglas/semántica deben confirmarse explícitamente.

## Archivos
- NUEVO `enterprise_ai/admin_console.py`
- MODIFICADO `enterprise_ai/api.py`
- MODIFICADO `VERSION.txt`

## Pruebas
- `test_r10_10_patch.py`
- `test_r10_10_ui.py`
- `test_r10_10_installed.py` se ejecuta en la instalación real.

## Versión
`8.5.5-r10.10-unified-admin`
