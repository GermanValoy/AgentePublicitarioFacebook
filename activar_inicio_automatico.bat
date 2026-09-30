@echo off
REM Hace que el agente arranque solo y OCULTO (en segundo plano) cada vez que prendes la PC.
cd /d "%~dp0"
set "INICIO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
del "%INICIO%\AgenteFacebook.bat" >nul 2>nul
> "%INICIO%\AgenteFacebook.vbs" echo CreateObject("WScript.Shell").Run """%~dp0iniciar_en_segundo_plano.vbs""", 0, False
echo Listo: el agente va a arrancar solo y oculto cada vez que prendas la PC.
echo Te va a llegar "Agente en marcha" a Telegram cuando arranque.
echo.
echo Para desactivarlo, borra este archivo:
echo   %INICIO%\AgenteFacebook.vbs
pause
