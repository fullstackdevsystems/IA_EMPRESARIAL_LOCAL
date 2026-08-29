param([string]$Root="")
$ErrorActionPreference="Stop"
if(-not $Root){
 if(Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local"){$Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local"}
 elseif(Test-Path "C:\IA_Local"){$Root="C:\IA_Local"}
 else{throw "No se encontro IA_Local."}
}
$Root=(Resolve-Path $Root).Path
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Current=(Get-Content (Join-Path $Root "VERSION.txt") -Raw).Trim()
if($Current -notlike "*r10.11.1*"){
 throw "R10.11.2 requiere el hotfix R10.11.1 V6 instalado."
}
Write-Host "Base detectada: $Current"

$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Backup=Join-Path $Root "updates\pre_r10_11_2_semantic_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup|Out-Null
foreach($f in @("VERSION.txt","scripts\enterprise_prompt_compiler.py","scripts\dashboard_dynamic.py")){
 $src=Join-Path $Root $f
 if(Test-Path $src){Copy-Item $src (Join-Path $Backup ([IO.Path]::GetFileName($f))) -Force}
}
Write-Host "Backup R10.11.2: $Backup"

Copy-Item (Join-Path $Here "semantic_contract_enforcer.py") (Join-Path $Root "scripts\semantic_contract_enforcer.py") -Force

$Old=$ErrorActionPreference;$ErrorActionPreference="Continue"
& python (Join-Path $Here "apply_r10_11_2.py") $Root
$Code=$LASTEXITCODE;$ErrorActionPreference=$Old
if($Code -ne 0){throw "FALLO apply_r10_11_2.py"}

$Old=$ErrorActionPreference;$ErrorActionPreference="Continue"
& python (Join-Path $Here "test_r10_11_2_installed.py") $Root
$Code=$LASTEXITCODE;$ErrorActionPreference=$Old
if($Code -ne 0){throw "FALLO test_r10_11_2_installed.py"}

Write-Host ""
Write-Host "R10.11.2 SEMANTIC CONTRACT ENFORCEMENT APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version final: $((Get-Content (Join-Path $Root "VERSION.txt") -Raw).Trim())"
