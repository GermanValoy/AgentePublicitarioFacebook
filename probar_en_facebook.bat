@echo off
REM Prueba real en Facebook SIN publicar: escribe, adjunta la foto, saca una captura y descarta.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt 2>nul
python -m agente sincronizar
echo.
echo Publicaciones disponibles:
python -m agente vista-previa | findstr /B "==="
echo.
set /p ID="Escribi el id de la publicacion a probar (Enter = servicio-lunes): "
if "%ID%"=="" set ID=servicio-lunes
python -m agente simular --id %ID%
echo.
echo Subiendo el resultado de la prueba para que Claude lo revise...
python -m agente reporte >nul
python -m agente sincronizar
echo.
echo Mira la captura en la carpeta datos\capturas
pause
