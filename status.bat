@echo off
echo ========================================
echo    Service Status Check
echo ========================================
echo.

echo [Backend Service]
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo Status: Running
    echo URL: http://localhost:8000
    curl -s http://localhost:8000/api/health
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
