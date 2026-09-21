# IA Empresarial Local — Guía de instalación

Versión del producto: 8.5.5
Documentación: R10.24E3

## Objetivo

Instalar IA Empresarial Local en un equipo Windows soportado sin editar código fuente ni archivos internos.

## Requisitos

- Windows 10/11 x64.
- Permisos de administrador durante la instalación.
- Espacio suficiente para producto, dependencias, modelos y datos empresariales.
- Conexión a Internet cuando sea necesario obtener dependencias o modelos que aún no estén disponibles localmente.
- Paquete completo de distribución de IA Empresarial Local.

## Antes de instalar

1. Extrae todo el paquete en una carpeta temporal.
2. No ejecutes archivos directamente desde el ZIP.
3. Conserva juntos MANIFEST_SHA256.json, RELEASE_METADATA.json, los instaladores y la carpeta IA_Local.
4. No copies una carpeta .venv desde otra computadora.
5. No agregues contraseñas, tokens o datos empresariales al paquete.

## Instalación

Utiliza el punto de entrada:

    INSTALAR_IA_EMPRESARIAL_LOCAL.bat

El proceso de instalación valida la integridad del paquete mediante SHA-256 y prepara el entorno administrado del producto.

También existen para soporte:

    InstalarLimpio.ps1
    InstallerR1020C1.ps1
    ValidarInstalador.ps1

## Primera configuración

Después de instalar:

1. Abre IA Empresarial Local.
2. Completa la configuración inicial.
3. Define la empresa y el administrador inicial.
4. Configura las fuentes de datos necesarias.
5. Configura el proveedor de IA cuando las funciones de IA generativa lo requieran.

El producto puede mantener disponibles funciones determinísticas y empresariales aunque el proveedor de IA todavía no esté configurado.

## Verificación

Soporte puede utilizar:

    .\OperarIA.ps1 -Action status
    .\OperarIA.ps1 -Action validate
    .\OperarIA.ps1 -Action health

La experiencia principal del usuario comienza en:

    /app

## Seguridad

- No edites MANIFEST_SHA256.json para ocultar diferencias.
- No copies secretos desde otra instalación.
- No mezcles manualmente datos persistentes de empresas distintas.
- Utiliza respaldo y restauración para mover estado gobernado.

## Resultado esperado

La instalación finaliza validada y lista para configurar empresa, usuarios, datos y proveedor de IA según corresponda.
