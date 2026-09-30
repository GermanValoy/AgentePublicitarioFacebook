@echo off
REM Cierra el agente que esta funcionando en segundo plano.
cd /d "%~dp0"
if not exist datos\agente.pid (
  echo El agente no esta funcionando.
  pause
  exit /b 0
)
set /p PID=<datos\agente.pid
taskkill /PID %PID% /T /F >nul 2>nul
del datos\agente.pid >nul 2>nul
echo Agente detenido. Para volver a iniciarlo: iniciar_en_segundo_plano.vbs
pause
