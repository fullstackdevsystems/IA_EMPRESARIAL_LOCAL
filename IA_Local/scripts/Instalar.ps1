. "$PSScriptRoot\Comun.ps1"
Ensure-Folders

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "       IA EMPRESARIAL LOCAL V8.5.5 R7 - INSTALACION COMPLETA" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Destino fijo: C:\IA_Local"
Write-Host "Modelo por defecto: qwen3:4b-instruct"
Write-Host "Incluye IA local, memoria persistente, RAG/Qdrant, analizador BI, Dashboard Enterprise, PDF y Excel."
Write-Host ""

if ((Split-Path -Parent $PSScriptRoot) -ne $Root) {
    Write-Host "Este paquete debe estar en C:\IA_Local." -ForegroundColor Yellow
    Write-Host "Ruta actual: $(Split-Path -Parent $PSScriptRoot)"
    Write-Host ""
    Write-Host "Extrae la carpeta IA_Local directamente dentro de C:\ y vuelve a ejecutar." -ForegroundColor Yellow
    exit 2
}

# Detiene servicios de versiones anteriores para evitar que V2/V3/V4/V5 sigan atendiendo en los puertos 8080/8090.
try { & "$PSScriptRoot\Detener.ps1" } catch {}
Start-Sleep -Seconds 1

# Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama no fue detectado." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Intentando instalar Ollama con winget..."
        try {
            & winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
        } catch {
            Write-Host "No se pudo instalar Ollama automaticamente." -ForegroundColor Red
        }
    }

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "Ollama sigue sin estar disponible. Instala Ollama y vuelve a ejecutar este archivo." -ForegroundColor Red
        exit 3
    }
}
Write-Host "Ollama detectado." -ForegroundColor Green

# Python 3.11
$Py311 = Find-Python311
if (-not $Py311) {
    Write-Host "Python 3.11 no fue detectado." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Instalando Python 3.11..."
        try {
            & winget install --id Python.Python.3.11 -e --scope user --accept-package-agreements --accept-source-agreements
        } catch {
            & winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
        }
        Start-Sleep -Seconds 4
        $Py311 = Find-Python311
    }
}
if (-not $Py311) {
    Write-Host "No fue posible localizar Python 3.11." -ForegroundColor Red
    Write-Host "Instala Python 3.11 x64 y vuelve a ejecutar INSTALAR_Y_ABRIR.bat."
    exit 4
}
Write-Host "Python 3.11: $Py311" -ForegroundColor Green

# Repara automaticamente entornos virtuales copiados desde otra PC/usuario.
if (Test-Path $Venv) {
    if (-not (Test-PythonExecutable $Python)) {
        Write-Host ""
        Write-Host "El entorno virtual existente apunta a otro Python/usuario o esta danado." -ForegroundColor Yellow
        Write-Host "Se reconstruira C:\IA_Local\.venv automaticamente..."
        Remove-Item $Venv -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $Python)) {
    Write-Host ""
    Write-Host "Creando entorno virtual local..."
    & $Py311 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}
if (-not (Test-PythonExecutable $Python)) {
    throw "El Python del entorno virtual no funciona."
}

Write-Host ""
Write-Host "Actualizando pip..."
& $Python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "Fallo al actualizar pip." }

Write-Host ""
Write-Host "Instalando Open WebUI, Open Terminal, analizador y dependencias V8..."
if (Test-Path $Requirements) {
    & $Python -m pip install --upgrade -r $Requirements
} else {
    & $Python -m pip install --upgrade open-webui open-terminal pandas openpyxl xlrd pyxlsb xlsxwriter matplotlib reportlab pypdf pymupdf python-docx tabulate fastapi uvicorn python-multipart requests
}
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de paquetes Python." }

Write-Host ""
Write-Host "Intentando instalar Qdrant local (opcional; existe fallback SQLite persistente)..." -ForegroundColor Cyan
& $Python -m pip install --upgrade qdrant-client
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo instalar qdrant-client. V8 utilizara SQLiteVectorStore hasta que pueda instalarse Qdrant." -ForegroundColor Yellow
}

Write-TerminalConfig

Write-Host ""
Write-Host "Comprobando Ollama..."
Start-OllamaIfNeeded

Write-Host ""
Write-Host "Descargando/actualizando modelo qwen3:4b-instruct (~2.5 GB). Esto puede tardar..." -ForegroundColor Cyan
& ollama pull qwen3:4b-instruct
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo descargar qwen3:4b-instruct. Podras reintentarlo despues con: ollama pull qwen3:4b-instruct" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Descargando modelo local de embeddings nomic-embed-text..." -ForegroundColor Cyan
& ollama pull nomic-embed-text
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo descargar nomic-embed-text. Memoria semantica/RAG requeriran reintentar: ollama pull nomic-embed-text" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Inicializando base persistente, seguridad y token local V8..." -ForegroundColor Cyan
$env:IA_LOCAL_ROOT = $Root
& $Python "$PSScriptRoot\bootstrap_enterprise.py" --root $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo la inicializacion de memoria/RAG V8." }

Write-Host ""
Write-Host "Ejecutando gate BI V8.5.5..." -ForegroundColor Cyan
$env:PYTHONPATH = (Join-Path $Root "scripts")
& $Python (Join-Path $Root "tests\test_bi_productivo.py")
if ($LASTEXITCODE -ne 0) { throw "Fallo el gate BI V8.5.5." }

Write-Host ""
Write-Host "Ejecutando gate Enterprise/Memoria/RAG/Streaming..." -ForegroundColor Cyan
& $Python (Join-Path $Root "scripts\run_enterprise_tests.py")
if ($LASTEXITCODE -ne 0) { throw "Fallo el gate Enterprise/Memoria/RAG/Streaming." }

Write-Host ""
Write-Host "Instalacion V8.5.5 R7 terminada y validada." -ForegroundColor Green
Write-Host "Iniciando servicios..."
& "$PSScriptRoot\Iniciar.ps1"
