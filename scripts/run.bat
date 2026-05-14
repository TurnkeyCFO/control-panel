@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHONPATH=%CD%"
start "" /B pythonw -m app.main >> "%LOCALAPPDATA%\turnkey-cp\stderr.log" 2>&1
endlocal
