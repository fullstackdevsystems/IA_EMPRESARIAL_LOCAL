param(
    [ValidateSet("start","stop","restart","status","health","validate","diagnostics","diagnostic-bundle","configure","configuration","configure-sql","configure-ai","backup","restore")]
    [string]$Action = "status",

    [string]$RuntimeRoot = $PSScriptRoot,

    [string]$HostAddress = "127.0.0.1",

    [ValidateRange(1,65535)]
    [int]$Port = 8090,

    [string]$TenantId,
    [string]$TenantName,
    [string]$AdminUserId,
    [string]$AdminUsername,
    [string]$AdminDisplayName,
    [string]$ConnectionId,
    [string]$Server,
    [string]$Database,
    [string]$AuthMode = "WINDOWS_INTEGRATED",
    [string[]]$AllowedSchemas,
    [string[]]$AllowedTables,
    [string]$SecretReference,
    [string]$SqlUsername,
    [string]$Provider,
    [string]$BaseUrl,
    [string]$Model,
    [int]$Timeout = 30,
    [string]$BackupPath,
    [string]$RestorePath
)

$ErrorActionPreference = "Stop"

$ProductRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$RuntimeRoot = Join-Path $ProductRoot "IA_Local"

$Python   = Join-Path $ProductRoot ".venv\Scripts\python.exe"
$Scripts  = Join-Path $RuntimeRoot "scripts"
$Analyzer = Join-Path $Scripts "analizador_universal.py"
$Onboarding = Join-Path $Scripts "enterprise_onboarding.py"
$BackupEngine = Join-Path $Scripts "enterprise_backup_recovery.py"
$Logs     = Join-Path $RuntimeRoot "logs"

$PidFile  = Join-Path $Logs "analizador.pid"
$OutLog   = Join-Path $Logs "analizador.out.log"
$ErrLog   = Join-Path $Logs "analizador.err.log"

$BaseUrl    = "http://${HostAddress}:${Port}"
$VersionUrl = "$BaseUrl/version"
$LiveUrl    = "$BaseUrl/api/enterprise/health/live"
$ReadyUrl   = "$BaseUrl/api/enterprise/health/ready"

function Test-RuntimeInstallation {
    $checks = [ordered]@{
        runtime_root = Test-Path $RuntimeRoot
        python       = Test-Path $Python
        analyzer     = Test-Path $Analyzer
        scripts      = Test-Path $Scripts
    }

    return [pscustomobject]$checks
}

function Test-RuntimePort {
    param([int]$TargetPort)

    $client = $null

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect(
            "127.0.0.1",
            $TargetPort,
            $null,
            $null
        )

        if (-not $async.AsyncWaitHandle.WaitOne(700)) {
            return $false
        }

        $client.EndConnect($async)

        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        if ($client) {
            $client.Close()
        }
    }
}

function Get-PortListenerPid {
    param([int]$TargetPort)

    try {
        $listener = Get-NetTCPConnection `
            -LocalPort $TargetPort `
            -State Listen `
            -ErrorAction Stop |
            Select-Object -First 1

        if ($listener) {
            return [int]$listener.OwningProcess
        }
    }
    catch {}

    return $null
}

function Get-OwnedAnalyzerProcess {
    param([int]$ProcessId)

    if (-not $ProcessId) {
        return $null
    }

    try {
        $p = Get-CimInstance Win32_Process `
            -Filter "ProcessId=$ProcessId" `
            -ErrorAction Stop

        if (-not $p) {
            return $null
        }

        $command = [string]$p.CommandLine

        if (
            $command -like "*analizador_universal.py*" -and
            $command -like "*IA_EMPRESARIAL_LOCAL*"
        ) {
            return $p
        }
    }
    catch {}

    return $null
}

function Get-RegisteredPid {
    if (-not (Test-Path $PidFile)) {
        return $null
    }

    try {
        $value = (Get-Content $PidFile -Raw).Trim()

        if ($value -match '^\d+$') {
            return [int]$value
        }
    }
    catch {}

    return $null
}

function Get-RegisteredRuntimeProcess {
    $runtimePid = Get-RegisteredPid

    if (-not $runtimePid) {
        return $null
    }

    return Get-OwnedAnalyzerProcess -ProcessId $runtimePid
}

function Repair-StalePid {
    if (-not (Test-Path $PidFile)) {
        return
    }

    $runtimePid = Get-RegisteredPid

    if (-not $runtimePid) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    $process = Get-Process -Id $runtimePid -ErrorAction SilentlyContinue

    if (-not $process) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    $ownedProcess = Get-RegisteredRuntimeProcess

    if (-not $ownedProcess) {
        Write-Host (
            "ADVERTENCIA: el PID registrado $runtimePid no corresponde " +
            "al runtime esperado. No se detendra ese proceso."
        ) -ForegroundColor Yellow

        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Get-RuntimeHealth {
    $result = [ordered]@{
        ok      = $false
        live    = $false
        ready   = $false
        version = $null
        motor   = $null
        url     = $BaseUrl
    }

    try {
        $v = Invoke-RestMethod `
            -Uri $VersionUrl `
            -TimeoutSec 4

        $result.version = $v.version
        $result.motor   = $v.motor
    }
    catch {}

    try {
        $h = Invoke-RestMethod `
            -Uri $LiveUrl `
            -TimeoutSec 4

        $result.live = (
            $h.ok -eq $true -or
            $h.status -in @(
                "ok",
                "healthy",
                "live",
                "PASS"
            )
        )
    }
    catch {}

    try {
        $r = Invoke-RestMethod `
            -Uri $ReadyUrl `
            -TimeoutSec 6

        $result.ready = (
            $r.ok -eq $true -or
            $r.status -in @(
                "ok",
                "healthy",
                "ready",
                "PASS"
            )
        )
    }
    catch {}

    $result.ok = $result.live -and $result.ready

    return [pscustomobject]$result
}

function Show-RuntimeStatus {
    Repair-StalePid

    $runtimePid = Get-RegisteredPid
    $owned = Get-RegisteredRuntimeProcess
    $portOpen = Test-RuntimePort $Port
    $health = Get-RuntimeHealth

    if ($owned -and $health.live) {
        $state = "RUNNING"
    }
    elseif ($portOpen -and $health.live) {
        $state = "RUNNING_UNMANAGED"
    }
    elseif ($owned -or $portOpen) {
        $state = "DEGRADED"
    }
    else {
        $state = "STOPPED"
    }

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host " IA EMPRESARIAL LOCAL - RUNTIME STATUS" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    Write-Host "Estado:     $state"
    Write-Host (
        "PID:        " +
        $(if ($runtimePid) { $runtimePid } else { "N/A" })
    )
    Write-Host "Host:       $HostAddress"
    Write-Host "Puerto:     $Port"
    Write-Host (
        "Liveness:   " +
        $(if ($health.live) { "PASS" } else { "FAIL" })
    )
    Write-Host (
        "Readiness:  " +
        $(if ($health.ready) { "PASS" } else { "FAIL" })
    )
    Write-Host (
        "Version:    " +
        $(if ($health.version) { $health.version } else { "N/A" })
    )
    Write-Host (
        "Motor:      " +
        $(if ($health.motor) { $health.motor } else { "N/A" })
    )
    Write-Host "Runtime:    $RuntimeRoot"
    Write-Host "URL:        $BaseUrl"
    Write-Host ""

    return [pscustomobject]@{
        state  = $state
        pid    = $runtimePid
        health = $health
    }
}

function Test-RuntimeConfiguration {
    $installation = Test-RuntimeInstallation

    Write-Host ""
    Write-Host "IA EMPRESARIAL LOCAL - VALIDACION" -ForegroundColor Cyan
    Write-Host "---------------------------------"

    Write-Host "Runtime root: $RuntimeRoot"

    foreach ($item in $installation.psobject.Properties) {
        Write-Host (
            "{0}: {1}" -f
            $item.Name,
            $(if ($item.Value) { "PASS" } else { "FAIL" })
        )
    }

    $pythonPass = $false

    if ($installation.python) {
        try {
            $version = & $Python --version 2>&1

            if ($LASTEXITCODE -eq 0) {
                $pythonPass = $true
                Write-Host "Python: PASS ($version)"
            }
        }
        catch {}
    }

    if (-not $pythonPass) {
        Write-Host "Python: FAIL"
    }

    $importsPass = $false

    if ($pythonPass) {
        try {
            & $Python -c "import fastapi,uvicorn; print('IMPORTS_PASS')" |
                Out-Null

            if ($LASTEXITCODE -eq 0) {
                $importsPass = $true
                Write-Host "Imports FastAPI/Uvicorn: PASS"
            }
        }
        catch {}
    }

    if (-not $importsPass) {
        Write-Host "Imports FastAPI/Uvicorn: FAIL"
    }

    $allPass = (
        $installation.runtime_root -and
        $installation.python -and
        $installation.analyzer -and
        $installation.scripts -and
        $pythonPass -and
        $importsPass
    )

    if ($allPass) {
        Write-Host ""
        Write-Host "VALIDATION: PASS" -ForegroundColor Green
        return $true
    }

    Write-Host ""
    Write-Host "VALIDATION: FAIL" -ForegroundColor Red
    return $false
}

function Rotate-RuntimeLog {
    param(
        [string]$Path,
        [int64]$MaxBytes = 5MB,
        [int]$Keep = 3
    )

    if (-not (Test-Path $Path)) {
        return
    }

    $file = Get-Item $Path -ErrorAction SilentlyContinue

    if (-not $file -or $file.Length -lt $MaxBytes) {
        return
    }

    for ($i = $Keep - 1; $i -ge 1; $i--) {
        $source = "$Path.$i"
        $target = "$Path.$($i + 1)"

        if (Test-Path $source) {
            Move-Item `
                -Path $source `
                -Destination $target `
                -Force
        }
    }

    Move-Item `
        -Path $Path `
        -Destination "$Path.1" `
        -Force
}

function Protect-DiagnosticText {
    param([string]$Text)

    if ($null -eq $Text) {
        return ""
    }

    $safe = $Text

    $patterns = @(
        '(?i)(authorization\s*:\s*bearer\s+)[^\s]+',
        '(?i)(bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*',
        '(?i)(password\s*[=:]\s*)[^\s;]+',
        '(?i)(pwd\s*[=:]\s*)[^\s;]+',
        '(?i)(secret\s*[=:]\s*)[^\s;]+',
        '(?i)(token\s*[=:]\s*)[^\s;]+'
    )

    foreach ($pattern in $patterns) {
        $safe = [regex]::Replace(
            $safe,
            $pattern,
            '${1}[REDACTED]'
        )
    }

    return $safe
}

function Start-Runtime {
    Repair-StalePid

    if (-not (Test-RuntimeConfiguration)) {
        throw "RUNTIME_VALIDATION_FAILED"
    }

    $portOpen = Test-RuntimePort $Port

    if ($portOpen) {
        $health = Get-RuntimeHealth

        if ($health.live) {
            Write-Host "ALREADY_RUNNING" -ForegroundColor Yellow
            Show-RuntimeStatus | Out-Null
            return
        }

        throw "PORT_IN_USE: $Port"
    }

    New-Item `
        -ItemType Directory `
        -Force `
        -Path $Logs |
        Out-Null

    Write-Host ""
    Write-Host "Iniciando IA Empresarial Local..." -ForegroundColor Cyan

    Rotate-RuntimeLog -Path $OutLog
    Rotate-RuntimeLog -Path $ErrLog

    $env:IA_LOCAL_ROOT = $RuntimeRoot

    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            ('"{0}"' -f $Analyzer),
            "--host",
            $HostAddress,
            "--port",
            "$Port"
        ) `
        -WorkingDirectory $RuntimeRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -PassThru

    Set-Content `
        -Path $PidFile `
        -Value $process.Id `
        -Encoding ASCII

    $deadline = (Get-Date).AddSeconds(45)

    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500

        if ($process.HasExited) {
            Remove-Item `
                $PidFile `
                -Force `
                -ErrorAction SilentlyContinue

            throw (
                "START_FAILED: el runtime termino durante el arranque. " +
                "Revisa $ErrLog"
            )
        }

        $health = Get-RuntimeHealth

        if ($health.live) {
            $listenerPid = Get-PortListenerPid -TargetPort $Port

            if (-not $listenerPid) {
                throw "START_FAILED: health responde pero no se encontro listener PID."
            }

            $listenerProcess = Get-OwnedAnalyzerProcess -ProcessId $listenerPid

            if (-not $listenerProcess) {
                throw "START_FAILED: el listener no corresponde a analizador_universal.py."
            }

            Set-Content `
                -Path $PidFile `
                -Value $listenerPid `
                -Encoding ASCII

            Write-Host "PID LISTENER REGISTRADO: $listenerPid" -ForegroundColor Green
            Write-Host "START: PASS" -ForegroundColor Green

            if ($health.ready) {
                Write-Host "READINESS: PASS" -ForegroundColor Green
            }
            else {
                Write-Host "READINESS: DEGRADED" -ForegroundColor Yellow
            }

            Show-RuntimeStatus | Out-Null
            return
        }
    }

    try {
        Stop-Process `
            -Id $process.Id `
            -Force `
            -ErrorAction SilentlyContinue
    }
    catch {}

    Remove-Item `
        $PidFile `
        -Force `
        -ErrorAction SilentlyContinue

    throw (
        "START_FAILED: timeout esperando liveness. " +
        "Revisa $ErrLog"
    )
}

function Stop-Runtime {
    Repair-StalePid

    $runtimePid = Get-RegisteredPid

    if (-not $runtimePid) {
        Write-Host "STOPPED: no hay runtime registrado." -ForegroundColor Yellow
        return
    }

    $owned = Get-RegisteredRuntimeProcess

    if (-not $owned) {
        Remove-Item `
            $PidFile `
            -Force `
            -ErrorAction SilentlyContinue

        Write-Host (
            "STALE_PID: se elimino el registro; no se termino ningun proceso."
        ) -ForegroundColor Yellow

        return
    }

    Write-Host "Deteniendo runtime PID $runtimePid..." -ForegroundColor Cyan

    Stop-Process `
        -Id $runtimePid `
        -Force `
        -ErrorAction Stop

    try {
        Wait-Process `
            -Id $runtimePid `
            -Timeout 15 `
            -ErrorAction SilentlyContinue
    }
    catch {}

    Remove-Item `
        $PidFile `
        -Force `
        -ErrorAction SilentlyContinue

    Write-Host "STOP: PASS" -ForegroundColor Green
}

function Show-Diagnostics {
    Repair-StalePid

    $runtimePid = Get-RegisteredPid
    $owned = Get-RegisteredRuntimeProcess
    $portOpen = Test-RuntimePort $Port
    $health = Get-RuntimeHealth

    $pythonVersion = $null

    try {
        $pythonVersion = (& $Python --version 2>&1 | Out-String).Trim()
    }
    catch {}

    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue

    $drive = Get-PSDrive `
        -Name ([System.IO.Path]::GetPathRoot($ProductRoot).TrimEnd('\').TrimEnd(':')) `
        -ErrorAction SilentlyContinue

    $diag = [ordered]@{
        product_root = $ProductRoot
        runtime_root = $RuntimeRoot
        python = $pythonVersion
        os = if ($os) { $os.Caption } else { $null }
        architecture = if ($cs) { $cs.SystemType } else { $null }
        pid = $runtimePid
        process_owned = [bool]$owned
        port = $Port
        port_listening = $portOpen
        health = @{
            live = $health.live
            ready = $health.ready
            version = $health.version
            motor = $health.motor
        }
        paths = @{
            analyzer = $Analyzer
            logs = $Logs
            out_log = $OutLog
            err_log = $ErrLog
        }
        disk_free_gb = if ($drive) {
            [math]::Round($drive.Free / 1GB, 2)
        } else {
            $null
        }
    }

    $diag | ConvertTo-Json -Depth 6
}

function New-DiagnosticBundle {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"

    $bundleRoot = Join-Path `
        $Logs `
        "diagnostics_$stamp"

    $zipPath = "$bundleRoot.zip"

    New-Item `
        -ItemType Directory `
        -Force `
        -Path $bundleRoot |
        Out-Null

    try {
        $diagFile = Join-Path $bundleRoot "diagnostics.json"

        $diagJson = (& powershell.exe `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $PSCommandPath `
            -Action diagnostics |
            Out-String)

        $diagJson = Protect-DiagnosticText $diagJson

        Set-Content `
            -Path $diagFile `
            -Value $diagJson `
            -Encoding UTF8

        foreach ($sourceLog in @($OutLog,$ErrLog)) {
            if (-not (Test-Path $sourceLog)) {
                continue
            }

            $target = Join-Path `
                $bundleRoot `
                ([System.IO.Path]::GetFileName($sourceLog))

            $raw = Get-Content `
                $sourceLog `
                -Raw `
                -ErrorAction SilentlyContinue

            $safe = Protect-DiagnosticText $raw

            Set-Content `
                -Path $target `
                -Value $safe `
                -Encoding UTF8
        }

        $versionFile = Join-Path $bundleRoot "runtime.txt"

        @(
            "Generated: $(Get-Date -Format o)"
            "ProductRoot: $ProductRoot"
            "RuntimeRoot: $RuntimeRoot"
            "Python: $Python"
            "Analyzer: $Analyzer"
            "Host: $HostAddress"
            "Port: $Port"
        ) |
        Set-Content `
            -Path $versionFile `
            -Encoding UTF8

        Compress-Archive `
            -Path "$bundleRoot\*" `
            -DestinationPath $zipPath `
            -Force

        Write-Host "DIAGNOSTIC BUNDLE: $zipPath" -ForegroundColor Green

        return $zipPath
    }
    finally {
        Remove-Item `
            $bundleRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

switch ($Action) {
    "backup" { if([string]::IsNullOrWhiteSpace($BackupPath)){exit 1}; & $Python $BackupEngine backup --runtime-root $ProductRoot --backup-path $BackupPath;exit $LASTEXITCODE }
    "restore" { if([string]::IsNullOrWhiteSpace($RestorePath)){exit 1}; & $Python $BackupEngine restore --runtime-root $ProductRoot --restore-path $RestorePath;exit $LASTEXITCODE }
    "configuration" {
        & $Python $Onboarding status --runtime-root $ProductRoot
        exit $LASTEXITCODE
    }

    "configure" {
        if (-not $env:IA_ONBOARDING_ADMIN_PASSWORD) {
            Write-Host "CONFIGURATION: REQUIRED (set IA_ONBOARDING_ADMIN_PASSWORD for this process)" -ForegroundColor Yellow
            exit 1
        }
        & $Python $Onboarding configure --runtime-root $ProductRoot --tenant-id $TenantId --tenant-name $TenantName --admin-user-id $AdminUserId --admin-username $AdminUsername --admin-display-name $AdminDisplayName
        exit $LASTEXITCODE
    }

    "configure-sql" {
        if (-not $AllowedSchemas -or -not $AllowedTables) { Write-Host "SQL allowlist schema/table requerida" -ForegroundColor Yellow; exit 1 }
        if ($AuthMode -eq 'SQL_AUTH' -and ([string]::IsNullOrWhiteSpace($SecretReference) -or [string]::IsNullOrWhiteSpace($SqlUsername))) { Write-Host "SQL_AUTH requiere username y secret reference" -ForegroundColor Yellow; exit 1 }
        $argsList = @($Onboarding, 'configure-sql', '--runtime-root', $ProductRoot, '--tenant-id', $TenantId, '--connection-id', $ConnectionId, '--server', $Server, '--database', $Database, '--auth-mode', $AuthMode)
        if ($AllowedSchemas -and $AllowedSchemas.Count -gt 0) { $argsList += @('--allowed-schemas', ($AllowedSchemas -join ',')) }
        if ($AllowedTables -and $AllowedTables.Count -gt 0) { $argsList += @('--allowed-tables', ($AllowedTables -join ',')) }
        if (-not [string]::IsNullOrWhiteSpace($SecretReference)) { $argsList += @('--secret-reference', $SecretReference) }
        if (-not [string]::IsNullOrWhiteSpace($SqlUsername)) { $argsList += @('--username', $SqlUsername) }
        & $Python @argsList
        exit $LASTEXITCODE
    }

    "configure-ai" {
        $argsList = @($Onboarding, 'configure-ai', '--runtime-root', $ProductRoot, '--tenant-id', $TenantId, '--provider', $Provider, '--timeout', $Timeout)
        if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) { $argsList += @('--base-url', $BaseUrl) }
        if (-not [string]::IsNullOrWhiteSpace($Model)) { $argsList += @('--model', $Model) }
        & $Python @argsList
        exit $LASTEXITCODE
    }

    "validate" {
        if (-not (Test-RuntimeConfiguration)) {
            exit 1
        }
    }

    "start" {
        Start-Runtime
    }

    "stop" {
        Stop-Runtime
    }

    "restart" {
        Stop-Runtime
        Start-Sleep -Seconds 1
        Start-Runtime
    }

    "status" {
        $status = Show-RuntimeStatus

        if ($status.state -notin @("RUNNING","RUNNING_UNMANAGED")) {
            exit 1
        }
    }

    "health" {
        $health = Get-RuntimeHealth
        $health | ConvertTo-Json -Depth 5

        if (-not $health.live) {
            exit 1
        }
    }

    "diagnostics" {
        Show-Diagnostics
    }

    "diagnostic-bundle" {
        New-DiagnosticBundle | Out-Null
    }
}













