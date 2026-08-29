param(
    [string]$Root = ""
)
$ErrorActionPreference = "Stop"

function Resolve-IARoot {
    param([string]$Requested)
    if ($Requested) {
        if (Test-Path (Join-Path $Requested "scripts\enterprise_ai\factory.py")) { return (Resolve-Path $Requested).Path }
        throw "La ruta indicada no parece una instalacion IA_Local valida: $Requested"
    }
    foreach ($p in @("C:\IA_EMPRESARIAL_LOCAL\IA_Local", "C:\IA_Local")) {
        if (Test-Path (Join-Path $p "scripts\enterprise_ai\factory.py")) { return $p }
    }
    throw "No se encontro IA_Local. Use -Root C:\ruta\IA_Local"
}

$root = Resolve-IARoot $Root
$patch = Split-Path -Parent $MyInvocation.MyCommand.Path
$scripts = Join-Path $root "scripts"
$pkg = Join-Path $scripts "enterprise_ai"
$factory = Join-Path $pkg "factory.py"
$version = Join-Path $root "VERSION.txt"
$tests = Join-Path $root "tests"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $root "updates\pre_r10_3_governance_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

Write-Host "===================================================="
Write-Host " IA EMPRESARIAL LOCAL - R10.3 KNOWLEDGE GOVERNANCE"
Write-Host "===================================================="
Write-Host "Root: $root"
Write-Host "Backup: $backup"

Copy-Item $factory (Join-Path $backup "factory.py") -Force
if (Test-Path $version) { Copy-Item $version (Join-Path $backup "VERSION.txt") -Force }
if (Test-Path (Join-Path $pkg "knowledge_governance.py")) { Copy-Item (Join-Path $pkg "knowledge_governance.py") (Join-Path $backup "knowledge_governance.py") -Force }

Copy-Item (Join-Path $patch "knowledge_governance.py") (Join-Path $pkg "knowledge_governance.py") -Force
New-Item -ItemType Directory -Force -Path $tests | Out-Null
Copy-Item (Join-Path $patch "test_r10_3_governance.py") (Join-Path $tests "test_r10_3_governance.py") -Force

$text = Get-Content $factory -Raw -Encoding UTF8
if ($text -notmatch 'knowledge_governance import KnowledgeGovernance') {
    $needle = 'from .memory import MemoryManager'
    if (-not $text.Contains($needle)) { throw "No se encontro punto seguro de parcheo para import en factory.py" }
    $text = $text.Replace($needle, $needle + "`r`nfrom .knowledge_governance import KnowledgeGovernance")
}

$oldSig = 'def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, context, service, logger):'
$newSig = 'def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, context, service, logger):'
if ($text.Contains($oldSig)) { $text = $text.Replace($oldSig, $newSig) }
elseif (-not $text.Contains($newSig)) { throw "Firma Components inesperada; se cancela para evitar regresion" }

if ($text -notmatch 'self\.governance = governance') {
    $needle = '        self.documents = documents'
    if (-not $text.Contains($needle)) { throw "No se encontro punto seguro para self.governance" }
    $text = $text.Replace($needle, $needle + "`r`n        self.governance = governance")
}

if ($text -notmatch 'governance = KnowledgeGovernance\(db\)') {
    $needle = '    documents = DocumentService(cfg, db, embeddings, vectors, datasets)'
    if (-not $text.Contains($needle)) { throw "No se encontro punto seguro para crear governance" }
    $text = $text.Replace($needle, $needle + "`r`n    governance = KnowledgeGovernance(db)")
}

$oldReturn = '    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, context, service, logger)'
$newReturn = '    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, governance, context, service, logger)'
if ($text.Contains($oldReturn)) { $text = $text.Replace($oldReturn, $newReturn) }
elseif (-not $text.Contains($newReturn)) { throw "Return Components inesperado; se cancela para evitar regresion" }

Set-Content -Path $factory -Value $text -Encoding UTF8
Set-Content -Path $version -Value "8.5.5-r10.3-governance" -Encoding ASCII

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Compilando archivos..."
& $python -m py_compile (Join-Path $pkg "knowledge_governance.py") $factory
if ($LASTEXITCODE -ne 0) { throw "Fallo py_compile" }

Write-Host "Ejecutando pruebas R10.3..."
Push-Location $scripts
try {
    & $python (Join-Path $tests "test_r10_3_governance.py")
    if ($LASTEXITCODE -ne 0) { throw "Fallaron pruebas R10.3" }
} finally { Pop-Location }

Write-Host ""
Write-Host "R10.3 KNOWLEDGE GOVERNANCE APLICADO CORRECTAMENTE"
Write-Host "Version: 8.5.5-r10.3-governance"
Write-Host "Se agregaron reglas empresariales y diccionario semantico con estados, vigencia, conflictos, versionado, aislamiento y procedencia."

