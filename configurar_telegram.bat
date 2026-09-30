@echo off
REM Conecta un bot de Telegram para aprobar las publicaciones desde el celular o la PC (gratis).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m agente configurar-telegram
echo.
echo Si quedo conectado, cerra el agente (si estaba abierto) y abri de nuevo ejecutar_agente.bat
pause
