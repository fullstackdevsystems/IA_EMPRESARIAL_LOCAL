# IA Empresarial Local — R10.24A Unified Product Experience

## Estado

Diseño contractual de UX para R10.24A.

Base técnica certificada:

- R10.23 RC4
- Commit base: 3a9227fdf2da3c6215db206ca020348728365f54
- Rama de trabajo: feature/r10.24-professional-product-experience

Este documento define la experiencia comercial objetivo antes de modificar
el comportamiento productivo existente.

---

# 1. Objetivo

IA Empresarial Local debe poder ser instalada, configurada y utilizada por
una persona sin conocimientos de:

- programación
- Python
- PowerShell
- SQL técnico
- Ollama
- proveedores de IA
- modelos LLM
- RAG
- tenants
- APIs
- puertos
- archivos JSON
- SHA-256

La complejidad técnica debe permanecer disponible para soporte y administración
avanzada, pero no debe formar parte de la experiencia diaria normal.

---

# 2. Principio de producto

La interfaz debe organizarse alrededor de lo que la persona quiere hacer,
no alrededor de los componentes internos de la plataforma.

La pregunta principal del producto será:

> ¿Qué quieres hacer hoy?

---

# 3. Navegación principal oficial

## Usuario normal

### Inicio
Ruta objetivo: /app

Propósito:
Vista principal y punto de entrada único al producto.

### Asistente
Ruta objetivo: /assistan

Propósito:
Preguntar en lenguaje natural sobre información empresarial,
documentos, conocimiento y datos conectados.

### Analizar
Ruta objetivo: /analyze

Propósito:
Subir Excel, CSV u otra fuente soportada y generar análisis,
dashboard, PDF y Excel.

### Datos
Ruta objetivo: /data

Propósito:
Ver las fuentes de información disponibles para el usuario.

No debe mostrar configuraciones técnicas.

### Reportes
Ruta objetivo: /reports

Propósito:
Consultar dashboards, análisis y entregables previamente generados.

---

# 4. Navegación administrativa

Configuración sólo será visible para usuarios con permisos suficientes.

Ruta objetivo:

/settings

Secciones:

## Mi empresa

- nombre comercial
- logo
- color principal
- tema claro u oscuro
- idioma
- zona horaria
- giro o perfil empresarial
- moneda
- país

Los identificadores internos no deben mostrarse en modo básico.

## Usuarios

La interfaz utilizará nombres comprensibles:

- Administrador
- Analista
- Consulta

Los roles internos SYSTEM_ADMIN, TENANT_ADMIN, ANALYST y VIEWER
permanecerán en backend.

## Datos y conexiones

Configuración guiada de:

- SQL Server
- archivos
- documentos
- otras fuentes futuras

Flujo SQL básico:

1. Servidor
2. Base de datos
3. Tipo de acceso
4. Probar conexión
5. Descubrir información
6. Seleccionar tablas
7. Guardar

## Inteligencia artificial

Modo básico:

1. Buscar IA disponible
2. Mostrar modelos encontrados
3. Elegir modelo
4. Probar
5. Guardar

La URL, timeout, context window y parámetros técnicos sólo aparecerán
en Configuración avanzada.

## Apariencia

- logo
- nombre
- color
- tema
- vista previa

## Seguridad y recuperación

- respaldo
- restauración
- sesiones
- estado general

## Avanzado

Aquí permanecerán las funciones técnicas necesarias para soporte:

- memoria
- RAG
- diccionario semántico
- reglas empresariales
- reglas analíticas
- feedback
- trazabilidad
- historial
- auditoría
- parámetros técnicos de IA
- parámetros avanzados SQL

---

# 5. Términos prohibidos en UX básica

Los siguientes términos no deben mostrarse al usuario normal salvo que
se encuentre en un área explícitamente avanzada:

- tenan
- RAG
- provider
- renderer
- SHA-256
- ODBC
- context window
- timeou
- SYSTEM_ADMIN
- TENANT_ADMIN
- ANALYS
- VIEWER
- WINDOWS_INTEGRATED
- SQL_AUTH
- localhos
- 127.0.0.1
- puerto
- JSON
- Python
- Pandas
- Qwen
- Ollama

Excepción:

El nombre del motor/modelo puede mostrarse en Configuración de IA cuando
ayude al administrador a elegirlo.

---

# 6. Estrategia de transición

R10.24A no romperá las rutas productivas existentes.

Durante la transición:

- / continuará sirviendo la experiencia RC4 existente.
- /assistant continuará funcionando.
- /admin continuará disponible como consola administrativa legacy.
- /app será la nueva experiencia unificada.
- Open WebUI continuará existiendo internamente mientras siga siendo necesario.
- El usuario final no necesitará abrir directamente el puerto 8080.

Cuando /app supere aceptación comercial:

- / será promovido a entrada principal.
- /admin quedará como compatibilidad o administración avanzada.
- enlaces técnicos serán retirados de la navegación normal.

---

# 7. Primera pantalla a construir: Inicio

Ruta:

/app

## Encabezado

Debe mostrar:

- logo de la empresa si existe
- nombre comercial
- nombre del usuario
- acceso a perfil
- cerrar sesión

No debe mostrar:

- versión interna
- release
- motor
- puerto
- rutas de archivos
- información de infraestructura

## Mensaje principal

Ejemplo:

Hola, Rafael.

¿Qué quieres hacer hoy?

El nombre se obtiene de la identidad autenticada.

## Acciones principales

### Preguntar a mi empresa

Descripción:

Haz preguntas sobre tus datos, documentos y conocimiento empresarial.

Destino:

/assistan

### Analizar un archivo

Descripción:

Carga un Excel o CSV y genera automáticamente análisis y reportes.

Destino:

/analyze

### Consultar mis datos

Descripción:

Explora la información conectada de tu empresa.

Destino:

/data

### Ver reportes

Descripción:

Consulta dashboards, PDF, Excel y análisis anteriores.

Destino:

/reports

### Conectar información

Sólo visible cuando el usuario puede configurar fuentes.

Descripción:

Conecta SQL Server u otras fuentes de información.

Destino:

/settings?section=data

---

# 8. Estado del sistema en Inicio

La página Inicio podrá mostrar un resumen amigable.

Estados de ejemplo:

Empresa lista
Datos conectados
IA disponible
Sistema listo

No debe presentar directamente:

READY
CONFIGURED
TESTED
BLOCKED
DEGRADED

Mapeo visual:

READY -> Listo
TESTED -> Verificado
CONFIGURED -> Configurado
BLOCKED -> Requiere configuración
DEGRADED -> Requiere atención

El backend conservará sus estados canónicos.

---

# 9. Configuración inicial comercial

Primer uso esperado:

Paso 1 — Tu empresa
Paso 2 — Tu administrador
Paso 3 — Identidad visual
Paso 4 — Tus datos
Paso 5 — Inteligencia artificial
Paso 6 — Verificación
Paso 7 — Entrar

Una instalación nueva debe poder completar este flujo sin PowerShell.

---

# 10. Perfil empresarial universal

La plataforma no tendrá versiones separadas por giro.

Se utilizará un perfil empresarial configurable.

Ejemplos de giros:

- comercial
- distribución
- agropecuario
- transporte
- manufactura
- construcción
- servicios
- salud
- educación
- restaurante
- otro

El perfil sólo adapta:

- terminología
- ejemplos
- accesos rápidos
- métricas sugeridas
- plantillas

Nunca debe limitar el motor universal.

---

# 11. Reglas de interfaz

Toda acción importante debe tener lenguaje humano.

Incorrecto:

AI_PROVIDER_UNAVAILABLE

Correcto:

No pudimos conectarnos con la inteligencia artificial.

Incorrecto:

SQL_AUTH_FAILED

Correcto:

No fue posible iniciar sesión en SQL Server.
Revisa el usuario y la contraseña.

Incorrecto:

CONFIGURATION_REQUIRED

Correcto:

Falta completar la configuración de tu empresa.

Los códigos técnicos pueden conservarse en logs y diagnóstico.

---

# 12. Progressive disclosure

La plataforma tendrá tres niveles.

## Nivel 1 — Usuario

Sólo acciones empresariales.

## Nivel 2 — Administrador

Configuración guiada.

## Nivel 3 — Avanzado / Soporte

Configuración técnica completa y diagnóstico.

---

# 13. Diseño visual

La nueva interfaz debe reutilizar el sistema visual existente:

- professional-ligh
- professional-dark
- branding por empresa
- accent color
- logo
- tokens compartidos

Objetivo visual:

producto SaaS empresarial moderno aunque se ejecute localmente.

Debe funcionar correctamente en:

- escritorio
- laptop
- table

---

# 14. Criterios R10.24A

R10.24A no será aceptado hasta demostrar:

- navegación unificada
- Inicio profesional
- autenticación reutilizada
- branding por empresa
- responsive
- permisos respetados
- cero regresiones sobre RC4
- rutas legacy todavía operativas
- ninguna configuración técnica obligatoria para usar Inicio
- ninguna dependencia de Interne
- ningún requisito de Node.js en la computadora cliente

---

# 15. Primer incremento

El primer incremento de código será:

R10.24A1 — Unified Home Shell

Alcance:

- crear /app
- reutilizar autenticación existente
- mostrar identidad de usuario
- mostrar branding de empresa
- navegación principal
- tarjetas de acciones
- readiness amigable
- responsive
- sin eliminar rutas RC4
- sin cambiar todavía los motores de análisis

Este incremento debe poder probarse de forma aislada antes de modificar
Analizador, Asistente o Administración.
