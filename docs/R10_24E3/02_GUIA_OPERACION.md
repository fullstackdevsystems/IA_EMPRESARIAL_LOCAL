# IA Empresarial Local — Guía de operación

Versión del producto: 8.5.5
Documentación: R10.24E3

## Objetivo

Administrar el ciclo de vida de IA Empresarial Local sin modificar código fuente.

## Herramienta operativa

Desde la carpeta instalada utiliza:

    .\OperarIA.ps1

## Iniciar

    .\OperarIA.ps1 -Action start

## Detener

    .\OperarIA.ps1 -Action stop

## Reiniciar

    .\OperarIA.ps1 -Action restart

## Consultar estado

    .\OperarIA.ps1 -Action status

## Salud

    .\OperarIA.ps1 -Action health

## Validar instalación

    .\OperarIA.ps1 -Action validate

## Diagnóstico

    .\OperarIA.ps1 -Action diagnostics

## Paquete de diagnóstico

    .\OperarIA.ps1 -Action diagnostic-bundle

Los paquetes de diagnóstico deben estar sanitizados y no deben utilizarse para compartir contraseñas, tokens o secretos.

## Live y readiness

El servicio diferencia:

- live: confirma que el servicio está ejecutándose.
- ready: confirma además las dependencias consideradas por el chequeo de readiness.

Si el proveedor de IA no está configurado, el servicio puede estar live y mostrar readiness degradado.

## Puertos

Antes de cambiar o liberar un puerto identifica siempre el proceso propietario, su ruta y su línea de comando.

Nunca termines un proceso desconocido sólo para liberar un puerto.

## Reglas de operación

- Utiliza OperarIA.ps1 en lugar de iniciar manualmente analizador_universal.py.
- Genera respaldo antes de cambios importantes.
- No modifiques estado persistente mientras el producto está en ejecución.
- Conserva logs y diagnósticos únicamente el tiempo necesario para soporte.
