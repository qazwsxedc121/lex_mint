@echo off
echo ========================================
echo    Service Status Check
echo ========================================
echo.

REM Read port from .env
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

echo [Backend Service]
curl -s http://localhost:%API_PORT%/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo Status: Running
    echo URL: http://localhost:%API_PORT%
    curl -s http://localhost:%API_PORT%/api/health
) else (
    echo Status: Not Running
)

echo.
echo [Frontend Service]
curl -s http://localhost:%FRONTEND_PORT% >nul 2>&1
if %errorlevel% equ 0 (
    echo Status: Running
    echo URL: http://localhost:%FRONTEND_PORT%
) else (
    echo Status: Not Running
)

echo.
echo [Session Statistics]
if exist "conversations" (
    for /f %%a in ('dir /b conversations\*.md 2^>nul ^| find /c ".md"') do (
        echo Conversation files: %%a
    )
) else (
    echo Conversations directory not found
)

echo.
echo ========================================
pause
