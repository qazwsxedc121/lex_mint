@echo off
echo ========================================
echo    LangGraph Agent - Installation
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

echo [OK] Node.js is installed
echo.

REM Create virtual environment
if not exist "venv" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
    echo     Virtual environment created
) else (
    echo [1/4] Virtual environment exists, skipping
)

echo.
echo [2/4] Installing Python dependencies...
call venv\Scripts\activate
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies
    pause
    exit /b 1
)
echo     Python dependencies installed

echo.
echo [3/4] Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    pause
    exit /b 1
)
cd ..
echo     Frontend dependencies installed

echo.
echo [4/4] Checking configuration file...
if not exist ".env" (
    echo [WARNING] .env file not found
    copy .env.example .env >nul 2>&1
    echo     Please edit .env file for API_PORT/CORS settings if needed
    echo     API keys are stored in %USERPROFILE%\.lex_mint\keys_config.yaml
    echo.
    notepad .env
) else (
    echo     .env file exists
)

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Next step: Run start.bat to launch services
echo.
pause
