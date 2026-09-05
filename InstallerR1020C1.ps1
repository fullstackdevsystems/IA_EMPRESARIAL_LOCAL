[CmdletBinding()]
param([string]$InstallPath=(Join-Path $env:LOCALAPPDATA 'IA_Empresarial_Local'),[switch]$NonInteractive,[string]$TenantId,[string]$TenantName,[string]$AdminUsername,[switch]$SkipSqlCheck,[switch]$SkipAiCheck,[switch]$ValidateOnly)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path;$source=Join-Path $root 'IA_Local';$log=Join-Path $root 'logs\installer-r10.20c.1.log'
function Note($x){if($ValidateOnly){Write-Host $x;return};New-Item -ItemType Directory -Force (Split-Path $log)|Out-Null;Add-Content $log "$(Get-Date -Format o) $x";Write-Host $x}
function Stop-Install($x){Note "FAIL: $x";throw $x}
Note 'R10.20C.1 installer starting'
if($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem){Stop-Install 'Windows x64 required'}
if(-not(Test-Path $source)){Stop-Install 'Critical IA_Local source missing'}
function Resolve-CompatiblePython {
    $candidates = @()

    foreach ($path in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        'C:\Python312\python.exe',
        'C:\Python311\python.exe',
        'C:\Program Files\Python312\python.exe',
        'C:\Program Files\Python311\python.exe'
    )) {
        if (Test-Path $path -PathType Leaf) {
            $candidates += @{ Kind = "direct"; Command = $path; Args = @() }
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue

    if ($pyLauncher -and $pyLauncher.Source) {
        $candidates += @{
            Kind = "launcher"
            Command = $pyLauncher.Source
            Args = @("-3.12")
        }

        $candidates += @{
            Kind = "launcher"
            Command = $pyLauncher.Source
            Args = @("-3.11")
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue

    if ($pythonCommand -and $pythonCommand.Source) {
        $candidates += @{
            Kind = "direct"
            Command = $pythonCommand.Source
            Args = @()
        }
    }

    foreach ($candidate in $candidates) {
        try {
            $versionText = & $candidate.Command @($candidate.Args) --version 2>&1

            if ($LASTEXITCODE -ne 0) {
                continue
            }

            $version = (
                [string]$versionText -replace '^Python\s+',''
            ).Trim()

            if ($version -match '^3\.(11|12)(\.|$)') {
                return [pscustomobject]@{
                    Command = $candidate.Command
                    Args = @($candidate.Args)
                    Version = $version
                }
            }
        }
        catch {}
    }

    return $null
}

$py = Resolve-CompatiblePython

if (-not $py) {
    Stop-Install 'Python 3.11 or 3.12 required. Python 3.13 is not supported by the current Open WebUI dependency set.'
}

Note "Compatible Python detected: $($py.Version)"
$manifest=Join-Path $root 'MANIFEST_SHA256.json';if(Test-Path $manifest){foreach($e in (Get-Content $manifest -Raw|ConvertFrom-Json).files){$f=Join-Path $root ([string]$e.path).Replace('/','\');if(-not(Test-Path $f)){Stop-Install "Manifest missing $($e.path)"};if((Get-FileHash $f -Algorithm SHA256).Hash -ne $e.sha256){Stop-Install "Manifest mismatch $($e.path)"}}}
if($ValidateOnly){Note 'VALIDATE-ONLY: PASS';exit 0}
$ProductRoot = [System.IO.Path]::GetFullPath($InstallPath)
$RuntimeRoot = Join-Path $ProductRoot 'IA_Local'

try {
    New-Item -ItemType Directory -Force $ProductRoot | Out-Null
}
catch {
    Stop-Install 'Install path not writable'
}

if (-not (Test-Path (Join-Path $RuntimeRoot 'scripts'))) {
    New-Item -ItemType Directory -Force $RuntimeRoot | Out-Null
    Copy-Item (Join-Path $source '*') $RuntimeRoot -Recurse -Force
}

foreach ($d in 'config','data','logs','workspace','Reportes') {
    New-Item -ItemType Directory -Force (Join-Path $RuntimeRoot $d) | Out-Null
}

$rootFiles = @(
    'OperarIA.ps1',
    'LEEME_INSTALACION_LIMPIA.txt',
    'MANIFEST_SHA256.json',
    'InstallerR1020C1.ps1',
    'InstalarLimpio.ps1',
    'INSTALAR_IA_EMPRESARIAL_LOCAL.bat'
)

foreach ($rootFile in $rootFiles) {
    $sourceFile = Join-Path $root $rootFile

    if (Test-Path $sourceFile -PathType Leaf) {
        Copy-Item $sourceFile (Join-Path $ProductRoot $rootFile) -Force
    }
}

$vp = Join-Path $ProductRoot '.venv\Scripts\python.exe'

if(-not(Test-Path $vp)){
    & $py.Command @($py.Args) -m venv (Join-Path $ProductRoot '.venv')

    if($LASTEXITCODE){
        Stop-Install 'venv creation failed'
    }
}
& $vp -m pip install --disable-pip-version-check -r (Join-Path $RuntimeRoot 'requirements-local.txt');if($LASTEXITCODE){Stop-Install 'dependency install failed'}
$RuntimeScripts = Join-Path $RuntimeRoot 'scripts'
$HealthScript = Join-Path $ProductRoot '.installer_health_check.py'

$HealthScriptContent = @"
import sys

sys.path.insert(0, sys.argv[1])

import fastapi
import pandas
import openpyxl
import reportlab
import pyodbc
import enterprise_sql_gateway
import enterprise_platform_config
import analizador_universal

print("HEALTH:PASS")
"@

try {
    [System.IO.File]::WriteAllText(
        $HealthScript,
        $HealthScriptContent,
        [System.Text.UTF8Encoding]::new($false)
    )

    & $vp $HealthScript $RuntimeScripts
    $healthExit = $LASTEXITCODE
}
finally {
    Remove-Item $HealthScript -Force -ErrorAction SilentlyContinue
}

if($healthExit){
    Stop-Install 'health imports failed'
}
if(-not $SkipSqlCheck){Note 'SQL driver checked through pyodbc; ODBC Driver 18 may be configured later.'};if(-not $SkipAiCheck){Note 'AI_PROVIDER: NOT CONFIGURED is valid; no model download occurs.'}
if($TenantId -and $TenantName -and $AdminUsername){Note "Bootstrap requested for tenant $TenantId/admin $AdminUsername; password is never accepted or logged on command line."}else{Note 'No hardcoded tenant/admin/password. Bootstrap explicitly after install.'}
Note 'INSTALL: PASS'
