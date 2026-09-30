@echo off
REM Instala el agente en Windows (requiere Python 3.10+ de python.org, con "Add to PATH" marcado)
cd /d "%~dp0"
python -m venv .venv || goto error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto error
python -m playwright install chromium || goto error
echo.
echo Listo. Siguiente paso: iniciar_sesion.bat
pause
exit /b 0
:error
echo Hubo un error durante la instalacion.
pause
exit /b 1
