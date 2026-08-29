param([string]$Root="")
$ErrorActionPreference="Stop"
if (-not $Root) {
  if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") { $Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local" }
  elseif (Test-Path "C:\IA_Local") { $Root="C:\IA_Local" }
  else { throw "No se encontro IA_Local. Use -Root C:\ruta\IA_Local" }
}
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path

# R10.8 requiere el RAG avanzado de R10.7. Si falta, se aplica el payload incluido.
if (-not (Test-Path "$Root\scripts\enterprise_ai\advanced_retrieval.py")) {
  $Pre = Join-Path (Split-Path -Parent $Here) "prerequisite_r10_7\Aplicar_R10_7_RAG_Avanzado.ps1"
  if (-not (Test-Path $Pre)) { throw "Falta R10.7 y no se encontro el prerequisito incluido." }
  Write-Host "R10.7 no detectado. Aplicando prerequisito acumulativo..." -ForegroundColor Yellow
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Pre -Root $Root
  if ($LASTEXITCODE -ne 0) { throw "No se pudo aplicar el prerequisito R10.7" }
}
$Python=$null
foreach($p in @("$Root\.venv\Scripts\python.exe","python.exe","py.exe")){try{& $p --version *> $null;if($LASTEXITCODE -eq 0){$Python=$p;break}}catch{}}
if(-not $Python){throw "Python no disponible"}
& $Python "$Here\apply_r10_8.py" --root "$Root"
if($LASTEXITCODE -ne 0){throw "Fallo aplicando R10.8"}
& $Python -m py_compile "$Root\scripts\enterprise_ai\feedback.py" "$Root\scripts\enterprise_ai\factory.py" "$Root\scripts\enterprise_ai\api.py"
if($LASTEXITCODE -ne 0){throw "Fallo de compilacion R10.8"}
& $Python "$Here\test_r10_8_installed.py" --root "$Root"
if($LASTEXITCODE -ne 0){throw "Pruebas R10.8 FALLARON"}
Write-Host ""
Write-Host "R10.8 FEEDBACK Y APRENDIZAJE CONTROLADO APLICADO CORRECTAMENTE" -ForegroundColor Green
Get-Content "$Root\VERSION.txt"
