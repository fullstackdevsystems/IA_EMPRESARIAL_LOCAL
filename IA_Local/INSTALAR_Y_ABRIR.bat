@echo off
title IA Empresarial Local - Instalacion
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Instalar.ps1"
echo.
echo Presiona una tecla para cerrar...
pause >nul
