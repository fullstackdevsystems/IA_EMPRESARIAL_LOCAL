param([string]$Root="")
$ErrorActionPreference="Stop"

if (-not $Root) {
  if (Test-Path "C:\IA_EMPRESARIAL_LOCAL\IA_Local") { $Root="C:\IA_EMPRESARIAL_LOCAL\IA_Local" }
  elseif (Test-Path "C:\IA_Local") { $Root="C:\IA_Local" }
  else { throw "No se encontro IA_Local. Use -Root." }
}

$Root=(Resolve-Path $Root).Path
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionFile=Join-Path $Root "VERSION.txt"
$Current=if(Test-Path $VersionFile){(Get-Content $VersionFile -Raw).Trim()}else{""}
$PerformanceModule=Join-Path $Root "scripts\enterprise_ai\performance.py"

if (-not (Test-Path $PerformanceModule)) {
  throw "R10.11.1 requiere la capacidad R10.11: falta scripts\enterprise_ai\performance.py"
}

Write-Host "Prerequisito R10.11: OK"
Write-Host "Version detectada antes de recuperacion: $Current"

$AnalyzerApp=Join-Path $Root "scripts\analizador_app.py"
$NeedRecovery=$false

# Si V2/V3 dejo marcada exactamente la version hotfix rota,
# recuperar directamente sin intentar compilar el archivo dañado.
if ($Current -eq "8.5.5-r10.11.1-data-contract-hotfix") {
  $NeedRecovery=$true
}
else {
  # Para otros estados, comprobar sintaxis sin permitir que stderr de Python
  # sea tratado por PowerShell como una excepcion antes de leer $LASTEXITCODE.
  $OldEap=$ErrorActionPreference
  $ErrorActionPreference="Continue"
  & python -m py_compile $AnalyzerApp 2>$null
  $CompileExit=$LASTEXITCODE
  $ErrorActionPreference=$OldEap
  if ($CompileExit -ne 0) { $NeedRecovery=$true }
}

if ($NeedRecovery) {
  $Updates=Join-Path $Root "updates"
  $Candidates=Get-ChildItem $Updates -Directory -Filter "pre_r10_11_1_hotfix_*" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending

  $Recovery=$null
  foreach($c in $Candidates) {
    # No usar respaldos V3 creados despues del daño si carecen de una base R10.12 limpia.
    if ($c.Name -like "pre_r10_11_1_hotfix_v3_*") { continue }

    $Required=@(
      "VERSION.txt",
      "universal_prompt_engine.py",
      "analizador_universal.py",
      "bi_productivo.py",
      "analizador_app.py"
    )
    $All=$true
    foreach($f in $Required) {
      if(-not (Test-Path (Join-Path $c.FullName $f))) { $All=$false; break }
    }

    if($All) {
      $BackupVersion=(Get-Content (Join-Path $c.FullName "VERSION.txt") -Raw).Trim()
      if($BackupVersion -like "*r10.12*") {
        $Recovery=$c.FullName
        break
      }
    }
  }

  if(-not $Recovery) {
    throw "No se encontro un backup pre_r10_11_1_hotfix_* completo con base R10.12 para recuperacion automatica."
  }

  Write-Host "Recuperando base previa desde: $Recovery" -ForegroundColor Yellow

  Copy-Item (Join-Path $Recovery "VERSION.txt") (Join-Path $Root "VERSION.txt") -Force
  Copy-Item (Join-Path $Recovery "universal_prompt_engine.py") (Join-Path $Root "scripts\universal_prompt_engine.py") -Force
  Copy-Item (Join-Path $Recovery "analizador_universal.py") (Join-Path $Root "scripts\analizador_universal.py") -Force
  Copy-Item (Join-Path $Recovery "bi_productivo.py") (Join-Path $Root "scripts\bi_productivo.py") -Force
  Copy-Item (Join-Path $Recovery "analizador_app.py") (Join-Path $Root "scripts\analizador_app.py") -Force

  $Recovered=(Get-Content (Join-Path $Root "VERSION.txt") -Raw).Trim()
  Write-Host "Base recuperada. Version: $Recovered" -ForegroundColor Green

  $OldEap=$ErrorActionPreference
  $ErrorActionPreference="Continue"
  & python -m py_compile `
      (Join-Path $Root "scripts\analizador_app.py") `
      (Join-Path $Root "scripts\analizador_universal.py") `
      (Join-Path $Root "scripts\bi_productivo.py") `
      (Join-Path $Root "scripts\universal_prompt_engine.py")
  $RecoveredCompileExit=$LASTEXITCODE
  $ErrorActionPreference=$OldEap

  if($RecoveredCompileExit -ne 0) {
    throw "La base restaurada no compila. Se detiene sin aplicar el hotfix."
  }

  Write-Host "Compilacion de base restaurada: OK" -ForegroundColor Green
}

# Backup limpio justo antes de aplicar V4.
$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Backup=Join-Path $Root "updates\pre_r10_11_1_hotfix_v4_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

$Files=@(
 "VERSION.txt",
 "scripts\universal_prompt_engine.py",
 "scripts\analizador_universal.py",
 "scripts\bi_productivo.py",
 "scripts\analizador_app.py"
)

foreach($f in $Files){
  $src=Join-Path $Root $f
  if(Test-Path $src){
    Copy-Item $src (Join-Path $Backup ([IO.Path]::GetFileName($f))) -Force
  }
}

Write-Host "Backup V4: $Backup"

Copy-Item (Join-Path $Here "data_contract.py") (Join-Path $Root "scripts\data_contract.py") -Force

$OldEap=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "apply_r10_11_1.py") $Root
$ApplyExit=$LASTEXITCODE
$ErrorActionPreference=$OldEap

if($ApplyExit -ne 0) {
  throw "FALLO apply_r10_11_1.py. No se declara instalado."
}

$OldEap=$ErrorActionPreference
$ErrorActionPreference="Continue"
& python (Join-Path $Here "test_r10_11_1_installed.py") $Root
$TestExit=$LASTEXITCODE
$ErrorActionPreference=$OldEap

if($TestExit -ne 0) {
  throw "FALLO test_r10_11_1_installed.py. No se declara instalado."
}

Write-Host ""
Write-Host "R10.11.1 HOTFIX DATA CONTRACT V4 APLICADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "Version final: $((Get-Content $VersionFile -Raw).Trim())"
