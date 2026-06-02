@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [Quiz Solver] Verific Python...

set "PY_EXE="
where py >nul 2>&1 && set "PY_LAUNCHER=py -3"
if defined PY_LAUNCHER goto :have_py

where python >nul 2>&1 && set "PY_LAUNCHER=python"
if defined PY_LAUNCHER goto :have_py

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PY_LAUNCHER=%LocalAppData%\Programs\Python\Python312\python.exe"
    goto :have_py
)

echo Python nu este instalat. Incerc instalare automata (winget)...
where winget >nul 2>&1
if errorlevel 1 (
    echo Instaleaza Python manual: https://www.python.org/downloads/
    echo Bifeaza "Add python.exe to PATH", apoi ruleaza din nou setup.bat
    pause
    exit /b 1
)

winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Instalarea cu winget a esuat. Instaleaza Python manual.
    pause
    exit /b 1
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PY_LAUNCHER=%LocalAppData%\Programs\Python\Python312\python.exe"
    goto :have_py
)

echo Python instalat. Inchide fereastra, deschide una noua si ruleaza setup.bat
pause
exit /b 0

:have_py
echo [Quiz Solver] Creez mediul virtual...
if not exist ".venv\Scripts\python.exe" (
    %PY_LAUNCHER% -m venv .venv
    if errorlevel 1 (
        echo Nu am putut crea .venv
        pause
        exit /b 1
    )
)

echo [Quiz Solver] Instalez dependinte...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo pip install a esuat.
    pause
    exit /b 1
)

echo.
echo [Quiz Solver] Setup complet.
echo Ruleaza start.bat (sau duble-click pe start.bat)
echo.
exit /b 0
