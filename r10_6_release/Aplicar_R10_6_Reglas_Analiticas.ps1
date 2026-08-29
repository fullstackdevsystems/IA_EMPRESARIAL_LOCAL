param([string]$Root="")
$ErrorActionPreference="Stop"
if (-not $Root) {
  if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") { $Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local" }
  elseif (Test-Path "C:\IA_Local") { $Root="C:\IA_Local" }
  else { throw "No se encontro IA_Local. Usa -Root C:\ruta\IA_Local" }
}
$Root=(Resolve-Path $Root).Path
$Py=Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py="python" }
Write-Host "=== IA EMPRESARIAL LOCAL R10.6 - REGLAS EMPRESARIALES ANALITICAS ==="
if (-not (Test-Path "$Root\scripts\enterprise_ai\semantic_registry.py")) {
  Write-Host "R10.5 no detectado; preparando R10.4/R10.5 incluidos..."
  if (-not (Test-Path "$Root\scripts\enterprise_ai\precedence_engine.py")) {
    & $Py "$PSScriptRoot\apply_r10_4.py" --root $Root
    if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar R10.4" }
  }
  & $Py "$PSScriptRoot\apply_r10_5.py" --root $Root
  if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar R10.5" }
}
& $Py "$PSScriptRoot\apply_r10_6.py" --root $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo el parche R10.6" }
$files=@(
 "$Root\scripts\enterprise_ai\analytic_rules.py",
 "$Root\scripts\enterprise_ai\factory.py",
 "$Root\scripts\enterprise_ai\structured_data.py",
 "$Root\scripts\bi_productivo.py",
 "$Root\scripts\analizador_universal.py"
)
foreach($f in $files){ & $Py -m py_compile $f; if($LASTEXITCODE -ne 0){throw "No compila: $f"} }
& $Py "$PSScriptRoot\test_r10_6_installed.py" $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo integracion R10.6" }
Write-Host "R10.6 ANALYTIC RULES APLICADO CORRECTAMENTE" -ForegroundColor Green
Get-Content "$Root\VERSION.txt"
