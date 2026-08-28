@echo off
title IA Empresarial Local - Diagnostico
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Diagnostico.ps1"
pause
