@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p='C:\IA_Local\config\local-user.token'; if(Test-Path $p){$t=(Get-Content $p -Raw).Trim(); Start-Process ('http://127.0.0.1:8090/assistant#token='+[uri]::EscapeDataString($t))}else{Write-Host 'Falta token V8. Ejecuta INSTALAR_Y_ABRIR.bat.'; pause}"
