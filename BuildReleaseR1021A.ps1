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

function Invoke-ReleaseGit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$IndexPath
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = $Arguments
    $startInfo.EnvironmentVariables["GIT_INDEX_FILE"] = $IndexPath

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo

    if (-not $process.Start()) {
        throw "RELEASE_GIT_PROCESS_START_FAILED"
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $process.WaitForExit()

    $exitCode = $process.ExitCode
    $stdout = [string]$stdoutTask.Result
    $stderr = [string]$stderrTask.Result

    $process.Dispose()

    return [pscustomobject]@{
        ExitCode = $exitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Write-GitCheckoutMaterialized {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $normalized = $RelativePath.Replace('\', '/')

    $tempIndex = Join-Path `
        $env:TEMP `
        (".ia_release_index_" + [Guid]::NewGuid().ToString("N"))

    $tempCheckoutPath = $null

    try {
        $quotedRoot = '"' + $Root.Replace('"', '\"') + '"'
        $quotedPath = '"' + $normalized.Replace('"', '\"') + '"'

        $readTree = Invoke-ReleaseGit `
            -Arguments ("-C {0} read-tree HEAD" -f $quotedRoot) `
            -IndexPath $tempIndex

        if ($readTree.ExitCode -ne 0) {
            throw (
                "ISOLATED_INDEX_READ_TREE_FAILED: " +
                $normalized +
                " | " +
                $readTree.Stderr.Trim()
            )
        }

        $stage = Invoke-ReleaseGit `
            -Arguments ("-C {0} add --all" -f $quotedRoot) `
            -IndexPath $tempIndex

        if ($stage.ExitCode -ne 0) {
            throw (
                "ISOLATED_INDEX_STAGE_FAILED: " +
                $normalized +
                " | " +
                $stage.Stderr.Trim()
            )
        }

        $checkout = Invoke-ReleaseGit `
            -Arguments (
                "-C {0} checkout-index --temp -- {1}" -f
                $quotedRoot,
                $quotedPath
            ) `
            -IndexPath $tempIndex

        if ($checkout.ExitCode -ne 0) {
            throw (
                "ISOLATED_INDEX_CHECKOUT_FAILED: " +
                $normalized +
                " | " +
                $checkout.Stderr.Trim()
            )
        }

        $checkoutLines = @(
            $checkout.Stdout -split "`r?`n" |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace([string]$_)
            }
        )

        if ($checkoutLines.Count -lt 1) {
            throw "ISOLATED_INDEX_CHECKOUT_EMPTY: $normalized"
        }

        $checkoutLine = [string]$checkoutLines[0]
        $tempName = ($checkoutLine -split "`t", 2)[0].Trim()

        if ([string]::IsNullOrWhiteSpace($tempName)) {
            throw "ISOLATED_INDEX_TEMP_NAME_EMPTY: $normalized"
        }

        $tempCheckoutPath = Join-Path $Root $tempName

        if (-not (
            Test-Path `
                -LiteralPath $tempCheckoutPath `
                -PathType Leaf
        )) {
            throw "ISOLATED_INDEX_TEMP_FILE_MISSING: $normalized"
        }

        [System.IO.File]::Copy(
            [System.IO.Path]::GetFullPath($tempCheckoutPath),
            [System.IO.Path]::GetFullPath($Destination),
            $true
        )
    }
    finally {
        if (
            -not [string]::IsNullOrWhiteSpace(
                [string]$tempCheckoutPath
            ) -and
            (Test-Path -LiteralPath $tempCheckoutPath)
        ) {
            Remove-Item `
                -LiteralPath $tempCheckoutPath `
                -ErrorAction SilentlyContinue
        }

        if (Test-Path -LiteralPath $tempIndex) {
            Remove-Item `
                -LiteralPath $tempIndex `
                -ErrorAction SilentlyContinue
        }
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

    # RELEASE_METADATA.json is supplied explicitly by the release authority.
    # Every other manifested file uses the same isolated Git-index +
    # checkout-index materialization model as tools/regenerate_manifest.py.
    if ($relative -eq "RELEASE_METADATA.json") {
        [System.IO.File]::Copy(
            [System.IO.Path]::GetFullPath($source),
            [System.IO.Path]::GetFullPath($destination),
            $true
        )
    }
    else {
        Write-GitCheckoutMaterialized `
            -RelativePath $relative `
            -Destination $destination
    }

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

# El manifest mismo forma parte del paquete aunque no se liste a sÃ­ mismo.
Copy-Item `
    $ManifestPath `
    (Join-Path $stageRoot "MANIFEST_SHA256.json") `
    -Force

# Archivos de entrada necesarios para instalaciÃ³n/operaciÃ³n.
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
