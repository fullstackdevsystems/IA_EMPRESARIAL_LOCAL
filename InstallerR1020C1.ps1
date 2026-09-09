[CmdletBinding()]
param([string]$InstallPath=(Join-Path $env:LOCALAPPDATA 'IA_Empresarial_Local'),[switch]$NonInteractive,[string]$TenantId,[string]$TenantName,[string]$AdminUsername,[switch]$SkipSqlCheck,[switch]$SkipAiCheck,[switch]$ValidateOnly)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path;$releaseMetadataPath=Join-Path $root 'RELEASE_METADATA.json';if(-not(Test-Path $releaseMetadataPath -PathType Leaf)){throw 'RELEASE_METADATA_MISSING'};$releaseMetadata=Get-Content $releaseMetadataPath -Raw|ConvertFrom-Json;$productVersion=[string]$releaseMetadata.product_version;$release=[string]$releaseMetadata.release;$channel=[string]$releaseMetadata.channel;$source=Join-Path $root 'IA_Local';$log=Join-Path $root ("logs\installer-{0}.log" -f $release)
function Note($x){if($ValidateOnly){Write-Host $x;return};New-Item -ItemType Directory -Force (Split-Path $log)|Out-Null;Add-Content $log "$(Get-Date -Format o) $x";Write-Host $x}
function Stop-Install($x){Note "FAIL: $x";throw $x}

$backupRoot = $null
$previousScripts = $null
$freshMetadataBootstrap = $null

function Cleanup-FreshMetadataBootstrap {
    if (
        $freshMetadataBootstrap -and
        (Test-Path $freshMetadataBootstrap -PathType Leaf)
    ) {
        Remove-Item `
            -LiteralPath $freshMetadataBootstrap `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

function Cleanup-FreshInstallArtifacts {
    if ($existingInstall) {
        return
    }

    Cleanup-FreshMetadataBootstrap

    if (
        -not $runtimeRootPreExisted -and
        (Test-Path $RuntimeRoot)
    ) {
        Remove-Item `
            -LiteralPath $RuntimeRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }

    if (
        -not $venvPreExisted -and
        (Test-Path $venvRoot)
    ) {
        Remove-Item `
            -LiteralPath $venvRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }

    if (
        -not $productRootPreExisted -and
        (Test-Path $ProductRoot)
    ) {

        $remaining = @(
            Get-ChildItem `
                -LiteralPath $ProductRoot `
                -Force `
                -ErrorAction SilentlyContinue
        )

        if ($remaining.Count -eq 0) {
            Remove-Item `
                -LiteralPath $ProductRoot `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }
}

function Restore-PreviousManagedScripts {
    if (
        $previousScripts -and
        (Test-Path $previousScripts)
    ) {
        Remove-Item `
            (Join-Path $RuntimeRoot 'scripts') `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue

        Move-Item `
            $previousScripts `
            (Join-Path $RuntimeRoot 'scripts') `
            -Force
    }
}

function Cleanup-ManagedScriptBackup {
    if (
        $backupRoot -and
        (Test-Path $backupRoot)
    ) {
        Remove-Item `
            -LiteralPath $backupRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

Note "Installer starting - product $productVersion / release $release / channel $channel"
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
$manifestPath=Join-Path $root 'MANIFEST_SHA256.json';$manifestData=$null;if(Test-Path $manifestPath){$manifestData=Get-Content $manifestPath -Raw|ConvertFrom-Json;foreach($e in $manifestData.files){$f=Join-Path $root ([string]$e.path).Replace('/','\');if(-not(Test-Path $f)){Stop-Install "Manifest missing $($e.path)"};if((Get-FileHash $f -Algorithm SHA256).Hash -ne $e.sha256){Stop-Install "Manifest mismatch $($e.path)"}}}
if($ValidateOnly){Note 'VALIDATE-ONLY: PASS';exit 0}
$ProductRoot = [System.IO.Path]::GetFullPath($InstallPath)
$RuntimeRoot = Join-Path $ProductRoot 'IA_Local'

$productRootPreExisted = Test-Path `
    $ProductRoot `
    -PathType Container

$runtimeRootPreExisted = Test-Path `
    $RuntimeRoot `
    -PathType Container

$venvRoot = Join-Path `
    $ProductRoot `
    '.venv'

$venvPreExisted = Test-Path `
    $venvRoot `
    -PathType Container

try {
    New-Item -ItemType Directory -Force $ProductRoot | Out-Null
}
catch {
    Stop-Install 'Install path not writable'
}

${existingInstall} = Test-Path (Join-Path $RuntimeRoot 'scripts')

if (
    $runtimeRootPreExisted -and
    -not $existingInstall
) {
    Stop-Install 'RUNTIME_ROOT_CONFLICT'
}

if (-not $existingInstall) {
    Note 'INSTALL MODE: FRESH'

    try {
        New-Item `
            -ItemType Directory `
            -Force `
            $RuntimeRoot |
            Out-Null

        Copy-Item `
            (Join-Path $source '*') `
            $RuntimeRoot `
            -Recurse `
            -Force

        # FRESH_METADATA_BOOTSTRAP
        # analizador_universal requires canonical release identity
        # at ProductRoot during import health validation. This copy
        # is temporary and is removed before the managed root-file
        # transaction begins.
        $freshMetadataBootstrap = Join-Path `
            $ProductRoot `
            'RELEASE_METADATA.json'

        Copy-Item `
            -LiteralPath $releaseMetadataPath `
            -Destination $freshMetadataBootstrap `
            -Force

        Note 'FRESH_METADATA_BOOTSTRAP: canonical release metadata prepared for health validation'
    }
    catch {
        Cleanup-FreshInstallArtifacts
        Stop-Install 'fresh payload deployment failed'
    }
}
else {
    Note 'INSTALL MODE: UPGRADE'
    $backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ia-update-" + [guid]::NewGuid().ToString())
    $stagedScripts = Join-Path $backupRoot 'new_scripts'
    $previousScripts = Join-Path $backupRoot 'previous_scripts'
    try {
        if (-not $manifestData) { throw 'UPGRADE manifest data unavailable' }
        New-Item -ItemType Directory -Force $backupRoot | Out-Null
        $stagedCount = 0
        foreach ($entry in $manifestData.files) {
            $relative = [string]$entry.path
            if ($relative -notlike 'IA_Local/*' -or $relative -notlike 'IA_Local/scripts/*') { continue }
            $from = Join-Path $root $relative
            $suffix = $relative.Substring('IA_Local/scripts/'.Length)
            $to = Join-Path $stagedScripts $suffix
            New-Item -ItemType Directory -Force (Split-Path $to -Parent) | Out-Null
            Copy-Item $from $to -Force
            $stagedCount++
        }
        if ($stagedCount -lt 1 -or -not (Test-Path $stagedScripts) -or -not (Test-Path (Join-Path $stagedScripts 'analizador_universal.py') -PathType Leaf)) {
            throw 'UPGRADE staged runtime incomplete'
        }
        Move-Item (Join-Path $RuntimeRoot 'scripts') $previousScripts -Force
        New-Item -ItemType Directory -Force (Join-Path $RuntimeRoot 'scripts') | Out-Null
        Copy-Item (Join-Path $stagedScripts '*') (Join-Path $RuntimeRoot 'scripts') -Recurse -Force
    }
    catch {
        $runtimeDeploymentError = $_

        Restore-PreviousManagedScripts
        Cleanup-ManagedScriptBackup

        Stop-Install (
            "UPGRADE runtime deployment failed: " +
            $runtimeDeploymentError.Exception.Message +
            "; previous managed runtime scripts restored"
        )
    }
}

foreach ($d in 'config','data','logs','workspace','Reportes') {
    New-Item -ItemType Directory -Force (Join-Path $RuntimeRoot $d) | Out-Null
}

$rootFiles = @(
    'OperarIA.ps1',
    'LEEME_INSTALACION_LIMPIA.txt',
    'MANIFEST_SHA256.json',
    'RELEASE_METADATA.json',
    'InstallerR1020C1.ps1',
    'InstalarLimpio.ps1',
    'INSTALAR_IA_EMPRESARIAL_LOCAL.bat',
    'ValidarInstalador.ps1'
)

$vp = Join-Path $ProductRoot '.venv\Scripts\python.exe'

if(-not(Test-Path $vp)){
    & $py.Command @($py.Args) -m venv (Join-Path $ProductRoot '.venv')

    if($LASTEXITCODE){
        Cleanup-FreshInstallArtifacts
        Restore-PreviousManagedScripts
        Cleanup-ManagedScriptBackup
        Stop-Install 'venv creation failed'
    }
}
& $vp -m pip install `
    --disable-pip-version-check `
    -r (Join-Path $RuntimeRoot 'requirements-local.txt')

if($LASTEXITCODE){
    Cleanup-FreshInstallArtifacts
    Restore-PreviousManagedScripts
    Cleanup-ManagedScriptBackup
    Stop-Install 'dependency install failed'
}
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
    Cleanup-FreshInstallArtifacts
    Restore-PreviousManagedScripts
    Cleanup-ManagedScriptBackup
    Stop-Install 'health imports failed'
}

# The fresh-only metadata copy existed solely so runtime
# imports could resolve canonical release identity. Remove
# it now so the complete managed root transaction remains
# authoritative and can still treat metadata as a new file
# during a clean install.
Cleanup-FreshMetadataBootstrap

# Managed root files are deployed only after runtime health
# validation succeeds. They are staged and rolled back as
# one controlled root-file transaction.
$rootUpdateBackup = Join-Path `
    ([System.IO.Path]::GetTempPath()) `
    ("ia-root-update-" + [guid]::NewGuid().ToString())

$stagedRoot = Join-Path `
    $rootUpdateBackup `
    'new_root'

$previousRoot = Join-Path `
    $rootUpdateBackup `
    'previous_root_files'

$newRootFiles = @()

try {
    New-Item `
        -ItemType Directory `
        -Force `
        $stagedRoot |
        Out-Null

    New-Item `
        -ItemType Directory `
        -Force `
        $previousRoot |
        Out-Null

    # Stage every managed root file from the verified
    # release package before changing ProductRoot.
    foreach ($rootFile in $rootFiles) {

        $sourceFile = Join-Path `
            $root `
            $rootFile

        if (-not (
            Test-Path `
                $sourceFile `
                -PathType Leaf
        )) {
            throw "ROOT_FILE_SOURCE_MISSING: $rootFile"
        }

        $stagedFile = Join-Path `
            $stagedRoot `
            $rootFile

        Copy-Item `
            $sourceFile `
            $stagedFile `
            -Force
    }

    # Preserve the complete previous managed root-file
    # set before installing any new root file.
    foreach ($rootFile in $rootFiles) {

        $liveFile = Join-Path `
            $ProductRoot `
            $rootFile

        $previousFile = Join-Path `
            $previousRoot `
            $rootFile

        if (
            Test-Path `
                $liveFile `
                -PathType Leaf
        ) {
            Copy-Item `
                $liveFile `
                $previousFile `
                -Force
        }
        else {
            $newRootFiles += $rootFile
        }
    }

    # Deploy only from the fully prepared staging area.
    foreach ($rootFile in $rootFiles) {

        $stagedFile = Join-Path `
            $stagedRoot `
            $rootFile

        $liveFile = Join-Path `
            $ProductRoot `
            $rootFile

        Copy-Item `
            $stagedFile `
            $liveFile `
            -Force
    }
}
catch {
    $rootDeploymentError = $_

    # Restore every root file that existed before.
    foreach ($rootFile in $rootFiles) {

        $previousFile = Join-Path `
            $previousRoot `
            $rootFile

        $liveFile = Join-Path `
            $ProductRoot `
            $rootFile

        if (
            Test-Path `
                $previousFile `
                -PathType Leaf
        ) {
            Copy-Item `
                $previousFile `
                $liveFile `
                -Force
        }
        elseif (
            $newRootFiles -contains $rootFile
        ) {
            Remove-Item `
                $liveFile `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }

    Cleanup-FreshInstallArtifacts
    Restore-PreviousManagedScripts
    Cleanup-ManagedScriptBackup

    Stop-Install (
        "UPGRADE root deployment failed: " +
        $rootDeploymentError.Exception.Message +
        "; previous managed root files and scripts restored"
    )
}
finally {
    Remove-Item `
        $rootUpdateBackup `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue
}

# Managed scripts and managed root files have now
# completed successfully. The previous scripts can
# finally be discarded.
Cleanup-ManagedScriptBackup

if(-not $SkipSqlCheck){Note 'SQL driver checked through pyodbc; ODBC Driver 18 may be configured later.'};if(-not $SkipAiCheck){Note 'AI_PROVIDER: NOT CONFIGURED is valid; no model download occurs.'}
if($TenantId -and $TenantName -and $AdminUsername){Note "Bootstrap requested for tenant $TenantId/admin $AdminUsername; password is never accepted or logged on command line."}else{Note 'No hardcoded tenant/admin/password. Bootstrap explicitly after install.'}
Note 'INSTALL: PASS'
