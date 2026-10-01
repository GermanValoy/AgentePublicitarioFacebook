@echo off
REM Arranca el agente OCULTO (sin ventana). Se controla desde Telegram (/estado, /pausar, /reanudar).
REM Para cerrarlo: detener_agente.bat   |   Si no arranca, mira datos\arranque.log y datos\agente.log
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo No esta instalado el agente en esta carpeta. Ejecuta instalar.bat
  pause
  exit /b 1
)
echo Actualizando componentes...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt >nul 2>&1
start "" .venv\Scripts\pythonw.exe -m agente ejecutar
echo Agente iniciado en segundo plano. En unos segundos te llega "Agente en marcha" a Telegram.
timeout /t 5 >nul
