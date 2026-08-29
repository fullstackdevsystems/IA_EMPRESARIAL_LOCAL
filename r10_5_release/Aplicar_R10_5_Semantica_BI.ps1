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
Write-Host "=== IA EMPRESARIAL LOCAL R10.5 - INTEGRACION SEMANTICA UNIVERSAL BI ==="
if (-not (Test-Path "$Root\scripts\enterprise_ai\precedence_engine.py")) {
  Write-Host "R10.4 no detectado; aplicando base de gobernanza/precedencia incluida..."
  & $Py "$PSScriptRoot\apply_r10_4.py" --root $Root
  if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar la base R10.4" }
}
& $Py "$PSScriptRoot\apply_r10_5.py" --root $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo el parche R10.5" }
$files=@(
 "$Root\scripts\enterprise_ai\semantic_registry.py",
 "$Root\scripts\enterprise_ai\factory.py",
 "$Root\scripts\bi_productivo.py",
 "$Root\scripts\dashboard_dynamic.py",
 "$Root\scripts\dashboard_planner.py",
 "$Root\scripts\analizador_universal.py"
)
foreach($f in $files){ & $Py -m py_compile $f; if($LASTEXITCODE -ne 0){throw "No compila: $f"} }
& $Py "$PSScriptRoot\test_r10_5_semantics.py" $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo suite R10.5" }
& $Py "$PSScriptRoot\test_r10_5_integration_installed.py" $Root
if ($LASTEXITCODE -ne 0) { throw "Fallo integracion R10.5" }
Write-Host "R10.5 SEMANTIC BI APLICADO CORRECTAMENTE" -ForegroundColor Green
Get-Content "$Root\VERSION.txt"
