@echo off
REM Prueba real en Facebook SIN publicar: escribe, adjunta la foto, saca una captura y descarta.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m agente sincronizar
echo.
echo Publicaciones disponibles:
python -m agente vista-previa | findstr /B "==="
echo.
set /p ID="Escribi el id de la publicacion a probar (Enter = servicio-lunes): "
if "%ID%"=="" set ID=servicio-lunes
python -m agente simular --id %ID%
echo.
echo Mira la captura en la carpeta datos\capturas
pause
