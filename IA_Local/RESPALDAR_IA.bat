@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\BackupIA.ps1"
if errorlevel 1 (
  echo ERROR creando respaldo.
  pause
  exit /b 1
)
pause
