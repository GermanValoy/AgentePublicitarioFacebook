@echo off
REM Publica YA una publicacion del calendario. En modo aprobacion te la manda a Telegram para que la apruebes.
REM Respeta las reglas anti-baneo: horario, limite diario y descanso por grupo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt 2>nul
python -m agente sincronizar
echo.
echo Publicaciones disponibles:
python -m agente vista-previa | findstr /B "==="
echo.
set /p ID="Escribi el id de la publicacion (Enter = servicio-lunes): "
if "%ID%"=="" set ID=servicio-lunes
python -m agente publicar-ahora --id %ID%
pause
