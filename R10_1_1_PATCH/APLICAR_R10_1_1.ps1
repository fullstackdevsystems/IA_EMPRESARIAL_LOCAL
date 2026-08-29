$ErrorActionPreference = 'Stop'
$PatchRoot = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $PatchRoot '..')).Path
$Target = Join-Path $Root 'IA_Local'
if (-not (Test-Path $Target)) { throw "No se encontró IA_Local en $Root" }

$branch = (git -C $Root branch --show-current 2>$null)
if ($LASTEXITCODE -eq 0 -and $branch -eq 'main') {
    throw "R10.1.1 no debe aplicarse directamente sobre main. Cree/cambie primero a feature/r10-dashboard-intelligence."
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Root "_backup_r10_1_1\$stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

$files = @(
  'VERSION.txt',
  'scripts\dashboard_dynamic.py',
  'scripts\analizador_universal.py',
  'scripts\enterprise_prompt_compiler.py',
  'scripts\prompt_execution_plan.py',
  'tests\test_bi_productivo.py'
)
foreach ($rel in $files) {
    $dst = Join-Path $Target $rel
    if (Test-Path $dst) {
        $bak = Join-Path $Backup $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $bak -Parent) | Out-Null
        Copy-Item $dst $bak -Force
    }
    $src = Join-Path (Join-Path $PatchRoot 'IA_Local') $rel
    if (-not (Test-Path $src)) { throw "Falta archivo del parche: $src" }
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item $src $dst -Force
}

Write-Host ''
Write-Host 'R10.1.1 aplicado correctamente.' -ForegroundColor Green
Write-Host 'Nuevo: portada ejecutiva con 6 KPIs, filtros esenciales, cobertura por valor y navegación avanzada ordenada.'
Write-Host 'Las alertas técnicas permanecen cerradas al inicio; filtros y KPIs adicionales se muestran bajo demanda.'
Write-Host "Backup: $Backup"
Write-Host 'Versión objetivo: 8.5.5-r10.1.1'
