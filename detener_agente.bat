@echo off
REM Cierra el agente que esta funcionando en segundo plano, de forma ordenada
REM (termina lo que esta haciendo para no dejar archivos a medio guardar).
cd /d "%~dp0"
if not exist datos\agente.pid (
  echo El agente no esta funcionando.
  pause
  exit /b 0
)
echo Pidiendo al agente que se detenga (puede tardar hasta 1 minuto)...
echo.> datos\DETENER
for /l %%i in (1,1,60) do (
  if not exist datos\agente.pid goto listo
  timeout /t 1 >nul
)
echo No respondio a tiempo: se cierra a la fuerza.
set /p PID=<datos\agente.pid
taskkill /PID %PID% /T /F >nul 2>nul
del datos\agente.pid >nul 2>nul
del datos\DETENER >nul 2>nul
:listo
echo Agente detenido. Para volver a iniciarlo: iniciar_en_segundo_plano.bat
pause
