@echo off
REM Corre todas las pruebas sin abrir Facebook
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m agente validar
python -m agente vista-previa
python -m agente estado
pause
