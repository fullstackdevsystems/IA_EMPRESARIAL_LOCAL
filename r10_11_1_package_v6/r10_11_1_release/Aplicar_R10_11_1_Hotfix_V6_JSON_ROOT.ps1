param([string]$Root="")
$ErrorActionPreference="Stop"

if (-not $Root) {
  if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") { $Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local" }
  elseif (Test-Path "C:\IA_Local") { $Root="C:\IA_Local" }
  else { throw "No se encontro IA_Local. Use -Root." }
}

$Root=(Resolve-Path $Root).Path
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionFile=Join-Path $Root "VERSION.txt"
$Current=if(Test-Path $VersionFile){(Get-Content $VersionFile -Raw).Trim()}else{""}

if (-not (Test-Path (Join-Path $Root "scripts\enterprise_ai\performance.py"))) {
  throw "Falta capacidad R10.11 performance.py."
}
if (-not (Test-Path (Join-Path $Root "scripts\data_contract.py"))) {
  throw "Falta Data Contract V4."
}

Write-Host "Base detectada: $Current"

$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Backup=Join-Path $Root "updates\pre_r10_11_1_hotfix_v6_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
Copy-Item (Join-Path $Root "VERSION.txt") $Backup -Force
Copy-Item (Join-Path $Root "scripts\dashboard_dynamic.py") $Backup -Force
Copy-Item (Join-Path $Root "scripts\analizador_app.py") $Backup -Force
Write-Host "Backup V6: $Backup"

$OldEap=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "apply_r10_11_1_v6.py") $Root
$ApplyExit=$LASTEXITCODE
$ErrorActionPreference=$OldEap
if($ApplyExit -ne 0){ throw "FALLO apply_r10_11_1_v6.py" }

$OldEap=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "test_r10_11_1_v6_installed.py") $Root
$TestExit=$LASTEXITCODE
$ErrorActionPreference=$OldEap
if($TestExit -ne 0){ throw "FALLO test_r10_11_1_v6_installed.py" }

Write-Host ""
Write-Host "R10.11.1 HOTFIX V6 JSON + ROOT APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version final: $((Get-Content $VersionFile -Raw).Trim())"
