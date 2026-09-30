@echo off
REM Conecta ESTA carpeta del agente con el repositorio de GitHub (se hace una sola vez).
REM Requiere Git para Windows: https://git-scm.com/download/win
cd /d "%~dp0"
set REPO=https://github.com/GermanValoy/AgentePublicitarioFacebook.git
set RAMA=claude/cool-einstein-1k9uxt

where git >nul 2>nul || (echo Primero instala Git desde https://git-scm.com/download/win y volve a ejecutar este archivo. & pause & exit /b 1)
if exist .git (echo Esta carpeta ya esta conectada a GitHub. & pause & exit /b 0)

echo Guardando una copia de seguridad de config y publicaciones en la carpeta "respaldo"...
xcopy /E /I /Y /Q config respaldo\config >nul
xcopy /E /I /Y /Q publicaciones respaldo\publicaciones >nul

git init -q || (echo Error al iniciar git. & pause & exit /b 1)
git remote add origin %REPO%
echo Descargando desde GitHub (si te pide iniciar sesion en GitHub, acepta)...
git fetch -q origin %RAMA% || (echo No se pudo descargar. Revisa tu internet o tu usuario de GitHub. & pause & exit /b 1)
git checkout -q -f -B %RAMA% origin/%RAMA% || (echo Error al preparar los archivos. & pause & exit /b 1)
git branch -q --set-upstream-to=origin/%RAMA%

if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
  pip install -q -r requirements.txt
  echo.
  echo Probando la sincronizacion. La primera vez se abre una ventana para iniciar sesion en GitHub.
  python -m agente sincronizar
) else (
  echo Falta instalar el agente: ejecuta instalar.bat
)
echo.
echo Listo. La carpeta quedo conectada con GitHub.
pause
