@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHONPATH=%CD%"
pythonw "%~dp0start_tunnel.py" >> "%LOCALAPPDATA%\turnkey-cp\tunnel.log" 2>&1
endlocal
