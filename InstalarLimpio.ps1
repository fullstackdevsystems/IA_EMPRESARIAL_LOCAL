param([string]$InstallPath,[switch]$NonInteractive,[string]$TenantId,[string]$TenantName,[string]$AdminUsername,[switch]$SkipSqlCheck,[switch]$SkipAiCheck,[switch]$ValidateOnly)
$ErrorActionPreference = "Stop"
& (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'InstallerR1020C1.ps1') @PSBoundParameters
exit $LASTEXITCODE
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $PackageRoot "IA_Local"
$Destination = "C:\IA_Local"
$ManifestPath = Join-Path $PackageRoot "MANIFEST_SHA256.json"

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "ERROR: ejecuta INSTALAR_IA_EMPRESARIAL_LOCAL.bat como Administrador." -ForegroundColor Red
        exit 2
    }
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " IA EMPRESARIAL LOCAL V8.5.5 R7" -ForegroundColor Cyan
Write-Host " INSTALACION COMPLETA Y LIMPIA" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""
Assert-Admin

if (-not (Test-Path $Source)) { throw "Falta la carpeta IA_Local dentro del paquete." }
if (-not (Test-Path $ManifestPath)) { throw "Falta MANIFEST_SHA256.json." }

Write-Host "Verificando integridad del paquete..."
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$count = 0
foreach ($entry in $manifest.files) {
    $relative = [string]$entry.path
    $full = Join-Path $PackageRoot ($relative.Replace('/', '\\'))
    if (-not (Test-Path $full -PathType Leaf)) { throw "Archivo faltante: $relative" }
    $hash = (Get-FileHash -Path $full -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$entry.sha256).ToLowerInvariant()) { throw "SHA-256 invalido: $relative" }
    $count++
}
Write-Host "Integridad: OK ($count archivos)." -ForegroundColor Green

if (Test-Path $Destination) {
    Write-Host ""
    Write-Host "ERROR: ya existe C:\IA_Local." -ForegroundColor Red
    Write-Host "Este instalador limpio NO sobrescribe instalaciones existentes para proteger memoria, documentos, tokens y reportes." -ForegroundColor Yellow
    Write-Host "Si deseas una instalacion realmente nueva, respalda/renombra primero la carpeta existente o utiliza el actualizador acumulativo." -ForegroundColor Yellow
    exit 3
}

Write-Host "Copiando base limpia a C:\IA_Local..."
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force

Write-Host "Base copiada. Iniciando instalacion de dependencias y modelos..." -ForegroundColor Green
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Destination "scripts\Instalar.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: la instalacion no termino correctamente." -ForegroundColor Red
    Write-Host "La carpeta C:\IA_Local se conserva para diagnostico. No contiene datos previos del usuario." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host " INSTALACION COMPLETA FINALIZADA" -ForegroundColor Green
Write-Host " Chat:       http://127.0.0.1:8080" -ForegroundColor Green
Write-Host " Analizador: http://127.0.0.1:8090" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
