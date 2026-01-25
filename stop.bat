@echo off
echo ========================================
echo    Stop All Services
echo ========================================
echo.

echo [1/2] Stopping backend service (uvicorn)...
taskkill /F /FI "WINDOWTITLE eq LangGraph Backend*" >nul 2>&1
if %errorlevel% equ 0 (
    echo     Backend service stopped
) else (
    echo     No running backend service found
)

echo.
echo [2/2] Stopping frontend service (npm)...
taskkill /F /FI "WINDOWTITLE eq LangGraph Frontend*" >nul 2>&1
if %errorlevel% equ 0 (
    echo     Frontend service stopped
) else (
    echo     No running frontend service found
)

echo.
echo ========================================
echo    All Services Stopped
echo ========================================
echo.
pause
