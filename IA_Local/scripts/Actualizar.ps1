. "$PSScriptRoot\Comun.ps1"

if (-not (Test-PythonExecutable $Python)) {
    Write-Host "No existe una instalacion valida. Ejecuta INSTALAR_Y_ABRIR.bat para repararla."
    exit 1
}

& "$PSScriptRoot\Detener.ps1"

Write-Host ""
Write-Host "Actualizando componentes..."
if (Test-Path $Requirements) {
    & $Python -m pip install --upgrade -r $Requirements
} else {
    & $Python -m pip install --upgrade open-webui open-terminal pandas openpyxl xlrd pyxlsb xlsxwriter matplotlib reportlab pypdf pymupdf python-docx tabulate fastapi uvicorn python-multipart requests
}
if ($LASTEXITCODE -ne 0) { throw "La actualizacion de paquetes Python fallo." }

Write-Host "Intentando actualizar qdrant-client (opcional)..."
& $Python -m pip install --upgrade qdrant-client
if ($LASTEXITCODE -ne 0) { Write-Host "Qdrant no disponible; se conservara fallback SQLite." -ForegroundColor Yellow }

Write-Host ""
Write-Host "Actualizando modelo qwen3:4b-instruct..."
Start-OllamaIfNeeded
& ollama pull qwen3:4b-instruct
Write-Host "Actualizando embeddings nomic-embed-text..."
& ollama pull nomic-embed-text
$env:IA_LOCAL_ROOT = $Root
& $Python "$PSScriptRoot\bootstrap_enterprise.py" --root $Root

Write-Host ""
Write-Host "Actualizacion terminada."
& "$PSScriptRoot\Iniciar.ps1"
