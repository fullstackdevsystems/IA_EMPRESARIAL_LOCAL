$ErrorActionPreference = 'Stop'
$PatchRoot = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $PatchRoot '..')).Path
$Target = Join-Path $Root 'IA_Local'

if (-not (Test-Path $Target)) {
    throw "No se encontró IA_Local en $Root. Extraiga el contenido del ZIP directamente dentro de C:\IA_EMPRESARIAL_LOCAL\R10_2_PATCH."
}

$branch = (git -C $Root branch --show-current).Trim()
if ($branch -ne 'feature/r10-dashboard-intelligence') {
    throw "R10.2 debe aplicarse sobre feature/r10-dashboard-intelligence. Rama actual: $branch"
}

$version = (Get-Content (Join-Path $Target 'VERSION.txt') -Raw).Trim()
if ($version -ne '8.5.5-r10.1.1') {
    Write-Warning "Se esperaba 8.5.5-r10.1.1 antes de aplicar R10.2; versión detectada: $version"
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $Root "_backup_r10_2\$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null

$files = @(
    'IA_Local\VERSION.txt',
    'IA_Local\scripts\dashboard_dynamic.py',
    'IA_Local\scripts\enterprise_prompt_compiler.py',
    'IA_Local\scripts\prompt_execution_plan.py',
    'IA_Local\scripts\analizador_universal.py',
    'IA_Local\scripts\semantic_layer.py',
    'IA_Local\tests\test_bi_productivo.py'
)

foreach ($rel in $files) {
    $dst = Join-Path $Root $rel
    if (Test-Path $dst) {
        $bak = Join-Path $backup $rel
        New-Item -ItemType Directory -Path (Split-Path $bak -Parent) -Force | Out-Null
        Copy-Item $dst $bak -Force
    }
    $src = Join-Path $PatchRoot $rel
    if (-not (Test-Path $src)) { throw "Falta archivo del parche: $rel" }
    New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
    Copy-Item $src $dst -Force
}

Write-Host ''
Write-Host 'R10.2 aplicado correctamente.' -ForegroundColor Green
Write-Host 'Nuevo: capa semántica genérica auditable con confianza EXACT/STRONG/INFERRED/AMBIGUOUS/MISSING.'
Write-Host 'AMBIGUOUS nunca se usa para cálculos automáticos; se separan costo de flete y tarifa de flete.'
Write-Host "Backup: $backup"
Write-Host 'Versión objetivo: 8.5.5-r10.2'
