# IA Empresarial Local — Guía de respaldo y recuperación

Versión del producto: 8.5.5
Documentación: R10.24E3

## Objetivo

Proteger configuración y estado persistente gobernado antes de mantenimiento, actualización, reparación, migración o desinstalación.

## Crear respaldo

Desde la carpeta instalada utiliza:

    .\OperarIA.ps1 -Action backup -BackupPath "C:\Respaldos\IA_Empresarial_Local_backup.zip"

El respaldo debe almacenarse fuera de la carpeta de instalación.

## Cuándo respaldar

- Antes de una actualización.
- Antes de una reparación.
- Antes de eliminar datos empresariales.
- Antes de una migración.
- Antes de cambios operativos importantes.

## Restaurar

Utiliza un respaldo gobernado conocido y autorizado:

    .\OperarIA.ps1 -Action restore -RestorePath "C:\Respaldos\IA_Empresarial_Local_backup.zip"

## Verificación posterior

Ejecuta:

    .\OperarIA.ps1 -Action validate
    .\OperarIA.ps1 -Action status

Después verifica usuarios, empresa, configuración, datos disponibles y reportes persistentes.

## Desinstalación conservando datos

La desinstalación normal debe conservar los datos empresariales salvo que se solicite explícitamente una eliminación total.

Herramienta:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DesinstalarIA.ps1 -InstallPath "C:\RUTA\IA_Empresarial_Local"

## Eliminación total

Debe existir confirmación explícita y un respaldo válido fuera de la instalación.

No elimines manualmente identidad, tenants, configuración, conocimiento, reportes o bases persistentes.

## Reglas

- No restaures ZIP arbitrarios.
- No utilices respaldos incompletos.
- No modifiques el manifiesto del respaldo.
- No mezcles manualmente información persistente de empresas diferentes.
- Valida siempre la instalación después de restaurar.
