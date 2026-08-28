@echo off
title IA Empresarial Local V8 - Pruebas
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno virtual. Ejecuta INSTALAR_Y_ABRIR.bat.
  pause
  exit /b 1
)
set IA_LOCAL_ROOT=%~dp0
".venv\Scripts\python.exe" "scripts\run_enterprise_tests.py"
pause
