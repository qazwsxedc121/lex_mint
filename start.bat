@echo off
echo ========================================
echo    LangGraph Agent - One Click Start
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run install.bat first
    pause
    exit /b 1
)

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed. Please run install.bat first
    pause
    exit /b 1
)

REM Check .env file
if not exist ".env" (
    echo [WARNING] .env file not found
    echo [TIP] API keys are configured in %USERPROFILE%\.lex_mint\keys_config.yaml
    echo.
    pause
)

REM Read ports from .env
set "API_PORT="
set "FRONTEND_PORT="
if exist .env (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_PORT= ^FRONTEND_PORT=" .env 2^>nul') do (
        if /I "%%a"=="API_PORT" set "API_PORT=%%b"
        if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
    )
)
if not defined API_PORT (
    echo [ERROR] API_PORT not set in .env
    pause
    exit /b 1
)
if not defined FRONTEND_PORT (
    echo [WARNING] FRONTEND_PORT not set in .env, fallback to 5173
    set "FRONTEND_PORT=5173"
)

echo [1/3] Starting backend service...
start "LangGraph Backend" cmd /k ".\venv\Scripts\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port %API_PORT%"
echo     Backend starting at http://localhost:%API_PORT%
timeout /t 3 >nul

echo.
echo [2/3] Starting frontend service...
start "LangGraph Frontend" cmd /k "cd frontend && npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT% --strictPort"
echo     Frontend starting at http://localhost:%FRONTEND_PORT%
timeout /t 3 >nul

echo.
echo [3/3] Waiting for services to be ready...
timeout /t 5 >nul

echo.
echo ========================================
echo    Services Started Successfully!
echo ========================================
echo.
echo Frontend:  http://localhost:%FRONTEND_PORT%
echo Backend:   http://localhost:%API_PORT%
echo API Docs:  http://localhost:%API_PORT%/docs
echo.
echo TIP: Closing this window will NOT stop services
echo      Use stop.bat to stop all services
echo      To change ports, edit API_PORT / FRONTEND_PORT in .env
echo ========================================
echo.

REM Auto open browser
timeout /t 3 >nul
start http://localhost:%FRONTEND_PORT%

pause
