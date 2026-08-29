param([string]$Root="")
$ErrorActionPreference="Stop"
if (-not $Root) { if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") {$Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local"} elseif(Test-Path "C:\IA_Local"){$Root="C:\IA_Local"} else {throw "No se encontro IA_Local. Use -Root."} }
$Root=(Resolve-Path $Root).Path; $Here=Split-Path -Parent $MyInvocation.MyCommand.Path; $Version=(Get-Content (Join-Path $Root 'VERSION.txt') -Raw).Trim()
if ($Version -notlike '*r10.11*' -and $Version -notlike '*r10.12*') { throw 'R10.12 requiere R10.11 instalado. Use prerequisite_R10_11.zip incluido.' }
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'; $Backup=Join-Path $Root "updates\pre_r10_12_finetune_$Stamp"; New-Item -ItemType Directory -Force -Path $Backup|Out-Null
Copy-Item (Join-Path $Root 'VERSION.txt') $Backup -ErrorAction SilentlyContinue; Copy-Item (Join-Path $Root 'scripts\enterprise_ai\api.py') $Backup -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Here 'fine_tuning_dataset.py') (Join-Path $Root 'scripts\enterprise_ai\fine_tuning_dataset.py') -Force
Write-Host "Backup: $Backup"; & python (Join-Path $Here 'apply_r10_12.py') $Root; & python (Join-Path $Here 'test_r10_12_installed.py') $Root
Write-Host ''; Write-Host 'R10.12 DATASET CONTROLADO PARA FINE-TUNING APLICADO CORRECTAMENTE' -ForegroundColor Green; Write-Host 'Version: 8.5.5-r10.12-controlled-finetune-dataset'; Write-Host 'Esta fase NO entrena ningun modelo.'
