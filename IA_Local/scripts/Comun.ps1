$ErrorActionPreference = "Stop"

$Root = "C:\IA_Local"
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$OpenWebUI = Join-Path $Venv "Scripts\open-webui.exe"
$OpenTerminal = Join-Path $Venv "Scripts\open-terminal.exe"
$AnalyzerScript = Join-Path $Root "scripts\analizador_universal.py"
$Requirements = Join-Path $Root "requirements-local.txt"
$ConfigDir = Join-Path $Root "config"
$DataDir = Join-Path $Root "data\open-webui"
$Workspace = Join-Path $Root "workspace"
$Logs = Join-Path $Root "logs"
$TerminalKeyFile = Join-Path $ConfigDir "open-terminal.key"
$TerminalConfig = Join-Path $ConfigDir "open-terminal.toml"
$EnterpriseConfig = Join-Path $ConfigDir "enterprise_ai.json"
$EnterpriseToken = Join-Path $ConfigDir "local-user.token"

function Ensure-Folders {
    @(
        $Root,
        $ConfigDir,
        $DataDir,
        $Workspace,
        (Join-Path $Workspace "Entrada"),
        (Join-Path $Workspace "Reportes"),
        (Join-Path $Workspace "Historico"),
        (Join-Path $Workspace "Conocimiento"),
        (Join-Path $Root "data\enterprise"),
        $Logs
    ) | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
        }
    }
}

function Find-Python311 {
    $candidates = @()

    try {
        $py = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $py) { $candidates += $py.Trim() }
    } catch {}

    $candidates += @(
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files (x86)\Python311\python.exe"
    )

    foreach ($c in ($candidates | Select-Object -Unique)) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

function Test-PythonExecutable([string]$Exe) {
    if (-not $Exe -or -not (Test-Path $Exe)) { return $false }
    try {
        & $Exe -c "import sys; print(sys.version_info[:2])" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-Port([int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $ar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $ar.AsyncWaitHandle.WaitOne(700, $false)
        if ($ok -and $client.Connected) {
            $client.EndConnect($ar)
            $client.Close()
            return $true
        }
        $client.Close()
    } catch {}
    return $false
}

function Wait-Port([int]$Port, [int]$Seconds = 60) {
    for ($i=0; $i -lt $Seconds; $i++) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-TerminalKey {
    Ensure-Folders
    if (-not (Test-Path $TerminalKeyFile)) {
        $key = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
        Set-Content -Path $TerminalKeyFile -Value $key -Encoding ASCII
    }
    return (Get-Content $TerminalKeyFile -Raw).Trim()
}

function Write-TerminalConfig {
    $key = Get-TerminalKey
    $cfg = @"
host = "127.0.0.1"
port = 8000
api_key = "$key"
log_dir = "$($Logs.Replace('\','\\'))"
max_terminal_sessions = 2
enable_terminal = true
enable_notebooks = true
execute_timeout = 300
execute_description = "Entorno local limitado a C:\\IA_Local\\workspace para analizar Excel, CSV y PDF y generar reportes. No inventes datos."
"@
    Set-Content -Path $TerminalConfig -Value $cfg -Encoding UTF8
}

function Start-OllamaIfNeeded {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Ollama no esta instalado o no aparece en PATH."
    }

    if (-not (Test-Port 11434)) {
        Write-Host "Iniciando Ollama..."
        Start-Process -FilePath $cmd.Source -ArgumentList "serve" -WindowStyle Hidden
        if (-not (Wait-Port 11434 30)) {
            throw "No fue posible iniciar Ollama en el puerto 11434."
        }
    }
}
