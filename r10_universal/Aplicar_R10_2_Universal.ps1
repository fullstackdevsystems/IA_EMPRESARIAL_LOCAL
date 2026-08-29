param(
    [string]$Root = ""
)
$ErrorActionPreference = "Stop"

function Find-Root {
    param([string]$Requested)
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    $candidates += @(
        "C:\IA_EMPRESARIAL_LOCAL\IA_Local",
        "C:\IA_Local",
        (Join-Path $PSScriptRoot "IA_Local")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path (Join-Path $c "scripts\analizador_universal.py"))) { return (Resolve-Path $c).Path }
    }
    throw "No se encontro IA_Local. Ejecuta: powershell -ExecutionPolicy Bypass -File .\Aplicar_R10_2_Universal.ps1 -Root C:\ruta\IA_Local"
}

$ia = Find-Root $Root
$scripts = Join-Path $ia "scripts"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $ia "updates\pre_r10_2_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$targets = @("enterprise_prompt_compiler.py", "prompt_execution_plan.py", "analizador_universal.py")
foreach ($name in $targets) {
    $src = Join-Path $scripts $name
    if (Test-Path $src) { Copy-Item $src (Join-Path $backup $name) -Force }
}
if (Test-Path (Join-Path $ia "VERSION.txt")) { Copy-Item (Join-Path $ia "VERSION.txt") (Join-Path $backup "VERSION.txt") -Force }

# Instalar motor universal y adaptadores.
Copy-Item (Join-Path $PSScriptRoot "universal_prompt_engine.py") (Join-Path $scripts "universal_prompt_engine.py") -Force
Copy-Item (Join-Path $PSScriptRoot "enterprise_prompt_compiler.py") (Join-Path $scripts "enterprise_prompt_compiler.py") -Force
Copy-Item (Join-Path $PSScriptRoot "prompt_execution_plan.py") (Join-Path $scripts "prompt_execution_plan.py") -Force

# Mejorar seleccion automatica de hoja: prompt explicito manda; en ausencia de eso,
# se pondera nivel transaccional real y no solo volumen/nombre de hoja.
$anPath = Join-Path $scripts "analizador_universal.py"
$an = Get-Content $anPath -Raw -Encoding UTF8
$oldPattern = '(?s)def _sheet_relevance\(sheet: str, df: pd\.DataFrame, prompt: str\) -> float:\r?\n.*?\r?\n\s*return score\r?\n'
$newFunction = @'
def _sheet_relevance(sheet: str, df: pd.DataFrame, prompt: str) -> float:
    """R10.2: rank sheets by explicit user intent + transactional detail.

    A sheet is no longer selected merely because it is large or because a domain
    prompt happened to mention legacy columns. If the user explicitly names a
    sheet, that instruction wins. Otherwise the engine favors tables that look
    like detailed transactions and only uses prompt/schema overlap as a tiebreaker.
    """
    from universal_prompt_engine import norm as _unorm, score_transactional_source

    p = _unorm(prompt)
    sname = _unorm(sheet)
    info = score_transactional_source(df)
    score = float(info.get("score", 0.0)) * 4.0

    # Explicit source references are authoritative.
    explicit_patterns = [
        rf"\bhoja\s+{re.escape(sname)}\b",
        rf"\b{sname}\s+(?:es\s+)?(?:la\s+)?(?:fuente|base de datos principal|unica fuente)\b",
    ] if sname else []
    if any(re.search(pat, p) for pat in explicit_patterns):
        score += 1000.0
    elif sname and sname in p:
        score += 40.0

    # Prompt/schema overlap is useful, but secondary to transactional structure.
    stop = {"analiza","analizar","archivo","excel","reporte","resumen","completo","completamente",
            "dame","quiero","calcula","calcular","datos","informacion","principales","mejor","peor",
            "todos","todas","sobre","para","con","del","las","los","una","uno","por","que"}
    tokens = [t for t in p.split() if len(t) >= 3 and t not in stop]
    blob_cols = " | ".join(_unorm(c) for c in df.columns)
    for tok in tokens:
        if tok in blob_cols:
            score += 1.5
        if tok in sname:
            score += 2.0

    # Weak naming hints only; never override explicit user choice.
    if any(x in sname for x in ("resumen", "dashboard", "grafica", "pivot", "td", "reporte")):
        score -= 6.0
    if any(x in sname for x in ("bd", "base", "datos", "detalle", "movimiento", "transaccion")):
        score += 3.0
    return score
'@
if ([regex]::IsMatch($an, $oldPattern)) {
    $an = [regex]::Replace($an, $oldPattern, $newFunction + "`r`n", 1)
} else {
    throw "No se encontro la funcion _sheet_relevance esperada; se cancela para no modificar codigo desconocido."
}
Set-Content $anPath $an -Encoding UTF8

# Version visible.
Set-Content (Join-Path $ia "VERSION.txt") "8.5.5-r10.2-universal" -Encoding ASCII

# Pruebas de sintaxis y regresion universal.
$py = $null
$venvPy = Join-Path $ia ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = (Get-Command python).Source }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { throw "No se encontro Python para validar la actualizacion." }

if ($py -eq "py") {
    & py -3 -m py_compile (Join-Path $scripts "universal_prompt_engine.py") (Join-Path $scripts "enterprise_prompt_compiler.py") (Join-Path $scripts "prompt_execution_plan.py") (Join-Path $scripts "analizador_universal.py")
    & py -3 (Join-Path $PSScriptRoot "test_r10_2_universal.py") $scripts
} else {
    & $py -m py_compile (Join-Path $scripts "universal_prompt_engine.py") (Join-Path $scripts "enterprise_prompt_compiler.py") (Join-Path $scripts "prompt_execution_plan.py") (Join-Path $scripts "analizador_universal.py")
    & $py (Join-Path $PSScriptRoot "test_r10_2_universal.py") $scripts
}
if ($LASTEXITCODE -ne 0) { throw "Las pruebas R10.2 fallaron. Backup disponible en $backup" }

Write-Host ""
Write-Host "R10.2 UNIVERSAL APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "IA_Local: $ia"
Write-Host "Backup:   $backup"
Write-Host "Version:  8.5.5-r10.2-universal"
Write-Host ""
Write-Host "Cambios principales:"
Write-Host " - Prompt compiler universal, sin gate de granos/ventas."
Write-Host " - Roles semanticos detectados desde columnas reales."
Write-Host " - Seleccion de hoja por detalle transaccional salvo fuente explicita."
Write-Host " - Metricas no derivables quedan N/D/bloqueadas."
Write-Host " - Compatibilidad con prompts anteriores conservada cuando sus columnas existen."
