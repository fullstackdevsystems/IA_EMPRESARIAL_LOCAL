. "$PSScriptRoot\Comun.ps1"

Write-Host "Deteniendo IA Empresarial Local..."

foreach ($name in @("open-webui","open-terminal","analizador")) {
    $pidFile = Join-Path $Logs "$name.pid"
    if (Test-Path $pidFile) {
        $processId = (Get-Content $pidFile -Raw).Trim()
        if ($processId -match '^\d+$') {
            try {
                & taskkill.exe /PID $processId /T /F | Out-Null
                Write-Host "$name detenido."
            } catch {}
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

try {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.CommandLine -like "*C:\IA_Local\.venv*open-webui*") -or
        ($_.CommandLine -like "*C:\IA_Local\.venv*open-terminal*") -or
        ($_.CommandLine -like "*C:\IA_Local*analizador_universal.py*") -or
        ($_.CommandLine -like "*C:\IA_Local*analizador_app.py*")
    } | ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }
} catch {}

Write-Host "Listo. Ollama se deja encendido porque puede ser usado por otras aplicaciones."
