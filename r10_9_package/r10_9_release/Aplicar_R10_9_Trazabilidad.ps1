param([string]$Root="")
$ErrorActionPreference='Stop'
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Root){
  if(Test-Path 'C:\IA_EMPRESARIAL_LOCAL\IA_Local'){ $Root='C:\IA_EMPRESARIAL_LOCAL\IA_Local' }
  elseif(Test-Path 'C:\IA_Local'){ $Root='C:\IA_Local' }
  else { throw 'No se encontro IA_Local. Use -Root C:\ruta\IA_Local' }
}
$Root=(Resolve-Path $Root).Path
$Py=$null
if(Test-Path (Join-Path $Root '.venv\Scripts\python.exe')){$Py=Join-Path $Root '.venv\Scripts\python.exe'}
elseif(Get-Command python -ErrorAction SilentlyContinue){$Py='python'}
elseif(Get-Command py -ErrorAction SilentlyContinue){$Py='py'}
else{throw 'Python no encontrado'}

# R10.9 requiere la capa de feedback acumulativa. Si falta, aplica el payload incluido.
if(-not (Test-Path (Join-Path $Root 'scripts\enterprise_ai\feedback.py'))){
  $Prev=Join-Path $Here 'r10_8_payload\r10_8_release\Aplicar_R10_8_Feedback.ps1'
  if(-not (Test-Path $Prev)){throw 'Falta R10.8 y no se encontro payload acumulativo'}
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Prev -Root $Root
  if($LASTEXITCODE -ne 0){throw 'Fallo al aplicar prerequisito R10.8'}
}
& $Py (Join-Path $Here 'apply_r10_9.py') --root $Root
if($LASTEXITCODE -ne 0){throw 'Fallo parche R10.9'}
$Files=@(
 'scripts\enterprise_ai\traceability.py','scripts\enterprise_ai\factory.py','scripts\enterprise_ai\context_engine.py',
 'scripts\enterprise_ai\structured_data.py','scripts\enterprise_ai\service.py','scripts\enterprise_ai\api.py'
)
foreach($f in $Files){ & $Py -m py_compile (Join-Path $Root $f); if($LASTEXITCODE -ne 0){throw "Compilacion fallo: $f"} }
& $Py (Join-Path $Here 'test_r10_9_installed.py') $Root
if($LASTEXITCODE -ne 0){throw 'Pruebas instaladas R10.9 fallaron'}
Write-Host ''
Write-Host 'R10.9 TRAZABILIDAD APLICADO CORRECTAMENTE' -ForegroundColor Green
Write-Host 'Version: 8.5.5-r10.9-traceability'
