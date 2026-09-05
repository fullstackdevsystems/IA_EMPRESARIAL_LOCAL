param([string]$RuntimeRoot=(Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),[Parameter(Mandatory=$true)][string]$BackupPath)
$ErrorActionPreference='Stop'
& (Join-Path $RuntimeRoot 'OperarIA.ps1') -Action backup -RuntimeRoot $RuntimeRoot -BackupPath $BackupPath
exit $LASTEXITCODE
