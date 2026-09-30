@echo off
REM Hace que el agente arranque solo (minimizado) cada vez que prendes la PC e iniciás sesion en Windows.
cd /d "%~dp0"
set "DESTINO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AgenteFacebook.bat"
> "%DESTINO%" echo @echo off
>> "%DESTINO%" echo cd /d "%~dp0"
>> "%DESTINO%" echo start "Agente Facebook" /min cmd /c ejecutar_agente.bat
echo Listo: el agente va a arrancar solo cada vez que prendas la PC.
echo Para desactivarlo, borra este archivo:
echo   %DESTINO%
pause
