$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Target = Join-Path $Root "IA_Local"
if (-not (Test-Path $Target)) { throw "No se encontro IA_Local en $Root. Extrae R9_8_PATCH dentro de C:\IA_EMPRESARIAL_LOCAL." }
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $Root "_backup_r9_8\$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
$Files = @(
 "scripts\dashboard_dynamic.py",
 "scripts\prompt_execution_plan.py",
 "scripts\enterprise_prompt_compiler.py",
 "scripts\analizador_universal.py",
 "tests\test_bi_productivo.py",
 "VERSION.txt"
)
foreach ($rel in $Files) {
  $dst = Join-Path $Target $rel
  if (Test-Path $dst) {
    $bak = Join-Path $Backup $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $bak -Parent) | Out-Null
    Copy-Item $dst $bak -Force
  }
  $src = Join-Path $PSScriptRoot ("files\IA_Local\" + $rel)
  New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
  Copy-Item $src $dst -Force
}
Write-Host ""
Write-Host "R9.8 aplicado correctamente." -ForegroundColor Green
Write-Host "Nuevo: exportacion XLSX real de los datos filtrados, totalmente offline." -ForegroundColor Cyan
Write-Host "Se conserva R9.7.1: opcion Todos en filtros y multiseleccion." -ForegroundColor Cyan
Write-Host "Backup: $Backup"
Write-Host "Version objetivo: 8.5.5-r9.8"
