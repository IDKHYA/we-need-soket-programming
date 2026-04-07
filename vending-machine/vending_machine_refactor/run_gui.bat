@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_EXE="

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
)

if not defined PYTHON_EXE (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    )
)

if not defined PYTHON_EXE (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)

if not defined PYTHON_EXE (
    if exist "%USERPROFILE%\anaconda3\python.exe" (
        set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

"%PYTHON_EXE%" "%~dp0run_gui.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch the vending machine.
    pause
    exit /b 1
)
