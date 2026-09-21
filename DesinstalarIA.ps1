param(
    [string]$InstallPath = (Join-Path $env:LOCALAPPDATA 'IA_Empresarial_Local'),
    [switch]$RemoveBusinessData,
    [switch]$ConfirmRemoveBusinessData,
    [string]$BackupPath,
    [switch]$NonInteractive,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

function Write-Fail {
    param([string]$Code, [string]$Message)
    Write-Host ("UNINSTALL_FAIL|{0}|{1}" -f $Code, $Message) -ForegroundColor Red
    exit 1
}

function Full-Path {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Is-Within {
    param([string]$Candidate, [string]$Parent)
    $c = (Full-Path $Candidate).TrimEnd('\')
    $p = (Full-Path $Parent).TrimEnd('\')
    return $c.Equals($p, [System.StringComparison]::OrdinalIgnoreCase) -or
        $c.StartsWith($p + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Validate-GovernedBackup {
    param([string]$Path, [string]$ProductRoot)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        Write-Fail 'BACKUP_REQUIRED' 'Para eliminar los datos empresariales se requiere un respaldo gobernado previo.'
    }

    $full = Full-Path $Path

    if (Is-Within $full $ProductRoot) {
        Write-Fail 'BACKUP_INSIDE_INSTALL' 'El respaldo debe estar fuera de la carpeta de instalacion.'
    }

    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        Write-Fail 'BACKUP_NOT_FOUND' 'No se encontro el respaldo indicado.'
    }

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
        $zip = [System.IO.Compression.ZipFile]::OpenRead($full)
        try {
            $entry = $zip.GetEntry('backup_manifest.json')
            if ($null -eq $entry) {
                Write-Fail 'BACKUP_MANIFEST_MISSING' 'El archivo no es un respaldo gobernado valido.'
            }

            $reader = New-Object System.IO.StreamReader($entry.Open())
            try {
                $manifestText = $reader.ReadToEnd()
            }
            finally {
                $reader.Dispose()
            }

            $manifest = $manifestText | ConvertFrom-Json

            if ([string]$manifest.format -ne 'IA_EMPRESARIAL_LOCAL_BACKUP') {
                Write-Fail 'BACKUP_FORMAT_INVALID' 'El formato del respaldo no corresponde a IA Empresarial Local.'
            }

            if ([int]$manifest.total_files -lt 1) {
                Write-Fail 'BACKUP_EMPTY' 'El respaldo gobernado no contiene estado persistente.'
            }
        }
        finally {
            $zip.Dispose()
        }
    }
    catch {
        Write-Fail 'BACKUP_INVALID' ('No se pudo validar el respaldo: ' + $_.Exception.Message)
    }

    return $full
}

if ([string]::IsNullOrWhiteSpace($InstallPath)) {
    Write-Fail 'INSTALL_PATH_REQUIRED' 'Debes indicar la carpeta de instalacion.'
}

$ProductRoot = Full-Path $InstallPath
$rootOfPath = [System.IO.Path]::GetPathRoot($ProductRoot)

if ($ProductRoot.TrimEnd('\').Equals($rootOfPath.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Fail 'UNSAFE_INSTALL_PATH' 'No se permite operar sobre la raiz de una unidad.'
}

if (-not (Test-Path -LiteralPath $ProductRoot -PathType Container)) {
    Write-Host 'UNINSTALL: NOTHING_TO_DO'
    exit 0
}

$RuntimeRoot = Join-Path $ProductRoot 'IA_Local'
$Operator = Join-Path $ProductRoot 'OperarIA.ps1'
$validatedBackup = $null

if ($RemoveBusinessData) {
    if (-not $ConfirmRemoveBusinessData) {
        Write-Fail 'CONFIRMATION_REQUIRED' 'La eliminacion de datos requiere -ConfirmRemoveBusinessData.'
    }

    $validatedBackup = Validate-GovernedBackup -Path $BackupPath -ProductRoot $ProductRoot
}

$mode = if ($RemoveBusinessData) { 'REMOVE_ALL' } else { 'PRESERVE_BUSINESS_DATA' }

Write-Host 'IA EMPRESARIAL LOCAL - DESINSTALACION'
Write-Host '------------------------------------'
Write-Host ("InstallPath: {0}" -f $ProductRoot)
Write-Host ("Mode:        {0}" -f $mode)

if ($RemoveBusinessData) {
    Write-Host ("Backup:      {0}" -f $validatedBackup)
}
else {
    Write-Host 'Business data: RETAINED'
    Write-Host 'Retained namespaces include workspace, data, config and legacy governed stores.'
}

if ($ValidateOnly) {
    Write-Host 'VALIDATE-ONLY: PASS'
    exit 0
}

if (Test-Path -LiteralPath $Operator -PathType Leaf) {
    Write-Host 'Stopping managed runtime...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Operator -Action stop -RuntimeRoot $ProductRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'RUNTIME_STOP_FAILED' 'No fue posible detener el runtime administrado de forma segura.'
    }
}

Set-Location -LiteralPath $env:TEMP

if ($RemoveBusinessData) {
    Remove-Item -LiteralPath $ProductRoot -Recurse -Force
    if (Test-Path -LiteralPath $ProductRoot) {
        Write-Fail 'FULL_REMOVE_FAILED' 'La carpeta de instalacion no pudo eliminarse por completo.'
    }

    Write-Host 'BUSINESS_DATA: REMOVED'
    Write-Host ("RECOVERY_BACKUP: {0}" -f $validatedBackup)
    Write-Host 'UNINSTALL: PASS'
    exit 0
}

$managedRootEntries = @(
    '.venv',
    'InstalarLimpio.ps1',
    'InstallerR1020C1.ps1',
    'ValidarInstalador.ps1',
    'OperarIA.ps1',
    'INSTALAR_IA_EMPRESARIAL_LOCAL.bat',
    'DESINSTALAR_IA_EMPRESARIAL_LOCAL.bat',
    'DesinstalarIA.ps1',
    'RELEASE_METADATA.json',
    'MANIFEST_SHA256.json',
    'README.md',
    'LEEME_INSTALACION_LIMPIA.txt',
    'LEEME_DESINSTALACION_Y_RECUPERACION.txt'
)

foreach ($name in $managedRootEntries) {
    $target = Join-Path $ProductRoot $name
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

if (Test-Path -LiteralPath $RuntimeRoot -PathType Container) {
    $managedRuntimeEntries = @(
        'scripts',
        'tests',
        'requirements-local.txt',
        'ACTUALIZAR_IA.bat',
        'INSTALAR_Y_ABRIR.bat'
    )

    foreach ($name in $managedRuntimeEntries) {
        $target = Join-Path $RuntimeRoot $name
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

$noticePath = Join-Path $ProductRoot 'UNINSTALL_RETAINED_DATA.txt'
$noticeLines = @(
    'IA Empresarial Local fue desinstalado conservando los datos empresariales.',
    '',
    'Se conservaron los espacios persistentes existentes bajo IA_Local, incluyendo workspace, data, config y almacenes gobernados heredados.',
    'Para recuperar la aplicacion, vuelve a ejecutar el instalador usando exactamente esta misma ruta de instalacion.',
    '',
    ('InstallPath=' + $ProductRoot),
    ('Fecha=' + (Get-Date -Format o))
)
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllLines($noticePath, $noticeLines, $utf8NoBom)

Write-Host ("RETAINED_DATA_NOTICE: {0}" -f $noticePath)
Write-Host 'BUSINESS_DATA: RETAINED'
Write-Host 'REINSTALL_RECOVERY: USE_SAME_INSTALL_PATH'
Write-Host 'UNINSTALL: PASS'
exit 0
