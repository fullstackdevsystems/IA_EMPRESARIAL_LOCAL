$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Fail-Validation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

$wrapperPath = Join-Path $root 'InstalarLimpio.ps1'
$installerPath = Join-Path $root 'InstallerR1020C1.ps1'
$metadataPath = Join-Path $root 'RELEASE_METADATA.json'
$manifestPath = Join-Path $root 'MANIFEST_SHA256.json'

$requiredFiles = @(
    $wrapperPath,
    $installerPath,
    $metadataPath,
    $manifestPath
)

foreach ($requiredFile in $requiredFiles) {

    if (-not (
        Test-Path `
            -LiteralPath $requiredFile `
            -PathType Leaf
    )) {
        Fail-Validation "archivo requerido ausente: $requiredFile"
    }
}

$parseTargets = @(
    $wrapperPath,
    $installerPath
)

foreach ($target in $parseTargets) {

    $tokens = $null
    $errors = $null

    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $target,
        [ref]$tokens,
        [ref]$errors
    )

    if (
        $null -ne $errors -and
        $errors.Count -gt 0
    ) {

        Write-Host `
            "ERROR: sintaxis PowerShell invalida: $target" `
            -ForegroundColor Red

        foreach ($parseError in $errors) {
            Write-Host `
                " - $($parseError.Message)" `
                -ForegroundColor Red
        }

        exit 1
    }
}

Write-Host `
    "Sintaxis PowerShell: OK" `
    -ForegroundColor Green

try {

    $metadata = Get-Content `
        -LiteralPath $metadataPath `
        -Raw |
        ConvertFrom-Json
}
catch {
    Fail-Validation "RELEASE_METADATA.json invalido"
}

if ([int]$metadata.schema_version -ne 1) {
    Fail-Validation "schema_version de metadata no soportado"
}

if (
    [string]$metadata.product -ne
    "IA_EMPRESARIAL_LOCAL"
) {
    Fail-Validation "producto de metadata invalido"
}

$metadataFields = @(
    "product_version",
    "release",
    "channel"
)

foreach ($field in $metadataFields) {

    $value = [string]$metadata.$field

    if (
        [string]::IsNullOrWhiteSpace(
            $value
        )
    ) {
        Fail-Validation "metadata incompleta: $field"
    }
}

try {

    $manifest = Get-Content `
        -LiteralPath $manifestPath `
        -Raw |
        ConvertFrom-Json
}
catch {
    Fail-Validation "MANIFEST_SHA256.json invalido"
}

# INSTALLER_ROOT_CONTRACT_VALIDATION_R1027
# The commercial validator must enforce the same managed-root
# contract that InstallerR1020C1.ps1 will consume after validation.
$installerContractText = Get-Content $installerPath -Raw

$installerRootMatch = [regex]::Match(
    $installerContractText,
    '(?ms)\$rootFiles\s*=\s*@\((.*?)\)'
)

if (-not $installerRootMatch.Success) {
    Fail-Validation "Contrato rootFiles del instalador no encontrado"
}

$installerRootFiles = @(
    [regex]::Matches(
        $installerRootMatch.Groups[1].Value,
        "['""]([^'""]+)['""]"
    ) |
    ForEach-Object {
        $_.Groups[1].Value.Replace('\','/')
    }
)

if ($installerRootFiles.Count -lt 1) {
    Fail-Validation "Contrato rootFiles del instalador vacio"
}

$manifestContractPaths = @{}

foreach ($manifestContractEntry in $manifest.files) {
    $manifestContractPath = ([string]$manifestContractEntry.path).Replace('\','/')
    $manifestContractPaths[$manifestContractPath] = $true
}

foreach ($installerRootFile in $installerRootFiles) {

    $installerRootNormalized = $installerRootFile.Replace('\','/')
    $installerRootSource = Join-Path $root $installerRootFile

    if (-not (Test-Path $installerRootSource -PathType Leaf)) {
        Fail-Validation "Archivo requerido por instalador ausente: $installerRootNormalized"
    }

    # MANIFEST_SHA256.json cannot contain its own hash.
    if ($installerRootNormalized -eq 'MANIFEST_SHA256.json') {
        continue
    }

    if (-not $manifestContractPaths.ContainsKey($installerRootNormalized)) {
        Fail-Validation "Archivo requerido por instalador fuera del manifest: $installerRootNormalized"
    }
}
# END_INSTALLER_ROOT_CONTRACT_VALIDATION_R1027
if (
    [string]$manifest.version -ne
    [string]$metadata.release
) {
    Fail-Validation `
        "version de manifest no coincide con release $($metadata.release)"
}

$entries = @(
    $manifest.files
)

if ($entries.Count -eq 0) {
    Fail-Validation "manifest sin archivos"
}

$seen = @{}

foreach ($entry in $entries) {

    $relative = (
        [string]$entry.path
    ).Replace('\','/')

    $expectedHash = (
        [string]$entry.sha256
    ).ToLowerInvariant()

    if (
        [string]::IsNullOrWhiteSpace(
            $relative
        )
    ) {
        Fail-Validation "manifest contiene ruta vacia"
    }

    if (
        [System.IO.Path]::IsPathRooted(
            $relative
        )
    ) {
        Fail-Validation "manifest contiene ruta absoluta: $relative"
    }

    $segments = @(
        $relative.Split('/')
    )

    if ($segments -contains '..') {
        Fail-Validation "manifest contiene traversal: $relative"
    }

    $key = $relative.ToLowerInvariant()

    if ($seen.ContainsKey($key)) {
        Fail-Validation "manifest contiene ruta duplicada: $relative"
    }

    $seen[$key] = $true

    $windowsRelative = `
        $relative.Replace('/','\')

    $fullPath = Join-Path `
        $root `
        $windowsRelative

    if (-not (
        Test-Path `
            -LiteralPath $fullPath `
            -PathType Leaf
    )) {
        Fail-Validation "archivo del manifest ausente: $relative"
    }

    $actualHash = (
        Get-FileHash `
            -LiteralPath $fullPath `
            -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($actualHash -ne $expectedHash) {
        Fail-Validation "hash invalido: $relative"
    }
}

Write-Host `
    "Integridad de paquete: OK" `
    -ForegroundColor Green

Write-Host `
    "Release: $($metadata.release) / $($metadata.channel)" `
    -ForegroundColor Green

exit 0
