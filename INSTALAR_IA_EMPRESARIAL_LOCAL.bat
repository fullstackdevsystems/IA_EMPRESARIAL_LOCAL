@echo off
setlocal
cd /d "%~dp0"
title IA Empresarial Local - Instalacion

echo ====================================================
echo  IA EMPRESARIAL LOCAL
echo  INSTALADOR COMERCIAL
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
  echo ERROR: no se pudo instalar IA Empresarial Local.
  pause
  exit /b 1
)

echo.
echo Instalacion IA Empresarial Local completada.
pause
exit /b 0
