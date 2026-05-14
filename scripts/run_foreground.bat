@echo off
REM Use this for manual testing - logs to the console, Ctrl+C to stop.
setlocal
cd /d "%~dp0\.."
set "PYTHONPATH=%CD%"
python -m app.main
endlocal
