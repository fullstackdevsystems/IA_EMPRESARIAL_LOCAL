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
if ($Current -notlike "*r10.11*" -and $Current -notlike "*r10.11.1*") {
  throw "R10.11.1 requiere R10.11 instalado."
}
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
