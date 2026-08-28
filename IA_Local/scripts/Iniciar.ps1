. "$PSScriptRoot\Comun.ps1"
Ensure-Folders

if (-not (Test-PythonExecutable $Python)) {
    Write-Host "La IA aun no esta instalada o el entorno Python esta danado." -ForegroundColor Yellow
    Write-Host "Ejecuta C:\IA_Local\INSTALAR_Y_ABRIR.bat para repararlo."
    exit 1
}
if (-not (Test-Path $OpenWebUI)) {
    Write-Host "Open WebUI no esta instalado. Ejecuta INSTALAR_Y_ABRIR.bat." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $AnalyzerScript)) {
    Write-Host "Falta scripts\analizador_universal.py. Vuelve a extraer el paquete completo." -ForegroundColor Red
    exit 1
}

Start-OllamaIfNeeded
Write-TerminalConfig
$key = Get-TerminalKey

# Garantiza que la BD persistente, config y token de V8 existan aun si se actualizo desde V7.
$env:IA_LOCAL_ROOT = $Root
& $Python "$PSScriptRoot\bootstrap_enterprise.py" --root $Root
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo inicializar la capa V8 de Memoria/RAG." -ForegroundColor Red
    exit 1
}

# V8.5.5: precalienta SOLO el LLM principal cuando runtime.warmup_llm=true. No precalienta embeddings;
# nomic-embed-text debe arrancar únicamente cuando una consulta realmente use RAG.
try {
    $warmModel = "qwen3:4b-instruct"
    $warmCtx = 2048
    $warmProvider = "ollama"
    $warmEnabled = $true
    $openTerminalEnabled = $false
    if (Test-Path $EnterpriseConfig) {
        $warmCfg = Get-Content $EnterpriseConfig -Raw | ConvertFrom-Json
        if ($warmCfg.llm.ollama_model) { $warmModel = [string]$warmCfg.llm.ollama_model }
        if ($warmCfg.llm.num_ctx) { $warmCtx = [int]$warmCfg.llm.num_ctx }
        if ($warmCfg.llm.provider) { $warmProvider = [string]$warmCfg.llm.provider }
        if ($null -ne $warmCfg.runtime.warmup_llm) { $warmEnabled = [bool]$warmCfg.runtime.warmup_llm }
        if ($null -ne $warmCfg.runtime.open_terminal_enabled) { $openTerminalEnabled = [bool]$warmCfg.runtime.open_terminal_enabled }
    }
    if ($warmProvider -eq "ollama" -and $warmEnabled) {
        Write-Host "Precalentando modelo Ollama $warmModel (contexto $warmCtx)..."
        $warmBody = @{
            model = $warmModel
            prompt = ""
            stream = $false
            keep_alive = "30m"
            options = @{ num_ctx = $warmCtx }
        } | ConvertTo-Json -Depth 5
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -ContentType "application/json" -Body $warmBody -TimeoutSec 180 | Out-Null
        Write-Host "Modelo principal precalentado." -ForegroundColor Green
    }
} catch {
    Write-Host "ADVERTENCIA: no se pudo precalentar el LLM. La IA continuara y lo cargara en la primera consulta." -ForegroundColor Yellow
}

# Open Terminal: opcional. En modo productivo queda desactivado por defecto para
# eliminar un servicio innecesario y evitar warnings/puertos adicionales.
if ($openTerminalEnabled -and (Test-Path $OpenTerminal)) {
    if (-not (Test-Port 8000)) {
        Write-Host "Iniciando Open Terminal (herramientas de archivos)..."
        $otOut = Join-Path $Logs "open-terminal.out.log"
        $otErr = Join-Path $Logs "open-terminal.err.log"
        $p = Start-Process -FilePath $OpenTerminal `
            -ArgumentList @("run","--config",$TerminalConfig,"--cwd",$Workspace) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $otOut `
            -RedirectStandardError $otErr `
            -PassThru
        Set-Content (Join-Path $Logs "open-terminal.pid") $p.Id
        if (-not (Wait-Port 8000 30)) {
            Write-Host "Open Terminal no respondio. El analizador directo sigue disponible. Revisa $otErr" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Open Terminal: ya iniciado." -ForegroundColor Green
    }
} elseif (-not $openTerminalEnabled) {
    Write-Host "Open Terminal: desactivado en configuracion productiva." -ForegroundColor DarkGray
}

# Analizador universal de archivos grandes. Verifica que NO quede una version vieja escuchando en 8090.
$AnalyzerExpectedVersion = "8.5.5"
$AnalyzerExpectedMotor = "universal-profesional-memoria-rag"
$restartAnalyzer = $true
if (Test-Port 8090) {
    try {
        $v = Invoke-RestMethod -Uri "http://127.0.0.1:8090/version" -TimeoutSec 3
        if ($v.version -eq $AnalyzerExpectedVersion -and $v.motor -eq $AnalyzerExpectedMotor) {
            Write-Host ("Analizador Universal V{0}: ya iniciado." -f $AnalyzerExpectedVersion) -ForegroundColor Green
            $restartAnalyzer = $false
        } else {
            Write-Host "Se detecto un analizador anterior en el puerto 8090. Se reiniciara para cargar V$AnalyzerExpectedVersion..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "El puerto 8090 esta ocupado por una version anterior/no identificada. Se intentara reiniciar el analizador local..." -ForegroundColor Yellow
    }
}

if ($restartAnalyzer) {
    # Primero mata PID registrado si existe.
    $pidFile = Join-Path $Logs "analizador.pid"
    if (Test-Path $pidFile) {
        $oldPid = (Get-Content $pidFile -Raw).Trim()
        if ($oldPid -match '^\d+$') {
            try { & taskkill.exe /PID $oldPid /T /F | Out-Null } catch {}
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    # Tambien elimina procesos viejos de V2/V3/V4/V5 de este producto.
    try {
        Get-CimInstance Win32_Process | Where-Object {
            ($_.CommandLine -like "*C:\IA_Local*analizador_app.py*") -or
            ($_.CommandLine -like "*C:\IA_Local*analizador_universal.py*")
        } | ForEach-Object {
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
        }
    } catch {}
    Start-Sleep -Seconds 1

    if (Test-Port 8090) {
        Write-Host "ERROR: El puerto 8090 sigue ocupado por otro proceso." -ForegroundColor Red
        Write-Host "Ejecuta DETENER_IA.bat o revisa que aplicacion usa el puerto 8090."
        exit 2
    }

    Write-Host "Iniciando Analizador Universal Empresarial V$AnalyzerExpectedVersion..."
    $env:IA_LOCAL_ROOT = $Root
    $env:OLLAMA_URL = "http://127.0.0.1:11434"
    # V8.5.5: nunca forzar un modelo viejo. El analizador hereda el modelo
    # persistido en enterprise_ai.json.
    $env:OLLAMA_MODEL = "qwen3:4b-instruct"
    try {
        if (Test-Path $EnterpriseConfig) {
            $runtimeCfg = Get-Content $EnterpriseConfig -Raw | ConvertFrom-Json
            if ($runtimeCfg.llm.ollama_model) { $env:OLLAMA_MODEL = [string]$runtimeCfg.llm.ollama_model }
        }
    } catch {
        Write-Host "ADVERTENCIA: no se pudo leer el modelo de enterprise_ai.json; se usara qwen3:4b-instruct." -ForegroundColor Yellow
    }
    $anOut = Join-Path $Logs "analizador.out.log"
    $anErr = Join-Path $Logs "analizador.err.log"
    $pa = Start-Process -FilePath $Python `
        -ArgumentList @($AnalyzerScript,"--host","127.0.0.1","--port","8090") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $anOut `
        -RedirectStandardError $anErr `
        -PassThru
    Set-Content (Join-Path $Logs "analizador.pid") $pa.Id
    if (-not (Wait-Port 8090 45)) {
        Write-Host "El Analizador Universal no respondio." -ForegroundColor Red
        Write-Host "Revisa: $anErr"
        exit 2
    }
    try {
        $v = Invoke-RestMethod -Uri "http://127.0.0.1:8090/version" -TimeoutSec 5
        if ($v.version -ne $AnalyzerExpectedVersion -or $v.motor -ne $AnalyzerExpectedMotor) { throw "Version/motor incorrecto" }
        Write-Host "Analizador Universal V$($v.version) confirmado." -ForegroundColor Green
        try {
            $ready = Invoke-RestMethod -Uri "http://127.0.0.1:8090/api/enterprise/health/ready" -TimeoutSec 5
            if ($ready.ok) { Write-Host "Readiness productivo: OK." -ForegroundColor Green }
        } catch {
            Write-Host "ADVERTENCIA: readiness productivo degradado. Revisa /api/enterprise/health/ready" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "ERROR: El servicio inicio, pero no se pudo confirmar V$AnalyzerExpectedVersion." -ForegroundColor Red
        exit 2
    }
}

# Open WebUI
if (-not (Test-Port 8080)) {
    Write-Host "Iniciando Open WebUI..."
    $env:DATA_DIR = $DataDir
    $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
    $env:ENABLE_OLLAMA_API = "True"
    $env:ENABLE_OPENAI_API = "False"
    $env:WEBUI_NAME = "IA Empresarial Local"
    $env:RAG_FILE_MAX_SIZE = "250"
    $env:ENABLE_COMMUNITY_SHARING = "False"
    $env:TERMINAL_SERVER_CONNECTIONS = "[{`"id`":`"local-terminal`",`"name`":`"Archivos y reportes`",`"url`":`"http://127.0.0.1:8000`",`"key`":`"$key`",`"auth_type`":`"bearer`",`"config`":{`"access_grants`":[]}}]"

    $owOut = Join-Path $Logs "open-webui.out.log"
    $owErr = Join-Path $Logs "open-webui.err.log"
    $p2 = Start-Process -FilePath $OpenWebUI `
        -ArgumentList @("serve","--host","127.0.0.1","--port","8080") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $owOut `
        -RedirectStandardError $owErr `
        -PassThru
    Set-Content (Join-Path $Logs "open-webui.pid") $p2.Id

    Write-Host "Esperando a Open WebUI..."
    if (-not (Wait-Port 8080 150)) {
        Write-Host "Open WebUI no respondio a tiempo." -ForegroundColor Red
        Write-Host "Revisa: $owErr"
        exit 3
    }
} else {
    Write-Host "Open WebUI: ya iniciado." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host " IA EMPRESARIAL LOCAL LISTA" -ForegroundColor Green
Write-Host " Chat:       http://127.0.0.1:8080" -ForegroundColor Green
Write-Host " Analizador:  http://127.0.0.1:8090" -ForegroundColor Green
Write-Host " Asistente:   http://127.0.0.1:8090/assistant" -ForegroundColor Green
Write-Host " Memoria/RAG: http://127.0.0.1:8090/admin" -ForegroundColor Green
Write-Host " Entrada:    C:\IA_Local\workspace\Entrada" -ForegroundColor Green
Write-Host " Reportes:   C:\IA_Local\workspace\Reportes" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Para Excel grandes (por ejemplo 40 MB o cientos de miles de filas), usa el Analizador en el puerto 8090."
Write-Host "No adjuntes esos Excel directamente al chat de Open WebUI: su cargador documental aplica limites de seguridad al XLSX descomprimido."
Write-Host ""

if (Test-Path $EnterpriseToken) {
    $tok = (Get-Content $EnterpriseToken -Raw).Trim()
    Start-Process ("http://127.0.0.1:8090/assistant#token=" + [uri]::EscapeDataString($tok))
} else {
    Start-Process "http://127.0.0.1:8090"
}
