param([string]$Root="")
$ErrorActionPreference='Stop'
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Root){if(Test-Path 'C:\IA_EMPRESARIAL_LOCAL\IA_Local'){$Root='C:\IA_EMPRESARIAL_LOCAL\IA_Local'}elseif(Test-Path 'C:\IA_Local'){$Root='C:\IA_Local'}else{throw 'No se encontro IA_Local. Use -Root C:\ruta\IA_Local'}}
$Root=(Resolve-Path $Root).Path
if(Test-Path (Join-Path $Root '.venv\Scripts\python.exe')){$Py=Join-Path $Root '.venv\Scripts\python.exe'}elseif(Get-Command python -ErrorAction SilentlyContinue){$Py='python'}elseif(Get-Command py -ErrorAction SilentlyContinue){$Py='py'}else{throw 'Python no encontrado'}
if(-not (Test-Path (Join-Path $Root 'scripts\enterprise_ai\traceability.py'))){$Prev=Join-Path $Here 'r10_9_payload\r10_9_release\Aplicar_R10_9_Trazabilidad.ps1';if(-not(Test-Path $Prev)){throw 'Falta R10.9 y no existe payload acumulativo'};& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Prev -Root $Root;if($LASTEXITCODE -ne 0){throw 'Fallo prerequisito R10.9'}}
& $Py (Join-Path $Here 'apply_r10_10.py') --root $Root
if($LASTEXITCODE -ne 0){throw 'Fallo parche R10.10'}
& $Py (Join-Path $Here 'test_r10_10_installed.py') $Root
if($LASTEXITCODE -ne 0){throw 'Pruebas instaladas R10.10 fallaron'}
Write-Host '';Write-Host 'R10.10 ADMINISTRACION UNIFICADA APLICADO CORRECTAMENTE' -ForegroundColor Green;Write-Host 'Version: 8.5.5-r10.10-unified-admin';Write-Host 'Abra ABRIR_ADMIN_MEMORIA_RAG.bat para usar la consola.'
