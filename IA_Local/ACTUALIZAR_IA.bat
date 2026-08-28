@echo off
title IA Empresarial Local - Actualizar
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Actualizar.ps1"
pause
