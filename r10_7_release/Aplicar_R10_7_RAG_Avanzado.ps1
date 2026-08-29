param([string]$Root="")
$ErrorActionPreference="Stop"
if(-not $Root){
  if(Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local"){$Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local"}
  elseif(Test-Path "C:\IA_Local"){$Root="C:\IA_Local"}
  else{throw "No se encontro IA_Local. Usa -Root C:\ruta\IA_Local"}
}
$Root=(Resolve-Path $Root).Path
$Py=Join-Path $Root ".venv\Scripts\python.exe"; if(-not(Test-Path $Py)){$Py="python"}
Write-Host "=== IA EMPRESARIAL LOCAL R10.7 - RAG EMPRESARIAL AVANZADO ==="
if(-not(Test-Path "$Root\scripts\enterprise_ai\analytic_rules.py")){ throw "R10.6 no detectado. Aplica primero R10.6 o usa el instalador limpio maestro." }
& $Py "$PSScriptRoot\apply_r10_7.py" --root $Root
if($LASTEXITCODE -ne 0){throw "Fallo parche R10.7"}
$files=@(
 "$Root\scripts\enterprise_ai\advanced_retrieval.py",
 "$Root\scripts\enterprise_ai\context_engine.py",
 "$Root\scripts\enterprise_ai\factory.py"
)
foreach($f in $files){& $Py -m py_compile $f;if($LASTEXITCODE -ne 0){throw "No compila: $f"}}
& $Py "$PSScriptRoot\test_r10_7_installed.py" $Root
if($LASTEXITCODE -ne 0){throw "Fallo integracion R10.7"}
Write-Host "R10.7 ADVANCED RAG APLICADO CORRECTAMENTE" -ForegroundColor Green
Get-Content "$Root\VERSION.txt"
