@echo off
setlocal
title IA Empresarial Local - Desinstalar conservando datos
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DesinstalarIA.ps1" -InstallPath "%~dp0"
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo La desinstalacion no pudo completarse. Revisa el mensaje anterior.
) else (
  echo Desinstalacion completada. Los datos empresariales fueron conservados.
)
exit /b %EXITCODE%
