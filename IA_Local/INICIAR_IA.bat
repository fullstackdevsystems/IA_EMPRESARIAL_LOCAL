@echo off
title IA Empresarial Local
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Iniciar.ps1"
if errorlevel 1 (
  echo.
  echo Ocurrio un problema. Revisa la ventana anterior o C:\IA_Local\logs
  pause
)
