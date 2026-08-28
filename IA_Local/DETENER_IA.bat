@echo off
title IA Empresarial Local - Detener
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Detener.ps1"
pause
