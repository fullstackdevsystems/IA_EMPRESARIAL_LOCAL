param([string]$Root = "")
$ErrorActionPreference = "Stop"
function Resolve-IARoot([string]$Requested) {
  if ($Requested) {
    if (Test-Path (Join-Path $Requested "scripts\enterprise_ai\factory.py")) { return (Resolve-Path $Requested).Path }
    throw "La ruta indicada no parece una instalacion IA_Local valida: $Requested"
  }
  foreach ($p in @("C:\IA_EMPRESARIAL_LOCAL\IA_Local", "C:\IA_Local")) {
    if (Test-Path (Join-Path $p "scripts\enterprise_ai\factory.py")) { return $p }
  }
  throw "No se encontro IA_Local. Use -Root C:\ruta\IA_Local"
}
$root=Resolve-IARoot $Root
$patch=Split-Path -Parent $MyInvocation.MyCommand.Path
$python=Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python="python" }
Write-Host "===================================================="
Write-Host " IA EMPRESARIAL LOCAL - R10.4 ENTERPRISE PRECEDENCE"
Write-Host "===================================================="
Write-Host "Root: $root"
& $python (Join-Path $patch "apply_r10_4.py") --root $root
if ($LASTEXITCODE -ne 0) { throw "Fallo aplicando R10.4" }
$pkg=Join-Path $root "scripts\enterprise_ai"
Write-Host "Compilando integracion..."
& $python -m py_compile (Join-Path $pkg "knowledge_governance.py") (Join-Path $pkg "precedence_engine.py") (Join-Path $pkg "structured_data.py") (Join-Path $pkg "context_engine.py") (Join-Path $pkg "factory.py")
if ($LASTEXITCODE -ne 0) { throw "Fallo py_compile R10.4" }
Write-Host "Ejecutando pruebas R10.4 sobre la instalacion..."
Push-Location (Join-Path $root "scripts")
try {
  & $python (Join-Path $patch "test_r10_4_integration_installed.py")
  if ($LASTEXITCODE -ne 0) { throw "Fallaron pruebas R10.4" }
} finally { Pop-Location }
Write-Host ""
Write-Host "R10.4 ENTERPRISE PRECEDENCE APLICADO CORRECTAMENTE"
Write-Host "Version: 8.5.5-r10.4-precedence"
Write-Host "Reglas y definiciones VALIDADO ahora tienen precedencia sobre inferencias, memoria y LLM."
