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
$PerformanceModule=Join-Path $Root "scripts\enterprise_ai\performance.py"

# R10.11 se valida por capacidad instalada, no solo por la cadena VERSION.
# Esto tolera sufijos posteriores o una VERSION.txt modificada por otra fase,
# siempre que el motor de rendimiento R10.11 realmente exista.
$HasR1011Capability = Test-Path $PerformanceModule
$VersionLooksCompatible = ($Current -match '(?i)r10\.11(?:\.1)?(?:[-+.]|$)')

if (-not $HasR1011Capability -and -not $VersionLooksCompatible) {
  throw "R10.11.1 requiere la capacidad R10.11. No se encontro scripts\enterprise_ai\performance.py y VERSION='$Current'."
}

Write-Host "Prerequisito R10.11: OK"
Write-Host "Version detectada: $Current"
$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Backup=Join-Path $Root "updates\pre_r10_11_1_hotfix_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
$Files=@(
 "VERSION.txt",
 "scripts\universal_prompt_engine.py",
 "scripts\analizador_universal.py",
 "scripts\bi_productivo.py",
 "scripts\analizador_app.py"
)
foreach($f in $Files){
 $src=Join-Path $Root $f
 if(Test-Path $src){
   Copy-Item $src (Join-Path $Backup ([IO.Path]::GetFileName($f))) -Force
 }
}
Copy-Item (Join-Path $Here "data_contract.py") (Join-Path $Root "scripts\data_contract.py") -Force
Write-Host "Backup: $Backup"
& python (Join-Path $Here "apply_r10_11_1.py") $Root
& python (Join-Path $Here "test_r10_11_1_installed.py") $Root
Write-Host ""
Write-Host "R10.11.1 HOTFIX DATA CONTRACT APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version: 8.5.5-r10.11.1-data-contract-hotfix"
