param(
    [string]$OutputDir = "$PSScriptRoot\release",
    [string]$ManifestPath,
    [string]$ReleaseMetadataPath
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = [System.IO.Path]::Combine(
        $Root,
        "MANIFEST_SHA256.json"
    )
}

if (-not (Test-Path $ManifestPath -PathType Leaf)) {
    throw "MANIFEST_NOT_FOUND"
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($ReleaseMetadataPath)) {
    $ReleaseMetadataPath = [System.IO.Path]::Combine(
        $Root,
        "RELEASE_METADATA.json"
    )
}

if (-not (Test-Path $ReleaseMetadataPath -PathType Leaf)) {
    throw "RELEASE_METADATA_MISSING"
}

$releaseMetadata = Get-Content $ReleaseMetadataPath -Raw | ConvertFrom-Json

$product = [string]$releaseMetadata.product
$productVersion = [string]$releaseMetadata.product_version
$release = [string]$releaseMetadata.release
$channel = [string]$releaseMetadata.channel

if ([string]::IsNullOrWhiteSpace($product)) {
    throw "RELEASE_PRODUCT_INVALID"
}

if ([string]::IsNullOrWhiteSpace($productVersion)) {
    throw "RELEASE_PRODUCT_VERSION_INVALID"
}

if ([string]::IsNullOrWhiteSpace($release)) {
    throw "RELEASE_ID_INVALID"
}

if ([string]::IsNullOrWhiteSpace($channel)) {
    throw "RELEASE_CHANNEL_INVALID"
}

if ([string]$manifest.version -ne $release) {
    throw "MANIFEST_RELEASE_METADATA_MISMATCH"
}

$version = $release

$sha = (
    git -C $Root rev-parse --short=12 HEAD
).Trim()

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sha)) {
    throw "GIT_SHA_UNAVAILABLE"
}

$dirty = git -C $Root status --porcelain

if ($dirty) {
    throw "WORKING_TREE_NOT_CLEAN"
}

$packageName = "IA_EMPRESARIAL_LOCAL_${version}_${sha}"
$stageRoot = Join-Path $OutputDir $packageName
$zipPath = Join-Path $OutputDir "$packageName.zip"

if (Test-Path $stageRoot) {
    Remove-Item $stageRoot -Recurse -Force
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

foreach ($item in $manifest.files) {
    $relative = [string]$item.path
    if ($relative -eq "RELEASE_METADATA.json") {
        $source = $ReleaseMetadataPath
    }
    else {
        $source = Join-Path $Root $relative
    }
    $destination = Join-Path $stageRoot $relative

    if (-not (Test-Path $source -PathType Leaf)) {
        throw "PACKAGE_SOURCE_MISSING: $relative"
    }

    $destinationDir = Split-Path $destination -Parent

    if (-not (Test-Path $destinationDir)) {
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    }

    Copy-Item $source $destination -Force
}

# El manifest mismo forma parte del paquete aunque no se liste a sí mismo.
Copy-Item `
    $ManifestPath `
    (Join-Path $stageRoot "MANIFEST_SHA256.json") `
    -Force

# Archivos de entrada necesarios para instalación/operación.
$requiredRootFiles = @(
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "InstalarLimpio.ps1",
    "InstallerR1020C1.ps1",
    "OperarIA.ps1",
    "LEEME_INSTALACION_LIMPIA.txt"
)

foreach ($relative in $requiredRootFiles) {
    $source = Join-Path $Root $relative
    $destination = Join-Path $stageRoot $relative

    if (-not (Test-Path $source -PathType Leaf)) {
        throw "REQUIRED_RELEASE_FILE_MISSING: $relative"
    }

    Copy-Item $source $destination -Force
}

# Exclusiones defensivas.
$forbiddenPatterns = @(
    "\.git",
    "\.venv",
    "__pycache__",
    "diagnostics_",
    ".env",
    ".pyc"
)

$packagedFiles = Get-ChildItem $stageRoot -Recurse -File

foreach ($file in $packagedFiles) {
    $relative = $file.FullName.Substring($stageRoot.Length).TrimStart("\","/")

    # Dentro de logs solo se permite el placeholder .keep.
    if (
        $relative -like "IA_Local\logs\*" -and
        $relative -ne "IA_Local\logs\.keep"
    ) {
        throw "FORBIDDEN_RELEASE_LOG_CONTENT: $relative"
    }

    foreach ($pattern in $forbiddenPatterns) {
        if ($relative -match [regex]::Escape($pattern)) {
            throw "FORBIDDEN_RELEASE_CONTENT: $relative"
        }
    }
}

Compress-Archive `
    -Path (Join-Path $stageRoot "*") `
    -DestinationPath $zipPath `
    -CompressionLevel Optimal `
    -Force

$zipHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()

$result = [ordered]@{
    package = $packageName
    version = $version
    git_sha = $sha
    files = $packagedFiles.Count
    zip = $zipPath
    sha256 = $zipHash
}

$result | ConvertTo-Json

Write-Host ""
Write-Host "$($release.ToUpper()) RELEASE PACKAGE BUILD: PASS" -ForegroundColor Green
