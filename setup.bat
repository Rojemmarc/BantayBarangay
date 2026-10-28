@echo off
setlocal
cd /d "%~dp0backend"

if not exist "venv\Scripts\python.exe" (
    py -3 -m venv venv
    if errorlevel 1 (
        echo Failed to create the virtual environment. Install Python 3 and ensure the py launcher is available.
        exit /b 1
    )
)

"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

set "DEBUG=1"
"venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 exit /b 1

"venv\Scripts\python.exe" manage.py createcachetable
if errorlevel 1 exit /b 1

echo.
echo Setup complete. Run run.bat from the project folder to start BantayBarangay.
