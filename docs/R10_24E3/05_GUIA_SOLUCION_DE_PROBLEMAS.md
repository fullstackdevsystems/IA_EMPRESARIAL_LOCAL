# IA Empresarial Local — Guía de solución de problemas

Versión del producto: 8.5.5
Documentación: R10.24E3

## Regla principal

No elimines archivos, no mates procesos desconocidos y no edites configuración interna antes de identificar la causa.

## La aplicación no abre

Ejecuta:

    .\OperarIA.ps1 -Action status
    .\OperarIA.ps1 -Action start
    .\OperarIA.ps1 -Action health

Si continúa el problema:

    .\OperarIA.ps1 -Action diagnostics

## Live funciona pero readiness está degradado

El producto diferencia liveness y readiness.

Cuando el proveedor de IA está NOT_CONFIGURED, readiness puede responder HTTP 503 con llm=false y database=true.

Esto no implica automáticamente que instalación, reportes, archivos o funciones determinísticas estén dañados.

Si se requieren funciones dependientes del LLM, configura un proveedor de IA compatible.

## Puerto ocupado

Identifica primero el proceso propietario del puerto, su ruta y su línea de comando.

No termines procesos desconocidos.

## No puedo iniciar sesión

- Verifica el usuario.
- Confirma que el usuario esté activo.
- No reutilices contraseñas de otra instalación.
- Solicita un cambio de contraseña al administrador cuando corresponda.

No edites directamente el almacén de identidad.

## Acceso denegado

Puede deberse al rol o al alcance de empresa.

Solicita revisión de permisos; no utilices credenciales de otra persona.

## SQL Server no conecta

- Verifica disponibilidad del servidor SQL Server.
- Revisa el método de autenticación.
- Utiliza únicamente credenciales autorizadas.
- Ejecuta diagnostics.

No escribas contraseñas en scripts o documentación de soporte.

## Un reporte no aparece

- Confirma que el análisis terminó.
- Abre /reports.
- Verifica los permisos del usuario.
- Ejecuta validate si sospechas un problema de instalación.

## Un reporte no descarga

- Reintenta desde /reports.
- Verifica que el servicio esté live.
- Ejecuta diagnostics.
- No reconstruyas manualmente el registro de entregables.

## Falta información después de reiniciar

No reinstales inmediatamente.

Ejecuta:

    .\OperarIA.ps1 -Action status
    .\OperarIA.ps1 -Action validate
    .\OperarIA.ps1 -Action diagnostics

Si existe un respaldo gobernado válido, utiliza el procedimiento oficial de restore.

## Evidencia para soporte

Genera un paquete sanitizado:

    .\OperarIA.ps1 -Action diagnostic-bundle

No compartas contraseñas, tokens, secretos ni información empresarial por canales no autorizados.

## Logs

Los Logs son para diagnóstico técnico.

Revisa su contenido antes de compartirlos y conserva únicamente la evidencia necesaria.
