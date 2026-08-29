param([string]$Root="")
$ErrorActionPreference="Stop"

if(-not $Root){
  if(Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local"){$Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local"}
  elseif(Test-Path "C:\IA_Local"){$Root="C:\IA_Local"}
  else{throw "No se encontro IA_Local."}
}

$Root=(Resolve-Path $Root).Path
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionFile=Join-Path $Root "VERSION.txt"
$Current=(Get-Content $VersionFile -Raw).Trim()

if($Current -notlike "*r10.11.2-semantic-contract*"){
  throw "R10.11.3 requiere R10.11.2 Semantic Contract instalado."
}

if(-not (Test-Path (Join-Path $Root "scripts\semantic_contract_enforcer.py"))){
  throw "No se encontro semantic_contract_enforcer.py."
}

Write-Host "Base detectada: $Current"

$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Backup=Join-Path $Root "updates\pre_r10_11_3_plan_utf8_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

foreach($f in @("VERSION.txt","scripts\prompt_execution_plan.py","scripts\dashboard_dynamic.py")){
  $src=Join-Path $Root $f
  if(Test-Path $src){
    Copy-Item $src (Join-Path $Backup ([IO.Path]::GetFileName($f))) -Force
  }
}
Write-Host "Backup R10.11.3: $Backup"

$Old=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "apply_r10_11_3.py") $Root
$Code=$LASTEXITCODE
$ErrorActionPreference=$Old
if($Code -ne 0){throw "FALLO apply_r10_11_3.py"}

$Old=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "test_r10_11_3_installed.py") $Root
$Code=$LASTEXITCODE
$ErrorActionPreference=$Old
if($Code -ne 0){throw "FALLO test_r10_11_3_installed.py"}

Write-Host ""
Write-Host "R10.11.3 PLAN CONSISTENCY + UTF8 APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version final: $((Get-Content $VersionFile -Raw).Trim())"
