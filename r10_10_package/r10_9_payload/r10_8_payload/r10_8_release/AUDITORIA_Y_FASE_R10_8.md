# R10.8 — Feedback y Aprendizaje Controlado

## Objetivo
Convertir feedback del usuario en evidencia persistente y propuestas gobernadas, sin aprender automáticamente información no confirmada.

## Implementado
- `feedback_events` y `feedback_history` persistentes.
- Feedback `CORRECTO` sin aprendizaje automático.
- `REQUIERE_CORRECCION` crea propuesta `rule`, `semantic` o `memory`.
- Regla/definición queda `PROPUESTO`; memoria queda `pending`.
- Validación y rechazo explícitos.
- Procedencia `source_ref=feedback:<id>`.
- Aislamiento por empresa y usuario.
- Endpoints autenticados de feedback.
- Controles en el Asistente: Correcto, Requiere corrección, Guardar/Validar, Rechazar.

## Regla crítica
Una corrección nunca se convierte directamente en conocimiento `VALIDADO`.

## Compatibilidad
Migración aditiva. No elimina memoria, RAG, reglas, diccionario ni dashboards existentes.
