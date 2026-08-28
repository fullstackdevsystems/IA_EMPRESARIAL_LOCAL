@echo off
if exist "C:\IA_Local\config\local-user.token" (
  type "C:\IA_Local\config\local-user.token"
) else (
  echo Token no encontrado. Ejecuta INSTALAR_Y_ABRIR.bat.
)
echo.
pause
