@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE="
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [INFO] Checking required modules...
"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, uvicorn, httpx, openpyxl, PySide6" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing required Python packages.
    echo         Required: fastapi, sqlalchemy, uvicorn, httpx, openpyxl, PySide6
    echo         Auto-install is disabled.
    pause
    exit /b 1
)

echo [INFO] Opening server2 window...
start "Vending Server 2" "%~dp0run_server2.bat"
timeout /t 2 >nul
echo [INFO] Opening server1 window...
start "Vending Server 1" "%~dp0run_server1.bat"

echo.
echo [SERVER1] http://127.0.0.1:8001/docs
echo [SERVER2] http://127.0.0.1:8002/docs
echo.
echo [WORKBOOK CONFIG]
echo machine_id = VM-A
echo server_id = server1
echo server_api_base_url = http://127.0.0.1:8001
echo network_enabled = Y
echo.
echo [QUICK TEST]
echo python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx insert --amount 500
echo python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx buy --product-id P001
echo.
pause
