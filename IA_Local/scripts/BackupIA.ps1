param(
    [string]$Root = "C:\IA_Local",
    [int]$Retention = 7
)
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $Root "backups"
$stage = Join-Path $backupRoot "stage_$stamp"
$zip = Join-Path $backupRoot "IA_Local_Backup_$stamp.zip"
New-Item -ItemType Directory -Path $stage -Force | Out-Null

function Test-Port([int]$Port) {
    try { return (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded } catch { return $false }
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " IA EMPRESARIAL V8.5.3 - RESPALDO CONSISTENTE" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
if (Test-Port 8090) {
    Write-Host "ERROR: el servicio de IA sigue activo en 8090." -ForegroundColor Red
    Write-Host "Para un respaldo consistente ejecuta primero C:\IA_Local\DETENER_IA.bat"
    exit 2
}

$items = @(
    @{src="config"; dst="config"},
    @{src="data\enterprise"; dst="data\enterprise"},
    @{src="workspace\Conocimiento"; dst="workspace\Conocimiento"},
    @{src="VERSION.txt"; dst="VERSION.txt"}
)
foreach ($item in $items) {
    $src = Join-Path $Root $item.src
    if (Test-Path $src) {
        $dst = Join-Path $stage $item.dst
        $parent = Split-Path $dst -Parent
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Copy-Item $src $dst -Recurse -Force
    }
}
$manifest = @{
    created_at = (Get-Date).ToString("o")
    root = $Root
    contains_secrets = $true
    note = "Protege este respaldo: incluye token/secretos locales y conocimiento empresarial."
} | ConvertTo-Json -Depth 5
Set-Content (Join-Path $stage "BACKUP_MANIFEST.json") $manifest -Encoding UTF8
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -CompressionLevel Optimal -Force
Remove-Item $stage -Recurse -Force
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
Set-Content ($zip + ".sha256") ("$hash  " + [IO.Path]::GetFileName($zip)) -Encoding ASCII
Write-Host "Respaldo creado: $zip" -ForegroundColor Green
Write-Host "SHA-256: $hash"
Write-Host "IMPORTANTE: el ZIP contiene información y secretos locales; almacénalo en ubicación protegida." -ForegroundColor Yellow

Get-ChildItem $backupRoot -Filter "IA_Local_Backup_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Retention | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    Remove-Item ($_.FullName + ".sha256") -Force -ErrorAction SilentlyContinue
}
