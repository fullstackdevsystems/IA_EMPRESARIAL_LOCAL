$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path (Join-Path $Root 'IA_Local\scripts\dashboard_dynamic.py'))) {
    throw "No se encontro IA Empresarial Local en $Root. Extrae R9_6_PATCH dentro de C:\IA_EMPRESARIAL_LOCAL y vuelve a ejecutar."
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $Root "_backup_r9_6\$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
 'IA_Local\scripts\dashboard_dynamic.py',
 'IA_Local\scripts\enterprise_prompt_compiler.py',
 'IA_Local\scripts\analizador_universal.py',
 'IA_Local\tests\test_bi_productivo.py',
 'IA_Local\VERSION.txt'
)
foreach ($rel in $files) {
    $dst = Join-Path $Root $rel
    if (Test-Path $dst) {
        $bak = Join-Path $backup $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $bak -Parent) | Out-Null
        Copy-Item $dst $bak -Force
    }
    $src = Join-Path $PSScriptRoot (Join-Path 'files' $rel)
    if (-not (Test-Path $src)) { throw "Falta archivo del parche: $src" }
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item $src $dst -Force
}
Write-Host "R9.6 aplicado correctamente." -ForegroundColor Green
Write-Host "Backup: $backup"
Write-Host "Version objetivo: 8.5.5-r9.6"
Write-Host "Ejecuta las pruebas indicadas en LEEME_R9_6.md antes de usar el dashboard."
