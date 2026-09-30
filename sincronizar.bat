@echo off
REM Sube tus fotos e ideas a GitHub y baja lo nuevo que preparo Claude.
REM (El agente tambien lo hace solo cada 30 minutos mientras esta andando.)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m agente sincronizar
pause
