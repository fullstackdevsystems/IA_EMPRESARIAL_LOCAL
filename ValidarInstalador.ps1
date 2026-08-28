$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'InstalarLimpio.ps1'

if (-not (Test-Path $target -PathType Leaf)) {
    Write-Host 'ERROR: no se encontro InstalarLimpio.ps1.' -ForegroundColor Red
    exit 2
}

$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($target, [ref]$tokens, [ref]$errors)

if ($errors -and $errors.Count -gt 0) {
    Write-Host 'ERROR: el instalador PowerShell contiene errores de sintaxis:' -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host (' - ' + $err.Message) -ForegroundColor Red
    }
    exit 1
}

Write-Host 'Sintaxis PowerShell: OK' -ForegroundColor Green
exit 0
