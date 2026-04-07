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
if not exist "%~dp0data\server" mkdir "%~dp0data\server"
"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, uvicorn, httpx" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Missing server packages: fastapi, sqlalchemy, uvicorn, httpx
    pause
    exit /b 1
)
"%PYTHON_EXE%" -m vending_machine.server.runner --server-id server2 --database-url sqlite:///./data/server/server2.db --peer-server-id server1 --peer-sync-host 127.0.0.1 --peer-sync-port 9101 --sync-host 127.0.0.1 --sync-port 9102 --host 127.0.0.1 --port 8002
pause
