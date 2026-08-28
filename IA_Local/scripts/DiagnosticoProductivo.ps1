$ErrorActionPreference = "Continue"
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " IA EMPRESARIAL V8.5.5 - DIAGNOSTICO PRODUCTIVO" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
try { $v = Invoke-RestMethod http://127.0.0.1:8090/version -TimeoutSec 5; Write-Host "Version: $($v.version) / $($v.motor)" -ForegroundColor Green } catch { Write-Host "Version 8090: NO DISPONIBLE" -ForegroundColor Red }
try { $l = Invoke-RestMethod http://127.0.0.1:8090/api/enterprise/health/live -TimeoutSec 5; Write-Host "Liveness: $($l.status)" -ForegroundColor Green } catch { Write-Host "Liveness: ERROR" -ForegroundColor Red }
try { $r = Invoke-RestMethod http://127.0.0.1:8090/api/enterprise/health/ready -TimeoutSec 8; Write-Host "Readiness: $($r.status) | DB=$($r.database) | LLM=$($r.llm) | Vector=$($r.vector_store)" -ForegroundColor Green } catch { Write-Host "Readiness: DEGRADADO/ERROR" -ForegroundColor Yellow }
Write-Host ""
Write-Host "Modelos Ollama cargados:" -ForegroundColor Cyan
try { & ollama ps } catch { Write-Host "Ollama no disponible" -ForegroundColor Red }
Write-Host ""
Write-Host "Puertos esperados:" -ForegroundColor Cyan
foreach ($p in 11434,8090,8080) {
    try { $ok=(Test-NetConnection 127.0.0.1 -Port $p -WarningAction SilentlyContinue).TcpTestSucceeded } catch { $ok=$false }
    Write-Host ("  {0}: {1}" -f $p, $(if($ok){"OK"}else{"NO"}))
}
