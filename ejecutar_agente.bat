@echo off
REM Deja el agente trabajando segun el calendario. Cerrar la ventana lo detiene.
REM Para que arranque solo al prender la PC: Win+R, escribir shell:startup y poner ahi un acceso directo a este archivo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt 2>nul
python -m agente ejecutar
pause
