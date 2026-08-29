$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Source = Join-Path $PSScriptRoot 'files\IA_Local'
$Target = Join-Path $Root 'IA_Local'

if (-not (Test-Path (Join-Path $Target 'scripts\analizador_universal.py'))) {
    throw "No se encontro IA Empresarial Local en $Root. Extrae R9_7_PATCH dentro de C:\IA_EMPRESARIAL_LOCAL y vuelve a ejecutar."
}

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Root ("_backup_r9_7\" + $Stamp)
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

$Relative = @(
  'VERSION.txt',
  'scripts\dashboard_dynamic.py',
  'scripts\enterprise_prompt_compiler.py',
  'scripts\prompt_execution_plan.py',
  'scripts\analizador_universal.py',
  'tests\test_bi_productivo.py'
)
foreach ($Rel in $Relative) {
    $Dst = Join-Path $Target $Rel
    if (Test-Path $Dst) {
        $Bak = Join-Path $Backup $Rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Bak) | Out-Null
        Copy-Item $Dst $Bak -Force
    }
    $Src = Join-Path $Source $Rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dst) | Out-Null
    Copy-Item $Src $Dst -Force
}
Write-Host "R9.7 aplicado correctamente." -ForegroundColor Green
Write-Host "Backup: $Backup"
Write-Host "Version objetivo: 8.5.5-r9.7"
