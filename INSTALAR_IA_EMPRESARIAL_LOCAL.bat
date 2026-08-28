@echo off
setlocal
cd /d "%~dp0"
title IA Empresarial Local V8.5.5 R7 - Instalacion Limpia Corregida V2

echo ====================================================
echo  IA EMPRESARIAL LOCAL V8.5.5 R7
echo  INSTALADOR COMPLETO LIMPIO - CORREGIDO V2
echo ====================================================
echo.
echo Validando sintaxis del instalador PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ValidarInstalador.ps1"
if errorlevel 1 (
  echo.
  echo ERROR: el instalador PowerShell no paso la validacion previa.
  pause
  exit /b 1
)

echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0InstalarLimpio.ps1"
if errorlevel 1 (
  echo.
  echo ERROR: no se pudo instalar IA Empresarial Local V8.5.5 R7.
  pause
  exit /b 1
)

echo.
echo Instalacion IA Empresarial Local V8.5.5 R7 completada.
pause
exit /b 0
