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

# Defense in depth: a commercial build never trusts a hand-edited manifest to
# reintroduce development, regression, or secret-display utilities.
$forbiddenManifestPatterns = @(
    '^IA_Local/tests/',
    '^IA_Local/scripts/(run_.*tests.*|prueba_regresion.*)\.py$',
    '^IA_Local/MOSTRAR_TOKEN_LOCAL\.bat$',
    '^IA_Local/(LEEME_PRIMERO|README_INSTALACION|GUIA_PRUEBAS_MEMORIA_RAG_V8|ARQUITECTURA_MEMORIA_RAG_V8|PROMPT_).*'
)

foreach ($item in $manifest.files) {
    $relative = ([string]$item.path).Replace('\', '/')
    foreach ($pattern in $forbiddenManifestPatterns) {
        if ($relative -match $pattern) {
            throw "FORBIDDEN_COMMERCIAL_MANIFEST_CONTENT: $relative"
        }
    }
}

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

function Write-GitHeadBlob {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $normalized = $RelativePath.Replace('\', '/')
    $spec = "HEAD:$normalized"

    $destinationDir = Split-Path $Destination -Parent

    if (-not (Test-Path $destinationDir)) {
        New-Item `
            -ItemType Directory `
            -Force `
            -Path $destinationDir |
            Out-Null
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $escapedSpec = $spec.Replace('"', '\"')
    $startInfo.Arguments = "cat-file blob `"$escapedSpec`""

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo

    if (-not $process.Start()) {
        throw "GIT_BLOB_PROCESS_START_FAILED: $normalized"
    }

    $stderrTask = $process.StandardError.ReadToEndAsync()

    $output = [System.IO.File]::Open(
        $Destination,
        [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )

    try {
        $process.StandardOutput.BaseStream.CopyTo(
            $output
        )
    }
    finally {
        $output.Dispose()
    }

    $process.WaitForExit()
    $stderr = $stderrTask.Result

    if ($process.ExitCode -ne 0) {
        Remove-Item `
            -LiteralPath $Destination `
            -Force `
            -ErrorAction SilentlyContinue

        $message = "GIT_HEAD_BLOB_READ_FAILED: $normalized | $($stderr.Trim())"
        throw $message
    }
}

$manifestPathSet = @{}

foreach ($item in $manifest.files) {
    $relative = ([string]$item.path).Replace('\', '/')
    $destination = Join-Path $stageRoot $relative
    $manifestPathSet[$relative] = $true

    $destinationDir = Split-Path $destination -Parent

    if (-not (Test-Path $destinationDir)) {
        New-Item `
            -ItemType Directory `
            -Force `
            -Path $destinationDir |
            Out-Null
    }

    if ($relative -eq "RELEASE_METADATA.json") {
        $source = $ReleaseMetadataPath
    }
    else {
        $source = Join-Path $Root $relative
    }

    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "PACKAGE_SOURCE_MISSING: $relative"
    }

    # R10.27 release authority is the exact byte representation from the
    # controlled clean checkout. This preserves .gitattributes materialization
    # such as eol=crlf/eol=lf instead of reverting to normalized Git blobs.
    [System.IO.File]::Copy(
        [System.IO.Path]::GetFullPath($source),
        [System.IO.Path]::GetFullPath($destination),
        $true
    )

    if (-not (Test-Path $destination -PathType Leaf)) {
        throw "PACKAGE_MATERIALIZATION_MISSING: $relative"
    }

    $expectedHash = ([string]$item.sha256).ToLowerInvariant()
    $actualHash = (
        Get-FileHash `
            -LiteralPath $destination `
            -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($actualHash -ne $expectedHash) {
        throw "PACKAGE_MATERIALIZED_HASH_MISMATCH: $relative"
    }

    $expectedSize = [long]$item.size
    $actualSize = (
        Get-Item `
            -LiteralPath $destination
    ).Length

    if ($actualSize -ne $expectedSize) {
        throw "PACKAGE_MATERIALIZED_SIZE_MISMATCH: $relative"
    }
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
    "LEEME_INSTALACION_LIMPIA.txt",
    "ValidarInstalador.ps1",
    "RELEASE_METADATA.json",
    "DesinstalarIA.ps1",
    "DESINSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "LEEME_DESINSTALACION_Y_RECUPERACION.txt",
    "IA_Local/VERSION.txt",
    "IA_Local/requirements-local.txt"
)

foreach ($relative in $requiredRootFiles) {
    $normalized = $relative.Replace('\', '/')
    $destination = Join-Path $stageRoot $relative

    if (-not $manifestPathSet.ContainsKey($normalized)) {
        throw "REQUIRED_RELEASE_FILE_NOT_MANIFESTED: $normalized"
    }

    if (-not (Test-Path $destination -PathType Leaf)) {
        throw "REQUIRED_RELEASE_FILE_NOT_MATERIALIZED: $normalized"
    }
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
