@echo off
setlocal

if not exist "%~dp0backend\venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup first...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

cd /d "%~dp0backend"
set "DEBUG=1"

"venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 exit /b 1

"venv\Scripts\python.exe" manage.py createcachetable
if errorlevel 1 exit /b 1

"venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
