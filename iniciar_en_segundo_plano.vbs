' Arranca el agente OCULTO (sin ventana). Se controla desde Telegram (/estado, /pausar, /reanudar).
' Para cerrarlo: detener_agente.bat   |   Registro de lo que hace: datos\agente.log
Set shell = CreateObject("WScript.Shell")
carpeta = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = carpeta
shell.Run "cmd /c "".venv\Scripts\pip.exe install -q -r requirements.txt >nul 2>&1 & .venv\Scripts\python.exe -m agente ejecutar""", 0, False
