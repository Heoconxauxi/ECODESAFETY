@echo off
echo ================================================
echo      E-CODE SAFETY SYSTEM - AUTO START (WIN)
echo ================================================
echo.

REM 1) Tạo môi trường ảo
echo [1/5] Creating virtual environment...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Cannot create virtual environment
    exit /b 1
)
echo ✔ Virtual environment created.

REM 2) Kích hoạt môi trường
echo [2/5] Activating environment...
call venv\Scripts\activate
if "%VIRTUAL_ENV%"=="" (
    echo ❌ Failed to activate virtual environment.
    exit /b 1
)
echo ✔ Environment activated.

REM 3) Cài đặt thư viện
echo [3/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Failed to install dependencies
    exit /b 1
)
echo ✔ Dependencies installed.

REM 4) Chạy load_data.py
echo [4/5] Running load_data.py...
python load_data.py
if %ERRORLEVEL% NEQ 0 (
    echo ❌ load_data.py failed!
    exit /b 1
)
echo ✔ load_data.py completed.

REM 5) Chạy uvicorn
echo [5/5] Starting API server...
uvicorn api.main:app --reload

echo ================================================
echo           SERVER STOPPED / EXITED
echo ================================================
pause