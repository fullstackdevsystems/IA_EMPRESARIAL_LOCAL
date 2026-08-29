$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Target = Join-Path $Root "IA_Local"
if (-not (Test-Path $Target)) {
    throw "No se encontro IA Empresarial Local en $Root. Extrae R9_7_1_PATCH dentro de C:\IA_EMPRESARIAL_LOCAL y vuelve a ejecutar."
}
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $Root "_backup_r9_7_1\$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

$RelativeFiles = @(
    "scripts\dashboard_dynamic.py",
    "scripts\analizador_universal.py",
    "tests\test_bi_productivo.py"
)

foreach ($rel in $RelativeFiles) {
    $dst = Join-Path $Target $rel
    if (Test-Path $dst) {
        $b = Join-Path $Backup $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $b -Parent) | Out-Null
        Copy-Item $dst $b -Force
    }
    $src = Join-Path $PSScriptRoot ("files\IA_Local\" + $rel)
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item $src $dst -Force
}

Write-Host ""
Write-Host "R9.7.1 aplicado correctamente." -ForegroundColor Green
Write-Host "Correccion: todos los filtros muestran la opcion Todos; multi-seleccion permite volver a Todos." -ForegroundColor Cyan
Write-Host "Backup: $Backup"
Write-Host "Version objetivo: 8.5.5-r9.7.1"
