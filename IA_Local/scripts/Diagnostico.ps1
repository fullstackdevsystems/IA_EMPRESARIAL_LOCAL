. "$PSScriptRoot\Comun.ps1"

Write-Host "===================================================="
Write-Host " DIAGNOSTICO - IA EMPRESARIAL LOCAL V8 MEMORIA + RAG"
Write-Host "===================================================="
Write-Host ""

try {
    $cs = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    Write-Host "CPU: $($cpu.Name)"
    Write-Host "RAM: $ramGB GB"
    Write-Host "Windows: $($os.Caption) $($os.Version)"
} catch { Write-Host "No fue posible leer todos los datos del equipo." }

Write-Host ""
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama:"
    try { & ollama --version } catch {}
    Write-Host "Modelos:"
    try { & ollama list } catch {}
} else { Write-Host "Ollama: NO DETECTADO" }

Write-Host ""
if (Test-PythonExecutable $Python) {
    Write-Host "Python del entorno:"
    & $Python --version
    Write-Host "Vector store disponible:"
    $env:IA_LOCAL_ROOT = $Root
    try { & $Python "$PSScriptRoot\bootstrap_enterprise.py" --root $Root } catch {}
} else {
    Write-Host "Python del entorno: NO VALIDO - ejecuta INSTALAR_Y_ABRIR.bat para repararlo" -ForegroundColor Red
}

Write-Host ""
Write-Host "Puertos:"
Write-Host ("  Ollama 11434:       " + $(if (Test-Port 11434) {"ACTIVO"} else {"INACTIVO"}))
Write-Host ("  Open Terminal 8000: " + $(if (Test-Port 8000) {"ACTIVO"} else {"INACTIVO"}))
Write-Host ("  Open WebUI 8080:    " + $(if (Test-Port 8080) {"ACTIVO"} else {"INACTIVO"}))
Write-Host ("  V8 API 8090:        " + $(if (Test-Port 8090) {"ACTIVO"} else {"INACTIVO"}))

Write-Host ""
Write-Host "Persistencia:"
Write-Host ("  BD memoria/auditoria: " + $(if (Test-Path "C:\IA_Local\data\enterprise\enterprise_ai.sqlite3") {"OK"} else {"NO CREADA"}))
Write-Host ("  Token local:           " + $(if (Test-Path $EnterpriseToken) {"OK"} else {"NO CREADO"}))
Write-Host ("  Conocimiento:          C:\IA_Local\workspace\Conocimiento")
Write-Host ("  Reportes:              C:\IA_Local\workspace\Reportes")

if (Test-Port 8090) {
    try {
        $v = Invoke-RestMethod -Uri "http://127.0.0.1:8090/version" -TimeoutSec 5
        Write-Host "Version API: $($v.version) | Motor=$($v.motor)" -ForegroundColor Green
    } catch { Write-Host "Puerto 8090 activo pero fallo /version." -ForegroundColor Yellow }
    if (Test-Path $EnterpriseToken) {
        try {
            $tok = (Get-Content $EnterpriseToken -Raw).Trim()
            $headers = @{ Authorization = "Bearer $tok" }
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:8090/api/enterprise/health" -Headers $headers -TimeoutSec 5
            Write-Host "Enterprise V8: OK | LLM=$($h.llm_provider)/$($h.llm_model) | embeddings=$($h.embedding_model) | vector=$($h.vector_store)" -ForegroundColor Green
        } catch { Write-Host "Enterprise V8 responde con error. Revisa logs\analizador.err.log" -ForegroundColor Yellow }
    }
}
