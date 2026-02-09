@echo off
echo ========================================
echo    Service Status Check
echo ========================================
echo.

REM Read port from .env
if exist .env (
    for /f "tokens=1,2 delims==" %%a in ('findstr /r "^API_PORT=" .env 2^>nul') do set API_PORT=%%b
)
if not defined API_PORT (
    echo [ERROR] API_PORT not set in .env
    pause
    exit /b 1
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
curl -s http://localhost:5173 >nul 2>&1
if %errorlevel% equ 0 (
    echo Status: Running
    echo URL: http://localhost:5173
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
