param([string]$Root = "")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) {
  if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") { $Root = "C:\IA_EMPRESARIAL_LOCAL\IA_Local" }
  elseif (Test-Path "C:\IA_Local") { $Root = "C:\IA_Local" }
  else { throw "No se encontro IA_Local. Use -Root." }
}
$Root = (Resolve-Path $Root).Path
$VersionFile = Join-Path $Root "VERSION.txt"
$current = if(Test-Path $VersionFile){ (Get-Content $VersionFile -Raw).Trim() } else { "" }
if ($current -notmatch 'r10\.(10|11)') {
  Write-Host "R10.10 no detectado. Aplique primero el paquete prerequisite_R10_10.zip incluido." -ForegroundColor Yellow
  throw "R10.11 requiere base R10.10"
}
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $Root "updates\pre_r10_11_performance_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$targets = @("VERSION.txt","scripts\enterprise_ai\structured_data.py","scripts\enterprise_ai\api.py")
foreach($rel in $targets){ $p=Join-Path $Root $rel; if(Test-Path $p){ $dst=Join-Path $backup $rel; New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent)|Out-Null; Copy-Item $p $dst -Force } }
Write-Host "Backup: $backup"
& python (Join-Path $Here "apply_r10_11.py") $Root
if($LASTEXITCODE -ne 0){ throw "Fallo apply_r10_11.py" }
& python (Join-Path $Here "test_r10_11_installed.py") $Root
if($LASTEXITCODE -ne 0){ throw "Fallo test instalado R10.11" }
Write-Host ""
Write-Host "R10.11 OPTIMIZACION DE ARCHIVOS GRANDES APLICADA CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version: 8.5.5-r10.11-large-data"
