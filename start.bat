@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Prima rulare: rulez setup...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

set "API_KEY="
if not "%~1"=="" (
    set "API_KEY=%~1"
    goto :run
)

if exist "api_key.local" (
    set /p API_KEY=<api_key.local
    goto :run
)

".venv\Scripts\python.exe" quiz_solver.py
goto :eof

:run
".venv\Scripts\python.exe" quiz_solver.py "%API_KEY%"
